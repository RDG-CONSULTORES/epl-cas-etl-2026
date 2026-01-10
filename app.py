"""
EPL CAS 2026 - Dashboard de Supervisiones El Pollo Loco México
Flask Application
"""
import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func, desc
from functools import wraps
from datetime import datetime, date
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'epl-cas-2026-secret-key')

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:TszPoSlPeZmXodYvEqoPwQKaUUxBbSOE@caboose.proxy.rlwy.net:10380/railway')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

db = SQLAlchemy(app)

# Admin password
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'epl2026admin')

# ============================================
# MODELS (reflecting existing tables)
# ============================================

class GrupoOperativo(db.Model):
    __tablename__ = 'grupos_operativos'
    id = db.Column(db.Integer, primary_key=True)
    zenput_team_id = db.Column(db.Integer)
    nombre = db.Column(db.String(100))
    activo = db.Column(db.Boolean, default=True)
    sucursales = db.relationship('Sucursal', backref='grupo', lazy='dynamic')

class Sucursal(db.Model):
    __tablename__ = 'sucursales'
    id = db.Column(db.Integer, primary_key=True)
    zenput_location_id = db.Column(db.Integer, unique=True)
    numero = db.Column(db.Integer)
    nombre = db.Column(db.String(100))
    nombre_corto = db.Column(db.String(50))
    grupo_operativo_id = db.Column(db.Integer, db.ForeignKey('grupos_operativos.id'))
    ciudad = db.Column(db.String(100))
    estado = db.Column(db.String(50))
    latitud = db.Column(db.Numeric(10, 8))
    longitud = db.Column(db.Numeric(11, 8))
    clasificacion = db.Column(db.String(20), default='local')
    activo = db.Column(db.Boolean, default=True)

class PeriodoCAS(db.Model):
    __tablename__ = 'periodos_cas'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True)
    nombre = db.Column(db.String(100))
    anio = db.Column(db.Integer)
    fecha_inicio = db.Column(db.Date)
    fecha_fin = db.Column(db.Date)
    aplica_a = db.Column(db.String(20))

class SupervisionOperativa(db.Model):
    __tablename__ = 'supervisiones_operativas'
    id = db.Column(db.Integer, primary_key=True)
    zenput_submission_id = db.Column(db.String(50), unique=True)
    sucursal_id = db.Column(db.Integer, db.ForeignKey('sucursales.id'))
    periodo_id = db.Column(db.Integer, db.ForeignKey('periodos_cas.id'))
    supervisor = db.Column(db.String(100))
    fecha_supervision = db.Column(db.DateTime)
    calificacion_general = db.Column(db.Numeric(5, 2))
    lat_entrega = db.Column(db.Numeric(10, 8))
    lon_entrega = db.Column(db.Numeric(11, 8))
    sucursal = db.relationship('Sucursal', backref='supervisiones_op')
    periodo = db.relationship('PeriodoCAS', backref='supervisiones_op')

class SupervisionSeguridad(db.Model):
    __tablename__ = 'supervisiones_seguridad'
    id = db.Column(db.Integer, primary_key=True)
    zenput_submission_id = db.Column(db.String(50), unique=True)
    sucursal_id = db.Column(db.Integer, db.ForeignKey('sucursales.id'))
    periodo_id = db.Column(db.Integer, db.ForeignKey('periodos_cas.id'))
    supervisor = db.Column(db.String(100))
    fecha_supervision = db.Column(db.DateTime)
    calificacion_general = db.Column(db.Numeric(5, 2))
    sucursal = db.relationship('Sucursal', backref='supervisiones_seg')
    periodo = db.relationship('PeriodoCAS', backref='supervisiones_seg')

class CatalogoArea(db.Model):
    __tablename__ = 'catalogo_areas'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer)
    codigo = db.Column(db.String(50))
    nombre = db.Column(db.String(100))
    zenput_field = db.Column(db.String(100))

