"""API FastAPI del dashboard de Cumplimiento PLOG.

Lee SOLO de la BD (schema plog), con scoping por usuario en cada query.
Auth por cookie de sesión HttpOnly. El PWA y las apps nativas consumen estos
mismos endpoints (API-first).

Correr:  PLOG_DATABASE_URL=... .venv-plog/bin/uvicorn etl_plog.api.main:app --port 8000
"""
from __future__ import annotations

from datetime import date, timedelta

import asyncio
import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from etl_plog.api import admin, auth, scoping
from etl_plog.shared.db import conn

log = logging.getLogger("plog")
app = FastAPI(title="Cumplimiento PLOG", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(admin.router)
COOKIE = "plog_sesion"
_WEB = Path(__file__).resolve().parents[1] / "web"

# Scheduler interno de refresco (1 réplica). Cada REFRESH_HORAS corre sync incremental
# + recompute reciente + calificaciones. Desactivable con REFRESH_HORAS=0.
REFRESH_HORAS = float(os.environ.get("REFRESH_HORAS", "3"))


@app.on_event("startup")
async def _arranca_scheduler():
    if REFRESH_HORAS <= 0:
        return

    def _refresh():
        from etl_plog.scripts.refresh import run
        return run()

    async def loop():
        while True:
            await asyncio.sleep(REFRESH_HORAS * 3600)
            try:
                res = await asyncio.get_event_loop().run_in_executor(None, _refresh)
                log.info("refresh automático OK: %s", res)
            except Exception as e:  # noqa: BLE001
                log.error("refresh automático falló: %s", e)

    asyncio.create_task(loop())
    log.info("scheduler de refresco cada %sh activo", REFRESH_HORAS)


@app.get("/admin")
def admin_page():
    return FileResponse(_WEB / "admin.html")


# ── Auth dependency ──────────────────────────────────────────────────────
def sesion(request: Request) -> dict:
    u = auth.usuario_de_sesion(request.cookies.get(COOKIE))
    if not u:
        raise HTTPException(401, "No autenticado")
    return u


def solo_admin(u: dict = Depends(sesion)) -> dict:
    if u["rol"] != "admin":
        raise HTTPException(403, "Requiere rol admin")
    return u


@app.post("/api/login")
def post_login(payload: dict, request: Request, response: Response):
    token = auth.login(str(payload.get("usuario", "")), str(payload.get("password", "")),
                       request.headers.get("user-agent", ""))
    if not token:
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax",
                        secure=False, max_age=auth.SESION_DIAS * 86400)
    return {"ok": True}


@app.post("/api/logout")
def post_logout(request: Request, response: Response):
    tok = request.cookies.get(COOKIE)
    if tok:
        auth.logout(tok)
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/me")
def get_me(u: dict = Depends(sesion)):
    return {"usuario": u["usuario"], "nombre": u["nombre"], "rol": u["rol"],
            "zonas": sorted(scoping.zonas_visibles(u["scopes"]) or ["todas"])}


# ── Freshness / corte de datos ───────────────────────────────────────────
@app.get("/api/freshness")
def get_freshness(u: dict = Depends(sesion)):
    with conn() as c:
        r = c.execute("SELECT max(last_synced_at) ult FROM sync_state").fetchone()
    return {"corte": r["ult"].isoformat() if r["ult"] else None}


# ── Resumen (V1 header + KPI por zona) ───────────────────────────────────
@app.get("/api/resumen")
def get_resumen(u: dict = Depends(sesion), desde: str | None = None, hasta: str | None = None):
    w, params = scoping.clausula_scope(u["scopes"], "c")
    d = desde or (date.today() - timedelta(days=7)).isoformat()
    h = hasta or date.today().isoformat()
    with conn() as c:
        glob = c.execute(f"""
            SELECT count(*) FILTER (WHERE estado IN ('on_time','late')) cumpl,
                   count(*) FILTER (WHERE estado <> 'pending') base,
                   count(*) FILTER (WHERE estado='on_time') ot,
                   count(*) FILTER (WHERE estado='late') lt,
                   count(*) FILTER (WHERE estado='missed') ms,
                   count(*) FILTER (WHERE estado='pending') pd
            FROM cumplimiento c
            WHERE {w} AND periodo_inicio BETWEEN %s AND %s""",
            params + [d, h]).fetchone()
        zonas = c.execute(f"""
            SELECT zona, round(100.0*count(*) FILTER (WHERE estado IN ('on_time','late'))
                   /NULLIF(count(*) FILTER (WHERE estado<>'pending'),0),1) pct
            FROM cumplimiento c
            WHERE {w} AND periodo_inicio BETWEEN %s AND %s
            GROUP BY zona ORDER BY pct DESC NULLS LAST""",
            params + [d, h]).fetchall()
    pct = round(100.0 * glob["cumpl"] / glob["base"], 1) if glob["base"] else None
    return {"desde": d, "hasta": h, "pct": pct, **{k: glob[k] for k in ("ot", "lt", "ms", "pd")},
            "zonas": zonas}


