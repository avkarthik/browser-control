# Environment Variables

This is the complete reference for every environment variable the project understands. There are **two** `.env` files:

1. **Root `.env`** — used by `sample-agent.py` (loaded via `python-dotenv`'s `load_dotenv()`).
2. **`agent-service/.env`** — used by the FastAPI service (loaded via `pydantic-settings`' `Settings` class, which reads `.env` from the service directory).

`watch.js` does **not** use a `.env` — its config is hardcoded constants at the top of the file (see [`watch.md`](./watch.md)).

## Root `.env` (for `sample-agent.py`)

`sample-agent.py` calls `load_dotenv()` and reads keys via `os.getenv(...)`. Only the keys for the providers you use are required.

| Variable | Required? | Used by | Purpose |
| --- | --- | --- | --- |
| `GOOGLE_API_KEY` | Yes (for Gemini/fallback) | `ChatGoogle` via `langchain-google-genai` | Google AI API key. Used by the default Gemini provider and by `get_fallback_llm()`. |
| `DEEPSEEK_API_KEY` | Only if using DeepSeek | `ChatOpenAI` in the `deepseek` branch | DeepSeek API key. |
| `OPENROUTER_API_KEY` | Only if using OpenRouter | `ChatOpenAI` in the `openrouter` branch | OpenRouter API key. |

> Ollama needs no env var — the host is hardcoded as `OLLAMA_HOST = "http://127.0.0.1:11434"` in `sample-agent.py`. Edit the constant to change it.

### Example root `.env`

```
GOOGLE_API_KEY=AIza...
DEEPSEEK_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
```

## `agent-service/.env` (for the FastAPI service)

`app/config.py` defines a `Settings(BaseSettings)` class. Every field is overridable via an env var with the same name (case-insensitive). The defaults below are baked into the class.

### WAHA / WhatsApp

| Variable | Default | Purpose |
| --- | --- | --- |
| `WAHA_URL` | `http://192.168.2.152:3001` | Base URL of the WAHA instance. |
| `WAHA_API_KEY` | `""` | `X-Api-Key` header value. Empty = no auth. |
| `WHATSAPP_CHAT_ID` | `120363407334128082@g.us` | Chat to send to. `@g.us` = group, `@c.us` = direct. |
| `WHATSAPP_SESSION` | `default` | WAHA session name. |

### LLM providers

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://192.168.2.152:11434` | Ollama HTTP endpoint. |
| `OLLAMA_DEFAULT_MODEL` | `gemma4` | Default model when `provider=ollama` and no `provider_model`. |
| `GOOGLE_API_KEY` | `""` | Google AI key. Required for Gemini + fallback. |
| `DEEPSEEK_API_KEY` | `""` | DeepSeek key. |
| `OPENROUTER_API_KEY` | `""` | OpenRouter key. |

### Agent defaults

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEFAULT_PROVIDER` | `gemini` | Default provider if a `TaskRequest` omits it. |
| `DEFAULT_MAX_STEPS` | `25` | Used when `TaskRequest.max_steps` is falsy. (The Pydantic default is `10`, but `run()` falls back to this.) |
| `PAUSE_EVERY_N_STEPS` | `6` | How often the `on_step_end` hook pauses and sends a consolidated WhatsApp message. |
| `PORT` | `8765` | Uvicorn listen port. Also used by `docker-compose.yml` (`${PORT:-8765}`). |

### Per-provider default models

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_DEFAULT` | `gemini-3.1-flash-lite` | Default Gemini model. (Comment in code notes `gemini-flash-latest` as an alternative.) |
| `DEEPSEEK_DEFAULT` | `DeepSeek-V4-Flash` | Default DeepSeek model. |
| `OPENROUTER_DEFAULT` | `nvidia/nemotron-nano-12b-v2-vl:free` | Default OpenRouter model. |

### Fallback

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_FALLBACK_MODEL` | `gemma-4-31b-it` | Model used by `llm_service.get_fallback_llm()` for non-Gemini providers. |

### Example `agent-service/.env`

```
# WhatsApp / WAHA
WAHA_URL=http://192.168.2.152:3001
WAHA_API_KEY=
WHATSAPP_CHAT_ID=120363407334128082@g.us
WHATSAPP_SESSION=default

# LLM providers
OLLAMA_HOST=http://192.168.2.152:11434
OLLAMA_DEFAULT_MODEL=gemma4
GOOGLE_API_KEY=AIza...
DEEPSEEK_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...

# Agent defaults
DEFAULT_PROVIDER=gemini
DEFAULT_MAX_STEPS=25
PAUSE_EVERY_N_STEPS=6
PORT=8765

# Per-provider default models
GEMINI_DEFAULT=gemini-3.1-flash-lite
DEEPSEEK_DEFAULT=DeepSeek-V4-Flash
OPENROUTER_DEFAULT=nvidia/nemotron-nano-12b-v2-vl:free

# Fallback
GEMINI_FALLBACK_MODEL=gemma-4-31b-it
```

## How `pydantic-settings` reads these

`Settings` has:

```python
class Config:
    env_file = ".env"
```

So it reads `agent-service/.env` when the service is started from the `agent-service/` directory (which `agent_service.py` and the Dockerfile both do). Field names map 1:1 to env var names (case-insensitive). A value present in the real environment takes precedence over the `.env` file.

## Secrets hygiene

- **Never commit `.env`.** The `.gitignore` excludes `.env` and `agent-service/.env`.
- **Do commit `.env.example`** files (root and `agent-service/`) with placeholder values so the shape is documented.
- The Docker compose file uses `env_file: .env`, so the same file feeds both the local and containerized runs.

## Related

- [`llm-providers.md`](./llm-providers.md) — how these keys are used per provider.
- [`whatsapp-integration.md`](./whatsapp-integration.md) — WAHA-specific settings.
- [`deployment.md`](./deployment.md) — how `.env` feeds Docker.