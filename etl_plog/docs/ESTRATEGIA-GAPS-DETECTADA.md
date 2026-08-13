# Estrategia de gaps — detectada de la DATA REAL (2026-08-13)

Roberto pidió peinar/estandarizar/pulir los 5 gaps de negocio con comportamiento real, no supuestos. Minería sobre 44,771 submissions (jun-2025→ago-2026). Cada gap: qué dice la data + estrategia + qué se pregunta a directores (mínimo).

---

## GAP 1 — Cadencia real de los formularios "por visita/supervisión"

Método: intervalo mediano entre submissions consecutivas por sucursal + día de semana dominante. **La data revela una agenda de-facto clarísima:**

| Formulario | n | sucs | Intervalo | Cadencia detectada | Día dominante |
|---|---|---|---|---|---|
| pro_suc_4_autoeval | 343 | 18 | 7 días | **SEMANAL** | Domingo (320!) |
| autogestion_calidad | 79 | 8 | 7 días | SEMANAL (S1-S4) | Miércoles |
| comisariato_evaluacion | 113 | 4 | 3 días | SEMANAL | Lunes |
| visita_negocio | 149 | 16 | 16 días | **QUINCENAL** | Lunes |
| visita_seguimiento | 66 | 12 | 13.5 días | quincenal (condicional*) | Domingo |
| rh1_visita | 194 | 18 | 28 días | **MENSUAL** | Jueves |
| pro_suc_1 | 209 | 18 | 31 días | MENSUAL | Viernes |
| pro_suc_3 | 214 | 18 | 28 días | MENSUAL | Viernes |
| do_supervision_operativa | 102 | 18 | 34 días | MENSUAL | Viernes |
| vcal_calidad_integral | 77 | 17 | 28 días | MENSUAL | Viernes |
| mtto_mensual | 36 | 14 | 30 días | MENSUAL | Martes |
| pro_csc_5_vehiculos | 5 | 4 | 34 días | mensual (data escasa) | Jueves |
| do_control_seguridad | 33 | 11 | 59 días | **TRIMESTRAL** | Martes |
| pro_sc_6_seguridad | 24 | 17 | 50 días | TRIMESTRAL | Jueves |
| mtto_trimestral | 6 | 6 | — | trimestral (1/periodo) | — |
| mtto_semestral | 8 | 8 | — | semestral (1/periodo) | — |
| **revision_operativa_plog** | 3 | 3 | — | **SIN DATA suficiente** | — |
| **gestion_finanzas_plog** | 3 | 2 | — | **SIN DATA suficiente** | — |
| **matriz_imagen_plog** | 0 | 0 | — | **CERO submissions** | — |
| **auditoria_proveedores** | 0 | 0 | — | **CERO submissions** | — |

*visita_seguimiento = condicional ("donde haya hallazgos"), la cadencia es ruido — no se mide por calendario.

**Hallazgo fuerte:** las supervisiones se agendan por día de semana (todas las mensuales caen VIERNES; pro_suc_4 los DOMINGO). Eso NO es azar — es su agenda operativa. El sistema puede pre-cargar estas cadencias detectadas como propuesta y el director solo confirma.

**Estrategia:**
1. Sembrar en el admin la **cadencia + día esperado detectados** como default por formulario (no "por_visita" vacío).
2. **Nueva pantalla admin "Agenda"**: por formulario × zona (o × sucursal) capturar: frecuencia, día(s) esperados, hora si aplica, tolerancia. Alimenta el motor.
3. Solo **4 formularios necesitan que el director defina desde cero** (los 3 nuevos PLOG + auditoría proveedores: sin data). El resto = confirmar la propuesta detectada.
4. Motor: agregar frecuencia con **día-de-semana esperado** (hoy semanal ignora el día). Ventana semanal/mensual "con día objetivo" → on_time si cae el día ±tolerancia.

**Pregunta mínima a directores:** confirmar las 16 cadencias detectadas (checklist) + definir los 4 sin data.

### 🎯 ¿Cuáles podemos contestar NOSOTROS? (cruce Excel-propuesto vs data-real, 2026-08-13)
Clave: la cadencia del config = **la EXPECTATIVA/estándar** (lo que se DEBE hacer), no lo observado. Si ponemos expectativa = observado, todos salen ~100% y el sistema no sirve. Por eso el cruce importa:

