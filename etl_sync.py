#!/usr/bin/env python3
"""
EPL CAS ETL 2026 - Sincronización Diaria
Extrae supervisiones de Zenput y las carga en PostgreSQL

Ejecutar manualmente: python etl_sync.py
Cron en Railway: 0 12 * * * (6 AM México)
"""

import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# ============================================================
# CONFIGURACIÓN (Variables de entorno en Railway)
# ============================================================

# Sin defaults: correr sin variables NO debe pegarle a producción por accidente.
DATABASE_URL = os.environ.get('DATABASE_URL')
ZENPUT_TOKEN = os.environ.get('ZENPUT_TOKEN')
ZENPUT_BASE = 'https://www.zenput.com/api/v3'

FORMS = {
    'operativas': {'id': 877138, 'tabla': 'supervisiones_operativas'},
    'seguridad': {'id': 877139, 'tabla': 'supervisiones_seguridad'}
}

# ============================================================
# MAPEO DE 29 ÁREAS OPERATIVAS
# ============================================================
AREA_MAP = {
    'PROCESO MARINADO': 'PROCESO_MARINADO',
    'CUARTO FRIO 1': 'CUARTO_FRIO_1',
    'AREA COCINA FRIA/CALIENTE': 'AREA_COCINA',
    'REFRIGERADORES DE SERVICIO': 'REFRIGERADORES_SERVICIO',
    'CUARTO FRIO 2': 'CUARTO_FRIO_2',
    'ALMACEN JARABES': 'ALMACEN_JARABES',
    'ALMACEN GENERAL': 'ALMACEN_GENERAL',
    'CONGELADOR PAPA': 'CONGELADOR_PAPA',
    'MAQUINA DE HIELO': 'MAQUINA_HIELO',
    'BAÑO EMPLEADOS': 'BANO_EMPLEADOS',
    'LAVADO DE UTENSILIOS': 'LAVADO_UTENSILIOS',
    'HORNOS': 'HORNOS',
    'FREIDORA DE PAPA': 'FREIDORA_PAPA',
    'CONSERVADOR PAPA FRITA': 'CONSERVADOR_PAPA',
    'ASADORES': 'ASADORES',
    'BARRA DE SERVICIO': 'BARRA_SERVICIO',
    'COMEDOR AREA COMEDOR': 'COMEDOR',
    'BAÑO CLIENTES': 'BANO_CLIENTES',
    'DISPENSADOR DE REFRESCOS': 'DISPENSADOR_REFRESCOS',
    'BARRA DE SALSAS': 'BARRA_SALSAS',
    'TIEMPOS DE SERVICIO': 'TIEMPOS_SERVICIO',
    'ALMACEN QUÍMICOS': 'ALMACEN_QUIMICOS',
    'AVISO DE FUNCIONAMIENTO, BITACORAS, CARPETA DE FUMIGACION CONTROL': 'DOCUMENTACION',
    'AREA MARINADO': 'AREA_MARINADO',
    'CAJAS DE TOTOPO EMPACADO': 'CAJAS_TOTOPO',
    'PLANCHA Y MESA DE TRABAJO PARA QUESADILLAS Y BURRITOS': 'PLANCHA_MESA',
    'FREIDORAS': 'FREIDORAS',
    'EXTERIOR SUCURSAL': 'EXTERIOR',
}

# Mapeo de 11 KPIs de Seguridad
KPI_MAP = {
    'COMEDOR': 'COMEDOR',
    'ASADORES': 'ASADORES', 
    'AREA MARINADO': 'AREA_MARINADO',
    'BODEGA': 'BODEGA',
    'HORNOS': 'HORNOS',
    'FREIDORAS': 'FREIDORAS',
    'CENTRO DE CARGA': 'CENTRO_CARGA',
    'AZOTEA': 'AZOTEA',
    'EXTERIOR': 'EXTERIOR',
    'PROGRAMA PROTECCION CIVIL': 'PROTECCION_CIVIL',
    'BITACORAS': 'BITACORAS'
}

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

_TIENE_ACTIVA_DESDE = None

