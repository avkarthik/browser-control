import asyncio
import sys
from dotenv import load_dotenv
from browser_use import Agent
import os
from browser_use import Agent, BrowserProfile, BrowserSession

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
#   python sample-agent.py openrouter                  → nvidia/nemotron-3-super-120b-a12b:free (default) - no image read
#   python sample-agent.py openrouter:openai/gpt-oss-120b:free                  → trial for image
# python sample-agent.py openrouter:openai/gpt-oss-120b:free --no-vision
# nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free # image reading should be possible
# gemini models
# gemma-4-31b-it # not working - need to know the correct model name
# google/gemma-4-31b-it:free
# gemma-4-27b-it

OLLAMA_DEFAULT = "gemma4"
GEMINI_DEFAULT = "gemini-flash-latest"
OLLAMA_HOST = "http://127.0.0.1:11434"
DEEPSEEK_DEFAULT = "DeepSeek-V4-Flash" # DeepSeek-V4-Pro
OPENROUTER_DEFAULT = "nvidia/nemotron-nano-12b-v2-vl:free" #"nvidia/nemotron-3-super-120b-a12b:free"

def get_llm(provider_arg: str = "gemini"):
    # Ollama branch
    if provider_arg.startswith("ollama"):
        from browser_use import ChatOllama
        # from langchain_ollama import ChatOllama
        parts = provider_arg.split(":", 1)
        model = parts[1] if len(parts) > 1 else OLLAMA_DEFAULT
        print(f"[LLM] Ollama → {model}")
        return ChatOllama(
            model=model,
            host=OLLAMA_HOST,  # explicit IP instead of localhost
            # num_ctx=32000    # larger context helps browser-use
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
            add_schema_to_system_prompt=True,   # DeepSeek needs schema in prompt
            remove_min_items_from_schema=True,  # improves compatibility
            temperature=None,                   # must be None in thinking mode
            frequency_penalty=None,             # not supported in thinking mode
        )

    # OpenRouter — works with ChatOpenAI, covers ALL providers
    if provider_arg.startswith("openrouter"):
        from browser_use import ChatOpenAI
        parts = provider_arg.split(":", 1)
        # Default: DeepSeek V4 Flash (cheap + reliable tool calling)
        model = parts[1] if len(parts) > 1 else OPENROUTER_DEFAULT
        print(f"[LLM] OpenRouter → {model}")
        return ChatOpenAI(
            model=model,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            add_schema_to_system_prompt=True,
            remove_min_items_from_schema=True,
            dont_force_structured_output=True,      # don't use JSON schema enforcement
            remove_defaults_from_schema=True,       # extra compatibility for non-OpenAI models
            temperature=None,
            frequency_penalty=None,
        )

    # Gemini branch (default)
    from browser_use import ChatGoogle
    # If they passed a full model name like "gemini-2.0-flash", use it directly
    print(f"Provider arg: {provider_arg}")
    model = provider_arg if provider_arg.startswith("gem") else GEMINI_DEFAULT
    print(f"[LLM] Google → {model}")
    return ChatGoogle(model=model)

async def main():
    provider_arg = sys.argv[1] if len(sys.argv) > 1 else "gemini"
    llm = get_llm(provider_arg)
    # pass --no-vision flag to disable: python sample-agent.py openrouter:gpt-oss-120b:free --no-vision
    use_vision = "--no-vision" not in sys.argv

    browser_profile = BrowserProfile(
        headless=False,          # visible browser — bypasses most bot detection
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        disable_security=False,
    )
    browser_session = BrowserSession(browser_profile=browser_profile)

    agent = Agent(
        task="Go to bestbuy.ca and find the current price of the LG C4 65-inch OLED TV",
        llm=llm,
        browser_session=browser_session,
        use_vision=use_vision
    )
    result = await agent.run()
    print(result)

asyncio.run(main())