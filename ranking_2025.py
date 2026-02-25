#!/usr/bin/env python3
"""
EPL CAS 2025 - Rankings para Premios de Convención
Genera rankings de Grupos Operativos y Sucursales (Locales/Foráneas)
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ['DATABASE_URL']

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def ranking_grupos():
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 100)
    print("  RANKING GENERAL POR GRUPOS OPERATIVOS 2025")
    print("  Criterio: Promedio Supervisión Operativa | Desempate: Supervisión de Seguridad")
    print("=" * 100)

    # Promedio operativo por grupo
    cur.execute('''
        SELECT
            g.id, g.nombre,
            ROUND(AVG(so.calificacion_general)::numeric, 2) as prom_operativo,
            COUNT(so.id) as total_evals_op,
            COUNT(DISTINCT so.sucursal_id) as sucursales_evaluadas,
            (SELECT COUNT(*) FROM sucursales ss WHERE ss.grupo_operativo_id = g.id AND ss.activo = true) as total_sucursales
        FROM grupos_operativos g
        LEFT JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true
        LEFT JOIN supervisiones_operativas so ON s.id = so.sucursal_id
            AND EXTRACT(YEAR FROM so.fecha_supervision) = 2025
        WHERE g.activo = true
        GROUP BY g.id, g.nombre
        ORDER BY prom_operativo DESC NULLS LAST
    ''')
    grupos_op = cur.fetchall()

    # Promedio seguridad por grupo (para desempate)
    cur.execute('''
        SELECT
            g.id,
            ROUND(AVG(ss.calificacion_general)::numeric, 2) as prom_seguridad,
            COUNT(ss.id) as total_evals_seg
        FROM grupos_operativos g
        LEFT JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true
        LEFT JOIN supervisiones_seguridad ss ON s.id = ss.sucursal_id
            AND EXTRACT(YEAR FROM ss.fecha_supervision) = 2025
        WHERE g.activo = true
        GROUP BY g.id
    ''')
    seg_map = {r['id']: r for r in cur.fetchall()}

    # Combinar
    grupos = []
    for g in grupos_op:
        seg = seg_map.get(g['id'], {})
        prom_op = float(g['prom_operativo']) if g['prom_operativo'] else 0
        prom_seg = float(seg.get('prom_seguridad') or 0)
        grupos.append({
            'id': g['id'],
            'nombre': g['nombre'],
            'prom_op': prom_op,
            'evals_op': g['total_evals_op'],
            'sucursales_eval': g['sucursales_evaluadas'],
            'total_sucursales': g['total_sucursales'],
            'prom_seg': prom_seg,
            'evals_seg': seg.get('total_evals_seg', 0),
        })

    # Ordenar: prom_op DESC, desempate prom_seg DESC
    grupos.sort(key=lambda x: (-x['prom_op'], -x['prom_seg']))

    # Asignar posiciones con empate técnico
    pos = 1
    for i, g in enumerate(grupos):
        if g['prom_op'] == 0:
            g['pos'] = '-'
        elif i > 0 and g['prom_op'] == grupos[i-1]['prom_op'] and g['prom_seg'] == grupos[i-1]['prom_seg']:
            g['pos'] = grupos[i-1]['pos']
        else:
            g['pos'] = pos
        pos += 1

    header = f"{'Pos':<5} {'Grupo Operativo':<30} {'Prom Op':>8} {'Prom Seg':>9} {'Evals':>6} {'Sucs':>10}"
    print(header)
    print("-" * 100)
    for g in grupos:
        p = str(g['pos']) if g['pos'] != '-' else 'S/E'
        sucs = f"{g['sucursales_eval']}/{g['total_sucursales']}"
        print(f"{p:<5} {g['nombre']:<30} {g['prom_op']:>7.2f}% {g['prom_seg']:>8.2f}% {g['evals_op']:>6} {sucs:>10}")

    print(f"\nTotal grupos: {len(grupos)}")
    conn.close()
    return grupos


def ranking_sucursales(clasificacion):
    conn = get_conn()
    cur = conn.cursor()

    tipo_label = "LOCALES" if clasificacion == 'local' else "FORANEAS"
    evals_esperadas = 4 if clasificacion == 'local' else 2

    print("\n" + "=" * 110)
    print(f"  RANKING DE SUCURSALES {tipo_label} 2025")
    print(f"  Evaluaciones esperadas: {evals_esperadas} | Desempate: Supervisión de Seguridad")
    print("=" * 110)

    # Promedio operativo por sucursal
    cur.execute('''
        SELECT
            s.id, s.nombre, s.numero, g.nombre as grupo,
            ROUND(AVG(so.calificacion_general)::numeric, 2) as prom_operativo,
            COUNT(so.id) as total_evals
        FROM sucursales s
        JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
        LEFT JOIN supervisiones_operativas so ON s.id = so.sucursal_id
            AND EXTRACT(YEAR FROM so.fecha_supervision) = 2025
        WHERE s.activo = true AND s.clasificacion = %s
        GROUP BY s.id, s.nombre, s.numero, g.nombre
        ORDER BY prom_operativo DESC NULLS LAST
    ''', (clasificacion,))
    sucs_op = cur.fetchall()

    # Promedio seguridad por sucursal (desempate)
    cur.execute('''
        SELECT
            s.id,
            ROUND(AVG(ss.calificacion_general)::numeric, 2) as prom_seguridad,
            COUNT(ss.id) as total_evals_seg
        FROM sucursales s
        LEFT JOIN supervisiones_seguridad ss ON s.id = ss.sucursal_id
            AND EXTRACT(YEAR FROM ss.fecha_supervision) = 2025
        WHERE s.activo = true AND s.clasificacion = %s
        GROUP BY s.id
    ''', (clasificacion,))
    seg_map = {r['id']: r for r in cur.fetchall()}

    # Combinar
    sucursales = []
    for s in sucs_op:
        seg = seg_map.get(s['id'], {})
        prom_op = float(s['prom_operativo']) if s['prom_operativo'] else 0
        prom_seg = float(seg.get('prom_seguridad') or 0)
        sucursales.append({
            'id': s['id'],
            'nombre': s['nombre'],
            'numero': s['numero'],
            'grupo': s['grupo'],
            'prom_op': prom_op,
            'evals_op': s['total_evals'],
            'prom_seg': prom_seg,
            'evals_seg': seg.get('total_evals_seg', 0),
        })

    # Ordenar: prom_op DESC, desempate prom_seg DESC
    sucursales.sort(key=lambda x: (-x['prom_op'], -x['prom_seg']))

    # Asignar posiciones con empate técnico
    pos = 1
    for i, s in enumerate(sucursales):
        if s['prom_op'] == 0:
            s['pos'] = '-'
        elif i > 0 and s['prom_op'] == sucursales[i-1]['prom_op'] and s['prom_seg'] == sucursales[i-1]['prom_seg']:
            s['pos'] = sucursales[i-1]['pos']
        else:
            s['pos'] = pos
        pos += 1

    header = f"{'Pos':<5} {'Sucursal':<30} {'Grupo':<25} {'Prom Op':>8} {'Prom Seg':>9} {'Evals Op':>9} {'Evals Seg':>10}"
    print(header)
    print("-" * 110)

    evaluadas = 0
    for s in sucursales:
        p = str(s['pos']) if s['pos'] != '-' else 'S/E'
        if s['evals_op'] > 0:
            evaluadas += 1
        print(f"{p:<5} {s['nombre']:<30} {s['grupo']:<25} {s['prom_op']:>7.2f}% {s['prom_seg']:>8.2f}% {s['evals_op']:>9} {s['evals_seg']:>10}")

    total = len(sucursales)
    print(f"\nTotal {tipo_label.lower()}: {total} | Evaluadas: {evaluadas} | Sin evaluar: {total - evaluadas}")
    conn.close()
    return sucursales


if __name__ == '__main__':
    print("\n")
    grupos = ranking_grupos()

    locales = ranking_sucursales('local')
    foraneas = ranking_sucursales('foraneo')

    # Resumen final
    print("\n" + "=" * 100)
    print("  RESUMEN GENERAL 2025")
    print("=" * 100)
    print(f"  Grupos evaluados:     {len([g for g in grupos if g['prom_op'] > 0])}/21")
    print(f"  Sucursales locales:   {len([s for s in locales if s['prom_op'] > 0])}/55 evaluadas")
    print(f"  Sucursales foraneas:  {len([s for s in foraneas if s['prom_op'] > 0])}/31 evaluadas")
    print(f"  Total evaluadas:      {len([s for s in locales if s['prom_op'] > 0]) + len([s for s in foraneas if s['prom_op'] > 0])}/86")
