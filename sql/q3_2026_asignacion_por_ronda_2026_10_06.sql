-- ============================================================
-- EPL CAS — Reasignación por RONDA (Q1/Q2/Q3 2026) · 2026-10-06
-- ============================================================
-- Regla de negocio (Roberto): el trimestre NO es calendario; cada sucursal
-- recibe UNA visita por ronda y la ronda cierra cuando todas las que aplican
-- fueron auditadas (los cortes se recorren).
--
-- Peinado de prod 2026-10-06 (verificado por recálculo independiente):
--   * 5 visitas de la ronda Q2 hechas a inicios de julio quedaron en Q3 en el
--     corte del 23-jul → regresan a Q2 (operativa + seguridad de la misma visita):
--       Guasave 6/7-jul, Constituyentes 30-jun (guardada en UTC 1-jul),
--       Huerta 1-jul, Madero (Morelia) 1-jul, Lázaro Cárdenas (Morelia) 2-jul.
--   * Seguridad de Guasave 13-abr quedó en Q2 y su operativa en Q1 → Q1.
--   * 88 - Linares es nueva (0 supervisiones) → no entra al universo de Q3;
--     empieza a contar en Q4 (sucursales.activa_desde_periodo_id).
--
-- Resultado esperado: Q1 83/83 aplicables (Otilio abrió en jun), Q2 84/84, Q3 83/84 (falta Guasave).
--
-- Idempotente: cada UPDATE filtra por id + sucursal + submission de Zenput +
-- periodo actual; si el dato ya no está como se encontró, no toca nada y el
-- bloque de verificación final aborta la transacción.
-- ============================================================

BEGIN;

-- 1) Columna para sucursales que empiezan a contar en un periodo futuro
ALTER TABLE sucursales
    ADD COLUMN IF NOT EXISTS activa_desde_periodo_id INTEGER REFERENCES periodos_cas(id);

-- 2) Q3 → Q2: visitas tardías de la ronda Q2 (operativas)
UPDATE supervisiones_operativas so SET periodo_id = q2.id
FROM periodos_cas q2, periodos_cas q3
WHERE q2.codigo = 'Q2-2026' AND q3.codigo = 'Q3-2026' AND so.periodo_id = q3.id
  AND (so.id, so.sucursal_id) IN (
        (408, 16),   -- 23 - Guasave            7-jul
        (403, 47),   -- 51 - Constituyentes     30-jun (UTC 1-jul)
        (405, 60),   -- 63 - Madero (Morelia)   1-jul
        (406, 61),   -- 64 - Huerta             1-jul
        (407, 59));  -- 62 - Lázaro C. (Morelia) 2-jul

-- 3) Q3 → Q2: la seguridad de esas mismas visitas
UPDATE supervisiones_seguridad ss SET periodo_id = q2.id
FROM periodos_cas q2, periodos_cas q3
WHERE q2.codigo = 'Q2-2026' AND q3.codigo = 'Q3-2026' AND ss.periodo_id = q3.id
  AND (ss.id, ss.sucursal_id) IN ((408, 16), (403, 47), (405, 60), (406, 61), (407, 59));

-- 4) Q2 → Q1: seguridad de Guasave 13-abr (su operativa ya está en Q1)
UPDATE supervisiones_seguridad ss SET periodo_id = q1.id
FROM periodos_cas q1, periodos_cas q2
WHERE q1.codigo = 'Q1-2026' AND q2.codigo = 'Q2-2026' AND ss.periodo_id = q2.id
  AND ss.id = 324 AND ss.sucursal_id = 16;

-- 5) Linares fuera del universo de Q3; el ETL la activa al abrir Q4
UPDATE sucursales SET activo = false,
       activa_desde_periodo_id = (SELECT id FROM periodos_cas WHERE codigo = 'Q4-2026')
WHERE id = 65 AND nombre = '88 - Linares' AND activo AND activa_desde_periodo_id IS NULL
  AND (SELECT activo FROM periodos_cas WHERE codigo = 'Q3-2026')
  AND NOT EXISTS (SELECT 1 FROM supervisiones_operativas WHERE sucursal_id = 65
                  AND periodo_id IN (SELECT id FROM periodos_cas WHERE codigo IN ('Q1-2026','Q2-2026','Q3-2026')));

-- 6) Verificación: si algo no cuadra, se aborta todo
DO $$
DECLARE r RECORD; universo INT;
BEGIN
    SELECT COUNT(*) INTO universo FROM sucursales WHERE activo;
    IF universo <> 84 THEN RAISE EXCEPTION 'Universo activo = %, se esperaba 84', universo; END IF;

    FOR r IN
        SELECT p.codigo,
               (SELECT COUNT(DISTINCT so.sucursal_id) FROM supervisiones_operativas so
                  JOIN sucursales s ON s.id = so.sucursal_id AND s.activo WHERE so.periodo_id = p.id) op,
               (SELECT COUNT(DISTINCT ss.sucursal_id) FROM supervisiones_seguridad ss
                  JOIN sucursales s ON s.id = ss.sucursal_id AND s.activo WHERE ss.periodo_id = p.id) seg,
               (SELECT COUNT(*) FROM (SELECT so.sucursal_id FROM supervisiones_operativas so
                  WHERE so.periodo_id = p.id GROUP BY 1 HAVING COUNT(*) > 1) d) dup_op,
               (SELECT COUNT(*) FROM (SELECT ss.sucursal_id FROM supervisiones_seguridad ss
                  WHERE ss.periodo_id = p.id GROUP BY 1 HAVING COUNT(*) > 1) d) dup_seg
        FROM periodos_cas p WHERE p.codigo IN ('Q1-2026','Q2-2026','Q3-2026')
    LOOP
        RAISE NOTICE '% → operativa %/84 · seguridad %/84 · repetidas op % seg %', r.codigo, r.op, r.seg, r.dup_op, r.dup_seg;
        IF r.dup_op > 0 OR r.dup_seg > 0 THEN RAISE EXCEPTION '% tiene sucursales repetidas', r.codigo; END IF;
        -- Q1: OTILIO GONZALEZ (id 66) abrió en junio → no aplica, 83 de 83 aplicables
        IF r.codigo = 'Q1-2026' AND (r.op <> 83 OR r.seg <> 83) THEN
            RAISE EXCEPTION 'Q1 no quedó 83/83 aplicables (op %, seg %)', r.op, r.seg; END IF;
        IF r.codigo = 'Q2-2026' AND (r.op <> 84 OR r.seg <> 84) THEN
            RAISE EXCEPTION 'Q2 no quedó 84/84 (op %, seg %)', r.op, r.seg; END IF;
        IF r.codigo = 'Q3-2026' AND (r.op <> 83 OR r.seg <> 83) THEN
            RAISE EXCEPTION 'Q3 no quedó 83/84 (op %, seg %)', r.op, r.seg; END IF;
    END LOOP;

    IF EXISTS (SELECT 1 FROM supervisiones_operativas so JOIN periodos_cas p ON p.id = so.periodo_id
               WHERE so.sucursal_id = 16 AND p.codigo = 'Q3-2026') THEN
        RAISE EXCEPTION 'Guasave todavía tiene operativa en Q3'; END IF;
END $$;

COMMIT;
