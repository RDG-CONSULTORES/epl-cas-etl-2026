"""Motor esperado-vs-real: genera ventanas esperadas desde config_formularios
(la config VIVA que edita el admin) y las cruza con raw_submissions.

Recomputable: al cambiar la config (activar/desactivar, hora límite, etc.) se
recalcula el rango completo — la verdad vive en raw, esto es una vista derivada.

Estados:
  on_time  = submission dentro de la ventana y antes de la hora límite
  late     = submission después del límite pero dentro de los días de gracia
  missed   = ventana + gracia vencidas sin submission
  pending  = la ventana (o su gracia) aún no cierra

Correr:  .venv-plog/bin/python -m etl_plog.cumplimiento.motor --desde 2026-07-01
"""
from __future__ import annotations

import argparse
import calendar
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from etl_plog.shared.db import conn
from etl_plog.sync.raw_sync import FAMILIAS_SIN_LOCATION

log = logging.getLogger(__name__)
TZ_MTY = ZoneInfo("America/Monterrey")

# día de la semana (date.weekday()) -> sufijo de serie
DIA_SUFIJO = {0: "lun", 1: "mar", 2: "mie", 3: "jue", 4: "vie", 5: "sab", 6: "dom"}

# Alistamiento diario: A1-A7 y L1-L7 son la MISMA obligación (checklist de apertura),
# day-specific (1=lunes … 7=domingo). Se cumple con la A O la L del día correcto.
# Se registra cuál serie contestaron. Opcional serie_requerida por sucursal (A/L) la acota.
ALISTAMIENTO_FAMILIAS = {"alistamiento_a", "alistamiento_l"}
FT_DIA_SERIE = {  # form_template_id -> (sufijo_dia, serie)
    954598: ("lun", "A"), 1040520: ("mar", "A"), 1040521: ("mie", "A"), 1040522: ("jue", "A"),
    1040523: ("vie", "A"), 1040524: ("sab", "A"), 1010538: ("dom", "A"),
    1040507: ("lun", "L"), 1040506: ("mar", "L"), 1040504: ("mie", "L"), 1040505: ("jue", "L"),
    1038660: ("vie", "L"), 1038659: ("sab", "L"), 1038658: ("dom", "L"),
}
SEMANA_MES = {"s1": (1, 7), "s2": (8, 14), "s3": (15, 21), "s4": (22, 31)}
MESES_POR_FRECUENCIA = {"mensual": 1, "bimestral": 2, "trimestral": 3, "semestral": 6, "anual": 12}


def _fin_mes(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[-1])