def _tiene_activa_desde(cur):
    """¿Existe sucursales.activa_desde_periodo_id? (se agregó 2026-10-06)"""
    global _TIENE_ACTIVA_DESDE
    if _TIENE_ACTIVA_DESDE is None:
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'sucursales' AND column_name = 'activa_desde_periodo_id'
        """)
        _TIENE_ACTIVA_DESDE = cur.fetchone() is not None
    return _TIENE_ACTIVA_DESDE

def resolver_periodo(cur, sucursal_id, tabla, fecha):
    """
    Determina a qué periodo asignar una supervisión nueva.

    Regla de negocio (Roberto, 2026-10-06): el trimestre NO es calendario; es
    una RONDA — cada sucursal recibe una visita por periodo y el periodo activo
    cierra cuando todas las sucursales activas fueron supervisadas (los cortes
    se recorren). Por eso la asignación depende de la sucursal, no de la fecha:

    0. Seguridad: va al mismo periodo que la operativa de la misma visita
       (misma sucursal, ±1 día). Así una visita nunca queda partida.
    1. Sucursal que empieza a contar en un periodo futuro
       (activa_desde_periodo_id) → ese periodo.
    2. Sucursal SIN visita en el periodo activo → periodo activo
       (p. ej. la visita pendiente que cierra la ronda).
    3. Sucursal que YA tiene visita en el periodo activo → siguiente periodo
       en el que aún no tenga visita (ya es la ronda que sigue).
    4. Sin periodo activo → fallback por fecha actual / último periodo.
    """
    # 0. Seguridad pegada a su operativa
    if tabla == 'supervisiones_seguridad' and fecha:
        cur.execute("""
            SELECT periodo_id FROM supervisiones_operativas
            WHERE sucursal_id = %s
              AND ABS(EXTRACT(EPOCH FROM fecha_supervision - %s::timestamp)) <= 86400
            ORDER BY ABS(EXTRACT(EPOCH FROM fecha_supervision - %s::timestamp))
            LIMIT 1
        """, (sucursal_id, fecha, fecha))
        par = cur.fetchone()
        if par and par['periodo_id']:
            return par['periodo_id']

    cur.execute("""
        SELECT id, fecha_inicio FROM periodos_cas
        WHERE activo = true ORDER BY fecha_inicio DESC LIMIT 1
    """)
    activo = cur.fetchone()

    if activo:
        # 1. Sucursal nueva que empieza a contar después del periodo activo
        if _tiene_activa_desde(cur):
            cur.execute("""
                SELECT p.id FROM sucursales s
                JOIN periodos_cas p ON p.id = s.activa_desde_periodo_id
                WHERE s.id = %s AND p.fecha_inicio > %s
            """, (sucursal_id, activo['fecha_inicio']))
            futura = cur.fetchone()
            if futura:
                return futura['id']

        # 2/3. ¿Esta sucursal ya tiene visita en el periodo activo?
        cur.execute(f"""
            SELECT p.id
            FROM periodos_cas p
            WHERE p.fecha_inicio >= %s
              AND NOT EXISTS (SELECT 1 FROM {tabla} t
                              WHERE t.periodo_id = p.id AND t.sucursal_id = %s)
            ORDER BY p.fecha_inicio ASC
            LIMIT 1
        """, (activo['fecha_inicio'], sucursal_id))
        libre = cur.fetchone()
        if libre:
            return libre['id']
        # Ya tiene visita en todos los periodos definidos → último periodo (queda repetida)
        cur.execute("SELECT id, codigo FROM periodos_cas ORDER BY fecha_inicio DESC LIMIT 1")
        ultimo = cur.fetchone()
        log(f"  Sucursal {sucursal_id} ya tiene visita en {ultimo['codigo']} y no hay periodo "
            f"siguiente dado de alta en periodos_cas → queda repetida; crear el periodo que sigue", 'WARN')
        return ultimo['id']

    # 4. Sin periodo activo → fallback por fecha
    cur.execute("""
        SELECT id FROM periodos_cas
        WHERE CURRENT_DATE BETWEEN fecha_inicio AND fecha_fin
        LIMIT 1
    """)
    por_fecha = cur.fetchone()
    if por_fecha:
        return por_fecha['id']

    cur.execute("SELECT id FROM periodos_cas ORDER BY fecha_inicio DESC LIMIT 1")
    ultimo = cur.fetchone()
    return ultimo['id'] if ultimo else None

def log(msg, level='INFO'):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}")

def get_db():
    if not DATABASE_URL:
        raise SystemExit('Falta la variable de entorno DATABASE_URL')
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def fetch_zenput(form_id, after_date=None):
    """Obtiene supervisiones de Zenput API"""
    headers = {'X-API-TOKEN': ZENPUT_TOKEN}
    all_data = []
    offset = 0
    
    while True:
        params = {'form_template_id': form_id, 'limit': 100, 'offset': offset}
        if after_date:
            params['date_submitted_after'] = after_date.isoformat()
        
        try:
            resp = requests.get(f'{ZENPUT_BASE}/submissions/', headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json().get('data', [])
            
            if not data:
                break
            
            all_data.extend(data)
            log(f"  Fetched {len(data)} records (offset={offset})")
            
            if len(data) < 100:
                break
            offset += 100
            
        except Exception as e:
            log(f"Error fetching from Zenput: {e}", 'ERROR')
            break
    
    return all_data

def extract_area_code(title):
    """Extrae el código del área basado en el título"""
    title_clean = title.upper()
    title_clean = title_clean.replace('CALIFICACION', '').replace('CALIFICACIÓN', '')
    title_clean = title_clean.replace('PORCENTAJE', '').replace('%', '').strip()
    
    for key, code in AREA_MAP.items():
        if key == title_clean:
            return code
    
    for key, code in AREA_MAP.items():
        if key in title_clean or title_clean in key:
            return code
    
    if title.strip().upper() in ['PORCENTAJE %', 'PORCENTAJE']:
        return 'CALIFICACION_GENERAL'
    
    return None

def extract_areas(answers):
    """Extrae las 29 áreas"""
    areas = {}
    for ans in answers:
        if ans.get('field_type') != 'formula':
            continue
        title = ans.get('title', '')
        if 'PORCENTAJE' not in title.upper():
            continue
        value = ans.get('value')
        if value is None:
            continue
        
        codigo = extract_area_code(title)
        if codigo and codigo not in areas:
            areas[codigo] = value
    
    return areas

def extract_calificacion_general(answers):
    """Extrae la calificación general"""
    # Buscar en orden de prioridad
    campos_calificacion = [
        'PORCENTAJE %',              # Operativas
        'CALIFICACION PORCENTAJE %'  # Seguridad
    ]

    for ans in answers:
        if ans.get('field_type') != 'formula':
            continue
        title = ans.get('title', '').strip().upper()

        for campo in campos_calificacion:
            if title == campo.upper():
                return ans.get('value')

    return None

def extract_kpis(answers):
    """Extrae los 11 KPIs de seguridad"""
    kpis = {}
    for ans in answers:
        if ans.get('field_type') != 'formula':
            continue
        title = ans.get('title', '').upper()
        value = ans.get('value')
        if value is None:
            continue
        
        for key, code in KPI_MAP.items():
            if f'{key} PORCENTAJE' in title or f'{key} CALIFICACION' in title:
                kpis[code] = value
                break
    return kpis

# ============================================================
# SINCRONIZACIÓN
# ============================================================

def sync_operativas(conn, submissions):
    """Sincroniza supervisiones operativas con sus 29 áreas"""
    cur = conn.cursor()
    nuevos = 0
    areas_insertadas = 0
    
    for sub in submissions:
        meta = sub.get('smetadata', {})
        location = meta.get('location', {})
        
        if not location or not location.get('id'):
            continue
        
        submission_id = str(sub.get('id'))
        
        cur.execute("SELECT id FROM supervisiones_operativas WHERE zenput_submission_id = %s", (submission_id,))
        if cur.fetchone():
            continue
        
        loc_id = location.get('id')
        supervisor = meta.get('created_by', {}).get('display_name', '')
        fecha = meta.get('date_submitted', '')
        lat = meta.get('lat')
        lon = meta.get('lon')
        answers = sub.get('answers', [])
        
        calificacion = extract_calificacion_general(answers)

        # Resolver sucursal_id
        cur.execute("SELECT id FROM sucursales WHERE zenput_location_id = %s", (str(loc_id),))
        sucursal_row = cur.fetchone()
        if not sucursal_row:
            log(f"  Sucursal no encontrada para location_id {loc_id}", 'WARN')
            continue
        sucursal_id = sucursal_row['id']

        # Asignar periodo por ronda (ver resolver_periodo)
        periodo_id = resolver_periodo(cur, sucursal_id, 'supervisiones_operativas', fecha)

        try:
            cur.execute("""
                INSERT INTO supervisiones_operativas
                (zenput_submission_id, sucursal_id, periodo_id, supervisor,
                 fecha_supervision, calificacion_general, lat_entrega, lon_entrega)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (submission_id, sucursal_id, periodo_id, supervisor, fecha, calificacion, lat, lon))
            
            sup_id = cur.fetchone()['id']
            nuevos += 1
            
            areas = extract_areas(answers)
            for codigo, porcentaje in areas.items():
                cur.execute("""
                    INSERT INTO supervision_areas (supervision_id, area_id, porcentaje)
                    SELECT %s, id, %s FROM catalogo_areas WHERE codigo = %s
                    ON CONFLICT DO NOTHING
                """, (sup_id, porcentaje, codigo))
                areas_insertadas += 1
                
        except Exception as e:
            log(f"Error insertando supervisión {submission_id}: {e}", 'ERROR')
            continue
    
    log(f"  → {nuevos} supervisiones nuevas, {areas_insertadas} áreas insertadas")
    return nuevos

