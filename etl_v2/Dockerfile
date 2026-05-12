FROM python:3.12-slim

WORKDIR /app
COPY etl_v2/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY etl_v2/ ./etl_v2/
COPY sql/operacion_diaria/ ./sql/operacion_diaria/

ENV PYTHONUNBUFFERED=1
ENV TZ=America/Monterrey

# Start command override per Railway service:
#   web:       uvicorn etl_v2.api.main:app --host 0.0.0.0 --port $PORT
#   hourly:    python -m etl_v2.operacion_diaria.orchestrator.hourly
#   daily:     python -m etl_v2.operacion_diaria.orchestrator.daily_close
#   weekly:    python -m etl_v2.operacion_diaria.orchestrator.weekly_rollup
#   backfill:  python -m etl_v2.scripts.backfill --semanas N
CMD ["uvicorn", "etl_v2.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
