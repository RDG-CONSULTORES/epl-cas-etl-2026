"""Cron lunes 5am: rollup semana anterior + (si es primer lunes del mes) mes."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import pytz

from etl_v2.operacion_diaria.load import (
    compute_monthly_summary,
    compute_weekly_summary,
    month_start,
    week_start,
)
from etl_v2.shared.compliance import LOCAL_TZ
from etl_v2.shared.config import settings
from etl_v2.shared.db import log_etl_run

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
log = logging.getLogger("orchestrator.weekly_rollup")


def _is_first_monday_of_month(d: date) -> bool:
    return d.weekday() == 0 and d.day <= 7


def run() -> tuple[int, int]:
    started = datetime.now(pytz.UTC)
    today_local = datetime.now(LOCAL_TZ).date()
    prev_week = week_start(today_local - timedelta(days=7))
    log.info("weekly_rollup prev_week=%s", prev_week)
    try:
        n_week = compute_weekly_summary(prev_week)
        n_month = 0
        if _is_first_monday_of_month(today_local):
            prev_month = month_start(today_local - timedelta(days=1))
            n_month = compute_monthly_summary(prev_month)
            log.info("first-monday → monthly_summary month=%s n=%d", prev_month, n_month)
        log_etl_run("weekly_rollup", "ok", rows_affected=n_week + n_month,
                    metadata={"week_start": prev_week.isoformat(),
                              "weekly_rows": n_week, "monthly_rows": n_month},
                    started_at=started)
        log.info("weekly_rollup OK weekly=%d monthly=%d", n_week, n_month)
        return n_week, n_month
    except Exception as e:
        log.exception("weekly_rollup FAIL")
        log_etl_run("weekly_rollup", "error", error_message=str(e), started_at=started)
        raise


if __name__ == "__main__":
    run()
