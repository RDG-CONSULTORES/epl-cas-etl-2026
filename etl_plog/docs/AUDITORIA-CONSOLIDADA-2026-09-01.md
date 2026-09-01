# Auditoría Consolidada A-Z — ETL PLOG (2026-09-01)
Verificación fresca del código y el sistema vivo (no de memoria), por RDG Consultores. Enfoque: cerrar cualquier gap que no podamos contestar frente al cliente + detectar lo débil. Semáforo: ✅ sólido · 🟡 deuda/parcial · 🔴 gap fuerte.

## VEREDICTO GLOBAL
El ETL PLOG está **vivo, sano y con cimientos sólidos**. Los **números diarios son CONFIABLES** (RL1/RL2/cierre/alistamiento/depósito). Desde la auditoría del 13-ago se **arreglaron** los 3 sesgos de cálculo grandes. Lo que queda son **2 gaps de datos** que importan para la integración con Homero (cobertura de auditorías DO + histórico) y **débiles de resiliencia operativa** (backups, alertas). Ninguna fuga de secretos.

## ✅ LO SÓLIDO (defendible hoy)
- **Pipeline de datos**: incremental con solape 3 días, `ON CONFLICT DO NOTHING`, reintentos 3× a Zenput, `sync_state` con trazabilidad por formulario, `/api/freshness` expone el corte.
- **Números de cumplimiento diario**: 4 estados correctos (on_time/late/missed/pending); `pending` nunca se pinta como falta.
- **Sesgos ARREGLADOS** (vs 13-ago): serie A/L (ya no infla Laguna), doble conteo periódico (membresía por fecha_local exclusiva), freeze inline (ventana cerrada → missed congelado).
- **Seguridad/accesos**: scoping impuesto en el backend (un director NO ve otra zona; scope vacío = FALSE), passwords bcrypt, lockout 5 intentos/15min, sesiones server-side, bitácora de accesos. Sin secretos hardcodeados; `.env` gitignoreado.
- **Git**: en `RDG-CONSULTORES/epl-cas-etl-2026` (rama `feat/plog-cumplimiento`). Requirements pinneados (builds reproducibles).

## 🔴🟡 GAPS Y DÉBILES (lo que hay que pulir)

### Datos / motor
| # | Hallazgo | Sev | Estado | Fix |
|---|---|---|---|---|
| D1 | **Gemelos de auditorías DO** (877138/877139/901109) no mapeados ni sincronizados → **subcuenta cobertura de auditorías** | 🔴 | ABIERTO | agregar FTs en `build_catalogo.py:71-72`, regenerar catálogo, re-ingesta; dedup por ventana ya cubierto |
| D2 | **Histórico solo ~6 semanas** — Homero pide **desde ene-2026** (y YoY necesita 2025) | 🟡 | ABIERTO | correr backfill `raw_sync --desde 2025-01-01` + `motor.run(2026-01-01)` + `calificaciones` (script `backfill.py` de una sola vez) |
| D3 | **`submission_id` no se guarda** (motor inserta `None`) → detalle no liga a la submission/PDF/foto | 🟡 | ABIERTO | propagar submission_id acreditado en `motor.py` (SELECT+INSERT) |
| D4 | Effectivity parcial (política nueva recalcula días previos no congelados) | 🟡 | deuda | `valid_from/valid_to` en config o congelar diario |
| D5 | Depósito N-por-día contado como 1/día · Sin calendario de feriados/cierres | 🟡 | decisión negocio | requiere regla de Roberto/directores |

### Operación / resiliencia
| # | Hallazgo | Sev | Fix |
|---|---|---|---|
| O1 | **Sin backup automatizado de Postgres** — "¿está respaldado?" hoy = no (salvo lo de Railway) | 🔴 | activar backups Railway o cron `pg_dump` + retención + prueba de restore |
| O2 | **Falla silenciosa del sync** (token expira / Zenput cambia) → tablero se congela 3h+ sin avisar (escenario PolloBot) | 🔴 | alerta cuando `max(last_synced_at)` > N horas + notificar excepción del refresh |
| O3 | Sync = timer in-process (sin hora fija, single-worker, sin redundancia); depende del web vivo | 🟡 | mover a cron-service Railway o dead-man's-switch |
| O4 | Reportes por correo en **preview permanente** (sin `RESEND_API_KEY`, sin cron) — hoy NO llega ningún correo | 🟡 | decidir Resend vs SMTP @plog + agendar cron |

### Seguridad / deploy (menores)
| # | Hallazgo | Sev | Fix |
|---|---|---|---|
| S1 | Cookie de sesión `secure=False` en HTTPS (`main.py:84`) | 🔴 | `secure=True` en prod |
| S2 | `.env` se hornea en la imagen (no fuga pública, innecesario) | 🟡 | añadir `.env` a `.railwayignore` |
| S3 | Prod corre de rama feature, 1 commit sin pushear; `main` = CAS legacy | 🟡 | pushear + decidir merge/documentar |
| S4 | Sin `healthcheckPath` en railway.json; rol `director`==`viewer`; sin CSRF token en mutaciones admin | 🟡 | cablear healthcheck; aclarar roles con cliente |

## PLAN DE PULIDO PRIORIZADO
**Tanda 1 — quick wins seguros (código/config, sin tocar datos vivos):** S1 cookie Secure · S2 .railwayignore · S3 push commit · S4 healthcheckPath.
**Tanda 2 — críticos de resiliencia (tocan infra viva, requieren OK):** O1 backups Postgres · O2 alerta de frescura estancada.
**Tanda 3 — datos para Homero (recálculo sobre BD viva, requieren OK):** D1 gemelos DO + re-ingesta · D2 backfill histórico · D3 submission_id.
**Tanda 4 — decisiones de negocio:** D5 feriados/depósito · O4 proveedor de correo · D4 effectivity.

## PARA LA INTEGRACIÓN CON HOMERO (¿podemos contestar todo?)
- **Sí**, salvo dos matices honestos: (a) **cobertura de auditorías DO** está subcontada hasta cerrar D1 — NO presentar ese número aún; (b) el **histórico** se entrega completo solo tras D2. El resto (cumplimiento diario, IDs, fechas, zona horaria, volumen, capacidad técnica) ya está respondido en el paquete de entrega.
