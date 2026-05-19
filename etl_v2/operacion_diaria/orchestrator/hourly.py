"""Cron horario: cada hora 7-23 (Monterrey).

Captura submissions de HOY (task_date == today) y hace UPSERT.

Por qué UPSERT (no DELETE+INSERT) en hourly:
- Hourly debe acumular updates a lo largo del día sin perder lo que ya
  capturó. Si las 8 AM ya guardó la apertura como on_time, las 9 AM no
  debe borrarla.
- Priority on_time > late > missed se respeta. Como hourly solo procesa
  submissions del mismo día, no aparece el caso missed-next-day aquí
  (ese se procesa en daily_close del día siguiente).

Trade-off:
- Pull full 10K submissions/activity (~5 min/run). El API no filtra por
  fecha realmente. 17 runs/día × 5 min = ~85 min API time/día. Aceptable.
- Si TASK creada ayer se completó hoy → este hourly NO la procesa (filtra
  por task_date == today). Quedará pendiente hasta daily_close, donde se
  marcará missed.
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
    today = now_local.date()

    # Rango = día completo de hoy (para extract). Transform filtra a task_date == today.
    start_dt = LOCAL_TZ.localize(datetime.combine(today, datetime.min.time()))
    end_dt = LOCAL_TZ.localize(datetime.combine(today, datetime.max.time()))

    log.info("hourly today=%s now=%s", today, now_local.isoformat())
    try:
        subs_by_project = await extract_submissions(start_dt, end_dt)
        active_ids = {s["location_id"] for s in get_active_sucursales()}
        rows = submissions_to_rows(subs_by_project, active_ids,
                                    day_range=(today, today))
        n = upsert_daily_compliance(rows)
        log_etl_run(
            "hourly", "ok", rows_affected=n,
            metadata={
                "today": today.isoformat(),
                "submissions_pulled": sum(len(v) for v in subs_by_project.values()),
                "rows_upserted": n,
            },
            started_at=started,
        )
        log.info("hourly OK rows_upserted=%d", n)
        return n
    except Exception as e:
        log.exception("hourly FAIL")
        log_etl_run("hourly", "error", error_message=str(e), started_at=started)
        raise


if __name__ == "__main__":
    asyncio.run(run())
