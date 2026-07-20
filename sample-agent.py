import asyncio
import sys
from dotenv import load_dotenv
import os
from browser_use import Agent, BrowserProfile, BrowserSession
from browser_use.browser.profile import ViewportSize
from playwright_stealth import Stealth

load_dotenv()

# --- Model selection ---
# Usage:
#   python sample-agent.py                             → default: gemini-flash-latest
#   python sample-agent.py gemini                      → gemini-flash-latest
#   python sample-agent.py gemini-2.0-flash            → specific gemini model
#   python sample-agent.py gemini-3.1-flash-lite       → specific gemini model
#   python sample-agent.py gemini-2.5-flash            → specific gemini model
#   python sample-agent.py gemini-2.5-flash-lite       → specific gemini model
#   python sample-agent.py ollama                      → default ollama model (gemma4)
#   python sample-agent.py ollama:gemma4               → gemma4 via ollama
#   python sample-agent.py ollama:qwen3.5              → qwen3.5 via ollama
#   python sample-agent.py ollama:gpt-oss:20b          → gpt-oss:20b via ollama
#   python sample-agent.py ollama:qwen3:14b            → qwen3:14b via ollama
#   python sample-agent.py deepseek                    → deepseek-v4-flash (default)
#   python sample-agent.py deepseek:deepseek-v4-flash  → explicit flash
#   python sample-agent.py deepseek:deepseek-v4-pro    → pro (slower, smarter)
#   python sample-agent.py openrouter                  → google/gemini-2.5-flash:free (default, reliable free model through OpenRouter)
#   python sample-agent.py openrouter:google/gemma-4-31b-it:free  → explicit Gemini via OpenRouter
#   python sample-agent.py openrouter:google/gemma-4-26b-a4b-it:free     → Gemma via OpenRouter
#   python sample-agent.py openrouter:nvidia/nemotron-3-super-120b-a12b:free → Nemotron via OpenRouter
#   python sample-agent.py openrouter:openai/gpt-oss-120b:free       → GPT-OSS via OpenRouter

OLLAMA_DEFAULT = "gemma4" 
GEMINI_DEFAULT = "gemini-flash-latest" #gemma-4-31b-it
OLLAMA_HOST = "http://127.0.0.1:11434"
DEEPSEEK_DEFAULT = "DeepSeek-V4-Flash"  # DeepSeek-V4-Pro
# Use a reliable free model from OpenRouter that handles structured output well.
# google/gemini-2.5-flash:free is a strong, free model with good JSON compliance. -- no such model
OPENROUTER_DEFAULT = "nvidia/nemotron-nano-12b-v2-vl:free"

# System message extension to force Google-first search with DuckDuckGo fallback
SEARCH_ENGINE_OVERRIDE = """
IMPORTANT SEARCH ENGINE RULES:
- When using the `search` action, ALWAYS set `engine` to "google" as the first choice.
- If Google fails or returns a CAPTCHA/block page, ONLY THEN fall back to `engine: "duckduckgo"`.
- NEVER default to DuckDuckGo — always try Google first.
- When Google fails, use DuckDuckGo as a reliable fallback.
"""


def get_llm(provider_arg: str = "gemini"):
    # Ollama branch
    if provider_arg.startswith("ollama"):
        from browser_use import ChatOllama
        parts = provider_arg.split(":", 1)
        model = parts[1] if len(parts) > 1 else OLLAMA_DEFAULT
        print(f"[LLM] Ollama → {model}")
        return ChatOllama(
            model=model,
            host=OLLAMA_HOST,
        )

    # DeepSeek via OpenAI-compatible API
    if provider_arg.startswith("deepseek"):
        from browser_use import ChatOpenAI
        parts = provider_arg.split(":", 1)
        model = parts[1] if len(parts) > 1 else DEEPSEEK_DEFAULT
        print(f"[LLM] DeepSeek → {model}")
        return ChatOpenAI(
            model=model,
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
            add_schema_to_system_prompt=True,
            remove_min_items_from_schema=True,
            temperature=None,
            frequency_penalty=None,
        )

    # OpenRouter — works with ChatOpenAI, covers ALL providers
    if provider_arg.startswith("openrouter"):
        from browser_use import ChatOpenAI
        parts = provider_arg.split(":", 1)
        model = parts[1] if len(parts) > 1 else OPENROUTER_DEFAULT
        print(f"[LLM] OpenRouter → {model}")
        return ChatOpenAI(
            model=model,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            add_schema_to_system_prompt=True,
            remove_min_items_from_schema=True,
            dont_force_structured_output=True,
            remove_defaults_from_schema=True,
            temperature=None,
            frequency_penalty=None,
        )

    # Gemini branch (default)
    from browser_use import ChatGoogle
    model = provider_arg if provider_arg.startswith("gem") else GEMINI_DEFAULT
    print(f"[LLM] Google → {model}")
    return ChatGoogle(model=model)


def get_fallback_llm():
    """Return a Gemini fallback LLM for when the primary model fails.
    Uses gemma-4-31b-it via the Google Gemini API.
    """
    from browser_use import ChatGoogle

    print("[Fallback] Using gemma-4-31b-it as fallback LLM")
    return ChatGoogle(model="gemma-4-31b-it")


async def main():
    provider_arg = sys.argv[1] if len(sys.argv) > 1 else "gemini"
    llm = get_llm(provider_arg)
    use_vision = "--no-vision" not in sys.argv

    # Only configure a fallback if the primary LLM is not already Gemini
    # (Gemini doesn't need a Gemini fallback)
    fallback_llm = None
    if not provider_arg.startswith("gemini") or provider_arg.startswith("gemini-"):
        # For non-Gemini providers (openrouter, deepseek, ollama), use Gemini as fallback
        try:
            fallback_llm = get_fallback_llm()
        except Exception as e:
            print(f"[WARNING] Could not configure fallback LLM: {e}")

    browser_profile = BrowserProfile(
        headless=False,                # visible browser — essential for avoiding bot detection
        disable_security=False,          #  ← Change to False; True adds detectable flags -->strip automation flags that trigger CAPTCHAs / access denied
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        window_size=ViewportSize(width=1280, height=720),  # controls visible browser window (not just inner viewport)
        wait_between_actions=2.5,       # slightly slower, more human-like pacing
        minimum_wait_page_load_time=2.5,
    )
    browser_session = BrowserSession(browser_profile=browser_profile)

    agent = Agent(
        task="Go to bestbuy.ca and find the current price of the LG C4 65-inch OLED TV",
        llm=llm,
        browser_session=browser_session,
        use_vision=use_vision,
        extend_system_message=SEARCH_ENGINE_OVERRIDE,
        fallback_llm=fallback_llm,
    )
    result = await agent.run()
    print(result)


asyncio.run(main())
