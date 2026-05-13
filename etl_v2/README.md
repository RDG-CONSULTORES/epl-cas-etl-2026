# Módulo `etl_v2` — Operación Diaria EPL CAS

Mide el cumplimiento de los **3 formularios diarios** de Zenput (Apertura, Entrega
de Turno, Cierre) para las **68 sucursales** EPL CAS, agrupadas en **18 Grupos
Operativos**. Vive en paralelo al dashboard de Supervisiones existente (Flask en
`app.py`) y no comparte código ni schema con él.

## Estructura

```
etl_v2/
├── shared/            # config, db pool, cliente Zenput, resolver GO, scoring
├── operacion_diaria/  # extract / transform / load + orchestrators
├── api/               # FastAPI app + 8 routers (/api/operacion/*)
├── web/               # dashboard standalone (index.html + JS/CSS vanilla)
└── scripts/           # backfill.py
sql/operacion_diaria/  # 3 SQL files (schema + tablas + índices)
```

## Despliegue (Railway, 4 servicios nuevos en proyecto `epl-cas-2026`)

| Servicio | Tipo | Start command | Cron |
|---|---|---|---|
| `web-operacion-diaria` | web (FastAPI) | `uvicorn etl_v2.api.main:app --host 0.0.0.0 --port $PORT` | — |
| `cron-operacion-hourly` | cron | `python -m etl_v2.operacion_diaria.orchestrator.hourly` | `0 7-23 * * *` |
| `cron-operacion-daily-close` | cron | `python -m etl_v2.operacion_diaria.orchestrator.daily_close` | `30 0 * * *` |
| `cron-operacion-weekly-rollup` | cron | `python -m etl_v2.operacion_diaria.orchestrator.weekly_rollup` | `0 5 * * 1` |

Cron en hora local de Monterrey (Railway respeta `TZ=America/Monterrey`).

### Variables de entorno (por servicio)

```
DATABASE_URL=${{ Postgres.DATABASE_URL }}
ZENPUT_TOKEN=<token Zenput — mismo que usa el servicio epl-cas-etl-2026 viejo>
APP_SCHEMA=operacion_diaria
TZ=America/Monterrey
LOG_LEVEL=INFO
PORT=8000   # solo para web-operacion-diaria
```

## Base de datos

Schema aislado `operacion_diaria` (no toca `public`). Usuario propio
`operacion_diaria_app` con privilegios limitados a su schema.

Tablas:
- `dim_sucursales` — 68 sucursales con `go_id` y flag `has_epl_cas_tag`.
- `dim_grupos_operativos` — 18 GOs.
- `daily_compliance` — PK `(sucursal_id, day, form_key)`. Status:
  `on_time` (1.0) / `late` (0.5) / `missed` (0.0).
- `weekly_summary` / `monthly_summary` — rollups por scope
  (`global` / `go` / `sucursal`) y `form_key` (incluye `'overall'`).
- `etl_runs` — bitácora de ejecuciones.

## Scoring mixto

```python
if window_start <= submitted_at.time() <= window_end:
    score = 1.0  # on_time
else:
    score = 0.5  # late
# si no hay submission y la tarea está archived_incomplete o no existe registro
# → score = 0.0, status = 'missed'
```

Ventanas (Monterrey):
- Apertura: **07:00–11:00**
- Entrega: **14:00–17:00**
- Cierre:  **19:00–23:00**

UPSERT regla: una submission `late` que llega DESPUÉS de una `on_time` ya
registrada no la sobreescribe. `missed` se reemplaza por cualquier registro real.

## Endpoints (`/api/operacion/*`)

| Path | Descripción |
|---|---|
| `GET /periodo?tipo=week|month&offset=0` | Metadata del periodo (fechas, is_current). |
| `GET /kpis?periodo=current-week` | KPIs global + por form. |
| `GET /ranking?scope=go|sucursal&periodo=...` | Ranking ordenado. |
| `GET /grupo/{go_id}?periodo=...` | Detalle de un GO + sus sucursales. |
| `GET /sucursal/{location_id}?periodo=...` | Detalle por días × forms. |
| `GET /heatmap?periodo=...&go_id=` | Matriz sucursal × día × form. |
| `GET /historico?scope=&semanas=8&form_key=overall` | Serie semanal. |
| `GET /alertas` | Bajo compliance + pendientes hoy. |
| `GET /api/health` | Health check. |

`Cache-Control: max-age=60` para periodos abiertos, `max-age=300` para cerrados.

## Backfill

```bash
railway run -s web-operacion-diaria python -m etl_v2.scripts.backfill --semanas 8
```

Recorre semana por semana para evitar el cap ~10K de Zenput. Idempotente: los
UPSERT respetan la regla de prioridad `on_time > late > missed`.

## Comandos útiles

```bash
# Logs por servicio
railway logs -s cron-operacion-hourly --tail 100
railway logs -s cron-operacion-daily-close
railway logs -s cron-operacion-weekly-rollup
railway logs -s web-operacion-diaria

# Re-correr backfill (idempotente)
railway run -s web-operacion-diaria python -m etl_v2.scripts.backfill --semanas 8

# Inspeccionar DB
railway run -s web-operacion-diaria psql $DATABASE_URL -c \
  "SELECT day, form_key, status, COUNT(*) FROM operacion_diaria.daily_compliance \
   GROUP BY 1,2,3 ORDER BY 1 DESC LIMIT 30;"

# Rollback (si hace falta, NUNCA tocar Postgres ni epl-cas-etl-2026):
#   railway service web-operacion-diaria --remove  (PEDIR CONFIRMACIÓN PRIMERO)
#   railway service cron-operacion-hourly --remove
#   railway service cron-operacion-daily-close --remove
#   railway service cron-operacion-weekly-rollup --remove
```

## Gotchas de Zenput v3 (validados contra el API real, mayo 2026)

1. **API es v3**, no v1. Paths: `/api/v3/{submissions,locations,teams,projects,forms}/`.
2. **`/api/v3/tasks/` no existe** — los "missed" se obtienen con
   `/api/v3/submissions/?status=archived_incomplete`.
3. **Paginación** vía `meta.next` URL absoluta (no `page=N`).
4. **`meta.count`** puede reportar `10000` como cap; real total se conoce solo iterando.
5. **Location** de una submission vive en **`smetadata.location.id`**, NO en top-level.
6. **Fechas** en milisegundos epoch como string para los query params.
7. **`smetadata.parent_project.id`** liga submission al proyecto recurrente.
8. **GO de sucursal** se resuelve subiendo `team.parent.id` hasta encontrar uno
   cuyo `parent.id == 115095` (root "El Pollo Loco México").

## Seguridad

- `ZENPUT_TOKEN` y password de `operacion_diaria_app` viven solo en
  Railway variables. **Nunca** commit ni log.
- El usuario `operacion_diaria_app` no puede `CREATE` en `public` (solo lee).
