from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    log_level: str = "INFO"
    app_name: str = "School ERP Assistant"

    # optional shared secret. when set, every endpoint needs the X-API-Key header.
    api_key: str = ""

    # mock ERP data ships with the repo; the runtime dbs are written next to it
    data_dir: str = "mock_data"
    memory_db: str = "data/memory.db"
    audit_db: str = "data/audit.db"

    # the assistant treats this as "today". pinning it keeps "tomorrow" and
    # "this month" answers deterministic during a demo or test run.
    today: str = "2025-11-10"

    # how many past turns to replay into the model for context
    memory_window: int = 8

    # hard cap on the reason→act loop so a confused model can't spin forever
    max_agent_steps: int = 6


@lru_cache
def get_settings() -> Settings:
    # cached so we don't re-read the .env on every request
    return Settings()
