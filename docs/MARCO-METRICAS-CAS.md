# Marco de Medición — Dashboard EPL CAS

> Documento de diseño (el "deber ser") para el cálculo de calificaciones por
> sucursal, grupo operativo y agrupación. Acordado con el cliente el
> **2026-06-18**. Este documento es la fuente de verdad; el código (`app.py`)
> debe reflejarlo.

---

## 0. Principio rector

> **Ningún número de desempeño se muestra sin tres cosas: qué mide, de qué
> periodo, y sobre cuántas sucursales (cobertura).**

El defecto histórico del dashboard fue violar esto: un promedio de **toda la
historia** (que incluía 2025) se presentaba como si fuera el del trimestre. Un
promedio de dos años no se mueve por definición → de ahí el reporte "no se
actualiza / parece el acumulado".

---

## 1. Unidad de verdad

Una **supervisión** = `(sucursal, fecha, calificación 0–100)`.
Todo lo demás se deriva de ahí, con **una sola definición** por métrica
reutilizada en todo el código. Cero fórmulas paralelas.

---

## 2. Diccionario de métricas

| # | Métrica | Pregunta | Definición a nivel sucursal | Agregación a grupo |
|---|---------|----------|------------------------------|--------------------|
| **M1** | **Calificación del Periodo** | ¿Cómo nos fue en *este trimestre*? | **Promedio de las supervisiones de la sucursal dentro del trimestre.** Sin supervisión en el trimestre → **N/A** (no es 0, no se arrastra). | Promedio simple de las M1 de las sucursales evaluadas (peso igual por sucursal) |
| **M2** | **Estado Actual** | ¿Cómo está la sucursal *hoy*? | Su **última** supervisión registrada (de cualquier fecha) | Promedio simple de las M2 |
| **M3** | **YTD (acumulado del año)** | ¿Cómo va el *año*? | Promedio de sus **M1 de los trimestres del año en curso** (Q1, Q2, …) | Promedio de las M3 |
| **M4** | **Tendencia (Δ)** | ¿Vamos *mejor o peor*? | M1 del trimestre − M1 del trimestre anterior | Δ del promedio del grupo |
| **M5** | **Cobertura** | ¿De *cuántas* sucursales hablo? | Evaluada en el periodo (sí/no) | Evaluadas / activas del grupo |

**Prohibido:** "promedio de toda la historia". No responde ninguna pregunta de
negocio (mezcla años). Se elimina del producto.

### Decisión clave (re-supervisión)
Si una sucursal se supervisa **más de una vez en el mismo trimestre** (ej. una
visita correctiva), **M1 = el promedio de esas supervisiones**. Premia la
consistencia y evita que una segunda visita "borre" una mala calificación.

---

## 3. Reglas de agregación y ponderación

- **Peso igual por sucursal** (cada sucursal es una unidad de rendición de
  cuentas del gerente). Es el default en grupos y rankings.
- **Sucursal sin datos en el periodo:** se **excluye** del promedio (no cuenta
  como 0). Aparece como N/A / gris.
- **Agrupación (PLOG = Nuevo León + Laguna + Querétaro):** **jerárquica** —
  `PLOG = promedio simple de los scores de sus subgrupos` (cada subgrupo pesa
  igual sin importar su número de sucursales). Subgrupo sin datos en el periodo
  → excluido del promedio de la agrupación.
- **Vista futura opcional** (no MVP): ponderación por ventas/tráfico ("impacto
  de negocio"), claramente etiquetada y separada del número operativo.

---

## 4. Semántica de periodo

- **Periodo = trimestre** (ventana de supervisión: Q1–Q4). El periodo "activo"
  se determina por **fecha**, nunca por adivinanza ni por fallback.
- **YTD se reinicia el 1 de enero.** "Acumulado del año" ≠ "acumulado de toda la
  vida".
- **Histórico** = la **serie** de M1 trimestre a trimestre (gráfica de
  tendencia), no un promedio aplanado.
- **Sin fallback silencioso.** Si el periodo seleccionado no tiene datos para una
  entidad, se muestra **N/A**, nunca el histórico disfrazado.

---

## 5. Casos borde

| Caso | Regla |
|------|-------|
| Sucursal sin eval en el periodo | N/A explícito, gris, excluida del promedio |
| Cobertura parcial (ej. Laguna 4/6) | Mostrar M1 **+ badge de cobertura** (M5) |
| Re-supervisión en el mismo trimestre | **Promedio** de las del trimestre (ver §2) |
| Alta/baja/cierre de sucursal | Patrón snapshot-freeze + ID virtual histórico (ya existente) |

---

## 6. Cómo se traduce a cada vista del dashboard

| Vista | Métrica(s) que muestra |
|-------|------------------------|
| **Header KPI** | **M1** del periodo + **M5** cobertura + **M4** (Δ). Toggle a **M3 (YTD)** y **M2 (Estado Actual)**, **ambos etiquetados** |
| **Ranking de grupos / sucursales** | **M1** del periodo seleccionado |
| **Detalle de sucursal** | **M2** (última foto) + desglose de áreas de esa supervisión + sparkline de tendencia |
| **Histórico** | Serie de **M1** por trimestre |
| **Selector "Todos"** | **M3 (YTD)**, nunca "all-history" |

---

## 7. Estado de implementación

| Pieza | Estado |
|-------|--------|
| M1 con alcance al periodo (fin del fallback a histórico) | ✅ Hecho |
| Agregación de grupo con peso igual por sucursal | ✅ Hecho |
| M1 = promedio de supervisiones **dentro** del trimestre (re-supervisión) | ✅ Hecho |
| Agrupación PLOG jerárquica (promedio de subgrupos) | ✅ Hecho |
| Fix bug `periodo_id='all'` en drill-downs | ✅ Hecho |
| Header con M3 (YTD) + M2 (Estado Actual) etiquetados | ⏳ Frontend — siguiente iteración |
| Badge de cobertura (M5) junto a cada score | ⏳ Frontend — siguiente iteración |
| M4 (Δ vs trimestre anterior) | ⏳ Siguiente iteración |

---

## 8. Gobernanza

- **Umbrales de color** (validar contra metas reales de EPL):
  ≥90 excelente · ≥80 bueno · ≥70 regular · <70 crítico.
- Cada número en pantalla lleva etiqueta de métrica + periodo + cobertura.
- Cualquier cambio de definición se actualiza **primero aquí**, luego en código.
