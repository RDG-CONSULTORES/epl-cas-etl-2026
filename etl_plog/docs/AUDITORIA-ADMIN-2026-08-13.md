# Auditoría: qué tenemos para el Admin Panel (2026-08-13)

Roberto: auditar lo que hay antes de construir el admin panel a la altura. Deep research de diseño corriendo en paralelo (wf_963e216b-0c0).

## Hallazgo clave: el MODELO DE DATOS del admin ya está ~80% listo
Porque desde el día 1 diseñamos la config como tablas VIVAS en BD + bitácora (siguiendo R#1). El admin panel es "solo" UI + endpoints de escritura sobre un modelo ya correcto. NO hay que rediseñar datos.

## ✅ Lo que YA existe (capa de datos)
| Entidad | Tabla | Campos editables | Bitácora |
|---|---|---|---|
| Formularios/políticas | `config_formularios` (87 filas) | activo, frecuencia, hora_limite, dias_gracia, medicion, origen, caso_uso, params | `config_audit` (12 entradas) ✅ |
| Sucursales | `sucursales` (21) | activo, es_comisariato, serie_requerida | (usa config_audit) |
| Usuarios | `usuarios` (2) | rol, activo, password_hash, ultimo_login, bloqueo | `acceso_audit` (3) ✅ |
| Accesos | `user_scopes` (2) | zona, location_ids[] | ✅ |

- Auth ya soporta roles admin/director/viewer y `crea_usuario()` con scopes.
- El freeze garantiza que editar una política NO reescribe el histórico (crítico para un admin que edita en vivo).

## 🔴 Lo que FALTA
1. **Endpoints de ESCRITURA (todo):** el API hoy es solo lectura + auth. Faltan:
   - `PUT /api/admin/formularios/{familia}/{zona}` (toggle activo, editar cadencia/hora/gracia) + escribir config_audit.
   - CRUD `usuarios` + `user_scopes` (alta, reset password, bloquear, editar scopes).
   - `PUT /api/admin/sucursales/{id}` (pausar, comisariato, serie).
   - `GET /api/admin/audit` (leer bitácora).
   - Todos gated a `rol=admin` (ya existe `solo_admin` dependency).
2. **Tabla `report_schedules`** (config de reportes: destinatarios, cadencia, canal) — NO existe.
3. **UI del admin** (0) — la pantalla en sí.
4. **Validación server-side** de ediciones (frecuencia válida, hora formato, gracia ≥0).
5. Recompute-forward al editar: tras cambiar una política, disparar recálculo de ventanas NO congeladas (el motor ya respeta freeze, solo falta el trigger desde el admin).

## Entidades y sus acciones (mapa para el diseño)
- **Formularios** (29 familias × 3 zonas): toggle on/off por zona · editar cadencia+día+hora+gracia · ver origen/caso_uso (solo lectura) · ver bitácora inline. Filtro por zona/tipo/origen.
- **Usuarios**: alta (usuario+password+rol) · asignar scope (zonas ☑ + sucursales) · reset password · activar/bloquear.
- **Sucursales**: pausar/activar (con rango fechas) · marcar comisariato · serie requerida A/L/cualquiera.
- **Reportes**: destinatarios (usuarios/correos) · cadencia (semanal…anual) · canal (correo/WhatsApp) · scope.
- **Bitácora**: quién cambió qué y cuándo (config_audit + acceso_audit unificados), con diff antes/después.

## Conclusión
El admin es una capa de UI + ~10 endpoints de escritura sobre datos ya listos. Estimado: 1 tabla nueva (reportes) + endpoints admin + UI. El deep research define el layout/patrones; con eso se construye. Prioridad de construcción sugerida (confirmar con research): Formularios (toggle+cadencia) → Usuarios/accesos → Sucursales → Bitácora → Reportes.
