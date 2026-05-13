"""Settings centralizados (pydantic-settings)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    ZENPUT_TOKEN: str
    APP_SCHEMA: str = "operacion_diaria"
    TZ: str = "America/Monterrey"
    LOG_LEVEL: str = "INFO"
    ZENPUT_BASE_URL: str = "https://www.zenput.com"


settings = Settings()
