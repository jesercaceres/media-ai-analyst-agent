from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Google Gemini (LLM provider)
    google_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.0

    # Google Cloud / BigQuery
    google_application_credentials: str
    gcp_project_id: str

    # Agent
    agent_max_iterations: int = 10

    # App
    app_title: str = "Media Analyst AI Agent"
    app_version: str = "1.0.1"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