- **✅ NOSOTROS lo contestamos (8): Excel-propuesto = data-observado.** Sin ambigüedad, política y realidad coinciden → los sembramos y listo: `rh1_visita` (mensual), `pro_suc_1` (mensual), `pro_suc_3` (mensual), `do_supervision_operativa` (mensual), `mtto_mensual`, `mtto_trimestral`, `mtto_semestral`, `autogestion_calidad` (semanal). (`pro_csc_5_vehiculos` coincide mensual pero n=5 + es por-unidad → default mensual, flag.)
- **⚠️ NO auto-contestar (7): Excel ≠ data — es decisión política, no medición.** La diferencia ES el insight de cumplimiento; adoptar lo observado = tapar el incumplimiento. Roberto (no necesariamente directores) decide si el estándar es lo que propuso o lo que hacen:
  - `visita_negocio`: propuso Semanal, hacen Quincenal (16d) → ¿el estándar es visitar cada semana (y miden la brecha) o cada 2?
  - `pro_suc_4_autoeval`: propuso Mensual, hacen Semanal domingo → data dice que ya es semanal.
  - `vcal_calidad_integral`: propuso Trimestral, hacen Mensual → lo hacen MÁS seguido.
  - `do_control_seguridad`: propuso Mensual, hacen Trimestral → lo hacen MENOS.
  - `pro_sc_6_seguridad`: propuso Bimestral, hacen ~Trimestral.
  - `comisariato_evaluacion`: propuso Mensual, hacen Semanal.
  - `visita_seguimiento`: condicional (no calendario) → no se mide por cadencia.
- **🚫 Necesitan definición (4): SIN DATA.** `revision_operativa_plog`, `gestion_finanzas_plog`, `matriz_imagen_plog`, `auditoria_proveedores` (los 3 nuevos PLOG + auditoría). Roberto/directores definen desde cero.

**Recomendación:** sembramos los 8 sólidos + defaults en los 7 (default = lo que propuso el Excel, marcado "realidad difiere") + 4 apagados hasta definir. Como el admin cambia cadencia sin deploy y sin tocar histórico (recompute-forward), el costo de un default ligeramente off ≈ 0 → NO bloquear el lanzamiento esperando junta. Los 7 que difieren son justo la lista de 2 minutos que Roberto revisa.

---

## GAP 2 — Depósito de Valores: sin límite fijo, ligado a movimiento/transporte

Data (jun-ago 2026, 18 sucursales):
- **Depósitos/día: mediana 3, rango 2-5.** Distribución: 2/día (574 veces), 3/día (532), 4/día (137), 1/día solo 40, 5/día raro.
- **Correlación con movimiento CONFIRMADA:** Lázaro Cárdenas 4.0/día y Gómez Morín 3.8 (alto) vs Campestre y Miguel de la Madrid 1.9 (bajo).
- **Horario disperso 14:00–23:00** (picos 16h y 22h), sin hora fija → consistente con recolección de transporte de valores a horas variables.

**Estrategia (tu intuición confirmada):** NO modelar como "N a hora fija". Regla de cumplimiento = **"al menos 1 depósito al día"** (defendible, no penaliza tiendas de bajo movimiento). El conteo real (2-4) se muestra como **dato informativo**, no como meta. Esto valida que el 99.8% actual ES correcto bajo "al menos 1/día".
- Opción futura si quieren exigir cobertura: meta configurable por sucursal en admin (ej. Lázaro ≥3), pero **arranque = ≥1/día**.

**Pregunta mínima:** ¿basta "al menos 1 depósito/día" o quieren exigir un mínimo por sucursal?

---

## GAP 3 — Pausar sucursal (cierres/incidencias)

Hoy siempre hay operación (sin feriados). Roberto: poder desactivar una sucursal si pasa algo y dejar de calificarla.

**Estrategia (ya casi listo):** el campo `sucursales.activo` YA existe y el motor YA filtra `WHERE activo`. Falta:
1. Toggle en admin "Pausar/Activar sucursal" (con motivo → config_audit).
2. **Pausa con rango de fechas** (`pausada_desde`/`pausada_hasta`): el motor no genera expectativas en ese rango, el histórico previo intacto, y al reactivar sigue. Mejor que un booleano crudo.
3. (Opcional futuro) tabla de feriados global si algún día aplica.

**Pregunta mínima:** ninguna — es capacidad, se construye. Solo confirmar que pausar = no generar expectativa (no borrar histórico).

---

## GAP 4 — Calificaciones sobre 100%: barrido exhaustivo

