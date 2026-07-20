"""Agent lifecycle: run, resume, stop — the core orchestration layer."""

import asyncio
import os
import traceback

# Disable browser_use's built-in CLI pause prompt (blocks on stdin in a service)
os.environ["BROWSER_USE_NO_INTERACTIVE"] = "1"

from browser_use import Agent

from app.config import settings
from app.core.state import agent_state
from app.core.exceptions import NoActiveAgentError
from app.models.requests import TaskRequest, ResumeRequest, StopRequest
from app.models.responses import TaskResponse
from app.services import llm_service, browser_service, whatsapp_service


# ---------------------------------------------------------------------------
# Step-end hook factory — accumulates silently, sends ONE consolidated msg
# ---------------------------------------------------------------------------
def _make_step_hook(max_steps: int):
    """Return an on_step_end callback that accumulates steps silently,
    then sends ONE consolidated message at each pause point."""

    steps_log: list[str] = []  # accumulated silently between pauses

    async def on_step_end(agent_instance: Agent):
        nonlocal steps_log
        step_num = agent_instance.state.n_steps
        agent_state.step = step_num

        # --- Safe URL extraction ---
        try:
            pages = await agent_instance.browser_session.get_pages()
            current_url = pages[-1].url if pages else "unknown"
        except Exception:
            current_url = "unknown"

        # --- Safe thought extraction ---
        try:
            thoughts = agent_instance.history.model_thoughts()
            last_thought = str(thoughts[-1]) if thoughts else "thinking..."
        except Exception:
            last_thought = "processing..."

        # --- Safe action extraction (human-readable label) ---
        try:
            actions = agent_instance.history.model_actions()
            action_obj = actions[-1] if actions else None
            label = whatsapp_service._action_label(action_obj) if action_obj else "..."
        except Exception:
            label = "..."

        # --- Accumulate silently (no per-step WhatsApp message) ---
        steps_log.append(f"• Step {step_num}: {label}")

        # --- Pause every N steps — send ONE consolidated message ---
        pause_interval = settings.pause_every_n_steps
        if step_num > 0 and step_num % pause_interval == 0:
            agent_state.paused = True
            await whatsapp_service.send_consolidated_pause(
                step=step_num,
                max_steps=max_steps,
                current_url=current_url,
                current_thought=last_thought,
                steps_log=steps_log,
            )
            steps_log.clear()

            # Wait until resumed by the /resume endpoint
            while agent_state.paused:
                await asyncio.sleep(0.5)

        # --- Hard stop at max_steps ---
        if step_num >= max_steps:
            await whatsapp_service.send_message(
                f"🛑 Reached max {max_steps} steps."
            )

    return on_step_end


# ---------------------------------------------------------------------------
# Pre-flight planning — ask the LLM for a strategy before executing
# ---------------------------------------------------------------------------
async def _generate_plan(task: str, llm) -> str | None:
    """Generate a concise execution plan for user approval."""
    plan_prompt = (
        "You are a browser automation planner. Given the task below, outline "
        "your approach in 4-8 bullet points. Keep each bullet under 60 words.\n\n"
        "Cover:\n"
        "1. Initial search strategy (what to search, which engine)\n"
        "2. Target websites to visit (in order)\n"
        "3. Data to extract (prices, names, availability, etc.)\n"
        "4. Expected challenges (CAPTCHAs, dynamic pages, etc.)\n"
        "5. Stopping criteria (when is the task complete?)\n\n"
        f"Task: {task}\n\n"
        "Plan:"
    )

    try:
        resp = await llm.ainvoke(plan_prompt)
        return resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        print(f"[Plan] Could not generate plan: {e}")
        return None


# ---------------------------------------------------------------------------
# Extract success/failure verdict from agent result
# ---------------------------------------------------------------------------
def _result_verdict(result) -> str:
    """Get verdict from the agent result object."""
    try:
        if hasattr(result, "is_successful"):
            status = "✅ SUCCESS" if result.is_successful() else "❌ FAILED"
            return status
    except Exception:
        pass
    return "⚠️ UNKNOWN"


