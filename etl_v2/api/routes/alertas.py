"""GET /alertas → sucursales con compliance bajo y formularios pendientes hoy."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, Response

from etl_v2.shared.compliance import EPL_CAS_PROJECTS, LOCAL_TZ
from etl_v2.shared.db import fetch_all

router = APIRouter()

LOW_THRESHOLD = 70.0  # pct


@router.get("/alertas")
def get_alertas(
    response: Response,
    semanas: int = Query(2, ge=1, le=8),
    threshold: float = Query(LOW_THRESHOLD, ge=0, le=100),
) -> dict:
    response.headers["Cache-Control"] = "max-age=60"

    today = datetime.now(LOCAL_TZ).date()
    bajo = fetch_all(
        """
        SELECT s.location_id, s.nombre, s.go_id, s.go_nombre,
               COUNT(*) AS n_total,
               COALESCE(SUM(d.score),0)::float AS sum_score
        FROM daily_compliance d
        JOIN dim_sucursales s ON s.location_id = d.sucursal_id
        WHERE d.day BETWEEN %s AND %s AND s.is_active = TRUE
        GROUP BY s.location_id, s.nombre, s.go_id, s.go_nombre
        HAVING COUNT(*) > 0
           AND SUM(d.score)/COUNT(*) * 100 < %s
        ORDER BY SUM(d.score)/COUNT(*) ASC
        """,
        (today.replace(day=1) if semanas >= 4 else today, today, threshold),
    )
    bajo_out = [{
        "location_id": r["location_id"],
        "nombre": r["nombre"],
        "go_id": r["go_id"],
        "go_nombre": r["go_nombre"],
        "pct_compliance": round((r["sum_score"] / r["n_total"]) * 100, 2),
    } for r in bajo]

    pendientes_hoy = fetch_all(
        """
        SELECT s.location_id, s.nombre, s.go_nombre, p.form_key
        FROM dim_sucursales s
        CROSS JOIN (SELECT unnest(%s::text[]) AS form_key) p
        LEFT JOIN daily_compliance d
            ON d.sucursal_id = s.location_id
           AND d.day = %s
           AND d.form_key = p.form_key
        WHERE s.is_active = TRUE
          AND (d.status IS NULL OR d.status = 'missed')
        ORDER BY s.go_nombre, s.nombre, p.form_key
        """,
        ([m["key"] for m in EPL_CAS_PROJECTS.values()], today),
    )

    return {
        "threshold": threshold,
        "today": today.isoformat(),
        "bajo_compliance": bajo_out,
        "pendientes_hoy": [{
            "location_id": r["location_id"],
            "nombre": r["nombre"],
            "go_nombre": r["go_nombre"],
            "form_key": r["form_key"],
        } for r in pendientes_hoy],
    }
