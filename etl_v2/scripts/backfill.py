"""Backfill histórico inicial.

Usage:
    python -m etl_v2.scripts.backfill --semanas 8
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import time
from datetime import datetime, timedelta

import pytz

from etl_v2.operacion_diaria.extract import (
    extract_missed_submissions,
    extract_submissions,
)
from etl_v2.operacion_diaria.load import (
    compute_monthly_summary,
    compute_weekly_summary,
    existing_keys_for_range,
    month_start,
    upsert_daily_compliance,
    week_start,
)
from etl_v2.operacion_diaria.transform import (
    fill_missing_combinations,
    missed_submissions_to_rows,
    submissions_to_rows,
)
from etl_v2.shared.compliance import LOCAL_TZ
from etl_v2.shared.config import settings
from etl_v2.shared.db import log_etl_run
from etl_v2.shared.locations import get_active_sucursales, sync_dim_sucursales
from etl_v2.shared.zenput_client import ZenputClient

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("backfill")


async def run(semanas: int) -> dict:
    t0 = time.time()
    started = datetime.now(pytz.UTC)
    today = datetime.now(LOCAL_TZ).date()
    end_day = today
    start_day = today - timedelta(weeks=semanas)
    log.info("backfill semanas=%d rango=%s..%s", semanas, start_day, end_day)

    totals = {"daily_submissions": 0, "daily_missed": 0,
              "daily_filled": 0, "weekly": 0, "monthly": 0}

    async with ZenputClient() as zc:
        suc_metrics = await sync_dim_sucursales(zc)
        log.info("dim_sucursales metrics=%s", suc_metrics)

    # Recorrer DÍA por DÍA: el API satura a 10K hits/form/listado.
    # Con 68 sucursales un día rara vez supera 1K, así que es seguro.
    active = get_active_sucursales()
    active_ids = {s["location_id"] for s in active}

    cur = start_day
    while cur <= end_day:
        s_dt = LOCAL_TZ.localize(datetime.combine(cur, datetime.min.time()))
        e_dt = LOCAL_TZ.localize(datetime.combine(cur, datetime.max.time()))
        log.info("--- día %s ---", cur)

        subs_by_project = await extract_submissions(s_dt, e_dt)
        sub_rows = submissions_to_rows(subs_by_project, active_ids)
        totals["daily_submissions"] += upsert_daily_compliance(sub_rows)

        missed_by_project = await extract_missed_submissions(s_dt, e_dt)
        missed_rows = missed_submissions_to_rows(missed_by_project, active_ids)
        totals["daily_missed"] += upsert_daily_compliance(missed_rows)

        existing = existing_keys_for_range(cur, cur)
        fill_rows = fill_missing_combinations(active, cur, cur, existing)
        totals["daily_filled"] += upsert_daily_compliance(fill_rows)

        cur += timedelta(days=1)

    # Rollups
    cur_monday = week_start(start_day)
    last_monday = week_start(end_day - timedelta(days=1))
    while cur_monday <= last_monday:
        totals["weekly"] += compute_weekly_summary(cur_monday)
        cur_monday += timedelta(days=7)

    cur_month = month_start(start_day)
    last_month = month_start(end_day)
    while cur_month < last_month:
        totals["monthly"] += compute_monthly_summary(cur_month)
        if cur_month.month == 12:
            cur_month = cur_month.replace(year=cur_month.year + 1, month=1)
        else:
            cur_month = cur_month.replace(month=cur_month.month + 1)

    elapsed = time.time() - t0
    log_etl_run("backfill", "ok", rows_affected=sum(totals.values()),
                metadata={"semanas": semanas, "start": start_day.isoformat(),
                          "end": end_day.isoformat(),
                          "elapsed_seconds": round(elapsed, 1),
                          **totals},
                started_at=started)
    log.info("backfill OK elapsed=%.1fs totals=%s", elapsed, totals)
    return totals


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--semanas", type=int, default=8)
    args = parser.parse_args()
    asyncio.run(run(args.semanas))
