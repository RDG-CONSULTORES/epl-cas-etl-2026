"""Orquestador de refresco: sync incremental + recomputar cumplimiento reciente +
extraer calificaciones. Para el cron de Railway (horario/diario).

El freeze protege el histórico; solo se recalculan las ventanas recientes no
congeladas (últimos ~45 días). El sync incremental corta al topar lo ya conocido.

Correr:  PLOG_DATABASE_URL=... ZENPUT_TOKEN=... python -m etl_plog.scripts.refresh
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from etl_plog.calificaciones import extractor
from etl_plog.cumplimiento import motor
from etl_plog.sync import raw_sync

log = logging.getLogger(__name__)


def run() -> dict:
    sync = raw_sync.run()                       # incremental (corta al topar conocido)
    desde = (date.today() - timedelta(days=45)).isoformat()
    cumpl = motor.run(date.fromisoformat(desde))   # recompute reciente (freeze protege lo viejo)
    calif = extractor.run(desde)
    res = {"sync": sync, "cumplimiento": cumpl, "calificaciones": calif}
    log.info("refresh OK: %s", res)
    return res


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    import json
    print(json.dumps(run(), default=str))
