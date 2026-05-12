"""GET /heatmap?periodo=current-week → matriz sucursal × día × form_key con status."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Query, Response

from etl_v2.shared.compliance import LOCAL_TZ
from etl_v2.shared.db import fetch_all

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


@router.get("/heatmap")
def get_heatmap(
    response: Response,
    periodo: str = Query("current-week"),
    go_id: int | None = Query(None),
) -> dict:
    start, end, is_current = _resolve_period(periodo)
    response.headers["Cache-Control"] = "max-age=60" if is_current else "max-age=300"

    params: list = [start, end]
    where_go = ""
    if go_id is not None:
        where_go = " AND s.go_id = %s"
        params.append(go_id)

    cells = fetch_all(
        f"""
        SELECT s.location_id, s.nombre, s.go_id, s.go_nombre,
               d.day, d.form_key, d.status, d.score
        FROM dim_sucursales s
        LEFT JOIN daily_compliance d
            ON d.sucursal_id = s.location_id AND d.day BETWEEN %s AND %s
        WHERE s.is_active = TRUE{where_go}
        ORDER BY s.go_nombre, s.nombre, d.day, d.form_key
        """,
        tuple(params),
    )
    return {
        "periodo": periodo,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "go_id": go_id,
        "cells": [
            {
                "location_id": c["location_id"],
                "sucursal": c["nombre"],
                "go_id": c["go_id"],
                "go_nombre": c["go_nombre"],
                "day": c["day"].isoformat() if c["day"] else None,
                "form_key": c["form_key"],
                "status": c["status"],
                "score": float(c["score"]) if c["score"] is not None else None,
            }
            for c in cells
        ],
    }