class CatalogoKPISeguridad(db.Model):
    __tablename__ = 'catalogo_kpis_seguridad'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer)
    codigo = db.Column(db.String(50))
    nombre = db.Column(db.String(100))

class SupervisionArea(db.Model):
    __tablename__ = 'supervision_areas'
    id = db.Column(db.Integer, primary_key=True)
    supervision_id = db.Column(db.Integer, db.ForeignKey('supervisiones_operativas.id'))
    area_id = db.Column(db.Integer, db.ForeignKey('catalogo_areas.id'))
    porcentaje = db.Column(db.Numeric(5, 2))
    area = db.relationship('CatalogoArea')

class SeguridadKPI(db.Model):
    __tablename__ = 'seguridad_kpis'
    id = db.Column(db.Integer, primary_key=True)
    supervision_id = db.Column(db.Integer, db.ForeignKey('supervisiones_seguridad.id'))
    kpi_id = db.Column(db.Integer, db.ForeignKey('catalogo_kpis_seguridad.id'))
    porcentaje = db.Column(db.Numeric(5, 2))
    kpi = db.relationship('CatalogoKPISeguridad')

# ============================================
# CONFIG SISTEMA (para admin panel)
# ============================================

class ConfigSistema(db.Model):
    __tablename__ = 'config_sistema'
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True)
    valor = db.Column(db.Text)
    descripcion = db.Column(db.String(200))

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_config(clave, default=None):
    """Obtener configuración del sistema"""
    try:
        config = ConfigSistema.query.filter_by(clave=clave).first()
        return config.valor if config else default
    except:
        return default

def set_config(clave, valor, descripcion=''):
    """Establecer configuración del sistema"""
    config = ConfigSistema.query.filter_by(clave=clave).first()
    if config:
        config.valor = valor
    else:
        config = ConfigSistema(clave=clave, valor=valor, descripcion=descripcion)
        db.session.add(config)
    db.session.commit()

def get_periodo_activo():
    """Obtener el periodo activo actual"""
    periodo_id = get_config('periodo_activo')
    if periodo_id:
        return PeriodoCAS.query.get(int(periodo_id))
    # Default: buscar periodo actual por fecha
    hoy = date.today()
    periodo = PeriodoCAS.query.filter(
        PeriodoCAS.fecha_inicio <= hoy,
        PeriodoCAS.fecha_fin >= hoy
    ).first()
    return periodo or PeriodoCAS.query.order_by(desc(PeriodoCAS.id)).first()

def get_color_class(porcentaje):
    """Retorna clase CSS según el porcentaje"""
    if porcentaje is None:
        return 'gray'
    p = float(porcentaje)
    if p >= 90:
        return 'green'
    elif p >= 80:
        return 'yellow'
    elif p >= 70:
        return 'orange'
    return 'red'

def get_trend(current, previous):
    """Calcular tendencia"""
    if previous is None or current is None:
        return 'neutral'
    diff = float(current) - float(previous)
    if diff > 2:
        return 'up'
    elif diff < -2:
        return 'down'
    return 'neutral'

# ============================================
# AUTH DECORATOR
# ============================================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# ROUTES - MAIN DASHBOARD
# ============================================

@app.route('/')
def index():
    """Dashboard principal"""
    periodos = PeriodoCAS.query.order_by(desc(PeriodoCAS.anio), desc(PeriodoCAS.id)).all()
    periodo_activo = get_periodo_activo()
    return render_template('index.html', 
                         periodos=periodos,
                         periodo_activo=periodo_activo)

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/api/periodos')
def api_periodos():
    """Lista de periodos disponibles"""
    periodos = PeriodoCAS.query.order_by(desc(PeriodoCAS.anio), desc(PeriodoCAS.id)).all()
    return jsonify([{
        'id': p.id,
        'codigo': p.codigo,
        'nombre': p.nombre,
        'anio': p.anio,
        'fecha_inicio': p.fecha_inicio.isoformat() if p.fecha_inicio else None,
        'fecha_fin': p.fecha_fin.isoformat() if p.fecha_fin else None,
        'aplica_a': p.aplica_a
    } for p in periodos])

