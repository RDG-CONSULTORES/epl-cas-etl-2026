"""Transform: convierte submissions/tasks Zenput → rows daily_compliance."""
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
    """Convierte el dict de submissions → rows listos para UPSERT a daily_compliance."""
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


def tasks_to_missed_rows(tasks: list[dict],
                         active_sucursal_ids: set[int],
                         project_by_form: dict[int, tuple[int, dict]]
                         ) -> list[dict[str, Any]]:
    """Tasks archived_incomplete → rows con status=missed (score=0)."""
    rows: list[dict[str, Any]] = []
    for t in tasks:
        loc_id = _extract_location_id(t)
        if not loc_id or loc_id not in active_sucursal_ids:
            continue
        form_template_id = _extract_form_template(t)
        proj = project_by_form.get(form_template_id)
        if not proj:
            continue
        project_id, meta = proj
        sched = _extract_scheduled_day(t)
        if not sched:
            continue
        rows.append({
            "sucursal_id": loc_id,
            "day": sched,
            "form_key": meta["key"],
            "project_id": project_id,
            "form_template_id": form_template_id,
            "status": "missed",
            "score": 0.0,
            "submission_id": None,
            "task_id": t.get("id"),
            "completed_at": None,
        })
    log.info("transform missed tasks → %d rows", len(rows))
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
# Helpers de extracción de campos (la forma exacta de Zenput varía
# entre endpoints — manejamos las variantes conocidas).
# ------------------------------------------------------------

def _extract_location_id(payload: dict) -> int | None:
    loc = payload.get("location")
    if isinstance(loc, dict):
        return loc.get("id")
    if isinstance(loc, int):
        return loc
    md = payload.get("smetadata") or payload.get("metadata") or {}
    loc2 = md.get("location")
    if isinstance(loc2, dict):
        return loc2.get("id")
    return payload.get("location_id")


def _extract_task_id(submission: dict) -> int | None:
    if "task_id" in submission:
        return submission["task_id"]
    md = submission.get("smetadata") or {}
    t = md.get("task") or {}
    return t.get("id") if isinstance(t, dict) else None


def _extract_form_template(task: dict) -> int | None:
    ft = task.get("form_template")
    if isinstance(ft, dict):
        return ft.get("id")
    if isinstance(ft, int):
        return ft
    return task.get("form_template_id")


def _extract_scheduled_day(task: dict) -> date | None:
    raw = (task.get("scheduled_date_local")
           or task.get("scheduled_date")
           or task.get("due_date_local")
           or task.get("due_date"))
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = LOCAL_TZ.localize(dt)
            return dt.astimezone(LOCAL_TZ).date()
        except ValueError:
            return None
    return None
