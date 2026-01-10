"""
EPL CAS 2026 Dashboard - Flask Application
Dashboard para supervisiones CAS con conexión a PostgreSQL Railway
"""

import os
from functools import wraps
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from dotenv import load_dotenv

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
    return render_template('admin.html')

# ============ API ENDPOINTS ============
@app.route('/api/periodos')
def api_periodos():
    """Obtener todos los periodos"""
    try:
        result = db.session.execute(text("""
            SELECT id, nombre, fecha_inicio, fecha_fin, activo, created_at
            FROM periodos_cas
            ORDER BY fecha_inicio DESC
        """))
        periodos = []
        for row in result:
            periodos.append({
                'id': row[0],
                'nombre': row[1],
                'fecha_inicio': str(row[2]) if row[2] else None,
                'fecha_fin': str(row[3]) if row[3] else None,
                'activo': row[4],
                'created_at': str(row[5]) if row[5] else None
            })
        return jsonify({'success': True, 'data': periodos})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/grupos-operativos')
def api_grupos_operativos():
    """Obtener todos los grupos operativos"""
    try:
        result = db.session.execute(text("""
            SELECT id, nombre, codigo, activo
            FROM grupos_operativos
            ORDER BY nombre
        """))
        grupos = []
        for row in result:
            grupos.append({
                'id': row[0],
                'nombre': row[1],
                'codigo': row[2],
                'activo': row[3]
            })
        return jsonify({'success': True, 'data': grupos})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sucursales')
def api_sucursales():
    """Obtener todas las sucursales"""
    try:
        result = db.session.execute(text("""
            SELECT id, nombre, codigo, grupo_operativo_id, activo
            FROM sucursales
            ORDER BY nombre
        """))
        sucursales = []
        for row in result:
            sucursales.append({
                'id': row[0],
                'nombre': row[1],
                'codigo': row[2],
                'grupo_operativo_id': row[3],
                'activo': row[4]
            })
        return jsonify({'success': True, 'data': sucursales})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dashboard/<tipo>/<int:periodo_id>')
def api_dashboard(tipo, periodo_id):
    """Obtener datos del dashboard por tipo y periodo"""
    try:
        if tipo == 'operativo':
            result = db.session.execute(text("""
                SELECT so.id, so.periodo_id, so.sucursal_id, so.calificacion,
                       so.observaciones, s.nombre as sucursal_nombre,
                       g.nombre as grupo_nombre
                FROM supervisiones_operativas so
                LEFT JOIN sucursales s ON so.sucursal_id = s.id
                LEFT JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
                WHERE so.periodo_id = :periodo_id
                ORDER BY so.calificacion DESC
            """), {'periodo_id': periodo_id})
        elif tipo == 'seguridad':
            result = db.session.execute(text("""
                SELECT ss.id, ss.periodo_id, ss.sucursal_id, ss.calificacion,
                       ss.observaciones, s.nombre as sucursal_nombre,
                       g.nombre as grupo_nombre
                FROM supervisiones_seguridad ss
                LEFT JOIN sucursales s ON ss.sucursal_id = s.id
                LEFT JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
                WHERE ss.periodo_id = :periodo_id
                ORDER BY ss.calificacion DESC
            """), {'periodo_id': periodo_id})
        else:
            return jsonify({'success': False, 'error': 'Tipo no válido'}), 400

        data = []
        for row in result:
            data.append({
                'id': row[0],
                'periodo_id': row[1],
                'sucursal_id': row[2],
                'calificacion': float(row[3]) if row[3] else 0,
                'observaciones': row[4],
                'sucursal_nombre': row[5],
                'grupo_nombre': row[6]
            })
        return jsonify({'success': True, 'data': data, 'tipo': tipo})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ranking/grupos')
def api_ranking_grupos():
    """Ranking de grupos operativos"""
    try:
        periodo_id = request.args.get('periodo_id')
        query = """
            SELECT g.id, g.nombre, g.codigo,
                   COALESCE(AVG(so.calificacion), 0) as promedio_operativo,
                   COALESCE(AVG(ss.calificacion), 0) as promedio_seguridad,
                   COUNT(DISTINCT s.id) as total_sucursales
            FROM grupos_operativos g
            LEFT JOIN sucursales s ON g.id = s.grupo_operativo_id
            LEFT JOIN supervisiones_operativas so ON s.id = so.sucursal_id
            LEFT JOIN supervisiones_seguridad ss ON s.id = ss.sucursal_id
        """
        params = {}
        if periodo_id:
            query += " WHERE (so.periodo_id = :periodo_id OR so.periodo_id IS NULL) AND (ss.periodo_id = :periodo_id OR ss.periodo_id IS NULL)"
            params['periodo_id'] = periodo_id

        query += " GROUP BY g.id, g.nombre, g.codigo ORDER BY promedio_operativo DESC"

        result = db.session.execute(text(query), params)
        ranking = []
        for row in result:
            promedio_general = (float(row[3]) + float(row[4])) / 2 if row[3] and row[4] else 0
            ranking.append({
                'id': row[0],
                'nombre': row[1],
                'codigo': row[2],
                'promedio_operativo': round(float(row[3]), 2),
                'promedio_seguridad': round(float(row[4]), 2),
                'promedio_general': round(promedio_general, 2),
                'total_sucursales': row[5]
            })
        return jsonify({'success': True, 'data': ranking})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ranking/sucursales')
