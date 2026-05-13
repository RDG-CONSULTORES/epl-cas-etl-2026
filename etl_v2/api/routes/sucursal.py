"""GET /sucursal/{location_id}?periodo=current-week → días + por-form de una sucursal."""
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


@router.get("/sucursal/{location_id}")
def get_sucursal(
    response: Response,
    location_id: int,
    periodo: str = Query("current-week"),
) -> dict:
    start, end, is_current = _resolve_period(periodo)
    response.headers["Cache-Control"] = "max-age=60" if is_current else "max-age=300"

    suc = fetch_one(
        "SELECT location_id, nombre, go_id, go_nombre FROM dim_sucursales WHERE location_id = %s",
        (location_id,),
    )
    if not suc:
        raise HTTPException(status_code=404, detail=f"Sucursal {location_id} no encontrada")

    days = fetch_all(
        """
        SELECT day, form_key, status, score, completed_at, submission_id
        FROM daily_compliance
        WHERE sucursal_id = %s AND day BETWEEN %s AND %s
        ORDER BY day, form_key
        """,
        (location_id, start, end),
    )

    by_day: dict[str, dict] = {}
    for r in days:
        k = r["day"].isoformat()
        by_day.setdefault(k, {"day": k, "forms": {}})
        by_day[k]["forms"][r["form_key"]] = {
            "status": r["status"],
            "score": float(r["score"]),
            "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            "submission_id": r["submission_id"],
        }
    for k, entry in by_day.items():
        scores = [f["score"] for f in entry["forms"].values()]
        entry["pct_day"] = round(sum(scores) / 3 * 100, 2)

    return {
        "sucursal": suc,
        "periodo": periodo,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": [by_day[k] for k in sorted(by_day)],
    }
