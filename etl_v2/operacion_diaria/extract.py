"""Extract: descarga SUBMISSIONS v3 de Zenput.

Validado contra fotos Project Completion 2025-05-16 (ver backfill_full.py).

API quirks aprendidos:
- /v3/submissions/?activity_id=X devuelve hasta 10K submissions (cap del API)
- start_date / end_date / account_id en query NO filtran realmente — el API
  los ignora. Filtramos client-side por `smetadata.date_created_local`.
- status, date_completed top-level siempre None. Los reales están en smetadata.
- Items vienen oldest-first; el "último" en el resultado es el más reciente,
  así que 10K cap nos da los más recientes (perdemos histórico antiguo, no
  data reciente).

Mapping fields:
- smetadata.location.id           → sucursal_id
- smetadata.date_created_local    → date_due (= día de la task)
- smetadata.date_completed_local  → completed_at (None = no completada)
- smetadata.task.id               → task_id
- smetadata.parent_project.id     → project_id
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from etl_v2.shared.compliance import EPL_CAS_PROJECTS, LOCAL_TZ
from etl_v2.shared.zenput_client import ZenputClient

log = logging.getLogger(__name__)


def _parse_local(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _submission_in_range(s: dict, start_local: datetime, end_local: datetime
                          ) -> bool:
    """True si la task fue creada (= scheduled) en [start, end] local."""
    sm = s.get("smetadata") or {}
    created = _parse_local(sm.get("date_created_local"))
    if not created:
        return False
    # start_local / end_local should be naive local (or LOCAL_TZ-aware)
    if start_local.tzinfo:
        start_local = start_local.replace(tzinfo=None)
    if end_local.tzinfo:
        end_local = end_local.replace(tzinfo=None)
    return start_local <= created <= end_local


async def extract_submissions(start: datetime, end: datetime
                               ) -> dict[int, list[dict]]:
    """Trae submissions v3 de las 3 activities EPL CAS para el rango [start, end].

    Retorna {project_id: [submissions]} donde cada submission tiene
    smetadata.date_created_local dentro del rango.

    Nota: paginar full 10K en cada llamada porque el API ignora date filters.
    Tiempo: ~100s por activity × 3 = ~5 min. Para hourly esto es aceptable.
    """
    out: dict[int, list[dict]] = {}
    async with ZenputClient() as zc:
        for project_id, meta in EPL_CAS_PROJECTS.items():
            activity_id = meta["activity_id"]
            all_subs = await zc.list_submissions(activity_id, start, end)
            filtered = [s for s in all_subs if _submission_in_range(s, start, end)]
            out[project_id] = filtered
            log.info("extract submissions activity=%s key=%s pulled=%d filtered=%d",
                     activity_id, meta["key"], len(all_subs), len(filtered))
    return out


async def extract_missed_submissions(start: datetime, end: datetime
                                      ) -> dict[int, list[dict]]:
    """DEPRECATED: missed se deriva en transform por (completed_local.date() !=
    task_date). No se hace fetch separado de archived_incomplete.
    """
    return {pid: [] for pid in EPL_CAS_PROJECTS}