def api_ranking_sucursales():
    """Ranking de sucursales"""
    try:
        periodo_id = request.args.get('periodo_id')
        grupo_id = request.args.get('grupo_id')

        query = """
            SELECT s.id, s.nombre, s.codigo, g.nombre as grupo_nombre,
                   COALESCE(so.calificacion, 0) as calificacion_operativa,
                   COALESCE(ss.calificacion, 0) as calificacion_seguridad
            FROM sucursales s
            LEFT JOIN grupos_operativos g ON s.grupo_operativo_id = g.id
            LEFT JOIN supervisiones_operativas so ON s.id = so.sucursal_id
            LEFT JOIN supervisiones_seguridad ss ON s.id = ss.sucursal_id
            WHERE s.activo = true
        """
        params = {}

        if periodo_id:
            query += " AND (so.periodo_id = :periodo_id OR so.periodo_id IS NULL)"
            query += " AND (ss.periodo_id = :periodo_id OR ss.periodo_id IS NULL)"
            params['periodo_id'] = periodo_id

        if grupo_id:
            query += " AND s.grupo_operativo_id = :grupo_id"
            params['grupo_id'] = grupo_id

        query += " ORDER BY calificacion_operativa DESC"

        result = db.session.execute(text(query), params)
        ranking = []
        for row in result:
            promedio = (float(row[4]) + float(row[5])) / 2
            ranking.append({
                'id': row[0],
                'nombre': row[1],
                'codigo': row[2],
                'grupo_nombre': row[3],
                'calificacion_operativa': round(float(row[4]), 2),
                'calificacion_seguridad': round(float(row[5]), 2),
                'promedio': round(promedio, 2)
            })
        return jsonify({'success': True, 'data': ranking})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/kpis/seguridad')
def api_kpis_seguridad():
    """Obtener KPIs de seguridad"""
    try:
        result = db.session.execute(text("""
            SELECT sk.id, sk.sucursal_id, sk.periodo_id, sk.kpi_id,
                   sk.valor, sk.meta, ck.nombre as kpi_nombre,
                   s.nombre as sucursal_nombre
            FROM seguridad_kpis sk
            LEFT JOIN catalogo_kpis_seguridad ck ON sk.kpi_id = ck.id
            LEFT JOIN sucursales s ON sk.sucursal_id = s.id
            ORDER BY sk.periodo_id DESC, s.nombre
        """))
        kpis = []
        for row in result:
            cumplimiento = (float(row[4]) / float(row[5]) * 100) if row[5] and row[5] > 0 else 0
            kpis.append({
                'id': row[0],
                'sucursal_id': row[1],
                'periodo_id': row[2],
                'kpi_id': row[3],
                'valor': float(row[4]) if row[4] else 0,
                'meta': float(row[5]) if row[5] else 0,
                'kpi_nombre': row[6],
                'sucursal_nombre': row[7],
                'cumplimiento': round(cumplimiento, 2)
            })
        return jsonify({'success': True, 'data': kpis})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
def api_stats():
    """Estadísticas generales del dashboard"""
    try:
        stats = {}

        # Total periodos
        result = db.session.execute(text("SELECT COUNT(*) FROM periodos_cas"))
        stats['total_periodos'] = result.scalar() or 0

        # Total grupos
        result = db.session.execute(text("SELECT COUNT(*) FROM grupos_operativos WHERE activo = true"))
        stats['total_grupos'] = result.scalar() or 0

        # Total sucursales
        result = db.session.execute(text("SELECT COUNT(*) FROM sucursales WHERE activo = true"))
        stats['total_sucursales'] = result.scalar() or 0

        # Total supervisiones operativas
        result = db.session.execute(text("SELECT COUNT(*) FROM supervisiones_operativas"))
        stats['total_supervisiones_operativas'] = result.scalar() or 0

        # Total supervisiones seguridad
        result = db.session.execute(text("SELECT COUNT(*) FROM supervisiones_seguridad"))
        stats['total_supervisiones_seguridad'] = result.scalar() or 0

        # Promedio general operativo
        result = db.session.execute(text("SELECT AVG(calificacion) FROM supervisiones_operativas"))
        stats['promedio_operativo'] = round(float(result.scalar() or 0), 2)

        # Promedio general seguridad
        result = db.session.execute(text("SELECT AVG(calificacion) FROM supervisiones_seguridad"))
        stats['promedio_seguridad'] = round(float(result.scalar() or 0), 2)

        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        return jsonify({'success': True, 'data': tables})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/table/<table_name>')
@login_required
def admin_table_data(table_name):
    """Obtener datos de una tabla específica"""
    allowed_tables = [
        'periodos_cas', 'grupos_operativos', 'sucursales',
        'supervisiones_operativas', 'supervisiones_seguridad',
        'supervision_areas', 'seguridad_kpis', 'catalogo_areas',
        'catalogo_kpis_seguridad'
    ]

    if table_name not in allowed_tables:
        return jsonify({'success': False, 'error': 'Tabla no permitida'}), 403

    try:
        result = db.session.execute(text(f"SELECT * FROM {table_name} LIMIT 100"))
        columns = result.keys()
        data = []
        for row in result:
            data.append(dict(zip(columns, [str(v) if v is not None else None for v in row])))
        return jsonify({'success': True, 'data': data, 'columns': list(columns)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