def _ventanas(frecuencia: str, desde: date, hasta: date, params: dict):
    """Genera (inicio, fin, ft_esperado|None) por ventana."""
    serie = params.get("serie")
    fts = params.get("form_templates") or {}
    if frecuencia in ("diario", "diario_por_dia"):
        d = desde
        while d <= hasta:
            ft = None
            if serie == "dia_semana":
                suf = DIA_SUFIJO[d.weekday()]
                ft = next((int(k) for k, v in fts.items() if v == suf), None)
            yield d, d, ft
            d += timedelta(days=1)
    elif frecuencia == "semanal":
        d = desde - timedelta(days=desde.weekday())  # lunes
        while d <= hasta:
            yield d, d + timedelta(days=6), None
            d += timedelta(days=7)
    elif frecuencia == "semana_del_mes":
        d = desde.replace(day=1)
        while d <= hasta:
            for suf, (d1, d2) in SEMANA_MES.items():
                ft = next((int(k) for k, v in fts.items() if v == suf), None)
                fin = min(d.replace(day=min(d2, _fin_mes(d).day)), _fin_mes(d))
                yield d.replace(day=d1), fin, ft
            d = (_fin_mes(d) + timedelta(days=1))
    elif frecuencia in MESES_POR_FRECUENCIA:
        paso = MESES_POR_FRECUENCIA[frecuencia]
        d = desde.replace(day=1)
        d = d.replace(month=((d.month - 1) // paso) * paso + 1)  # alinear al periodo
        while d <= hasta:
            m_fin = d.month + paso - 1
            fin = _fin_mes(date(d.year + (m_fin - 1) // 12, (m_fin - 1) % 12 + 1, 1))
            yield d, fin, None
            fin_next = fin + timedelta(days=1)
            d = fin_next
    # por_visita / quincenal sin política: no genera expectativa


def _limites(fin: date, hora_limite, dia_sig: bool, gracia: int) -> tuple[datetime, datetime]:
    """-> (limite, limite_gracia). limite = deadline; +gracia = cuándo se cierra la ventana."""
    limite_dia = fin + timedelta(days=1) if dia_sig else fin
    hora = hora_limite or time(23, 59, 59)
    limite = datetime.combine(limite_dia, hora, tzinfo=TZ_MTY)
    return limite, limite + timedelta(days=gracia)


def _estado(fin: date, hora_limite, dia_sig: bool, gracia: int,
            sub_ts: datetime | None, ahora: datetime) -> str:
    limite, limite_gracia = _limites(fin, hora_limite, dia_sig, gracia)
    if sub_ts is not None:
        return "on_time" if sub_ts <= limite else "late"
    if ahora <= limite_gracia:
        return "pending"
    return "missed"


def run(desde: date, hasta: date | None = None) -> dict[str, int]:
    hasta = hasta or datetime.now(TZ_MTY).date()
    ahora = datetime.now(TZ_MTY)
    with conn() as c:
        cfg = list(c.execute(
            """SELECT familia, zona, frecuencia, hora_limite, dias_gracia, params
               FROM config_formularios
               WHERE activo AND medicion IN ('cumplimiento', 'ambos')"""))
        sucs = list(c.execute(
            """SELECT location_id, zona, es_comisariato, serie_requerida
               FROM sucursales WHERE activo"""))
        subs = list(c.execute(
            """SELECT familia, form_template_id, location_id, fecha_local,
                      min(ts_completed) AS ts
               FROM raw_submissions
               WHERE fecha_local BETWEEN %s AND %s AND familia IS NOT NULL
               GROUP BY 1, 2, 3, 4""", (desde, hasta)))
        # ventanas YA congeladas: no se recalculan ni se sobrescriben (histórico inmutable)
        frozen = {(r["familia"], r["location_id"], r["periodo_inicio"]) for r in c.execute(
            """SELECT familia, location_id, periodo_inicio FROM cumplimiento
               WHERE congelado AND periodo_inicio BETWEEN %s AND %s""", (desde, hasta))}

    def _snap(hora_limite, gracia, frecuencia, dia_sig):
        return {"hora_limite": str(hora_limite) if hora_limite else None,
                "dias_gracia": gracia, "frecuencia": frecuencia, "dia_siguiente": dia_sig}

    # índices: (familia, loc) -> [(fecha, ft, ts)]
    por_fam_loc: dict[tuple, list] = {}
    # alistamiento diario mergeado: (loc, fecha) -> [(ft, serie, ts)] de AMBAS series
    alist_por_loc_dia: dict[tuple, list] = {}
    for s in subs:
        por_fam_loc.setdefault((s["familia"], s["location_id"]), []).append(
            (s["fecha_local"], s["form_template_id"], s["ts"]))
        if s["familia"] in ALISTAMIENTO_FAMILIAS:
            dia_serie = FT_DIA_SERIE.get(s["form_template_id"])
            if dia_serie:
                alist_por_loc_dia.setdefault((s["location_id"], s["fecha_local"]), []).append(
                    (s["form_template_id"], dia_serie[1], s["ts"]))

    filas, contadores = [], {"on_time": 0, "late": 0, "missed": 0, "pending": 0}
    for row in cfg:
        params = row["params"] or {}
        aplica = (params.get("sucursales_aplica") or "").lower()
        solo_comisariato = "comisariato" in aplica
        condicional = "hallazgo" in aplica            # visita_seguimiento: solo donde hay hallazgo
        flotilla = "flotilla" in aplica               # vehículos: por unidad, no por sucursal
        dia_sig = bool(params.get("dia_siguiente"))
        # alistamiento_l se procesa junto con alistamiento_a (mergeado); saltarlo suelto
        if row["familia"] == "alistamiento_l":
            continue
        es_alist = row["familia"] == "alistamiento_a"
        if condicional or flotilla:
            continue  # no generan expectativa fija de calendario (se miden aparte)
        for suc in sucs:
            if suc["zona"] != row["zona"]:
                continue
            if solo_comisariato:
                if not suc["es_comisariato"]:
                    continue
                es_virtual = suc["location_id"] < 0
                if es_virtual != (row["familia"] in FAMILIAS_SIN_LOCATION):
                    continue
            elif suc["location_id"] < 0:
                continue  # virtuales solo aplican a familias de comisariato

            if es_alist:
                # alistamiento diario: A o L del día correcto; registra cuál contestaron
                requerida = suc.get("serie_requerida")  # 'A'|'L'|None(cualquiera)
                d = desde
                while d <= hasta:
                    fin = d
                    if ("alistamiento_diario", suc["location_id"], d) in frozen:
                        d += timedelta(days=1); continue  # congelada: no tocar
                    hechas = alist_por_loc_dia.get((suc["location_id"], d), [])
                    if requerida:
                        hechas = [h for h in hechas if h[1] == requerida]
                    hechas.sort(key=lambda x: x[2] or datetime.max.replace(tzinfo=TZ_MTY))
                    ft_ok, serie_ok, sub_ts = (hechas[0] if hechas else (None, None, None))
                    est = _estado(fin, row["hora_limite"], dia_sig, row["dias_gracia"], sub_ts, ahora)
                    _, lim_gracia = _limites(fin, row["hora_limite"], dia_sig, row["dias_gracia"])
                    cerrado = ahora > lim_gracia
                    snap = Jsonb(_snap(row["hora_limite"], row["dias_gracia"], "diario", dia_sig)) if cerrado else None
                    contadores[est] += 1
                    filas.append(("alistamiento_diario", row["zona"], suc["location_id"],
                                  d, fin, est, None, sub_ts, serie_ok, ft_ok, cerrado, snap))
                    d += timedelta(days=1)
                continue

            hist = por_fam_loc.get((row["familia"], suc["location_id"]), [])
            for ini, fin, ft in _ventanas(row["frecuencia"], desde, hasta, params):
                if fin < desde or ini > hasta:
                    continue
                if (row["familia"], suc["location_id"], ini) in frozen:
                    continue  # congelada: no tocar
                candidatas = [(f, t, tpl) for f, tpl, t in hist
                              if ini <= f <= fin + timedelta(days=row["dias_gracia"])
                              and (ft is None or tpl == ft)]
                sub_ts = min((t for _, t, _ in candidatas), default=None)
                ft_ok = candidatas[0][2] if candidatas else None
                est = _estado(fin, row["hora_limite"], dia_sig,
                              row["dias_gracia"], sub_ts, ahora)
                _, lim_gracia = _limites(fin, row["hora_limite"], dia_sig, row["dias_gracia"])
                cerrado = ahora > lim_gracia
                snap = Jsonb(_snap(row["hora_limite"], row["dias_gracia"], row["frecuencia"], dia_sig)) if cerrado else None
                contadores[est] += 1
                filas.append((row["familia"], row["zona"], suc["location_id"],
                              ini, fin, est, None, sub_ts, None, ft_ok, cerrado, snap))

    with conn() as c:
        cur = c.cursor()
        # borrar SOLO ventanas NO congeladas en el rango (las congeladas son inmutables)
        cur.execute("""DELETE FROM cumplimiento
                       WHERE periodo_inicio BETWEEN %s AND %s AND NOT congelado""",
                    (desde, hasta))
        cur.executemany(
            """INSERT INTO cumplimiento
                 (familia, zona, location_id, periodo_inicio, periodo_fin,
                  estado, submission_id, ts_submission, serie_contestada, form_template_id,
                  congelado, politica_snapshot)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (familia, location_id, periodo_inicio) DO UPDATE
                 SET estado=EXCLUDED.estado, ts_submission=EXCLUDED.ts_submission,
                     periodo_fin=EXCLUDED.periodo_fin, serie_contestada=EXCLUDED.serie_contestada,
                     form_template_id=EXCLUDED.form_template_id, congelado=EXCLUDED.congelado,
                     politica_snapshot=EXCLUDED.politica_snapshot, computed_at=now()
                 WHERE NOT cumplimiento.congelado""",
            filas)
    return contadores


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", required=True)
    ap.add_argument("--hasta")
    a = ap.parse_args()
    res = run(date.fromisoformat(a.desde), date.fromisoformat(a.hasta) if a.hasta else None)
    total = sum(res.values())
    pct = (res["on_time"] + res["late"]) / max(total - res["pending"], 1) * 100
    print(f"ventanas: {total} · on_time {res['on_time']} · late {res['late']} · "
          f"missed {res['missed']} · pending {res['pending']} · cumplimiento {pct:.1f}%")
