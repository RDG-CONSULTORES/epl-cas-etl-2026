"""Renderiza los datos del reporte a HTML nativo de correo (tablas, colores inline).
Se lee en el teléfono sin abrir nada. On-brand oscuro CAS.
"""
from __future__ import annotations

NOMBRES = {
    "alistamiento_diario": "Alistamiento Diario", "rl1_entrega_t1": "RL1 Entrega 1er Turno",
    "rl2_entrega_t2": "RL2 Entrega 2º Turno", "checklist_cierre": "Checklist de Cierre",
    "deposito_valores": "Depósito de Valores", "alistamiento_servir": "Alistamiento SERVIR",
    "alistamiento_hornos": "Alistamiento Hornos", "autogestion_calidad": "Autogestión de Calidad",
    "pro_suc_1": "PRO-SUC-1 Evaluación", "pro_suc_3": "PRO-SUC-3 Procesos",
    "pro_suc_4_autoeval": "PRO-SUC-4 Autoevaluación", "visita_negocio": "Visita de Negocio",
    "rh1_visita": "RH-1 Visita", "recorrido_comisariato": "Recorrido Comisariato",
    "mtto_mensual": "Mtto Mensual", "vcal_calidad_integral": "VCAL Verificación Calidad",
}
ZN = {"nuevo_leon": "Nuevo León", "laguna": "Laguna", "queretaro": "Querétaro"}


def _color(p):
    return "#34d399" if (p is not None and p >= 90) else "#fbbf24" if (p is not None and p >= 70) else "#f0526a"


def _glifo(p):
    return "" if p is None else "✓" if p >= 90 else "~" if p >= 70 else "✕"


def _delta(d):
    if d is None:
        return '<span style="color:#6d6d7e">—</span>'
    col = "#34d399" if d > 0 else "#f0526a" if d < 0 else "#a4a4b4"
    fl = "▲" if d > 0 else "▼" if d < 0 else "▬"
    return f'<span style="color:{col};font-weight:700">{fl} {abs(d):g} pp</span>'


def html(d: dict, titulo: str = "Cumplimiento PLOG") -> str:
    per = d["periodo"]
    g = d["global"]
    gtxt = f"{round(g)}%" if g is not None else "—"
    filas_suc = "".join(
        f'<tr><td style="padding:7px 10px;border-top:1px solid #2c2c38;font-size:13px">{s["nombre"]}'
        f'<span style="color:#6d6d7e"> · {ZN.get(s["zona"], s["zona"])}</span></td>'
        f'<td style="padding:7px 10px;border-top:1px solid #2c2c38;text-align:right;font-weight:700;'
        f'color:{_color(s["pct"])};font-size:13px">{_glifo(s["pct"])} {round(s["pct"]) if s["pct"] is not None else "—"}%</td></tr>'
        for s in d["sucursales"][:12])
    filas_falt = "".join(
        f'<tr><td style="padding:6px 10px;border-top:1px solid #2c2c38;font-size:13px">{NOMBRES.get(f["familia"], f["familia"])}</td>'
        f'<td style="padding:6px 10px;border-top:1px solid #2c2c38;text-align:right;font-size:13px;color:#f0526a;font-weight:700">{f["faltas"]}</td></tr>'
        for f in d["top_faltados"])
    zonas_chips = " · ".join(
        f'<b style="color:{_color(z["pct"])}">{ZN.get(z["zona"], z["zona"])} {round(z["pct"]) if z["pct"] is not None else "—"}%</b>'
        for z in d["zonas"])

    return f"""<!DOCTYPE html><html><body style="margin:0;background:#0a0a0f;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif">
<div style="max-width:560px;margin:0 auto;padding:24px 18px;color:#f4f4f7">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
    <div style="width:30px;height:30px;border-radius:8px;background:#ff6b35;color:#1a0d06;font-weight:800;text-align:center;line-height:30px">PL</div>
    <div style="font-weight:700;font-size:17px">{titulo}</div></div>
  <div style="color:#6d6d7e;font-size:13px;margin-bottom:18px">{per['label']}</div>

  <table width="100%" style="background:#1e1e27;border:1px solid #2c2c38;border-radius:14px;border-collapse:separate">
    <tr><td style="padding:20px">
      <div style="font-size:42px;font-weight:800;color:{_color(g)};line-height:1">{_glifo(g)} {gtxt}</div>
      <div style="color:#a4a4b4;font-size:13px;margin-top:6px">Cumplimiento del periodo · vs anterior {_delta(d['delta_prev'])}{' · vs año pasado ' + str(_delta(d['delta_yoy'])) if d['delta_yoy'] is not None else ''}</div>
      <div style="color:#a4a4b4;font-size:13px;margin-top:10px">{zonas_chips}</div>
    </td></tr>
  </table>

  <div style="font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#6d6d7e;font-weight:700;margin:22px 0 8px">Sucursales (peores arriba)</div>
  <table width="100%" style="background:#1e1e27;border:1px solid #2c2c38;border-radius:12px;border-collapse:collapse">{filas_suc}</table>

  {'<div style="font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#6d6d7e;font-weight:700;margin:22px 0 8px">Formularios más faltados</div><table width="100%" style="background:#1e1e27;border:1px solid #2c2c38;border-radius:12px;border-collapse:collapse">' + filas_falt + '</table>' if filas_falt else ''}

  <div style="margin-top:24px;text-align:center">
    <a href="{{APP_URL}}" style="display:inline-block;background:#ff6b35;color:#1a0d06;text-decoration:none;font-weight:700;padding:12px 24px;border-radius:10px;font-size:14px">Ver tablero completo</a></div>
  <div style="color:#6d6d7e;font-size:11px;text-align:center;margin-top:18px">Reporte automático de Cumplimiento PLOG · datos al corte del envío</div>
</div></body></html>"""
