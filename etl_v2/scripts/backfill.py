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

from etl_v2.operacion_diaria.extract import extract_missed_tasks, extract_submissions
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
    submissions_to_rows,
    tasks_to_missed_rows,
)
from etl_v2.shared.compliance import LOCAL_TZ, PROJECT_BY_FORM_TEMPLATE
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

    totals = {"daily_submissions": 0, "daily_missed_tasks": 0,
              "daily_filled": 0, "weekly": 0, "monthly": 0}

    # 1) Catálogo de sucursales
    async with ZenputClient() as zc:
        suc_metrics = await sync_dim_sucursales(zc)
        log.info("dim_sucursales metrics=%s", suc_metrics)

        # 2) Recorrer por semana para evitar cap 10K
        cur = start_day
        while cur <= end_day:
            week_end = min(cur + timedelta(days=6), end_day)
            s_dt = LOCAL_TZ.localize(datetime.combine(cur, datetime.min.time()))
            e_dt = LOCAL_TZ.localize(datetime.combine(week_end, datetime.max.time()))

            log.info("--- semana %s..%s ---", cur, week_end)
            subs_by_project = await extract_submissions(s_dt, e_dt)
            sub_rows = submissions_to_rows(subs_by_project)
            totals["daily_submissions"] += upsert_daily_compliance(sub_rows)

            missed_tasks = await extract_missed_tasks(s_dt, e_dt)
            active = get_active_sucursales()
            active_ids = {s["location_id"] for s in active}
            missed_rows = tasks_to_missed_rows(missed_tasks, active_ids, PROJECT_BY_FORM_TEMPLATE)
            totals["daily_missed_tasks"] += upsert_daily_compliance(missed_rows)

            existing = existing_keys_for_range(cur, week_end)
            fill_rows = fill_missing_combinations(active, cur, week_end, existing)
            totals["daily_filled"] += upsert_daily_compliance(fill_rows)

            cur = week_end + timedelta(days=1)

    # 3) Rollups
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
