"""Pool de conexiones Postgres + helpers."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg_pool import ConnectionPool

from etl_v2.shared.config import settings

log = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.DATABASE_URL,
            min_size=1,
            max_size=8,
            kwargs={"autocommit": False, "options": f"-csearch_path={settings.APP_SCHEMA},public"},
        )
        log.info("psycopg pool inicializado schema=%s", settings.APP_SCHEMA)
    return _pool


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def execute(sql: str, params: tuple | list | dict | None = None) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        conn.commit()
        return cur.rowcount


def execute_many(sql: str, rows: list[tuple]) -> int:
    if not rows:
        return 0
    with get_conn() as conn, conn.cursor() as cur:
        cur.executemany(sql, rows)
        conn.commit()
        return cur.rowcount


def fetch_all(sql: str, params: tuple | list | dict | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(sql: str, params: tuple | list | dict | None = None) -> dict[str, Any] | None:
    with get_conn() as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def log_etl_run(job_name: str, status: str, rows_affected: int = 0,
                error_message: str | None = None, metadata: dict | None = None,
                started_at=None) -> None:
    """Inserta o cierra un row en etl_runs."""
    import json
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl_runs (job_name, started_at, finished_at, status, rows_affected, error_message, metadata)
            VALUES (%s, COALESCE(%s, NOW()), NOW(), %s, %s, %s, %s)
            """,
            (job_name, started_at, status, rows_affected, error_message,
             json.dumps(metadata) if metadata else None),
        )
        conn.commit()
