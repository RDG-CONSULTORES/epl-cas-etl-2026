# EPL CAS ETL 2026

ETL diario para sincronizar supervisiones de Zenput a PostgreSQL.

## 📊 Datos que procesa

- **Supervisiones Operativas**: 29 áreas de evaluación
- **Supervisiones Seguridad**: 11 KPIs

## 🚀 Deploy en Railway

1. Conectar este repo a Railway
2. El cron se ejecuta automáticamente a las 12:00 UTC (6:00 AM México)

## ⚙️ Variables de Entorno

```
DATABASE_URL = postgresql://...
ZENPUT_TOKEN = cb908e0d4e0f5501c635325c611db314
```

## 🔄 Ejecución Manual

```bash
pip install -r requirements.txt
python etl_sync.py
```

## 📅 Cron Schedule

- `0 12 * * *` = 12:00 UTC = 6:00 AM México (todos los días)

## 📁 Base de Datos

| Tabla | Descripción |
|-------|-------------|
| grupos_operativos | 20 grupos |
| sucursales | 86 sucursales |
| supervisiones_operativas | Supervisiones CAS operativas |
| supervision_areas | 29 áreas por supervisión |
| supervisiones_seguridad | Supervisiones CAS seguridad |
| seguridad_kpis | 11 KPIs por supervisión |
| sync_log | Log de ejecuciones |
| sync_checkpoints | Última fecha sincronizada |

## 🔗 APIs

- **Zenput API**: Form 877138 (operativas), Form 877139 (seguridad)
- **PostgreSQL**: Railway hosted

---
Creado para El Pollo Loco México - RDG Consultores 2026
