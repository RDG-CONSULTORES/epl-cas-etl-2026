# Reporte Ejecutivo de Auditoría — Sistema PLOG (Zenput ETL)
**Para: Roberto (dueño del sistema) · Fecha: 2026-08-11 · Auditor líder**

---

## 1. Veredicto general

**El sistema es mayormente confiable en su NÚCLEO, pero tiene una fuga de mapeo REAL que subcuenta cobertura de auditorías y dos bugs de cálculo en formularios periódicos.**

Lo bueno primero, porque es sólido: la matemática de cumplimiento, calificaciones y freeze de los **formularios diarios** (el grueso del volumen) está VERIFICADA a mano contra los datos crudos y **cuadra con diff=0** — cero falsos positivos, cero falsos negativos, sin inflación. La ingesta base también es sana: 18 sucursales presentes y activas, histórico continuo, volúmenes estables.

Pero NO es "todo verde":

- **Mapeo (ALTA):** estamos capturando solo UNA variante de las auditorías DO (Supervisión Operativa y Control de Seguridad) y omitiendo el **formulario gemelo activo** que sí recibe submissions de las 18 sucursales PLOG. Esto **subcuenta materialmente** la cobertura real de esas dos auditorías. No es un error de matemática, es datos que existen y no estamos leyendo.
- **Cálculo (ALTA):** en familias periódicas de bajo volumen (semestral/trimestral) hay **doble conteo** (una submission acredita dos ventanas) y **freeze no aplicado** a ventanas ya cerradas hace 44 días.

**Conclusión honesta:** confía en los números diarios. NO confíes todavía en la cobertura reportada de las auditorías DO ni en el cumplimiento de mantenimiento periódico hasta arreglar los cuatro puntos ALTA. El riesgo es subreportar trabajo real (auditorías) y reportar mal el mantenimiento — ambos afectan decisiones sobre sucursales.

---

## 2. Hallazgos por severidad

### 🔴 ALTA

#### A1. Mapeo — Auditorías DO capturan solo una variante; falta el gemelo activo (subcuenta cobertura)
- **Qué está mal:** El catálogo mapea `do_supervision_operativa` → template `1161748` (`*DO SUPERVISION OPERATIVA CAS 1.2`, prefijo DO, arranca 2026-01) e ignora el gemelo `877138` (`SUPERVISION OPERATIVA CAS 1.2`, sin prefijo, activo, **85 submissions PLOG de las 18 sucursales, rango 2025-03..2026-08**) más la revisión previa `901109` (41 subs PLOG). Mismo patrón exacto en `do_control_seguridad` → mapea `1161749` e ignora el gemelo `877139` (67 submissions PLOG, rango 2025-06..2026-08).
- **Evidencia:** raw_submissions solo tiene 102 subs de 1161748 y 33 de 1161749; los gemelos con 85+67 subs PLOG están **ausentes de raw**. Cruce contra Zenput en vivo.
- **Impacto:** La cobertura real de estas auditorías está **subreportada**; una sucursal puede aparecer con menos auditorías de las que realmente hizo.
- **Fix:** Confirmar con negocio si son copias (rol distrito vs rol sucursal) de la MISMA auditoría. Si sí: agregar `877138`/`877139` (y rev previa `901109`) al mapeo en `catalogo.json`/`config_formularios`, re-ingestar histórico, y aplicar **dedup por sucursal+periodo** para no doble-contar cuando ambas copias coexisten.

#### A2. Cálculo — Doble conteo entre ventanas adyacentes en familias periódicas
- **Qué está mal:** UNA sola submission acredita DOS ventanas a la vez (la que cierra como `late` + la que abre como `on_time`), inflando cumplimiento. Afecta **7 submissions → 14 ventanas** (semestral 4, trimestral 3).
- **Evidencia:** Sucursal 2247039 (Lázaro Cárdenas): 1 sola submission `mtto_semestral` del 2026-07-01 aparece en periodo H1 como `late` **y** en H2 como `on_time`. Idéntico en `mtto_trimestral` (Q2 late + Q3 on_time). Query confirma 7 grupos con COUNT>1.
- **Fix:** Acreditar cada submission a UNA sola ventana usando `fecha_local` dentro de `[periodo_inicio, periodo_fin]`, no un `ts_submission` fuera de ventana. Si se permite gracia (1 día tarde cuenta `late`), garantizar exclusión mutua. Recalcular las 14 ventanas.

