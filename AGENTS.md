# AGENTS.md — Quickstart for LLMs & Coding Agents

> **Audience:** an LLM or coding agent (Cline, Cursor, Copilot, etc.) about to make changes to this repo. Read this first — it's the dense, gotcha-heavy map that saves you from reading every file.

## TL;DR

`browser-control` is an LLM-driven browser automation system with three entry points:

| Entry point | Language | What it does |
| --- | --- | --- |
| `sample-agent.py` | Python | One-shot CLI agent. Hardcoded task. Reference impl for LLM routing + browser profile. |
| `watch.js` | Node.js | Polls a URL, checks for target text (direct + Ollama fuzzy match), saves screenshots. |
| `agent-service/` | Python (FastAPI) | HTTP-controllable agent with WhatsApp (WAHA) notifications, pause/resume/stop, pre-flight planning. |

Core engine for both Python entry points: [`browser-use`](https://github.com/browser-use/browser-use) (`Agent`, `BrowserProfile`, `BrowserSession`, `ChatGoogle`, `ChatOllama`, `ChatOpenAI`).

## File map (what to edit for what)

| Goal | File(s) |
| --- | --- |
| Change the CLI's hardcoded task | `sample-agent.py` → `task="..."` in `main()` |
| Add/change an LLM provider | `agent-service/app/services/llm_service.py` + `agent-service/app/models/requests.py` (`Literal`) + `agent-service/app/config.py` + `sample-agent.py` `get_llm()` |
| Change browser anti-detection | `agent-service/app/services/browser_service.py` + `sample-agent.py` `browser_profile` |
| Change pause frequency | `agent-service/app/config.py` → `pause_every_n_steps` (or `.env`) |
| Change WhatsApp message text/format | `agent-service/app/services/whatsapp_service.py` |
| Add an HTTP endpoint | new file in `agent-service/app/routers/` + register in `agent-service/app/main.py` |
| Change request/response schema | `agent-service/app/models/requests.py` / `responses.py` |
| Change the watcher's URL/target | top of `watch.js` (constants) |
| Change Docker config | `agent-service/Dockerfile`, `agent-service/docker-compose.yml` |

## Critical gotchas (read before touching the service)

1. **`BROWSER_USE_NO_INTERACTIVE=1`** is set at the top of `agent-service/app/services/agent_service.py`. It disables `browser-use`'s built-in CLI pause prompt, which reads from stdin. **Do not remove this** — in a service context stdin is closed and the agent would hang forever.

2. **Never call `agent.pause()`.** It blocks on stdin. Pausing is implemented via an `on_step_end` hook that sets `agent_state.paused = True` and `await`s a `while paused: sleep(0.5)` loop. `/resume` clears the flag. If you need a new pause mechanism, follow this pattern — don't reach for `agent.pause()`.

3. **`shm_size: '2gb'`** in `docker-compose.yml` is load-bearing. Chromium crashes without it. Don't "clean up" this line.

4. **`headless=False` is intentional** in `browser_service.create_browser_profile()` and `sample-agent.py`. A visible browser avoids bot-detection fingerprinting. In Docker this works because Xvfb provides a virtual display. Don't flip it to `True` without testing against the target sites.

5. **`disable_security=False`** — setting it to `True` adds detectable automation flags that trigger CAPTCHAs. Leave it `False`.

6. **One agent at a time.** `agent_state` (`app/core/state.py`) is a singleton. A second `POST /task` while one is running returns `status: "busy"`. Don't add concurrency without reworking the state model.

7. **`POST /task` is fire-and-forget.** It uses `asyncio.create_task(agent_service.run(req))` and returns `status: "started"` immediately. The actual result goes to WhatsApp, not the HTTP response. Don't try to make it synchronous without a major refactor.

8. **`run()`'s `finally` block resets all state.** This is what keeps a crashed task from leaving the service stuck. Preserve this behavior if you refactor `run()`.

9. **`max_steps` has two defaults.** The Pydantic model default is `10`; `run()` falls back to `settings.default_max_steps` (25) when the request value is falsy. If you "fix" one, check the other.

10. **`send_message` swallows errors.** WhatsApp is best-effort. Don't add control flow that depends on a message being delivered — the HTTP endpoints are the source of truth.

11. **Inbound webhook text is lowercased** before routing in `routers/whatsapp.py`. `Continue`, `CONTINUE`, and `continue` all match. Keep this if you add new commands.

12. **The webhook has no auth.** Anyone who can reach `/webhook` can start/stop tasks. Don't expose it publicly without a reverse proxy / shared secret.

## LLM provider routing — the one string

Both `sample-agent.py` and `agent-service/app/services/llm_service.py` have a `get_llm(provider_arg)` that parses a single string by prefix:

```
"ollama" | "ollama:<model>"
"deepseek" | "deepseek:<model>"
"openrouter" | "openrouter:<model>"
"gemini" | "gemini-<version>" | (anything else → Gemini default)
```

The service wraps this with `resolve_provider_arg(provider, provider_model)` which combines the `TaskRequest` `Literal` provider + optional model override into that string. **Keep both `get_llm` implementations in sync** when adding a provider.

Non-Gemini providers get a Gemini fallback (`get_fallback_llm()` → `ChatGoogle(model=settings.gemini_fallback_model)`). The fallback condition differs slightly between the CLI and the service — see [`llm-providers.md`](./docs/llm-providers.md#fallback-strategy).

## Search-engine override

`SEARCH_ENGINE_OVERRIDE` (defined in both `sample-agent.py` and `agent-service/app/services/llm_service.py`) is injected via `Agent(extend_system_message=...)`. It forces Google-first search with DuckDuckGo fallback. Keep the two copies identical if you edit one.

## Environment

- Two `.env` files: root (for `sample-agent.py`) and `agent-service/.env` (for the service). Both are gitignored.
- `.env.example` files are committed with placeholder values — update them when you add a new env var.
- Full var reference: [`environment.md`](./docs/environment.md).
- Minimum to run the service: `GOOGLE_API_KEY`, `WAHA_URL`, `WHATSAPP_CHAT_ID`.

## How to verify your changes

There's no test suite (`package.json` has the default `npm test` that just errors). Verification is manual:

1. **CLI agent:** `python sample-agent.py gemini` — should open a visible Chromium and run the hardcoded task.
2. **Service locally:** `cd agent-service && python agent_service.py`, then `curl http://localhost:8765/health` → `{"status":"ok","version":"1.0.0"}`.
3. **Service endpoints:** `curl http://localhost:8765/status` → `{"active":false,...}`. `POST /task` with a small `max_steps` to watch it run.
4. **Docker:** `cd agent-service && docker compose up --build -d`, then health check as above.
5. **Watcher:** `node watch.js` — should log a JSON line and write a screenshot to `shots/`.

## Style / conventions

- Python: no linter configured. Follow the existing style (4-space indent, double quotes for strings in `sample-agent.py`, single quotes in some service files — match the file you're editing).
- Node: `watch.js` uses double quotes and CommonJS (`require`).
- Imports: `browser-use` classes are imported lazily inside `get_llm()` branches (only when that provider is selected). Preserve this — it avoids requiring all provider libs at startup.
- Error handling in the service: wrap `browser-use` history access in try/except (the agent's `state`/`history` objects can raise). The existing `on_step_end` hook does this everywhere.
- WhatsApp messages use emoji prefixes (`🚀`, `⏸️`, `✅`, `🛑`, `❌`, `⏱️`, `🌐`, `🔧`, `📋`, `▶️`, `📝`, `💭`, `📊`). Match the existing style when adding new message types.

## Don't

- Don't commit `.env` files.
- Don't remove `shm_size: '2gb'` from `docker-compose.yml`.
- Don't set `headless=True` or `disable_security=True` without testing against target sites.
- Don't call `agent.pause()`.
- Don't remove `BROWSER_USE_NO_INTERACTIVE=1`.
- Don't add a second concurrent agent without reworking `agent_state`.
- Don't delete `Archives/` — it's kept for reference.

## Pointers

- Architecture overview: [`architecture.md`](./docs/architecture.md)
- Service deep dive: [`agent-service.md`](./docs/agent-service.md)
- CLI usage: [`sample-agent.md`](./docs/sample-agent.md)
- Watcher: [`watch.md`](./docs/watch.md)
- LLM providers: [`llm-providers.md`](./docs/llm-providers.md)
- WhatsApp: [`whatsapp-integration.md`](./docs/whatsapp-integration.md)
- Docker: [`deployment.md`](./docs/deployment.md)
- Env vars: [`environment.md`](./docs/environment.md)