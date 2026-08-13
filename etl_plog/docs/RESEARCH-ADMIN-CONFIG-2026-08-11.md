# Research: sistema admin-configurable de cumplimiento (síntesis)
**2026-08-11** · Deep research 106 agentes, claims verificados 3-0 adversarialmente. Raw: `research-admin-config-raw-2026-08-11.json`.
Fuentes clave: docs oficiales Prefect (scheduler), Martin Fowler (Effectivity/bitemporal), soporte Zenput/Crunchtime (Projects), Jolt (Item Completion Report), Unleash (feature flags), CRUDAdmin.

## Lo que el research VALIDA de lo ya construido
1. **Raw-first ELT** — Crunchtime mismo vende este patrón ("Data Streaming": raw data → warehouse del cliente + BI externo). Nuestro API-pull a Postgres es lo mismo con menos latencia y sin add-on.
2. **Config viva en BD + bitácora** — `config_formularios` + `config_audit` van en la dirección correcta (Unleash: todo cambio de flag con audit trail; archivar, nunca borrar).
3. **Estados no binarios** — on_time/late/missed/pending es exactamente el modelo de Jolt (azul oscuro/azul claro/rojo) y Zenput (que además distingue "no asignado" de "missed"). `missed` solo después de vencer ventana+gracia ✓ (ya lo hace el motor).
4. **El modelo de política del propio Zenput** (Projects) es el template del admin: frecuencia One-time/Daily/Weekly(días)/Monthly(día fijo o relativo)/Yearly + ventana "Due Between" + scope por atributos/ubicaciones. Zenput NO tiene grace_days (solo un booleano Auto-Archive) → nuestros días de gracia son un diferenciador, mantenerlos simples (int, default 0).

## Las 3 CORRECCIONES al diseño actual (aplicar antes del admin panel)
1. **Snapshot de política + recompute-forward (Fowler).** Hoy el motor recomputa todo el rango → si el admin cambia la hora límite, el histórico MUTA silenciosamente. Corrección: cada ventana finalizada guarda `policy_snapshot` (jsonb con frecuencia/límite/gracia usados) y se CONGELA; un cambio de política solo borra/regenera ventanas futuras `pending`. Fowler explícito: el "trace of the calculation" es más simple y suficiente vs tablas bitemporales (NO hacer bitemporal completo).
2. **Effectivity en políticas.** `valid_from`/`valid_to` en config_formularios (patrón más común según Fowler) y el audit log con DOS fechas: `effective_at` + `recorded_at`. Archivar (activo=false) en vez de borrar.
3. **Pre-materializar expectativas (patrón Prefect).** En vez de generar ventanas al vuelo en cada corrida: job idempotente que materializa `expected_occurrence` con horizonte rodante (~35 días), con `due_at_local` Y `due_at_utc` + tz IANA por sucursal. Al editar política: borrar solo futuras no vencidas y regenerar (así lo hace Prefect y así lo hace el propio Crunchtime: "edits apply only to future instances").

## Decisiones de implementación
- **Admin panel: 4 pantallas CRUD vanilla JS propias** (no CRUDAdmin: es pre-1.0, no respeta los estilos del PWA, y solo auditaría cambios hechos por su propio panel). Roles: admin (edita) / viewer (lee). Audit escrito EN LA MISMA transacción del update. Toggle activo/inactivo con archivo, log de cambios visible inline.
- **N-veces-al-día**: si algún form lo necesita → múltiples filas de política con ventanas distintas (Zenput tampoco soporta N-per-day en una sola).
- **"No asignado" ≠ "missed"**: sucursal sin el form asignado no genera fila (o `not_required`) — nunca cuenta como falta. Aplica directo al problema serie A vs L: asignación por sucursal.
- **TZ**: México abolió DST en 2022 → riesgo bajo, pero guardar tz IANA por sucursal de todos modos (America/Monterrey / America/Mexico_City).

## Trampas conocidas (cada una con fuente verificada)
- Contar como missed trabajo cuya ventana sigue abierta (Jolt separa Open/Closed por esto) ✓ ya evitada.
- Confundir "no asignado" con "missed" (Zenput: celda vacía ≠ No) → resolver con asignación por sucursal.
- Histórico que muta al cambiar política → snapshot + recompute-forward.
- Bugs de DST por calcular límites en UTC → due local + tz por sucursal.
- Borrar configs y perder el trail → archivar siempre.
- Ediciones de recurrencia afectando instancias ya generadas → solo futuras.

## Orden de construcción recomendado (research) vs estado real
1. Raw ELT ✅ hecho · 2. Config con effectivity + audit 🔶 parcial (falta valid_from/to + effective_at) · 3. Generador de expectativas materializado 🔶 rediseñar motor · 4. Matcher 4 estados ✅ lógica hecha (falta snapshot/freeze) · 5. Admin panel ⬜ · 6. Dashboards drill-down sobre filas precomputadas ⬜.
