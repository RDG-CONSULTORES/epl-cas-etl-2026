-- ============================================================
-- 002_tables.sql — modelo de datos operacion_diaria
-- ============================================================

SET search_path TO operacion_diaria;

CREATE TABLE IF NOT EXISTS dim_sucursales (
    location_id      BIGINT PRIMARY KEY,
    nombre           TEXT NOT NULL,
    go_id            BIGINT,
    go_nombre        TEXT,
    has_epl_cas_tag  BOOLEAN DEFAULT FALSE,
    is_active        BOOLEAN DEFAULT TRUE,
    last_synced_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dim_grupos_operativos (
    go_id            BIGINT PRIMARY KEY,
    nombre           TEXT NOT NULL,
    director         TEXT,
    n_sucursales     INT DEFAULT 0,
    is_epl_cas       BOOLEAN DEFAULT TRUE,
    last_synced_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_compliance (
    sucursal_id      BIGINT NOT NULL,
    day              DATE NOT NULL,
    form_key         TEXT NOT NULL,
    project_id       BIGINT NOT NULL,
    form_template_id BIGINT NOT NULL,
    status           TEXT NOT NULL,
    score            NUMERIC(3,2) NOT NULL,
    submission_id    TEXT,
    task_id          BIGINT,
    completed_at     TIMESTAMPTZ,
    last_updated_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (sucursal_id, day, form_key)
);

CREATE TABLE IF NOT EXISTS weekly_summary (
    week_start       DATE NOT NULL,
    scope            TEXT NOT NULL,
    scope_id         BIGINT,
    form_key         TEXT NOT NULL,
    n_on_time        INT DEFAULT 0,
    n_late           INT DEFAULT 0,
    n_missed         INT DEFAULT 0,
    n_total          INT DEFAULT 0,
    sum_score        NUMERIC(8,2) DEFAULT 0,
    pct_compliance   NUMERIC(5,2),
    delta_prev_week  NUMERIC(5,2),
    computed_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (week_start, scope, scope_id, form_key)
);

CREATE TABLE IF NOT EXISTS monthly_summary (
    month_start      DATE NOT NULL,
    scope            TEXT NOT NULL,
    scope_id         BIGINT,
    form_key         TEXT NOT NULL,
    n_on_time        INT DEFAULT 0,
    n_late           INT DEFAULT 0,
    n_missed         INT DEFAULT 0,
    n_total          INT DEFAULT 0,
    pct_compliance   NUMERIC(5,2),
    delta_prev_month NUMERIC(5,2),
    computed_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (month_start, scope, scope_id, form_key)
);

CREATE TABLE IF NOT EXISTS etl_runs (
    id               BIGSERIAL PRIMARY KEY,
    job_name         TEXT NOT NULL,
    started_at       TIMESTAMPTZ DEFAULT NOW(),
    finished_at      TIMESTAMPTZ,
    status           TEXT,
    rows_affected    INT,
    error_message    TEXT,
    metadata         JSONB
);