@app.route('/api/dashboard/<tipo>/<int:periodo_id>')
def api_dashboard(tipo, periodo_id):
    """Datos del dashboard para un periodo y tipo (operativas/seguridad)"""
    periodo = PeriodoCAS.query.get_or_404(periodo_id)
    
    # Obtener periodo anterior para tendencias
    periodo_anterior = PeriodoCAS.query.filter(
        PeriodoCAS.id < periodo_id
    ).order_by(desc(PeriodoCAS.id)).first()
    
    if tipo == 'operativas':
        # Supervisiones operativas
        supervisiones = SupervisionOperativa.query.filter_by(periodo_id=periodo_id).all()
        
        # Promedio general
        promedio = db.session.query(func.avg(SupervisionOperativa.calificacion_general))\
            .filter(SupervisionOperativa.periodo_id == periodo_id).scalar()
        
        # Promedio periodo anterior
        promedio_ant = None
        if periodo_anterior:
            promedio_ant = db.session.query(func.avg(SupervisionOperativa.calificacion_general))\
                .filter(SupervisionOperativa.periodo_id == periodo_anterior.id).scalar()
        
        # Total sucursales y supervisadas
        total_sucursales = Sucursal.query.filter_by(activo=True).count()
        sucursales_supervisadas = db.session.query(func.count(func.distinct(SupervisionOperativa.sucursal_id)))\
            .filter(SupervisionOperativa.periodo_id == periodo_id).scalar()
        
    else:  # seguridad
        supervisiones = SupervisionSeguridad.query.filter_by(periodo_id=periodo_id).all()
        
        promedio = db.session.query(func.avg(SupervisionSeguridad.calificacion_general))\
            .filter(SupervisionSeguridad.periodo_id == periodo_id).scalar()
        
        promedio_ant = None
        if periodo_anterior:
            promedio_ant = db.session.query(func.avg(SupervisionSeguridad.calificacion_general))\
                .filter(SupervisionSeguridad.periodo_id == periodo_anterior.id).scalar()
        
        total_sucursales = Sucursal.query.filter_by(activo=True).count()
        sucursales_supervisadas = db.session.query(func.count(func.distinct(SupervisionSeguridad.sucursal_id)))\
            .filter(SupervisionSeguridad.periodo_id == periodo_id).scalar()
    
    cobertura = (sucursales_supervisadas / total_sucursales * 100) if total_sucursales > 0 else 0
    
    return jsonify({
        'periodo': {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre
        },
        'kpis': {
            'promedio': float(promedio) if promedio else 0,
            'promedio_anterior': float(promedio_ant) if promedio_ant else None,
            'tendencia': get_trend(promedio, promedio_ant),
            'color': get_color_class(promedio),
            'supervisiones': len(supervisiones),
            'sucursales_supervisadas': sucursales_supervisadas or 0,
            'total_sucursales': total_sucursales,
            'cobertura': round(cobertura, 1)
        }
    })

