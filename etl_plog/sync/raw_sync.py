"""Sync raw: extrae TODAS las submissions de los form templates del catálogo.

Se extrae TODO (aunque el form esté desactivado en config) — el admin panel
gobierna qué se MUESTRA, no qué se guarda. Filtra a las 18 sucursales PLOG
client-side (varios forms son compartidos con CAS).

Incremental: desde sync_state.last_ts_seen - solape de 3 días (por submissions
tardías). Backfill: --desde 2025-01-01.

Correr:  .venv-plog/bin/python -m etl_plog.sync.raw_sync [--desde YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from etl_plog.shared import catalogo
from etl_plog.shared.config import settings
from etl_plog.shared.db import conn
from etl_plog.shared.zenput_client import ZenputClient

log = logging.getLogger(__name__)
TZ_MTY = ZoneInfo("America/Monterrey")
SOLAPE = timedelta(days=3)

# Comisariatos no tienen location en Zenput: el Recorrido Diario llega con
# location=None y se atribuye por la persona que lo llena a la sucursal
# VIRTUAL de su zona (ids negativos, ver seed). Editable a futuro en admin.
FAMILIAS_SIN_LOCATION = {"recorrido_comisariato"}
RESPONSABLE_A_COMISARIATO = {
    "Galilea Gallegos": -1,  # Comisariato Nuevo León (Excel: resp. comisariato NL)
}
COMISARIATO_ZONA = {-1: "nuevo_leon", -2: "laguna", -3: "queretaro"}


def _ts(v: int | float | str | None) -> datetime | None:
    """Fechas Zenput: epoch ms (int) o ISO-8601 (str), según endpoint."""
    if not v:
        return None
    if isinstance(v, str):
        if v.isdigit():
            v = int(v)
        else:
            dt = datetime.fromisoformat(v)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(v / 1000, tz=timezone.utc)


def sync_form(client: ZenputClient, ft: int, desde: datetime,
              plog_locs: dict[int, str], fam: str,
              corte: datetime | None = None) -> tuple[int, int]:
    """-> (ingeridas_plog, vistas_total).

    corte: si se da, corta la paginación al topar submissions más viejas que `corte`.
    El API devuelve NEWEST-first → una vez que vemos ts < corte, el resto es aún más
    viejo (ya lo tenemos) → paramos. Optimiza el sync incremental (no re-escanea 45k).
    """
    vistas = ingeridas = 0
    max_ts: datetime | None = None
    viejas_seguidas = 0
    batch: list[tuple] = []
    for s in client.submissions(ft, start=desde):
        vistas += 1
        meta = s.get("smetadata") or {}
        ts = _ts(meta.get("date_created") or meta.get("date_submitted"))
        if ts and (max_ts is None or ts > max_ts):
            max_ts = ts
        if corte and ts and ts < corte:
            viejas_seguidas += 1
            if viejas_seguidas >= 20:  # buffer anti-jitter de orden; luego todo es viejo
                break
            continue
        viejas_seguidas = 0
        loc = (meta.get("location") or {}).get("id")
        creador = (meta.get("created_by") or {}).get("display_name")
        if loc is None and fam in FAMILIAS_SIN_LOCATION:
            loc = RESPONSABLE_A_COMISARIATO.get(creador)
            if loc is None:
                log.warning("submission %s de %s sin location y sin mapeo de responsable (%s)",
                            s["id"], fam, creador)
                continue
            zona = COMISARIATO_ZONA[loc]
        elif loc in plog_locs:
            zona = plog_locs[loc]
        else:
            continue  # submission de sucursal CAS en form compartido
        fecha_local = ts.astimezone(TZ_MTY).date() if ts else None
        batch.append((s["id"], ft, fam, loc, zona, fecha_local,
                      _ts(meta.get("date_completed")) or ts,
                      (meta.get("created_by") or {}).get("display_name"), Jsonb(s)))
        ingeridas += 1
    if batch or max_ts:
        with conn() as c:
            cur = c.cursor()
            if batch:
                cur.executemany(
                    """INSERT INTO raw_submissions
                         (submission_id, form_template_id, familia, location_id, zona,
                          fecha_local, ts_completed, created_by, payload)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (submission_id) DO NOTHING""",
                    batch,
                )
            cur.execute(
                """INSERT INTO sync_state (form_template_id, last_synced_at, last_ts_seen, total_ingeridas)
                   VALUES (%s, now(), %s, %s)
                   ON CONFLICT (form_template_id) DO UPDATE
                     SET last_synced_at = now(),
                         last_ts_seen   = GREATEST(COALESCE(sync_state.last_ts_seen, EXCLUDED.last_ts_seen), EXCLUDED.last_ts_seen),
                         total_ingeridas = sync_state.total_ingeridas + EXCLUDED.total_ingeridas""",
                (ft, max_ts, ingeridas),
            )
    return ingeridas, vistas


def run(desde_arg: str | None = None) -> dict[str, int]:
    with conn() as c:
        plog_locs = {r["location_id"]: r["zona"]
                     for r in c.execute("SELECT location_id, zona FROM sucursales WHERE activo")}
        estado = {r["form_template_id"]: r["last_ts_seen"]
                  for r in c.execute("SELECT form_template_id, last_ts_seen FROM sync_state")}
    if not plog_locs:
        raise SystemExit("sucursales vacía — corre primero etl_plog.scripts.seed")

    fam_de = catalogo.ft_a_familia()
    client = ZenputClient()
    tot_ing = tot_vis = 0
    try:
        for ft in catalogo.todos_los_fts():
            corte = None
            if desde_arg:
                desde = datetime.fromisoformat(desde_arg).replace(tzinfo=timezone.utc)
            elif estado.get(ft):
                desde = estado[ft] - SOLAPE
                corte = desde  # incremental: cortar paginación al topar lo ya conocido
            else:
                desde = datetime.now(timezone.utc) - timedelta(days=90)
            ing, vis = sync_form(client, ft, desde, plog_locs, fam_de[ft], corte)
            tot_ing += ing
            tot_vis += vis
            log.info("ft %s (%s): %s PLOG / %s vistas desde %s",
                     ft, fam_de[ft], ing, vis, desde.date())
    finally:
        client.close()
    return {"ingeridas": tot_ing, "vistas": tot_vis}


if __name__ == "__main__":
    logging.basicConfig(level=settings.LOG_LEVEL)
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", help="YYYY-MM-DD (backfill); default incremental")
    args = ap.parse_args()
    res = run(args.desde)
    print(f"sync OK: {res['ingeridas']} submissions PLOG ingeridas ({res['vistas']} vistas)")
