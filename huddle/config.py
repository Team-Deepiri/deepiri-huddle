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

    huddle_repos: str = Field(default="", alias="HUDDLE_REPOS")
    huddle_doc_patterns: str = Field(
        default="**/*.md,**/*.rst",
        alias="HUDDLE_DOC_PATTERNS",
    )
    git_history_days: int = Field(default=7, alias="GIT_HISTORY_DAYS")
    risk_high_churn_threshold: int = Field(default=10, alias="RISK_HIGH_CHURN_THRESHOLD")
    risk_stale_days: int = Field(default=30, alias="RISK_STALE_DAYS")
    no_llm_fallback: bool = Field(default=True, alias="NO_LLM_FALLBACK")

    def provider_order(self) -> list[str]:
        return [item.strip().lower() for item in self.llm_provider_order.split(",") if item.strip()]

    def doc_patterns(self) -> list[str]:
        return [p.strip() for p in self.huddle_doc_patterns.split(",") if p.strip()]

    def extra_repos(self) -> list[str]:
        return [p.strip() for p in self.huddle_repos.split(",") if p.strip()]
