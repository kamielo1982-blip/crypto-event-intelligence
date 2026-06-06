from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(...)
    admin_username: str = "admin"
    admin_password: str = Field(..., min_length=12)
    session_secret: str = Field(..., min_length=32)
    session_cookie_secure: bool = False
    frontend_origin: str = "http://localhost:3000"
    enable_demo_data: bool = True
    openai_api_key: str | None = None
    openai_model: str = "local-heuristic"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
