"""Pool Postgres para etl_plog (search_path = plog)."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from etl_plog.shared.config import settings

log = logging.getLogger(__name__)


@contextmanager
def conn() -> Iterator[psycopg.Connection]:
    c = psycopg.connect(
        settings.DATABASE_URL,
        options=f"-csearch_path={settings.APP_SCHEMA},public",
        row_factory=dict_row,
    )
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