@app.route('/api/ranking/grupos/<tipo>/<int:periodo_id>')
def api_ranking_grupos(tipo, periodo_id):
    """Ranking de grupos operativos"""
    periodo = PeriodoCAS.query.get_or_404(periodo_id)
    periodo_anterior = PeriodoCAS.query.filter(PeriodoCAS.id < periodo_id).order_by(desc(PeriodoCAS.id)).first()
    
    if tipo == 'operativas':
        Model = SupervisionOperativa
    else:
        Model = SupervisionSeguridad
    
    # Query para ranking actual
    ranking = db.session.query(
        GrupoOperativo.id,
        GrupoOperativo.nombre,
        func.avg(Model.calificacion_general).label('promedio'),
        func.count(Model.id).label('supervisiones')
    ).join(Sucursal, Sucursal.grupo_operativo_id == GrupoOperativo.id)\
     .join(Model, Model.sucursal_id == Sucursal.id)\
     .filter(Model.periodo_id == periodo_id)\
     .group_by(GrupoOperativo.id, GrupoOperativo.nombre)\
     .order_by(desc('promedio'))\
     .all()
    
    # Promedios del periodo anterior para tendencias
    promedios_ant = {}
    if periodo_anterior:
        ranking_ant = db.session.query(
            GrupoOperativo.id,
            func.avg(Model.calificacion_general).label('promedio')
        ).join(Sucursal, Sucursal.grupo_operativo_id == GrupoOperativo.id)\
         .join(Model, Model.sucursal_id == Sucursal.id)\
         .filter(Model.periodo_id == periodo_anterior.id)\
         .group_by(GrupoOperativo.id)\
         .all()
        promedios_ant = {r.id: float(r.promedio) if r.promedio else None for r in ranking_ant}
    
    result = []
    for i, r in enumerate(ranking, 1):
        promedio = float(r.promedio) if r.promedio else 0
        promedio_ant = promedios_ant.get(r.id)
        result.append({
            'posicion': i,
            'id': r.id,
            'nombre': r.nombre,
            'promedio': round(promedio, 1),
            'supervisiones': r.supervisiones,
            'color': get_color_class(promedio),
            'tendencia': get_trend(promedio, promedio_ant)
        })
    
    return jsonify(result)

@app.route('/api/ranking/sucursales/<tipo>/<int:periodo_id>')
def api_ranking_sucursales(tipo, periodo_id):
    """Ranking de sucursales"""
    if tipo == 'operativas':
        Model = SupervisionOperativa
    else:
        Model = SupervisionSeguridad
    
    ranking = db.session.query(
        Sucursal.id,
        Sucursal.nombre_corto,
        Sucursal.numero,
        GrupoOperativo.nombre.label('grupo'),
        func.avg(Model.calificacion_general).label('promedio'),
        func.count(Model.id).label('supervisiones')
    ).join(Model, Model.sucursal_id == Sucursal.id)\
     .outerjoin(GrupoOperativo, Sucursal.grupo_operativo_id == GrupoOperativo.id)\
     .filter(Model.periodo_id == periodo_id)\
     .group_by(Sucursal.id, Sucursal.nombre_corto, Sucursal.numero, GrupoOperativo.nombre)\
     .order_by(desc('promedio'))\
     .all()
    
    result = []
    for i, r in enumerate(ranking, 1):
        promedio = float(r.promedio) if r.promedio else 0
        result.append({
            'posicion': i,
            'id': r.id,
            'nombre': r.nombre_corto or f'Suc. {r.numero}',
            'numero': r.numero,
            'grupo': r.grupo,
            'promedio': round(promedio, 1),
            'supervisiones': r.supervisiones,
            'color': get_color_class(promedio)
        })
    
    return jsonify(result)

@app.route('/api/mapa/<tipo>/<int:periodo_id>')
def api_mapa(tipo, periodo_id):
    """Datos para el mapa"""
    if tipo == 'operativas':
        Model = SupervisionOperativa
    else:
        Model = SupervisionSeguridad
    
    # Obtener sucursales con sus promedios
    data = db.session.query(
        Sucursal.id,
        Sucursal.nombre_corto,
        Sucursal.numero,
        Sucursal.ciudad,
        Sucursal.estado,
        Sucursal.latitud,
        Sucursal.longitud,
        GrupoOperativo.nombre.label('grupo'),
        func.avg(Model.calificacion_general).label('promedio')
    ).outerjoin(Model, (Model.sucursal_id == Sucursal.id) & (Model.periodo_id == periodo_id))\
     .outerjoin(GrupoOperativo, Sucursal.grupo_operativo_id == GrupoOperativo.id)\
     .filter(Sucursal.activo == True)\
     .group_by(Sucursal.id, Sucursal.nombre_corto, Sucursal.numero, 
               Sucursal.ciudad, Sucursal.estado, Sucursal.latitud, 
               Sucursal.longitud, GrupoOperativo.nombre)\
     .all()
    
    result = []
    for s in data:
        if s.latitud and s.longitud:
            promedio = float(s.promedio) if s.promedio else None
            result.append({
                'id': s.id,
                'nombre': s.nombre_corto or f'Suc. {s.numero}',
                'numero': s.numero,
                'ciudad': s.ciudad,
                'estado': s.estado,
                'grupo': s.grupo,
                'lat': float(s.latitud),
                'lng': float(s.longitud),
                'promedio': round(promedio, 1) if promedio else None,
                'color': get_color_class(promedio),
                'supervisada': promedio is not None
            })
    
    return jsonify(result)

