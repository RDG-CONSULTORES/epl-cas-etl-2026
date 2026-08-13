"""Cron de reportes: envía las programaciones activas de report_schedules cuyo
día toca hoy. Respeta el scope de cada programación. Idempotente por corrida.

Railway cron sugerido: lunes 07:00 semanal, día 1 mensual, etc. Este job filtra
por cadencia+fecha para no duplicar.

Correr:  PLOG_DATABASE_URL=... RESEND_API_KEY=... .venv-plog/bin/python -m etl_plog.reportes.cron
"""
from __future__ import annotations

import logging
from datetime import date

from etl_plog.reportes import envio, generador, render
from etl_plog.shared.db import conn

log = logging.getLogger(__name__)


def _toca_hoy(cadencia: str, hoy: date) -> bool:
    """¿Hoy toca enviar esta cadencia? (semanal=lunes, mensual=día 1, etc.)"""
    if cadencia == "semanal":
        return hoy.weekday() == 0
    if cadencia == "quincenal":
        return hoy.day in (1, 16)
    return hoy.day == 1  # mensual y periodos mayores: primer día del periodo


def run(hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    enviados = 0
    with conn() as c:
        progs = c.execute("""SELECT id, nombre, cadencia, canal, destinatarios, zona
                             FROM report_schedules WHERE activo""").fetchall()
    for p in progs:
        if not _toca_hoy(p["cadencia"], hoy):
            continue
        scopes = [{"zona": p["zona"], "location_ids": None}] if p["zona"] else [{"zona": None, "location_ids": None}]
        d = generador.datos(p["cadencia"], hoy, scopes)
        html = render.html(d)
        asunto = f"Cumplimiento PLOG · {d['periodo']['label']}"
        res = envio.envia_correo(list(p["destinatarios"] or []), asunto, html)
        envio.registra_envio(p["cadencia"], list(p["destinatarios"] or []), asunto, res)
        if res.get("enviado"):
            enviados += 1
        log.info("reporte %s (%s): %s", p["nombre"], p["cadencia"], res)
    return {"programaciones": len(progs), "enviados": enviados}


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    print(run())