Barrí el campo TOTAL de las 23 familias con score. **Resultado limpio: solo UNA rebasa 100%.**

| Familia | scores | >100 | máx | Diagnóstico |
|---|---|---|---|---|
| **pro_suc_1** (ft 954599 "2025V1") | 209 | **30** | **104.2%** | Puntos bonus: 100 pts sobre base de 96 = 104%. |
| mtto_mensual | 36 | 0 | **0.0** | ⚠️ extractor P3 roto: "Calificación General" sale null → arreglar mapeo. |
| revision_operativa_plog | 3 | 0 | 58.7 | de 62% (por diseño <100; combina con gestión). |
| gestion_finanzas_plog | 3 | 0 | 38.1 | de 38% (par: revisión 62 + gestión 38 = 100). |
| Las otras 19 | — | 0 | 100.0 | ✅ ya topan en 100 exacto. |

**Estrategia de estandarización (100% absoluto, como pediste):**
- **Regla A (default) — clamp:** `score_estandar = min(100, raw)`. Aplica a pro_suc_1 (única que rebasa). Se guarda el raw aparte por si quieren ver "excelencia/bonus", pero el estándar mostrado = 100 tope.
- **Regla B (par ponderado):** revision_operativa (62) + gestion_finanzas (38) → un solo **score combinado /100**. Son un par diseñado; se muestran juntos.
- **Regla C (bug de extracción):** mtto_mensual/trimestral/semestral usan patrón "Calificación General" (P3) que el drilldown_spec lee mal (sale 0/null) → arreglar el matcher de áreas P3 (áreas "AREA X" sin "%", sub-ítems "Calificación X"). NO es dato malo, es extracción.
- Las 19 restantes: sin cambios.

**Pregunta mínima:** ¿pro_suc_1 se recorta a 100 (estándar) mostrando bonus aparte, o prefieren ver el 104% crudo?

---

## GAP 5 — Recorrido de comisariato: atribuir por quien contesta, no por responsable fijo

Roberto: "con que contesten el formulario; cualquiera puede; no asignar responsable". Qro y Laguna sí tienen comisariato (parcial) → habilitar la opción.

Data: el Recorrido no trae `location` (llega None), pero **`created_by.id` SÍ está** (Galilea = 394317) y mapea a `users` (email g.gallegos@**plog.com.mx**, rol Gerente). Los teams del payload vienen null, pero el usuario se resuelve por el endpoint users→team→zona.

**Estrategia:** eliminar el hardcode "Galilea→NL". En su lugar:
1. Los 3 comisariatos virtuales (ids -1/-2/-3, uno por zona) ya existen → **habilitar Qro y Laguna** (ya sembrados).
2. **Cualquier** submission del Recorrido se atribuye al comisariato-virtual de **la zona del que contesta**, resolviendo `created_by.id` → usuario PLOG → zona (dominio @plog.com.mx + team). Editable en admin (`comisariato_responsables`: persona→zona) por si un usuario no resuelve solo.
3. Cumplimiento del comisariato = ese Recorrido diario por zona (hoy NL ~5%, Qro/Laguna aparecerán al haber quien conteste).

**¿En qué nos pega no tener responsable fijo?** En nada operativamente — el cumplimiento es "el comisariato de la zona hizo su recorrido hoy". Solo perderíamos saber *quién* si rota la persona, pero eso queda en el histórico (created_by). Riesgo mínimo.

**Pregunta mínima:** confirmar que Qro y Laguna tienen comisariato (aunque sea parcial) para dejar sus 3 tableros activos.

---

## Resumen — de 5 gaps de negocio a decisiones acotadas
- **Gap 1:** ya no es "sin definir" — 16 cadencias DETECTADAS para confirmar + 4 forms nuevos a definir. Requiere pantalla "Agenda" en admin.
- **Gap 2:** regla = ≥1 depósito/día (confirma el 99.8%). Conteo real como info.
- **Gap 3:** pausar sucursal con rango de fechas (capacidad, ya casi está).
- **Gap 4:** solo pro_suc_1 rebasa (clamp a 100 + bonus aparte); + arreglar extractor P3 de mantenimientos; par revisión+gestión = 100 combinado.
- **Gap 5:** atribuir Recorrido por zona del que contesta (sin responsable fijo); habilitar Qro/Laguna.

Esto se incorpora al Motor v2 + pantalla Agenda en el admin. Los defaults salen de la DATA, no de supuestos → los directores validan, no definen desde cero (salvo 4 forms).