@app.route('/api/detalle/grupo/<int:grupo_id>/<tipo>/<int:periodo_id>')
def api_detalle_grupo(grupo_id, tipo, periodo_id):
    """Detalle de un grupo operativo"""
    grupo = GrupoOperativo.query.get_or_404(grupo_id)
    
    if tipo == 'operativas':
        Model = SupervisionOperativa
    else:
        Model = SupervisionSeguridad
    
    # Promedio del grupo
    promedio = db.session.query(func.avg(Model.calificacion_general))\
        .join(Sucursal, Model.sucursal_id == Sucursal.id)\
        .filter(Sucursal.grupo_operativo_id == grupo_id, Model.periodo_id == periodo_id)\
        .scalar()
    
    # Sucursales del grupo
    sucursales = db.session.query(
        Sucursal.id,
        Sucursal.nombre_corto,
        Sucursal.numero,
        func.avg(Model.calificacion_general).label('promedio'),
        func.count(Model.id).label('supervisiones')
    ).outerjoin(Model, (Model.sucursal_id == Sucursal.id) & (Model.periodo_id == periodo_id))\
     .filter(Sucursal.grupo_operativo_id == grupo_id, Sucursal.activo == True)\
     .group_by(Sucursal.id, Sucursal.nombre_corto, Sucursal.numero)\
     .order_by(desc('promedio'))\
     .all()
    
    # Tendencia histórica (últimos 4 periodos)
    periodos = PeriodoCAS.query.filter(PeriodoCAS.id <= periodo_id)\
        .order_by(desc(PeriodoCAS.id)).limit(4).all()
    
    tendencia = []
    for p in reversed(periodos):
        prom = db.session.query(func.avg(Model.calificacion_general))\
            .join(Sucursal, Model.sucursal_id == Sucursal.id)\
            .filter(Sucursal.grupo_operativo_id == grupo_id, Model.periodo_id == p.id)\
            .scalar()
        tendencia.append({
            'periodo': p.codigo,
            'promedio': round(float(prom), 1) if prom else None
        })
    
    return jsonify({
        'grupo': {
            'id': grupo.id,
            'nombre': grupo.nombre
        },
        'promedio': round(float(promedio), 1) if promedio else None,
        'color': get_color_class(promedio),
        'sucursales': [{
            'id': s.id,
            'nombre': s.nombre_corto or f'Suc. {s.numero}',
            'numero': s.numero,
            'promedio': round(float(s.promedio), 1) if s.promedio else None,
            'supervisiones': s.supervisiones,
            'color': get_color_class(s.promedio)
        } for s in sucursales],
        'tendencia': tendencia
    })

