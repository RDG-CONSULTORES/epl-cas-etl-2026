# EPL CAS 2026 - Dashboard de Supervisiones

Dashboard móvil para El Pollo Loco México - Sistema CAS (Calificación, Auditoría y Seguimiento).

## 🚀 Features

- **Dashboard Principal**: KPIs, rankings de grupos y sucursales
- **Mapa Interactivo**: Visualización geográfica de sucursales
- **Histórico**: Tendencias por periodo
- **Alertas**: Sucursales críticas y sin supervisar
- **Drill-down**: Detalle de áreas/KPIs por sucursal
- **Panel Admin**: Configuración de periodos activos

## 📱 Mobile-First Design

Diseño optimizado para iOS con:
- Tab bar fijo inferior
- Header fijo superior
- Gestos táctiles
- Transiciones fluidas
- Tema oscuro

## 🛠 Tech Stack

- **Backend**: Flask + SQLAlchemy
- **Frontend**: Vanilla JS + CSS (no frameworks)
- **Database**: PostgreSQL (Railway)
- **Maps**: Leaflet.js
- **Deployment**: Railway (Docker)

## 📦 Deployment en Railway

### Opción 1: Deploy desde GitHub

1. Fork o sube este código a tu repositorio GitHub
2. En Railway, crea nuevo proyecto "Deploy from GitHub repo"
3. Selecciona el repositorio
4. Railway detectará el Dockerfile automáticamente
5. Configura las variables de entorno:

```env
DATABASE_URL=postgresql://postgres:PASSWORD@host:port/railway
SECRET_KEY=tu-secret-key-aqui
ADMIN_PASSWORD=tu-password-admin
```

6. Deploy!

### Opción 2: Railway CLI

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Crear proyecto
railway init

# Deploy
railway up
```

### Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | (requerido) |
| `SECRET_KEY` | Flask secret key | `epl-cas-2026-secret-key` |
| `ADMIN_PASSWORD` | Password del panel admin | `epl2026admin` |
| `PORT` | Puerto del servidor | `5000` |

## 🗄 Base de Datos

El dashboard se conecta a la BD existente con estas tablas:

- `periodos_cas` - Configuración de periodos
- `grupos_operativos` - 20 grupos operativos
- `sucursales` - 86 sucursales con coordenadas
- `supervisiones_operativas` - Supervisiones operativas
- `supervisiones_seguridad` - Supervisiones de seguridad
- `supervision_areas` - Detalle de 29 áreas operativas
- `seguridad_kpis` - Detalle de 10 KPIs seguridad

## 📋 Endpoints API

| Endpoint | Descripción |
|----------|-------------|
| `GET /api/periodos` | Lista de periodos |
| `GET /api/dashboard/{tipo}/{periodo_id}` | KPIs principales |
| `GET /api/ranking/grupos/{tipo}/{periodo_id}` | Ranking de grupos |
| `GET /api/ranking/sucursales/{tipo}/{periodo_id}` | Ranking de sucursales |
| `GET /api/mapa/{tipo}/{periodo_id}` | Datos para mapa |
| `GET /api/detalle/grupo/{id}/{tipo}/{periodo_id}` | Detalle de grupo |
| `GET /api/detalle/sucursal/{id}/{tipo}/{periodo_id}` | Detalle de sucursal |
| `GET /api/alertas/{tipo}/{periodo_id}` | Alertas |
| `GET /api/historico/{tipo}` | Histórico completo |

## 🔐 Admin Panel

Accede a `/admin` con la contraseña configurada para:

- Ver estadísticas generales
- Configurar periodo activo
- Ver periodos configurados

## 🎨 Colores de Calificación

| Rango | Color |
|-------|-------|
| ≥90% | 🟢 Verde |
| 80-89% | 🟡 Amarillo |
| 70-79% | 🟠 Naranja |
| <70% | 🔴 Rojo |

## 📄 License

© 2026 El Pollo Loco México / RDG Consultores
