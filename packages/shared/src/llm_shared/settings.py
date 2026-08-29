from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./autopilot.db"
    redis_url: str = "redis://localhost:6379/0"
    gateway_secret: str = "dev-secret-change-me"
    cors_origins: str = "http://localhost:3000"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    mock_providers: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    cache_ttl_seconds: int = 86400

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