@app.route('/api/detalle/sucursal/<int:sucursal_id>/<tipo>/<int:periodo_id>')
def api_detalle_sucursal(sucursal_id, tipo, periodo_id):
    """Detalle de una sucursal con áreas/KPIs"""
    sucursal = Sucursal.query.get_or_404(sucursal_id)
    
    if tipo == 'operativas':
        # Última supervisión operativa
        supervision = SupervisionOperativa.query.filter_by(
            sucursal_id=sucursal_id, periodo_id=periodo_id
        ).order_by(desc(SupervisionOperativa.fecha_supervision)).first()
        
        areas = []
        if supervision:
            areas_data = db.session.query(
                CatalogoArea.nombre,
                SupervisionArea.porcentaje
            ).join(SupervisionArea, SupervisionArea.area_id == CatalogoArea.id)\
             .filter(SupervisionArea.supervision_id == supervision.id)\
             .order_by(SupervisionArea.porcentaje)\
             .all()
            
            areas = [{
                'nombre': a.nombre,
                'porcentaje': round(float(a.porcentaje), 1) if a.porcentaje else None,
                'color': get_color_class(a.porcentaje)
            } for a in areas_data]
        
        detalle_items = areas
        
    else:  # seguridad
        supervision = SupervisionSeguridad.query.filter_by(
            sucursal_id=sucursal_id, periodo_id=periodo_id
        ).order_by(desc(SupervisionSeguridad.fecha_supervision)).first()
        
        kpis = []
        if supervision:
            kpis_data = db.session.query(
                CatalogoKPISeguridad.nombre,
                SeguridadKPI.porcentaje
            ).join(SeguridadKPI, SeguridadKPI.kpi_id == CatalogoKPISeguridad.id)\
             .filter(SeguridadKPI.supervision_id == supervision.id)\
             .order_by(SeguridadKPI.porcentaje)\
             .all()
            
            kpis = [{
                'nombre': k.nombre,
                'porcentaje': round(float(k.porcentaje), 1) if k.porcentaje else None,
                'color': get_color_class(k.porcentaje)
            } for k in kpis_data]
        
        detalle_items = kpis
    
    # Tendencia histórica
    if tipo == 'operativas':
        Model = SupervisionOperativa
    else:
        Model = SupervisionSeguridad
    
    periodos = PeriodoCAS.query.filter(PeriodoCAS.id <= periodo_id)\
        .order_by(desc(PeriodoCAS.id)).limit(4).all()
    
    tendencia = []
    for p in reversed(periodos):
        sup = Model.query.filter_by(sucursal_id=sucursal_id, periodo_id=p.id).first()
        tendencia.append({
            'periodo': p.codigo,
            'promedio': round(float(sup.calificacion_general), 1) if sup and sup.calificacion_general else None
        })
    
    # Ranking de la sucursal
    subq = db.session.query(
        Model.sucursal_id,
        func.avg(Model.calificacion_general).label('promedio')
    ).filter(Model.periodo_id == periodo_id)\
     .group_by(Model.sucursal_id)\
     .subquery()
    
    ranking_pos = db.session.query(func.count())\
        .select_from(subq)\
        .filter(subq.c.promedio > (
            db.session.query(func.avg(Model.calificacion_general))
            .filter(Model.sucursal_id == sucursal_id, Model.periodo_id == periodo_id)
        )).scalar()
    
    return jsonify({
        'sucursal': {
            'id': sucursal.id,
            'nombre': sucursal.nombre_corto or sucursal.nombre,
            'numero': sucursal.numero,
            'grupo': sucursal.grupo.nombre if sucursal.grupo else None,
            'ciudad': sucursal.ciudad,
            'estado': sucursal.estado
        },
        'calificacion': round(float(supervision.calificacion_general), 1) if supervision and supervision.calificacion_general else None,
        'color': get_color_class(supervision.calificacion_general if supervision else None),
        'ranking': (ranking_pos or 0) + 1,
        'fecha': supervision.fecha_supervision.strftime('%d/%m/%Y') if supervision else None,
        'supervisor': supervision.supervisor if supervision else None,
        'detalle': detalle_items,
        'tendencia': tendencia
    })

