# Auditoría Integral — Dashboard EPL CAS 2026

> Auditoría A→Z del dashboard de supervisiones CAS. Hecha el **2026-06-18** contra
> **producción en vivo** (https://epl-cas-etl-2026-production.up.railway.app).
> Metodología: principios de firmas top (McKinsey / KPMG / Deloitte / Bain):
> **una sola fuente de verdad, métricas MECE, integridad de periodo, indicadores
> líder vs rezagado, y "ningún número sin contexto".**
> Complementa `docs/MARCO-METRICAS-CAS.md` (el "deber ser"); aquí está el "cómo
> está hoy" + el plan de cierre.

---

## 0. Reglas de negocio confirmadas con el cliente (2026-06-18)

1. **Cadencia:** cada una de las **86 sucursales se supervisa 1 vez por trimestre = 4 veces al año.** En 2026 no hay re-supervisión rutinaria (1 dato por sucursal por trimestre).
2. **Cierre de trimestre POR CONTEO, no por fecha fija.** El trimestre "actual" se mantiene abierto hasta que las **86 sucursales** estén supervisadas — para darle chance a los supervisores. La fecha del calendario es **referencia**, no disparador.
3. **Alcance temporal del producto = 2026.** El histórico que importa es el **del año en curso** (Q1→Q4 2026). 2025 NO debe contaminar los números operativos.
4. **Claridad total:** cada número en pantalla dice qué mide, de qué trimestre, y sobre cuántas sucursales (cobertura).

---

## 1. Estado real de los datos (producción, 2026-06-18)

| Trimestre | id | Cobertura | Calificación (M1) | Distribución (E/B/R/C) | Estado |
|-----------|----|-----------|-------------------|------------------------|--------|
| **Q1 2026** | 7 | **86/86 (100%)** | **93.19** | 69 / 9 / 5 / 3 | ✅ Cerrado (completo) |
| **Q2 2026** | 8 | **70/86 (81.4%)** | **92.72** | 53 / 9 / 3 / 5 | 🟡 **En curso** |
| Q3 2026 | 9 | 0/86 | — | 0 / 0 / 0 / 0 | ⏳ Futuro |
| Q4 2026 | 10 | 0/86 | — | 0 / 0 / 0 / 0 | ⏳ Futuro |
| 2025 (6 periodos) | 1-4, 5, 6 | histórico | — | — | ⚠️ Contamina el "acumulado" |

**Lectura ejecutiva:**
- Estamos en **Q2 2026**, **70 de 86** sucursales supervisadas (faltan 16). El trimestre sigue abierto correctamente porque aún no llega a 86 → la regla de conteo **ya opera parcialmente** (ver §3).
- **YTD 2026 real ≈ 93** (promedio de Q1=93.19 y Q2 en curso=92.72), peso igual por sucursal.
- El dashboard hoy, en modo "Todos", muestra **90.78** — está **mal** (mezcla 2025).

---

## 2. 🔴 HALLAZGOS CRÍTICOS (rompen la confianza en el número)

### C1 — El "acumulado" todavía mete 2025 (la queja original sigue viva en modo "Todos")
- **Dónde:** `app.py:381-383` (`_score_cte(tabla, False)` sin filtro de año) y el selector "Todos" del frontend (`app.js`, label literal *"Histórico acumulado"*).
- **Síntoma medido:** modo "Todos" → **90.78**, cuando el YTD 2026 real es ≈93. La diferencia es puro arrastre de 2025.
- **Debe ser:** "Todos" / acumulado = **M3 YTD = solo periodos del año en curso** (reinicio 1-ene). 2025 jamás entra al número operativo (a lo más, vista histórica separada y etiquetada).

### C2 — Cobertura imposible: 87/86 = 101.2%
- **Dónde:** `app.py:397` cuenta `COUNT(DISTINCT sucursal_id)` sobre TODA la historia sin acotar a sucursales activas; `app.py:406` divide entre 86.
- **Causa:** existe ≥1 `sucursal_id` en supervisiones que **no está en las 86 activas** (sucursal cerrada / ID virtual histórico del cutover Puerto Rico→Otilio González, ver patrón snapshot-freeze).
- **Debe ser:** el numerador de cobertura y los conteos SIEMPRE se restringen a `sucursales.activo = true` **del periodo seleccionado**. Cobertura nunca puede pasar de 100%.

### C3 — El "cierre por conteo (86)" está a medias y NO auto-avanza al siguiente trimestre
- **Dónde:** `app.py:214-235` (`/api/periodo-contexto`) ya implementa la lógica correcta: *"si el periodo activo NO tiene 86/86, mantenerlo"* (`metodo: 'activo_incompleto'`). **Esto es justo lo que pidió el cliente y ya jala** (por eso Q2 sigue abierto con 70/86).
- **Lo que falta:**
  1. Cuando Q2 llegue a **86/86, nada activa Q3 automáticamente** — hoy depende de que un admin entre a `/admin` y lo cambie a mano (`app.py:160-178`).
  2. Persiste un **fallback por fecha** (`app.py:238-252`, `metodo: 'fecha'`) que contradice la regla "no por fecha fija". Debe degradarse a *referencia*, no a disparador.
  3. El umbral 86 está implícito (cuenta de activas). Conviene hacerlo explícito y a prueba de altas/bajas de sucursal.

### C4 — El "histórico/tendencia" mezcla 2025 y 2026
- **Dónde:** `app.py:1102-1133` (`/api/historico`) hace `CROSS JOIN periodos_cas` sin filtrar año → la gráfica de tendencia incluye los 6 periodos de 2025.
- **Debe ser:** la tendencia del producto = **serie Q1→Q4 del año en curso**. (2025 solo en una vista histórica explícita, opcional, fuera del MVP.)

---

## 3. 🟠 HALLAZGOS DE MÉTRICA / DISEÑO (definir al 100%)

### M1 — Faltan 3 de las 5 métricas del marco (header incompleto)
Confirmado contra `MARCO-METRICAS-CAS.md §7`:
- ✅ **M1 Calificación del Periodo** — implementada y correcta (promedio dentro del trimestre, peso igual por sucursal).
- ❌ **M2 Estado Actual** — no se expone como KPI de header.
- ❌ **M3 YTD (año en curso)** — no existe endpoint; "Todos" usa acumulado all-history (ver C1).
- ❌ **M4 Tendencia (Δ vs trimestre anterior)** — no se calcula.
- ⚠️ **M5 Cobertura** — se calcula pero con el bug C2, y no se muestra como badge junto a cada score.

### M2 — Definiciones canónicas a fijar (propuesta lista para aprobar)
| Métrica | Etiqueta UI | Definición a nivel sucursal | Agregación | Pregunta de negocio |
|---------|-------------|------------------------------|------------|---------------------|
| **M1** | "Calificación Qn" | promedio de sus supervisiones del trimestre (1 en 2026) | promedio simple por sucursal | ¿Cómo nos fue este trimestre? |
| **M2** | "Estado Actual" | su última supervisión (cualquier fecha **del año en curso**) | promedio simple | ¿Cómo está hoy? |
| **M3** | "YTD 2026" | promedio de sus M1 de los trimestres de 2026 | promedio simple | ¿Cómo va el año? |
| **M4** | "Tendencia Δ" | M1(Qn) − M1(Qn-1) | Δ del promedio del grupo | ¿Mejor o peor? |
| **M5** | "Cobertura" | supervisada en el trimestre (sí/no) | evaluadas / 86 activas | ¿De cuántas hablo? |

> **Regla de oro (consultoría):** prohibido "promedio de toda la historia". Mezcla años → no responde ninguna pregunta. Se elimina del producto (degradar "Todos" a "YTD 2026").

### M3 — Q2 está incompleto: hay que marcar "parcial" sin penalizar
Q2 va 70/86. Si comparas el 92.72 de Q2 (parcial) contra el 93.19 de Q1 (completo) sin avisar, induces a error (las 16 que faltan podrían mover el número). **Todo número de un trimestre abierto debe llevar badge "Parcial — 70/86"** (indicador líder), distinto del número de un trimestre cerrado (indicador rezagado, definitivo).

---

## 4. 🟡 HALLAZGOS DE FRONTEND (peinado de UI — del audit de templates/app.js)

| # | Hallazgo | Dónde | Acción |
|---|----------|-------|--------|
| F1 | Selector "Todos" se llama *"Histórico acumulado"* y jala all-history | `app.js` openPeriodSheet | Renombrar a **"YTD 2026"** y apuntar a M3 |
| F2 | Heatmap histórico **corta a 15 grupos** (`slice(0,15)`) sin avisar | `app.js:1047` | Mostrar todos o avisar "+N ocultos" |
| F3 | Historico no filtra año → muestra periodos 2025 | `app.js` loadHistorico + `app.py:1102` | Filtrar al año en curso |
| F4 | Color del KPI principal usa color del API sin fallback local a cortes | `app.js:406-407` | Fallback a `getColorClass()` |
| F5 | Etiquetas inconsistentes "Promedio" (grupo) vs "Calificación" (sucursal) | `app.js:667` vs `807` | Unificar a "Calificación" |
| F6 | Alertas: header dice "En Riesgo (70-79%)" pero el texto vacío dice "Sin grupos en riesgo" aunque la vista sea de sucursales | `app.js` alertas | Texto neutral |
| F7 | Tendencia de sucursal ignora el periodo (intencional) pero no está etiquetado como "histórico" | `app.js` sucursal-tendencia | Etiquetar "Histórico de la sucursal" |
| F8 | El header NO muestra M2/M3/M4/M5 (solo M1 + conteos) | `index.html:82-101` | Construir header de 4 métricas etiquetadas |

**Consistencia del semáforo:** ✅ correcta y unificada (cortes 90/80/70 en `app.py:get_color_class` y `app.js:getColorClass`, mismos cortes en ranking, mapa, distribución, áreas, alertas y leyendas). Único riesgo es F4 (fallback). Distribución cuadra exacto con cobertura (Q1: 69+9+5+3=86; Q2: 53+9+3+5=70). ✅

---

## 5. ✅ Lo que YA está bien (no tocar)
- M1 con alcance al periodo, sin fallback silencioso periodo→acumulado (`app.py:433`).
- Agregación de grupo y agrupación PLOG jerárquica, peso igual por sucursal (`app.py:539-554`).
- Drill-downs de grupo y sucursal respetan el `periodo_id` (fix `abca7b2`).
- Guard de `periodo_id='all'` en todos los endpoints (`con_periodo = bool(... != 'all')`).
- Estados "Pendiente" / "Sin revisión en este trimestre" en gris (no "0% rojo").
- Semáforo unificado + coordenadas de las 86 sucursales completas.

---

## 6. Plan de cierre (priorizado por impacto / esfuerzo)

### Fase A — Saneamiento del número (CRÍTICO, backend) — ✅ HECHA (2026-06-18, staging)
1. **A1 (C1):** ✅ "Todos" → **"Acumulado del Año"** (solo año en curso). Validado: 90.77 (con 2025) → **92.85** (solo 2026).
2. **A2 (C2):** ✅ conteos y cobertura solo `sucursales.activo = true`. Validado: 87/86 (101.2%) → **86/86 (100%)**. El fantasma era OTILIO GONZÁLEZ/Puerto Rico (cutover) → **se deja separado** (decisión cliente). Q1 = 85/86 (correcto: Otilio abre en Q2).
3. **A3 (C4):** ✅ `/api/historico` + selector solo año en curso. Validado: tendencia = Q1→Q4 2026.
4. **Frontend (D parcial):** ✅ etiquetas "Acumulado del Año", badge "En curso (x/86)", chip "revisadas". **Sin "YTD"** (rechazado por el cliente).

### Fase B — Métricas faltantes (backend + contrato API)
4. **B1 (M2):** endpoint/campo **M2 Estado Actual** (última eval del año por sucursal).
5. **B2 (M4):** **M4 Tendencia Δ** vs trimestre anterior (grupo y global).
6. **B3 (M3):** badge **cobertura** + flag **"parcial"** en cada score de trimestre abierto.

### Fase C — Cierre automático de trimestre (la regla de los 86)
7. **C1:** al alcanzar **86/86**, marcar el trimestre como cerrado y **auto-activar el siguiente** (job o lógica en `periodo-contexto` + persistencia del flag `activo`). Degradar el fallback por fecha a solo-referencia.

### Fase D — Frontend (header de 4 métricas + peinado)
8. **D1:** header con **M1 Qn (+badge cobertura) · M2 Estado Actual · M3 YTD · M4 Δ**, todos etiquetados.
9. **D2:** F1–F7 (renombrar "Todos"→YTD, quitar slice 15, fallback color, unificar labels, etiquetar tendencias).

### Validación (todas las fases)
- Probar E2E en **staging** (rama `fix/dashboard-metrica-ultima-eval`, DB = copia de prod) antes de PR a prod.
- Criterio de aceptación: YTD 2026 ≈ 93 (no 90.78), cobertura ≤ 100%, Q2 marcado "parcial 70/86", tendencia solo 2026.
</content>
</invoke>
