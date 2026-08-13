# Diseño del Admin Panel PLOG (síntesis research 2026-08-13)

Basado en deep research verificado 3-0 (`research-admin-design-raw-2026-08-13.json`) + auditoría (`AUDITORIA-ADMIN-2026-08-13.md`). Mismo design system oscuro (#0a0a0f / naranja).

## Layout (verificado)
- **Sidebar izquierdo** con 5 secciones nombradas por el TRABAJO, no por la tabla: **Formularios · Usuarios y accesos · Sucursales · Reportes · Bitácora**.
- **Top bar delgado**: búsqueda global, usuario logueado, y superficie de feedback de guardado (toast).
- Desktop-first (admin denso en datos), responsive suficiente para tablet.

## Patrón de edición por entidad (verificado)
- **Toggle switch = efecto instantáneo:** activar/desactivar formulario por zona, pausar sucursal, bloquear usuario. Se guarda solo, con toast.
- **Drawer lateral (panel deslizante) = editar registro completo manteniendo la lista visible:** editor de política (cadencia+día+hora+gracia+tipo) y editor de usuario (rol+scopes). Con **botón Guardar explícito** (no autosave para lo que necesita revisión) + toast + bitácora.
- **Modal = SOLO confirmaciones destructivas:** borrar/pausar, reset password.

## Reglas UX (verificadas)
- **Toggle vs Guardar:** toggle solo si aplica al instante; si necesita revisión (cadencia/hora) → campos + botón Guardar prominente. Siempre feedback de guardado.
- **Permisos por ROL** (admin/director/viewer) con descripción en lenguaje simple + **mostrar el scope explícito de cada usuario** ("Ve Laguna · 6 sucursales"), no implícito.
- **Acciones destructivas** → diálogo de confirmación (aunque el botón sea rojo).
- **Un solo botón primario** con verbo+objeto ("Guardar política", no "Guardar/Aplicar/Actualizar"). Jerarquía primario/secundario/peligro.
- **Color solo para estado** (verde ok / rojo falla / amarillo pendiente); jerarquía por tipografía y espacio.
- Estados vacíos y de error explícitos; toda edición de config a `config_audit`.

## Pantallas (wireframe verbal)
1. **Formularios** — tabla: familia · nombre · origen(badge) · tipo · [toggle activo por zona] · cadencia · hora · acción(editar→drawer). Filtros: zona, tipo, origen, activos/todos. Drawer: editor de política con campos condicionales según frecuencia. Bitácora inline del formulario.
2. **Usuarios** — tabla: usuario · nombre · rol(badge) · scope("Laguna·6 suc") · estado · acciones(editar→drawer, reset pass→modal, bloquear→toggle). Botón "+ Nuevo usuario"→drawer (usuario+password+rol+zonas☑+sucursales). Descripción de cada rol.
3. **Sucursales** — tabla: nombre · zona · [toggle activo] · [toggle comisariato] · serie requerida(select A/L/cualquiera) · director. Pausar con rango de fechas (drawer).
4. **Reportes** — lista de programaciones: cadencia · destinatarios · canal · scope · [toggle activo]. "+ Nueva". (tabla report_schedules nueva).
5. **Bitácora** — feed unificado config_audit + acceso_audit: quién · qué cambió (diff antes→después) · cuándo. Filtros por tipo/usuario/fecha.

## Endpoints admin (todos gated a rol=admin)
GET/PUT `/api/admin/formularios[/{familia}/{zona}]` · GET/POST/PUT `/api/admin/usuarios[/{id}]` · PUT `/api/admin/sucursales/{id}` · GET/POST/PUT `/api/admin/reportes` · GET `/api/admin/audit`. Validación server-side. Tras editar política → recompute-forward de ventanas no congeladas (cron diario o trigger).

## Orden de construcción
1. Endpoints admin + tabla report_schedules. 2. UI shell (sidebar+topbar+toast+drawer+modal reutilizables). 3. **Formularios** (el core: toggle+drawer política) → 4. Usuarios/accesos → 5. Sucursales → 6. Bitácora → 7. Reportes.
