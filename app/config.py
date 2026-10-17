"""Application settings from environment variables."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_base_url: str = "http://localhost:8000"
    database_url: str = "sqlite:///./data/crm.sqlite3"
    secret_key: str = Field(min_length=32)
    admin_username: str = "admin"
    admin_password_hash: str = ""
    session_ttl_hours: int = 12
    app_timezone: str = "Europe/Moscow"
    app_currency: str = "RUB"
    log_level: str = "INFO"
    backup_dir: str = "./backups"
    backup_cron: str = "0 3 * * *"
    backup_retention_days: int = 14

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    google_token_encryption_key: str = ""
    google_picker_api_key: str = ""
    google_cloud_project_number: str = ""
    google_oauth_client_file: str = ""
    google_export_folder_name: str = "CRM Экспорт"
    export_max_rows: int = 10000
    export_timeout_seconds: int = 60
    export_file_name_template: str = "{entity} — {now:%Y-%m-%d %H-%M}"

    @field_validator("secret_key")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def google_configured(self) -> bool:
        return bool(
            self.google_oauth_client_id
            and self.google_oauth_client_secret
            and self.google_token_encryption_key
        )

    @property
    def oauth_redirect_uri(self) -> str:
        if self.google_oauth_redirect_uri:
            return self.google_oauth_redirect_uri
        base = self.app_base_url.rstrip("/")
        return f"{base}/settings/google/oauth/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
