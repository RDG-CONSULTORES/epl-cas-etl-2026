-- ============================================================
-- 003_indexes.sql — índices para queries del dashboard
-- ============================================================

SET search_path TO operacion_diaria;

CREATE INDEX IF NOT EXISTS idx_daily_compliance_day ON daily_compliance(day);
CREATE INDEX IF NOT EXISTS idx_daily_compliance_form ON daily_compliance(form_key, day);
CREATE INDEX IF NOT EXISTS idx_daily_compliance_sucursal_day ON daily_compliance(sucursal_id, day DESC);
CREATE INDEX IF NOT EXISTS idx_weekly_summary_week ON weekly_summary(week_start DESC);
CREATE INDEX IF NOT EXISTS idx_weekly_summary_scope ON weekly_summary(scope, scope_id, week_start DESC);
CREATE INDEX IF NOT EXISTS idx_monthly_summary_month ON monthly_summary(month_start DESC);
CREATE INDEX IF NOT EXISTS idx_monthly_summary_scope ON monthly_summary(scope, scope_id, month_start DESC);
CREATE INDEX IF NOT EXISTS idx_etl_runs_started ON etl_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_dim_sucursales_go ON dim_sucursales(go_id);
