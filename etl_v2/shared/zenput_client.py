"""Cliente HTTPX para Zenput API con retry, paginación y logging.

Gotchas validados (documentar para futuros lectores):
- /api/v1/tasks/list_tasks/ NECESITA include_future_tasks_v2=true.
- Fechas: string de milisegundos epoch plano, NO {"$date": ...}.
- Cap ~10K por listado; segmentar rangos cortos si se requiere más.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncIterator

import httpx

from etl_v2.shared.config import settings

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
MAX_RETRIES = 3
PAGE_SIZE = 1000


def _epoch_ms(dt: datetime) -> str:
    return str(int(dt.timestamp() * 1000))


class ZenputClient:
    def __init__(self, token: str | None = None, base_url: str | None = None):
        self.token = token or settings.ZENPUT_API_TOKEN
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

    async def _request(self, method: str, path: str, **kw) -> dict[str, Any]:
        assert self._client is not None, "ZenputClient must be used as async context manager"
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kw)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(f"server {resp.status_code}", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                last_exc = e
                wait = 2 ** attempt
                log.warning("zenput %s %s intento %d falló: %s — retry en %ss",
                            method, path, attempt, e, wait)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(wait)
        assert last_exc is not None
        raise last_exc

    async def _paginate(self, path: str, params: dict, results_key: str = "results") -> AsyncIterator[dict]:
        total_yielded = 0
        page = 1
        while True:
            p = {**params, "page": page, "page_size": PAGE_SIZE}
            data = await self._request("GET", path, params=p)
            items = data.get(results_key) or data.get("data") or []
            if not items and isinstance(data, list):
                items = data
            for item in items:
                yield item
                total_yielded += 1
            if total_yielded >= 10_000:
                log.warning("zenput %s alcanzó cap 10K — segmentar rango", path)
                break
            if not data.get("next") and len(items) < PAGE_SIZE:
                break
            page += 1
            if page > 50:
                log.warning("zenput %s safety break en page=50", path)
                break

    # ------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------
    async def list_submissions(self, form_template_id: int, start: datetime, end: datetime
                               ) -> list[dict]:
        params = {
            "form_template_id": form_template_id,
            "start_date": _epoch_ms(start),
            "end_date": _epoch_ms(end),
        }
        out: list[dict] = []
        async for sub in self._paginate("/api/v1/submissions/list_submissions/", params):
            out.append(sub)
        log.info("zenput submissions form=%s rango=%s..%s → %d",
                 form_template_id, start.date(), end.date(), len(out))
        return out

    async def list_tasks(self, start: datetime, end: datetime,
                         status: str | None = None) -> list[dict]:
        params = {
            "include_future_tasks_v2": "true",
            "start_date": _epoch_ms(start),
            "end_date": _epoch_ms(end),
        }
        if status:
            params["status"] = status
        out: list[dict] = []
        async for task in self._paginate("/api/v1/tasks/list_tasks/", params):
            out.append(task)
        log.info("zenput tasks rango=%s..%s status=%s → %d",
                 start.date(), end.date(), status, len(out))
        return out

    async def list_locations(self) -> list[dict]:
        out: list[dict] = []
        async for loc in self._paginate("/api/v1/locations/list_locations/", {}):
            out.append(loc)
        log.info("zenput locations → %d", len(out))
        return out

    async def list_teams(self) -> list[dict]:
        out: list[dict] = []
        async for team in self._paginate("/api/v1/teams/list_teams/", {}):
            out.append(team)
        log.info("zenput teams → %d", len(out))
        return out

    async def list_projects(self) -> list[dict]:
        out: list[dict] = []
        async for prj in self._paginate("/api/v1/projects/list_projects/", {}):
            out.append(prj)
        log.info("zenput projects → %d", len(out))
        return out
