# browser-control — Documentation

Welcome to the `browser-control` documentation. This folder is the canonical reference for humans, LLMs, and coding agents working on this project.

## Start here

| If you want to… | Read this |
| --- | --- |
| Understand the project at a glance | [`architecture.md`](./architecture.md) |
| Run the standalone CLI agent | [`sample-agent.md`](./sample-agent.md) |
| Run the FastAPI + WhatsApp service | [`agent-service.md`](./agent-service.md) |
| Use the webpage watcher | [`watch.md`](./watch.md) |
| Configure LLM providers | [`llm-providers.md`](./llm-providers.md) |
| Set up WhatsApp via WAHA | [`whatsapp-integration.md`](./whatsapp-integration.md) |
| Deploy with Docker | [`deployment.md`](./deployment.md) |
| See every environment variable | [`environment.md`](./environment.md) |
| Make changes quickly as an agent/LLM | [`AGENTS.md`](../AGENTS.md) |

## Project in one paragraph

`browser-control` is an LLM-driven browser automation system built on the [`browser-use`](https://github.com/browser-use/browser-use) library. It ships in three forms: a standalone CLI agent (`sample-agent.py`), a Node.js webpage watcher (`watch.js`), and a FastAPI service (`agent-service/`) that drives a `browser-use` `Agent` over HTTP and reports progress to a WhatsApp chat via [WAHA](https://waha.devlike.pro/). All three support multiple LLM providers (Gemini, Ollama, DeepSeek, OpenRouter) and are tuned to avoid bot detection.

## Repository layout

```
browser-control/
├── sample-agent.py            # Standalone CLI browser agent
├── watch.js                   # Node.js Playwright webpage watcher
├── package.json               # Node deps (playwright) for watch.js
├── agent-service/             # FastAPI service wrapping browser-use
│   ├── agent_service.py       # Uvicorn entrypoint
│   ├── Dockerfile             # Chromium + Xvfb + FastAPI
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── app/
│       ├── main.py            # FastAPI app + router registration
│       ├── config.py          # Pydantic settings (env-driven)
│       ├── core/              # state.py (singleton), exceptions.py
│       ├── models/            # Pydantic request/response schemas
│       ├── routers/           # agent.py, status.py, whatsapp.py
│       └── services/          # agent, browser, llm, whatsapp services
├── Archives/                  # Older single-file versions (reference only)
├── shots/                     # Screenshots from watch.js
└── docs/                      # This folder
```

## Conventions

- **Python** for the agent and service; **Node.js** only for `watch.js`.
- All secrets live in `.env` files (never committed). See [`environment.md`](./environment.md).
- The `browser-use` `Agent` is the core engine; everything else is orchestration around it.
- Documentation is Markdown-only; no static-site generator. Open the files directly in VS Code or on GitHub.