"""GET /kpis?periodo=current-week|current-month → KPIs globales + por form."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Query, Response

from etl_v2.shared.compliance import EPL_CAS_PROJECTS, LOCAL_TZ
from etl_v2.shared.db import fetch_all, fetch_one

router = APIRouter()


def _resolve_period(periodo: str) -> tuple[date, date, bool]:
    today = datetime.now(LOCAL_TZ).date()
    if periodo == "current-week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6), True
    if periodo == "current-month":
        start = today.replace(day=1)
        if start.month == 12:
            end = date(start.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(start.year, start.month + 1, 1) - timedelta(days=1)
        return start, end, True
    if periodo == "prev-week":
        monday = today - timedelta(days=today.weekday())
        start = monday - timedelta(days=7)
        return start, start + timedelta(days=6), False
    raise ValueError(f"periodo inválido: {periodo}")


@router.get("/kpis")
def get_kpis(
    response: Response,
    periodo: str = Query("current-week"),
) -> dict:
    start, end, is_current = _resolve_period(periodo)
    response.headers["Cache-Control"] = "max-age=60" if is_current else "max-age=300"

    overall = fetch_one(
        """
        SELECT
            COUNT(*) AS n_total,
            SUM(CASE WHEN status='on_time' THEN 1 ELSE 0 END) AS n_on_time,
            SUM(CASE WHEN status='late' THEN 1 ELSE 0 END) AS n_late,
            SUM(CASE WHEN status='missed' THEN 1 ELSE 0 END) AS n_missed,
            COALESCE(SUM(score), 0)::float AS sum_score
        FROM daily_compliance d
        JOIN dim_sucursales s ON s.location_id = d.sucursal_id
        WHERE d.day BETWEEN %s AND %s AND s.is_active = TRUE
        """,
        (start, end),
    ) or {}

    n_total = overall.get("n_total") or 0
    pct = round((overall.get("sum_score") or 0) / n_total * 100, 2) if n_total else 0.0

    per_form = fetch_all(
        """
        SELECT d.form_key,
               COUNT(*) AS n_total,
               SUM(CASE WHEN status='on_time' THEN 1 ELSE 0 END) AS n_on_time,
               SUM(CASE WHEN status='late' THEN 1 ELSE 0 END) AS n_late,
               SUM(CASE WHEN status='missed' THEN 1 ELSE 0 END) AS n_missed,
               COALESCE(SUM(score), 0)::float AS sum_score
        FROM daily_compliance d
        JOIN dim_sucursales s ON s.location_id = d.sucursal_id
        WHERE d.day BETWEEN %s AND %s AND s.is_active = TRUE
        GROUP BY d.form_key
        """,
        (start, end),
    )
    per_form_out = []
    for r in per_form:
        nt = r["n_total"] or 0
        per_form_out.append({
            "form_key": r["form_key"],
            "n_on_time": r["n_on_time"] or 0,
            "n_late": r["n_late"] or 0,
            "n_missed": r["n_missed"] or 0,
            "n_total": nt,
            "pct_compliance": round((r["sum_score"] or 0) / nt * 100, 2) if nt else 0.0,
        })

    return {
        "periodo": periodo,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "overall": {
            "n_total": n_total,
            "n_on_time": overall.get("n_on_time") or 0,
            "n_late": overall.get("n_late") or 0,
            "n_missed": overall.get("n_missed") or 0,
            "pct_compliance": pct,
        },
        "per_form": per_form_out,
        "forms_meta": [
            {"key": v["key"], "title": v["title"],
             "window": f"{v['window_start']}–{v['window_end']}"}
            for v in EPL_CAS_PROJECTS.values()
        ],
    }
