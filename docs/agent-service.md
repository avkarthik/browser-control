# `agent-service/` — FastAPI Browser Agent Service

The FastAPI service wraps `browser-use`'s `Agent` with HTTP control and WhatsApp notifications. This document covers the endpoints, request/response schemas, the pause/resume/stop lifecycle, and how to run it locally.

## Run locally

```powershell
cd agent-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

# Create .env (see environment.md). At minimum set GOOGLE_API_KEY.
cp .env.example .env   # then edit

python agent_service.py        # starts uvicorn on 0.0.0.0:8765
```

The OpenAPI docs are available at `http://localhost:8765/docs` once running.

## Endpoints

### Agent control — `routers/agent.py`

| Method | Path | Body | Returns | Behavior |
| --- | --- | --- | --- | --- |
| `POST` | `/task` | `TaskRequest` | `TaskResponse` | Starts a new agent task in the background (`asyncio.create_task`). Returns immediately with `status: "started"`. If an agent is already running, returns `status: "busy"`. |
| `POST` | `/resume` | `ResumeRequest` | `TaskResponse` | Resumes a paused agent. If `instruction` is non-empty, it is injected via `agent.add_new_task(instruction)` first. |
| `POST` | `/stop` | `StopRequest` | `TaskResponse` | Stops the running agent by clearing `agent_state`. Does **not** call `agent.pause()` (that blocks on stdin). |

### Status — `routers/status.py`

| Method | Path | Returns | Notes |
| --- | --- | --- | --- |
| `GET` | `/health` | `HealthResponse` `{status, version}` | Liveness probe. |
| `GET` | `/status` | `StatusResponse` `{active, task, step, paused, provider}` | Reads the `agent_state` singleton. `active` is `agent is not None`. |

### WhatsApp inbound — `routers/whatsapp.py`

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| `POST` | `/webhook` | WAHA webhook JSON | Routes inbound WhatsApp messages. See [`whatsapp-integration.md`](./whatsapp-integration.md). |

## Request / response schemas

### `TaskRequest` (`models/requests.py`)

