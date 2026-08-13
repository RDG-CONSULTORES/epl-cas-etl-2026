SET search_path TO plog, public;
CREATE TABLE IF NOT EXISTS report_schedules (
    id           BIGSERIAL PRIMARY KEY,
    nombre       TEXT NOT NULL,
    cadencia     TEXT NOT NULL,            -- semanal|quincenal|mensual|bimestral|trimestral|semestral|anual
    canal        TEXT NOT NULL DEFAULT 'correo',  -- correo|whatsapp|push
    destinatarios TEXT[] NOT NULL DEFAULT '{}',   -- correos o usuarios
    zona         TEXT,                     -- NULL = todas (respeta scope del destinatario)
    activo       BOOLEAN NOT NULL DEFAULT TRUE,
    creado_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by   TEXT
);
