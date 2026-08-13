# Auditoría A-Z — Sistema de Cumplimiento PLOG (2026-08-13)

Estado real verificado con la data y el código, no de memoria. Semáforo: ✅ listo · 🟡 parcial/con deuda · 🔴 no existe.

## Resumen ejecutivo
El **cimiento de datos y diseño está sólido** (ETL, catálogo, config, clasificación, blueprint, mockup). Lo que falta es **casi toda la capa de producto** (motor v2, calificaciones, auth, API, admin, frontend real, reportes, deploy) — es normal, apenas terminamos discovery+diseño. **2 riesgos inmediatos:** (1) nada está en git aún, (2) el % de cumplimiento tiene un sesgo conocido (serie A/L) que infla los faltantes.

---

## A · Datos / ETL — ✅ sólido, 🟡 1 optimización pendiente
- ✅ 44,838 submissions, rango jun-2025→ago-2026. **Cero** nulos de fecha, cero huérfanos, cero duplicados, cero fechas futuras. Integridad impecable.
- ✅ 100% de sucursales PLOG (cero foráneas). Depósito por zona (3 templates) OK.
- 🟡 **Sync no optimizado:** el API ignora `start_date` → cada corrida re-escanea todo. A escala horaria re-baja 45k/hora. **Falta corte incremental** (parar al topar submissions conocidas). Bloquea la cadencia horaria en prod.
- 🟡 Falta: reconciliación semanal (full-refresh), soft-delete, freshness SLA visible.

## B · Motor de cumplimiento — 🟡 v1 funciona, 7 deudas
- ✅ Genera 4 estados, corre E2E (5,174 ventanas).
- 🔴 **Solo calculado jun29–ago10 (~6 semanas), NO el histórico completo** (hay data desde jun-2025 → falta para comparativos YoY).
- 🔴 **Sesgo serie A/L: 124 "faltó" falsos** solo en Laguna (cuenta la serie que la tienda no usa). Infla incumplimiento HOY. Alta prioridad.
- 🔴 Sin freeze/policy_snapshot (histórico muta si cambia política) · sin expected_occurrence materializada · sin effectivity · submission_id no se guarda en cumplimiento (V4 no liga).
- 🟡 `sucursales_aplica` texto libre sin interpretar: **Flotilla** (vehículos = por unidad, hoy se mide por tienda) y **Donde haya hallazgos** (visita_seguimiento = condicional, no debe generar expectativa).

## C · Calificaciones — 🔴 no construido (spec listo)
- ✅ drilldown_spec mapeado (áreas por form, 4 patrones P1-P4).
- 🔴 **Módulo extractor NO existe. Tabla `calificaciones` = 0 filas.** Todo el drill-down de áreas del mockup es demo hasta esto.
- 🟡 Pendientes ya identificados: bug extractor P3 (mtto sale 0), clamp pro_suc_1 (>100%), par revisión+gestión=100, auditoría (fórmulas genéricas hasta 1er envío).

## D · Catálogo y config — ✅ sólido
- ✅ 29 familias, form_template_ids verificados, cadencias detectadas de data, origen/caso_uso/quien_llena clasificado y VISIBLE para admin, bitácora config_audit, series A/L/S resueltas.
- ✅ 5 en espera con formulación extraída, listos para activar.

## E · Comisariatos — 🟡 parcial
- ✅ 3 virtuales por zona + 4 tiendas anfitrionas marcadas. Categoría propia (Recorrido + PRO-COM-2).
- 🔴 Solo responsable NL (Galilea) mapeado → **Qro y Laguna sin atribuir** (salen 0%). Falta confirmar responsables con directores.

## F · Auth / seguridad — 🔴 no existe
- 🔴 **0 usuarios, sin login, sin roles, sin scopes.** Toda la capa de acceso (admin/director/viewer, scope por zona+sucursal) por construir.
- ✅ Token Zenput en `.env` gitignoreado, no hardcodeado en código.

## G · Backend / API — 🔴 no existe
- 🔴 Sin FastAPI, sin endpoints. El mockup no lee de ningún backend. Es la capa que conecta BD↔frontend con scoping — por construir entera.

## H · Frontend — 🟡 solo mockup
- ✅ Mockup de 4 vistas, on-brand, datos reales en agregados, badges de origen, drill-down coherente.
- 🔴 No es PWA real (sin manifest/service worker/instalable), no cableado a backend, sparklines/áreas aún demo.

## I · Reportes / entrega — 🔴 no existe
- 🔴 Sin generador de reportes (semanal…anual+comparativos), sin correo (Resend), sin capa notificaciones. Todo por construir.

## J · Deploy / infraestructura — 🔴 local + ⚠️ RIESGO
- 🔴 Todo corre en BD local `epl_plog_local`. Nada en Railway (schema plog, crons, servicio web, secrets).
- ⚠️ **`etl_plog/` NO está en git (untracked).** Todo el trabajo (código+docs+config) sin respaldar. Riesgo de pérdida. Roberto pidió históricamente commitear todo.

## K · Inputs de negocio pendientes — 🟡
- Cadencias: 16 detectadas a confirmar + 4 nuevos por definir (directores).
- Política Depósito (¿≥1/día o N?), responsables comisariato Qro/Laguna, clamp bonus pro_suc_1, quién recibe reportes, quiénes son los usuarios del dashboard.

## L · Tests — 🔴 cero
- 🔴 0 archivos de test. El motor (corazón) sin cobertura. Riesgo alto al construir encima.

## M · Documentación — ✅ excelente
- ✅ 9 docs (blueprint, 4 researches, gaps, estrategia, visibilidad, formulación, diccionario) + memoria. Muy por encima del promedio.

---

## Prioridades recomendadas (orden)
1. **🔴 AHORA: commitear `etl_plog/` a git** (respaldo — 5 min, evita perder todo).
2. **🔴 Motor v2** con los 7 arreglos — especialmente serie A/L (124 falsos) y freeze. + tests. Recalcular histórico completo.
3. **🔴 Extractor de calificaciones** (P1-P4 + fixes) → poblar tabla, drill-down real.
4. **🔴 Auth + API FastAPI** con scoping.
5. **🟡 Sync optimizado** (corte incremental) antes del cron horario.
6. **PWA real + admin + reportes → deploy Railway.**
7. Cerrar inputs de negocio con directores (paralelo, no bloquea).
