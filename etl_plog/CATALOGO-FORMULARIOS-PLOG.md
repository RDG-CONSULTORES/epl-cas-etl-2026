# Catálogo de Formularios PLOG — Definitivo
**Generado:** 2026-08-11 desde `etl_plog/config/catalogo.json` (fuente: Excel Definición de Políticas v3 + API Zenput en vivo + correcciones Roberto)

**Prioridad acordada:** el tablero arranca con CUMPLIMIENTO (los 23 formularios que lo miden); las calificaciones con drill-down por área vienen en la fase siguiente.

Correcciones aplicadas: PRO-SUC-1 usa las versiones vivas (954599 + 954592; 901109 excluida por ser la de CAS) · Conteo Diario de Pollo EXCLUIDO · Revisión a Vehículos INCLUIDO · Checklist Auditoría a Proveedores INCLUIDO (nuevo, 8 áreas).


## 📋 Cumplimiento (12 familias)

| Familia | Formulario | Form IDs | Zonas que lo usan | Frecuencia | Hora límite | Gracia |
|---|---|---|---|---|---|---|
| `alistamiento_a` | A1–A7 Alistamiento diario (uno por día Lun–Do | serie dia_semana: 954598,1040520,1040521,1040522,104052 | NL, Lag, Qro | Diario | 23:59 | 0 |
| `alistamiento_l` | L1–L7 Alistamiento diario (uno por día Lun–Do | serie dia_semana: 1040507,1040506,1040504,1040505,10386 | Lag, Qro | Diario | 23:59 | 0 |
| `rl1_entrega_t1` | RL1 Entrega Primer Turno | 954595 | NL, Lag | Diario | 15:00 | 0 |
| `rl2_entrega_t2` | RL2 Entrega Segundo Turno | 954602 | NL, Lag, Qro | Diario | 22:00 | 0 |
| `checklist_cierre` | Checklist de Cierre | 1040519 | NL, Lag | Diario | 01:00 (día sig.) | 0 |
| `deposito_valores` | Depósito de Valores (el de su región) | NL:997145 · Lag:1043394 · Qro:1043393 | NL, Qro | Diario | 23:59 | 0 |
| `visita_negocio` | Alistamiento Regional Visita Negocio | 1059179 | NL, Lag, Qro | Semanal | — | — |
| `visita_seguimiento` | Alistamiento Regional Visita Seguimiento | 954591 | NL, Lag, Qro | Por visita | — | 14 días por hallazgo |
| `rh1_visita` | RH-1 Alistamiento de visita Regional | 954604 | Lag, Qro | Mensual | — | — |
| `recorrido_comisariato` | Recorrido Diario Comisariato | 1161752 | NL, Qro | Diario | 23:59 | 0 |
| `pro_csc_5_vehiculos` | PRO-CSC-5 Revisión a Vehículos PLOG | 954594 | NL, Lag, Qro | Mensual | — | — |
| `matriz_imagen_plog` | MATRIZ DE CRITERIO DE IMAGEN PLOG (nuevo) | 1657858 | NL, Lag, Qro | Por definir | — | 0 |

## 📋+⭐ Cumplimiento y Calificación (11 familias)

| Familia | Formulario | Form IDs | Zonas que lo usan | Frecuencia | Hora límite | Gracia |
|---|---|---|---|---|---|---|
| `alistamiento_servir` | Alistamiento SERVIR | 1040698 | NL, Lag | Diario | 13:00 | 0 |
| `alistamiento_hornos` | Alistamiento Hornos | 997146 | NL, Lag | Diario | 12:00 | 0 |
| `autogestion_calidad` | Autogestión de Calidad S1–S4 | serie semana_del_mes: 1560060,1568530,1568532,1568536 | NL, Lag | Semanal | — | 2 días |
| `pro_suc_4_autoeval` | PRO-SUC-4 Autoevaluación de Procesos | 954596 | NL, Lag | Mensual | — | Hasta fin de mes |
| `mtto_mensual` | Mantenimiento Preventivo Mensual | 1572636 | NL, Lag, Qro | Mensual | — | Hasta fin de mes |
| `mtto_trimestral` | Mantenimiento Preventivo Trimestral | 1572200 | NL, Lag, Qro | Trimestral | — | El 3er mes |
| `mtto_semestral` | Mantenimiento Preventivo Semestral | 1572620 | NL, Lag | Semestral | — | Últimos 45 días |
| `do_supervision_operativa` | *DO Supervisión Operativa CAS 1.2 | 1161748 | NL, Lag, Qro | Mensual | — | — |
| `do_control_seguridad` | *DO Control Op. de Seguridad CAS 1.2 | 1161749 | Lag, Qro | Mensual | — | — |
| `revision_operativa_plog` | REVISIÓN OPERATIVA PLOG (nuevo) | 1638930 | NL, Lag | Por definir | — | 0 |
| `gestion_finanzas_plog` | GESTIÓN Y FINANZAS PLOG (nuevo) | 1638942 | NL, Lag | Por definir | — | 0 |

## ⭐ Calificación (6 familias)

| Familia | Formulario | Form IDs | Zonas que lo usan | Frecuencia | Hora límite | Gracia |
|---|---|---|---|---|---|---|
| `pro_suc_1` | PRO-SUC-1 / 1.1 Evaluación de Procesos | 954599,954592 | NL, Lag, Qro | Mensual | — | — |
| `pro_suc_3` | PRO-SUC-3 / 3.1 Evaluación Procesos Operativo | 1038657,1059183 | NL, Lag, Qro | Mensual | — | — |
| `vcal_calidad_integral` | VCAL25 / VCALQRO Verificación Calidad Integra | 954593,1059169 | Lag | Trimestral | — | — |
| `comisariato_evaluacion` | Verificación / PRO-COM-2 Comisariato | 954601,954600,1059170,1059182 | Lag, Qro | Mensual | — | — |
| `pro_sc_6_seguridad` | PRO-SC-6 Revisión Condiciones de Seguridad | 954603 | Lag | Bimestral | — | — |
| `auditoria_proveedores` | CHECKLIST AUDITORÍA PROVEEDORES PLOG | 1695114 | NL, Lag, Qro | Mensual | — | 0 |

## Notas operativas
- **Serie A/L (alistamiento diario):** el form esperado depende del día de la semana (A1=lunes … A7=domingo). El motor de cumplimiento lo maneja automático.
- **Autogestión de Calidad:** S1 se espera del día 1–7 del mes, S2 del 8–14, S3 del 15–21, S4 del 22 al fin de mes.
- **Depósito de Valores:** form distinto por zona (NL 997145 · Laguna 1043394 · Qro 1043393). Laguna dijo "No" en el Excel.
- **Recorrido Comisariato / Comisariato:** aplican solo a sucursales con comisariato — el sistema las detecta por historial de submissions (afinar con directores).
- **Vehículos (PRO-CSC-5):** el Excel lo mide "por unidad"; sin padrón de flotilla se mide por submissions/mes por sucursal (afinar cuando haya padrón).
- **Revisión Operativa (62%) + Gestión y Finanzas (38%):** par que suma una calificación combinada de 100%.
- **Auditoría a Proveedores:** política propuesta mensual (por validar). Áreas: Instalaciones · Higiene Personal · Manejo de Alimentos · Temperatura · Limpieza · Plagas · Almacenamiento · Maquila.
- **Matriz de Imagen:** sin campos de score en su diseño → solo cumplimiento (secciones Exterior/Interior).
- Detalle completo por zona (horarios, agenda, responsables): `catalogo.json` y el Excel v3.