@app.route('/api/alertas/<tipo>/<int:periodo_id>')
def api_alertas(tipo, periodo_id):
    """Alertas del periodo"""
    if tipo == 'operativas':
        Model = SupervisionOperativa
    else:
        Model = SupervisionSeguridad
    
    # Críticos (<70%)
    criticos = db.session.query(
        Sucursal.id,
        Sucursal.nombre_corto,
        Sucursal.numero,
        Model.calificacion_general,
        Model.fecha_supervision
    ).join(Model, Model.sucursal_id == Sucursal.id)\
     .filter(Model.periodo_id == periodo_id, Model.calificacion_general < 70)\
     .order_by(Model.calificacion_general)\
     .all()
    
    # Sin supervisar
    supervisadas = db.session.query(Model.sucursal_id)\
        .filter(Model.periodo_id == periodo_id)\
        .distinct()
    
    sin_supervisar = Sucursal.query.filter(
        Sucursal.activo == True,
        ~Sucursal.id.in_(supervisadas)
    ).all()
    
    return jsonify({
        'criticos': [{
            'id': c.id,
            'nombre': c.nombre_corto or f'Suc. {c.numero}',
            'calificacion': round(float(c.calificacion_general), 1),
            'fecha': c.fecha_supervision.strftime('%d/%m/%Y'),
            'color': get_color_class(c.calificacion_general)
        } for c in criticos],
        'sin_supervisar': [{
            'id': s.id,
            'nombre': s.nombre_corto or f'Suc. {s.numero}',
            'numero': s.numero
        } for s in sin_supervisar],
        'total_criticos': len(criticos),
        'total_sin_supervisar': len(sin_supervisar)
    })

@app.route('/api/historico/<tipo>')
def api_historico(tipo):
    """Histórico de todos los periodos"""
    if tipo == 'operativas':
        Model = SupervisionOperativa
    else:
        Model = SupervisionSeguridad
    
    periodos = PeriodoCAS.query.order_by(PeriodoCAS.anio, PeriodoCAS.id).all()
    
    result = []
    for p in periodos:
        promedio = db.session.query(func.avg(Model.calificacion_general))\
            .filter(Model.periodo_id == p.id).scalar()
        count = Model.query.filter_by(periodo_id=p.id).count()
        
        if count > 0:
            result.append({
                'id': p.id,
                'codigo': p.codigo,
                'nombre': p.nombre,
                'anio': p.anio,
                'promedio': round(float(promedio), 1) if promedio else None,
                'supervisiones': count,
                'color': get_color_class(promedio)
            })
    
    return jsonify(result)

# ============================================
# ADMIN ROUTES
# ============================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Login del admin"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        return render_template('admin_login.html', error='Contraseña incorrecta')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_panel():
    """Panel de administración"""
    periodos = PeriodoCAS.query.order_by(desc(PeriodoCAS.anio), desc(PeriodoCAS.id)).all()
    periodo_activo_id = get_config('periodo_activo')
    
    # Stats
    total_op = SupervisionOperativa.query.count()
    total_seg = SupervisionSeguridad.query.count()
    total_sucursales = Sucursal.query.filter_by(activo=True).count()
    total_grupos = GrupoOperativo.query.filter_by(activo=True).count()
    
    return render_template('admin.html',
                         periodos=periodos,
                         periodo_activo_id=int(periodo_activo_id) if periodo_activo_id else None,
                         total_op=total_op,
                         total_seg=total_seg,
                         total_sucursales=total_sucursales,
                         total_grupos=total_grupos)

@app.route('/admin/set-periodo', methods=['POST'])
@admin_required
def admin_set_periodo():
    """Establecer periodo activo"""
    periodo_id = request.form.get('periodo_id')
    set_config('periodo_activo', periodo_id, 'ID del periodo activo')
    return redirect(url_for('admin_panel'))

# ============================================
# INITIALIZE
# ============================================

def init_db():
    """Inicializar configuración del sistema"""
    with app.app_context():
        # Crear tabla config_sistema si no existe
        db.session.execute(text('''
            CREATE TABLE IF NOT EXISTS config_sistema (
                id SERIAL PRIMARY KEY,
                clave VARCHAR(50) UNIQUE NOT NULL,
                valor TEXT,
                descripcion VARCHAR(200)
            )
        '''))
        db.session.commit()

# ============================================
# RUN
# ============================================

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False').lower() == 'true')
