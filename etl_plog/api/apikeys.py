"""API keys para la superficie externa read-only (/api/v1).

Modelo: cada consumidor (ej. sistemas de EPL) recibe UNA llave opaca que empieza
con `plog_live_`. En la BD solo vive su hash SHA-256 — la llave en claro se muestra
una sola vez al crearla y nunca más se puede recuperar (como en Stripe/GitHub).

La dependencia `require_api_key` valida la llave, aplica un rate-limit ligero en
memoria y audita cada llamada en `api_access_log`. Devuelve el registro de la llave
(incluye `zonas` para acotar los resultados por zona si aplica).
"""
from __future__ import annotations

import hashlib
import secrets
import time
from collections import deque

from fastapi import HTTPException, Request

from etl_plog.shared.db import conn

PREFIJO = "plog_live_"
RATE_MAX = 120          # llamadas
RATE_VENTANA = 60.0     # segundos (ventana deslizante por llave)

# Ventana deslizante en memoria: key_id -> deque[timestamps]. Suficiente para 1 réplica;
# si algún día hay varias, mover a Redis. Degradación: si se reinicia, se reinicia el conteo.
_hits: dict[int, deque] = {}


def _hash(llave: str) -> str:
    return hashlib.sha256(llave.encode()).hexdigest()


def genera_llave() -> tuple[str, str, str]:
    """Crea una llave nueva. -> (llave_en_claro, prefijo_visible, hash). Guardar solo el hash."""
    cuerpo = secrets.token_urlsafe(32)
    llave = f"{PREFIJO}{cuerpo}"
    return llave, llave[: len(PREFIJO) + 6], _hash(llave)


def crea_api_key(etiqueta: str, zonas: list[str] | None = None,
                 creado_por: str = "admin", notas: str | None = None) -> dict:
    """Registra una llave nueva y devuelve {id, etiqueta, llave} (la llave, solo esta vez)."""
    llave, prefijo, h = genera_llave()
    with conn() as c:
        row = c.execute(
            """INSERT INTO api_keys (etiqueta, key_prefix, key_hash, zonas, creado_por, notas)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (etiqueta, prefijo, h, zonas, creado_por, notas)).fetchone()
    return {"id": row["id"], "etiqueta": etiqueta, "zonas": zonas, "llave": llave}


def revoca_api_key(key_id: int) -> bool:
    with conn() as c:
        r = c.execute("UPDATE api_keys SET activo=FALSE WHERE id=%s", (key_id,))
        return r.rowcount > 0


def _rate_limit(key_id: int) -> None:
    import math
    ahora = time.monotonic()
    q = _hits.setdefault(key_id, deque())
    while q and ahora - q[0] > RATE_VENTANA:
        q.popleft()
    if len(q) >= RATE_MAX:
        # segundos hasta que la petición más vieja salga de la ventana → el cliente puede reintentar
        retry = max(1, math.ceil(RATE_VENTANA - (ahora - q[0])))
        raise HTTPException(
            429, f"Límite de {RATE_MAX} solicitudes por minuto excedido",
            headers={"Retry-After": str(retry),
                     "X-RateLimit-Limit": str(RATE_MAX),
                     "X-RateLimit-Remaining": "0"})
    q.append(ahora)


def require_api_key(request: Request) -> dict:
    """Dependencia FastAPI: valida X-API-Key. -> registro de la llave. 401 si inválida."""
    presentada = request.headers.get("X-API-Key") or ""
    if not presentada.startswith(PREFIJO):
        raise HTTPException(401, "Falta o es inválida la cabecera X-API-Key")
    with conn() as c:
        k = c.execute(
            "SELECT id, etiqueta, zonas, activo FROM api_keys WHERE key_hash=%s",
            (_hash(presentada),)).fetchone()
    if not k or not k["activo"]:
        raise HTTPException(401, "API key inválida o revocada")
    _rate_limit(k["id"])
    with conn() as c:
        c.execute("UPDATE api_keys SET ultimo_uso=now(), llamadas=llamadas+1 WHERE id=%s", (k["id"],))
    return k


def registra_acceso(request: Request, key: dict, status: int, filas: int | None = None) -> None:
    """Auditoría por llamada. Nunca revienta la respuesta si el log falla."""
    try:
        with conn() as c:
            c.execute(
                """INSERT INTO api_access_log (key_id, ip, metodo, path, query, status, filas)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (key.get("id"), request.client.host if request.client else None,
                 request.method, request.url.path, str(request.url.query)[:500], status, filas))
    except Exception:  # noqa: BLE001 — la auditoría nunca debe tumbar la API
        pass
