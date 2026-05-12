"""Extract: descarga submissions + tasks de Zenput para los 3 proyectos EPL CAS."""
from __future__ import annotations

import logging
from datetime import datetime

from etl_v2.shared.compliance import EPL_CAS_PROJECTS
from etl_v2.shared.zenput_client import ZenputClient

log = logging.getLogger(__name__)


async def extract_submissions(start: datetime, end: datetime
                              ) -> dict[int, list[dict]]:
    """Descarga submissions de los 3 form templates EPL CAS.

    Retorna {project_id: [submissions]}.
    """
    out: dict[int, list[dict]] = {}
    async with ZenputClient() as zc:
        for project_id, meta in EPL_CAS_PROJECTS.items():
            subs = await zc.list_submissions(meta["form_template_id"], start, end)
            filtered = [s for s in subs if _belongs_to_project(s, project_id)]
            out[project_id] = filtered
            log.info("extract project=%s form=%s submissions_total=%d in_scope=%d",
                     project_id, meta["form_template_id"], len(subs), len(filtered))
    return out


async def extract_missed_tasks(start: datetime, end: datetime) -> list[dict]:
    """Descarga tasks status=archived_incomplete (= missed) en el rango."""
    async with ZenputClient() as zc:
        return await zc.list_tasks(start, end, status="archived_incomplete")


def _belongs_to_project(submission: dict, project_id: int) -> bool:
    """Liga submission al proyecto padre via smetadata.parent_project.id."""
    md = submission.get("smetadata") or submission.get("metadata") or {}
    parent = md.get("parent_project") or {}
    pid = parent.get("id") if isinstance(parent, dict) else None
    return pid == project_id
