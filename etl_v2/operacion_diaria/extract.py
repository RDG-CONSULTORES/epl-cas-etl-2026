"""Extract: descarga TASKS (no submissions) de Zenput.

Una task = asignación recurrente para una sucursal en un día específico.
Esto es lo que Zenput usa para su reporte 'Project Completion'.

Status de tasks:
- current_state='complete' + is_completed_late=0  → on_time  (score 1.0)
- current_state='complete' + is_completed_late=1  → late      (score 0.5)
- current_state in ('overdue','unavailable','archived_incomplete') → missed (score 0.0)
- current_state='open'  → no se cuenta (aún en ventana)
"""
from __future__ import annotations

import logging
from datetime import datetime

from etl_v2.shared.compliance import EPL_CAS_PROJECTS
from etl_v2.shared.zenput_client import ZenputClient

log = logging.getLogger(__name__)


async def extract_tasks(start: datetime, end: datetime) -> dict[int, list[dict]]:
    """Tasks de las 3 activities EPL CAS en el rango.

    Retorna {project_id: [tasks]}. Las tasks vienen del endpoint v1
    /api/v1/tasks/list_tasks/ con `is_completed_late` y `current_state`.
    """
    out: dict[int, list[dict]] = {}
    async with ZenputClient() as zc:
        for project_id, meta in EPL_CAS_PROJECTS.items():
            tasks = await zc.list_tasks(meta["activity_id"], start, end)
            out[project_id] = tasks
            log.info("extract tasks project=%s activity=%s tasks=%d",
                     project_id, meta["activity_id"], len(tasks))
    return out


# Compatibilidad backward: alias para que el resto del módulo siga importando
extract_submissions = extract_tasks


async def extract_missed_submissions(start: datetime, end: datetime
                                      ) -> dict[int, list[dict]]:
    """DEPRECATED: ahora todo viene en extract_tasks (las tasks incluyen
    los missed via current_state). Se deja como no-op para no romper imports.
    """
    return {pid: [] for pid in EPL_CAS_PROJECTS}
