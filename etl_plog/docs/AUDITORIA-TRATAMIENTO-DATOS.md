# Auditoría del tratamiento de datos — Cumplimiento PLOG
**2026-08-13** · Trazabilidad completa: de dónde vienen los datos, qué campos usamos, cómo los formulamos, y la veracidad de cada número. Verificado contra la fuente real.

---

## 1. ORIGEN — de dónde vienen los datos

- **Fuente única: Zenput (Crunchtime Ops Execution), API v3.** Base `https://www.zenput.com/api/v3/`, auth por header `X-API-TOKEN`. No hay otra fuente; nada se inventa ni se captura a mano.
- **Universo: las 18 sucursales PLOG** (ids Zenput 2247034–2247050 + 2261286), en 3 zonas: Nuevo León (8), Laguna (6), Querétaro (4). Resueltas del árbol de `teams` de Zenput (subárbol de PLOG NL/Laguna/Qro), NO de una lista escrita a mano.
- **Lo que jalamos: submissions** (formularios llenados) de esas sucursales. Cada submission es un registro inmutable de que alguien llenó un formulario, con sus respuestas y metadatos.
- **Histórico: jun-2025 → hoy** (17 meses). Se re-sincroniza automáticamente cada 3 h (incremental).

## 2. EXTRACCIÓN — cómo y qué jalamos

- **Endpoint:** `GET /submissions/?form_template_id={ft}` por cada formulario del catálogo (29 familias). Se filtra client-side por `smetadata.location.id ∈ las 18 PLOG` (varios formularios son plantillas compartidas con las tiendas CAS; **solo contamos las submissions de PLOG**, verificado: 0 foráneas en la base).
- **Guardado RAW e inmutable:** cada submission completa se guarda tal cual en `plog.raw_submissions.payload` (JSONB), con su `submission_id` (nunca se re-escribe: `ON CONFLICT DO NOTHING`). Todo lo demás (cumplimiento, calificaciones) es DERIVADO y recomputable desde este raw.
- **Incremental:** el API devuelve newest-first; el sync corta al topar submissions ya conocidas (watermark − solape de 3 días para datos tardíos). No re-baja los 45k cada vez.

## 3. CAMPOS EXACTOS que usamos (de cada submission)

De `smetadata` (metadatos de la submission):
| Campo Zenput | Para qué lo usamos |
|---|---|
| `smetadata.location.id` + `.name` | identificar la sucursal (filtro PLOG + a qué tienda pertenece) |
| `smetadata.date_created` | fecha/hora en que se hizo (→ fecha local MX, define el día/periodo) |
| `smetadata.date_completed` / `date_submitted` | hora de entrega (→ on_time vs late contra la hora límite) |
| `smetadata.created_by.display_name` | quién lo llenó (atribución del Recorrido Comisariato sin location) |
| `smetadata.user_role` | rol de quien llenó (referencia) |

De `answers[]` (las respuestas del formulario), SOLO para calificaciones:
| Campo Zenput | Para qué |
|---|---|
| `answers[].field_type == 'formula'` | identifica los campos de puntaje (Zenput los PRE-calcula, nosotros los leemos, NO los sumamos) |
| `answers[].title` | el nombre del campo (ej. "PORCENTAJE %", "Marinado (100%):") → mapea al score total o a un área |
| `answers[].value` | el valor numérico del puntaje |

**Nada más se consume.** Para cumplimiento NO leemos el contenido de las respuestas — solo si la submission existe y cuándo. Para calificaciones solo leemos los campos `formula` (el score que Zenput ya calculó).

## 4. FORMULACIÓN — cómo se calcula cada número

