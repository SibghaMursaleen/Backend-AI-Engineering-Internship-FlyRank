from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    STRIPE_API_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Usage Metering & Billing Engine"

    # In Docker, .env is loaded via docker-compose env_file or direct env vars
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
