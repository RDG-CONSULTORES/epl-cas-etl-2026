-- ============================================================
-- EPL CAS ETL 2026 - Schema de Base de Datos
-- Usar para crear la estructura en staging (sin datos de produccion)
-- ============================================================

-- Periodos de evaluacion CAS
CREATE TABLE IF NOT EXISTS periodos_cas (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20),
    nombre VARCHAR(100),
    fecha_inicio DATE,
    fecha_fin DATE,
    activo BOOLEAN DEFAULT false
);

-- Grupos operativos (21 grupos)
CREATE TABLE IF NOT EXISTS grupos_operativos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    activo BOOLEAN DEFAULT true
);

-- Sucursales (86 sucursales)
CREATE TABLE IF NOT EXISTS sucursales (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    numero VARCHAR(20),
    estado VARCHAR(100),
    ciudad VARCHAR(100),
    grupo_operativo_id INTEGER REFERENCES grupos_operativos(id),
    latitud DECIMAL(10, 7),
    longitud DECIMAL(10, 7),
    clasificacion VARCHAR(20) DEFAULT 'local',
    activo BOOLEAN DEFAULT true,
    zenput_location_id VARCHAR(50)
);

-- Catalogo de 29 areas operativas
CREATE TABLE IF NOT EXISTS catalogo_areas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    numero INTEGER
);

-- Catalogo de 11 KPIs de seguridad
CREATE TABLE IF NOT EXISTS catalogo_kpis_seguridad (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    numero INTEGER
);

-- Supervisiones operativas
CREATE TABLE IF NOT EXISTS supervisiones_operativas (
    id SERIAL PRIMARY KEY,
    zenput_submission_id VARCHAR(50) UNIQUE,
    sucursal_id INTEGER REFERENCES sucursales(id),
    periodo_id INTEGER REFERENCES periodos_cas(id),
    supervisor VARCHAR(200),
    fecha_supervision TIMESTAMP,
    calificacion_general DECIMAL(5, 2),
    lat_entrega DECIMAL(10, 7),
    lon_entrega DECIMAL(10, 7)
);

-- Supervisiones de seguridad
CREATE TABLE IF NOT EXISTS supervisiones_seguridad (
    id SERIAL PRIMARY KEY,
    zenput_submission_id VARCHAR(50) UNIQUE,
    sucursal_id INTEGER REFERENCES sucursales(id),
    periodo_id INTEGER REFERENCES periodos_cas(id),
    supervisor VARCHAR(200),
    fecha_supervision TIMESTAMP,
    calificacion_general DECIMAL(5, 2)
);

-- Areas por supervision operativa (29 areas)
CREATE TABLE IF NOT EXISTS supervision_areas (
    id SERIAL PRIMARY KEY,
    supervision_id INTEGER REFERENCES supervisiones_operativas(id),
    area_id INTEGER REFERENCES catalogo_areas(id),
    porcentaje DECIMAL(5, 2),
    UNIQUE(supervision_id, area_id)
);

-- KPIs por supervision de seguridad (11 KPIs)
CREATE TABLE IF NOT EXISTS seguridad_kpis (
    id SERIAL PRIMARY KEY,
    supervision_id INTEGER REFERENCES supervisiones_seguridad(id),
    kpi_id INTEGER REFERENCES catalogo_kpis_seguridad(id),
    porcentaje DECIMAL(5, 2),
    UNIQUE(supervision_id, kpi_id)
);

-- Usuarios del sistema
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    email VARCHAR(200) NOT NULL UNIQUE,
    nombre VARCHAR(200) NOT NULL,
    password_hash VARCHAR(300) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'viewer',
    activo BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    nda_accepted_version INTEGER DEFAULT 0,
    nda_accepted_at TIMESTAMP
);

-- Credenciales WebAuthn (Face ID / Touch ID / Passkeys)
CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES usuarios(id),
    credential_id BYTEA NOT NULL UNIQUE,
    credential_public_key BYTEA NOT NULL,
    current_sign_count INTEGER DEFAULT 0,
    device_name VARCHAR(255),
    transports TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    evento VARCHAR(50) NOT NULL,
    email VARCHAR(200),
    ip VARCHAR(50),
    detalle VARCHAR(500),
    user_agent VARCHAR(500)
);

