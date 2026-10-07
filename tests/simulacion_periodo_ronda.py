#!/usr/bin/env python3
"""Simulación del ETL por ronda (2026-10-06).

Requiere una BD local `epl_cas_q3fix` = dump de prod + sql/q3_2026_asignacion_por_ronda_2026_10_06.sql.
Uso: python tests/simulacion_periodo_ronda.py .   (crea/borra BDs sim_a y sim_d desde esa plantilla)
"""
import os, sys, subprocess, importlib
W = sys.argv[1]; sys.path.insert(0, W)
def fresh(name):
    subprocess.run(['dropdb','--if-exists',name],check=True)
    subprocess.run(['createdb','-T','epl_cas_q3fix',name],check=True)
    os.environ['DATABASE_URL']=f'postgresql://robertodavila@localhost/{name}'
    import etl_sync; importlib.reload(etl_sync); etl_sync._TIENE_ACTIVA_DESDE=None
    return etl_sync
def sub(sid, loc, fecha, sup='Sim', with_loc=True):
    return {'id': sid, 'answers': [], 'smetadata': {'location': {'id': loc} if with_loc else {}, 'created_by': {'display_name': sup},
            'date_submitted': fecha, 'lat': None, 'lon': None}}
def per(cur, tabla, zid):
    cur.execute(f"select p.codigo from {tabla} t join periodos_cas p on p.id=t.periodo_id where zenput_submission_id=%s",(zid,)); r=cur.fetchone(); return r and r['codigo']
def estado(cur):
    cur.execute("select codigo from periodos_cas where activo"); a=[r['codigo'] for r in cur.fetchall()]
    cur.execute("select activo from sucursales where id=65"); lin=cur.fetchone()['activo']
    cur.execute("""select p.codigo, count(distinct so.sucursal_id) n from supervisiones_operativas so join periodos_cas p on p.id=so.periodo_id
                   join sucursales s on s.id=so.sucursal_id and s.activo where p.codigo in ('Q3-2026','Q4-2026') group by 1 order by 1""")
    return a, lin, {r['codigo']:r['n'] for r in cur.fetchall()}
ok=True
def check(cond,msg):
    global ok; print(('  ✅ ' if cond else '  ❌ ')+msg); ok&=bool(cond)
PN,MON,GUA,LIN=2247069,2247056,2247022,2247067

print('== A. Hoy: Piedras Negras (op+seg) y mañana Monclova; Q3 sigue abierto')
e=fresh('sim_a'); 
with e.get_db() as c:
    e.sync_operativas(c,[sub('PN-OP',PN,'2026-10-06T17:00:00Z'), sub('MON-OP',MON,'2026-10-07T17:00:00Z')])
    e.sync_seguridad(c,[sub('PN-SEG',PN,'2026-10-06T16:30:00Z'), sub('MON-SEG',MON,'2026-10-07T16:40:00Z','Sim',True)]); c.commit()
    e.verificar_transicion_periodo(c); cur=c.cursor()
    for z,t in [('PN-OP','supervisiones_operativas'),('PN-SEG','supervisiones_seguridad'),('MON-OP','supervisiones_operativas'),('MON-SEG','supervisiones_seguridad')]:
        check(per(cur,t,z)=='Q4-2026', f'{z} → {per(cur,t,z)}')
    a,lin,n=estado(cur); check(a==['Q3-2026'] and n.get('Q3-2026')==83, f'activo={a}, Q3 {n.get("Q3-2026")}/84, Linares activa={lin}')
    check(lin is False,'Linares sigue fuera del universo')

print('== B. Luego visitan Guasave (op+seg, seg SIN location casada por supervisor/fecha) → cierra Q3, abre Q4, entra Linares')
with e.get_db() as c:
    e.sync_operativas(c,[sub('GUA-OP',GUA,'2026-10-20T18:00:00Z','Jorge Reynosa')])
    e.sync_seguridad(c,[sub('GUA-SEG',None,'2026-10-20T17:30:00Z','Jorge Reynosa',with_loc=False)]); c.commit()
    nuevo=e.verificar_transicion_periodo(c); cur=c.cursor()
    check(per(cur,'supervisiones_operativas','GUA-OP')=='Q3-2026', f"GUA-OP → {per(cur,'supervisiones_operativas','GUA-OP')}")
    check(per(cur,'supervisiones_seguridad','GUA-SEG')=='Q3-2026', f"GUA-SEG → {per(cur,'supervisiones_seguridad','GUA-SEG')}")
    a,lin,n=estado(cur); check(a==['Q4-2026'] and lin is True and n.get('Q3-2026')==84, f'transición={nuevo}, activo={a}, Q3 {n.get("Q3-2026")}/84, Linares activa={lin}')

print('== C. Después: Linares y otra de Guasave → Q4; una 2a de Piedras Negras en Q4 → no se repite en Q4')
with e.get_db() as c:
    e.sync_operativas(c,[sub('LIN-OP',LIN,'2026-10-25T18:00:00Z'), sub('GUA2-OP',GUA,'2026-11-20T18:00:00Z'), sub('PN2-OP',PN,'2026-11-21T18:00:00Z')]); c.commit(); cur=c.cursor()
    for z in ('LIN-OP','GUA2-OP'): check(per(cur,'supervisiones_operativas',z)=='Q4-2026', f"{z} → {per(cur,'supervisiones_operativas',z)}")
    p=per(cur,'supervisiones_operativas','PN2-OP'); check(p=='Q4-2026', f'PN2-OP → {p} (no existe Q1-2027: queda en Q4 con WARN en log)')

print('== D. Linares visitada ANTES de cerrar Q3 → Q4, y no cuenta en Q3')
e=fresh('sim_d')
with e.get_db() as c:
    e.sync_operativas(c,[sub('LIN-OP',LIN,'2026-10-08T18:00:00Z')]); c.commit()
    e.verificar_transicion_periodo(c); cur=c.cursor()
    check(per(cur,'supervisiones_operativas','LIN-OP')=='Q4-2026', f"LIN-OP → {per(cur,'supervisiones_operativas','LIN-OP')}")
    a,lin,n=estado(cur); check(a==['Q3-2026'] and n.get('Q3-2026')==83, f'activo={a}, Q3 {n.get("Q3-2026")}/84')
del e
import gc; gc.collect()
for d in ('sim_a','sim_d'): subprocess.run(['dropdb','--force',d])
print('\nRESULTADO:', 'TODO OK' if ok else 'HAY FALLAS'); sys.exit(0 if ok else 1)
