# Visibilidad: origen y caso de uso de cada formulario (2026-08-13)

Roberto pidió ver cuáles formularios son de CAS/compartidos y sus casos de uso — no mezclar. Clasificado con muestreo real del API (% de submissions PLOG vs total del template). **Guardado como campos `origen`/`quien_llena`/`caso_uso` en `config_formularios` → VISIBLE en el admin (badge por formulario).**

## 🔑 Regla de oro (garantía de datos)
**Sin importar si un formulario es exclusivo o compartido, el sistema SOLO ingiere y cuenta submissions de las 18 sucursales PLOG.** Verificado: 0 submissions de tiendas fuera de PLOG en la base. "Compartido" = la MISMA plantilla de Zenput la usan también las 68 tiendas CAS; NO significa que datos de CAS contaminen los números de PLOG. Filtramos por las 18 ubicaciones siempre.

> **Corrección Roberto 2026-08-13:** Autogestión, Comisariato-evaluación y los Mantenimientos SON de PLOG (la plantilla se reusa pero son formularios de ellos). Recorrido Diario agrupa en Comisariatos. Solo quedan como Compartido-CAS los 2 "DO ... CAS".

## 🟢 PLOG-exclusivos (22) — de PLOG
Diarios de tienda: **A1-A7 Alistamiento**, **L1-L7 Alistamiento**, **Alistamiento Hornos**, **Alistamiento SERVIR**, **RL1 Entrega 1er Turno**, **Checklist de Cierre**, **Depósito de Valores** (form propio por zona: NL/Laguna/Qro).
Semanal/mensual de tienda: **Autogestión de Calidad** (S1-S4), **Mtto Preventivo Mensual / Trimestral / Semestral**.
Supervisión/dirección: **PRO-SUC-1 Evaluación** (versión 2025V1), **PRO-SUC-4 Autoevaluación**, **Visita de Negocio**, **Visita de Seguimiento**, **RH-1 Visita**, **PRO-CSC-5 Vehículos**, **PRO-SC-6 Seguridad**.
Nuevos PLOG: **Revisión Operativa**, **Gestión y Finanzas**, **Matriz de Imagen**, **Auditoría a Proveedores**.

## 🟢 PLOG-exclusivos* (3) — plantilla compartida pero ≈100% PLOG (1-2 stray)
- **RL2 Entrega 2º Turno** (49/50 PLOG) · **PRO-SUC-3 Evaluación Procesos Operativos** (48/50) · **VCAL Verificación Calidad Integral** (49/50). El stray = tienda reasignada/prueba. Se tratan como PLOG.

## 🔵 Comisariatos (2) — categoría propia (PLOG)
- **Recorrido Diario Comisariato**: llega SIN location en Zenput → se atribuye por la zona del que contesta.
- **PRO-COM-2 Evaluación de Comisariatos**: evaluación del comisariato.
- Ambos son de PLOG; van en la categoría/vista "Comisariatos".

## 🟡 COMPARTIDOS con CAS (2) — únicos verdaderamente institucionales
| Formulario | Nombre en Zenput | % PLOG muestra | Quién lo llena |
|---|---|---|---|
| DO Supervisión Operativa | *DO SUPERVISION OPERATIVA **CAS** 1.2 | 28/50 | Gerente operativo |
| DO Control de Seguridad | *DO CONTROL OP. SEGURIDAD **CAS** 1.2 | 33/50 | Gerente operativo |

Son las plantillas institucionales que ambos grupos comparten (CAS en el nombre). Aun así, el sistema solo cuenta las submissions de las 18 PLOG. DO Control ya está fuera del arranque; DO Supervisión sí se mide.

## Uso en el producto
- **Badge visible en el admin y en el detalle del formulario:** 🟢 PLOG · 🟢 PLOG* · 🟡 Compartido CAS · 🔵 Comisariato. Con su caso de uso y quién lo llena.
- **Filtro opcional en las vistas:** "solo formularios PLOG-exclusivos" vs "todos" — por si quieren ver el cumplimiento sin las plantillas compartidas.
- **Drill-down coherente:** cada formulario muestra SIEMPRE sus áreas REALES (de `drilldown_spec`), nunca mezcladas con otro. (Corregido: el mockup demo había etiquetado DO Supervisión con áreas de PRO-SUC-3 — las reales de DO Supervisión son zonas físicas: Marinado, Cuarto Frío, Cocina, Almacenes, Congelador Papa, Máquina de Hielo…; las de PRO-SUC-3 son procesos: Alistamiento, Asignación de Funciones, Entrega de Turno, SERVIR…).
