"""Scoring mixto: on_time=1.0, late=0.5, missed=0.0."""
from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any

import pytz

from etl_v2.shared.config import settings

log = logging.getLogger(__name__)

LOCAL_TZ = pytz.timezone(settings.TZ)

EPL_CAS_PROJECTS = {
    511091345: {
        "title": "*APERTURA EPL CAS",
        "form_template_id": 877142,
        "activity_id": 864763,
        "activity_name": "APERTURA EPL CAS",
        "window_start": "07:00",
        "window_end": "11:00",
        "key": "apertura",
    },
    511091348: {
        "title": "*ENTREGA DE TURNO EPL CAS",
        "form_template_id": 877140,
        "activity_id": 864761,
        "activity_name": "ENTREGA DE TURNO EPL CAS",
        "window_start": "14:00",
        "window_end": "17:00",
        "key": "entrega",
    },
    511091349: {
        "title": "*CIERRE EPL CAS",
        "form_template_id": 877141,
        "activity_id": 864762,
        "activity_name": "CIERRE EPL CAS",
        "window_start": "19:00",
        "window_end": "23:00",
        "key": "cierre",
    },
}

PROJECT_BY_FORM_TEMPLATE = {v["form_template_id"]: (k, v) for k, v in EPL_CAS_PROJECTS.items()}
PROJECT_BY_KEY = {v["key"]: (k, v) for k, v in EPL_CAS_PROJECTS.items()}


def _parse_iso_local(s: str) -> datetime:
    """Parsea timestamp ISO de Zenput. Si trae offset lo respeta; si no, asume LOCAL_TZ."""
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = LOCAL_TZ.localize(dt)
    return dt.astimezone(LOCAL_TZ)


def calcular_score(submission: dict | None, project_window: dict
                   ) -> tuple[str, float, datetime | None]:
    """Retorna (status, score, completed_at_local_or_None)."""
    if not submission:
        return ("missed", 0.0, None)

    md = submission.get("smetadata") or submission.get("metadata") or {}
    raw = (
        md.get("date_submitted_local")
        or md.get("date_submitted")
        or submission.get("date_submitted_local")
        or submission.get("date_submitted")
        or submission.get("completed_at")
    )
    if not raw:
        log.warning("submission sin timestamp; tratando como late id=%s",
                    submission.get("id"))
        return ("late", 0.5, None)

    submitted_at = _parse_iso_local(raw)
    window_start = time.fromisoformat(project_window["window_start"])
    window_end = time.fromisoformat(project_window["window_end"])

    if window_start <= submitted_at.time() <= window_end:
        return ("on_time", 1.0, submitted_at)
    return ("late", 0.5, submitted_at)


def expected_day_for_submission(submitted_at_local: datetime) -> date:
    """Día calendario al que pertenece la submission (zona local)."""
    return submitted_at_local.date()


def aggregate_sucursal_day(scores_by_form: dict[str, float]) -> float:
    """Pct cumplimiento sucursal-día = sum(scores) / 3."""
    return round(sum(scores_by_form.values()) / 3.0, 4)


def aggregate_window(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrega un conjunto de daily_compliance rows en métricas de bucket.

    rows: cada uno con keys status, score.
    Retorna n_on_time, n_late, n_missed, n_total, sum_score, pct_compliance.
    """
    n_on_time = sum(1 for r in rows if r["status"] == "on_time")
    n_late = sum(1 for r in rows if r["status"] == "late")
    n_missed = sum(1 for r in rows if r["status"] == "missed")
    n_total = n_on_time + n_late + n_missed
    sum_score = sum(float(r["score"]) for r in rows)
    pct = round((sum_score / n_total) * 100.0, 2) if n_total else 0.0
    return {
        "n_on_time": n_on_time,
        "n_late": n_late,
        "n_missed": n_missed,
        "n_total": n_total,
        "sum_score": round(sum_score, 2),
        "pct_compliance": pct,
    }
