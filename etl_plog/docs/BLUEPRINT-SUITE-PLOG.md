# Blueprint — Suite completa de Cumplimiento PLOG
**Act. 2026-08-13** · Basado en 4 deep researches (claims verificados 3-0 adversarialmente) + drill-down spec de data real + decisiones de Roberto.
- R#1 admin/config-driven (`RESEARCH-ADMIN-CONFIG-2026-08-11.md`)
- R#2 vistas/reporte/entrega (`research-vistas-suite-verif-2026-08-13.json`, 19 claims)
- R#3 nativo/paridad iOS-Android (`research-nativo-paridad-raw-2026-08-13.json`, 25 claims)
- R#4 arquitectura de datos/sync/agente IA (`research-datos-sync-agente-raw-2026-08-13.json`, 15 claims)
- Síntesis y recomendaciones consolidadas en §10-13.

**Alcance:** puros CUMPLIMIENTO al arranque (¿contestaron el día y hora correctos?); formularios se van activando desde el admin; calificaciones por área ya mapeadas (drilldown_spec) se prenden en fase posterior.

---

## 1. Vistas del PWA (mobile-first, tema oscuro, design system CAS)

**V1 · HOY (home).** Semáforo del día en curso. Header: % del día por zona (según scope del usuario). Lista de sucursales, cada una con fila de puntos por formulario activo del día: ✅ a tiempo · 🟡 tarde · 🔴 faltó · ⚪ aún en ventana (pending NUNCA se pinta rojo — regla verificada Jolt open/closed). Tap sucursal → V3. Barra superior con selector de zona (solo las que el usuario ve).

**V2 · MATRIZ SEMANAL (heatmap).** Filas = sucursales, columnas = días Lun–Dom, celda = % del día (verde ≥90 · amarillo 70–89 · rojo <70 · gris = sin expectativa "no asignado ≠ faltó", patrón Zenput celda vacía). Selector de semana ←→ y de formulario ("Todos" o uno). Es la vista para la junta semanal; ordenable por % ascendente (peores arriba — patrón ranking Jolt).

**V3 · SCORECARD SUCURSAL.** Header: % semana actual + tendencia vs semana anterior (▲▼). Lista de formularios activos con su % de la semana y sparkline de 8 semanas. Tap formulario → V4. Sección "Faltantes de hoy" arriba (accionable primero).

**V4 · DETALLE FORMULARIO × SUCURSAL.** Calendario del mes con cada ventana esperada: a tiempo/tarde/faltó + hora real de submission vs hora límite. Cuando el form tenga calificación activada: score total + semáforo por área (del drilldown_spec). Aquí termina el drill-down: zona → sucursal → formulario → día/área.

**V5 · ADMIN (solo rol admin).** 4 pantallas CRUD: (a) Formularios: toggle activo por zona, editar frecuencia/días/hora límite/gracia, ver bitácora de cambios inline; (b) Usuarios: alta con usuario+contraseña, rol, zona(s) y sucursales visibles; (c) Sucursales: nombre/zona/comisariato/serie A-L asignada; (d) Reportes: destinatarios, día/hora de envío, canal.

Reglas de UX (research + PWA CAS): tap-targets grandes, nada de gráficas densas en móvil, máximo 2 niveles de navegación por tap, colores semáforo consistentes con estados del motor, "pending" siempre visualmente neutro.

## 2. Reporte semanal automatizado

