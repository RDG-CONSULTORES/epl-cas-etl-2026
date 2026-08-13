"""Extractor de calificaciones: de raw_submissions → tabla plog.calificaciones.

Por cada submission de un formulario con score, extrae el score TOTAL y el % por
ÁREA usando drilldown_spec.json (mapeo campo→area por form_template). Estandariza:
- 100% ABSOLUTO: score_total se recorta a min(100, raw); el bonus se guarda en raw.
- Áreas: % directo del campo formula (ya viene calculado por Zenput).
- Solo PLOG (raw_submissions ya está filtrado a las 18 sucursales).

Correr:  PLOG_DATABASE_URL=... .venv-plog/bin/python -m etl_plog.calificaciones.extractor [--desde YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from psycopg.types.json import Jsonb

from etl_plog.shared.db import conn

log = logging.getLogger(__name__)
_SPEC = Path(__file__).resolve().parents[1] / "config" / "drilldown_spec.json"


def _num(v):
    """Parsea el valor de una formula a float (tolera '96.23', 96, None, '')."""
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _clean(t: str) -> str:
    return re.sub(r"</?b>", "", t or "").strip()


def cargar_spec() -> dict[int, dict]:
    raw = json.loads(_SPEC.read_text())
    return {int(ft): e for ft, e in raw.items()}


def _extraer_p3(formulas: dict) -> tuple[float | None, float | None, list]:
    """Mantenimientos: el total 'Calificación General' viene 0/None; se calcula
    del promedio de las áreas 'AREA <X>' (secciones), que sí traen valor."""
    areas = []
    for titulo, val in formulas.items():
        if titulo.upper().startswith("AREA "):
            pct = _num(val)
            if pct is not None:
                areas.append({"area": titulo[5:].strip(), "pct": min(pct, 100.0),
                              "puntos": None, "puntos_max": None})
    if not areas:
        return None, None, []
    prom = sum(a["pct"] for a in areas) / len(areas)
    return min(prom, 100.0), prom, areas


def extraer_submission(payload: dict, spec_ft: dict, patron: str | None = None) -> tuple[float | None, float | None, list]:
    """-> (score_estandar<=100, score_raw, areas[])"""
    # índice título->valor de las formulas de esta submission
    formulas = {_clean(a.get("title")): a.get("value")
                for a in payload.get("answers", []) if a.get("field_type") == "formula"}

    if patron == "p3":
        p3 = _extraer_p3(formulas)
        if p3[0] is not None:          # trae áreas "AREA X" -> úsalo
            return p3
        # sin "AREA X" (mtto trimestral/semestral con estructura distinta) -> método normal

    raw = _num(formulas.get(_clean(spec_ft.get("score_total") or "")))
    score_std = min(raw, 100.0) if raw is not None else None

    areas = []
    for a in spec_ft.get("areas", []):
        pct = _num(formulas.get(_clean(a["campo_pct"])))
        pts = _num(formulas.get(_clean(a["campo_puntos"]))) if a.get("campo_puntos") else None
        pts_max = None
        if a.get("campo_puntos"):
            m = re.search(r"\((\d+)\s*Puntos", a["campo_puntos"])
            if m:
                pts_max = float(m.group(1))
        if pct is not None or pts is not None:
            areas.append({"area": a["area"], "pct": pct if pct is None else min(pct, 100.0),
                          "puntos": pts, "puntos_max": pts_max})
    return score_std, raw, areas


def run(desde: str | None = None) -> dict[str, int]:
    spec = cargar_spec()
    where = "WHERE r.familia IS NOT NULL"
    args: list = []
    if desde:
        where += " AND r.fecha_local >= %s"
        args.append(desde)

    from etl_plog.shared import catalogo
    patron_de = {f: e.get("score_patron") for f, e in catalogo.familias().items()}

    with conn() as c:
        # solo familias con medición calificación/ambos y activas
        scored_fams = {r["familia"] for r in c.execute(
            "SELECT DISTINCT familia FROM config_formularios WHERE medicion IN ('calificacion','ambos')")}
        rows = list(c.execute(
            f"""SELECT r.submission_id, r.form_template_id, r.familia, r.zona,
                       r.location_id, r.fecha_local, r.payload
                FROM raw_submissions r {where}""", args))

    filas = []
    sin_total = 0
    for r in rows:
        if r["familia"] not in scored_fams:
            continue
        spec_ft = spec.get(r["form_template_id"]) or {}
        patron = patron_de.get(r["familia"])
        if not spec_ft and patron != "p3":
            continue
        score_std, score_raw, areas = extraer_submission(r["payload"], spec_ft, patron)
        if score_std is None and not areas:
            sin_total += 1
            continue
        filas.append((r["submission_id"], r["familia"], r["zona"], r["location_id"],
                      r["fecha_local"], score_std, score_raw, Jsonb(areas)))

    with conn() as c:
        cur = c.cursor()
        cur.executemany(
            """INSERT INTO calificaciones
                 (submission_id, familia, zona, location_id, fecha_local,
                  score_total, score_raw, areas)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (submission_id) DO UPDATE
                 SET score_total=EXCLUDED.score_total, score_raw=EXCLUDED.score_raw,
                     areas=EXCLUDED.areas, computed_at=now()""",
            filas)
    return {"extraidas": len(filas), "sin_score": sin_total}


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde")
    a = ap.parse_args()
    res = run(a.desde)
    print(f"calificaciones extraídas: {res['extraidas']} · sin score legible: {res['sin_score']}")
