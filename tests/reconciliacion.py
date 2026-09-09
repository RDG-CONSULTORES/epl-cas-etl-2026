#!/usr/bin/env python3
"""
Prueba de RECONCILIACIÓN del dashboard EPL CAS.
Recalcula con SQL (misma regla en todo: M1 por sucursal-trimestre, M3 anidado por año,
peso igual por sucursal, solo activas) y compara contra CADA endpoint del dashboard:
header, chips, ranking de grupos y sucursales, modal de grupo y de sucursal, mapa,
histórico y alertas, para operativas y seguridad, en Q1/Q2/Q3 y año completo.
Si un solo número no cuadra, la prueba falla (exit 1).

Uso:  python tests/reconciliacion.py --base https://epl-cas-etl-2026-staging.up.railway.app \
          --dsn postgresql://robertodavila@localhost/epl_cas_audit [--tol 0.01]
"""
import argparse, json, sys, time, urllib.request
import psycopg2

ap = argparse.ArgumentParser()
ap.add_argument('--base', required=True); ap.add_argument('--dsn', required=True)
ap.add_argument('--tol', type=float, default=0.011); ap.add_argument('--anio', type=int, default=None)
A = ap.parse_args()
conn = psycopg2.connect(A.dsn); cur = conn.cursor()
def q(sql, p=()): cur.execute(sql, p); return cur.fetchall()
def api(path):
    for i in range(3):
        try:
            with urllib.request.urlopen(A.base + path, timeout=60) as r: return json.load(r)
        except Exception as e:
            if i == 2: raise
            time.sleep(1)
def r2(v): return None if v is None else round(float(v), 2)

FALLAS, N = [], [0]
def check(where, esperado, obtenido, tol=None):
    N[0] += 1
    tol = A.tol if tol is None else tol
    ok = (esperado is None and obtenido is None) or (esperado is not None and obtenido is not None and abs(float(esperado) - float(obtenido)) <= tol)
    if not ok: FALLAS.append((where, esperado, obtenido))
def check_eq(where, esperado, obtenido):
    N[0] += 1
    if esperado != obtenido: FALLAS.append((where, esperado, obtenido))

anio = A.anio or q("SELECT EXTRACT(YEAR FROM fecha_inicio)::int FROM periodos_cas WHERE activo ORDER BY fecha_inicio DESC LIMIT 1")[0][0]
periodos = q("SELECT id, codigo, nombre FROM periodos_cas WHERE EXTRACT(YEAR FROM fecha_inicio)=%s ORDER BY fecha_inicio", (anio,))
activas = {r[0]: (r[1], r[2]) for r in q("SELECT id, nombre, grupo_operativo_id FROM sucursales WHERE activo")}
grupos = {r[0]: r[1] for r in q("SELECT id, nombre FROM grupos_operativos WHERE activo")}
TABLAS = {'operativas': 'supervisiones_operativas', 'seguridad': 'supervisiones_seguridad'}

def m1(tabla, pid):
    """M1 por sucursal activa en el trimestre."""
    return {r[0]: float(r[1]) for r in q(f"SELECT so.sucursal_id, AVG(so.calificacion_general) FROM {tabla} so JOIN sucursales sa ON sa.id=so.sucursal_id AND sa.activo WHERE so.periodo_id=%s GROUP BY 1", (pid,))}
def m3(tabla, yr, solo_activas=True):
    act = "AND sa.activo" if solo_activas else ""
    return {r[0]: float(r[1]) for r in q(f"""SELECT sucursal_id, AVG(m1) FROM (SELECT so.sucursal_id, so.periodo_id, AVG(so.calificacion_general) m1 FROM {tabla} so JOIN sucursales sa ON sa.id=so.sucursal_id {act} JOIN periodos_cas p ON p.id=so.periodo_id WHERE EXTRACT(YEAR FROM p.fecha_inicio)=%s GROUP BY 1,2) x GROUP BY 1""", (yr,))}
def avg(vals): 
    vals = [v for v in vals if v is not None]
    return (sum(vals) / len(vals)) if vals else None
def grupo_avg(sc, gid): return avg([sc[s] for s in activas if activas[s][1] == gid and s in sc])
def sem(v): return 'excelente' if v >= 90 else 'bueno' if v >= 80 else 'regular' if v >= 70 else 'critico'

