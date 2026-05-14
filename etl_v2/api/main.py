"""FastAPI app — sirve dashboard estático + endpoints /api/operacion/*."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
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


FAVICON_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    b'<rect width="100" height="100" rx="20" fill="#0a84ff"/>'
    b'<text x="50" y="62" font-size="52" text-anchor="middle" fill="white" '
    b'font-family="-apple-system">\xe2\x9c\x93</text></svg>'
)


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "operacion-diaria"})


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(content=FAVICON_SVG, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/")
def root() -> FileResponse:
    return FileResponse(str(WEB_DIR / "index.html"))
