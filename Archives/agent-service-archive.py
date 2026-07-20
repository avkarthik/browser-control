# agent_service.py
import asyncio
import aiohttp
from aiohttp import web
import os
from dotenv import load_dotenv
from browser_use import Agent, BrowserProfile, BrowserSession
from browser_use import ChatGoogle
from browser_use.browser.profile import ViewportSize
from playwright_stealth import Stealth

load_dotenv()

HA_URL = os.getenv("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.getenv("HA_TOKEN")
WHATSAPP_NOTIFY_SERVICE = "notify.whatsapp"  # your HA notify service name

# ---- Send message back via HA ----
async def send_whatsapp(message: str):
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"message": message}
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"{HA_URL}/api/services/{WHATSAPP_NOTIFY_SERVICE.replace('.', '/')}",
            json=payload,
            headers=headers,
        )

# ---- browser-use step hook ----
def make_step_hook(max_steps: int):
    async def on_step_end(agent: Agent):
        step_num = agent.state.n_steps
        
        # Get current state summary
        state = await agent.browser_session.get_browser_state_summary()
        thoughts = agent.history.model_thoughts()
        last_thought = thoughts[-1] if thoughts else "..."
        actions = agent.history.model_actions()
        last_action = str(actions[-1]) if actions else "..."

        # Build update message
        update = (
            f"🔄 *Step {step_num}/{max_steps}*\n"
            f"🌐 URL: {state.url}\n"
            f"💭 {last_thought[:200]}\n"
            f"⚡ Action: {last_action[:150]}"
        )
        await send_whatsapp(update)

        # Pause at step 5 to ask for guidance
        if step_num == 5:
            agent.pause()
            await send_whatsapp(
                f"⏸️ *Paused at step 5* — should I continue?\n"
                f"Reply *continue* to proceed, or give me a new instruction."
            )
            # Wait for resume signal (set by /resume endpoint)
            while agent.state.paused:
                await asyncio.sleep(1)

        # Hard stop at max_steps
        if step_num >= max_steps:
            await send_whatsapp(f"🛑 Reached {max_steps} steps. Stopping.")

    return on_step_end

# ---- Agent runner ----
active_agent: Agent | None = None

async def run_agent(task: str, max_steps: int = 10):
    global active_agent

    browser_profile = BrowserProfile(
        headless=False,
        disable_security=False,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        window_size=ViewportSize(width=1280, height=800),
        wait_between_actions=2.0,
        minimum_wait_page_load_time=2.0,
    )
    browser_session = BrowserSession(browser_profile=browser_profile)
    await browser_session.start()

    # Apply stealth
    stealth = Stealth(chrome_runtime=True)
    await stealth.apply_stealth_async(browser_session.context)

    llm = ChatGoogle(model="gemini-flash-latest")

    agent = Agent(
        task=task,
        llm=llm,
        browser_session=browser_session,
    )
    active_agent = agent

    await send_whatsapp(f"🚀 *Starting task:* {task}\nMax steps: {max_steps}")

    try:
        result = await agent.run(
            max_steps=max_steps,
            on_step_end=make_step_hook(max_steps),
        )
        final = result.final_result() or "Task complete, no result extracted."
        await send_whatsapp(f"✅ *Done!*\n\n{final[:1500]}")
    except Exception as e:
        await send_whatsapp(f"❌ Agent error: {str(e)}")
    finally:
        active_agent = None
        await browser_session.stop()

# ---- HTTP endpoints ----
async def handle_task(request: web.Request):
    """Called by HA when you send a WhatsApp message."""
    data = await request.json()
    task = data.get("task", "").strip()
    max_steps = int(data.get("max_steps", 10))

    if not task:
        return web.json_response({"error": "No task provided"}, status=400)

    # Fire-and-forget — don't block the HTTP response
    asyncio.create_task(run_agent(task, max_steps))
    return web.json_response({"status": "started", "task": task})

async def handle_resume(request: web.Request):
    """Called by HA when you reply 'continue' on WhatsApp."""
    global active_agent
    data = await request.json()
    new_instruction = data.get("instruction", "")

    if active_agent is None:
        return web.json_response({"error": "No active agent"}, status=404)

    if new_instruction:
        # Inject a new instruction before resuming
        active_agent.add_new_task(new_instruction)
        await send_whatsapp(f"📝 Updated task: {new_instruction}")

    active_agent.resume()
    await send_whatsapp("▶️ Resuming...")
    return web.json_response({"status": "resumed"})

async def handle_stop(request: web.Request):
    global active_agent
    if active_agent:
        active_agent.pause()
        await send_whatsapp("🛑 Agent stopped.")
    return web.json_response({"status": "stopped"})

app = web.Application()
app.router.add_post("/task", handle_task)
app.router.add_post("/resume", handle_resume)
app.router.add_post("/stop", handle_stop)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8765)