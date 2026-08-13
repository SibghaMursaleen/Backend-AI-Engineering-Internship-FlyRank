import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    port: int = 8000
    host: str = "127.0.0.1"
    llm_enabled: bool = True
    llm_stub: bool = True
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-2.5-flash"
    openrouter_timeout: float = 30.0
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
