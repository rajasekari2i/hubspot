"""Application configuration with Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables with defaults."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/pipeline_intelligence"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Gmail / GCP
    google_cloud_project: str = ""
    pubsub_subscription: str = "gmail-push-sub"
    google_client_id: str = ""
    google_client_secret: str = ""

    # HubSpot
    hubspot_access_token: str = ""

    # Slack
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_alert_channel: str = "#pipeline-intelligence-alerts"

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_primary_provider: str = "anthropic"
    llm_fallback_provider: str = "openai"
    llm_primary_model: str = "claude-haiku-4-5-20251001"
    llm_fallback_model: str = "gpt-4o-mini"

    # Encryption
    encryption_key: str = ""

    # Auth (OIDC)
    oidc_issuer: str = "https://accounts.google.com"
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:8000/api/v1/auth/callback"
    session_secret: str = "change-me-in-production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
