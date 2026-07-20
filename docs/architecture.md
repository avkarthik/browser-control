# Architecture

This document explains the system at a high level: the components, how they fit together, and the request lifecycle. Read this first if you're new to the codebase.

## High-level diagram

```
                       ┌──────────────────────────────┐
                       │         LLM Providers         │
                       │  Gemini · Ollama · DeepSeek  │
                       │         · OpenRouter         │
                       └──────────────┬───────────────┘
                                      │ (chat completions)
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
   ┌──────────────────┐   ┌────────────────────┐   ┌──────────────────┐
   │  sample-agent.py │   │   agent-service/   │   │     watch.js     │
   │  (CLI one-shot)  │   │  (FastAPI + WAHA)  │   │  (Node poller)   │
   └────────┬─────────┘   └─────────┬──────────┘   └────────┬─────────┘
            │                       │                       │
            │                       │ HTTP                  │ fetch
            │                       ▼                       ▼
            │            ┌────────────────────┐   ┌──────────────────┐
            │            │  WAHA (WhatsApp    │   │  Ollama (local)  │
            │            │   HTTP API)        │   │  fuzzy match     │
            │            └─────────┬──────────┘   └──────────────────┘
            │                      │
            ▼                      ▼
   ┌──────────────────────────────────────────┐
   │       browser-use Agent + Playwright     │
   │   (real Chromium, anti-bot-detection)    │
   └──────────────────────┬───────────────────┘
                          │
                          ▼
                   ┌────────────┐
                   │  The Web   │
                   └────────────┘
```

## Components

### 1. `sample-agent.py` — Standalone CLI agent

A single-file Python script that runs one task end-to-end and exits. It is the **reference implementation** for the LLM provider routing and browser profile tuning that the FastAPI service later adopted.

- Parses `sys.argv[1]` to pick a provider/model (e.g. `gemini`, `ollama:qwen3:14b`, `deepseek`, `openrouter:...`).
- Builds a `BrowserProfile` with a realistic Chrome 148 user-agent, `headless=False`, and human-like delays to avoid bot detection.
- Creates a `browser_use.Agent` with an optional **Gemini fallback LLM** (used when the primary provider is not Gemini).
- Injects `SEARCH_ENGINE_OVERRIDE` into the system message to force Google-first search with DuckDuckGo fallback.
- Runs `agent.run()` and prints the result.

### 2. `watch.js` — Webpage watcher

A Node.js script (Playwright + local Ollama) that periodically checks whether a page contains target content.

- Launches headless Chromium, navigates to `URL`, and reads `body.innerText()`.
- First tries a **direct substring match** against `TARGET_TEXT`.
- If that fails, asks the local Ollama model (`gemma4` by default) for a `MATCH` / `NO_MATCH` verdict.
- Saves a full-page screenshot to `shots/` (prefixed `match-` or `check-`) and logs a JSON line.
- Runs once on startup, then every `CHECK_EVERY_MS` (default 60s) via `setInterval`.

### 3. `agent-service/` — FastAPI service

A production-shaped service that wraps `browser-use`'s `Agent` with HTTP control and WhatsApp notifications. This is the most complex component; see [`agent-service.md`](./agent-service.md) for full details.

**Layered structure:**

```
agent_service.py        ← uvicorn entrypoint (runs app.main:app)
app/
├── main.py             ← FastAPI app, router registration, lifespan
├── config.py           ← Settings (pydantic-settings, reads .env)
├── core/
│   ├── state.py        ← AgentState singleton (agent, task, step, paused, provider)
│   └── exceptions.py   ← AgentBusyError, NoActiveAgentError
├── models/
│   ├── requests.py     ← TaskRequest, ResumeRequest, StopRequest
│   └── responses.py    ← TaskResponse, StatusResponse, HealthResponse
├── routers/
│   ├── agent.py        ← POST /task, /resume, /stop
│   ├── status.py       ← GET /health, /status
│   └── whatsapp.py     ← POST /webhook (WAHA inbound)
└── services/
    ├── agent_service.py    ← run/resume/stop lifecycle + on_step_end hook
    ├── browser_service.py  ← BrowserProfile/BrowserSession factory
    ├── llm_service.py      ← provider routing + fallback + search override
    └── whatsapp_service.py ← WAHA send_message + consolidated pause + errors
```

