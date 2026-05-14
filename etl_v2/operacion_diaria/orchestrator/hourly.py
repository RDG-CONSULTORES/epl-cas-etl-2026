"""Cron horario: cada hora 7-23 (Monterrey).

Captura últimas 4h de submissions de los 3 form templates EPL CAS y hace
UPSERT a daily_compliance. NO sobreescribe on_time con late.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import pytz

from etl_v2.operacion_diaria.extract import extract_submissions
from etl_v2.operacion_diaria.load import upsert_daily_compliance
from etl_v2.operacion_diaria.transform import submissions_to_rows
from etl_v2.shared.compliance import LOCAL_TZ
from etl_v2.shared.config import settings
from etl_v2.shared.db import log_etl_run
from etl_v2.shared.locations import get_active_sucursales

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
log = logging.getLogger("orchestrator.hourly")


async def run() -> int:
    started = datetime.now(pytz.UTC)
    now_local = datetime.now(LOCAL_TZ)
    start = now_local - timedelta(hours=4)
    log.info("hourly start=%s end=%s", start.isoformat(), now_local.isoformat())
    try:
        submissions = await extract_submissions(start, now_local)
        active_ids = {s["location_id"] for s in get_active_sucursales()}
        rows = submissions_to_rows(submissions, active_ids)
        n = upsert_daily_compliance(rows)
        log_etl_run("hourly", "ok", rows_affected=n,
                    metadata={"window_start": start.isoformat(),
                              "window_end": now_local.isoformat(),
                              "rows_upserted": n},
                    started_at=started)
        log.info("hourly OK rows_upserted=%d", n)
        return n
    except Exception as e:
        log.exception("hourly FAIL")
        log_etl_run("hourly", "error", error_message=str(e), started_at=started)
        raise


if __name__ == "__main__":
    asyncio.run(run())
