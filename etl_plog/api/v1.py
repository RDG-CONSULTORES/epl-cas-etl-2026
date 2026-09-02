"""API pública v1 — SOLO LECTURA — para consumidores externos (sistemas EPL).

Superficie estable y versionada sobre los datos de cumplimiento PLOG. NO expone el
esquema interno ni el motor: devuelve un contrato limpio y documentado. Autenticada
por API key (cabecera `X-API-Key`), acotable por zona, auditada y con rate-limit.

Contrato de respuesta:
  - listas paginadas -> {"data": [...], "paging": {limit, offset, count, has_more}}
  - objetos simples  -> el objeto directo
Fechas en zona horaria de Monterrey (America/Monterrey), formato ISO (YYYY-MM-DD).
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from etl_plog.api import apikeys
from etl_plog.shared.db import conn

router = APIRouter(prefix="/api/v1", tags=["v1 (externo, solo lectura)"])

LIMIT_DEF = 100
LIMIT_MAX = 1000


# Enums: un valor fuera del set devuelve 422 (evita el "200 vacío" que engaña al consumidor).
class Zona(str, Enum):
    nuevo_leon = "nuevo_leon"
    laguna = "laguna"
    queretaro = "queretaro"


class Estado(str, Enum):
    on_time = "on_time"
    late = "late"
    missed = "missed"
    pending = "pending"


# Familia es válida si el SISTEMA la conoce en cualquier tabla (raw/cumplimiento/config).
# Así un typo da 422, pero una familia real que un endpoint no puntúa/cubre devuelve vacío
# (no 422). Incluye familias sintéticas de cumplimiento (ej 'alistamiento_diario'). Cacheado.
_FAM_TTL = 300.0
_fam_cache: dict = {"set": frozenset(), "ts": 0.0}


def _familias_conocidas(forzar: bool = False) -> frozenset:
    ahora = time.monotonic()
    if forzar or not _fam_cache["set"] or ahora - _fam_cache["ts"] > _FAM_TTL:
        with conn() as c:
            rows = c.execute(
                "SELECT familia FROM raw_submissions WHERE familia IS NOT NULL "
                "UNION SELECT familia FROM cumplimiento "
                "UNION SELECT familia FROM config_formularios").fetchall()
        _fam_cache["set"] = frozenset(r["familia"] for r in rows if r["familia"])
        _fam_cache["ts"] = ahora
    return _fam_cache["set"]


def _valida_familia(familia: str | None) -> None:
    """422 solo si la familia no la conoce ninguna tabla del sistema (típicamente un typo)."""
    if familia is None or familia in _familias_conocidas():
        return
    # podría ser una familia recién ingerida → refrescar una vez antes de rechazar
    if familia not in _familias_conocidas(forzar=True):
        raise HTTPException(422, f"familia desconocida: '{familia}'")


def _paging(limit: int, offset: int, filas: list) -> dict:
    return {"limit": limit, "offset": offset, "count": len(filas),
            "has_more": len(filas) == limit}


def _zona_filtro(key: dict, params: list) -> str:
    """Si la llave está acotada por zonas, agrega el filtro y el parámetro."""
    if key.get("zonas"):
        params.append(key["zonas"])
        return " AND zona = ANY(%s)"
    return ""


# ── Sanidad / frescura ─────────────────────────────────────────────────────
@router.get("/ping", summary="Verifica la llave y la frescura de los datos")
def ping(request: Request, key: dict = Depends(apikeys.require_api_key)):
    with conn() as c:
        f = c.execute(
            "SELECT max(last_synced_at) AS ult FROM sync_state").fetchone()
    apikeys.registra_acceso(request, key, 200)
    return {"ok": True, "llave": key["etiqueta"], "zonas": key.get("zonas"),
            "datos_actualizados_at": f["ult"]}


@router.get("/freshness", summary="Último corte de sincronización con la fuente (Zenput)")
def freshness(request: Request, key: dict = Depends(apikeys.require_api_key)):
    with conn() as c:
        f = c.execute("""SELECT max(last_synced_at) AS ult_sync,
                                max(last_ts_seen)   AS ult_submission,
                                sum(total_ingeridas) AS total
                         FROM sync_state""").fetchone()
    apikeys.registra_acceso(request, key, 200)
    return {"ultimo_sync_at": f["ult_sync"], "ultima_submission_at": f["ult_submission"],
            "total_submissions": f["total"]}


# ── Catálogo de formularios ────────────────────────────────────────────────
@router.get("/catalogo/formularios", summary="Catálogo de formularios monitoreados")
def catalogo_formularios(
    request: Request,
    solo_activos: bool = Query(True),
    key: dict = Depends(apikeys.require_api_key),
):
    params: list = []
    where = "WHERE activo" if solo_activos else "WHERE TRUE"
    where += _zona_filtro(key, params)
    with conn() as c:
        rows = c.execute(f"""
            SELECT familia, zona, nombre, medicion, frecuencia,
                   to_char(hora_limite,'HH24:MI') AS hora_limite,
                   dias_gracia, activo
            FROM config_formularios {where}
            ORDER BY nombre, zona""", params).fetchall()
    apikeys.registra_acceso(request, key, 200, len(rows))
    return {"data": rows, "paging": None}


# ── Sucursales ─────────────────────────────────────────────────────────────
@router.get("/sucursales", summary="Catálogo de sucursales")
def sucursales(
    request: Request,
    solo_activas: bool = Query(True),
    key: dict = Depends(apikeys.require_api_key),
):
    params: list = []
    where = "WHERE activo" if solo_activas else "WHERE TRUE"
    where += _zona_filtro(key, params)
    with conn() as c:
        rows = c.execute(f"""
            SELECT location_id, nombre, zona, director, team_id,
                   es_comisariato, lat, lon, activo
            FROM sucursales {where}
            ORDER BY zona, nombre""", params).fetchall()
    apikeys.registra_acceso(request, key, 200, len(rows))
    return {"data": rows, "paging": None}


# ── Cumplimiento (núcleo) ──────────────────────────────────────────────────
@router.get("/cumplimiento", summary="Estados de cumplimiento por sucursal y periodo")
def cumplimiento(
    request: Request,
    desde: date | None = Query(None, description="Inicio (por defecto: hace 30 días)"),
    hasta: date | None = Query(None, description="Fin (por defecto: hoy)"),
    zona: Zona | None = Query(None),
    familia: str | None = Query(None),
    location_id: int | None = Query(None),
    estado: Estado | None = Query(None, description="on_time | late | missed | pending"),
    limit: int = Query(LIMIT_DEF, ge=1, le=LIMIT_MAX),
    offset: int = Query(0, ge=0),
    key: dict = Depends(apikeys.require_api_key),
):
    _valida_familia(familia)
    hasta = hasta or date.today()
    desde = desde or (hasta - timedelta(days=30))
    where = ["periodo_inicio >= %s", "periodo_inicio <= %s"]
    params: list = [desde, hasta]
    if zona:
        where.append("zona = %s"); params.append(zona.value)
    if familia:
        where.append("familia = %s"); params.append(familia)
    if location_id:
        where.append("location_id = %s"); params.append(location_id)
    if estado:
        where.append("estado = %s"); params.append(estado.value)
    if key.get("zonas"):
        where.append("zona = ANY(%s)"); params.append(key["zonas"])
    # Orden con desempate ÚNICO (PK = familia,location_id,periodo_inicio) → paginación sin
    # duplicados ni omisiones. periodo_inicio DESC solo NO era total-order (empataba).
    sql = f"""
        SELECT familia, zona, location_id, periodo_inicio, periodo_fin,
               estado, submission_id, ts_submission
        FROM cumplimiento
        WHERE {' AND '.join(where)}
        ORDER BY periodo_inicio DESC, zona, location_id, familia
        LIMIT %s OFFSET %s"""
    params += [limit, offset]
    with conn() as c:
        rows = c.execute(sql, params).fetchall()
    apikeys.registra_acceso(request, key, 200, len(rows))
    return {"data": rows, "paging": _paging(limit, offset, rows)}


# ── Calificaciones ─────────────────────────────────────────────────────────
@router.get("/calificaciones", summary="Calificaciones (score por submission y área)")
def calificaciones(
    request: Request,
    desde: date | None = Query(None),
    hasta: date | None = Query(None),
    zona: Zona | None = Query(None),
    familia: str | None = Query(None),
    location_id: int | None = Query(None),
    limit: int = Query(LIMIT_DEF, ge=1, le=LIMIT_MAX),
    offset: int = Query(0, ge=0),
    key: dict = Depends(apikeys.require_api_key),
):
    _valida_familia(familia)
    hasta = hasta or date.today()
    desde = desde or (hasta - timedelta(days=30))
    where = ["fecha_local >= %s", "fecha_local <= %s"]
    params: list = [desde, hasta]
    if zona:
        where.append("zona = %s"); params.append(zona.value)
    if familia:
        where.append("familia = %s"); params.append(familia)
    if location_id:
        where.append("location_id = %s"); params.append(location_id)
    if key.get("zonas"):
        where.append("zona = ANY(%s)"); params.append(key["zonas"])
    # Desempate único por submission_id (PK) → paginación estable.
    sql = f"""
        SELECT submission_id, familia, zona, location_id, fecha_local,
               score_total, areas
        FROM calificaciones
        WHERE {' AND '.join(where)}
        ORDER BY fecha_local DESC, zona, location_id, submission_id
        LIMIT %s OFFSET %s"""
    params += [limit, offset]
    with conn() as c:
        rows = c.execute(sql, params).fetchall()
    apikeys.registra_acceso(request, key, 200, len(rows))
    return {"data": rows, "paging": _paging(limit, offset, rows)}


# ── Submissions (metadatos; respuestas opcionales) ─────────────────────────
@router.get("/submissions", summary="Submissions de Zenput (metadatos; respuestas opcionales)")
def submissions(
    request: Request,
    desde: date | None = Query(None),
    hasta: date | None = Query(None),
    zona: Zona | None = Query(None),
    familia: str | None = Query(None),
    location_id: int | None = Query(None),
    incluir_respuestas: bool = Query(False, description="Incluye el payload completo (más pesado)"),
    limit: int = Query(LIMIT_DEF, ge=1, le=LIMIT_MAX),
    offset: int = Query(0, ge=0),
    key: dict = Depends(apikeys.require_api_key),
):
    _valida_familia(familia)
    hasta = hasta or date.today()
    desde = desde or (hasta - timedelta(days=30))
    where = ["fecha_local >= %s", "fecha_local <= %s"]
    params: list = [desde, hasta]
    if zona:
        where.append("zona = %s"); params.append(zona.value)
    if familia:
        where.append("familia = %s"); params.append(familia)
    if location_id:
        where.append("location_id = %s"); params.append(location_id)
    if key.get("zonas"):
        where.append("zona = ANY(%s)"); params.append(key["zonas"])
    col_payload = ", payload" if incluir_respuestas else ""
    # Desempate único por submission_id (PK) → paginación estable aunque ts_completed empate.
    sql = f"""
        SELECT submission_id, form_template_id, familia, location_id, zona,
               fecha_local, ts_completed, created_by{col_payload}
        FROM raw_submissions
        WHERE {' AND '.join(where)}
        ORDER BY ts_completed DESC NULLS LAST, submission_id
        LIMIT %s OFFSET %s"""
    params += [limit, offset]
    with conn() as c:
        rows = c.execute(sql, params).fetchall()
    apikeys.registra_acceso(request, key, 200, len(rows))
    return {"data": rows, "paging": _paging(limit, offset, rows)}
