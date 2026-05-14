"""Extract: descarga submissions de Zenput v3 para los 3 form templates EPL CAS.

Incluye submissions completas (on_time/late) y archived_incomplete (missed).
"""
from __future__ import annotations

import logging
from datetime import datetime

from etl_v2.shared.compliance import EPL_CAS_PROJECTS
from etl_v2.shared.zenput_client import ZenputClient

log = logging.getLogger(__name__)


async def extract_submissions(start: datetime, end: datetime
                              ) -> dict[int, list[dict]]:
    """Submissions COMPLETAS de las 3 activities EPL CAS.

    Filtramos por activity_id (recurrent activity) + status=complete.
    Esto trae SOLO submissions reales (no drafts/incomplete), evitando el
    cap de 10K hits del API.

    Retorna {project_id: [submissions]}. Doble check por
    `smetadata.parent_project.id` por si el API retorna algo de otro proyecto.
    """
    out: dict[int, list[dict]] = {}
    async with ZenputClient() as zc:
        for project_id, meta in EPL_CAS_PROJECTS.items():
            subs = await zc.list_submissions(
                meta["activity_id"], start, end, status="complete")
            filtered = [s for s in subs if _belongs_to_project(s, project_id)]
            out[project_id] = filtered
            log.info("extract project=%s activity=%s subs_total=%d in_scope=%d",
                     project_id, meta["activity_id"], len(subs), len(filtered))
    return out


async def extract_missed_submissions(start: datetime, end: datetime
                                      ) -> dict[int, list[dict]]:
    """Submissions archived_incomplete (= missed) de las 3 activities EPL CAS."""
    out: dict[int, list[dict]] = {}
    async with ZenputClient() as zc:
        for project_id, meta in EPL_CAS_PROJECTS.items():
            subs = await zc.list_archived_submissions(
                meta["activity_id"], start, end)
            filtered = [s for s in subs if _belongs_to_project(s, project_id)]
            out[project_id] = filtered
            log.info("extract missed project=%s activity=%s archived=%d in_scope=%d",
                     project_id, meta["activity_id"], len(subs), len(filtered))
    return out


def _belongs_to_project(submission: dict, project_id: int) -> bool:
    """Liga submission al proyecto padre via smetadata.parent_project.id."""
    md = submission.get("smetadata") or {}
    parent = md.get("parent_project") or {}
    pid = parent.get("id") if isinstance(parent, dict) else None
    return pid == project_id