for tipo, tabla in TABLAS.items():
    alcances = [(p[0], p[1]) for p in periodos if q(f"SELECT 1 FROM {tabla} WHERE periodo_id=%s LIMIT 1", (p[0],))] + [('all', f'Año {anio}')]
    for pid, lab in alcances:
        sc = m3(tabla, anio) if pid == 'all' else m1(tabla, pid)
        tag = f"{tipo}/{lab}"
        # ---- header ----
        k = api(f"/api/kpis/{tipo}?periodo_id={pid}")['data']
        check(f"{tag} header.promedio", avg(sc.values()), k['promedio'])
        check_eq(f"{tag} header.sucursales_supervisadas", len(sc), k['sucursales_supervisadas'])
        check_eq(f"{tag} header.total_sucursales", len(activas), k['total_sucursales'])
        dist = {'excelente': 0, 'bueno': 0, 'regular': 0, 'critico': 0}
        for v in sc.values(): dist[sem(v)] += 1
        for kk in dist: check_eq(f"{tag} header.distribucion.{kk}", dist[kk], k['distribucion'][kk])
        check_eq(f"{tag} header.total_grupos", len({activas[s][1] for s in sc}), k['total_grupos'])
        check(f"{tag} header.promedio_acumulado (M3 {anio})", avg(m3(tabla, anio).values()), k['promedio_acumulado'])
        check(f"{tag} header.promedio_anio_anterior (M3 {anio-1}, todas)", avg(m3(tabla, anio - 1, False).values()), k['promedio_anio_anterior'])
        m2 = q(f"SELECT AVG(cg) FROM (SELECT DISTINCT ON (so.sucursal_id) so.calificacion_general cg FROM {tabla} so JOIN sucursales sa ON sa.id=so.sucursal_id AND sa.activo ORDER BY so.sucursal_id, so.fecha_supervision DESC) x")[0][0]
        check(f"{tag} header.estado_actual (M2)", m2, k['estado_actual'])
        for ch in k['trimestres']:
            check(f"{tag} chip {ch['codigo']}", avg(m1(tabla, ch['id']).values()), ch['promedio'])
            check_eq(f"{tag} chip {ch['codigo']}.evaluadas", len(m1(tabla, ch['id'])), ch['evaluadas'])
        # ---- ranking sucursales ----
        rs = api(f"/api/ranking/sucursales/{tipo}?periodo_id={pid}")['data']
        check_eq(f"{tag} ranking.sucursales.count", len(activas), len(rs))
        for it in rs:
            check(f"{tag} ranking.sucursal[{it['nombre']}]", sc.get(it['id']), it['promedio'])
        # ---- ranking grupos + PLOG ----
        rg = api(f"/api/ranking/grupos/{tipo}?periodo_id={pid}")['data']
        vistos = 0
        for it in rg:
            if it['tipo'] == 'agrupacion':
                subs = [grupo_avg(sc, g['id']) for g in it['grupos']]
                check(f"{tag} ranking.agrupacion[{it['nombre']}] (jerárquico)", avg(subs), it['promedio'])
                for g in it['grupos']:
                    check(f"{tag} ranking.grupo[{g['nombre']}]", grupo_avg(sc, g['id']), g['promedio']); vistos += 1
            else:
                check(f"{tag} ranking.grupo[{it['nombre']}]", grupo_avg(sc, it['id']), it['promedio']); vistos += 1
        check_eq(f"{tag} ranking.grupos.count", len(grupos), vistos)
        proms = [it['promedio'] for it in rg if it['promedio'] is not None]
        check_eq(f"{tag} ranking.grupos.orden", proms, sorted(proms, reverse=True))
        # ---- modal de grupo (todos) ----
        for gid, gname in grupos.items():
            g = api(f"/api/grupo/{gid}/{tipo}?periodo_id={pid}")['data']
            check(f"{tag} modal.grupo[{gname}].promedio", grupo_avg(sc, gid), g['promedio'])
            for s in g['sucursales']:
                check(f"{tag} modal.grupo[{gname}].sucursal[{s['nombre']}]", sc.get(s['id']), s['promedio'])
        # ---- modal de sucursal (todas) ----
        for sid, (sname, _) in activas.items():
            s = api(f"/api/sucursal/{sid}/{tipo}?periodo_id={pid}")['data']
            check(f"{tag} modal.sucursal[{sname}].promedio", sc.get(sid), s['promedio'])
        # ---- mapa ----
        mp = api(f"/api/mapa/{tipo}?periodo_id={pid}")['data']
        check_eq(f"{tag} mapa.count", len(activas), len(mp))
        for m in mp: check(f"{tag} mapa[{m['nombre']}]", sc.get(m['id']), m['promedio'])
        # ---- alertas ----
        al = api(f"/api/alertas/{tipo}?periodo_id={pid}")['data']
        crit = sorted(s for s, v in sc.items() if v < 70)
        check_eq(f"{tag} alertas.criticos", crit, sorted(a['sucursal_id'] for a in al['alertas'] if a['tipo'] == 'critical'))
        warn = sorted(gid for gid in grupos if (ga := grupo_avg(sc, gid)) is not None and 70 <= ga < 80)
        check_eq(f"{tag} alertas.grupos_en_riesgo", warn, sorted(a['grupo_id'] for a in al['alertas'] if a['tipo'] == 'warning'))
    # ---- histórico ----
    h = api(f"/api/historico/{tipo}")['data']
    for p in periodos:
        scp = m1(tabla, p[0])
        if not scp: continue
        check(f"{tipo} historico.EPL_CAS[{p[2]}]", avg(scp.values()), (h['epl_cas']['periodos'].get(p[2]) or {}).get('promedio'))
        for g in h['grupos']:
            check(f"{tipo} historico.grupo[{g['nombre']}][{p[2]}]", grupo_avg(scp, g['id']), (g['periodos'].get(p[2]) or {}).get('promedio'))
    check_eq(f"{tipo} historico.grupos.count", len(grupos), len(h['grupos']))

print(f"\nRECONCILIACIÓN {A.base}\n  comparaciones: {N[0]}  ·  diferencias: {len(FALLAS)}")
for w, e, o in FALLAS[:60]: print(f"  ✗ {w}: esperado {r2(e) if isinstance(e,(int,float)) else e} · dashboard {r2(o) if isinstance(o,(int,float)) else o}")
sys.exit(1 if FALLAS else 0)
