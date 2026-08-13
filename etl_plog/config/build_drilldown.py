"""Genera drilldown_spec.json — mapa de indicadores por formulario, derivado de
las submissions REALES en plog.raw_submissions (no del Excel).

Por form template: campo de score TOTAL + áreas (nombre, campo %, campo puntos),
en el ORDEN del documento. Alimenta el extractor de calificaciones y las vistas
de drill-down (zona → sucursal → formulario → área).

Correr:  PLOG_DATABASE_URL=... .venv-plog/bin/python -m etl_plog.config.build_drilldown
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from etl_plog.shared.db import conn

HERE = Path(__file__).parent

TOTAL_PATTERNS = [  # en orden de prioridad
    re.compile(r"^CALIFICACION GENERAL PORCENTAJE %$", re.I),
    re.compile(r"^(CALIFICACION )?PORCENTAJE %$", re.I),
    re.compile(r"^Puntuación \(100%\):?$", re.I),
    re.compile(r"^RESULTADO TOTAL", re.I),
    re.compile(r"^Calificación General", re.I),
]
AREA_PCT = [
    re.compile(r"^CALIFICACION (?P<area>.+?) PORCENTAJE %$", re.I),
    re.compile(r"^(?P<area>.+?)\s*(Puntuación)?\s*\(100%\):?$", re.I),
    re.compile(r"^(?P<area>.+?) PORCENTAJE %$", re.I),
    re.compile(r"^SUBTOTAL\s*-\s*(?P<area>.+)$", re.I),
]
PUNTOS = re.compile(r"^(?P<area>.+?)\s*\((?P<max>\d+) Puntos( Posibles)?\):?$", re.I)


def _clean(t: str) -> str:
    return re.sub(r"</?b>", "", t or "").strip()


def _campos_en_orden(payload: dict) -> list[tuple[str, str]]:
    return [(_clean(a.get("title")), a.get("field_type"))
            for a in payload.get("answers", []) if a.get("title")]


def analizar_ft(c, ft: int) -> dict | None:
    # la submission más reciente con más campos contestados define la estructura
    subs = list(c.execute(
        """SELECT payload FROM raw_submissions WHERE form_template_id=%s
           ORDER BY fecha_local DESC LIMIT 20""", (ft,)))
    if not subs:
        return None
    mejor = max(subs, key=lambda s: len(s["payload"].get("answers", [])))
    campos = _campos_en_orden(mejor["payload"])
    formulas = [t for t, ftype in campos if ftype == "formula"]

    total = None
    for pat in TOTAL_PATTERNS:
        total = next((t for t in formulas if pat.match(t)), None)
        if total:
            break
    if total is None:  # fallback: primera formula con "(100%)"
        total = next((t for t in formulas if "(100%)" in t), None)

    areas, vistos = [], set()
    for t in formulas:
        if t == total:
            continue
        nombre = None
        for pat in AREA_PCT:
            m = pat.match(t)
            if m:
                nombre = re.sub(r"\s*Puntuación\s*$", "", m.group("area")).strip(" -:")
                break
        if not nombre:
            continue
        if nombre.lower() in vistos or "PUNTOS" in t.upper() and "%" not in t:
            continue
        vistos.add(nombre.lower())
        # campo de puntos hermano (mismo prefijo)
        pts = next((p for p in formulas
                    if (m2 := PUNTOS.match(p)) and m2.group("area").strip().lower() == nombre.lower()), None)
        areas.append({"area": nombre, "campo_pct": t, "campo_puntos": pts})
    return {"score_total": total, "areas": areas, "n_formulas": len(set(formulas))}


def main() -> None:
    with conn() as c:
        fts = [r["form_template_id"] for r in c.execute(
            "SELECT DISTINCT form_template_id FROM raw_submissions ORDER BY 1")]
        fams = {r["form_template_id"]: r["familia"] for r in c.execute(
            "SELECT DISTINCT form_template_id, familia FROM raw_submissions")}
        spec = {}
        for ft in fts:
            a = analizar_ft(c, ft)
            if a:
                a["familia"] = fams.get(ft)
                spec[ft] = a
    out = HERE / "drilldown_spec.json"
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    for ft, e in sorted(spec.items(), key=lambda x: (x[1]["familia"] or "", x[0])):
        tot = (e["score_total"] or "—")[:40]
        print(f"{(e['familia'] or '?')[:25]:<25} ft{ft} total={tot:<40} áreas={len(e['areas'])}")


if __name__ == "__main__":
    main()
