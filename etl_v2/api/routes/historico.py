"""GET /historico?scope=global|go|sucursal&scope_id=...&semanas=N → serie semanal."""
from __future__ import annotations

from fastapi import APIRouter, Query, Response

from etl_v2.shared.db import fetch_all

router = APIRouter()


@router.get("/historico")
def get_historico(
    response: Response,
    scope: str = Query("global", pattern="^(global|go|sucursal)$"),
    scope_id: int | None = Query(None),
    semanas: int = Query(8, ge=1, le=52),
    form_key: str = Query("overall"),
) -> dict:
    response.headers["Cache-Control"] = "max-age=300"

    params: list = [scope, form_key, semanas]
    where_scope_id = "scope_id IS NULL"
    if scope_id is not None:
        where_scope_id = "scope_id = %s"
        params.insert(2, scope_id)

    rows = fetch_all(
        f"""
        SELECT week_start, pct_compliance, n_total, n_on_time, n_late, n_missed,
               delta_prev_week
        FROM weekly_summary
        WHERE scope = %s AND form_key = %s AND {where_scope_id}
        ORDER BY week_start DESC
        LIMIT %s
        """,
        tuple(params),
    )
    return {
        "scope": scope,
        "scope_id": scope_id,
        "form_key": form_key,
        "items": [
            {
                "week_start": r["week_start"].isoformat(),
                "pct_compliance": float(r["pct_compliance"]) if r["pct_compliance"] is not None else 0.0,
                "n_total": r["n_total"],
                "n_on_time": r["n_on_time"],
                "n_late": r["n_late"],
                "n_missed": r["n_missed"],
                "delta_prev_week": float(r["delta_prev_week"]) if r["delta_prev_week"] is not None else None,
            }
            for r in reversed(rows)
        ],
    }
