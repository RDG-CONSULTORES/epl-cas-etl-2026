-- Auth y accesos segmentados para el dashboard PLOG. Aislado en schema plog.
SET search_path TO plog, public;

CREATE TABLE IF NOT EXISTS usuarios (
    id            BIGSERIAL PRIMARY KEY,
    usuario       TEXT UNIQUE NOT NULL,          -- login (sin correo obligatorio)
    nombre        TEXT,
    password_hash TEXT NOT NULL,                 -- bcrypt
    rol           TEXT NOT NULL DEFAULT 'viewer', -- admin | director | viewer
    activo        BOOLEAN NOT NULL DEFAULT TRUE,
    creado_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_login  TIMESTAMPTZ,
    intentos_fallidos INT NOT NULL DEFAULT 0,
    bloqueado_hasta   TIMESTAMPTZ
);

-- Scope por usuario: cada fila autoriza una zona (o toda) y opcionalmente una
-- lista de sucursales. Sin filas = no ve nada. zona NULL = todas las zonas.
CREATE TABLE IF NOT EXISTS user_scopes (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    zona         TEXT,                            -- NULL = todas
    location_ids BIGINT[],                        -- NULL = todas las de la zona
    UNIQUE (user_id, zona)
);

-- Sesiones server-side (la cookie solo lleva el token opaco).
CREATE TABLE IF NOT EXISTS sesiones (
    token      TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    creada_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expira_at  TIMESTAMPTZ NOT NULL,
    ultimo_uso TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_agent TEXT
);
CREATE INDEX IF NOT EXISTS idx_sesiones_user ON sesiones (user_id);

-- Bitácora de accesos (login/logout/denegado) — auditoría de seguridad.
CREATE TABLE IF NOT EXISTS acceso_audit (
    id       BIGSERIAL PRIMARY KEY,
    usuario  TEXT,
    evento   TEXT NOT NULL,       -- login_ok | login_fail | logout | bloqueado
    detalle  TEXT,
    ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);
