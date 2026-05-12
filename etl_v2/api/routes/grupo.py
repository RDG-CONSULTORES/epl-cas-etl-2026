"""GET /grupo/{go_id}?periodo=current-week → detalle de un GO con sus sucursales."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Response

from etl_v2.shared.compliance import LOCAL_TZ
from etl_v2.shared.db import fetch_all, fetch_one

router = APIRouter()


def _resolve_period(periodo: str) -> tuple[date, date, bool]:
    today = datetime.now(LOCAL_TZ).date()
    if periodo == "current-week":
        s = today - timedelta(days=today.weekday())
        return s, s + timedelta(days=6), True
    if periodo == "current-month":
        s = today.replace(day=1)
        e = (date(s.year + 1, 1, 1) if s.month == 12 else date(s.year, s.month + 1, 1)) - timedelta(days=1)
        return s, e, True
    raise ValueError(periodo)


@router.get("/grupo/{go_id}")
def get_grupo(
    response: Response,
    go_id: int,
    periodo: str = Query("current-week"),
) -> dict:
    start, end, is_current = _resolve_period(periodo)
    response.headers["Cache-Control"] = "max-age=60" if is_current else "max-age=300"

    grupo = fetch_one(
        "SELECT go_id, nombre, director, n_sucursales FROM dim_grupos_operativos WHERE go_id = %s",
        (go_id,),
    )
    if not grupo:
        raise HTTPException(status_code=404, detail=f"GO {go_id} no encontrado")

    overall = fetch_one(
        """
        SELECT COUNT(*) AS n_total,
               SUM(CASE WHEN d.status='on_time' THEN 1 ELSE 0 END) AS n_on_time,
               SUM(CASE WHEN d.status='late' THEN 1 ELSE 0 END) AS n_late,
               SUM(CASE WHEN d.status='missed' THEN 1 ELSE 0 END) AS n_missed,
               COALESCE(SUM(d.score), 0)::float AS sum_score
        FROM daily_compliance d
        JOIN dim_sucursales s ON s.location_id = d.sucursal_id
        WHERE s.go_id = %s AND d.day BETWEEN %s AND %s AND s.is_active = TRUE
        """,
        (go_id, start, end),
    ) or {}
    nt = overall.get("n_total") or 0
    pct = round((overall.get("sum_score") or 0) / nt * 100, 2) if nt else 0.0

    sucursales = fetch_all(
        """
        SELECT s.location_id, s.nombre,
               COUNT(*) AS n_total,
               SUM(CASE WHEN d.status='on_time' THEN 1 ELSE 0 END) AS n_on_time,
               SUM(CASE WHEN d.status='late' THEN 1 ELSE 0 END) AS n_late,
               SUM(CASE WHEN d.status='missed' THEN 1 ELSE 0 END) AS n_missed,
               COALESCE(SUM(d.score), 0)::float AS sum_score
        FROM dim_sucursales s
        LEFT JOIN daily_compliance d
            ON d.sucursal_id = s.location_id AND d.day BETWEEN %s AND %s
        WHERE s.go_id = %s AND s.is_active = TRUE
        GROUP BY s.location_id, s.nombre
        ORDER BY (CASE WHEN COUNT(d.*)=0 THEN 0 ELSE SUM(d.score)/COUNT(d.*) END) DESC NULLS LAST
        """,
        (start, end, go_id),
    )
    suc_out = []
    for s in sucursales:
        ntt = s["n_total"] or 0
        suc_out.append({
            "location_id": s["location_id"],
            "nombre": s["nombre"],
            "n_on_time": s["n_on_time"] or 0,
            "n_late": s["n_late"] or 0,
            "n_missed": s["n_missed"] or 0,
            "n_total": ntt,
            "pct_compliance": round((s["sum_score"] or 0) / ntt * 100, 2) if ntt else 0.0,
        })

    return {
        "grupo": grupo,
        "periodo": periodo,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "overall": {
            "n_total": nt,
            "n_on_time": overall.get("n_on_time") or 0,
            "n_late": overall.get("n_late") or 0,
            "n_missed": overall.get("n_missed") or 0,
            "pct_compliance": pct,
        },
        "sucursales": suc_out,
    }
