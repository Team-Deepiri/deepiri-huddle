from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="gemma2:9b", alias="OLLAMA_MODEL")

    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")

    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="meta-llama/llama-3.1-8b-instruct:free",
        alias="OPENROUTER_MODEL",
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    llm_provider_order: str = Field(
        default="ollama,deepseek,gemini,openrouter,openai",
        alias="LLM_PROVIDER_ORDER",
    )
    llm_timeout_seconds: float = Field(default=120.0, alias="LLM_TIMEOUT_SECONDS")

    discord_bot_token: str | None = Field(default=None, alias="DISCORD_BOT_TOKEN")
    discord_channel_id: str | None = Field(default=None, alias="DISCORD_CHANNEL_ID")
    discord_announcements_channel: str = Field(
        default="announcements",
        alias="DISCORD_ANNOUNCEMENTS_CHANNEL",
    )
    discord_fetch_limit: int = Field(default=20, alias="DISCORD_FETCH_LIMIT")

    memory_file: str = Field(default=".huddle/memory.jsonl", alias="MEMORY_FILE")

    huddle_log_level: str = Field(
        default="INFO",
        alias="HUDDLE_LOG_LEVEL",
        description="Python logging level for the huddle package (DEBUG, INFO, WARNING, ...).",
    )

    def provider_order(self) -> list[str]:
        return [item.strip().lower() for item in self.llm_provider_order.split(",") if item.strip()]