-- Checkpoints del ETL (ultima fecha de sync)
CREATE TABLE IF NOT EXISTS sync_checkpoints (
    formulario VARCHAR(100) PRIMARY KEY,
    ultima_fecha TIMESTAMP
);

-- Log de ejecuciones del ETL
CREATE TABLE IF NOT EXISTS sync_log (
    id SERIAL PRIMARY KEY,
    workflow VARCHAR(100),
    inicio TIMESTAMP,
    fin TIMESTAMP,
    registros_nuevos INTEGER DEFAULT 0,
    estado VARCHAR(20) DEFAULT 'running'
);

-- ============================================================
-- DATOS SEMILLA: Catalogos (necesarios para que funcione)
-- ============================================================

-- 29 Areas operativas
INSERT INTO catalogo_areas (nombre, codigo, numero) VALUES
('Proceso Marinado', 'PROCESO_MARINADO', 1),
('Cuarto Frio 1', 'CUARTO_FRIO_1', 2),
('Cuarto Frio 2', 'CUARTO_FRIO_2', 3),
('Area Cocina', 'AREA_COCINA', 4),
('Refrigeradores de Servicio', 'REFRIGERADORES_SERVICIO', 5),
('Almacen Jarabes', 'ALMACEN_JARABES', 6),
('Almacen General', 'ALMACEN_GENERAL', 7),
('Congelador Papa', 'CONGELADOR_PAPA', 8),
('Maquina de Hielo', 'MAQUINA_HIELO', 9),
('Bano Empleados', 'BANO_EMPLEADOS', 10),
('Lavado de Utensilios', 'LAVADO_UTENSILIOS', 11),
('Hornos', 'HORNOS', 12),
('Freidora de Papa', 'FREIDORA_PAPA', 13),
('Conservador Papa', 'CONSERVADOR_PAPA', 14),
('Asadores', 'ASADORES', 15),
('Barra de Servicio', 'BARRA_SERVICIO', 16),
('Comedor', 'COMEDOR', 17),
('Bano Clientes', 'BANO_CLIENTES', 18),
('Dispensador de Refrescos', 'DISPENSADOR_REFRESCOS', 19),
('Barra de Salsas', 'BARRA_SALSAS', 20),
('Tiempos de Servicio', 'TIEMPOS_SERVICIO', 21),
('Almacen Quimicos', 'ALMACEN_QUIMICOS', 22),
('Documentacion', 'DOCUMENTACION', 23),
('Area Marinado', 'AREA_MARINADO', 24),
('Cajas de Totopo', 'CAJAS_TOTOPO', 25),
('Plancha y Mesa', 'PLANCHA_MESA', 26),
('Freidoras', 'FREIDORAS', 27),
('Exterior', 'EXTERIOR', 28)
ON CONFLICT (codigo) DO NOTHING;

-- 11 KPIs de seguridad
INSERT INTO catalogo_kpis_seguridad (nombre, codigo, numero) VALUES
('Comedor', 'COMEDOR', 1),
('Asadores', 'ASADORES', 2),
('Area Marinado', 'AREA_MARINADO', 3),
('Bodega', 'BODEGA', 4),
('Hornos', 'HORNOS', 5),
('Freidoras', 'FREIDORAS', 6),
('Centro de Carga', 'CENTRO_CARGA', 7),
('Azotea', 'AZOTEA', 8),
('Exterior', 'EXTERIOR', 9),
('Proteccion Civil', 'PROTECCION_CIVIL', 10),
('Bitacoras', 'BITACORAS', 11)
ON CONFLICT (codigo) DO NOTHING;

-- Checkpoints iniciales del ETL
INSERT INTO sync_checkpoints (formulario, ultima_fecha) VALUES
('supervisiones_operativas', NULL),
('supervisiones_seguridad', NULL)
ON CONFLICT (formulario) DO NOTHING;

-- Un periodo de prueba
INSERT INTO periodos_cas (codigo, nombre, fecha_inicio, fecha_fin, activo) VALUES
('TEST-2026', 'Periodo de Prueba Staging', '2026-01-01', '2026-12-31', true)
ON CONFLICT DO NOTHING;
