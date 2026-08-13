# Diccionario de Datos PLOG — Discovery Zenput (Fase 0)
**Fecha:** 2026-08-11 · **Fuente:** API Zenput v3 en vivo (token verificado) + Excel `Definicion_Politicas_Formularios_PLOG_v3`
**Generado por:** discovery automatizado en `etl_plog/discovery/` (raw JSONs en `data/`)

## 1. Sucursales PLOG (18, verificadas en vivo)

| Loc ID | Sucursal | Director (team) | Zona |
|---|---|---|---|
| 2247034 | 35 - Apodaca | Lourdes Azuara | Nuevo León |
| 2247035 | 36 - Apodaca Centro | Lourdes Azuara | Nuevo León |
| 2247036 | 37 - Stiva | Lourdes Azuara | Nuevo León |
| 2247037 | 38 - Gomez Morin | Jesus Arellano | Nuevo León |
| 2247038 | 39 - Lazaro Cardenas | Jesus Arellano | Nuevo León |
| 2247039 | 40 - Plaza 1500 | Lourdes Azuara | Nuevo León |
| 2247040 | 41 - Vasconcelos | Jesus Arellano | Nuevo León |
| 2247041 | 42 - Independencia | Jose Angel Barbosa | Laguna |
| 2247042 | 43 - Revolucion | Jose Angel Barbosa | Laguna |
| 2247043 | 44 - Senderos | Jose Angel Barbosa | Laguna |
| 2247044 | 45 - Triana | Jose Angel Barbosa | Laguna |
| 2247045 | 46 - Campestre | Jose Angel Barbosa | Laguna |
| 2247046 | 47 - San Antonio | Jose Angel Barbosa | Laguna |
| 2247047 | 48 - Refugio | Martin Sanchez | Querétaro |
| 2247048 | 49 - Pueblito | Martin Sanchez | Querétaro |
| 2247049 | 50 - Patio | Martin Sanchez | Querétaro |
| 2247050 | 51 - Constituyentes | Martin Sanchez | Querétaro |
| 2261286 | 86 - Miguel de la Madrid | Lourdes Azuara | Nuevo León |

Teams: PLOG Nuevo Leon 115099 (directores Jesús Arellano 115119, Lourdes Azuara 115751) · PLOG Laguna 115106 (José Ángel Barbosa 115129) · PLOG Queretaro 115107 (Martín Sánchez 115131)

## 2. Reglas de extracción (verificadas empíricamente)

1. **La mayoría de los forms PLOG NO tienen activity** → query por `form_template_id`. Solo ~15 tienen activity (lista abajo).
2. **Varios forms son COMPARTIDOS con sucursales CAS** (ej. Mtto Mensual: solo 12/40 submissions recientes son PLOG; PRO-SUC-1 901109: 2/40) → **filtrado client-side por `smetadata.location.id` ∈ las 18 locs PLOG es OBLIGATORIO** en todos.
3. Filtros de fecha del query se ignoran → filtrar client-side por `smetadata.date_created_local` (epoch ms).
4. Depósito de Valores NL (997145) tiene >10k submissions → backfill vía endpoint Large Batch (cursor `next_token`).
5. Bonus points existen: PRO-SUC-1 2025V1 muestra 104.17% → no clampear a 100 sin decidirlo con PLOG.

## 3. Catálogo de formularios — cumplimiento (solo existencia + ventana, NO requiere parsear contenido)

| Form ID(s) | Formulario | Activity | Data viva |
|---|---|---|---|
| A1 954598 · A2 1040520 · A3 1040521 · A4 1040522 · A5 1040523 · A6 1040524 · A7 1010538 | Alistamiento diario serie A (Lun–Dom) | — | ✅ 2026-08-11 |
| L1 1040507 · L2 1040506 · L3 1040504 · L4 1040505 · L5 1038660 · L6 1038659 · L7 1038658 | Alistamiento diario serie L (Lun–Dom) | — | ✅ 2026-08-10 |
| 954595 | RL1 Entrega Primer Turno | — | ✅ hoy |
| 954602 | RL2 Entrega Segundo Turno | — | ✅ hoy |
| 1040519 | Checklist de Cierre | — | ✅ hoy |
| 997145 (NL) / 1043394 (Laguna, act 1041999) / 1043393 (QRO, act 1041998) | Depósito de Valores | parcial | ✅ hoy |
| 1108481 | SUC-F0-141 Conteo Diario de Pollo | 1107067 | ⚠️ últ. 2026-05-24 (stale) |
| 1059179 | Alistamiento Regional Visita Negocio | — | ✅ 2026-08-05 |
| 954591 | Alistamiento Regional Visita Seguimiento | — | ✅ 2026-07-29 |
| 954604 | RH-1 Alistamiento visita Regional | — | ✅ hoy |
| 1161752 | Recorrido Diario Comisariato | 1160317 | ✅ 2026-08-05 |
| 954594 | PRO-CSC-5 Revisión Vehículos PLOG | — | ⚠️ últ. 2026-06-03 |