#### A3. Cálculo — Freeze no aplicado a ventanas cerradas hace 44 días
- **Qué está mal:** 14 ventanas `mtto_semestral` del periodo 2026-H1 (cerró 2026-06-30, hace ~44 días) siguen `congelado=false`; **9 siguen en `pending`** pese a que la ventana cerró, así que su resultado **puede seguir cambiando**. 2025-H1 y 2025-H2 sí están congelados (correcto) → el freeze se detuvo antes de 2026.
- **Evidencia:** De las 14 filas de 2026-H1: 9 `pending`, 4 `late`, 1 `on_time`. Las 9 pending tienen `raw_in_win=0` (nunca hubo submission) → deberían ser `missed` congelado, no `pending` abierto.
- **Fix:** Correr/arreglar el freeze para congelar toda ventana con `periodo_fin < CURRENT_DATE`; antes de congelar, resolver `pending` → `missed` cuando `raw_in_win=0`. Investigar por qué el job cubrió 2025 pero no 2026-H1 (¿cutoff hardcodeado? ¿job no corrido tras cierre de junio?).

#### A4. Diseño — Estado comunicado SOLO por color (falla para ~8% de gerentes daltónicos)
- **Qué está mal:** Cumplimiento se muestra únicamente con color (verde ≥90 / amarillo 70-89 / rojo <70), sin ícono ni etiqueta redundante en píldoras, matriz semanal ni barras. Un director con daltonismo rojo-verde — público objetivo principal — **no puede distinguir una tienda que cumple de una que falla**, el dato más importante de la app.
- **Evidencia:** `index.html` funciones `cvar/pbg/pfg` (171-173) solo mapean color; `.pctpill`/`.cell` muestran solo el número teñido.
- **Fix:** Añadir glifo/etiqueta redundante (✓ a tiempo / ~ tarde / ✕ faltó, o texto 'OK'/'Tarde'/'Falta'). El calendario de detalle YA usa ✓/~/✕ (293-294) — replicar ese patrón en píldoras, KPIs y matriz.

#### A5. Diseño — Fetch fallido deja la vista en "Cargando…" para siempre
- **Qué está mal:** Cualquier error de red/4xx/5xx congela la vista en spinner eterno. Los render usan `await api(...)` sin try/catch; si el endpoint falla, el innerHTML nunca se reemplaza y el gerente no sabe qué pasó ni cómo reintentar.
- **Evidencia:** `renderHoy` (220), `renderSemana` (249), `abreSucursal` (260), `abreForm` (278) sin captura; `api()` hace `Promise.reject` en `!r.ok`. Igual en admin (`vForms/vUsers/vSuc/vAudit`).
- **Fix:** Envolver cada carga en try/catch con estado de error explícito y botón 'Reintentar'. Diferenciar 401 (sesión expirada → login) de error transitorio.

#### A6. Diseño/Seguridad — Inyección de nombres de sucursal en `onclick` inline
- **Qué está mal:** Nombres de tienda se inyectan en atributos `onclick` con comillas; solo se limpian comillas simples (`replace(/'/g,'')`) pero NO comillas dobles, backslashes ni caracteres que rompan JS/HTML. Un nombre con `"` rompe el render o permite inyección.
- **Evidencia:** `index.html` línea 241 `onclick="abreSucursal(${s.location_id},'${s.nombre.replace(/'/g,'')}',...)"` y 270/299 similares.
- **Fix:** Eliminar strings por `onclick` inline. Usar delegación de eventos con `data-*` (data-id, data-zona) y listener que lea `dataset`. Elimina el problema de escape y la manipulación del nombre visible.

---

### 🟡 MEDIA

#### M1. Mapeo — Formularios operativos/financieros PLOG fuera del catálogo
- **Qué:** Formularios con submissions PLOG no modelados: `1108481` Conteo Diario de Pollo (34 subs, 7 sucursales), `1096277`/`1161737` Fondo Fijo (4+4 subs), `1110926` Control Semanal de Merma (2 subs), `877137` Supervisión de Imagen (1 sub). Ninguno en raw ni catálogo.
- **Fix:** Revisar con negocio si deben medirse (Conteo de Pollo y Fondo Fijo parecen procesos reales de sucursal). Si sí, crear familia y mapeo; si son residuales/pruebas, documentar exclusión explícita.

