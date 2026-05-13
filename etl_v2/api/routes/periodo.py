"""GET /periodo?tipo=week|month&offset=0  → metadata del periodo activo."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytz
from fastapi import APIRouter, Query, Response

from etl_v2.shared.compliance import LOCAL_TZ

router = APIRouter()


@router.get("/periodo")
def get_periodo(
    response: Response,
    tipo: str = Query("week", pattern="^(week|month)$"),
    offset: int = Query(0, ge=-52, le=0),
) -> dict:
    today = datetime.now(LOCAL_TZ).date()
    if tipo == "week":
        monday = today - timedelta(days=today.weekday())
        start = monday + timedelta(weeks=offset)
        end = start + timedelta(days=6)
    else:
        first = today.replace(day=1)
        year, month = first.year, first.month + offset
        while month <= 0:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)

    is_current = start <= today <= end
    response.headers["Cache-Control"] = "max-age=60" if is_current else "max-age=300"
    return {
        "tipo": tipo,
        "offset": offset,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "is_current": is_current,
        "today": today.isoformat(),
    }
