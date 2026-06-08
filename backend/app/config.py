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
    coingecko_api_base_url: str = "https://api.coingecko.com/api/v3"
    coingecko_api_key: str | None = None
    coingecko_api_key_header: str = "x-cg-demo-api-key"
    coingecko_history_days: str = "365"
    exchange_candle_history_days: str = "365"
    binance_api_base_url: str = "https://data-api.binance.vision"
    binance_futures_api_base_url: str = "https://fapi.binance.com"
    upbit_api_base_url: str = "https://api.upbit.com"
    bithumb_api_base_url: str = "https://api.bithumb.com"
    fx_api_base_url: str = "https://open.er-api.com/v6/latest"
    fear_greed_api_base_url: str = "https://api.alternative.me"
    live_data_stale_after_seconds: int = 900
    usd_krw_rate: float = 1350.0
    openai_api_key: str | None = None
    openai_model: str = "local-heuristic"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
