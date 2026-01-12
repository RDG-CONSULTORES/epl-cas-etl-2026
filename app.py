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
from datetime import datetime

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
    locales = ['TEPEYAC', 'OGAS', 'EFM', 'EPL SO', 'PLOG NUEVO LEON', 'GRUPO CENTRITO', 'GRUPO SABINAS HIDALGO']
    mixtos = ['TEC', 'EXPO', 'GRUPO SALTILLO']

    for local in locales:
        if local.lower() in grupo_nombre.lower():
            return 'local'
    for mixto in mixtos:
        if mixto.lower() in grupo_nombre.lower():
            return 'mixto'
    return 'foranea'

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
        total_op = db.session.execute(text("SELECT COUNT(*) FROM supervisiones_operativas")).scalar() or 0
        total_seg = db.session.execute(text("SELECT COUNT(*) FROM supervisiones_seguridad")).scalar() or 0
        total_sucursales = db.session.execute(text("SELECT COUNT(*) FROM sucursales WHERE activo = true")).scalar() or 0
        total_grupos = db.session.execute(text("SELECT COUNT(*) FROM grupos_operativos WHERE activo = true")).scalar() or 0

        result = db.session.execute(text("""
            SELECT id, nombre, fecha_inicio, fecha_fin
            FROM periodos_cas ORDER BY fecha_inicio DESC
        """))
        periodos = [{'id': r[0], 'nombre': r[1],
                     'fecha_inicio': str(r[2]) if r[2] else '',
                     'fecha_fin': str(r[3]) if r[3] else ''} for r in result]

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

        # Promedio general
        query_prom = f"SELECT AVG(calificacion_general) FROM {tabla}"
        params = {}
        if periodo_id:
            query_prom += " WHERE periodo_id = :periodo_id"
            params['periodo_id'] = periodo_id

        promedio = db.session.execute(text(query_prom), params).scalar() or 0

        # Total supervisiones
        query_total = f"SELECT COUNT(*) FROM {tabla}"
        if periodo_id:
            query_total += " WHERE periodo_id = :periodo_id"
        total_supervisiones = db.session.execute(text(query_total), params).scalar() or 0

        # Sucursales supervisadas
        query_suc = f"SELECT COUNT(DISTINCT sucursal_id) FROM {tabla}"
        if periodo_id:
            query_suc += " WHERE periodo_id = :periodo_id"
        sucursales_supervisadas = db.session.execute(text(query_suc), params).scalar() or 0

        # Total sucursales
        total_sucursales = db.session.execute(text("SELECT COUNT(*) FROM sucursales WHERE activo = true")).scalar() or 0

        # Total grupos
        total_grupos = db.session.execute(text("SELECT COUNT(*) FROM grupos_operativos WHERE activo = true")).scalar() or 0

        # Cobertura
        cobertura = round((sucursales_supervisadas / total_sucursales * 100) if total_sucursales > 0 else 0, 1)

        # Distribución por rendimiento
        query_dist = f"""
            SELECT
                SUM(CASE WHEN calificacion_general >= 90 THEN 1 ELSE 0 END) as excelente,
                SUM(CASE WHEN calificacion_general >= 80 AND calificacion_general < 90 THEN 1 ELSE 0 END) as bueno,
                SUM(CASE WHEN calificacion_general >= 70 AND calificacion_general < 80 THEN 1 ELSE 0 END) as regular,
                SUM(CASE WHEN calificacion_general < 70 THEN 1 ELSE 0 END) as critico
            FROM {tabla}
        """
        if periodo_id:
            query_dist += " WHERE periodo_id = :periodo_id"

        dist_result = db.session.execute(text(query_dist), params).fetchone()
        distribucion = {
            'excelente': dist_result[0] or 0,
            'bueno': dist_result[1] or 0,
            'regular': dist_result[2] or 0,
            'critico': dist_result[3] or 0
        }

        return jsonify({
            'success': True,
            'data': {
                'promedio': float(round(promedio, 2)),
                'color': get_color_class(promedio),
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
    """Ranking de grupos operativos"""
    try:
        periodo_id = request.args.get('periodo_id')
        territorio = request.args.get('territorio')  # local, foranea, mixto, all

        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        query = f"""
            SELECT g.id, g.nombre,
                   COALESCE(AVG(sup.calificacion_general), 0) as promedio,
                   COUNT(DISTINCT s.id) as total_sucursales,
                   COUNT(sup.id) as total_supervisiones
            FROM grupos_operativos g
            LEFT JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true
            LEFT JOIN {tabla} sup ON s.id = sup.sucursal_id
            WHERE g.activo = true
        """

        params = {}
        if periodo_id:
            query += " AND (sup.periodo_id = :periodo_id OR sup.periodo_id IS NULL)"
            params['periodo_id'] = periodo_id

        query += " GROUP BY g.id, g.nombre ORDER BY promedio DESC"

        result = db.session.execute(text(query), params)
        ranking = []
        pos = 1
        for row in result:
            grupo_territorio = get_territorio(row[1])

            # Filtrar por territorio si se especifica
            if territorio and territorio != 'all':
                if territorio == 'local' and grupo_territorio not in ['local', 'mixto']:
                    continue
                if territorio == 'foranea' and grupo_territorio not in ['foranea', 'mixto']:
                    continue

            ranking.append({
                'posicion': pos,
                'id': row[0],
                'nombre': row[1],
                'promedio': round(float(row[2]), 2),
                'color': get_color_class(float(row[2])),
                'total_sucursales': row[3],
                'total_supervisiones': row[4],
                'territorio': grupo_territorio
            })
            pos += 1

        return jsonify({'success': True, 'data': ranking})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ranking/sucursales/<tipo>')
def api_ranking_sucursales(tipo):
    """Ranking de sucursales"""
    try:
        periodo_id = request.args.get('periodo_id')
        grupo_id = request.args.get('grupo_id')

        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        query = f"""
            SELECT s.id, s.nombre, g.nombre as grupo_nombre, g.id as grupo_id,
                   COALESCE(AVG(sup.calificacion_general), 0) as promedio,
                   COUNT(sup.id) as total_supervisiones
            FROM sucursales s
            LEFT JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
            LEFT JOIN {tabla} sup ON s.id = sup.sucursal_id
            WHERE s.activo = true
        """

        params = {}
        if periodo_id:
            query += " AND (sup.periodo_id = :periodo_id OR sup.periodo_id IS NULL)"
            params['periodo_id'] = periodo_id

        if grupo_id:
            query += " AND s.grupo_operativo_id = :grupo_id"
            params['grupo_id'] = grupo_id

        query += " GROUP BY s.id, s.nombre, g.nombre, g.id ORDER BY promedio DESC"

        result = db.session.execute(text(query), params)
        ranking = []
        pos = 1
        for row in result:
            ranking.append({
                'posicion': pos,
                'id': row[0],
                'nombre': row[1],
                'grupo_nombre': row[2],
                'grupo_id': row[3],
                'promedio': round(float(row[4]), 2),
                'color': get_color_class(float(row[4])),
                'total_supervisiones': row[5]
            })
            pos += 1

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

        # Promedio del grupo
        query_prom = f"""
            SELECT AVG(sup.calificacion_general)
            FROM {tabla} sup
            JOIN sucursales s ON sup.sucursal_id = s.id
            WHERE s.grupo_operativo_id = :grupo_id
        """
        params = {'grupo_id': grupo_id}
        if periodo_id:
            query_prom += " AND sup.periodo_id = :periodo_id"
            params['periodo_id'] = periodo_id

        promedio = db.session.execute(text(query_prom), params).scalar() or 0

        # Sucursales del grupo
        query_suc = f"""
            SELECT s.id, s.nombre,
                   COALESCE(AVG(sup.calificacion_general), 0) as promedio,
                   COUNT(sup.id) as supervisiones
            FROM sucursales s
            LEFT JOIN {tabla} sup ON s.id = sup.sucursal_id
            WHERE s.grupo_operativo_id = :grupo_id AND s.activo = true
        """
        if periodo_id:
            query_suc += " AND (sup.periodo_id = :periodo_id OR sup.periodo_id IS NULL)"
        query_suc += " GROUP BY s.id, s.nombre ORDER BY promedio DESC"

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

        # Info de la sucursal
        suc = db.session.execute(text("""
            SELECT s.id, s.nombre, s.codigo, s.estado, s.municipio,
                   g.nombre as grupo_nombre, g.id as grupo_id
            FROM sucursales s
            LEFT JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
            WHERE s.id = :id
        """), {'id': sucursal_id}).fetchone()

        if not suc:
            return jsonify({'success': False, 'error': 'Sucursal no encontrada'}), 404

        if tipo == 'operativas':
            # Supervisiones operativas con áreas
            query = """
                SELECT so.id, so.calificacion_general, so.fecha_supervision, so.supervisor
                FROM supervisiones_operativas so
                WHERE so.sucursal_id = :sucursal_id
            """
            params = {'sucursal_id': sucursal_id}
            if periodo_id:
                query += " AND so.periodo_id = :periodo_id"
                params['periodo_id'] = periodo_id
            query += " ORDER BY so.fecha_supervision DESC LIMIT 1"

            sup = db.session.execute(text(query), params).fetchone()

            areas = []
            promedio = 0
            if sup:
                promedio = float(sup[1]) if sup[1] else 0
                # Obtener áreas de la supervisión
                areas_result = db.session.execute(text("""
                    SELECT ca.nombre, sa.porcentaje
                    FROM supervision_areas sa
                    JOIN catalogo_areas ca ON sa.area_id = ca.id
                    WHERE sa.supervision_id = :sup_id
                    ORDER BY sa.porcentaje DESC
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
            if periodo_id:
                query += " AND ss.periodo_id = :periodo_id"
                params['periodo_id'] = periodo_id
            query += " ORDER BY ss.fecha_supervision DESC LIMIT 1"

            sup = db.session.execute(text(query), params).fetchone()

            areas = []
            promedio = 0
            if sup:
                promedio = float(sup[1]) if sup[1] else 0
                # Obtener KPIs de la supervisión
                kpis_result = db.session.execute(text("""
                    SELECT ck.nombre, sk.porcentaje
                    FROM seguridad_kpis sk
                    JOIN catalogo_kpis_seguridad ck ON sk.kpi_id = ck.id
                    WHERE sk.supervision_id = :sup_id
                    ORDER BY sk.porcentaje DESC
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
                    'id': suc[0], 'nombre': suc[1], 'codigo': suc[2],
                    'estado': suc[3], 'municipio': suc[4],
                    'grupo_nombre': suc[5], 'grupo_id': suc[6]
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
    """Tendencia histórica de una sucursal por período CAS"""
    try:
        tabla = 'supervisiones_operativas' if tipo == 'operativas' else 'supervisiones_seguridad'

        result = db.session.execute(text(f"""
            SELECT p.codigo, p.nombre, AVG(sup.calificacion_general) as promedio
            FROM {tabla} sup
            JOIN periodos_cas p ON sup.periodo_id = p.id
            WHERE sup.sucursal_id = :sucursal_id
            GROUP BY p.id, p.codigo, p.nombre, p.fecha_inicio
            ORDER BY p.fecha_inicio
        """), {'sucursal_id': sucursal_id})

        tendencia = []
        for row in result:
            tendencia.append({
                'periodo': row[0],
                'nombre': row[1],
                'promedio': round(float(row[2]), 2) if row[2] else 0,
                'color': get_color_class(float(row[2]) if row[2] else 0)
            })

        return jsonify({'success': True, 'data': tendencia})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ API ENDPOINTS - MAPA ============
@app.route('/api/mapa/<tipo>')
def api_mapa(tipo):
    """Datos para el mapa con ubicaciones desde supervisiones"""
    try:
        periodo_id = request.args.get('periodo_id')

        if tipo == 'operativas':
            # Usar lat/lon de supervisiones operativas
            query = """
                SELECT s.id, s.nombre, g.nombre as grupo_nombre,
                       AVG(sup.calificacion_general) as promedio,
                       AVG(sup.lat_entrega) as lat, AVG(sup.lon_entrega) as lng,
                       COUNT(sup.id) as supervisiones
                FROM sucursales s
                LEFT JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
                JOIN supervisiones_operativas sup ON s.id = sup.sucursal_id
                WHERE s.activo = true AND sup.lat_entrega IS NOT NULL
            """
            params = {}
            if periodo_id:
                query += " AND sup.periodo_id = :periodo_id"
                params['periodo_id'] = periodo_id
            query += " GROUP BY s.id, s.nombre, g.nombre"
        else:
            # Para seguridad, obtener coordenadas de las supervisiones operativas del mismo día
            query = """
                SELECT s.id, s.nombre, g.nombre as grupo_nombre,
                       AVG(ss.calificacion_general) as promedio,
                       AVG(so.lat_entrega) as lat, AVG(so.lon_entrega) as lng,
                       COUNT(ss.id) as supervisiones
                FROM sucursales s
                LEFT JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
                JOIN supervisiones_seguridad ss ON s.id = ss.sucursal_id
                LEFT JOIN supervisiones_operativas so ON s.id = so.sucursal_id
                    AND DATE(so.fecha_supervision) = DATE(ss.fecha_supervision)
                WHERE s.activo = true AND so.lat_entrega IS NOT NULL
            """
            params = {}
            if periodo_id:
                query += " AND ss.periodo_id = :periodo_id"
                params['periodo_id'] = periodo_id
            query += " GROUP BY s.id, s.nombre, g.nombre"

        result = db.session.execute(text(query), params)
        markers = []
        for row in result:
            if row[4] and row[5]:  # lat and lng exist
                markers.append({
                    'id': row[0],
                    'nombre': row[1],
                    'grupo': row[2],
                    'promedio': round(float(row[3]), 2) if row[3] else 0,
                    'color': get_color_class(float(row[3]) if row[3] else 0),
                    'lat': float(row[4]),
                    'lng': float(row[5]),
                    'supervisiones': row[6]
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

        # Obtener todos los períodos
        periodos = db.session.execute(text("""
            SELECT id, nombre FROM periodos_cas ORDER BY fecha_inicio
        """)).fetchall()

        # Obtener datos por grupo y período
        result = db.session.execute(text(f"""
            SELECT g.id, g.nombre, p.nombre as periodo_nombre, AVG(sup.calificacion_general) as promedio,
                   COUNT(sup.id) as evaluaciones
            FROM grupos_operativos g
            CROSS JOIN periodos_cas p
            LEFT JOIN sucursales s ON g.id = s.grupo_operativo_id AND s.activo = true
            LEFT JOIN {tabla} sup ON s.id = sup.sucursal_id AND sup.periodo_id = p.id
            WHERE g.activo = true
            GROUP BY g.id, g.nombre, p.nombre, p.fecha_inicio
            ORDER BY g.nombre, p.fecha_inicio
        """))

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

        # Calcular promedio EPL CAS por período
        epl_cas = {'nombre': 'EPL CAS', 'periodos': {}}
        for periodo in periodos:
            nombre = periodo[1]
            promedios = [g['periodos'].get(nombre, {}).get('promedio') for g in grupos_list
                        if g['periodos'].get(nombre, {}).get('promedio') is not None]
            if promedios:
                prom = round(sum(promedios) / len(promedios), 2)
                epl_cas['periodos'][nombre] = {'promedio': prom, 'color': get_color_class(prom)}

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

        # Alertas críticas (< 70%)
        query_criticos = f"""
            SELECT s.id, s.nombre, g.nombre as grupo, AVG(sup.calificacion_general) as promedio
            FROM sucursales s
            JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
            JOIN {tabla} sup ON s.id = sup.sucursal_id
            WHERE s.activo = true
        """
        params = {}
        if periodo_id:
            query_criticos += " AND sup.periodo_id = :periodo_id"
            params['periodo_id'] = periodo_id
        query_criticos += " GROUP BY s.id, s.nombre, g.nombre HAVING AVG(sup.calificacion_general) < 70 ORDER BY promedio"

        result = db.session.execute(text(query_criticos), params)
        for row in result:
            alertas.append({
                'tipo': 'critical',
                'titulo': f'Rendimiento Crítico: {row[1]}',
                'descripcion': f'Grupo {row[2]} - Promedio: {round(row[3], 1)}%',
                'sucursal_id': row[0],
                'promedio': round(row[3], 2)
            })

        # Alertas warning (caída de rendimiento - grupos bajo 80%)
        query_warning = f"""
            SELECT g.id, g.nombre, AVG(sup.calificacion_general) as promedio
            FROM grupos_operativos g
            JOIN sucursales s ON g.id = s.grupo_operativo_id
            JOIN {tabla} sup ON s.id = sup.sucursal_id
            WHERE g.activo = true
        """
        if periodo_id:
            query_warning += " AND sup.periodo_id = :periodo_id"
        query_warning += " GROUP BY g.id, g.nombre HAVING AVG(sup.calificacion_general) < 80 AND AVG(sup.calificacion_general) >= 70 ORDER BY promedio"

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

# ============ DEBUG ENDPOINT (TEMPORAL) ============
@app.route('/api/debug/explore')
def debug_explore():
    """Endpoint temporal para explorar estructura de BD"""
    try:
        result = {}

        # Listar todas las tablas
        tables = db.session.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """))
        result['tables'] = [row[0] for row in tables]

        # Estructura de cada tabla relevante
        for table in ['catalogo_areas', 'catalogo_kpis_seguridad', 'supervision_areas',
                      'seguridad_kpis', 'sucursales', 'supervisiones_operativas']:
            try:
                cols = db.session.execute(text(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = '{table}' ORDER BY ordinal_position
                """))
                result[f'{table}_columns'] = [{'name': r[0], 'type': r[1]} for r in cols]

                # Contar registros
                count = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                result[f'{table}_count'] = count

                # Muestra de datos
                sample = db.session.execute(text(f"SELECT * FROM {table} LIMIT 3"))
                columns = sample.keys()
                result[f'{table}_sample'] = [dict(zip(columns, [str(v) if v else None for v in row])) for row in sample]
            except Exception as e:
                result[f'{table}_error'] = str(e)

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
