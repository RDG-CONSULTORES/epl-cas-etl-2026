"""Transform: convierte submissions v3 → rows daily_compliance.

Fórmula validada (2026-05-16) contra fotos Zenput Project Completion:

Cada submission tiene:
- smetadata.location.id           → sucursal_id
- smetadata.date_created_local    → fecha de la task (date_due)
- smetadata.date_completed_local  → cuándo se completó (None = no completada)
- smetadata.task.id               → task_id

Clasificación por fecha + hora:
- Sin date_completed_local              → skip (no fabricar nada)
- completed_local.date() != task_date   → missed (Zenput la auto-archivó como Cut/Failed)
- mismo día, dentro de ventana          → on_time
- mismo día, fuera de ventana           → late

Resultado en DB ±2-3 pts vs fotos Zenput. El leve gap proviene del boundary
exacto de Zenput (probablemente date_due específico de la task, no la ventana
del proyecto), pero a nivel GO es despreciable.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import Any

import pytz

from etl_v2.shared.compliance import EPL_CAS_PROJECTS, LOCAL_TZ

log = logging.getLogger(__name__)


def _parse_local(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _to_utc(dt_local: datetime) -> datetime:
    """Convierte datetime local (naive) a UTC aware."""
    if dt_local.tzinfo is None:
        dt_local = LOCAL_TZ.localize(dt_local)
    return dt_local.astimezone(pytz.UTC)


def _window_hours(meta: dict) -> tuple[int, int]:
    """('07:00','11:00') → (7, 11)."""
    ws = time.fromisoformat(meta["window_start"]).hour
    we = time.fromisoformat(meta["window_end"]).hour
    return ws, we


_PRIO = {'on_time': 3, 'late': 2, 'missed': 1}


def submissions_to_rows(submissions_by_project: dict[int, list[dict]],
                         active_sucursal_ids: set[int] | None = None,
                         day_range: tuple[date, date] | None = None
                         ) -> list[dict[str, Any]]:
    """Submissions → rows para daily_compliance.

    - Filtra sucursales con `active_sucursal_ids` (si pasa None, acepta todas).
    - Filtra task_date dentro de `day_range` (si pasa None, acepta todas).
    - Si llegan múltiples submissions para misma (sucursal, día, form), aplica
      prioridad on_time(3) > late(2) > missed(1).
    """
    active = active_sucursal_ids if active_sucursal_ids is not None else None
    by_key: dict[tuple[int, date, str], dict[str, Any]] = {}
    skipped_no_loc = skipped_oos = skipped_no_created = skipped_no_completed = 0
    skipped_oor = 0

    for project_id, subs in submissions_by_project.items():
        meta = EPL_CAS_PROJECTS[project_id]
        form_key = meta["key"]
        win_start, win_end = _window_hours(meta)
        form_template_id = meta["form_template_id"]

        for s in subs:
            sm = s.get("smetadata") or {}
            loc = sm.get("location") or {}
            loc_id = loc.get("id")
            if not loc_id:
                skipped_no_loc += 1
                continue
            if active is not None and loc_id not in active:
                skipped_oos += 1
                continue

            created_local = _parse_local(sm.get("date_created_local"))
            if not created_local:
                skipped_no_created += 1
                continue
            task_date = created_local.date()
            if day_range and (task_date < day_range[0] or task_date > day_range[1]):
                skipped_oor += 1
                continue

            completed_local = _parse_local(sm.get("date_completed_local"))
            if not completed_local:
                # Submission existe pero no se completó (Zenput posiblemente
                # la marcará archived_incomplete después). Por ahora skip.
                skipped_no_completed += 1
                continue

            # Clasificación
            if completed_local.date() != task_date:
                status, score = "missed", 0.0
            else:
                h = completed_local.hour
                if win_start <= h < win_end:
                    status, score = "on_time", 1.0
                else:
                    status, score = "late", 0.5

            key = (loc_id, task_date, form_key)
            prev = by_key.get(key)
            if prev is None or _PRIO[status] > _PRIO[prev["status"]]:
                by_key[key] = {
                    "sucursal_id": loc_id,
                    "day": task_date,
                    "form_key": form_key,
                    "project_id": project_id,
                    "form_template_id": form_template_id,
                    "status": status,
                    "score": score,
                    "submission_id": s.get("id"),
                    "task_id": (sm.get("task") or {}).get("id"),
                    "completed_at": _to_utc(completed_local),
                }

    log.info(
        "transform submissions → %d rows (skipped no_loc=%d oos=%d no_created=%d "
        "no_completed=%d oor=%d)",
        len(by_key), skipped_no_loc, skipped_oos, skipped_no_created,
        skipped_no_completed, skipped_oor,
    )
    return list(by_key.values())


# Compatibilidad backward (los crons importan estos nombres)
def tasks_to_rows(*args, **kwargs):
    """DEPRECATED: usar submissions_to_rows."""
    return submissions_to_rows(*args, **kwargs)


def missed_submissions_to_rows(*args, **kwargs) -> list[dict[str, Any]]:
    """No-op: el missed se deriva en submissions_to_rows por completed_date !=
    task_date. No se hace fetch separado de archived_incomplete (validado: cuadra).
    """
    return []


def fill_missing_combinations(*args, **kwargs) -> list[dict[str, Any]]:
    """No-op intencional. Si Zenput no creó task → no debemos fabricar missed.
    Sucursales que NUNCA reportan (SALTILLO, RIO BRAVO, SABINAS) aparecen al 0%
    via LEFT JOIN desde dim_sucursales en los endpoints del dashboard.
    """
    return []
