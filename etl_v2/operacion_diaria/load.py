"""Load: UPSERT a daily_compliance / weekly_summary / monthly_summary."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Iterable

from etl_v2.shared.compliance import aggregate_window
from etl_v2.shared.db import execute_many, fetch_all

log = logging.getLogger(__name__)


def upsert_daily_compliance(rows: list[dict[str, Any]],
                            overwrite_late_with_on_time: bool = True) -> int:
    """UPSERT a daily_compliance.

    Regla: si ya existe row con status='on_time', un nuevo registro 'late'
    NO la sobreescribe. Si existe 'late' y llega 'on_time', sí actualiza.
    Si existe 'missed' y llega cualquier real, actualiza.
    """
    if not rows:
        return 0

    params = [
        (r["sucursal_id"], r["day"], r["form_key"], r["project_id"],
         r["form_template_id"], r["status"], r["score"], r["submission_id"],
         r["task_id"], r["completed_at"])
        for r in rows
    ]

    # Status priority: on_time(3) > late(2) > missed(1).
    # Solo actualizamos si el nuevo status tiene >= prioridad que el actual.
    sql = """
        INSERT INTO daily_compliance
            (sucursal_id, day, form_key, project_id, form_template_id,
             status, score, submission_id, task_id, completed_at, last_updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (sucursal_id, day, form_key) DO UPDATE SET
            project_id       = EXCLUDED.project_id,
            form_template_id = EXCLUDED.form_template_id,
            status           = CASE
                WHEN daily_compliance.status = 'on_time' AND EXCLUDED.status != 'on_time'
                    THEN daily_compliance.status
                ELSE EXCLUDED.status
            END,
            score            = CASE
                WHEN daily_compliance.status = 'on_time' AND EXCLUDED.status != 'on_time'
                    THEN daily_compliance.score
                ELSE EXCLUDED.score
            END,
            submission_id    = COALESCE(EXCLUDED.submission_id, daily_compliance.submission_id),
            task_id          = COALESCE(EXCLUDED.task_id, daily_compliance.task_id),
            completed_at     = COALESCE(EXCLUDED.completed_at, daily_compliance.completed_at),
            last_updated_at  = NOW()
    """
    n = execute_many(sql, params)
    log.info("upsert_daily_compliance rows=%d affected≈%d", len(params), n)
    return n


def existing_keys_for_range(start_day: date, end_day: date
                            ) -> set[tuple[int, date, str]]:
    rows = fetch_all(
        """
        SELECT sucursal_id, day, form_key
        FROM daily_compliance
        WHERE day BETWEEN %s AND %s
        """,
        (start_day, end_day),
    )
    return {(r["sucursal_id"], r["day"], r["form_key"]) for r in rows}


# ------------------------------------------------------------
# Rollups
# ------------------------------------------------------------

def week_start(d: date) -> date:
    # Lunes como inicio de semana
    return d - timedelta(days=d.weekday())


def month_start(d: date) -> date:
    return d.replace(day=1)


def compute_weekly_summary(week_monday: date) -> int:
    """Calcula y UPSERTs weekly_summary para la semana que empieza en week_monday.

    Genera rows por scope:
    - ('global', None, form_key) y ('global', None, 'overall')
    - ('go', go_id, form_key) y ('go', go_id, 'overall')
    - ('sucursal', sucursal_id, form_key) y ('sucursal', sucursal_id, 'overall')
    """
    week_end = week_monday + timedelta(days=6)
    rows = fetch_all(
        """
        SELECT d.sucursal_id, s.go_id, d.day, d.form_key, d.status, d.score
        FROM daily_compliance d
        JOIN dim_sucursales s ON s.location_id = d.sucursal_id
        WHERE d.day BETWEEN %s AND %s
          AND s.is_active = TRUE
        """,
        (week_monday, week_end),
    )
    if not rows:
        log.info("compute_weekly_summary week=%s sin datos", week_monday)
        return 0

    buckets: dict[tuple[str, int | None, str], list[dict]] = {}
    for r in rows:
        for scope, scope_id in (("global", None),
                                ("go", r["go_id"]),
                                ("sucursal", r["sucursal_id"])):
            for fk in (r["form_key"], "overall"):
                buckets.setdefault((scope, scope_id, fk), []).append(r)

    out_rows = []
    for (scope, scope_id, form_key), rs in buckets.items():
        agg = aggregate_window(rs)
        out_rows.append((
            week_monday, scope, scope_id, form_key,
            agg["n_on_time"], agg["n_late"], agg["n_missed"],
            agg["n_total"], agg["sum_score"], agg["pct_compliance"],
        ))

    n = execute_many(
        """
        INSERT INTO weekly_summary
            (week_start, scope, scope_id, form_key,
             n_on_time, n_late, n_missed, n_total, sum_score, pct_compliance, computed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (week_start, scope, scope_id, form_key) DO UPDATE SET
            n_on_time      = EXCLUDED.n_on_time,
            n_late         = EXCLUDED.n_late,
            n_missed       = EXCLUDED.n_missed,
            n_total        = EXCLUDED.n_total,
            sum_score      = EXCLUDED.sum_score,
            pct_compliance = EXCLUDED.pct_compliance,
            computed_at    = NOW()
        """,
        out_rows,
    )

    _update_delta_prev_week(week_monday)
    log.info("compute_weekly_summary week=%s rows=%d", week_monday, n)
    return n


def _update_delta_prev_week(week_monday: date) -> None:
    prev = week_monday - timedelta(days=7)
    execute_many(
        """
        UPDATE weekly_summary cur
        SET delta_prev_week = cur.pct_compliance - prev.pct_compliance
        FROM weekly_summary prev
        WHERE cur.week_start = %s
          AND prev.week_start = %s
          AND cur.scope = prev.scope
          AND cur.scope_id IS NOT DISTINCT FROM prev.scope_id
          AND cur.form_key = prev.form_key
        """,
        [(week_monday, prev)],
    )


def compute_monthly_summary(month_first: date) -> int:
    """Agrega un mes completo a monthly_summary."""
    # Último día del mes
    if month_first.month == 12:
        next_month = month_first.replace(year=month_first.year + 1, month=1)
    else:
        next_month = month_first.replace(month=month_first.month + 1)
    month_end = next_month - timedelta(days=1)

    rows = fetch_all(
        """
        SELECT d.sucursal_id, s.go_id, d.form_key, d.status, d.score
        FROM daily_compliance d
        JOIN dim_sucursales s ON s.location_id = d.sucursal_id
        WHERE d.day BETWEEN %s AND %s
          AND s.is_active = TRUE
        """,
        (month_first, month_end),
    )
    if not rows:
        log.info("compute_monthly_summary month=%s sin datos", month_first)
        return 0

    buckets: dict[tuple[str, int | None, str], list[dict]] = {}
    for r in rows:
        for scope, scope_id in (("global", None),
                                ("go", r["go_id"]),
                                ("sucursal", r["sucursal_id"])):
            for fk in (r["form_key"], "overall"):
                buckets.setdefault((scope, scope_id, fk), []).append(r)

    out_rows = []
    for (scope, scope_id, form_key), rs in buckets.items():
        agg = aggregate_window(rs)
        out_rows.append((
            month_first, scope, scope_id, form_key,
            agg["n_on_time"], agg["n_late"], agg["n_missed"],
            agg["n_total"], agg["pct_compliance"],
        ))

    n = execute_many(
        """
        INSERT INTO monthly_summary
            (month_start, scope, scope_id, form_key,
             n_on_time, n_late, n_missed, n_total, pct_compliance, computed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (month_start, scope, scope_id, form_key) DO UPDATE SET
            n_on_time      = EXCLUDED.n_on_time,
            n_late         = EXCLUDED.n_late,
            n_missed       = EXCLUDED.n_missed,
            n_total        = EXCLUDED.n_total,
            pct_compliance = EXCLUDED.pct_compliance,
            computed_at    = NOW()
        """,
        out_rows,
    )
    log.info("compute_monthly_summary month=%s rows=%d", month_first, n)
    return n
