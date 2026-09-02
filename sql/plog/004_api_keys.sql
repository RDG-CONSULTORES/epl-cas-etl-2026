-- API read-only para consumidores externos (ej. sistemas EPL / Homero).
-- Filosofía: NUNCA se comparte la BD ni el esquema interno; solo esta superficie
-- versionada (/api/v1) autenticada por API key. Cada key es revocable, acotable
-- por zona y auditada llamada por llamada.

SET search_path TO plog, public;

-- ── Llaves de API (una por consumidor) ─────────────────────────────────────
-- Guardamos SOLO el hash SHA-256 de la llave (nunca el texto). El prefijo visible
-- (primeros chars) sirve para identificarla en logs y en el admin sin exponerla.
CREATE TABLE IF NOT EXISTS api_keys (
    id           BIGSERIAL PRIMARY KEY,
    etiqueta     TEXT NOT NULL,                 -- ej. "EPL - Homero (sistemas)"
    key_prefix   TEXT NOT NULL,                 -- ej. plog_live_a1b2c3 (para identificar)
    key_hash     TEXT NOT NULL UNIQUE,          -- sha256(llave completa)
    zonas        TEXT[],                        -- NULL = todas las zonas; si no, acota
    activo       BOOLEAN NOT NULL DEFAULT TRUE, -- revocación = poner en FALSE
    creado_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    creado_por   TEXT NOT NULL DEFAULT 'admin',
    ultimo_uso   TIMESTAMPTZ,
    llamadas     BIGINT NOT NULL DEFAULT 0,
    notas        TEXT
);

-- ── Bitácora de acceso (auditoría por llamada) ─────────────────────────────
CREATE TABLE IF NOT EXISTS api_access_log (
    id        BIGSERIAL PRIMARY KEY,
    key_id    BIGINT REFERENCES api_keys(id),
    ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    ip        TEXT,
    metodo    TEXT,
    path      TEXT,
    query     TEXT,
    status    INT,
    filas     INT
);
CREATE INDEX IF NOT EXISTS idx_apilog_key_ts ON api_access_log (key_id, ts);
