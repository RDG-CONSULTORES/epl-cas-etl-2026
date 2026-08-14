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


def s3_keys_de(payload: dict) -> list[tuple[str, str]]:
    """-> [(titulo_campo, s3_key)] de los campos imagen de una submission."""
    out = []
    for a in payload.get("answers", []):
        if a.get("field_type") == "image":
            v = a.get("value")
            if isinstance(v, list):
                for foto in v:
                    if isinstance(foto, dict) and foto.get("s3_key"):
                        out.append((a.get("title", "Foto"), foto["s3_key"]))
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
    """-> [{titulo, url}] con las URLs firmadas listas para mostrar."""
    keys = s3_keys_de(payload)
    if not keys:
        return []
    out = []
    with httpx.Client() as c:
        for titulo, key in keys:
            url = url_firmada(c, key)
            if url:
                out.append({"titulo": titulo, "url": url})
    return out
