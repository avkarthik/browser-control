# LLM Providers

`browser-control` supports four LLM providers, all routed through `browser-use`'s chat-client abstractions. This document covers how each provider is configured, the fallback strategy, and the search-engine override.

## Providers at a glance

| Provider | `browser-use` class | Auth | Default model | Where configured |
| --- | --- | --- | --- | --- |
| **Gemini** (default) | `ChatGoogle` | `GOOGLE_API_KEY` env | `gemini-flash-latest` (CLI) / `gemini-3.1-flash-lite` (service) | `sample-agent.py`, `agent-service/app/services/llm_service.py` |
| **Ollama** (local) | `ChatOllama` | none (local HTTP) | `gemma4` | same |
| **DeepSeek** | `ChatOpenAI` (OpenAI-compatible) | `DEEPSEEK_API_KEY` env | `DeepSeek-V4-Flash` | same |
| **OpenRouter** | `ChatOpenAI` (OpenAI-compatible) | `OPENROUTER_API_KEY` env | `nvidia/nemotron-nano-12b-v2-vl:free` | same |

## Provider routing

Both `sample-agent.py` and `agent-service/app/services/llm_service.py` expose a `get_llm(provider_arg)` function. The argument is a string parsed by prefix:

```
provider_arg
├── "ollama"            → ChatOllama, default model
├── "ollama:<model>"    → ChatOllama, specific model
├── "deepseek"          → ChatOpenAI @ api.deepseek.com, default model
├── "deepseek:<model>"  → ChatOpenAI @ api.deepseek.com, specific model
├── "openrouter"        → ChatOpenAI @ openrouter.ai/api/v1, default model
├── "openrouter:<model>"→ ChatOpenAI @ openrouter.ai/api/v1, specific model
├── "gemini"            → ChatGoogle, configured default model
├── "gemini-<version>"  → ChatGoogle, that specific model
└── anything else       → ChatGoogle, configured default model
```

The FastAPI service additionally has `resolve_provider_arg(provider, provider_model)` in `llm_service.py`, which combines the `TaskRequest.provider` (a `Literal`) with an optional `provider_model` override into the single string `get_llm()` expects:

| `provider` | `provider_model` | Resolved arg |
| --- | --- | --- |
| `"gemini"` | `null` | `settings.gemini_default` (e.g. `gemini-3.1-flash-lite`) |
| `"gemini"` | `"gemini-2.5-flash"` | `gemini-2.5-flash` |
| `"ollama"` | `"qwen3:14b"` | `ollama:qwen3:14b` |
| `"deepseek"` | `null` | `deepseek` |
| `"openrouter"` | `"google/gemma-4-31b-it:free"` | `openrouter:google/gemma-4-31b-it:free` |

## Per-provider details

### Gemini (`ChatGoogle`)

- **Auth:** `GOOGLE_API_KEY` environment variable (read by `langchain-google-genai`).
- **Default model:**
  - `sample-agent.py`: `GEMINI_DEFAULT = "gemini-flash-latest"`
  - `agent-service`: `settings.gemini_default = "gemini-3.1-flash-lite"` (overridable via env)
- **No extra kwargs** — just `ChatGoogle(model=model)`.
- **Used as the fallback** for all non-Gemini providers (see below).

### Ollama (`ChatOllama`)

- **Auth:** none — local HTTP.
- **Host:**
  - `sample-agent.py`: `OLLAMA_HOST = "http://127.0.0.1:11434"`
  - `agent-service`: `settings.ollama_host = "http://192.168.2.152:11434"` (overridable via env)
- **Default model:** `gemma4` (`settings.ollama_default_model` in the service).
- **Constructor:** `ChatOllama(model=model, host=host)`.
- **Requires** a local Ollama daemon running and the model pulled (`ollama pull gemma4`).

### DeepSeek (`ChatOpenAI`, OpenAI-compatible)

- **Auth:** `DEEPSEEK_API_KEY` environment variable.
- **Base URL:** `https://api.deepseek.com`
- **Default model:** `DeepSeek-V4-Flash` (`settings.deepseek_default` in the service).
- **Constructor kwargs** (tuned for `browser-use` compatibility):
  - `add_schema_to_system_prompt=True`
  - `remove_min_items_from_schema=True`
  - `temperature=None`
  - `frequency_penalty=None`

### OpenRouter (`ChatOpenAI`, OpenAI-compatible)

