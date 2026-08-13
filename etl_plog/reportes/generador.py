"""Generador de reportes de cumplimiento — todas las cadencias + comparativos.

Un solo generador parametrizado por periodo. Lee cumplimiento/calificaciones (BD),
respeta el scope del destinatario, y arma los datos + comparativo (vs periodo
anterior y vs mismo periodo del año pasado).
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from etl_plog.api import scoping
from etl_plog.shared.db import conn

CADENCIAS = ("semanal", "quincenal", "mensual", "bimestral", "trimestral", "semestral", "anual")


def _fin_mes(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[-1])


def periodo(cadencia: str, ref: date) -> dict:
    """-> {inicio, fin, prev_inicio, prev_fin, yoy_inicio, yoy_fin, label}."""
    if cadencia == "semanal":
        ini = ref - timedelta(days=ref.weekday() + 7)  # lunes de la semana anterior
        fin = ini + timedelta(days=6)
        pini, pfin = ini - timedelta(days=7), fin - timedelta(days=7)
        label = f"Semana {ini.strftime('%d')}–{fin.strftime('%d %b %Y')}"
    elif cadencia == "quincenal":
        if ref.day <= 15:
            fin = ref.replace(day=1) - timedelta(days=1); ini = fin.replace(day=16)
        else:
            ini = ref.replace(day=1); fin = ref.replace(day=15)
        dias = (fin - ini).days + 1
        pini, pfin = ini - timedelta(days=dias), ini - timedelta(days=1)
        label = f"Quincena {ini.strftime('%d')}–{fin.strftime('%d %b %Y')}"
    elif cadencia == "mensual":
        prev = ref.replace(day=1) - timedelta(days=1)
        ini, fin = prev.replace(day=1), prev
        pini = (ini - timedelta(days=1)).replace(day=1); pfin = ini - timedelta(days=1)
        label = ini.strftime("%B %Y").capitalize()
    else:
        meses = {"bimestral": 2, "trimestral": 3, "semestral": 6, "anual": 12}[cadencia]
        m0 = ((ref.month - 1) // meses) * meses + 1
        ini_actual = ref.replace(month=m0, day=1)
        fin_prev = ini_actual - timedelta(days=1)
        pm0 = ((fin_prev.month - 1) // meses) * meses + 1
        ini = fin_prev.replace(month=pm0, day=1)
        fin = fin_prev
        pfin = ini - timedelta(days=1)
        ppm0 = ((pfin.month - 1) // meses) * meses + 1
        pini = pfin.replace(month=ppm0, day=1)
        label = f"{cadencia.capitalize()} {ini.strftime('%b')}–{fin.strftime('%b %Y')}"
    try:
        yini = ini.replace(year=ini.year - 1); yfin = fin.replace(year=fin.year - 1)
    except ValueError:
        yini = yfin = None
    return {"inicio": ini, "fin": fin, "prev_inicio": pini, "prev_fin": pfin,
            "yoy_inicio": yini, "yoy_fin": yfin, "label": label}


def _pct(cur, where, params, ini, fin) -> float | None:
    r = cur.execute(f"""SELECT round(100.0*count(*) FILTER (WHERE estado IN ('on_time','late'))
                        /NULLIF(count(*) FILTER (WHERE estado<>'pending'),0),1) p
                        FROM cumplimiento c WHERE {where} AND periodo_inicio BETWEEN %s AND %s""",
                    params + [ini, fin]).fetchone()
    return float(r["p"]) if r["p"] is not None else None


def datos(cadencia: str, ref: date, scopes: list[dict]) -> dict:
    per = periodo(cadencia, ref)
    w, params = scoping.clausula_scope(scopes, "c")
    with conn() as c:
        cur = c.cursor()
        glob = _pct(cur, w, params, per["inicio"], per["fin"])
        prev = _pct(cur, w, params, per["prev_inicio"], per["prev_fin"])
        yoy = _pct(cur, w, params, per["yoy_inicio"], per["yoy_fin"]) if per["yoy_inicio"] else None
        zonas = cur.execute(f"""SELECT zona, round(100.0*count(*) FILTER (WHERE estado IN ('on_time','late'))
                    /NULLIF(count(*) FILTER (WHERE estado<>'pending'),0),1) pct
                    FROM cumplimiento c WHERE {w} AND periodo_inicio BETWEEN %s AND %s
                    GROUP BY zona ORDER BY pct""", params + [per["inicio"], per["fin"]]).fetchall()
        sucs = cur.execute(f"""SELECT s.nombre, s.zona, round(100.0*count(*) FILTER (WHERE c.estado IN ('on_time','late'))
                    /NULLIF(count(*) FILTER (WHERE c.estado<>'pending'),0),1) pct
                    FROM cumplimiento c JOIN sucursales s USING(location_id)
                    WHERE {w} AND c.periodo_inicio BETWEEN %s AND %s
                    GROUP BY s.nombre, s.zona ORDER BY pct ASC LIMIT 30""",
                    params + [per["inicio"], per["fin"]]).fetchall()
        top_faltados = cur.execute(f"""SELECT familia, count(*) FILTER (WHERE estado='missed') faltas,
                    round(100.0*count(*) FILTER (WHERE estado IN ('on_time','late'))
                    /NULLIF(count(*) FILTER (WHERE estado<>'pending'),0),1) pct
                    FROM cumplimiento c WHERE {w} AND periodo_inicio BETWEEN %s AND %s
                    GROUP BY familia HAVING count(*) FILTER (WHERE estado='missed')>0
                    ORDER BY faltas DESC LIMIT 6""", params + [per["inicio"], per["fin"]]).fetchall()
    return {"cadencia": cadencia, "periodo": per, "global": glob, "prev": prev, "yoy": yoy,
            "delta_prev": (round(glob - prev, 1) if glob is not None and prev is not None else None),
            "delta_yoy": (round(glob - yoy, 1) if glob is not None and yoy is not None else None),
            "zonas": zonas, "sucursales": sucs, "top_faltados": top_faltados}
