"""Cron diario 00:30 Monterrey: cierra día anterior con DELETE+INSERT.

Por qué DELETE+INSERT y no UPSERT:
- El UPSERT en load.py tiene priority on_time > late > missed. No permite
  downgrade. Si una task quedó on_time en hourly de ayer pero al final del día
  Zenput la marcó archived_incomplete, el daily_close debe poder bajarla a
  missed. DELETE+INSERT es la forma limpia.

Pasos:
1. Sync dim_sucursales (refresca catálogo + tags EPL CAS)
2. Extract submissions v3 con date_created_local = ayer
3. Transform a rows (clasificación por hora vs ventana)
4. DELETE rows EPL CAS de ayer
5. INSERT rows nuevas
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import pytz

from etl_v2.operacion_diaria.extract import extract_submissions
from etl_v2.operacion_diaria.load import (
    delete_daily_compliance_range,
    insert_daily_compliance,
)
from etl_v2.operacion_diaria.transform import submissions_to_rows
from etl_v2.shared.compliance import LOCAL_TZ
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

    try:
        async with ZenputClient() as zc:
            await sync_dim_sucursales(zc)

        # Rango: día completo ayer en zona local
        start_dt = LOCAL_TZ.localize(datetime.combine(yesterday, datetime.min.time()))
        end_dt = LOCAL_TZ.localize(datetime.combine(yesterday, datetime.max.time()))

        active = get_active_sucursales()
        active_ids = {s["location_id"] for s in active}

        subs_by_project = await extract_submissions(start_dt, end_dt)
        rows = submissions_to_rows(subs_by_project, active_ids,
                                    day_range=(yesterday, yesterday))

        deleted = delete_daily_compliance_range(yesterday, yesterday)
        inserted = insert_daily_compliance(rows)

        log_etl_run(
            "daily_close", "ok", rows_affected=inserted,
            metadata={
                "day": yesterday.isoformat(),
                "submissions_pulled": sum(len(v) for v in subs_by_project.values()),
                "rows_deleted": deleted,
                "rows_inserted": inserted,
            },
            started_at=started,
        )
        log.info("daily_close OK deleted=%d inserted=%d", deleted, inserted)
        return inserted
    except Exception as e:
        log.exception("daily_close FAIL")
        log_etl_run("daily_close", "error", error_message=str(e), started_at=started)
        raise


if __name__ == "__main__":
    asyncio.run(run())