- **Auth:** `OPENROUTER_API_KEY` environment variable.
- **Base URL:** `https://openrouter.ai/api/v1`
- **Default model:** `nvidia/nemotron-nano-12b-v2-vl:free` — a free model that handles structured output reasonably well.
- **Constructor kwargs** (more conservative than DeepSeek because OpenRouter proxies many providers):
  - `add_schema_to_system_prompt=True`
  - `remove_min_items_from_schema=True`
  - `dont_force_structured_output=True`
  - `remove_defaults_from_schema=True`
  - `temperature=None`
  - `frequency_penalty=None`

> The OpenRouter default was chosen after `google/gemini-2.5-flash:free` turned out not to exist on OpenRouter. The comment in `sample-agent.py` documents this.

## Fallback strategy

Non-Gemini providers can fail (rate limits, network, bad structured output). To keep the agent running, a **Gemini fallback LLM** is configured whenever the primary provider is not Gemini.

### In `sample-agent.py`

```python
fallback_llm = None
if not provider_arg.startswith("gemini") or provider_arg.startswith("gemini-"):
    try:
        fallback_llm = get_fallback_llm()   # ChatGoogle(model="gemma-4-31b-it")
    except Exception as e:
        print(f"[WARNING] Could not configure fallback LLM: {e}")
```

> Note the condition: `gemini` alone (no version) skips the fallback, but `gemini-2.5-flash` etc. get one. This is a quirk of the original script — the intent is "only skip fallback for the default Gemini path."

### In `agent-service`

```python
if not provider_arg.startswith("gemini"):
    try:
        fallback_llm = llm_service.get_fallback_llm()
    except Exception as e:
        print(f"[WARNING] Could not configure fallback LLM: {e}")
```

The service uses `settings.gemini_fallback_model` (default `gemma-4-31b-it`) instead of a hardcoded string.

The fallback is passed to `Agent(..., fallback_llm=fallback_llm)`. `browser-use` uses it automatically when the primary LLM raises.

## Search-engine override

Both the CLI and the service inject the same system-message extension via `Agent(extend_system_message=SEARCH_ENGINE_OVERRIDE)`:

```
IMPORTANT SEARCH ENGINE RULES:
- When using the `search` action, ALWAYS set `engine` to "google" as the first choice.
- If Google fails or returns a CAPTCHA/block page, ONLY THEN fall back to `engine: "duckduckgo"`.
- NEVER default to DuckDuckGo — always try Google first.
- When Google fails, use DuckDuckGo as a reliable fallback.
```

This steers the agent's `search` action toward Google first, with DuckDuckGo as a fallback when Google blocks the request. The constant is defined in:

- `sample-agent.py` as `SEARCH_ENGINE_OVERRIDE`
- `agent-service/app/services/llm_service.py` as `SEARCH_ENGINE_OVERRIDE` (imported by `agent_service.py`)

## Adding a new provider

1. **`agent-service/app/services/llm_service.py`** — add a new `if provider_arg.startswith("..."):` branch in `get_llm()` returning the appropriate `browser-use` chat client.
2. **`agent-service/app/models/requests.py`** — add the provider name to the `Literal["gemini","ollama","deepseek","openrouter"]` on `TaskRequest.provider`.
3. **`agent-service/app/config.py`** — add any new env vars (API key, default model) to `Settings`.
4. **`sample-agent.py`** — add the same branch to its `get_llm()` and a default constant, so the CLI stays in sync.
5. **`docs/environment.md`** — document the new env vars.

## Environment variables

See [`environment.md`](./environment.md) for the full list. Provider-relevant ones:

| Variable | Used by | Purpose |
| --- | --- | --- |
| `GOOGLE_API_KEY` | Gemini + fallback | Google AI API key. |
| `DEEPSEEK_API_KEY` | DeepSeek | DeepSeek API key. |
| `OPENROUTER_API_KEY` | OpenRouter | OpenRouter API key. |
| `OLLAMA_HOST` | service only | Ollama HTTP endpoint. |
| `OLLAMA_DEFAULT_MODEL` | service only | Default Ollama model. |
| `GEMINI_DEFAULT` | service only | Default Gemini model. |
| `DEEPSEEK_DEFAULT` | service only | Default DeepSeek model. |
| `OPENROUTER_DEFAULT` | service only | Default OpenRouter model. |
| `GEMINI_FALLBACK_MODEL` | service only | Model used by `get_fallback_llm()`. |