## 4. Catálogo de formularios — con calificación (score + drill-down por área)

Patrones de score encontrados (4 distintos — el extractor debe soportar los 4):
- **P1 "PORCENTAJE %"** (patrón CAS): formula `PORCENTAJE %` o `CALIFICACION PORCENTAJE %` = total; áreas = formulas `<AREA> ... PORCENTAJE %`.
- **P2 "(100%)"**: formula `<nombre form> (100%)` o `Puntuación (100%)` = total; áreas = formulas `<Área> (100%)` / `<Área> Puntuación (100%)`; gemelas `(N Puntos)` = puntos crudos.
- **P3 "Calificación General"** (Mtto): formula `Calificación General ...` = total; áreas = formulas `AREA <X>`; sub-ítems `Calificación <equipo>`. OJO: muchas en None si no aplica.
- **P4 secciones ponderadas** (forms nuevos PLOG): `SUBTOTAL - <SECCIÓN>` + `RESULTADO TOTAL SOBRE N%`. **REVISIÓN OPERATIVA (62%) + GESTIÓN Y FINANZAS (38%) = calificación combinada 100%** — son un par diseñado para sumarse.

| Form ID | Formulario | Activity | Patrón score | Campo total (muestra) | Data viva |
|---|---|---|---|---|---|
| 1040698 | Alistamiento SERVIR | — | P2 | Revisión de proceso (100%) | ✅ hoy |
| 997146 | Alistamiento Hornos | — | P2 | Alistamiento Diario de Hornos (100%) | ✅ hoy |
| 1560060 | Autogestión Calidad S1 | 1558608 | P1 | PORCENTAJE % | ✅ 08-09 |
| 1568530 | Autogestión Calidad S2 | 1567076 | P1 | PORCENTAJE % | ✅ 07-15 |
| 1568532 | Autogestión Calidad S3 | 1567078 | P1 | PORCENTAJE % | ✅ 07-23 |
| 1568536 | Autogestión Calidad S4 | 1567082 | P1 | PORCENTAJE % | ✅ 07-29 |
| 954596 | PRO-SUC-4 Autoevaluación | — | P2 | PRO-SUC-4 ... Puntuación (100%) | ✅ 08-10 |
| 1572636 | Mtto Preventivo Mensual | 1571178 | P3 | Calificación General Mtto Mensual | ✅ hoy |
| 1572200 | Mtto Preventivo Trimestral | 1570742 | P3 | Calificación General | ✅ 08-10 |
| 1572620 | Mtto Preventivo Semestral | 1571162 | P3 | Calificación General | ✅ 07-28 |
| 901109 | PRO-SUC-1 Evaluación | 888704 | P1 | PORCENTAJE % | ⚠️ compartido CAS (2/40 PLOG) |
| 954592 | PRO-SUC-1.1 | — | P2 | Procesos Op. Gerente Puntuación (100%) | ✅ 08 |
| 954599 | PRO-SUC-1 2025V1 ⚠️NO en Excel | — | P2 | PRO-SUC-1 ... (100%) | ✅ 08-10, 40/40 PLOG |
| 1038657 | PRO-SUC-3 | — | P2 | Procesos Op. Gerente Puntuación (100%) | ✅ 08-10 |
| 1059183 | PRO-SUC-3.1 | — | P2 | Puntuación (100%) | ✅ 08 |
| 1161748 | *DO Supervisión Operativa 1.2 | 1160313 | P1 | PORCENTAJE % | ✅ 08-07, compartido |
| 1161749 | *DO Control Op. Seguridad 1.2 | 1160314 | P1 | CALIFICACION PORCENTAJE % | ✅ 08-06, compartido |
| 954593 | VCAL25 Verificación Calidad | — | P2 | Puntuación (100%) | ⚠️ últ. 2025-11-01 |
| 1059169 | VCALQRO | — | P2 | Puntuación (100%) | ⚠️ últ. 2025 (8 subs) |
| 954601 | PRO-COM-2 Comisariato | — | P2 | Evaluación Comisariatos Puntuación (100%) | ✅ 07-31 |
| 954603 | PRO-SC-6 Seguridad | — | P2 | Seguridad General Puntuación (100%) | ⚠️ últ. 2025-12-09 |
| 1638930 | REVISIÓN OPERATIVA PLOG 🆕 | 1637360 | P4 | RESULTADO TOTAL SOBRE 62% | 5 subs, 07-14 |
| 1638942 | GESTIÓN Y FINANZAS PLOG 🆕 | 1637372 | P4 | RESULTADO TOTAL DE 38% | 3 subs, 07-14 |
| 1657858 | MATRIZ CRITERIO IMAGEN PLOG 🆕 | 1656181 | ? | sin submissions aún | 0 subs |
| 1695114 | CHECKLIST AUDITORÍA PROVEEDORES PLOG 🆕 ⚠️NO en Excel | 1693323 | ? | sin submissions aún | 0 subs |