**Key design decisions:**

- **Singleton `AgentState`** (`app/core/state.py`) holds the single in-flight agent. The service runs one task at a time; a second `/task` while one is running returns `status: "busy"`.
- **`BROWSER_USE_NO_INTERACTIVE=1`** is set in `agent_service.py` to disable `browser-use`'s built-in CLI pause prompt, which would block on stdin in a service context.
- **No `agent.pause()`** — that method blocks on stdin. Instead, pausing is implemented via an `on_step_end` hook that sets `agent_state.paused = True` and `await`s a sleep loop until `/resume` clears the flag.
- **Consolidated notifications** — steps are accumulated silently and sent as **one** WhatsApp message at each pause point (every `pause_every_n_steps`), not one message per step.
- **Pre-flight planning** — before running the agent, the LLM is asked to produce a 4–8 bullet execution plan, which is sent to WhatsApp.

## Request lifecycle (FastAPI service)

```
User → WhatsApp → WAHA → POST /webhook
                            │
                            ├─ "continue"/"go"/"proceed" → agent_service.resume()
                            ├─ "stop"/"cancel"/"end"     → agent_service.stop()
                            └─ any other text            → /task (if idle) or /resume with instruction (if running)

HTTP client → POST /task {task, max_steps, provider, provider_model}
                            │
                            ▼
                  agent_service.run()  (asyncio.create_task — fire and forget)
                            │
                            ├─ llm_service.get_llm(provider_arg)
                            ├─ llm_service.get_fallback_llm()  (if not Gemini)
                            ├─ browser_service.create_browser_profile/session()
                            ├─ Agent(task, llm, browser_session, fallback_llm, ...)
                            ├─ _generate_plan() → WhatsApp "Execution Plan" message
                            ├─ agent.run(max_steps, on_step_end=hook)
                            │       │
                            │       └─ every N steps:
                            │            WhatsApp "Paused at step X/Y" + steps log
                            │            wait until /resume clears paused flag
                            │
                            └─ WhatsApp "Done!" + final_result() + verdict
```

## Data flow summary

| Flow | Trigger | Path |
| --- | --- | --- |
| Start task | `POST /task` or WhatsApp free-text | `routers/agent.py` → `services/agent_service.run()` → `Agent.run()` |
| Pause | Automatic every N steps | `on_step_end` hook sets `agent_state.paused = True` |
| Resume | `POST /resume` or WhatsApp "continue" | `agent_service.resume()` → `agent.resume()` + clears `paused` |
| Stop | `POST /stop` or WhatsApp "stop" | `agent_service.stop()` clears state (does **not** call `agent.pause()`) |
| Status | `GET /status` | reads `agent_state` singleton |
| Inbound message | WAHA → `POST /webhook` | `routers/whatsapp.py` routes by text |

## External dependencies

| Dependency | Purpose | Where used |
| --- | --- | --- |
| [`browser-use`](https://github.com/browser-use/browser-use) | LLM-driven browser agent | `sample-agent.py`, `agent-service/` |
| Playwright | Browser automation | `watch.js` (Node), `browser-use` (Python) |
| FastAPI + Uvicorn | HTTP service | `agent-service/` |
| [WAHA](https://waha.devlike.pro/) | WhatsApp HTTP API (external) | `agent-service/` via `whatsapp_service.py` |
| Ollama | Local LLM host | `watch.js`, optional provider in agents |
| `playwright-stealth` | Anti-detection (Python) | `sample-agent.py` import (stealth class) |

## Where to make common changes

| Change | File |
| --- | --- |
| Add a new LLM provider | `agent-service/app/services/llm_service.py` + `models/requests.py` (`Literal`) + `sample-agent.py` `get_llm()` |
| Change browser anti-detection settings | `agent-service/app/services/browser_service.py` + `sample-agent.py` `browser_profile` |
| Change pause frequency | `settings.pause_every_n_steps` in `app/config.py` or `.env` |
| Change WhatsApp message format | `agent-service/app/services/whatsapp_service.py` |
| Add a new HTTP endpoint | new file in `agent-service/app/routers/` + register in `app/main.py` |
| Change the watcher's target URL/text | top of `watch.js` |

See [`AGENTS.md`](./AGENTS.md) for the agent/LLM quickstart with gotchas.