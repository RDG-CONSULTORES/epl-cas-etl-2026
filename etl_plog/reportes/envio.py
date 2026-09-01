"""Envío de reportes y alertas por correo. Capa de notificaciones desacoplada:
hoy = correo; mañana = WhatsApp/push sin tocar el generador.

Dos vías, en orden de preferencia:
  1. SMTP (Google Workspace/Gmail): PLOG_SMTP_USER + PLOG_SMTP_PASSWORD
     (contraseña de APLICACIÓN de Google). Host/puerto por defecto smtp.gmail.com:587.
  2. Resend (respaldo): RESEND_API_KEY.
Si ninguna está configurada, no envía (modo preview). Bitácora en plog.envios.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from etl_plog.shared.db import conn

log = logging.getLogger(__name__)
RESEND_URL = "https://api.resend.com/emails"
FROM = os.environ.get("REPORTE_FROM", "PLOG <reportes@plog.mx>")
APP_URL = os.environ.get("PLOG_APP_URL", "https://plog.example/")

SMTP_HOST = os.environ.get("PLOG_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("PLOG_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("PLOG_SMTP_USER")          # tu correo Gmail/Workspace
SMTP_PASSWORD = os.environ.get("PLOG_SMTP_PASSWORD")  # contraseña de APLICACIÓN de Google


def _api_key() -> str | None:
    return os.environ.get("RESEND_API_KEY")


def _envia_smtp(a: list[str], asunto: str, html: str) -> dict:
    """Envía por Google SMTP (STARTTLS). -> {ok, enviado, id|error}."""
    remitente = FROM if "<" in FROM else f"PLOG <{SMTP_USER}>"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = ", ".join(a)
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(SMTP_USER, a, msg.as_string())
        return {"ok": True, "enviado": True, "id": f"smtp:{SMTP_HOST}"}
    except (smtplib.SMTPException, OSError) as e:
        return {"ok": False, "enviado": False, "error": str(e)[:200]}


def envia_correo(a: list[str], asunto: str, html: str) -> dict:
    """Envía un correo por SMTP (Google) o Resend. -> {ok, id|error, enviado}."""
    html = html.replace("{{APP_URL}}", APP_URL)
    if SMTP_USER and SMTP_PASSWORD:
        return _envia_smtp(a, asunto, html)
    key = _api_key()
    if not key:
        return {"ok": False, "enviado": False,
                "error": "Sin SMTP (PLOG_SMTP_USER/PASSWORD) ni RESEND_API_KEY (modo preview)"}
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
