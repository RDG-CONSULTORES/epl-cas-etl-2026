-- ============================================================
-- 001_schema_and_user.sql
-- Crea schema aislado + usuario de app con privilegios scoped.
-- IMPORTANTE: reemplazar CAMBIAR_ESTE_PASSWORD_ANTES_DE_EJECUTAR
-- por un password fuerte (openssl rand -base64 24) ANTES de correr.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS operacion_diaria;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'operacion_diaria_app') THEN
        CREATE USER operacion_diaria_app WITH PASSWORD 'CAMBIAR_ESTE_PASSWORD_ANTES_DE_EJECUTAR';
    END IF;
END
$$;

GRANT USAGE, CREATE ON SCHEMA operacion_diaria TO operacion_diaria_app;
GRANT ALL ON ALL TABLES IN SCHEMA operacion_diaria TO operacion_diaria_app;
GRANT ALL ON ALL SEQUENCES IN SCHEMA operacion_diaria TO operacion_diaria_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA operacion_diaria GRANT ALL ON TABLES TO operacion_diaria_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA operacion_diaria GRANT ALL ON SEQUENCES TO operacion_diaria_app;
REVOKE ALL ON SCHEMA public FROM operacion_diaria_app;
