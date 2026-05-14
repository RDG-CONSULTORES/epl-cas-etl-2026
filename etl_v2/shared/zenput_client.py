"""Cliente HTTPX para Zenput API v3 con retry, paginación (meta.next) y logging.

Notas validadas contra el API real (mayo 2026):
- API real es **v3**, no v1. Paths: /api/v3/{submissions,locations,teams,projects,forms}/
- Submissions filtrados por `form_template_id` + `start_date` + `end_date` (epoch ms).
- `status` puede ser `complete`, `incomplete`, `archived_incomplete`.
- Paginación: `meta.next` es una URL absoluta — usarla directamente para iterar.
- `meta.count` puede reportar `10000` como cap; real total se conoce solo iterando.
- Location de una submission vive en `smetadata.location` (no en top-level).
- Proyecto recurrente padre: `smetadata.parent_project.id`.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncIterator

import httpx

from etl_v2.shared.config import settings

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(45.0, connect=10.0)
MAX_RETRIES = 3
DEFAULT_LIMIT = 100  # Zenput v3 acepta 'limit' (no 'page_size'); 100 es el sweet spot
SAFETY_CAP = 200_000  # tope amplio para backfill grande


def _epoch_ms(dt: datetime) -> str:
    return str(int(dt.timestamp() * 1000))


class ZenputClient:
    def __init__(self, token: str | None = None, base_url: str | None = None):
        self.token = token or settings.ZENPUT_TOKEN
        self.base_url = (base_url or settings.ZENPUT_BASE_URL).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ZenputClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-API-TOKEN": self.token, "Accept": "application/json"},
            timeout=DEFAULT_TIMEOUT,
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            await self._client.aclose()

    async def _request(self, method: str, url: str, **kw) -> dict[str, Any]:
        assert self._client is not None, "ZenputClient must be used as async context manager"
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, url, **kw)
                if resp.status_code in (502, 503, 504):
                    raise httpx.HTTPStatusError(f"gateway {resp.status_code}",
                                                request=resp.request, response=resp)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                last_exc = e
                wait = 2 ** attempt
                log.warning("zenput %s %s intento %d falló: %s — retry en %ss",
                            method, url, attempt, e, wait)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(wait)
        assert last_exc is not None
        raise last_exc

    async def _paginate(self, path: str, params: dict | None = None,
                        limit: int = DEFAULT_LIMIT) -> AsyncIterator[dict]:
        """Itera items con limit+offset. Zenput v3 cap absoluto en offset=10000:
        cuando se alcanza ese cap retorna HTTP 400 — se trata como fin grácil.
        """
        params = dict(params or {})
        params["limit"] = limit
        offset = 0
        seen = 0
        while True:
            if offset >= 10000:
                log.info("zenput %s detenido en offset=10000 (cap del API)", path)
                return
            params["offset"] = offset
            try:
                data = await self._request("GET", path, params=params)
            except httpx.HTTPStatusError as e:
                if e.response is not None and e.response.status_code == 400:
                    log.info("zenput %s HTTP 400 en offset=%d → fin grácil", path, offset)
                    return
                raise
            items = data.get("data") or data.get("results") or []
            if not items:
                return
            for item in items:
                yield item
                seen += 1
            if len(items) < limit:
                return
            if seen >= SAFETY_CAP:
                log.warning("zenput %s safety cap %d alcanzado", path, SAFETY_CAP)
                return
            offset += limit

    # ------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------
    async def list_submissions(self, form_template_id: int, start: datetime, end: datetime,
                                status: str | None = None) -> list[dict]:
        """Submissions de un form_template en rango. status opcional:
        'complete', 'incomplete', 'archived_incomplete'.
        """
        params = {
            "form_template_id": form_template_id,
            "start_date": _epoch_ms(start),
            "end_date": _epoch_ms(end),
        }
        if status:
            params["status"] = status
        out: list[dict] = []
        async for sub in self._paginate("/api/v3/submissions/", params):
            out.append(sub)
        log.info("zenput v3 submissions form=%s status=%s rango=%s..%s → %d",
                 form_template_id, status or "*", start.date(), end.date(), len(out))
        return out

    async def list_archived_submissions(self, form_template_id: int,
                                         start: datetime, end: datetime) -> list[dict]:
        """Atajo para submissions con status=archived_incomplete (= missed)."""
        return await self.list_submissions(form_template_id, start, end,
                                           status="archived_incomplete")

    async def list_locations(self) -> list[dict]:
        out: list[dict] = []
        async for loc in self._paginate("/api/v3/locations/"):
            out.append(loc)
        log.info("zenput v3 locations → %d", len(out))
        return out

    async def list_teams(self) -> list[dict]:
        out: list[dict] = []
        async for team in self._paginate("/api/v3/teams/"):
            out.append(team)
        log.info("zenput v3 teams → %d", len(out))
        return out

    async def list_projects(self) -> list[dict]:
        out: list[dict] = []
        async for prj in self._paginate("/api/v3/projects/"):
            out.append(prj)
        log.info("zenput v3 projects → %d", len(out))
        return out
