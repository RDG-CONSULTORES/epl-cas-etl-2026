"""Envío de reportes por correo (Resend). Capa de notificaciones desacoplada:
hoy = correo; mañana = WhatsApp/push sin tocar el generador.

Requiere RESEND_API_KEY (env/.env). Si no está, no envía (modo preview).
Bitácora de cada envío en plog.envios.
"""
from __future__ import annotations

import logging
import os

import httpx

from etl_plog.shared.db import conn

log = logging.getLogger(__name__)
RESEND_URL = "https://api.resend.com/emails"
FROM = os.environ.get("REPORTE_FROM", "PLOG <reportes@plog.mx>")
APP_URL = os.environ.get("PLOG_APP_URL", "https://plog.example/")


def _api_key() -> str | None:
    return os.environ.get("RESEND_API_KEY")


def envia_correo(a: list[str], asunto: str, html: str) -> dict:
    """Envía un correo vía Resend. -> {ok, id|error, enviado}."""
    key = _api_key()
    html = html.replace("{{APP_URL}}", APP_URL)
    if not key:
        return {"ok": False, "enviado": False, "error": "RESEND_API_KEY no configurada (modo preview)"}
    try:
        r = httpx.post(RESEND_URL, timeout=30,
                       headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                       json={"from": FROM, "to": a, "subject": asunto, "html": html})
        if r.status_code >= 300:
            return {"ok": False, "enviado": False, "error": f"{r.status_code}: {r.text[:200]}"}
        return {"ok": True, "enviado": True, "id": r.json().get("id")}
    except httpx.HTTPError as e:
        return {"ok": False, "enviado": False, "error": str(e)[:200]}


def registra_envio(cadencia: str, destinatarios: list[str], asunto: str, resultado: dict) -> None:
    with conn() as c:
        c.cursor().execute(
            """INSERT INTO envios (canal, cadencia, destinatarios, asunto, enviado, detalle)
               VALUES ('correo',%s,%s,%s,%s,%s)""",
            (cadencia, destinatarios, asunto, resultado.get("enviado", False),
             resultado.get("id") or resultado.get("error")))
