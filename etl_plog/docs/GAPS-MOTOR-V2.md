# Gaps del Motor — inventario honesto (auditoría 2026-08-13)

Respuesta a "¿tenemos todos los gaps arreglados en v2?": **NO — y la lista original de 5 estaba incompleta.** Auditoría contra data real encontró ~5 más. Se separan en: **(A) gaps de código** (los arreglamos nosotros) y **(B) ambigüedades de negocio** (requieren decisión de Roberto/directores — no se pueden "programar" sin la regla).

## A. Gaps de CÓDIGO (los cierra el Motor v2)

1. **Freeze / policy_snapshot** — hoy el histórico muta si cambia una política. Congelar ventana con la política usada. ⚠️ sutileza: congelar SOLO cuando venció ventana+gracia (no en el cierre diario), o una submission tardía dentro de gracia dejaría un "missed" congelado mal.
2. **expected_occurrence materializada** — hoy genera al vuelo; pre-materializar horizonte 35d (Prefect).
3. **Effectivity (valid_from/valid_to)** en config_formularios + audit con effective_at.
4. **Serie A/L por sucursal** — hoy cuenta ambas series → la no-usada sale 0% falso. Asignar la serie real por tienda (auto-detect por historial o campo admin).
5. **Tests** — cero. El motor es el corazón; necesita suite (ventanas por frecuencia, estados on_time/late/missed/pending, bordes de gracia, DST no aplica MX pero probar TZ).
6. **submission_id NO se guarda en cumplimiento** (motor pone sub_id=None) → V4 no puede ligar al submission real. Resolver al materializar.
7. **`sucursales_aplica` en texto libre no se interpreta** — el motor solo entiende "comisariato". Valores reales sin manejar: "Flotilla" (aplica por UNIDAD, no por sucursal → Vehículos hoy se mide mal por tienda), "Donde haya hallazgos" (condicional → NO debe generar expectativa fija), "Las asignadas a serie L" (asignación de serie como texto → gap 4). Hay que normalizar a campo estructurado.

## B. Ambigüedades de NEGOCIO (necesitan decisión — no las inventamos)

8. **`por_visita` = 10 familias generan CERO expectativa hoy** → invisibles en cumplimiento. Incluye visita_seguimiento y los 3 forms nuevos (Revisión Operativa, Gestión y Finanzas, Matriz Imagen). **¿Cuál es la cadencia esperada de cada una?** El Excel dice "Por definir" en los nuevos y "por visita" en seguimiento. Sin regla, o no se miden (solo calificación) o se les pone frecuencia. **Decisión de directores.**
9. **N-veces-por-día** — Depósito de Valores tiene 3-4 submissions/día por sucursal (por turno/cajero). Hoy el motor cuenta "al menos 1 = cumplió". **¿La política es 1/día o N/día?** Si es N, hoy se sobre-reporta cumplimiento. Research: N-per-día = múltiples filas de política con ventanas distintas. **Decisión: confirmar política real.**
10. **Calendario de cierres/feriados** — un día que la tienda cerró legítimamente hoy cuenta como "missed". Sin tabla de excepciones (feriados, cierre por remodelación, apertura a media semana), el % se castiga injusto. **Decisión: ¿hay días válidos sin operación?**
11. **Scores >100% (bonus)** — 60 casos en data (visto 104%). Para la fase de calificación: ¿se clampean a 100 o se muestran? **Decisión de negocio.** (No bloquea cumplimiento.)
12. **Responsable comisariato Querétaro** — Recorrido Diario Qro marca 0% porque no hay a quién atribuirle (solo Galilea→NL mapeada). **Decisión: ¿quién llena el de Qro/Laguna?**

## Veredicto
- El **Motor v2 cierra los 7 gaps de código (A)** en 1 sesión enfocada + tests.
- Los **5 de negocio (B) NO los cierra el código** — se dejan con default sensato + bandera "por confirmar" y se resuelven cuando los directores validen el Excel. El sistema queda diseñado para absorberlos sin retrabajo (config viva en admin).
- **Conclusión honesta:** con Motor v2 tendremos el motor *técnicamente sólido y listo para construir encima*, pero el % de cumplimiento no será "verdad final" hasta cerrar los 5 de negocio con los directores. Eso está bien: se lanza con cumplimiento de los formularios SIN ambigüedad (diarios de tienda: RL1/RL2/cierre/alistamientos/depósito) y se activan los demás conforme se definan.
