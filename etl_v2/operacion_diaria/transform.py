"""Transform: convierte submissions Zenput v3 → rows daily_compliance."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import pytz

from etl_v2.shared.compliance import (
    EPL_CAS_PROJECTS,
    LOCAL_TZ,
    calcular_score,
    expected_day_for_submission,
)

log = logging.getLogger(__name__)


def submissions_to_rows(submissions_by_project: dict[int, list[dict]]
                        ) -> list[dict[str, Any]]:
    """Submissions completas → rows on_time/late con UPSERT a daily_compliance."""
    rows: list[dict[str, Any]] = []
    for project_id, subs in submissions_by_project.items():
        meta = EPL_CAS_PROJECTS[project_id]
        for sub in subs:
            location_id = _extract_location_id(sub)
            if not location_id:
                continue
            status, score, completed_at = calcular_score(sub, meta)
            if completed_at is None:
                continue
            day = expected_day_for_submission(completed_at)
            rows.append({
                "sucursal_id": location_id,
                "day": day,
                "form_key": meta["key"],
                "project_id": project_id,
                "form_template_id": meta["form_template_id"],
                "status": status,
                "score": score,
                "submission_id": str(sub.get("id") or ""),
                "task_id": _extract_task_id(sub),
                "completed_at": completed_at.astimezone(pytz.UTC),
            })
    log.info("transform submissions → %d rows", len(rows))
    return rows


def missed_submissions_to_rows(missed_by_project: dict[int, list[dict]],
                                active_sucursal_ids: set[int]
                                ) -> list[dict[str, Any]]:
    """Submissions archived_incomplete (= missed) → rows con status=missed, score=0."""
    rows: list[dict[str, Any]] = []
    for project_id, subs in missed_by_project.items():
        meta = EPL_CAS_PROJECTS[project_id]
        for sub in subs:
            location_id = _extract_location_id(sub)
            if not location_id or location_id not in active_sucursal_ids:
                continue
            day = _extract_missed_day(sub)
            if not day:
                continue
            rows.append({
                "sucursal_id": location_id,
                "day": day,
                "form_key": meta["key"],
                "project_id": project_id,
                "form_template_id": meta["form_template_id"],
                "status": "missed",
                "score": 0.0,
                "submission_id": str(sub.get("id") or ""),
                "task_id": _extract_task_id(sub),
                "completed_at": None,
            })
    log.info("transform missed submissions → %d rows", len(rows))
    return rows


def fill_missing_combinations(active_sucursales: list[dict],
                              start_day: date,
                              end_day: date,
                              existing_keys: set[tuple[int, date, str]]
                              ) -> list[dict[str, Any]]:
    """Para cada sucursal×día×form sin registro, genera row missed."""
    rows: list[dict[str, Any]] = []
    forms = list(EPL_CAS_PROJECTS.values())
    day = start_day
    while day <= end_day:
        for suc in active_sucursales:
            sid = suc["location_id"]
            for meta in forms:
                key = (sid, day, meta["key"])
                if key in existing_keys:
                    continue
                project_id = next(
                    pid for pid, m in EPL_CAS_PROJECTS.items() if m["key"] == meta["key"]
                )
                rows.append({
                    "sucursal_id": sid,
                    "day": day,
                    "form_key": meta["key"],
                    "project_id": project_id,
                    "form_template_id": meta["form_template_id"],
                    "status": "missed",
                    "score": 0.0,
                    "submission_id": None,
                    "task_id": None,
                    "completed_at": None,
                })
        day += timedelta(days=1)
    log.info("fill_missing_combinations rango=%s..%s → %d rows missed",
             start_day, end_day, len(rows))
    return rows


# ------------------------------------------------------------
# Helpers de extracción de campos para Zenput v3 (location vive
# dentro de smetadata, no en top-level).
# ------------------------------------------------------------

def _extract_location_id(submission: dict) -> int | None:
    md = submission.get("smetadata") or {}
    loc = md.get("location")
    if isinstance(loc, dict):
        return loc.get("id")
    if isinstance(loc, int):
        return loc
    # Fallback: en algunos endpoints viene en top-level
    loc2 = submission.get("location")
    if isinstance(loc2, dict):
        return loc2.get("id")
    if isinstance(loc2, int):
        return loc2
    return None


def _extract_task_id(submission: dict) -> int | None:
    md = submission.get("smetadata") or {}
    t = md.get("task")
    if isinstance(t, dict):
        return t.get("id")
    if isinstance(t, int):
        return t
    return None


def _extract_missed_day(submission: dict) -> date | None:
    """Para una submission archived_incomplete, ¿a qué día calendario pertenece?

    Preferencia: date_completed_local > date_submitted_local > date_created_local.
    """
    md = submission.get("smetadata") or {}
    for key in ("date_completed_local", "date_submitted_local", "date_created_local"):
        raw = md.get(key)
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = LOCAL_TZ.localize(dt)
            return dt.astimezone(LOCAL_TZ).date()
        except (ValueError, AttributeError):
            continue
    return None
