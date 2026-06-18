"""
EPL CAS 2026 Dashboard - Flask Application
Dashboard completo para supervisiones CAS con estilo iOS
"""

import os
from functools import wraps
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from dotenv import load_dotenv
from datetime import datetime, date

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'epl-cas-2026-rdg-secret')

# Configuración de base de datos
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '20Bube85!21637543')

# ============ HELPERS ============
def get_color_class(value):
    """Retorna clase de color según rendimiento"""
    if value is None:
        return 'gray'
    if value >= 90:
        return 'excellent'
    if value >= 80:
        return 'good'
    if value >= 70:
        return 'regular'
    return 'critical'

def get_territorio(grupo_nombre):
    """Determina territorio del grupo"""
    locales = ['TEPEYAC', 'OGAS', 'EFM', 'EPL SO', 'PLOG NUEVO LEON', 'GRUPO CENTRITO', 'GRUPO SABINAS HIDALGO', 'GRUPO CADE']
    mixtos = ['TEC', 'EXPO', 'GRUPO SALTILLO']

    for local in locales:
        if local.lower() in grupo_nombre.lower():
            return 'local'
    for mixto in mixtos:
        if mixto.lower() in grupo_nombre.lower():
            return 'mixto'
    return 'foranea'

# Configuración de agrupaciones de grupos operativos
GRUPOS_AGRUPACIONES = {
    'PLOG': {
        'nombre': 'PLOG',
        'patron': 'PLOG %'  # SQL LIKE pattern
    }
}

def _anio_actual():
    """
    Año en curso para el dashboard. Prioridad:
    1) año del periodo marcado activo, 2) año más reciente con periodos,
    3) año de hoy. Nunca devuelve None. Define el alcance del "Acumulado del Año"
    (M3) para que NUNCA se mezclen años (evita arrastrar 2025).
    """
    try:
        row = db.session.execute(text("""
            SELECT EXTRACT(YEAR FROM fecha_inicio)::int
            FROM periodos_cas WHERE activo = true
            ORDER BY fecha_inicio DESC LIMIT 1
        """)).fetchone()
        if row and row[0]:
            return int(row[0])
        row = db.session.execute(text("""
            SELECT MAX(EXTRACT(YEAR FROM fecha_inicio))::int FROM periodos_cas
        """)).fetchone()
        if row and row[0]:
            return int(row[0])
    except Exception:
        pass
    return date.today().year


def _score_cte(tabla, con_periodo, anio=None):
    """
    CTE 'ult' = calificación por sucursal dentro del alcance. SIEMPRE acotada a un
    alcance temporal — nunca "toda la historia" (eso mezclaba 2025 y era la causa
    de "no se mueve").

    - con_periodo=True  -> solo el trimestre :periodo_id  (M1 Calificación del Trimestre)
    - con_periodo=False -> "Acumulado del Año": todos los trimestres del año `anio`
                           (M3). `anio` es un int controlado por el servidor
                           (de _anio_actual), se inyecta directo — no es input del
                           usuario, sin riesgo de inyección.

    El % de una sucursal en el alcance = PROMEDIO de sus supervisiones (si hay
    re-supervisión correctiva, promedia todas). Los % de grupo promedian estos
    scores con peso igual por sucursal. Solo cuenta sucursales ACTIVAS (evita el
    fantasma 87/86). Ver docs/MARCO-METRICAS-CAS.md.
    """
    if con_periodo:
        join = ""
        filtro = "WHERE so.periodo_id = :periodo_id"
    else:
        anio_val = int(anio) if anio else date.today().year
        join = "JOIN periodos_cas p ON so.periodo_id = p.id"
        filtro = f"WHERE EXTRACT(YEAR FROM p.fecha_inicio) = {anio_val}"
    return f"""
        ult AS (
            SELECT so.sucursal_id,
                   AVG(so.calificacion_general) AS calificacion_general
            FROM {tabla} so
            JOIN sucursales sa ON sa.id = so.sucursal_id AND sa.activo = true
            {join}
            {filtro}
            GROUP BY so.sucursal_id
        )
    """

# ============ DECORADORES ============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ============ RUTAS PRINCIPALES ============
@app.route('/')
def index():
    """Página principal del dashboard"""
    return render_template('index.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Login del panel de administración"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        return render_template('admin_login.html', error='Contraseña incorrecta')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Cerrar sesión de admin"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    """Panel de administración"""
    try:
        # Asegurar que existe la columna activo en periodos_cas
        try:
            db.session.execute(text("""
                ALTER TABLE periodos_cas ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT false
            """))
            db.session.commit()
        except:
            db.session.rollback()

        total_op = db.session.execute(text("SELECT COUNT(*) FROM supervisiones_operativas")).scalar() or 0
        total_seg = db.session.execute(text("SELECT COUNT(*) FROM supervisiones_seguridad")).scalar() or 0
        total_sucursales = db.session.execute(text("SELECT COUNT(*) FROM sucursales WHERE activo = true")).scalar() or 0
        total_grupos = db.session.execute(text("SELECT COUNT(*) FROM grupos_operativos WHERE activo = true")).scalar() or 0

        result = db.session.execute(text("""
            SELECT id, codigo, nombre, fecha_inicio, fecha_fin,
                   COALESCE(activo, false) as activo
            FROM periodos_cas ORDER BY fecha_inicio DESC
        """))
        periodos = [{'id': r[0], 'codigo': r[1], 'nombre': r[2],
                     'fecha_inicio': str(r[3]) if r[3] else '',
                     'fecha_fin': str(r[4]) if r[4] else '',
                     'activo': r[5]} for r in result]

        periodo_activo_id = None
        result = db.session.execute(text("SELECT id FROM periodos_cas WHERE activo = true ORDER BY fecha_inicio DESC LIMIT 1"))
        row = result.fetchone()
        if row:
            periodo_activo_id = row[0]

        return render_template('admin.html', total_op=total_op, total_seg=total_seg,
            total_sucursales=total_sucursales, total_grupos=total_grupos,
            periodos=periodos, periodo_activo_id=periodo_activo_id)
    except Exception as e:
        return render_template('admin.html', total_op=0, total_seg=0,
            total_sucursales=0, total_grupos=0, periodos=[], periodo_activo_id=None, error=str(e))

@app.route('/admin/set-periodo', methods=['POST'])
@login_required
def admin_set_periodo():
    """Establecer el periodo activo"""
    try:
        periodo_id = request.form.get('periodo_id')
        if not periodo_id:
            return redirect(url_for('admin'))

        # Desactivar todos los periodos
        db.session.execute(text("UPDATE periodos_cas SET activo = false"))
        # Activar el seleccionado
        db.session.execute(text("UPDATE periodos_cas SET activo = true WHERE id = :id"), {'id': periodo_id})
        db.session.commit()

        return redirect(url_for('admin'))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for('admin'))