#### M2. Diseño — Contraste insuficiente de texto secundario (WCAG AA)
- **Qué:** `--ink-3` (#6d6d7e) sobre tarjetas queda ~3.4-4.0:1 (bajo el mínimo 4.5:1) en metadatos que el gerente sí necesita: subtítulos de tienda, faltas, horas límite, último acceso, timestamps.
- **Fix:** Subir `--ink-3` a ~#8a8a9c (≈4.6:1 sobre `--card`); reservar el tono más tenue solo para decoración no esencial.

#### M3. Diseño — Patrón de edición inconsistente en el admin
- **Qué:** Coexisten 3 patrones de mutación sin criterio visible: toggle inline con guardado inmediato, select inline, y drawer con botón Guardar. El usuario no sabe cuándo un cambio ya se guardó.
- **Fix:** Regla clara — booleanos rápidos = toggle inline con toast; cambios multi-campo = drawer con Guardar/Cancelar. Mover el select 'Serie requerida' a drawer. Añadir feedback 'guardando…'.

#### M4. Diseño — Jerga técnica expuesta a gerentes no técnicos
- **Qué:** Términos internos sin traducir: `medicion`, `familia`, `scopes`, frecuencias snake_case (`diario_por_dia`, `semana_del_mes`), origen `exclusivo*` con asterisco sin explicar. Bitácora muestra JSON crudo aplanado.
- **Fix:** Diccionario de presentación en español natural ('diario_por_dia'→'Diario (por día laboral)'), hint para 'medición', tooltip para el asterisco, y formatear bitácora como 'campo: antes → después'.

#### M5. Diseño — Estados vacíos débiles (indistinguibles de 'Cargando')
- **Qué:** Sin datos reutiliza la clase `.loading`, ambiguo si carga o no hay nada. Sin ícono ni CTA. En Reportes se mezcla 'sin datos' con roadmap.
- **Fix:** Clase `.empty` distinta (ícono + título + subtexto + acción), separada de `.loading`.

#### M6. Diseño — PWA bloquea zoom (`user-scalable=no`)
- **Qué:** Impide zoom por pinza; mala práctica WCAG, penaliza a gerentes con baja visión.
- **Fix:** Quitar `user-scalable=no`; asegurar inputs con `font-size ≥16px` para evitar el zoom accidental en iOS (login 15px → 16px).

---

### 🟢 BAJA

- **B1. Mapeo — Inconsistencia de location en comisariato:** `recorrido_comisariato` aterriza 100% en location sintético -1; `comisariato_evaluacion` aterriza en sucursales reales. Comisariatos -2 (Laguna) y -3 (Querétaro) sin datos. *Fix:* regla única de asignación; verificar si faltan recorridos de Laguna/Querétaro.
- **B2. Veracidad — `deposito_valores` de Laguna excluido:** 6454 submissions raw existen pero `config_formularios` tiene Laguna `activo=f` → 0 filas de cumplimiento. No es inflación, es **omisión silenciosa** de trabajo reportado. *Fix:* confirmar con negocio si debe medirse; exponer en tablero familias con raw>0 pero activo=f.
- **B3. Diseño — Punto de 'frescura' siempre verde:** Comunica falsa confianza si el ETL se atrasa; además acopla el cerrar sesión. *Fix:* colorear por antigüedad del corte; separar logout a control explícito.
- **B4. Diseño — Accesibilidad de foco/táctil:** Sin `:focus-visible`, sin `aria-label` en toggles, objetivos táctiles <44px. *Fix:* outline de foco, aria-labels, área táctil ≥44px, chips como `<button>`.
- **B5. Diseño — Admin no responsive:** Grid fijo 230px+1fr sin breakpoints; tablas anchas fuerzan scroll horizontal. *Fix:* breakpoint ~900px que colapse sidebar; envolver tablas en `overflow-x:auto`.

---

## 3. Qué está BIEN confirmado (tranquilidad justificada)

Verificado a mano, no asumido:

- ✅ **Cumplimiento diario CUADRA (diff=0):** Recálculo manual de `rl2_entrega_t2` y `rl1_entrega_t1` en 3 sucursales de zonas distintas empata **día por día** con los días que realmente tuvieron submission. Cero falsos positivos, cero falsos negativos.
- ✅ **Calificaciones correctas:** Los `score_total` extraídos del payload jsonb coinciden con la tabla `calificaciones`. El clamp a 100 es mecánicamente correcto: `score_raw` preserva el valor real >100, ninguno mal clampeado, ninguno >100 ni <0.
- ✅ **Depósito de valores NO se infla:** 6230 días con múltiples depósitos (17987 de 18163 submissions) colapsan correctamente a 1 cumplimiento por día (diff=0).
- ✅ **Freeze correcto en formularios diarios y en 2025:** Los diarios no tienen el bug de doble conteo; las ventanas de 2025 (H1/H2) están correctamente congeladas.
- ✅ **Ingesta base sana:** Las 18 sucursales PLOG presentes y activas (última submission 2026-08-10/11 en todas), histórico continuo jun-2025 a ago-2026 (un solo día vacío en el arranque, 2025-06-25), volúmenes estables (~3,700-4,000/mes desde sep-2025), y las 50 form_template_ids en raw tienen familia mapeada. La rampa de sucursales (10-11 en jun-jul, 18 en dic) es **onboarding real, no un hueco de sync**.
- ✅ **Calidad de UI base alta:** Design system oscuro coherente, tokens consistentes, tabular-nums, mobile-first real en PWA, layout desktop correcto en admin. Apto para producción una vez corregidos los defectos de accesibilidad.

---

## 4. Lista priorizada de correcciones

**Orden recomendado (impacto en decisiones × esfuerzo):**

| # | Corrección | Severidad | Por qué primero |
|---|-----------|-----------|-----------------|
| 1 | **A1 — Agregar gemelos DO (877138/877139) al mapeo + dedup + re-ingestar** | ALTA | Subcuenta cobertura de auditorías; afecta decisiones sobre sucursales. Requiere decisión de negocio (copia distrito vs sucursal) — arrancar ya la conversación. |
| 2 | **A2 — Fix doble conteo periódico (acreditar a 1 ventana por fecha_local)** | ALTA | Infla cumplimiento de mantenimiento; recalcular 14 ventanas. Fix acotado. |
| 3 | **A3 — Correr/arreglar freeze de ventanas cerradas + resolver pending→missed** | ALTA | 9 ventanas con resultado aún mutable; investigar cutoff del job. |
| 4 | **A4 — Estado con ícono/etiqueta además de color** | ALTA | Accesibilidad crítica; patrón ✓/~/✕ ya existe, bajo esfuerzo. |
| 5 | **A5 — try/catch + 'Reintentar' en todos los fetch** | ALTA | Evita spinner eterno; alta frecuencia de impacto. |
| 6 | **A6 — Eliminar onclick inline → delegación con data-***  | ALTA | Cierra riesgo de inyección/rotura. |
| 7 | M1 — Decidir mapeo de Conteo de Pollo / Fondo Fijo | MEDIA | Requiere decisión de negocio; empatar con #1. |
| 8 | M2–M6 — Contraste, edición consistente, jerga, estados vacíos, zoom | MEDIA | Pulido de UX; agrupar en una sola pasada. |
| 9 | B1–B5 — Comisariato, Laguna deposito, frescura, foco/aria, admin responsive | BAJA | Documentar decisiones (B1/B2) y limpieza de UI. |

**Decisiones de negocio que bloquean fixes de datos (pedirlas ya):**
1. ¿`1161748`/`877138` (y `1161749`/`877139`) son la MISMA auditoría en dos roles? → habilita A1 y su dedup.
2. ¿`deposito_valores` de Laguna debe medirse? (B2)
3. ¿Conteo de Pollo / Fondo Fijo son procesos PLOG a medir? (M1)

**Nota final honesta:** El mapeo NO está roto de raíz — el motor de cálculo diario es confiable y está verificado. Pero hay una fuga concreta (gemelos DO ausentes) que hace que la cobertura de auditorías reportada sea **más baja que la realidad**, y dos bugs de cálculo en mantenimiento periódico. Son arreglos acotados, no un rediseño. Prioriza A1–A3 antes de presentar números de auditorías o mantenimiento a directores.