def _result_judge_reason(result) -> str:
    """Get the judge's failure reason if available."""
    try:
        if hasattr(result, "judge_reason") and result.judge_reason():
            return result.judge_reason()[:500]
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# run — start a new agent task
# ---------------------------------------------------------------------------
async def run(req: TaskRequest) -> None:
    """Full agent lifecycle for a new task. Runs as a background asyncio task."""
    if agent_state.agent is not None:
        await whatsapp_service.send_message("⚠️ Agent is already running.")
        return

    try:
        # --- 1. Build LLM ---
        provider_arg = llm_service.resolve_provider_arg(req.provider, req.provider_model)
        llm = llm_service.get_llm(provider_arg)

        # Fallback: non-Gemini providers get a Gemini safety net
        fallback_llm = None
        if not provider_arg.startswith("gemini"):
            try:
                fallback_llm = llm_service.get_fallback_llm()
            except Exception as e:
                print(f"[WARNING] Could not configure fallback LLM: {e}")

        # --- 2. Set up browser (Agent handles start/stop internally) ---
        profile = browser_service.create_browser_profile()
        browser_session = browser_service.create_browser_session(profile)

        # --- 3. Create agent ---
        agent = Agent(
            task=req.task,
            llm=llm,
            browser_session=browser_session,
            use_vision=True,
            extend_system_message=llm_service.SEARCH_ENGINE_OVERRIDE,
            fallback_llm=fallback_llm,
        )
        agent_state.agent = agent
        agent_state.task = req.task
        agent_state.step = 0
        agent_state.paused = False
        agent_state.provider = provider_arg

        await whatsapp_service.send_message(
            f"🚀 *Starting task:* {req.task}\n"
            f"🧠 Provider: {provider_arg}\n"
            f"📏 Max steps: {req.max_steps}"
        )

        # --- 4. Pre-flight plan ---
        plan = await _generate_plan(req.task, llm)
        if plan:
            await whatsapp_service.send_message(
                f"📋 *Execution Plan*\n\n{plan[:1000]}\n\n"
                f"▶️ Running now..."
            )

        # --- 5. Run agent ---
        max_steps = req.max_steps or settings.default_max_steps
        result = await agent.run(
            max_steps=max_steps,
            on_step_end=_make_step_hook(max_steps),
        )

        # --- 6. Final result with verdict ---
        verdict = _result_verdict(result)
        judge_reason = _result_judge_reason(result)

        try:
            final = result.final_result() or "Task complete, no result extracted."
        except Exception:
            final = "Task complete, no result extracted."

        message = f"✅ *Done!*\n\n{final[:1000]}"
        if judge_reason:
            message += f"\n\n📝 *Verdict:* {verdict}\n{judge_reason[:400]}"
        await whatsapp_service.send_message(message)

    except Exception as e:
        print(f"[Agent] Error during run: {traceback.format_exc()}")
        await whatsapp_service.send_error(e)

    finally:
        agent_state.agent = None
        agent_state.task = None
        agent_state.step = 0
        agent_state.paused = False
        agent_state.provider = None


# ---------------------------------------------------------------------------
# resume — continue a paused agent, optionally with new instructions
# ---------------------------------------------------------------------------
async def resume(req: ResumeRequest) -> TaskResponse:
    """Resume a paused agent, optionally injecting a new instruction."""
    if agent_state.agent is None:
        return TaskResponse(status="error", message="No active agent")

    if req.instruction:
        try:
            agent_state.agent.add_new_task(req.instruction)
            await whatsapp_service.send_message(
                f"📝 Updated task: {req.instruction}"
            )
        except Exception as e:
            return TaskResponse(
                status="error",
                message=f"Could not add task: {e}",
            )

    agent_state.agent.resume()
    agent_state.paused = False
    await whatsapp_service.send_message("▶️ Resuming...")

    return TaskResponse(status="resumed", task=agent_state.task or "")


# ---------------------------------------------------------------------------
# stop — clear state (no agent.pause() — it blocks on stdin)
# ---------------------------------------------------------------------------
async def stop(req: StopRequest) -> TaskResponse:
    """Stop the running agent."""
    if agent_state.agent is None:
        return TaskResponse(status="error", message="No active agent")

    reason = f" — {req.reason}" if req.reason else ""
    agent_state.agent = None
    agent_state.task = None
    agent_state.step = 0
    agent_state.paused = False
    agent_state.provider = None

    await whatsapp_service.send_message(f"🛑 Agent stopped.{reason}")

    return TaskResponse(status="stopped")