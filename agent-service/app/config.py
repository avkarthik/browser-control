from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # WAHA (WhatsApp HTTP API)
    waha_url: str = "http://192.168.2.152:3001"
    waha_api_key: str = ""
    whatsapp_chat_id: str = "120363407334128082@g.us"
    whatsapp_session: str = "default"

    # LLM Providers
    ollama_host: str = "http://192.168.2.152:11434"
    ollama_default_model: str = "gemma4"
    google_api_key: str = ""
    deepseek_api_key: str = ""
    openrouter_api_key: str = ""

    # Agent defaults
    default_provider: str = "gemini"
    default_max_steps: int = 25
    pause_every_n_steps: int = 6
    port: int = 8765

    # Gemini default model name used by ChatGoogle
    gemini_default: str = "gemini-3.1-flash-lite" #"gemini-flash-latest"
    deepseek_default: str = "DeepSeek-V4-Flash"
    openrouter_default: str = "nvidia/nemotron-nano-12b-v2-vl:free"

    # Fallback
    gemini_fallback_model: str = "gemma-4-31b-it"

    class Config:
        env_file = ".env"


settings = Settings()