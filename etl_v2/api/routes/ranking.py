"""GET /ranking?scope=go|sucursal&periodo=current-week → ranking ordenado."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Query, Response

from etl_v2.shared.compliance import LOCAL_TZ
from etl_v2.shared.db import fetch_all

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
    raise ValueError(periodo)


@router.get("/ranking")
def get_ranking(
    response: Response,
    scope: str = Query("go", pattern="^(go|sucursal)$"),
    periodo: str = Query("current-week"),
) -> dict:
    start, end, is_current = _resolve_period(periodo)
    response.headers["Cache-Control"] = "max-age=60" if is_current else "max-age=300"

    if scope == "go":
        rows = fetch_all(
            """
            SELECT s.go_id AS id, MAX(s.go_nombre) AS nombre,
                   COUNT(DISTINCT s.location_id) AS n_sucursales,
                   COUNT(*) AS n_total,
                   SUM(CASE WHEN d.status='on_time' THEN 1 ELSE 0 END) AS n_on_time,
                   SUM(CASE WHEN d.status='late' THEN 1 ELSE 0 END) AS n_late,
                   SUM(CASE WHEN d.status='missed' THEN 1 ELSE 0 END) AS n_missed,
                   COALESCE(SUM(d.score), 0)::float AS sum_score
            FROM daily_compliance d
            JOIN dim_sucursales s ON s.location_id = d.sucursal_id
            WHERE d.day BETWEEN %s AND %s AND s.is_active = TRUE
            GROUP BY s.go_id
            ORDER BY (CASE WHEN COUNT(*)=0 THEN 0 ELSE SUM(d.score)/COUNT(*) END) DESC
            """,
            (start, end),
        )
    else:
        rows = fetch_all(
            """
            SELECT s.location_id AS id, s.nombre AS nombre,
                   s.go_id, s.go_nombre,
                   COUNT(*) AS n_total,
                   SUM(CASE WHEN d.status='on_time' THEN 1 ELSE 0 END) AS n_on_time,
                   SUM(CASE WHEN d.status='late' THEN 1 ELSE 0 END) AS n_late,
                   SUM(CASE WHEN d.status='missed' THEN 1 ELSE 0 END) AS n_missed,
                   COALESCE(SUM(d.score), 0)::float AS sum_score
            FROM daily_compliance d
            JOIN dim_sucursales s ON s.location_id = d.sucursal_id
            WHERE d.day BETWEEN %s AND %s AND s.is_active = TRUE
            GROUP BY s.location_id, s.nombre, s.go_id, s.go_nombre
            ORDER BY (CASE WHEN COUNT(*)=0 THEN 0 ELSE SUM(d.score)/COUNT(*) END) DESC
            """,
            (start, end),
        )

    out = []
    for i, r in enumerate(rows, 1):
        nt = r.get("n_total") or 0
        pct = round((r.get("sum_score") or 0) / nt * 100, 2) if nt else 0.0
        item = {
            "rank": i,
            "id": r["id"],
            "nombre": r["nombre"],
            "n_on_time": r["n_on_time"] or 0,
            "n_late": r["n_late"] or 0,
            "n_missed": r["n_missed"] or 0,
            "n_total": nt,
            "pct_compliance": pct,
        }
        if scope == "go":
            item["n_sucursales"] = r.get("n_sucursales") or 0
        else:
            item["go_id"] = r.get("go_id")
            item["go_nombre"] = r.get("go_nombre")
        out.append(item)

    return {"scope": scope, "periodo": periodo,
            "start": start.isoformat(), "end": end.isoformat(),
            "items": out}
