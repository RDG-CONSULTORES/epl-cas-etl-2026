"""Evidencia fotográfica: convierte los s3_key de las submissions en URLs firmadas
de Zenput (Media v2 storage). Las URLs expiran ~24h → se piden bajo demanda.
"""
from __future__ import annotations

import logging
import urllib.parse

import httpx

from etl_plog.shared.config import settings

log = logging.getLogger(__name__)
STORAGE = "https://www.zenput.com/api/v2/users/current/storage/"
MAX_FOTOS = 12


def s3_keys_de(payload: dict) -> list[tuple[str, str, str]]:
    """-> [(titulo, s3_key, tipo)] de campos imagen/video/firma de una submission.
    image/video = lista de dicts con s3_key; signature = lista de strings (el s3_key)."""
    out = []
    for a in payload.get("answers", []):
        ft = a.get("field_type")
        v = a.get("value")
        if ft in ("image", "video") and isinstance(v, list):
            for m in v:
                if isinstance(m, dict) and m.get("s3_key"):
                    out.append((a.get("title", "Evidencia"), m["s3_key"], ft))
        elif ft == "signature" and isinstance(v, list):
            for key in v:
                if isinstance(key, str) and key:
                    out.append((a.get("title", "Firma"), key, "signature"))
    return out[:MAX_FOTOS]


def url_firmada(client: httpx.Client, s3_key: str) -> str | None:
    try:
        r = client.get(STORAGE, params={"path": s3_key},
                       headers={"X-API-TOKEN": settings.ZENPUT_TOKEN}, timeout=20)
        if r.status_code == 200:
            return (r.json().get("data") or {}).get("location")
    except httpx.HTTPError as e:
        log.warning("foto %s: %s", s3_key[:40], e)
    return None


def fotos_de_payload(payload: dict) -> list[dict]:
    """-> [{titulo, url, tipo}] con URLs firmadas (foto/video/firma)."""
    keys = s3_keys_de(payload)
    if not keys:
        return []
    out = []
    with httpx.Client() as c:
        for titulo, key, tipo in keys:
            url = url_firmada(c, key)
            if url:
                out.append({"titulo": titulo, "url": url, "tipo": tipo})
    return out