@app.route('/admin/update-periodo', methods=['POST'])
@login_required
def admin_update_periodo():
    """Actualizar fechas de un periodo"""
    try:
        periodo_id = request.form.get('periodo_id')
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')

        if not periodo_id:
            return jsonify({'success': False, 'error': 'ID requerido'}), 400

        # Actualizar fechas
        db.session.execute(text("""
            UPDATE periodos_cas
            SET fecha_inicio = :fecha_inicio, fecha_fin = :fecha_fin
            WHERE id = :id
        """), {'id': periodo_id, 'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin})
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ENDPOINTS - PERIODO CONTEXTO ============
@app.route('/api/periodo-contexto/<tipo>')
def api_periodo_contexto(tipo):
    """Obtener contexto del periodo actual para el dashboard"""
    try:
        from datetime import date
        hoy = date.today()
        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        # 1. Buscar periodo activo (prioridad: activo incompleto > fecha > activo > último con datos)
        periodo_actual = None

        # Primero: si hay un periodo marcado activo que NO tiene 86/86, mantenerlo
        # (regla de cierre POR CONTEO, no por fecha). Solo cuenta sucursales ACTIVAS.
        result = db.session.execute(text(f"""
            SELECT p.id, p.codigo, p.nombre, p.fecha_inicio, p.fecha_fin,
                   COUNT(DISTINCT sa.id) as supervisadas,
                   (SELECT COUNT(*) FROM sucursales WHERE activo = true) as total
            FROM periodos_cas p
            LEFT JOIN {tabla} s ON s.periodo_id = p.id
            LEFT JOIN sucursales sa ON sa.id = s.sucursal_id AND sa.activo = true
            WHERE p.activo = true
            GROUP BY p.id, p.codigo, p.nombre, p.fecha_inicio, p.fecha_fin
            ORDER BY p.fecha_inicio DESC LIMIT 1
        """))
        row = result.fetchone()

        if row and (row[5] or 0) < (row[6] or 86):
            periodo_actual = {
                'id': row[0], 'codigo': row[1], 'nombre': row[2],
                'fecha_inicio': str(row[3]), 'fecha_fin': str(row[4]),
                'metodo': 'activo_incompleto'
            }

        # Si el activo ya tiene 86/86 o no tiene datos, buscar por fecha
        if not periodo_actual:
            result = db.session.execute(text("""
                SELECT id, codigo, nombre, fecha_inicio, fecha_fin
                FROM periodos_cas
                WHERE fecha_inicio <= :hoy AND fecha_fin >= :hoy
                ORDER BY fecha_inicio DESC LIMIT 1
            """), {'hoy': hoy})
            row = result.fetchone()

            if row:
                periodo_actual = {
                    'id': row[0], 'codigo': row[1], 'nombre': row[2],
                    'fecha_inicio': str(row[3]), 'fecha_fin': str(row[4]),
                    'metodo': 'fecha'
                }

        if not periodo_actual:
            # Fallback: periodo marcado como activo (sin filtro de progreso)
            result = db.session.execute(text("""
                SELECT id, codigo, nombre, fecha_inicio, fecha_fin
                FROM periodos_cas WHERE activo = true
                ORDER BY fecha_inicio DESC LIMIT 1
            """))
            row = result.fetchone()
            if row:
                periodo_actual = {
                    'id': row[0], 'codigo': row[1], 'nombre': row[2],
                    'fecha_inicio': str(row[3]), 'fecha_fin': str(row[4]),
                    'metodo': 'activo'
                }

        if not periodo_actual:
            # Fallback final: último periodo con datos
            result = db.session.execute(text(f"""
                SELECT p.id, p.codigo, p.nombre, p.fecha_inicio, p.fecha_fin
                FROM periodos_cas p
                JOIN {tabla} s ON s.periodo_id = p.id
                GROUP BY p.id, p.codigo, p.nombre, p.fecha_inicio, p.fecha_fin
                ORDER BY p.fecha_inicio DESC LIMIT 1
            """))
            row = result.fetchone()
            if row:
                periodo_actual = {
                    'id': row[0], 'codigo': row[1], 'nombre': row[2],
                    'fecha_inicio': str(row[3]), 'fecha_fin': str(row[4]),
                    'metodo': 'ultimo_con_datos'
                }

        # 2. Lista de periodos para el selector = solo trimestres del AÑO EN CURSO
        # (no 2025). El año se toma del periodo actual; fallback al año más reciente.
        anio_sel = None
        if periodo_actual and periodo_actual.get('fecha_inicio'):
            try:
                anio_sel = int(str(periodo_actual['fecha_inicio'])[:4])
            except (ValueError, TypeError):
                anio_sel = None
        if not anio_sel:
            anio_sel = _anio_actual()
        result = db.session.execute(text("""
            SELECT id, codigo, nombre, fecha_inicio, fecha_fin
            FROM periodos_cas
            WHERE EXTRACT(YEAR FROM fecha_inicio) = :anio
            ORDER BY fecha_inicio DESC
        """), {'anio': anio_sel})
        periodos = [{'id': r[0], 'codigo': r[1], 'nombre': r[2],
                     'fecha_inicio': str(r[3]) if r[3] else '',
                     'fecha_fin': str(r[4]) if r[4] else ''} for r in result]

        # 3. Progreso de sucursales (usa periodo_id del query param si viene, si no el actual)
        progreso_periodo_id = request.args.get('periodo_id') or (periodo_actual['id'] if periodo_actual else None)
        progreso = {'supervisadas': 0, 'total': 86, 'porcentaje': 0}
        if progreso_periodo_id:
            result = db.session.execute(text(f"""
                SELECT COUNT(DISTINCT so.sucursal_id) FROM {tabla} so
                JOIN sucursales sa ON sa.id = so.sucursal_id AND sa.activo = true
                WHERE so.periodo_id = :periodo_id
            """), {'periodo_id': progreso_periodo_id})
            supervisadas = result.scalar() or 0

            result = db.session.execute(text("SELECT COUNT(*) FROM sucursales WHERE activo = true"))
            total = result.scalar() or 86

            progreso = {
                'supervisadas': supervisadas,
                'total': total,
                'porcentaje': round((supervisadas / total * 100) if total > 0 else 0, 1)
            }

        return jsonify({
            'success': True,
            'data': {
                'periodo_actual': periodo_actual,
                'periodos': periodos,
                'progreso': progreso
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ENDPOINTS - DATOS BÁSICOS ============
@app.route('/api/periodos')
def api_periodos():
    """Obtener todos los periodos CAS"""
    try:
        result = db.session.execute(text("SELECT * FROM periodos_cas ORDER BY id DESC LIMIT 10"))
        columns = result.keys()
        periodos = []
        for row in result:
            periodo = {}
            for i, col in enumerate(columns):
                val = row[i]
                if val is not None:
                    periodo[col] = str(val) if hasattr(val, 'isoformat') else val
                else:
                    periodo[col] = None
            periodos.append(periodo)
        return jsonify({'success': True, 'data': periodos, 'columns': list(columns)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/estados')
def api_estados():
    """Obtener lista de estados con sucursales"""
    try:
        result = db.session.execute(text("""
            SELECT DISTINCT estado, COUNT(*) as total
            FROM sucursales WHERE activo = true AND estado IS NOT NULL
            GROUP BY estado ORDER BY estado
        """))
        estados = [{'nombre': row[0], 'total': row[1]} for row in result]
        return jsonify({'success': True, 'data': estados})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ENDPOINTS - KPIs DASHBOARD ============
@app.route('/api/kpis/<tipo>')
def api_kpis(tipo):
    """KPIs principales del dashboard"""
    try:
        periodo_id = request.args.get('periodo_id')
        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        params = {}
        params_periodo = {}

        anio = _anio_actual()
        con_periodo = bool(periodo_id and periodo_id != 'all')

        # Promedio del periodo = promedio de la ÚLTIMA evaluación de cada sucursal
        if con_periodo:
            params_periodo['periodo_id'] = periodo_id
            query_prom = f"WITH {_score_cte(tabla, True)} SELECT AVG(calificacion_general) FROM ult"
            promedio_periodo = db.session.execute(text(query_prom), params_periodo).scalar()
        else:
            promedio_periodo = None

        # "Acumulado del Año": promedio del AÑO EN CURSO (no toda la historia, no 2025).
        query_acum = f"WITH {_score_cte(tabla, False, anio)} SELECT AVG(calificacion_general) FROM ult"
        promedio_acumulado = db.session.execute(text(query_acum)).scalar() or 0

        # Total supervisiones (acotado al alcance: trimestre, o año en curso)
        if con_periodo:
            query_total = f"SELECT COUNT(*) FROM {tabla} WHERE periodo_id = :periodo_id"
            total_supervisiones = db.session.execute(text(query_total), params_periodo).scalar() or 0
        else:
            query_total = f"""
                SELECT COUNT(*) FROM {tabla} so
                JOIN periodos_cas p ON so.periodo_id = p.id
                JOIN sucursales sa ON sa.id = so.sucursal_id AND sa.activo = true
                WHERE EXTRACT(YEAR FROM p.fecha_inicio) = {int(anio)}
            """
            total_supervisiones = db.session.execute(text(query_total)).scalar() or 0

        # Sucursales supervisadas (avance) — solo ACTIVAS, en el alcance
        if con_periodo:
            query_suc = f"""
                SELECT COUNT(DISTINCT so.sucursal_id) FROM {tabla} so
                JOIN sucursales sa ON sa.id = so.sucursal_id AND sa.activo = true
                WHERE so.periodo_id = :periodo_id
            """
            sucursales_supervisadas = db.session.execute(text(query_suc), params_periodo).scalar() or 0
        else:
            query_suc = f"""
                SELECT COUNT(DISTINCT so.sucursal_id) FROM {tabla} so
                JOIN periodos_cas p ON so.periodo_id = p.id
                JOIN sucursales sa ON sa.id = so.sucursal_id AND sa.activo = true
                WHERE EXTRACT(YEAR FROM p.fecha_inicio) = {int(anio)}
            """
            sucursales_supervisadas = db.session.execute(text(query_suc)).scalar() or 0

        # Total sucursales
        total_sucursales = db.session.execute(text("SELECT COUNT(*) FROM sucursales WHERE activo = true")).scalar() or 0

        # Total grupos
        total_grupos = db.session.execute(text("SELECT COUNT(*) FROM grupos_operativos WHERE activo = true")).scalar() or 0

        # Avance del trimestre / año = sucursales revisadas / activas (nunca > 100%)
        cobertura = round((sucursales_supervisadas / total_sucursales * 100) if total_sucursales > 0 else 0, 1)

        # Distribución por rendimiento (cuenta cada sucursal una vez, por su última eval)
        query_dist = f"""
            WITH {_score_cte(tabla, con_periodo, anio)}
            SELECT
                SUM(CASE WHEN calificacion_general >= 90 THEN 1 ELSE 0 END) as excelente,
                SUM(CASE WHEN calificacion_general >= 80 AND calificacion_general < 90 THEN 1 ELSE 0 END) as bueno,
                SUM(CASE WHEN calificacion_general >= 70 AND calificacion_general < 80 THEN 1 ELSE 0 END) as regular,
                SUM(CASE WHEN calificacion_general < 70 THEN 1 ELSE 0 END) as critico
            FROM ult
        """
        if con_periodo:
            dist_result = db.session.execute(text(query_dist), params_periodo).fetchone()
        else:
            dist_result = db.session.execute(text(query_dist)).fetchone()

        distribucion = {
            'excelente': dist_result[0] or 0,
            'bueno': dist_result[1] or 0,
            'regular': dist_result[2] or 0,
            'critico': dist_result[3] or 0
        }

        # Promedio a mostrar: si hay periodo seleccionado se muestra el del periodo
        # (aunque sea None = sin datos en el periodo); solo en modo "Todos" se usa el acumulado.
        # No hay fallback silencioso periodo->acumulado (causaba el "no se mueve").
        promedio_mostrar = promedio_periodo if con_periodo else promedio_acumulado

        return jsonify({
            'success': True,
            'data': {
                'promedio': float(round(promedio_mostrar, 2)) if promedio_mostrar is not None else None,
                'promedio_periodo': float(round(promedio_periodo, 2)) if promedio_periodo is not None else None,
                'promedio_acumulado': float(round(promedio_acumulado, 2)),
                'anio': int(anio),
                'nombre_acumulado': f'Acumulado del Año {anio}',
                'color': get_color_class(promedio_mostrar),
                'total_supervisiones': int(total_supervisiones),
                'sucursales_supervisadas': int(sucursales_supervisadas),
                'total_sucursales': int(total_sucursales),
                'total_grupos': int(total_grupos),
                'cobertura': float(cobertura),
                'distribucion': {
                    'excelente': int(distribucion['excelente']),
                    'bueno': int(distribucion['bueno']),
                    'regular': int(distribucion['regular']),
                    'critico': int(distribucion['critico'])
                }
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ENDPOINTS - RANKINGS ============
@app.route('/api/ranking/grupos/<tipo>')
def api_ranking_grupos(tipo):
    """Ranking de grupos operativos - con empates y agrupaciones"""
    try:
        periodo_id = request.args.get('periodo_id')
        territorio = request.args.get('territorio')  # local, foranea, mixto, todas

        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        # Query que incluye todos los grupos.
        # promedio = promedio de la última eval de cada sucursal del grupo.
        # total_supervisiones aquí = nº de sucursales con evaluación (denominador del promedio).
        anio = _anio_actual()
        con_periodo = bool(periodo_id and periodo_id != 'all')
        query = f"""
            WITH {_score_cte(tabla, con_periodo, anio)}
            SELECT g.id, g.nombre,
                   AVG(u.calificacion_general) as promedio,
                   COUNT(DISTINCT s.id) as total_sucursales,
                   COUNT(u.sucursal_id) as total_supervisiones
            FROM grupos_operativos g
            LEFT JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true
            LEFT JOIN ult u ON u.sucursal_id = s.id
            WHERE g.activo = true
            GROUP BY g.id, g.nombre
            ORDER BY promedio DESC NULLS LAST, g.nombre ASC
        """
        params = {'periodo_id': periodo_id} if con_periodo else {}

        result = db.session.execute(text(query), params)
        rows = list(result)

        # Identificar grupos que pertenecen a agrupaciones
        grupos_agrupados = {}  # {key_agrupacion: [grupos]}
        grupos_independientes = []

        for row in rows:
            grupo_nombre = row[1]
            grupo_territorio = get_territorio(grupo_nombre)

            # Filtrar por territorio si se especifica
            if territorio and territorio != 'todas':
                if territorio == 'local' and grupo_territorio not in ['local', 'mixto']:
                    continue
                if territorio == 'foranea' and grupo_territorio not in ['foranea', 'mixto']:
                    continue
                if territorio == 'mixto' and grupo_territorio != 'mixto':
                    continue

            item = {
                'id': row[0],
                'nombre': row[1],
                'promedio': round(float(row[2]), 2) if row[2] else None,
                'total_sucursales': row[3],
                'total_supervisiones': row[4],
                'territorio': grupo_territorio,
                'tipo': 'grupo'
            }

            # Verificar si pertenece a alguna agrupación
            es_agrupado = False
            for key, config in GRUPOS_AGRUPACIONES.items():
                patron_check = config['patron'].replace('%', '').strip()
                if grupo_nombre.upper().startswith(patron_check):
                    if key not in grupos_agrupados:
                        grupos_agrupados[key] = []
                    grupos_agrupados[key].append(item)
                    es_agrupado = True
                    break

            if not es_agrupado:
                grupos_independientes.append(item)

        # Construir agrupaciones con sus promedios calculados correctamente
        agrupaciones_items = []
        for key, config in GRUPOS_AGRUPACIONES.items():
            if key not in grupos_agrupados or len(grupos_agrupados[key]) == 0:
                continue

            grupos_en_agrupacion = grupos_agrupados[key]

            # Agrupación JERÁRQUICA (decidida 2026-06-18): el score de la
            # agrupación = promedio simple de los scores de sus subgrupos
            # (cada subgrupo pesa igual sin importar su nº de sucursales).
            # Subgrupo sin datos en el periodo -> excluido del promedio.
            # Ver docs/MARCO-METRICAS-CAS.md §3.
            proms_subgrupos = [g['promedio'] for g in grupos_en_agrupacion if g['promedio'] is not None]
            if proms_subgrupos:
                promedio_agrup = round(sum(proms_subgrupos) / len(proms_subgrupos), 2)
                total_grupos = len(proms_subgrupos)
            else:
                promedio_agrup = None
                total_grupos = len(grupos_en_agrupacion)

            # total_supervisiones aquí = nº de sucursales evaluadas en la agrupación
            total_supervisiones = sum((g['total_supervisiones'] or 0) for g in grupos_en_agrupacion)
            total_sucursales = sum((g['total_sucursales'] or 0) for g in grupos_en_agrupacion)

            # Ordenar grupos dentro de la agrupación por promedio
            grupos_ordenados = sorted(
                grupos_en_agrupacion,
                key=lambda x: (x['promedio'] is None, -(x['promedio'] or 0))
            )

            # Asignar posiciones internas a grupos
            pos_interna = 1
            prev_prom = None
            for g in grupos_ordenados:
                if g['promedio'] is not None:
                    if prev_prom is not None and g['promedio'] == prev_prom:
                        g['posicion_interna'] = grupos_ordenados[grupos_ordenados.index(g) - 1].get('posicion_interna', pos_interna)
                    else:
                        g['posicion_interna'] = pos_interna
                    g['color'] = get_color_class(g['promedio'])
                    prev_prom = g['promedio']
                    pos_interna += 1
                else:
                    g['posicion_interna'] = None
                    g['color'] = 'gray'

            agrupacion_item = {
                'tipo': 'agrupacion',
                'id': f'agrupacion-{key}',
                'key': key,
                'nombre': config['nombre'],
                'promedio': promedio_agrup,
                'color': get_color_class(promedio_agrup) if promedio_agrup else 'gray',
                'total_grupos': total_grupos,
                'total_sucursales': total_sucursales,
                'total_supervisiones': total_supervisiones,
                'grupos': grupos_ordenados
            }
            agrupaciones_items.append(agrupacion_item)

        # Combinar agrupaciones + grupos independientes
        todos_items = agrupaciones_items + grupos_independientes

        # Separar con y sin supervisiones para ranking global
        con_supervisiones = []
        sin_supervisiones = []

        for item in todos_items:
            if item['tipo'] == 'agrupacion':
                if item['total_supervisiones'] > 0 and item['promedio'] is not None:
                    con_supervisiones.append(item)
                else:
                    sin_supervisiones.append(item)
            else:
                if item['total_supervisiones'] > 0 and item['promedio'] is not None:
                    con_supervisiones.append(item)
                else:
                    sin_supervisiones.append(item)

        # Ordenar por promedio
        con_supervisiones.sort(key=lambda x: -(x['promedio'] or 0))

        # Asignar posiciones globales con empates
        ranking = []
        pos = 1
        prev_promedio = None
        for item in con_supervisiones:
            if prev_promedio is not None and item['promedio'] == prev_promedio:
                item['posicion'] = ranking[-1]['posicion']
            else:
                item['posicion'] = pos

            if item['tipo'] != 'agrupacion':
                item['color'] = get_color_class(item['promedio'])
            ranking.append(item)
            prev_promedio = item['promedio']
            pos += 1

        # Agregar items sin supervisiones al final
        for item in sin_supervisiones:
            item['posicion'] = None
            if item['tipo'] != 'agrupacion':
                item['color'] = 'gray'
                item['promedio'] = None
            ranking.append(item)

        return jsonify({'success': True, 'data': ranking})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ranking/sucursales/<tipo>')
def api_ranking_sucursales(tipo):
    """Ranking de sucursales - incluye todas las 86, con empates"""
    try:
        periodo_id = request.args.get('periodo_id')
        grupo_id = request.args.get('grupo_id')
        territorio = request.args.get('territorio')  # local, foranea

        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        # Query que incluye TODAS las sucursales.
        # promedio = ÚLTIMA evaluación de la sucursal en el alcance (no promedio de todas).
        anio = _anio_actual()
        con_periodo = bool(periodo_id and periodo_id != 'all')
        cnt_filtro = "AND x.periodo_id = :periodo_id" if con_periodo else f"AND x.periodo_id IN (SELECT id FROM periodos_cas WHERE EXTRACT(YEAR FROM fecha_inicio) = {int(anio)})"
        query = f"""
            WITH {_score_cte(tabla, con_periodo, anio)}
            SELECT s.id, s.nombre, g.nombre as grupo_nombre, g.id as grupo_id,
                   s.clasificacion,
                   u.calificacion_general as promedio,
                   (SELECT COUNT(*) FROM {tabla} x
                      WHERE x.sucursal_id = s.id {cnt_filtro}) as total_supervisiones
            FROM sucursales s
            LEFT JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
            LEFT JOIN ult u ON u.sucursal_id = s.id
            WHERE s.activo = true
        """

        params = {}
        if con_periodo:
            params['periodo_id'] = periodo_id

        if grupo_id:
            query += " AND s.grupo_operativo_id = :grupo_id"
            params['grupo_id'] = grupo_id

        # Filtro por territorio (clasificacion de sucursal)
        if territorio and territorio != 'todas':
            if territorio == 'local':
                query += " AND s.clasificacion = 'local'"
            elif territorio == 'foranea':
                query += " AND s.clasificacion = 'foraneo'"

        query += " ORDER BY promedio DESC NULLS LAST, s.nombre ASC"

        result = db.session.execute(text(query), params)
        rows = list(result)

        # Separar supervisadas de pendientes
        supervisadas = []
        pendientes = []

        for row in rows:
            item = {
                'id': row[0],
                'nombre': row[1],
                'grupo_nombre': row[2],
                'grupo_id': row[3],
                'clasificacion': row[4] or 'local',
                'promedio': round(float(row[5]), 2) if row[5] else None,
                'total_supervisiones': row[6]
            }
            if row[6] > 0 and row[5] is not None:
                supervisadas.append(item)
            else:
                pendientes.append(item)

        # Asignar posiciones con empates para supervisadas
        ranking = []
        pos = 1
        prev_promedio = None
        for i, item in enumerate(supervisadas):
            if prev_promedio is not None and item['promedio'] == prev_promedio:
                # Empate - misma posición
                item['posicion'] = ranking[-1]['posicion']
            else:
                item['posicion'] = pos

            item['color'] = get_color_class(item['promedio'])
            ranking.append(item)
            prev_promedio = item['promedio']
            pos += 1

        # Agregar pendientes al final (sin posición)
        for item in pendientes:
            item['posicion'] = None
            item['color'] = 'gray'
            item['promedio'] = None
            ranking.append(item)

        return jsonify({'success': True, 'data': ranking})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ENDPOINTS - DRILL-DOWNS ============
@app.route('/api/grupo/<int:grupo_id>/<tipo>')
def api_grupo_detalle(grupo_id, tipo):
    """Detalle de un grupo operativo"""
    try:
        periodo_id = request.args.get('periodo_id')
        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        # Info del grupo
        grupo = db.session.execute(text("""
            SELECT id, nombre FROM grupos_operativos WHERE id = :id
        """), {'id': grupo_id}).fetchone()

        if not grupo:
            return jsonify({'success': False, 'error': 'Grupo no encontrado'}), 404

        # con_periodo: evita el bug de comparar periodo_id = 'all' contra un int
        anio = _anio_actual()
        con_periodo = bool(periodo_id and periodo_id != 'all')
        params = {'grupo_id': grupo_id}
        if con_periodo:
            params['periodo_id'] = periodo_id

        # Promedio del grupo = promedio de la última eval de cada sucursal
        query_prom = f"""
            WITH {_score_cte(tabla, con_periodo, anio)}
            SELECT AVG(u.calificacion_general)
            FROM ult u
            JOIN sucursales s ON u.sucursal_id = s.id
            WHERE s.grupo_operativo_id = :grupo_id
        """
        promedio = db.session.execute(text(query_prom), params).scalar() or 0

        # Sucursales del grupo (cada una con su última eval del alcance)
        cnt_filtro = "AND x.periodo_id = :periodo_id" if con_periodo else f"AND x.periodo_id IN (SELECT id FROM periodos_cas WHERE EXTRACT(YEAR FROM fecha_inicio) = {int(anio)})"
        query_suc = f"""
            WITH {_score_cte(tabla, con_periodo, anio)}
            SELECT s.id, s.nombre,
                   COALESCE(u.calificacion_general, 0) as promedio,
                   (SELECT COUNT(*) FROM {tabla} x
                      WHERE x.sucursal_id = s.id {cnt_filtro}) as supervisiones
            FROM sucursales s
            LEFT JOIN ult u ON u.sucursal_id = s.id
            WHERE s.grupo_operativo_id = :grupo_id AND s.activo = true
            ORDER BY promedio DESC
        """

        result = db.session.execute(text(query_suc), params)
        sucursales = []
        for row in result:
            sucursales.append({
                'id': row[0], 'nombre': row[1],
                'promedio': round(float(row[2]), 2),
                'color': get_color_class(float(row[2])),
                'supervisiones': row[3]
            })

        return jsonify({
            'success': True,
            'data': {
                'grupo': {'id': grupo[0], 'nombre': grupo[1]},
                'promedio': round(promedio, 2),
                'color': get_color_class(promedio),
                'total_sucursales': len(sucursales),
                'total_supervisiones': sum(s['supervisiones'] for s in sucursales),
                'sucursales': sucursales
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sucursal/<int:sucursal_id>/<tipo>')
def api_sucursal_detalle(sucursal_id, tipo):
    """Detalle de una sucursal con áreas/KPIs"""
    try:
        periodo_id = request.args.get('periodo_id')

        # Info de la sucursal (usando columnas correctas)
        suc = db.session.execute(text("""
            SELECT s.id, s.nombre, s.numero, s.estado, s.ciudad,
                   g.nombre as grupo_nombre, g.id as grupo_id
            FROM sucursales s
            LEFT JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
            WHERE s.id = :id
        """), {'id': sucursal_id}).fetchone()

        if not suc:
            return jsonify({'success': False, 'error': 'Sucursal no encontrada'}), 404

        areas = []
        promedio = 0
        sup = None

        if tipo == 'operativas':
            # Supervisiones operativas con áreas
            query = """
                SELECT so.id, so.calificacion_general, so.fecha_supervision, so.supervisor
                FROM supervisiones_operativas so
                WHERE so.sucursal_id = :sucursal_id
            """
            params = {'sucursal_id': sucursal_id}
            if periodo_id and periodo_id != 'all':
                query += " AND so.periodo_id = :periodo_id"
                params['periodo_id'] = periodo_id
            query += " ORDER BY so.fecha_supervision DESC LIMIT 1"

            sup = db.session.execute(text(query), params).fetchone()

            if sup:
                promedio = float(sup[1]) if sup[1] else 0
                # Obtener áreas de la supervisión
                areas_result = db.session.execute(text("""
                    SELECT ca.nombre, sa.porcentaje
                    FROM supervision_areas sa
                    JOIN catalogo_areas ca ON sa.area_id = ca.id
                    WHERE sa.supervision_id = :sup_id
                    ORDER BY ca.numero ASC
                """), {'sup_id': sup[0]})

                for row in areas_result:
                    areas.append({
                        'nombre': row[0],
                        'porcentaje': round(float(row[1]), 2) if row[1] else 0,
                        'color': get_color_class(float(row[1]) if row[1] else 0)
                    })
        else:
            # Supervisiones de seguridad con KPIs
            query = """
                SELECT ss.id, ss.calificacion_general, ss.fecha_supervision, ss.supervisor
                FROM supervisiones_seguridad ss
                WHERE ss.sucursal_id = :sucursal_id
            """
            params = {'sucursal_id': sucursal_id}
            if periodo_id and periodo_id != 'all':
                query += " AND ss.periodo_id = :periodo_id"
                params['periodo_id'] = periodo_id
            query += " ORDER BY ss.fecha_supervision DESC LIMIT 1"

            sup = db.session.execute(text(query), params).fetchone()

            if sup:
                promedio = float(sup[1]) if sup[1] else 0
                # Obtener KPIs de la supervisión
                kpis_result = db.session.execute(text("""
                    SELECT ck.nombre, sk.porcentaje
                    FROM seguridad_kpis sk
                    JOIN catalogo_kpis_seguridad ck ON sk.kpi_id = ck.id
                    WHERE sk.supervision_id = :sup_id
                    ORDER BY ck.numero ASC
                """), {'sup_id': sup[0]})

                for row in kpis_result:
                    areas.append({
                        'nombre': row[0],
                        'porcentaje': round(float(row[1]), 2) if row[1] else 0,
                        'color': get_color_class(float(row[1]) if row[1] else 0)
                    })

        return jsonify({
            'success': True,
            'data': {
                'sucursal': {
                    'id': suc[0],
                    'nombre': suc[1],
                    'numero': suc[2],
                    'estado': suc[3],
                    'ciudad': suc[4],
                    'grupo_nombre': suc[5],
                    'grupo_id': suc[6]
                },
                'promedio': round(promedio, 2),
                'color': get_color_class(promedio),
                'fecha_supervision': str(sup[2]) if sup and sup[2] else None,
                'supervisor': sup[3] if sup else None,
                'areas': areas
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sucursal-tendencia/<int:sucursal_id>/<tipo>')
def api_sucursal_tendencia(sucursal_id, tipo):
    """Últimas 4 supervisiones individuales de una sucursal"""
    try:
        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        # Obtener últimas 4 supervisiones individuales
        result = db.session.execute(text(f"""
            SELECT sup.id, sup.calificacion_general, sup.fecha_supervision, sup.supervisor
            FROM {tabla} sup
            WHERE sup.sucursal_id = :sucursal_id
            ORDER BY sup.fecha_supervision DESC
            LIMIT 4
        """), {'sucursal_id': sucursal_id})

        tendencia = []
        for row in result:
            fecha = row[2]
            fecha_str = fecha.strftime('%d/%m') if fecha else '-'
            tendencia.append({
                'id': row[0],
                'calificacion': round(float(row[1]), 2) if row[1] else 0,
                'fecha': fecha_str,
                'fecha_completa': str(fecha) if fecha else None,
                'supervisor': row[3],
                'color': get_color_class(float(row[1]) if row[1] else 0)
            })

        # Invertir para mostrar de más antigua a más reciente
        tendencia.reverse()

        return jsonify({'success': True, 'data': tendencia})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/supervision/<int:supervision_id>/areas/<tipo>')
def api_supervision_areas(supervision_id, tipo):
    """Obtener áreas/KPIs de una supervisión específica"""
    try:
        if tipo == 'operativas':
            # Obtener info de la supervisión
            sup = db.session.execute(text("""
                SELECT so.id, so.calificacion_general, so.fecha_supervision, so.supervisor,
                       p.nombre as periodo_nombre
                FROM supervisiones_operativas so
                LEFT JOIN periodos_cas p ON so.periodo_id = p.id
                WHERE so.id = :sup_id
            """), {'sup_id': supervision_id}).fetchone()

            if not sup:
                return jsonify({'success': False, 'error': 'Supervisión no encontrada'}), 404

            # Obtener áreas
            areas_result = db.session.execute(text("""
                SELECT ca.nombre, sa.porcentaje
                FROM supervision_areas sa
                JOIN catalogo_areas ca ON sa.area_id = ca.id
                WHERE sa.supervision_id = :sup_id
                ORDER BY ca.numero ASC
            """), {'sup_id': supervision_id})

            areas = []
            for row in areas_result:
                areas.append({
                    'nombre': row[0],
                    'porcentaje': round(float(row[1]), 2) if row[1] else 0,
                    'color': get_color_class(float(row[1]) if row[1] else 0)
                })

            fecha = sup[2]
            fecha_str = fecha.strftime('%d/%m/%Y') if fecha else '-'

            return jsonify({
                'success': True,
                'data': {
                    'supervision_id': sup[0],
                    'calificacion': round(float(sup[1]), 2) if sup[1] else 0,
                    'fecha': fecha_str,
                    'supervisor': sup[3],
                    'periodo': sup[4],
                    'areas': areas
                }
            })
        else:
            # Seguridad - KPIs
            sup = db.session.execute(text("""
                SELECT ss.id, ss.calificacion_general, ss.fecha_supervision, ss.supervisor,
                       p.nombre as periodo_nombre
                FROM supervisiones_seguridad ss
                LEFT JOIN periodos_cas p ON ss.periodo_id = p.id
                WHERE ss.id = :sup_id
            """), {'sup_id': supervision_id}).fetchone()

            if not sup:
                return jsonify({'success': False, 'error': 'Supervisión no encontrada'}), 404

            # Obtener KPIs
            kpis_result = db.session.execute(text("""
                SELECT ck.nombre, sk.porcentaje
                FROM supervision_kpis sk
                JOIN catalogo_kpis ck ON sk.kpi_id = ck.id
                WHERE sk.supervision_id = :sup_id
                ORDER BY ck.id ASC
            """), {'sup_id': supervision_id})

            areas = []
            for row in kpis_result:
                areas.append({
                    'nombre': row[0],
                    'porcentaje': round(float(row[1]), 2) if row[1] else 0,
                    'color': get_color_class(float(row[1]) if row[1] else 0)
                })

            fecha = sup[2]
            fecha_str = fecha.strftime('%d/%m/%Y') if fecha else '-'

            return jsonify({
                'success': True,
                'data': {
                    'supervision_id': sup[0],
                    'calificacion': round(float(sup[1]), 2) if sup[1] else 0,
                    'fecha': fecha_str,
                    'supervisor': sup[3],
                    'periodo': sup[4],
                    'areas': areas
                }
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ENDPOINTS - MAPA ============
@app.route('/api/mapa/<tipo>')
def api_mapa(tipo):
    """Datos para el mapa - muestra TODAS las sucursales siempre"""
    try:
        periodo_id = request.args.get('periodo_id')
        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        # Query que incluye TODAS las sucursales con coordenadas fijas.
        # promedio = última eval de la sucursal en el alcance.
        anio = _anio_actual()
        con_periodo = bool(periodo_id and periodo_id != 'all')
        cnt_filtro = "AND x.periodo_id = :periodo_id" if con_periodo else f"AND x.periodo_id IN (SELECT id FROM periodos_cas WHERE EXTRACT(YEAR FROM fecha_inicio) = {int(anio)})"
        query = f"""
            WITH {_score_cte(tabla, con_periodo, anio)}
            SELECT s.id, s.nombre, g.nombre as grupo_nombre,
                   s.latitud as lat, s.longitud as lng,
                   u.calificacion_general as promedio,
                   (SELECT COUNT(*) FROM {tabla} x
                      WHERE x.sucursal_id = s.id {cnt_filtro}) as supervisiones
            FROM sucursales s
            LEFT JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
            LEFT JOIN ult u ON u.sucursal_id = s.id
            WHERE s.activo = true AND s.latitud IS NOT NULL AND s.longitud IS NOT NULL
            ORDER BY promedio DESC NULLS LAST
        """
        params = {'periodo_id': periodo_id} if con_periodo else {}

        result = db.session.execute(text(query), params)
        markers = []
        for row in result:
            promedio = round(float(row[5]), 2) if row[5] else None
            supervisiones = row[6] or 0

            # Color: gris si no hay supervisiones, según promedio si hay
            if supervisiones > 0 and promedio is not None:
                color = get_color_class(promedio)
            else:
                color = 'gray'
                promedio = None

            markers.append({
                'id': row[0],
                'nombre': row[1],
                'grupo': row[2],
                'lat': float(row[3]),
                'lng': float(row[4]),
                'promedio': promedio,
                'color': color,
                'supervisiones': supervisiones
            })

        return jsonify({'success': True, 'data': markers})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ENDPOINTS - HISTÓRICO ============
@app.route('/api/historico/<tipo>')
def api_historico(tipo):
    """Datos históricos por período CAS estilo McKinsey"""
    try:
        territorio = request.args.get('territorio', 'all')
        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        # La tendencia es del AÑO EN CURSO (Q1..Q4), no toda la historia (no 2025).
        anio = _anio_actual()

        # Periodos del año en curso (columnas de la tendencia)
        periodos = db.session.execute(text("""
            SELECT id, nombre FROM periodos_cas
            WHERE EXTRACT(YEAR FROM fecha_inicio) = :anio
            ORDER BY fecha_inicio
        """), {'anio': anio}).fetchall()

        # Datos por grupo y período = promedio de la última eval de cada sucursal
        # dentro de cada periodo (peso igual por sucursal). Solo sucursales activas
        # y solo trimestres del año en curso.
        result = db.session.execute(text(f"""
            WITH ult AS (
                SELECT so.sucursal_id, so.periodo_id,
                       AVG(so.calificacion_general) AS calificacion_general
                FROM {tabla} so
                JOIN sucursales sa ON sa.id = so.sucursal_id AND sa.activo = true
                GROUP BY so.sucursal_id, so.periodo_id
            )
            SELECT g.id, g.nombre, p.nombre as periodo_nombre,
                   AVG(u.calificacion_general) as promedio,
                   COUNT(u.sucursal_id) as evaluaciones
            FROM grupos_operativos g
            CROSS JOIN periodos_cas p
            LEFT JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true
            LEFT JOIN ult u ON u.sucursal_id = s.id AND u.periodo_id = p.id
            WHERE g.activo = true AND EXTRACT(YEAR FROM p.fecha_inicio) = :anio
            GROUP BY g.id, g.nombre, p.nombre, p.fecha_inicio
            ORDER BY g.nombre, p.fecha_inicio
        """), {'anio': anio})

        # Organizar datos
        grupos_data = {}
        for row in result:
            grupo_id = row[0]
            grupo_nombre = row[1]
            periodo_nombre = row[2]
            promedio = round(float(row[3]), 2) if row[3] else None
            evaluaciones = row[4]

            grupo_territorio = get_territorio(grupo_nombre)

            # Filtrar por territorio
            if territorio != 'all':
                if territorio == 'local' and grupo_territorio not in ['local', 'mixto']:
                    continue
                if territorio == 'foranea' and grupo_territorio not in ['foranea', 'mixto']:
                    continue

            if grupo_id not in grupos_data:
                grupos_data[grupo_id] = {
                    'id': grupo_id,
                    'nombre': grupo_nombre,
                    'territorio': grupo_territorio,
                    'periodos': {},
                    'promedio_general': 0
                }

            grupos_data[grupo_id]['periodos'][periodo_nombre] = {
                'promedio': promedio,
                'evaluaciones': evaluaciones,
                'color': get_color_class(promedio) if promedio else 'gray'
            }

        # Calcular promedios generales
        for grupo_id, data in grupos_data.items():
            promedios = [p['promedio'] for p in data['periodos'].values() if p['promedio'] is not None]
            data['promedio_general'] = round(sum(promedios) / len(promedios), 2) if promedios else 0

        # Ordenar por promedio general
        grupos_list = sorted(grupos_data.values(), key=lambda x: x['promedio_general'], reverse=True)

        # Promedio EPL CAS por período = peso igual por SUCURSAL (no por grupo),
        # para que cuadre EXACTO con el número del header (M1). Solo activas, año en curso.
        epl_cas = {'nombre': 'EPL CAS', 'periodos': {}}
        epl_result = db.session.execute(text(f"""
            WITH ult AS (
                SELECT so.sucursal_id, so.periodo_id,
                       AVG(so.calificacion_general) AS cg
                FROM {tabla} so
                JOIN sucursales sa ON sa.id = so.sucursal_id AND sa.activo = true
                JOIN periodos_cas p ON so.periodo_id = p.id
                WHERE EXTRACT(YEAR FROM p.fecha_inicio) = :anio
                GROUP BY so.sucursal_id, so.periodo_id
            )
            SELECT p.nombre, AVG(u.cg) AS prom
            FROM periodos_cas p
            LEFT JOIN ult u ON u.periodo_id = p.id
            WHERE EXTRACT(YEAR FROM p.fecha_inicio) = :anio
            GROUP BY p.nombre, p.fecha_inicio
            ORDER BY p.fecha_inicio
        """), {'anio': anio})
        for row in epl_result:
            if row[1] is not None:
                prom = round(float(row[1]), 2)
                epl_cas['periodos'][row[0]] = {'promedio': prom, 'color': get_color_class(prom)}

        return jsonify({
            'success': True,
            'data': {
                'periodos': [{'nombre': p[1]} for p in periodos],
                'grupos': grupos_list,
                'epl_cas': epl_cas
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ENDPOINTS - ALERTAS ============
@app.route('/api/alertas/<tipo>')
def api_alertas(tipo):
    """Alertas de rendimiento"""
    try:
        periodo_id = request.args.get('periodo_id')
        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        alertas = []

        anio = _anio_actual()
        con_periodo = bool(periodo_id and periodo_id != 'all')
        params = {}
        if con_periodo:
            params['periodo_id'] = periodo_id

        # Alertas críticas: sucursales cuya ÚLTIMA evaluación está < 70%
        query_criticos = f"""
            WITH {_score_cte(tabla, con_periodo, anio)}
            SELECT s.id, s.nombre, g.nombre as grupo, u.calificacion_general as promedio
            FROM ult u
            JOIN sucursales s ON u.sucursal_id = s.id AND s.activo = true
            JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
            WHERE u.calificacion_general < 70
            ORDER BY promedio
        """

        result = db.session.execute(text(query_criticos), params)
        for row in result:
            alertas.append({
                'tipo': 'critical',
                'titulo': f'Rendimiento Crítico: {row[1]}',
                'descripcion': f'Grupo {row[2]} - Promedio: {round(row[3], 1)}%',
                'sucursal_id': row[0],
                'promedio': round(row[3], 2)
            })

        # Alertas warning: grupos cuyo promedio (de últimas evals) está entre 70 y 80%
        query_warning = f"""
            WITH {_score_cte(tabla, con_periodo, anio)}
            SELECT g.id, g.nombre, AVG(u.calificacion_general) as promedio
            FROM grupos_operativos g
            JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true
            JOIN ult u ON u.sucursal_id = s.id
            WHERE g.activo = true
            GROUP BY g.id, g.nombre
            HAVING AVG(u.calificacion_general) < 80 AND AVG(u.calificacion_general) >= 70
            ORDER BY promedio
        """

        result = db.session.execute(text(query_warning), params)
        for row in result:
            alertas.append({
                'tipo': 'warning',
                'titulo': f'Atención Requerida: {row[1]}',
                'descripcion': f'Promedio del grupo: {round(row[2], 1)}%',
                'grupo_id': row[0],
                'promedio': round(row[2], 2)
            })

        return jsonify({
            'success': True,
            'data': {
                'alertas': alertas,
                'total_criticos': len([a for a in alertas if a['tipo'] == 'critical']),
                'total_warnings': len([a for a in alertas if a['tipo'] == 'warning'])
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ENDPOINTS - HEALTH ============
@app.route('/api/health')
def health():
    """Health check endpoint"""
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'database': 'disconnected', 'error': str(e)}), 500

# ============ ADMIN API ENDPOINTS ============
@app.route('/api/admin/tables')
@login_required
def admin_tables():
    """Listar todas las tablas de la base de datos"""
    try:
        result = db.session.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """))
        return jsonify({'success': True, 'data': [row[0] for row in result]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/table/<table_name>')
@login_required
def admin_table_data(table_name):
    """Obtener datos de una tabla específica"""
    allowed = ['periodos_cas', 'grupos_operativos', 'sucursales', 'supervisiones_operativas',
               'supervisiones_seguridad', 'supervision_areas', 'seguridad_kpis',
               'catalogo_areas', 'catalogo_kpis_seguridad']

    if table_name not in allowed:
        return jsonify({'success': False, 'error': 'Tabla no permitida'}), 403

    try:
        result = db.session.execute(text(f"SELECT * FROM {table_name} LIMIT 100"))
        columns = result.keys()
        data = [dict(zip(columns, [str(v) if v is not None else None for v in row])) for row in result]
        return jsonify({'success': True, 'data': data, 'columns': list(columns)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
