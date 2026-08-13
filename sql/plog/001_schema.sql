-- Schema PLOG — aislado del dashboard CAS (no toca public ni operacion_diaria).
-- Filosofía raw-first: raw_submissions guarda TODO; lo derivado (cumplimiento,
-- calificaciones) es recomputable desde raw cuando cambia la config.

CREATE SCHEMA IF NOT EXISTS plog;
SET search_path TO plog, public;

-- ── Dimensiones ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sucursales (
    location_id     BIGINT PRIMARY KEY,          -- id Zenput
    nombre          TEXT NOT NULL,
    zona            TEXT NOT NULL,               -- nuevo_leon | laguna | queretaro
    director        TEXT,
    team_id         BIGINT,
    external_key    TEXT,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    es_comisariato  BOOLEAN NOT NULL DEFAULT FALSE,  -- editable en admin
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Config administrable (semilla = Excel v3 + correcciones; luego admin panel) ──
CREATE TABLE IF NOT EXISTS config_formularios (
    familia         TEXT NOT NULL,               -- clave del catálogo (ej. rl2_entrega_t2)
    zona            TEXT NOT NULL,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,   -- toggle admin: se ve / no se ve
    nombre          TEXT NOT NULL,
    medicion        TEXT NOT NULL,               -- cumplimiento | calificacion | ambos
    frecuencia      TEXT NOT NULL,               -- diario | diario_por_dia | semanal |
                                                 -- semana_del_mes | mensual | bimestral |
                                                 -- trimestral | semestral | por_visita
    hora_limite     TIME,                        -- para diarios; NULL = fin del periodo
    dias_gracia     INT NOT NULL DEFAULT 0,
    score_patron    TEXT,                        -- p1..p4 | NULL
    params          JSONB NOT NULL DEFAULT '{}', -- form_templates, serie, notas, etc.
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by      TEXT NOT NULL DEFAULT 'seed',
    PRIMARY KEY (familia, zona)
);

-- Bitácora de cambios de config (quién prendió/apagó qué y cuándo)
CREATE TABLE IF NOT EXISTS config_audit (
    id              BIGSERIAL PRIMARY KEY,
    familia         TEXT NOT NULL,
    zona            TEXT NOT NULL,
    cambios         JSONB NOT NULL,              -- {campo: {antes, despues}}
    usuario         TEXT NOT NULL,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Raw (se extrae TODO, inmutable) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw_submissions (
    submission_id    TEXT PRIMARY KEY,
    form_template_id BIGINT NOT NULL,
    familia          TEXT,                       -- resuelta al ingerir (NULL si form fuera de catálogo)
    location_id      BIGINT,
    zona             TEXT,
    fecha_local      DATE,                       -- date_created_local en TZ Monterrey
    ts_completed     TIMESTAMPTZ,
    created_by       TEXT,
    payload          JSONB NOT NULL,             -- submission completa (answers + smetadata)
    synced_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_raw_familia_loc_fecha ON raw_submissions (familia, location_id, fecha_local);
CREATE INDEX IF NOT EXISTS idx_raw_ft_fecha          ON raw_submissions (form_template_id, fecha_local);

CREATE TABLE IF NOT EXISTS sync_state (
    form_template_id BIGINT PRIMARY KEY,
    last_synced_at   TIMESTAMPTZ,
    last_ts_seen     TIMESTAMPTZ,                -- máxima fecha de submission vista
    total_ingeridas  BIGINT NOT NULL DEFAULT 0
);

-- ── Derivadas (recomputables desde raw + config) ───────────────────────────
CREATE TABLE IF NOT EXISTS cumplimiento (
    familia         TEXT NOT NULL,
    zona            TEXT NOT NULL,
    location_id     BIGINT NOT NULL,
    periodo_inicio  DATE NOT NULL,               -- inicio de la ventana esperada
    periodo_fin     DATE NOT NULL,
    estado          TEXT NOT NULL,               -- on_time | late | missed | pending
    submission_id   TEXT,                      -- la que cumplió (si hay)
    ts_submission   TIMESTAMPTZ,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (familia, location_id, periodo_inicio)
);
CREATE INDEX IF NOT EXISTS idx_cumpl_zona_periodo ON cumplimiento (zona, periodo_inicio);

CREATE TABLE IF NOT EXISTS calificaciones (
    submission_id   TEXT PRIMARY KEY REFERENCES raw_submissions(submission_id),
    familia         TEXT NOT NULL,
    zona            TEXT NOT NULL,
    location_id     BIGINT NOT NULL,
    fecha_local     DATE NOT NULL,
    score_total     NUMERIC(6,2),
    areas           JSONB NOT NULL DEFAULT '[]', -- [{area, score, puntos, puntos_max}]
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_calif_familia_fecha ON calificaciones (familia, zona, fecha_local);