Secciones/áreas por formulario (drill-down): en `data/scored_forms_fields.json` (títulos exactos de secciones y formulas por form).

## 5. Hallazgos para validar con Roberto / directores

1. **954599 PRO-SUC-1 2025V1** tiene 158 subs (40/40 PLOG, viva al 08-10) y NO está en el Excel — parece la variante que PLOG usa de verdad. ¿Se agrega?
2. **1695114 CHECKLIST AUDITORÍA PROVEEDORES PLOG** (act 1693323) creado después del Excel, 0 subs — falta política.
3. **REVISIÓN OPERATIVA + GESTIÓN Y FINANZAS suman 100%** (62+38) — confirmar que el tablero los muestre como calificación combinada.
4. Stale: Conteo Diario Pollo (may), PRO-CSC-5 Vehículos (jun), VCAL25 (nov-2025), PRO-SC-6 (dic-2025) — cuadra con los "No" del Excel en varias zonas.
5. Scores >100% posibles (bonus) — definir si se clampean.

## 6. Arquitectura acordada
- Mismo repo `epl-cas-etl-2026`, módulo nuevo `etl_plog/` (patrón etl_v2). Mismo Postgres Railway, **schema separado `plog`** (tablas propias, cero contacto con el dashboard actual). Mismo design system del PWA (style.css tokens). Crons propios.

---

## 7. Fase 1 construida y validada E2E (2026-08-11)

Módulo `etl_plog/` corriendo contra BD local `epl_plog_local` (schema `plog`) con data viva:
- **Sync raw:** 44,771 submissions PLOG ingeridas = **histórico completo jun-2025→hoy** (⚠️ hallazgo: el API IGNORA `start_date`/`end_date` — cada corrida re-escanea todo; optimizar con corte client-side o Large Batch antes del cron horario. Depósito NL topa cap offset 10k por corrida).
- **Seed:** 18 sucursales + 87 filas `config_formularios` (29 familias × 3 zonas, semilla del Excel + correcciones; `ON CONFLICT DO NOTHING` = nunca pisa cambios del admin).
- **Motor cumplimiento:** 5,092 ventanas jul-1→ago-10 · global 70% · NL 80.4% / Laguna 57.1% / Qro 67.5%.
- Insights reales que ya arroja: SERVIR casi no se llena (11.8%), RL1 se entrega tarde sistemáticamente (478 late vs 24 on_time → ¿hora límite 15:00 muy estricta?), visita semanal del director 10.2%, Vehículos 0%, Depósito de Valores 99.8%.
- **Recorrido Comisariato: 0 de 67 submissions son de las 18 sucursales** → los comisariatos son locations aparte; falta identificar cuáles (campo `es_comisariato` en admin).
- Pivote acordado con Roberto: **se extrae TODO siempre; un ADMIN PANEL activa/desactiva formularios y edita políticas sin deploy** (config viva en `plog.config_formularios` + `config_audit`). Deep research de mejores prácticas corriendo (wf_4657da9f-394).

## 8. Comisariatos (aclaración Roberto 2026-08-11)
- **No tienen location en Zenput.** Modelados como sucursales VIRTUALES (ids negativos: -1 NL, -2 Laguna, -3 Qro, `es_comisariato=true`).
- **Recorrido Diario (1161752):** llega con `location=None`; se atribuye por responsable (`Galilea Gallegos` → Comisariato NL, mapa `RESPONSABLE_A_COMISARIATO` en raw_sync). 67/67 ingeridas. Cumplimiento real ~5% (67 subs en un año vs política diaria).
- **Evaluaciones de comisariato (954600/954601/1059170/1059182):** llegan bajo la tienda que hospeda el comisariato → flag `es_comisariato` en Vasconcelos(2247040), Revolución(2247042), Pueblito(2247048), Constituyentes(2247050). Las de Santa Catarina (2247003) son de CAS y se excluyen.
- Pendiente afinar: responsable del comisariato Qro (Recorrido Qro marca 0%), y **asignación serie A vs L por sucursal** (hoy ambas series generan ventanas donde la zona dice Sí → la serie que la tienda no usa sale 0%; auto-detectar o asignar en admin).