### 4.1 CUMPLIMIENTO (¿lo hicieron a tiempo?)
Modelo "esperado vs real": generamos las ventanas ESPERADAS según la política (config del admin) y las cruzamos con las submissions REALES.
- **Esperado:** por cada formulario activo × sucursal, se generan ventanas según su frecuencia (diario/semanal/mensual/…), con su hora límite y días de gracia. Estas reglas viven en `plog.config_formularios` (editables en el admin, NO hardcodeadas) — Zenput no impone ninguna.
- **Real:** las submissions de esa familia+sucursal en la ventana (`fecha_local` dentro de `[inicio, fin]` — cada submission cuenta para UNA sola ventana, sin doble conteo).
- **4 estados:** `on_time` (entregado ≤ hora límite) · `late` (después del límite pero dentro de la gracia) · `missed` (venció límite+gracia sin submission) · `pending` (la ventana aún no cierra — NUNCA se pinta como falta).
- **% cumplimiento = (on_time + late) / (total − pending) × 100.**
- **Alistamiento diario:** las series A y L son la MISMA obligación (checklist de apertura), del día correcto (A1/L1=lunes…A7/L7=domingo); se cumple con A **o** L. Registra cuál contestaron.
- **Congelado (freeze):** una vez que una ventana cierra (venció límite+gracia), se guarda con la política usada y NO se recalcula. Editar una política en el admin NO reescribe el pasado — solo aplica hacia adelante.

### 4.2 CALIFICACIONES (¿qué tan bien?)
- El score lo PRE-calcula Zenput en campos `formula`; nosotros lo EXTRAEMOS, no lo recalculamos.
- **Score total:** el campo formula del total (patrones detectados: "PORCENTAJE %", "… (100%)", "Calificación General", "RESULTADO TOTAL"). Se recorta a **100 absoluto** (el bonus se guarda aparte en `score_raw`).
- **Por área (drill-down):** cada sección del formulario tiene su propio campo formula con su %; se extraen todas → semáforo por área.
- Mapeo de qué campo es el total y cuáles las áreas: `drilldown_spec.json`, derivado de las submissions REALES (no de supuestos).

## 5. TRATAMIENTO / transformaciones aplicadas

1. **Filtro a las 18 PLOG** (por location). Cero datos de otras tiendas.
2. **Zona horaria:** todo se convierte a `America/Monterrey`; el día/periodo se define en hora México (no UTC).
3. **Config-driven:** las reglas de qué se mide, cada cuándo y hasta qué hora viven en BD, editables sin tocar código. Cada cambio queda en bitácora (`config_audit`, quién/qué/cuándo, con diff antes→después).
4. **Comisariatos:** no existen como location en Zenput → sucursal virtual por zona; el Recorrido se atribuye por quien lo contesta. Solo NL lo hace (Qro/Laguna no → desactivados).
5. **Formularios excluidos a propósito** (con motivo en bitácora): DO Supervisión/Control (ejercicios de la marca CAS, no propios PLOG), Conteo de Pollo/Fondo Fijo/Merma (formularios muertos, sin uso reciente).

## 6. VERACIDAD — qué está verificado y qué es supuesto

**✅ Verificado a mano / por auditoría (swarm de 39 agentes + verificación propia):**
- Cumplimiento diario recalculado a mano vs datos crudos = **cuadra al peso (diff=0)**, cero falsos positivos/negativos.
- Calificaciones extraídas coinciden con el payload; clamp a 100 correcto.
- Depósito de Valores NO se infla (múltiples del día colapsan a 1 cumplimiento).
- Solo submissions de las 18 PLOG (0 foráneas).
- Series A/L asignadas por la fecha real de uso (la más reciente = vigente).

**⚠️ Supuestos / decisiones de negocio (documentadas, editables en el admin):**
- Las cadencias y horas límite propuestas (del Excel v3) — algunas difieren de lo que la data observa; se dejaron como estándar a confirmar por los directores.
- La regla "Depósito ≥1 al día" (confirmar si es N/día).
- Los 4 formularios nuevos PLOG sin data suficiente (cadencia por definir).

## 7. Qué NO hacemos (garantías)

- **No inventamos datos.** Todo número sale de una submission real de Zenput.
- **No calculamos calificaciones** — Zenput las pre-calcula, las leemos.
- **No mezclamos CAS con PLOG** — filtro por las 18 locations.
- **No reescribimos el histórico** — el freeze lo protege; un cambio de política aplica hacia adelante.
- **No borramos raw** — es inmutable; todo lo derivado se puede reconstruir desde él.

---

**En una frase:** cada número que ve un director sale de una submission real de sus 18 tiendas en Zenput, filtrada a hora México, medida contra reglas que ustedes controlan en el admin, con el histórico congelado para que no cambie solo — y el motor diario está verificado al peso contra los datos crudos.
