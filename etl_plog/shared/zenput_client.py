"""Cliente síncrono Zenput v3 para etl_plog (httpx, retry, paginación meta.next).

Validado contra el API real (discovery 2026-08-11):
- Submissions por `form_template_id` + `start_date`/`end_date` (epoch ms).
- Location de la submission vive en `smetadata.location`.
- Paginación: `meta.next` = URL absoluta.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Iterator

import httpx

from etl_plog.shared.config import settings

log = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(45.0, connect=10.0)
MAX_RETRIES = 3
LIMIT = 100
SAFETY_CAP = 200_000


def _epoch_ms(dt: datetime) -> str:
    return str(int(dt.timestamp() * 1000))


class ZenputClient:
    def __init__(self, token: str | None = None):
        self._client = httpx.Client(
            base_url=settings.ZENPUT_BASE_URL,
            headers={"X-API-TOKEN": token or settings.ZENPUT_TOKEN},
            timeout=TIMEOUT,
        )

    def close(self) -> None:
        self._client.close()

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict:
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.get(url, params=params)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                wait = 2 ** (attempt + 1)
                log.warning("Zenput retry %s en %ss: %s", attempt + 1, wait, e)
                time.sleep(wait)
        raise RuntimeError("unreachable")

    def _paginate(self, path: str, params: dict[str, Any]) -> Iterator[dict]:
        params = {**params, "limit": LIMIT}
        url: str | None = path
        seen = 0
        while url:
            resp = self._get(url, params=params if url == path else None)
            data = resp.get("data", [])
            yield from data
            seen += len(data)
            if seen >= SAFETY_CAP:
                log.warning("SAFETY_CAP alcanzado en %s", path)
                return
            url = (resp.get("meta") or {}).get("next")

    def submissions(self, form_template_id: int,
                    start: datetime | None = None,
                    end: datetime | None = None) -> Iterator[dict]:
        params: dict[str, Any] = {"form_template_id": form_template_id}
        if start:
            params["start_date"] = _epoch_ms(start)
        if end:
            params["end_date"] = _epoch_ms(end)
        yield from self._paginate("/submissions/", params)

    def locations(self) -> list[dict]:
        return list(self._paginate("/locations/", {}))

    def teams(self) -> list[dict]:
        return list(self._paginate("/teams/", {}))
