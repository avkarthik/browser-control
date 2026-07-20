"""LLM provider routing — ported from sample-agent.py with config integration."""

import os
from app.config import settings

# ---------------------------------------------------------------------------
# System message extension to force Google-first search with DuckDuckGo fallback
# ---------------------------------------------------------------------------
SEARCH_ENGINE_OVERRIDE = """
IMPORTANT SEARCH ENGINE RULES:
- When using the `search` action, ALWAYS set `engine` to "google" as the first choice.
- If Google fails or returns a CAPTCHA/block page, ONLY THEN fall back to `engine: "duckduckgo"`.
- NEVER default to DuckDuckGo — always try Google first.
- When Google fails, use DuckDuckGo as a reliable fallback.
"""


# ---------------------------------------------------------------------------
# Primary LLM factory
# ---------------------------------------------------------------------------
def get_llm(provider_arg: str = "gemini"):
    """Return a browser-use compatible LLM for the requested provider."""
    # --- Ollama ---
    if provider_arg.startswith("ollama"):
        from browser_use import ChatOllama
        parts = provider_arg.split(":", 1)
        model = parts[1] if len(parts) > 1 else settings.ollama_default_model
        print(f"[LLM] Ollama -> {model} @ {settings.ollama_host}")
        return ChatOllama(model=model, host=settings.ollama_host)

    # --- DeepSeek (OpenAI-compatible API) ---
    if provider_arg.startswith("deepseek"):
        from browser_use import ChatOpenAI
        parts = provider_arg.split(":", 1)
        model = parts[1] if len(parts) > 1 else settings.deepseek_default
        print(f"[LLM] DeepSeek -> {model}")
        return ChatOpenAI(
            model=model,
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
            add_schema_to_system_prompt=True,
            remove_min_items_from_schema=True,
            temperature=None,
            frequency_penalty=None,
        )

    # --- OpenRouter ---
    if provider_arg.startswith("openrouter"):
        from browser_use import ChatOpenAI
        parts = provider_arg.split(":", 1)
        model = parts[1] if len(parts) > 1 else settings.openrouter_default
        print(f"[LLM] OpenRouter -> {model}")
        return ChatOpenAI(
            model=model,
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            add_schema_to_system_prompt=True,
            remove_min_items_from_schema=True,
            dont_force_structured_output=True,
            remove_defaults_from_schema=True,
            temperature=None,
            frequency_penalty=None,
        )

    # --- Gemini (default) ---
    from browser_use import ChatGoogle
    # "gemini" alone is not a valid model — use the configured default
    model = provider_arg if provider_arg.startswith("gemini-") else settings.gemini_default
    print(f"[LLM] Google -> {model}")
    return ChatGoogle(model=model)


# ---------------------------------------------------------------------------
# Fallback LLM — Gemini for when non-Gemini providers fail
# ---------------------------------------------------------------------------
def get_fallback_llm():
    """Return a Gemini fallback LLM when the primary model fails."""
    from browser_use import ChatGoogle

    model = settings.gemini_fallback_model
    print(f"[Fallback] Using {model} as fallback LLM")
    return ChatGoogle(model=model)


# ---------------------------------------------------------------------------
# Build provider arg string from TaskRequest fields
# ---------------------------------------------------------------------------
def resolve_provider_arg(provider: str, provider_model: str | None = None) -> str:
    """Combine provider + optional model override into the arg get_llm() expects.

    Examples:
        ("gemini", None)                 -> "gemini-3.1-flash-lite" (from settings)
        ("gemini", "gemini-2.5-flash")   -> "gemini-2.5-flash"
        ("ollama", "qwen3:14b")          -> "ollama:qwen3:14b"
        ("deepseek", None)               -> "deepseek"
        ("openrouter", "google/gemma-4-31b-it:free") -> "openrouter:google/gemma-4-31b-it:free"
    """
    if provider_model:
        if provider == "gemini":
            return provider_model
        return f"{provider}:{provider_model}"

    # No model override — for Gemini, use the configured default model
    if provider == "gemini":
        return settings.gemini_default

    return provider