# Formulación de los 5 formularios EN ESPERA (listos para activar)

**2026-08-13** · Roberto: extraer cómo están construidos y dejarlos listos para cuando los directores contesten la cadencia. Estructura sacada de `primary_field_data` de cada activity (sirve aunque tengan 0 submissions). Datos crudos: `etl_plog/config/formulacion_5_espera.json`.

Estado en config: **activo=false en las 3 zonas** (bitácora en `config_audit`). Al activar solo falta 1 dato: **la cadencia** (frecuencia + día + hora). El scoring/drill-down YA está mapeado.

---

## 1. DO Control Operativo de Seguridad CAS 1.2 (ft 1161749 / act 1160314)
- **185 campos** · 57 sí/no + 57 fotos + 13 secciones + 36 fórmulas + 2 firmas.
- **Patrón score P1** (CAS-style). Total = `CALIFICACION PORCENTAJE %`.
- **13 áreas para drill-down**, cada una con PUNTOS MAX / PUNTOS TOTALES / PORCENTAJE %:
  Comedor · Asadores · Marinado · Bodega · Horno · Freidoras · Centro de Carga · Azotea · Exterior · Programa Protección Civil · Bitácoras.
- ✅ **Listo total** — extractor P1 ya lo maneja. Data histórica: 33 submissions. Solo falta cadencia (data sugería trimestral; Excel decía mensual → definir).

## 2. Revisión Operativa PLOG (ft 1638930 / act 1637360) 🆕
- **95 campos** · 39 sí/no + 6 secciones + 6 fórmulas.
- **Patrón score P4 (secciones ponderadas).** Total = `RESULTADO TOTAL SOBRE 62%`.
- **5 áreas con peso embebido en el título:** Mantenimiento 12% · Limpieza e Higiene 15% · Imagen de la Tienda 10% · Procesos Operativos 15% · Temperaturas (Papa y Plataformas) 10% = **62%**.
- ⚠️ **Es PAR con Gestión y Finanzas** → juntos = 100% (ver abajo).

## 3. Gestión y Finanzas PLOG (ft 1638942 / act 1637372) 🆕
- **42 campos** · 16 sí/no + 2 secciones + 3 fórmulas.
- **Patrón P4 ponderado.** Total = `RESULTADO TOTAL DE 38%`.
- **2 áreas:** Procesos Administrativos 13% · Indicadores Financieros 25% = **38%**.
- ⚠️ **REVISIÓN OPERATIVA (62%) + GESTIÓN Y FINANZAS (38%) = 100% combinado.** Se muestran como una sola calificación de tienda. El motor/vista deben sumar ambos → score_estandar PLOG.

## 4. Matriz de Criterio de Imagen PLOG (ft 1657858 / act 1656181) 🆕
- **33 campos** · 23 sí/no + 4 secciones + 0 fórmulas.
- **🔑 HALLAZGO: NO tiene score** (0 fórmulas) → es **CUMPLIMIENTO PURO** (checklist sí/no), NO calificación. Más simple de lo pensado.
- **4 secciones:** Exterior · Interior · Exterior-Interior · Firmas.
- Al activar: se mide como "¿la hicieron?" (existencia), sin porcentaje. **Reclasificar en catálogo: cumplimiento, no calificación.**

## 5. Checklist Auditoría a Proveedores PLOG (ft 1695114 / act 1693323) 🆕
- **56 campos** · 32 sí/no + 10 secciones + 9 fórmulas + firmas.
- **8 áreas de auditoría (drill-down):** Instalaciones · Higiene Personal · Manejo de Alimentos · Temperatura · Limpieza · Plagas · Almacenamiento · Maquila (+ Firmas + Calificación General).
- ⚠️ **Las 9 fórmulas se llaman genéricamente "Formula"** (sin título descriptivo) y **0 submissions** → los valores/mapeo exacto del score se resolverán con el **primer envío real**. Las 8 áreas ya están claras; el % por área se cablea cuando llegue data.

---

## Reclasificaciones que salieron de este análisis (aplicar al catálogo)
1. **matriz_imagen_plog → cumplimiento** (no calificación): 0 fórmulas, es checklist.
2. **revision_operativa + gestion_finanzas = par 62+38=100**: score combinado, no separados.
3. **auditoria_proveedores**: áreas mapeadas, pero fórmulas resuelven con 1er submission (marcar "score pendiente de data").

## Qué falta para activar cada uno (checklist)
| Form | Estructura | Score/áreas | Falta |
|---|---|---|---|
| DO Control Seguridad | ✅ | ✅ P1, 13 áreas | cadencia |
| Revisión Operativa | ✅ | ✅ P4, 5 áreas 62% | cadencia (par c/gestión) |
| Gestión y Finanzas | ✅ | ✅ P4, 2 áreas 38% | cadencia (par c/revisión) |
| Matriz Imagen | ✅ | ✅ cumplimiento puro | cadencia |
| Auditoría Proveedores | ✅ | 🔶 8 áreas ok, % con 1er envío | cadencia + 1er submission |

**Conclusión:** los 5 quedan plug-and-play. Cuando los directores contesten la cadencia, se activa el toggle en el admin y entran al tablero sin trabajo adicional (salvo auditoría, que además espera su primera submission para el % por área).
