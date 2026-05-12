"""FastAPI app — sirve dashboard estático + endpoints /api/operacion/*."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from etl_v2.api.routes import (
    alertas,
    grupo,
    heatmap,
    historico,
    kpis,
    periodo,
    ranking,
    sucursal,
)
from etl_v2.shared.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("api")

app = FastAPI(title="Operación Diaria EPL CAS", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

API_PREFIX = "/api/operacion"
app.include_router(periodo.router, prefix=API_PREFIX, tags=["periodo"])
app.include_router(kpis.router, prefix=API_PREFIX, tags=["kpis"])
app.include_router(ranking.router, prefix=API_PREFIX, tags=["ranking"])
app.include_router(grupo.router, prefix=API_PREFIX, tags=["grupo"])
app.include_router(sucursal.router, prefix=API_PREFIX, tags=["sucursal"])
app.include_router(heatmap.router, prefix=API_PREFIX, tags=["heatmap"])
app.include_router(historico.router, prefix=API_PREFIX, tags=["historico"])
app.include_router(alertas.router, prefix=API_PREFIX, tags=["alertas"])

WEB_DIR = Path(__file__).parent.parent / "web"
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "operacion-diaria"})


@app.get("/")
def root() -> FileResponse:
    return FileResponse(str(WEB_DIR / "index.html"))
