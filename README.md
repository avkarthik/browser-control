# browser-control

LLM-driven browser automation with a CLI agent, a FastAPI service, and a webpage watcher. Built on [`browser-use`](https://github.com/browser-use/browser-use) + Playwright, with multi-LLM support (Gemini, Ollama, DeepSeek, OpenRouter) and WhatsApp notifications via [WAHA](https://waha.devlike.pro/).

## What's inside

| Path | Language | Description |
| --- | --- | --- |
| [`sample-agent.py`](./sample-agent.py) | Python | Standalone CLI browser agent. One task, runs end-to-end, prints the result. Reference implementation for LLM routing + anti-bot-detection browser profile. |
| [`watch.js`](./watch.js) | Node.js | Polls a URL on an interval, checks for target text (direct match + Ollama fuzzy match), saves screenshots to `shots/`. |
| [`agent-service/`](./agent-service/) | Python (FastAPI) | HTTP-controllable agent service with WhatsApp notifications, pause/resume/stop lifecycle, pre-flight planning, and Docker deployment. |
| [`Archives/`](./Archives/) | Python | Older single-file versions of the agent scripts (kept for reference). |
| [`docs/`](./docs/) | Markdown | Full documentation — start in [`docs/README.md`](./docs/README.md). |

## Quickstart

### 1. CLI agent (`sample-agent.py`)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install browser-use langchain-google-genai python-dotenv playwright
python -m playwright install chromium

# Create .env with at least GOOGLE_API_KEY=...
python sample-agent.py                 # default: Gemini
python sample-agent.py ollama          # local Ollama
python sample-agent.py deepseek        # DeepSeek
python sample-agent.py openrouter      # OpenRouter free tier
```

See [`docs/sample-agent.md`](./docs/sample-agent.md) for all provider/model argument forms.

### 2. Webpage watcher (`watch.js`)

```powershell
npm install
npx playwright install chromium
# Ensure Ollama is running locally: ollama pull gemma4
node watch.js
```

Edit the constants at the top of `watch.js` to change the URL, target text, and interval. See [`docs/watch.md`](./docs/watch.md).

### 3. FastAPI service (`agent-service/`)

```powershell
cd agent-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

cp .env.example .env       # then edit: GOOGLE_API_KEY, WAHA_URL, WHATSAPP_CHAT_ID, ...
python agent_service.py    # starts on http://localhost:8765
```

Or with Docker:

```powershell
cd agent-service
cp .env.example .env       # edit as above
docker compose up --build -d
```

OpenAPI docs at `http://localhost:8765/docs`. See [`docs/agent-service.md`](./docs/agent-service.md) and [`docs/deployment.md`](./docs/deployment.md).

## Documentation

Full documentation lives in [`docs/`](./docs/). Start at [`docs/README.md`](./docs/README.md) for an index, or jump straight to:

- [`docs/architecture.md`](./docs/architecture.md) — system overview, components, request lifecycle.
- [`docs/AGENTS.md`](./docs/AGENTS.md) — **dense quickstart for LLMs/coding agents** (gotchas, file map, conventions).
- [`docs/agent-service.md`](./docs/agent-service.md) — FastAPI endpoints, schemas, pause/resume/stop lifecycle.
- [`docs/sample-agent.md`](./docs/sample-agent.md) — CLI usage and provider arguments.
- [`docs/watch.md`](./docs/watch.md) — webpage watcher configuration.
- [`docs/llm-providers.md`](./docs/llm-providers.md) — Gemini / Ollama / DeepSeek / OpenRouter setup + fallback.
- [`docs/whatsapp-integration.md`](./docs/whatsapp-integration.md) — WAHA setup, webhook contract, command routing.
- [`docs/deployment.md`](./docs/deployment.md) — Docker, Xvfb, `shm_size`, Home Assistant networking.
- [`docs/environment.md`](./docs/environment.md) — every environment variable.

## Environment

Secrets and tunables live in `.env` files (gitignored). Templates are committed:

- [`.env.example`](./.env.example) — for `sample-agent.py`.
- [`agent-service/.env.example`](./agent-service/.env.example) — for the FastAPI service.

Copy to `.env` and fill in real values. Minimum to run the service: `GOOGLE_API_KEY`, `WAHA_URL`, `WHATSAPP_CHAT_ID`.

## Requirements

- **Python 3.11+** for `sample-agent.py` and `agent-service/`.
- **Node.js 18+** for `watch.js` (uses global `fetch`).
- **Playwright Chromium** for all three.
- **Ollama** (local) if using the `ollama` provider or `watch.js` fuzzy matching.
- **WAHA** (external) for WhatsApp notifications from the service.

## License

None specified. Add a `LICENSE` file if you intend to share/distribute.