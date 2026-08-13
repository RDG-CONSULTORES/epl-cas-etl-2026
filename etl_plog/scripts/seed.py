"""Siembra dimensiones y config administrable.

- plog.sucursales: desde el API (teams PLOG -> 18 locations, zona + director).
- plog.config_formularios: desde catalogo.json (Excel v3 + correcciones Roberto).
  El admin panel edita estas filas después; este seed usa ON CONFLICT DO NOTHING
  para NUNCA pisar cambios hechos en el panel.

Correr:  .venv-plog/bin/python -m etl_plog.scripts.seed
"""
from __future__ import annotations

import json
import logging

from psycopg.types.json import Jsonb

from etl_plog.shared import catalogo
from etl_plog.shared.db import conn
from etl_plog.shared.zenput_client import ZenputClient

log = logging.getLogger(__name__)

PLOG_ROOTS = {115099: "nuevo_leon", 115106: "laguna", 115107: "queretaro"}


def _plog_tree(teams: list[dict]) -> tuple[dict[int, str], dict[int, str]]:
    """-> (team_id -> zona, team_id -> nombre_director) del subárbol PLOG."""
    by_parent: dict[int | None, list[dict]] = {}
    for t in teams:
        p = t.get("parent")
        pid = p.get("id") if isinstance(p, dict) else p
        by_parent.setdefault(pid, []).append(t)
    zona_de: dict[int, str] = dict(PLOG_ROOTS)
    director_de: dict[int, str] = {}
    stack = list(PLOG_ROOTS.items())
    while stack:
        tid, zona = stack.pop()
        for child in by_parent.get(tid, []):
            zona_de[child["id"]] = zona
            director_de[child["id"]] = child.get("name", "")
            stack.append((child["id"], zona))
    return zona_de, director_de


def seed_sucursales() -> int:
    client = ZenputClient()
    try:
        zona_de, director_de = _plog_tree(client.teams())
        locs = client.locations()
    finally:
        client.close()
    rows = []
    for l in locs:
        lteams = [t["id"] for t in (l.get("teams") or [])]
        zonas = [zona_de[t] for t in lteams if t in zona_de]
        if not zonas:
            continue
        directores = [director_de[t] for t in lteams if t in director_de]
        rows.append((l["id"], l.get("name", "?"), zonas[0],
                     directores[0] if directores else None,
                     lteams[0] if lteams else None, l.get("external_key"),
                     l.get("latitude"), l.get("longitude")))
    with conn() as c:
        c.cursor().executemany(
            """INSERT INTO sucursales (location_id, nombre, zona, director, team_id,
                                       external_key, lat, lon)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (location_id) DO UPDATE
                 SET nombre=EXCLUDED.nombre, zona=EXCLUDED.zona,
                     director=EXCLUDED.director, updated_at=now()""",
            rows,
        )
    return len(rows)


# Comisariatos: NO existen como location en Zenput (decisión EPL). Se modelan como
# sucursales VIRTUALES (id negativo) por zona; el Recorrido Diario llega con
# location=None y se atribuye por quien lo llena (ver raw_sync). Las evaluaciones
# de comisariato llegan bajo la tienda que lo hospeda -> flag es_comisariato.
COMISARIATOS_VIRTUALES = [
    (-1, "Comisariato Nuevo León", "nuevo_leon"),
    (-2, "Comisariato Laguna", "laguna"),
    (-3, "Comisariato Querétaro", "queretaro"),
]
TIENDAS_CON_COMISARIATO = [2247040, 2247042, 2247048, 2247050]  # Vasconcelos, Revolución, Pueblito, Constituyentes


def seed_comisariatos() -> None:
    with conn() as c:
        cur = c.cursor()
        cur.executemany(
            """INSERT INTO sucursales (location_id, nombre, zona, es_comisariato)
               VALUES (%s,%s,%s,TRUE) ON CONFLICT (location_id) DO NOTHING""",
            COMISARIATOS_VIRTUALES,
        )
        cur.execute(
            "UPDATE sucursales SET es_comisariato=TRUE WHERE location_id = ANY(%s)",
            (TIENDAS_CON_COMISARIATO,),
        )


def seed_config() -> int:
    n = 0
    with conn() as c:
        cur = c.cursor()
        for fam, e in catalogo.familias().items():
            for zona, pol in e["zonas"].items():
                usar = str(pol.get("usar", "")).lower().startswith(("sí", "si"))
                params = {
                    "form_templates": e.get("form_templates"),
                    "form_templates_por_zona": e.get("form_templates_por_zona"),
                    "serie": e.get("serie"),
                    "horario_esperado": pol.get("horario_esperado"),
                    "sucursales_aplica": pol.get("sucursales_aplica"),
                    "calificacion_vista": pol.get("calificacion_vista"),
                    "nota": e.get("nota") or pol.get("nota_override"),
                }
                hora = (pol.get("hora_limite") or "").strip()
                if not hora or not hora[0].isdigit():
                    hora_sql = None
                else:
                    # "01:00 (día sig.)" -> 01:00 con flag dia_siguiente
                    if "sig" in hora:
                        params["dia_siguiente"] = True
                    hora_sql = hora.split()[0]
                gracia = "".join(ch for ch in str(pol.get("dias_gracia", "0")) if ch.isdigit()) or "0"
                cur.execute(
                    """INSERT INTO config_formularios
                         (familia, zona, activo, nombre, medicion, frecuencia,
                          hora_limite, dias_gracia, score_patron, params)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (familia, zona) DO NOTHING""",
                    (fam, zona, usar, e["nombre"], e["tipo"],
                     _norm_frecuencia(pol.get("frecuencia", ""), e),
                     hora_sql, int(gracia), e.get("score_patron"), Jsonb(params)),
                )
                n += cur.rowcount
    return n


def _norm_frecuencia(f: str, entrada: dict) -> str:
    f = f.strip().lower()
    if entrada.get("serie") == "dia_semana":
        return "diario_por_dia"
    if entrada.get("serie") == "semana_del_mes":
        return "semana_del_mes"
    mapa = {"diario": "diario", "semanal": "semanal", "quincenal": "quincenal",
            "mensual": "mensual", "bimestral": "bimestral", "trimestral": "trimestral",
            "semestral": "semestral", "anual": "anual"}
    for k, v in mapa.items():
        if f.startswith(k):
            return v
    return "por_visita"


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    ns = seed_sucursales()
    seed_comisariatos()
    nc = seed_config()
    print(f"sucursales: {ns} (+3 comisariatos virtuales) · config_formularios sembradas: {nc}")