def sync_seguridad(conn, submissions):
    """Sincroniza supervisiones de seguridad con sus 11 KPIs"""
    cur = conn.cursor()
    nuevos = 0
    kpis_insertados = 0
    
    for sub in submissions:
        meta = sub.get('smetadata', {})
        location = meta.get('location', {})
        
        submission_id = str(sub.get('id'))
        
        cur.execute("SELECT id FROM supervisiones_seguridad WHERE zenput_submission_id = %s", (submission_id,))
        if cur.fetchone():
            continue
        
        if not location or not location.get('id'):
            fecha_corta = meta.get('date_submitted', '')[:10]
            supervisor = meta.get('created_by', {}).get('display_name', '')
            
            cur.execute("""
                SELECT s.zenput_location_id 
                FROM supervisiones_operativas so
                JOIN sucursales s ON so.sucursal_id = s.id
                WHERE DATE(so.fecha_supervision) = %s AND so.supervisor = %s
                LIMIT 1
            """, (fecha_corta, supervisor))
            match = cur.fetchone()
            if match:
                location = {'id': match['zenput_location_id']}
        
        if not location or not location.get('id'):
            continue
        
        loc_id = location.get('id')
        supervisor = meta.get('created_by', {}).get('display_name', '')
        fecha = meta.get('date_submitted', '')
        answers = sub.get('answers', [])
        
        calificacion = extract_calificacion_general(answers)

        # Resolver sucursal_id
        cur.execute("SELECT id FROM sucursales WHERE zenput_location_id = %s", (str(loc_id),))
        sucursal_row = cur.fetchone()
        if not sucursal_row:
            log(f"  Sucursal no encontrada para location_id {loc_id}", 'WARN')
            continue
        sucursal_id = sucursal_row['id']

        # Asignar periodo por ronda: pegada a la operativa de la misma visita
        periodo_id = resolver_periodo(cur, sucursal_id, 'supervisiones_seguridad', fecha)

        try:
            cur.execute("""
                INSERT INTO supervisiones_seguridad
                (zenput_submission_id, sucursal_id, periodo_id, supervisor,
                 fecha_supervision, calificacion_general)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (submission_id, sucursal_id, periodo_id, supervisor, fecha, calificacion))
            
            sup_id = cur.fetchone()['id']
            nuevos += 1
            
            kpis = extract_kpis(answers)
            for codigo, porcentaje in kpis.items():
                cur.execute("""
                    INSERT INTO seguridad_kpis (supervision_id, kpi_id, porcentaje)
                    SELECT %s, id, %s FROM catalogo_kpis_seguridad WHERE codigo = %s
                    ON CONFLICT DO NOTHING
                """, (sup_id, porcentaje, codigo))
                kpis_insertados += 1
                
        except Exception as e:
            log(f"Error insertando seguridad {submission_id}: {e}", 'ERROR')
            continue
    
    log(f"  → {nuevos} supervisiones nuevas, {kpis_insertados} KPIs insertados")
    return nuevos

def run_sync():
    """Ejecuta sincronización completa"""
    log("=" * 60)
    log("EPL CAS ETL 2026 - Iniciando sincronización")
    log("=" * 60)
    
    with get_db() as conn:
        cur = conn.cursor()
        resultados = {}
        
        for tipo, config in FORMS.items():
            log(f"\n{'='*40}")
            log(f"Procesando: {tipo.upper()}")
            log(f"{'='*40}")
            
            cur.execute("""
                SELECT ultima_fecha FROM sync_checkpoints WHERE formulario = %s
            """, (config['tabla'],))
            checkpoint = cur.fetchone()
            after_date = checkpoint['ultima_fecha'] if checkpoint else None
            
            if after_date:
                log(f"Última sync: {after_date}")
            else:
                log("Primera sincronización")
            
            cur.execute("""
                INSERT INTO sync_log (workflow, inicio, estado)
                VALUES (%s, NOW(), 'running') RETURNING id
            """, (f'etl_{tipo}',))
            log_id = cur.fetchone()['id']
            conn.commit()
            
            try:
                submissions = fetch_zenput(config['id'], after_date)
                log(f"Total obtenidos de Zenput: {len(submissions)}")
                
                if tipo == 'operativas':
                    nuevos = sync_operativas(conn, submissions)
                else:
                    nuevos = sync_seguridad(conn, submissions)
                
                cur.execute("""
                    UPDATE sync_checkpoints SET ultima_fecha = NOW() WHERE formulario = %s
                """, (config['tabla'],))
                
                cur.execute("""
                    UPDATE sync_log SET fin = NOW(), registros_nuevos = %s, estado = 'success'
                    WHERE id = %s
                """, (nuevos, log_id))
                
                conn.commit()
                
                resultados[tipo] = {'nuevos': nuevos, 'total': len(submissions)}
                log(f"✅ {tipo}: {nuevos} nuevos registros")
                
            except Exception as e:
                cur.execute("""
                    UPDATE sync_log SET fin = NOW(), estado = 'error' WHERE id = %s
                """, (log_id,))
                conn.commit()
                log(f"❌ Error: {e}", 'ERROR')
                resultados[tipo] = {'error': str(e)}
                raise  # Re-raise para que Railway detecte el error
        
        # Mostrar totales
        log("\n" + "=" * 60)
        log("ESTADO ACTUAL DE LA BASE DE DATOS")
        log("=" * 60)
        cur.execute("""
            SELECT 'Supervisiones Operativas' as tabla, COUNT(*) as total FROM supervisiones_operativas
            UNION ALL SELECT 'Áreas por Supervisión', COUNT(*) FROM supervision_areas
            UNION ALL SELECT 'Supervisiones Seguridad', COUNT(*) FROM supervisiones_seguridad
            UNION ALL SELECT 'KPIs Seguridad', COUNT(*) FROM seguridad_kpis
        """)
        for row in cur.fetchall():
            log(f"  {row['tabla']}: {row['total']}")

        # Verificar si hay que hacer transición de periodo
        log("\n" + "=" * 60)
        log("VERIFICANDO TRANSICIÓN DE PERIODO")
        log("=" * 60)
        nuevo_periodo = verificar_transicion_periodo(conn)
        if nuevo_periodo:
            resultados['transicion'] = nuevo_periodo

    log("\n" + "=" * 60)
    log("RESUMEN DE SINCRONIZACIÓN")
    log("=" * 60)
    for tipo, res in resultados.items():
        if tipo == 'transicion':
            log(f"  📅 Nuevo periodo activo: {res}")
        elif 'error' in res:
            log(f"  {tipo}: ERROR - {res['error']}", 'ERROR')
        else:
            log(f"  {tipo}: {res['nuevos']} nuevos / {res['total']} procesados")
    log("=" * 60)
    log("✅ ETL completado exitosamente")

    return resultados

# ============================================================
# FIX: Actualizar calificaciones de seguridad existentes
# ============================================================

def fix_seguridad_calificaciones():
    """Re-extrae calificaciones de seguridad desde Zenput para registros con calificacion=0"""
    log("=" * 60)
    log("FIX: Actualizando calificaciones de seguridad")
    log("=" * 60)

    # Obtener todas las submissions de seguridad desde Zenput
    log("Obteniendo submissions de Zenput...")
    submissions = fetch_zenput(FORMS['seguridad']['id'])
    log(f"Total submissions en Zenput: {len(submissions)}")

    # Crear mapa de submission_id -> calificacion
    calificaciones_zenput = {}
    for sub in submissions:
        sub_id = str(sub.get('id'))
        answers = sub.get('answers', [])
        calif = extract_calificacion_general(answers)
        if calif and calif > 0:
            calificaciones_zenput[sub_id] = calif

    log(f"Submissions con calificación válida: {len(calificaciones_zenput)}")

    with get_db() as conn:
        cur = conn.cursor()

        # Obtener supervisiones de seguridad con calificacion 0 o NULL
        cur.execute("""
            SELECT id, zenput_submission_id
            FROM supervisiones_seguridad
            WHERE calificacion_general IS NULL OR calificacion_general = 0
        """)
        registros = cur.fetchall()
        log(f"Registros en BD con calificación 0 o NULL: {len(registros)}")

        actualizados = 0
        for reg in registros:
            sup_id = reg['id']
            zenput_id = reg['zenput_submission_id']

            if zenput_id in calificaciones_zenput:
                calif = calificaciones_zenput[zenput_id]
                cur.execute("""
                    UPDATE supervisiones_seguridad
                    SET calificacion_general = %s
                    WHERE id = %s
                """, (calif, sup_id))
                actualizados += 1
                log(f"  ✓ ID {sup_id}: {calif}%")

        conn.commit()
        log(f"\n✅ Actualizados {actualizados} de {len(registros)} registros")

    return actualizados

# ============================================================
# TRANSICIÓN AUTOMÁTICA DE PERIODO
# ============================================================

def verificar_transicion_periodo(conn):
    """
    Verifica si el periodo activo tiene 86/86 sucursales supervisadas.
    Si es así, automáticamente activa el siguiente periodo.

    Returns:
        str: Código del nuevo periodo si hubo transición, None si no
    """
    cur = conn.cursor()

    # 1. Obtener periodo activo y su progreso (basado en supervisiones operativas)
    cur.execute('''
        SELECT p.id, p.codigo, p.nombre,
               COUNT(DISTINCT so.sucursal_id) as supervisadas,
               (SELECT COUNT(*) FROM sucursales WHERE activo = true) as total
        FROM periodos_cas p
        LEFT JOIN supervisiones_operativas so ON so.periodo_id = p.id
             AND so.sucursal_id IN (SELECT id FROM sucursales WHERE activo = true)
        WHERE p.activo = true
        GROUP BY p.id, p.codigo, p.nombre
    ''')
    activo = cur.fetchone()

    if not activo:
        log("⚠️ No hay periodo activo definido")
        return None

    periodo_codigo = activo['codigo'] or activo['nombre']
    supervisadas = activo['supervisadas'] or 0
    total = activo['total'] or 86

    log(f"Periodo activo: {periodo_codigo} - Progreso: {supervisadas}/{total}")

    # 2. ¿Se completaron todas las sucursales?
    if supervisadas < total:
        log(f"Periodo {periodo_codigo} continúa activo ({total - supervisadas} sucursales pendientes)")
        return None

    # 3. ¡Completado! Buscar siguiente periodo por fecha
    cur.execute('''
        SELECT id, codigo, nombre FROM periodos_cas
        WHERE fecha_inicio > (SELECT fecha_inicio FROM periodos_cas WHERE id = %s)
        ORDER BY fecha_inicio ASC
        LIMIT 1
    ''', (activo['id'],))
    siguiente = cur.fetchone()

    if not siguiente:
        log(f"✅ Periodo {periodo_codigo} COMPLETADO - No hay siguiente periodo definido")
        return None

    siguiente_codigo = siguiente['codigo'] or siguiente['nombre']

    # 4. Ejecutar la transición
    cur.execute("UPDATE periodos_cas SET activo = false WHERE id = %s", (activo['id'],))
    cur.execute("UPDATE periodos_cas SET activo = true WHERE id = %s", (siguiente['id'],))
    # Sucursales nuevas que empiezan a contar en este periodo (p. ej. Linares en Q4-2026)
    if _tiene_activa_desde(cur):
        cur.execute("""
            UPDATE sucursales SET activo = true
            WHERE activa_desde_periodo_id = %s AND activo = false
            RETURNING nombre
        """, (siguiente['id'],))
        for r in cur.fetchall():
            log(f"   Sucursal activada para {siguiente['codigo'] or siguiente['nombre']}: {r['nombre']}")
    conn.commit()

    log("=" * 60)
    log(f"🔄 TRANSICIÓN AUTOMÁTICA DE PERIODO")
    log(f"   {periodo_codigo} (COMPLETADO) → {siguiente_codigo} (ACTIVO)")
    log("=" * 60)

    return siguiente_codigo

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--fix-seguridad':
        fix_seguridad_calificaciones()
    else:
        run_sync()
