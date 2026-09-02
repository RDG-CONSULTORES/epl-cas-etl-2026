"""Endpoint de respaldo off-site (llamado por GitHub Actions en cron).

La BD es interna a Railway (no accesible desde fuera). Para respaldar off-site sin
exponer Postgres al internet, este endpoint corre `pg_dump` DENTRO del contenedor
(que sí alcanza la BD) y devuelve el volcado comprimido. Un workflow de GitHub lo
llama, lo CIFRA (AES256) y lo guarda como artifact + Release mensual.

Protección: cabecera `X-Backup-Token` comparada en tiempo constante contra
`PLOG_BACKUP_TOKEN`. Solo lectura (pg_dump). Nunca expone la URL de la BD en argv
(va por env al shell). Si el token no está configurado, el endpoint responde 503.
"""
from __future__ import annotations

import hmac
import os
import subprocess

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from etl_plog.shared.config import settings

router = APIRouter(prefix="/api/admin")

# pg_dump | gzip: la URL de la BD va por env ($DBURL), no en la línea de comando.
_CMD = 'pg_dump --schema=plog --no-owner --no-privileges "$DBURL" | gzip -9'


@router.get("/backup", include_in_schema=False)
def backup(request: Request):
    esperado = os.environ.get("PLOG_BACKUP_TOKEN", "")
    if not esperado:
        raise HTTPException(503, "Respaldo no configurado (falta PLOG_BACKUP_TOKEN)")
    presentado = request.headers.get("X-Backup-Token", "")
    if not hmac.compare_digest(presentado, esperado):
        raise HTTPException(401, "Token de respaldo inválido")

    env = {**os.environ, "DBURL": settings.DATABASE_URL, "PGCONNECT_TIMEOUT": "15"}
    proc = subprocess.Popen(["sh", "-c", _CMD], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env)

    def stream():
        try:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            proc.stdout.close()
            proc.wait()

    return StreamingResponse(
        stream(), media_type="application/gzip",
        headers={"Content-Disposition": 'attachment; filename="plog.sql.gz"'})
