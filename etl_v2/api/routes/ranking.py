"""GET /ranking?scope=go|sucursal&periodo=current-week → ranking ordenado.

LEFT JOIN desde el catálogo (dim_grupos_operativos / dim_sucursales) para que
GOs y sucursales SIN actividad en el periodo aparezcan con 0% (no se excluyen).
"""
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
        # LEFT JOIN desde dim_grupos_operativos: los 18 GOs aparecen siempre,
        # los que no tienen evaluaciones quedan en 0%.
        rows = fetch_all(
            """
            SELECT g.go_id AS id,
                   g.nombre AS nombre,
                   g.n_sucursales,
                   COUNT(d.*) AS n_total,
                   COALESCE(SUM(CASE WHEN d.status='on_time' THEN 1 ELSE 0 END), 0) AS n_on_time,
                   COALESCE(SUM(CASE WHEN d.status='late' THEN 1 ELSE 0 END), 0) AS n_late,
                   COALESCE(SUM(CASE WHEN d.status='missed' THEN 1 ELSE 0 END), 0) AS n_missed,
                   COALESCE(SUM(d.score), 0)::float AS sum_score
            FROM operacion_diaria.dim_grupos_operativos g
            LEFT JOIN operacion_diaria.dim_sucursales s
                ON s.go_id = g.go_id AND s.is_active = TRUE
            LEFT JOIN operacion_diaria.daily_compliance d
                ON d.sucursal_id = s.location_id AND d.day BETWEEN %s AND %s
            WHERE g.is_epl_cas = TRUE
            GROUP BY g.go_id, g.nombre, g.n_sucursales
            ORDER BY (CASE WHEN COUNT(d.*) = 0 THEN -1
                           ELSE SUM(d.score)::float / COUNT(d.*) END) DESC,
                     g.nombre
            """,
            (start, end),
        )
    else:
        # LEFT JOIN desde dim_sucursales activas
        rows = fetch_all(
            """
            SELECT s.location_id AS id,
                   s.nombre AS nombre,
                   s.go_id,
                   s.go_nombre,
                   COUNT(d.*) AS n_total,
                   COALESCE(SUM(CASE WHEN d.status='on_time' THEN 1 ELSE 0 END), 0) AS n_on_time,
                   COALESCE(SUM(CASE WHEN d.status='late' THEN 1 ELSE 0 END), 0) AS n_late,
                   COALESCE(SUM(CASE WHEN d.status='missed' THEN 1 ELSE 0 END), 0) AS n_missed,
                   COALESCE(SUM(d.score), 0)::float AS sum_score
            FROM operacion_diaria.dim_sucursales s
            LEFT JOIN operacion_diaria.daily_compliance d
                ON d.sucursal_id = s.location_id AND d.day BETWEEN %s AND %s
            WHERE s.is_active = TRUE
            GROUP BY s.location_id, s.nombre, s.go_id, s.go_nombre
            ORDER BY (CASE WHEN COUNT(d.*) = 0 THEN -1
                           ELSE SUM(d.score)::float / COUNT(d.*) END) DESC,
                     s.nombre
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
            "sin_data": nt == 0,
        }
        if scope == "go":
            item["n_sucursales"] = r.get("n_sucursales") or 0
        else:
            item["go_id"] = r.get("go_id")
            item["go_nombre"] = r.get("go_nombre")
        out.append(item)

    return {
        "scope": scope,
        "periodo": periodo,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "items": out,
    }
