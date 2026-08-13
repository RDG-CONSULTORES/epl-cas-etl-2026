"""Config etl_plog — env-driven, con fallback a .env del repo (solo local)."""
from __future__ import annotations

import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    env = _REPO / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


class Settings:
    ZENPUT_TOKEN: str = os.environ.get("ZENPUT_TOKEN", "")
    ZENPUT_BASE_URL: str = os.environ.get("ZENPUT_BASE_URL", "https://www.zenput.com/api/v3")
    DATABASE_URL: str = os.environ.get("PLOG_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    APP_SCHEMA: str = os.environ.get("PLOG_SCHEMA", "plog")
    TZ: str = os.environ.get("TZ", "America/Monterrey")
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


settings = Settings()