- **Cadencia:** lunes 07:00 (America/Monterrey), cubre Lun–Dom anterior. (Direccional research #2: mismo día fijo cada semana, revisión en 24-48h.)
- **Contenido (1 pantalla, 10-15 métricas máx):** % global de la zona vs semana anterior · tabla sucursales (% + tendencia ▲▼, peores arriba) · top 5 formularios más faltados · top faltantes por sucursal (form + días) · liga profunda al PWA (V2 de esa semana).
- **Formato:** HTML nativo de email (tablas simples, colores inline — se lee en el teléfono sin abrir nada) + liga al PWA. PDF adjunto opcional después (WeasyPrint ya dominado en epl-gpt). NO empezar con PDF: fricción y peso.
- **Scoping:** cada destinatario recibe SOLO sus zonas/sucursales (mismo user_scopes del punto 4).

## 3. Canal de entrega

- **Fase 1 — Correo (Resend):** Roberto ya lo opera en AMACARGA; API trivial, dominio verificado, ~1 día de trabajo. Volumen (≤30 correos/semana) entra en free tier.
- **Fase 2 — WhatsApp Business Platform:** los gerentes viven ahí. Requiere: Meta Business verificado + número dedicado + plantilla "utility" pre-aprobada + opt-in de cada destinatario. Pricing 2025+: por MENSAJE (ya no por conversación); plantillas utility son el tier barato (~80-90% menos que marketing). ⚠️ Cifras exactas MX pendientes de verificar (el research topó límite de sesión) — re-verificar antes de comprometer costos. Diseño: capa `notificaciones` desacoplada (tabla `envios` + workers por canal) para que WhatsApp se agregue sin tocar reportes.

## 4. Auth + accesos segmentados

- **Modelo:** `usuarios` (id, usuario, password_hash argon2/bcrypt, rol admin|director|viewer, activo) + `user_scopes` (user_id, zona NULL=todas, location_ids bigint[] NULL=toda la zona). Alta SOLO por admin (sin self-signup). Todo cambio de usuario/scope → `config_audit`.
- **Sesión:** cookie HttpOnly + Secure + SameSite (server-side session en Postgres) — NO JWT en localStorage (lección AMACARGA: refresh en localStorage = sesiones que se caen; cookie HttpOnly es el fix conocido).
- **Enforcement server-side:** todos los endpoints de datos filtran por el scope del usuario en SQL (WHERE zona = ANY(scopes) AND location_id = ANY(...)); el frontend solo esconde, el backend impone.
- Rate-limit login + lockout tras N intentos. Sin recuperación self-service: el admin resetea contraseñas.

## 5. Cadencia de sync y jobs (Railway, TZ America/Monterrey)

| Job | Cron | Qué hace |
|---|---|---|
| sync horario | `0 7-23 * * *` | pull Zenput → raw + resolver ventanas del día (V1 "en vivo" con ≤1h de rezago) |
| cierre diario | `30 0 * * *` | pull final del día + finalizar ventanas vencidas (freeze con policy_snapshot) |
| generador expectativas | dentro del cierre diario | materializa expected_occurrence horizonte 35 días (patrón Prefect) |
| reporte semanal | `0 7 * * 1` | render + envío por scope |

⚠️ El API ignora start_date → optimizar el sync horario con corte client-side (dejar de paginar al ver submissions ya conocidas) para no re-escanear 45k cada hora.

## 6. Orden de construcción (fases, cada una entregable usable)

1. **Motor v2** (correcciones research #1): expected_occurrence materializada + policy_snapshot/freeze + effectivity + asignación serie A/L por sucursal. *(la base de todo lo demás)*
2. **Auth + API FastAPI** (usuarios, scopes, endpoints de cumplimiento con scoping SQL).
3. **PWA V1 + V2** (Hoy + Matriz semanal) → *primer entregable visible para PLOG*.
4. **Admin V5** (formularios/usuarios/sucursales) → PLOG opera solo.
5. **V3 + V4** (scorecard + detalle) + reporte semanal por correo.
6. **Deploy Railway** (schema plog, crons, servicio web separado del CAS).
7. Fase posterior: calificaciones por área (drilldown_spec listo), WhatsApp, alertas del día.

---

## 7. Motor de reportes — TODAS las cadencias + comparativos (decisión Roberto 2026-08-12)

Un solo generador parametrizado por periodo (no 7 reportes distintos). Todos leen las mismas filas de `cumplimiento`/`expected_occurrence`:

| Cadencia | Periodo | Envío | Comparativo |
|---|---|---|---|
| Semanal | Lun–Dom ISO | lunes 07:00 | vs semana anterior |
| Quincenal | 1–15 / 16–fin | día 1 y 16, 07:00 | vs quincena anterior |
| Mensual | mes calendario | día 1, 07:00 | vs mes anterior + mismo mes año anterior |
| Bimestral / Trimestral / Semestral | periodos alineados | día 1 del periodo | vs periodo anterior + YoY |
| Anual | año calendario | 2-ene | vs año anterior |

- **Comparativos:** siempre dos ejes — vs periodo inmediato anterior y vs mismo periodo del año pasado (YoY posible desde jun-2026: hay histórico desde jun-2025). Delta en pp por zona/sucursal/formulario + "más mejoró / más cayó".
- **Config en admin (pantalla Reportes):** cadencias activas × destinatarios × canal (correo/WhatsApp/push) × scope. Tabla `report_schedules` + `envios` (bitácora de cada envío).
- ⚠️ Regla de comparabilidad: si el admin activó/desactivó formularios entre periodos, el comparativo marca "base distinta" (n formularios activos en cada periodo) — nunca comparar en silencio peras con manzanas.

## 8. Fase nativa iOS + Android (la cereza del pastel — documentado para no retrabajar)

**Principio rector: API-first HOY.** El backend FastAPI expone JSON puro; el PWA es el primer cliente. Las apps nativas consumen los MISMOS endpoints — cero cambios de backend al llegar aquí.

- **Auth dual desde el diseño:** cookie HttpOnly para el PWA + bearer token de larga vida (tabla `api_tokens`, revocable) para apps nativas. Se deja implementado en la Fase 2 de auth aunque lo nativo llegue después.
- **iOS (precedente: PolloBot):** SwiftUI + **Swift Charts** (gráficas nativas de alta calidad — la razón #1 de Roberto para nativo), pipeline ya dominado: xcodegen → TestFlight (API key .p8), liga pública tipo AMACARGA. Vistas = mismas V1–V4 del blueprint.
- **Android (precedente: app AMACARGA Android):** Kotlin + Jetpack Compose + Vico/MPAndroidChart para gráficas.
- **Push notifications nativas (iOS + Android): OneSignal** como capa única (ya operado en AMACARGA: iOS+Safari+Chrome) — un solo API para APNs+FCM+web push, segmentación por usuario/zona incluida. Alternativa directa APNs/FCM documentada pero NO recomendada para 1 dev.
- **Push — mejores prácticas (estéticas y de contenido):**
  - Tipos: (1) alerta del día "RL1 sin entregar en 3 tiendas — 14:40" (accionable, con hora límite cerca), (2) resumen diario 22:30 opcional, (3) aviso "tu reporte semanal está listo" con deep link.
  - Deep link SIEMPRE a la vista exacta (V1 filtrada / V4 del form / reporte) — nunca al home.
  - Opt-in por TIPO de notificación por usuario (pantalla de preferencias); horario silencioso 22:30–07:00 salvo alertas críticas; agrupadas por thread-id (iOS) / channel (Android) para que no se apilen feas.
  - Contenido: número + contexto + acción ("3 faltantes hoy en Laguna · toca para ver"), nunca genéricas ("Tienes notificaciones").
  - La capa `notificaciones` del punto 3 gana un canal más (push) — misma tabla `envios`, mismo scheduler.
- **Orden realista:** suite PWA completa y estable en producción → iOS (Swift Charts + push) → Android. El PWA ya es instalable con ícono desde el día 1 (como AMACARGA), así que lo nativo es upgrade de experiencia, no bloqueante.

## 9. Agente de IA conversacional (cereza #2 — fase final, documentado por adelantado)

Chat en español para gerentes: "¿cómo va Laguna esta semana?", "¿qué tiendas no han entregado RL1 hoy?", "compárame julio vs junio".

- **Lección PolloBot (ya pagada, no repetir):** text-to-SQL puro (Vanna) = 27-58s y errores; **KPIs pre-compilados con fast-path de intents = 2-8s**. Arquitectura híbrida desde el día 1: las ~20 preguntas comunes son intents deterministas que pegan a los MISMOS endpoints del API de cumplimiento (ya scoped por usuario); el long-tail va al LLM con guardrails.
- **Guardrails:** solo lectura absoluta · scoping por user_scopes (el agente NUNCA ve tiendas que el usuario no ve — mismo WHERE del API) · responde con cifras citando periodo y corte de datos ("al corte de las 14:00").
- **Ventaja estructural:** como el motor ya pre-calcula cumplimiento por ventana, el agente no calcula nada — consulta hechos. Es el mismo patrón kpi_cache.py de epl-gpt, reutilizable directo.
- Investigación en curso (research #4, wf_b3b02802-3dc): estado del arte 2026 híbrido intents+LLM, tool-use sobre API propia vs SQL directo.

---

## 10. Arquitectura de datos — VEREDICTO replicar-vs-API (R#4, verificado 3-0)

**Veredicto: REPLICAR a BD propia. No es empate — es el estándar de industria.** Evidencia dura:
- **Fivetran** (SaaS→destino): "initial sync" histórico único + luego "incremental sync mode: only data modified or added is extracted on schedule". Es exactamente lo que ya hicimos.
- **Airbyte**: cursor/watermark (`cursor_field > last_sync_max`), sync_state persistido por stream = start del próximo sync. Es exactamente nuestro `sync_state`.
- El propio **Crunchtime/Zenput** vende "Data Streaming" = replicar raw a warehouse del cliente. El fabricante te dice "para analizar, llévate los datos".

**Spec del sync confiable (adoptar de Fivetran/Airbyte):**
1. **Watermark por recurso** (ya: `sync_state.last_ts_seen`). Incremental = solo submissions con ts > watermark.
2. **Lookback window / solape** (ya: SOLAPE=3 días): re-consultar N días antes del corte para atrapar datos tardíos o editados. Airbyte: mitigación estándar para APIs que editan sin fecha confiable. ⚠️ Zenput edita sin actualizar fecha → **subir solape a 7 días** + full-refresh de reconciliación.
3. **Full-refresh periódico de reconciliación** (Fivetran "rollback sync" diario + reimport cuando la fuente no da incrementales confiables): 1×/semana (domingo madrugada) re-escanear todo y reconciliar conteos fuente-vs-destino.
4. **Deletes = soft-delete** (patrón Fivetran `_deleted` boolean): NUNCA borrar de raw; marcar `deleted_at`. En reconciliación semanal, submission en BD que ya no está en la fuente → marcar borrada (regla `_synced < re-sync start`).
5. **Freshness SLA visible**: el dashboard muestra "Datos al corte de las HH:MM" (última corrida OK de `sync_state`). Si el último sync > 2h → banner ámbar "datos pueden estar atrasados".
6. **Idempotencia** (ya: `ON CONFLICT DO NOTHING` por submission_id).

**Jobs en Railway (R#4 verificado):**
- Cron mínimo cada 5 min; **el cron DEBE terminar y salir — si cuelga (API lenta), bloquea TODAS las corridas futuras** → timeout duro + lock en cada job.
- Cadencia adoptada: **sync horario 7–23h** (cada hora en horas operativas), **cierre 00:30**, **reconciliación semanal domingo**. Para dashboards "del día" esto sobra (Crunchtime Data Streaming tiene 4-12h de latencia; nosotros ≤1h).
- Optimización obligatoria: el API ignora start_date → cortar la paginación al topar submissions ya conocidas (no re-bajar 45k/hora).

## 11. Capa nativa iOS+Android — decisión de framework (R#3, verificado 3-0)

Hechos verificados (no opinión):
- **Swift Charts hace heatmaps nativos** (sample oficial de Apple: "histograms, scatterplots, heatmaps") + plots vectorizados para datasets grandes. ✅ cubre V2.
- **Vico (Compose Multiplatform) NO tiene heatmap** (solo line/column/candlestick/pie) → el heatmap día×sucursal requeriría dibujo custom en Android/CMP.
- **Compose Multiplatform iOS = estable y production-ready** (JetBrains, mayo 2025, "scrolling on par with SwiftUI").
- **SkipUI** = SwiftUI→Android sobre Compose, pero cobertura incompleta (DatePicker solo "medium") y **renderiza Material 3** (se ve Android-nativo, no clona iOS).
- **Style Dictionary**: define design tokens 1 vez → genera Swift + XML Android + SCSS web. Es el puente para que PWA/iOS/Android compartan colores/tipografía.
- **OpenAPI Generator**: FastAPI emite OpenAPI 3.1 → genera clientes Swift y Kotlin type-safe (mismatches del contrato se cachan en compile-time). Swift OpenAPI Generator = plugin SPM oficial.
- **Google Play 2026**: cuentas personales creadas después de 13-nov-2023 requieren **12 testers × 14 días** en closed test antes de producción. **Cuentas de organización EXENTAS.** (TestFlight ya dominado de PolloBot.)

**RECOMENDACIÓN (síntesis):** para ESTE caso (1 dev, ya sabe SwiftUI, gráficas de alta calidad = prioridad #1 de Roberto, heatmap central), el orden es:
1. **PWA primero** (instalable, ya cubre 100% con ícono en home). Las 3 caras comparten tokens vía Style Dictionary desde el día 1.
2. **iOS nativo con SwiftUI + Swift Charts** (heatmap nativo, pipeline PolloBot probado). Cliente API generado del OpenAPI de FastAPI.
3. **Android**: decisión diferida a cuando iOS esté estable. Candidatos reales: (a) Compose Multiplatform reusando lógica Kotlin + Vico con heatmap custom, (b) Compose nativo. NO Capacitor (mata la calidad de gráficas que es el punto). Usar cuenta de organización Google Play para evitar el gate de 12 testers.

## 12. Push/deep links con paridad (R#3, verificado 3-0)

- **OneSignal** = capa única APNs+FCM+web (ya operado en AMACARGA). Confirmado: soporta deep link por Launch URL o Additional Data.
- ⚠️ **Gotcha verificado**: OneSignal Launch URL en iOS abre Safari y rebota vía Universal Links — usar **Additional Data + click listeners** para abrir la vista directo (más limpio).
- Paridad requiere config nativa estándar: iOS Universal Links (Associated Domains + archivo AASA) / Android App Links (intent filters + assetlinks.json). Deep link SIEMPRE a la vista exacta (V1 filtrada / V4 del form / reporte).

## 13. Reporte semanal + WhatsApp — costos reales (R#2, verificado 3-0)

- **Formato verificado**: reporte de 1 página = scorecard (tabla) + 5 secciones cortas. Métricas ops recomendadas: completion rate por turno y por sucursal, checks completados vs requeridos, ítem más faltado por sucursal.
- **Móvil**: progressive disclosure (overview → drill-down), barras máx 5-7 (horizontales), nada denso en pantalla chica.
- **WhatsApp costos (Meta, verificado)**: plantillas **utility/auth desde $0.0034/msg** (la página no muestra tarifa MX específica — el número exacto MX sigue pendiente). **Twilio cobra +$0.005/msg de markup** sobre Meta → Meta Cloud API directo es más barato. **Gratis dentro de la ventana de 24h** tras mensaje del usuario. Confirma: correo Resend fase 1, WhatsApp fase 2, y para WhatsApp ir **Meta directo, no Twilio**.
- **IA de las vistas Zenput/Jolt a copiar** (verificado): card "Frequently answered No" (preguntas más falladas), Zenput móvil = 4 tabs (Summary/Tasks/Activity/Recurring), Tasks por urgencia (overdue/due today/this week/upcoming) con filtro all/incomplete/complete/missed — mapea directo a nuestros estados.

## Pendientes menores (no bloquean construcción)
- Tarifa MX exacta de WhatsApp utility (Meta no la publica en la página; se ve al crear la cuenta Business).
- Confirmar formato del reporte con 2-3 usuarios reales tras el primer envío.
- Decisión final Android (CMP vs Compose nativo) al terminar iOS.
