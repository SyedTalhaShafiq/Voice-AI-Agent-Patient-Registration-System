"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Vapi
    vapi_api_key: str = ""

    # Database — SQLite by default; swap to Postgres for production
    database_url: str = "sqlite:///./patients.db"

    # Debug / logging verbosity
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
