"""Transform: convierte TASKS de Zenput v1 → rows daily_compliance.

Cada task tiene:
- account.id  → sucursal_id
- date_due_local → epoch ms (millis local) — fecha de vencimiento
- current_state → 'complete' / 'overdue' / 'unavailable' / 'archived_*' / 'open'
- is_completed_late → 0/1 (solo cuando complete)
- date_submitted → cuando se completó (epoch ms UTC)

Mapping:
- complete + is_completed_late=0  → on_time (1.0)
- complete + is_completed_late=1  → late    (0.5)
- overdue / unavailable / archived_incomplete → missed (0.0)
- open (todavía en ventana) → skip (no row)
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytz

from etl_v2.shared.compliance import EPL_CAS_PROJECTS, LOCAL_TZ

log = logging.getLogger(__name__)


def _epoch_ms_to_local_date(ms: int | dict | None) -> date | None:
    """date_due_local viene como {'$date': epoch_ms} o int."""
    if ms is None:
        return None
    if isinstance(ms, dict):
        ms = ms.get("$date")
    if ms is None:
        return None
    try:
        # date_due_local ya está en hora local "encoded" (no es UTC realmente,
        # es timestamp en local TZ). Decodificar como UTC y NO convertir.
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.date()
    except (ValueError, TypeError, OSError):
        return None


def _epoch_ms_to_utc(ms: int | dict | None) -> datetime | None:
    if ms is None:
        return None
    if isinstance(ms, dict):
        ms = ms.get("$date")
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=pytz.UTC)
    except (ValueError, TypeError, OSError):
        return None


def _task_status(task: dict) -> tuple[str | None, float | None]:
    """Retorna (status, score) o (None, None) para tasks que se deben skipear."""
    state = (task.get("current_state") or "").lower()
    is_late = task.get("is_completed_late") or 0
    if state == "complete":
        if is_late:
            return ("late", 0.5)
        return ("on_time", 1.0)
    if state in ("overdue", "unavailable", "archived_incomplete", "archived"):
        return ("missed", 0.0)
    if state == "open":
        # Ventana aún activa — no se cuenta aún
        return (None, None)
    # estados desconocidos: tratar como missed por conservador
    log.debug("task state desconocido: %s id=%s", state, task.get("id"))
    return ("missed", 0.0)


def tasks_to_rows(tasks_by_project: dict[int, list[dict]],
                   active_sucursal_ids: set[int],
                   day_range: tuple[date, date] | None = None
                   ) -> list[dict[str, Any]]:
    """Tasks → rows para daily_compliance.

    Solo incluye sucursales en active_sucursal_ids. Skipea tasks 'open'.
    Si `day_range` se pasa, filtra tasks cuyo date_due_local NO está en el rango
    (el API de Zenput filtra por date_modified, no date_due, así que hace falta).
    """
    rows: list[dict[str, Any]] = []
    skipped_open = 0
    skipped_no_loc = 0
    skipped_oos = 0
    skipped_oot = 0  # out of date_due range
    for project_id, tasks in tasks_by_project.items():
        meta = EPL_CAS_PROJECTS[project_id]
        for t in tasks:
            account = t.get("account") or {}
            loc_id = account.get("id")
            if not loc_id:
                skipped_no_loc += 1
                continue
            if loc_id not in active_sucursal_ids:
                skipped_oos += 1
                continue
            day = _epoch_ms_to_local_date(t.get("date_due_local"))
            if not day:
                continue
            if day_range and (day < day_range[0] or day > day_range[1]):
                skipped_oot += 1
                continue
            status, score = _task_status(t)
            if status is None:
                skipped_open += 1
                continue
            completed_at = None
            if status in ("on_time", "late"):
                completed_at = _epoch_ms_to_utc(t.get("date_submitted") or t.get("date_modified"))
            rows.append({
                "sucursal_id": loc_id,
                "day": day,
                "form_key": meta["key"],
                "project_id": project_id,
                "form_template_id": meta["form_template_id"],
                "status": status,
                "score": score,
                "submission_id": None,
                "task_id": t.get("id"),
                "completed_at": completed_at,
            })
    log.info("transform tasks → %d rows (skipped open=%d no_loc=%d oos=%d out_of_day_range=%d)",
             len(rows), skipped_open, skipped_no_loc, skipped_oos, skipped_oot)
    return rows


# Compatibilidad backward: alias
def submissions_to_rows(tasks_by_project: dict[int, list[dict]],
                         active_sucursal_ids: set[int] | None = None
                         ) -> list[dict[str, Any]]:
    return tasks_to_rows(tasks_by_project, active_sucursal_ids or set())


def missed_submissions_to_rows(*args, **kwargs) -> list[dict[str, Any]]:
    # No-op: las tasks ya incluyen los missed (state='overdue'/'unavailable')
    return []


def fill_missing_combinations(*args, **kwargs) -> list[dict[str, Any]]:
    """No-op: las tasks YA representan todas las combinaciones esperadas.
    Si Zenput no creó task para (sucursal, día, form), entonces no había
    expectativa — no debemos inventar un missed.
    """
    return []
