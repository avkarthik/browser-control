# `sample-agent.py` — Standalone CLI Browser Agent

A single-file Python script that runs one browser-automation task end-to-end and exits. It is the **reference implementation** for LLM provider routing and browser anti-detection tuning that the FastAPI service later adopted.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install browser-use langchain-google-genai python-dotenv
pip install playwright
python -m playwright install chromium
```

Create a `.env` in the project root (see [`environment.md`](./environment.md)) with at least:

```
GOOGLE_API_KEY=...
```

Add other keys as needed for the providers you want to use (`DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`).

## Usage

```powershell
python sample-agent.py [provider] [--no-vision]
```

- `provider` (optional, positional) — selects the LLM. Defaults to `gemini`.
- `--no-vision` (optional flag) — disables vision (screenshot understanding). Vision is on by default.

### Provider argument forms

The first positional argument is parsed by `get_llm()`. The general form is `provider` or `provider:model`.

| Argument | Resolves to |
| --- | --- |
| *(none)* | `gemini-flash-latest` (Gemini default) |
| `gemini` | `gemini-flash-latest` |
| `gemini-2.0-flash` | that specific Gemini model |
| `gemini-2.5-flash` | specific Gemini model |
| `gemini-2.5-flash-lite` | specific Gemini model |
| `gemini-3.1-flash-lite` | specific Gemini model |
| `ollama` | Ollama default model `gemma4` at `http://127.0.0.1:11434` |
| `ollama:gemma4` | `gemma4` via Ollama |
| `ollama:qwen3.5` | `qwen3.5` via Ollama |
| `ollama:gpt-oss:20b` | `gpt-oss:20b` via Ollama |
| `ollama:qwen3:14b` | `qwen3:14b` via Ollama |
| `deepseek` | `DeepSeek-V4-Flash` (DeepSeek default) |
| `deepseek:deepseek-v4-flash` | explicit flash |
| `deepseek:deepseek-v4-pro` | pro (slower, smarter) |
| `openrouter` | `nvidia/nemotron-nano-12b-v2-vl:free` (OpenRouter default) |
| `openrouter:google/gemma-4-31b-it:free` | explicit Gemma via OpenRouter |
| `openrouter:google/gemma-4-26b-a4b-it:free` | Gemma via OpenRouter |
| `openrouter:nvidia/nemotron-3-super-120b-a12b:free` | Nemotron via OpenRouter |
| `openrouter:openai/gpt-oss-120b:free` | GPT-OSS via OpenRouter |

> The full, up-to-date list of supported argument forms is in the comment block at the top of `sample-agent.py`. When in doubt, read the source.

## Examples

```powershell
# Default — Gemini Flash
python sample-agent.py

# Specific Gemini model
python sample-agent.py gemini-2.5-flash

# Ollama with default local model (gemma4)
python sample-agent.py ollama

# Ollama with a specific local model
python sample-agent.py ollama:qwen3:14b

# DeepSeek pro
python sample-agent.py deepseek:deepseek-v4-pro

# OpenRouter free model, no vision
python sample-agent.py openrouter --no-vision
```

## How it works

1. **Load env** — `load_dotenv()` reads `.env` from the current directory.
2. **Pick LLM** — `get_llm(provider_arg)` returns a `browser-use`-compatible chat client. See [`llm-providers.md`](./llm-providers.md) for the per-provider configuration.
3. **Fallback LLM** — if the primary provider is **not** Gemini (or is a specific `gemini-*` model), a Gemini fallback (`gemma-4-31b-it`) is configured via `get_fallback_llm()`. This is a safety net for when the primary model fails.
4. **Browser profile** — `BrowserProfile` with:
   - `headless=False` — a visible browser avoids fingerprinting.
   - `disable_security=False` — no detectable automation flags.
   - `user_agent` — realistic Chrome 148 on Windows 10.
   - `window_size` — `1280×720`.
   - `wait_between_actions=2.5`, `minimum_wait_page_load_time=2.5` — human-like pacing.
5. **Agent** — `Agent(task=..., llm=..., browser_session=..., use_vision=..., extend_system_message=SEARCH_ENGINE_OVERRIDE, fallback_llm=...)`.
6. **Run** — `await agent.run()`; the result is printed to stdout.

## The search-engine override

`SEARCH_ENGINE_OVERRIDE` is a system-message extension injected via `extend_system_message`:

```
IMPORTANT SEARCH ENGINE RULES:
- When using the `search` action, ALWAYS set `engine` to "google" as the first choice.
- If Google fails or returns a CAPTCHA/block page, ONLY THEN fall back to `engine: "duckduckgo"`.
- NEVER default to DuckDuckGo — always try Google first.
- When Google fails, use DuckDuckGo as a reliable fallback.
```

This steers the agent's `search` action toward Google first, with DuckDuckGo as a fallback when Google blocks the request.

## The hardcoded task

The current task in `main()` is:

> "Go to bestbuy.ca and find the current price of the LG C4 65-inch OLED TV"

To run a different task, edit the `task=` string in `sample-agent.py`. (The FastAPI service accepts the task via HTTP instead — see [`agent-service.md`](./agent-service.md).)

## Constants (top of file)

| Constant | Value | Purpose |
| --- | --- | --- |
| `OLLAMA_DEFAULT` | `"gemma4"` | Default Ollama model. |
| `GEMINI_DEFAULT` | `"gemini-flash-latest"` | Default Gemini model. |
| `OLLAMA_HOST` | `"http://127.0.0.1:11434"` | Local Ollama endpoint. |
| `DEEPSEEK_DEFAULT` | `"DeepSeek-V4-Flash"` | Default DeepSeek model. |
| `OPENROUTER_DEFAULT` | `"nvidia/nemotron-nano-12b-v2-vl:free"` | Default OpenRouter model. |

## Related

- [`llm-providers.md`](./llm-providers.md) — provider configuration details and fallback strategy.
- [`agent-service.md`](./agent-service.md) — the service version of this script.
- `Archives/sample-agent-archive*.py` — older versions kept for reference.