```json
{
  "task": "find cheapest iPhone 16 Pro on bestbuy.ca",
  "max_steps": 10,
  "provider": "gemini",
  "provider_model": null
}
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `task` | `str` | (required) | Natural language task for the browser agent. |
| `max_steps` | `int` | `10` | Maximum browser steps before auto-stop. |
| `provider` | `Literal["gemini","ollama","deepseek","openrouter"]` | `"gemini"` | LLM provider. |
| `provider_model` | `str \| null` | `null` | Optional model override, e.g. `"gemini-2.5-flash"` or `"ollama:qwen3:14b"`. |

> **Note:** `max_steps` defaults to `10` in the Pydantic model, but `agent_service.run()` falls back to `settings.default_max_steps` (25) when the request value is falsy. In practice, send an explicit value.

### `ResumeRequest`

```json
{ "instruction": "" }
```

`instruction` empty → just continue. Non-empty → injected as a new task before resuming.

### `StopRequest`

```json
{ "reason": "User cancelled" }
```

`reason` is optional and only included in the WhatsApp stop message.

### `TaskResponse`

```json
{ "status": "started", "task": "...", "message": "" }
```

`status` is one of `"started" | "busy" | "resumed" | "stopped" | "error"`.

### `StatusResponse`

```json
{ "active": true, "task": "...", "step": 6, "paused": true, "provider": "gemini" }
```

## The pause / resume / stop lifecycle

This is the most important behavior to understand when modifying the service.

### Why not `agent.pause()`?

`browser-use`'s `Agent.pause()` reads from stdin to wait for the user to press Enter. In a service context there is no stdin, so calling it would block forever. The service disables this entirely with:

```python
os.environ["BROWSER_USE_NO_INTERACTIVE"] = "1"
```

(set at the top of `app/services/agent_service.py`).

### How pausing actually works

`agent_service._make_step_hook(max_steps)` returns an `on_step_end` callback that runs after every agent step:

1. Reads `agent_instance.state.n_steps` and stores it in `agent_state.step`.
2. Extracts the current URL, last thought, and last action label (all wrapped in try/except — the agent's history objects can raise).
3. Appends a bullet line to a local `steps_log` list. **No WhatsApp message is sent per step.**
4. Every `pause_every_n_steps` (default `6`, configurable via `settings`):
   - Sets `agent_state.paused = True`.
   - Sends **one** consolidated WhatsApp message via `whatsapp_service.send_consolidated_pause(...)` containing the accumulated steps log, current URL, and last thought.
   - Clears `steps_log`.
   - Enters a `while agent_state.paused: await asyncio.sleep(0.5)` loop — this blocks the agent's event loop until `/resume` clears the flag.
5. At `step_num >= max_steps`, sends a `🛑 Reached max N steps` message.

### Resume

`agent_service.resume(req)`:

- If `req.instruction` is non-empty, calls `agent.add_new_task(instruction)` and sends a WhatsApp confirmation.
- Calls `agent.resume()` (the `browser-use` method that unblocks the agent's internal pause).
- Sets `agent_state.paused = False`, which breaks the `while` loop in the step hook.
- Sends a `▶️ Resuming...` WhatsApp message.

### Stop

`agent_service.stop(req)`:

- Clears all fields on `agent_state` (`agent = None`, `task = None`, `step = 0`, `paused = False`, `provider = None`).
- Sends a `🛑 Agent stopped` WhatsApp message (with optional reason).
- Does **not** gracefully terminate the running `Agent.run()` coroutine — clearing `agent_state.agent` means the next pause check has no agent to resume. The background task will wind down on its next iteration.

## Pre-flight planning

Before `agent.run()`, the service calls `_generate_plan(task, llm)`:

- Sends a prompt asking the LLM for a 4–8 bullet execution plan covering search strategy, target sites, data to extract, expected challenges, and stopping criteria.
- Sends the plan to WhatsApp as `📋 Execution Plan`.
- Failures are non-fatal — if the LLM call errors, the agent runs anyway.

## Result reporting

After `agent.run()` returns:

- `_result_verdict(result)` → `"✅ SUCCESS"` / `"❌ FAILED"` / `"⚠️ UNKNOWN"` via `result.is_successful()`.
- `_result_judge_reason(result)` → up to 500 chars of `result.judge_reason()` if available.
- `result.final_result()` → the extracted answer.
- Sends a final WhatsApp message: `✅ Done!` + the final result (truncated to 1000 chars) + optional verdict.

## Concurrency model

- The service runs **one agent at a time**. The `agent_state` singleton enforces this.
- `POST /task` uses `asyncio.create_task(agent_service.run(req))` — fire and forget. The HTTP response returns immediately.
- `run()`'s `finally` block always resets `agent_state`, so a crashed task won't leave the service stuck thinking an agent is running.
- `/resume` and `/stop` operate on the same singleton, so they affect the in-flight task.

## Files

| File | Responsibility |
| --- | --- |
| `agent_service.py` | Uvicorn entrypoint. Runs `app.main:app` on `0.0.0.0:settings.port`. |
| `app/main.py` | FastAPI app construction, lifespan, router registration. |
| `app/config.py` | `Settings` (pydantic-settings) — all env-driven config. |
| `app/core/state.py` | `AgentState` dataclass + `agent_state` singleton. |
| `app/core/exceptions.py` | `AgentBusyError`, `NoActiveAgentError`. |
| `app/models/requests.py` | `TaskRequest`, `ResumeRequest`, `StopRequest`. |
| `app/models/responses.py` | `TaskResponse`, `StatusResponse`, `HealthResponse`. |
| `app/routers/agent.py` | `/task`, `/resume`, `/stop`. |
| `app/routers/status.py` | `/health`, `/status`. |
| `app/routers/whatsapp.py` | `/webhook` (WAHA inbound). |
| `app/services/agent_service.py` | `run` / `resume` / `stop` + step hook + planning + verdict. |
| `app/services/browser_service.py` | `BrowserProfile` / `BrowserSession` factory. |
| `app/services/llm_service.py` | Provider routing + fallback + `SEARCH_ENGINE_OVERRIDE`. |
| `app/services/whatsapp_service.py` | WAHA `send_message` + consolidated pause + error categorization. |

See also: [`whatsapp-integration.md`](./whatsapp-integration.md), [`llm-providers.md`](./llm-providers.md), [`deployment.md`](./deployment.md).