# ── Sucursales (V1 lista + V2 base) ──────────────────────────────────────
@app.get("/api/sucursales")
def get_sucursales(u: dict = Depends(sesion), desde: str | None = None, hasta: str | None = None):
    w, params = scoping.clausula_scope(u["scopes"], "c")
    d = desde or (date.today() - timedelta(days=7)).isoformat()
    h = hasta or date.today().isoformat()
    with conn() as c:
        rows = c.execute(f"""
            SELECT s.location_id, s.nombre, s.zona, s.es_comisariato,
                   round(100.0*count(*) FILTER (WHERE c.estado IN ('on_time','late'))
                         /NULLIF(count(*) FILTER (WHERE c.estado<>'pending'),0),1) pct
            FROM cumplimiento c JOIN sucursales s USING(location_id)
            WHERE {w} AND c.periodo_inicio BETWEEN %s AND %s
            GROUP BY s.location_id, s.nombre, s.zona, s.es_comisariato
            ORDER BY pct ASC NULLS LAST""", params + [d, h]).fetchall()
    return {"sucursales": rows}


# ── Detalle sucursal (V3 scorecard: formularios activos con su %) ─────────
@app.get("/api/sucursal/{location_id}")
def get_sucursal(location_id: int, u: dict = Depends(sesion),
                 desde: str | None = None, hasta: str | None = None):
    w, params = scoping.clausula_scope(u["scopes"], "c")
    d = desde or (date.today() - timedelta(days=7)).isoformat()
    h = hasta or date.today().isoformat()
    with conn() as c:
        info = c.execute(f"""SELECT nombre, zona, director, es_comisariato
                             FROM sucursales WHERE location_id=%s""", (location_id,)).fetchone()
        if not info:
            raise HTTPException(404, "Sucursal no encontrada")
        forms = c.execute(f"""
            SELECT familia, round(100.0*count(*) FILTER (WHERE estado IN ('on_time','late'))
                   /NULLIF(count(*) FILTER (WHERE estado<>'pending'),0),1) pct,
                   count(*) FILTER (WHERE estado='missed') faltas
            FROM cumplimiento c
            WHERE {w} AND location_id=%s AND periodo_inicio BETWEEN %s AND %s
            GROUP BY familia ORDER BY pct ASC NULLS LAST""",
            params + [location_id, d, h]).fetchall()
    return {"location_id": location_id, **info, "formularios": forms}


# ── Detalle formulario×sucursal (V4: calendario + áreas) ─────────────────
@app.get("/api/formulario/{familia}/sucursal/{location_id}")
def get_form_detalle(familia: str, location_id: int, u: dict = Depends(sesion),
                     desde: str | None = None, hasta: str | None = None):
    w, params = scoping.clausula_scope(u["scopes"], "c")
    d = desde or (date.today() - timedelta(days=30)).isoformat()
    h = hasta or date.today().isoformat()
    with conn() as c:
        dias = c.execute(f"""
            SELECT periodo_inicio dia, estado, serie_contestada, ts_submission
            FROM cumplimiento c
            WHERE {w} AND familia=%s AND location_id=%s AND periodo_inicio BETWEEN %s AND %s
            ORDER BY periodo_inicio""", params + [familia, location_id, d, h]).fetchall()
        # última calificación con áreas (drill-down) si el form califica
        calif = c.execute(f"""
            SELECT fecha_local, score_total, areas
            FROM calificaciones
            WHERE familia=%s AND location_id=%s AND fecha_local BETWEEN %s AND %s
            ORDER BY fecha_local DESC LIMIT 1""",
            [familia, location_id, d, h]).fetchone()
    return {"familia": familia, "location_id": location_id, "dias": dias,
            "calificacion": calif}


@app.get("/api/formulario/{familia}/sucursal/{location_id}/fotos")
def get_fotos(familia: str, location_id: int, u: dict = Depends(sesion)):
    from etl_plog.api import fotos
    w, params = scoping.clausula_scope(u["scopes"])  # valida acceso a la sucursal
    with conn() as c:
        ok = c.execute(f"SELECT 1 FROM sucursales WHERE location_id=%s AND {w}",
                       [location_id] + params).fetchone()
        if not ok:
            raise HTTPException(403, "Sin acceso a esta sucursal")
        r = c.execute("""SELECT payload FROM raw_submissions
                         WHERE familia=%s AND location_id=%s
                         ORDER BY fecha_local DESC, ts_completed DESC LIMIT 1""",
                      (familia, location_id)).fetchone()
    if not r:
        return {"fotos": []}
    return {"fotos": fotos.fotos_de_payload(r["payload"])}


@app.get("/api/health")
def health():
    with conn() as c:
        c.execute("SELECT 1")
    return {"ok": True}


# ── PWA (mismo origen para que la cookie de sesión aplique) ──────────────
@app.get("/")
def root():
    return FileResponse(_WEB / "index.html")


@app.get("/manifest.json")
def manifest():
    return FileResponse(_WEB / "manifest.json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(_WEB / "sw.js", media_type="application/javascript")


app.mount("/static", StaticFiles(directory=_WEB), name="static")
