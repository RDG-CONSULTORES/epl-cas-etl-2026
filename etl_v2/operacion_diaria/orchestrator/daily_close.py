"""Cron diario 00:30 Monterrey: cierra día anterior.

- Captura submissions completas del día anterior
- Captura tasks archived_incomplete (= missed)
- Genera rows missed para combinaciones sin registro
- UPSERT a daily_compliance
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import pytz

from etl_v2.operacion_diaria.extract import extract_missed_tasks, extract_submissions
from etl_v2.operacion_diaria.load import (
    existing_keys_for_range,
    upsert_daily_compliance,
)
from etl_v2.operacion_diaria.transform import (
    fill_missing_combinations,
    submissions_to_rows,
    tasks_to_missed_rows,
)
from etl_v2.shared.compliance import LOCAL_TZ, PROJECT_BY_FORM_TEMPLATE
from etl_v2.shared.config import settings
from etl_v2.shared.db import log_etl_run
from etl_v2.shared.locations import get_active_sucursales, sync_dim_sucursales
from etl_v2.shared.zenput_client import ZenputClient

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
log = logging.getLogger("orchestrator.daily_close")


async def run() -> int:
    started = datetime.now(pytz.UTC)
    now_local = datetime.now(LOCAL_TZ)
    yesterday = (now_local - timedelta(days=1)).date()

    log.info("daily_close yesterday=%s", yesterday)
    total = 0
    try:
        # Refrescar catálogo de sucursales/GOs por si hubo altas/bajas/cambios
        async with ZenputClient() as zc:
            await sync_dim_sucursales(zc)

        start_dt = LOCAL_TZ.localize(datetime.combine(yesterday, datetime.min.time()))
        end_dt = LOCAL_TZ.localize(datetime.combine(yesterday, datetime.max.time()))

        submissions = await extract_submissions(start_dt, end_dt)
        sub_rows = submissions_to_rows(submissions)
        total += upsert_daily_compliance(sub_rows)

        active = get_active_sucursales()
        active_ids = {s["location_id"] for s in active}

        missed_tasks = await extract_missed_tasks(start_dt, end_dt)
        missed_rows = tasks_to_missed_rows(missed_tasks, active_ids, PROJECT_BY_FORM_TEMPLATE)
        total += upsert_daily_compliance(missed_rows)

        existing = existing_keys_for_range(yesterday, yesterday)
        fill_rows = fill_missing_combinations(active, yesterday, yesterday, existing)
        total += upsert_daily_compliance(fill_rows)

        log_etl_run("daily_close", "ok", rows_affected=total,
                    metadata={"day": yesterday.isoformat(),
                              "submission_rows": len(sub_rows),
                              "missed_task_rows": len(missed_rows),
                              "filled_rows": len(fill_rows)},
                    started_at=started)
        log.info("daily_close OK total=%d", total)
        return total
    except Exception as e:
        log.exception("daily_close FAIL")
        log_etl_run("daily_close", "error", error_message=str(e), started_at=started)
        raise


if __name__ == "__main__":
    asyncio.run(run())
