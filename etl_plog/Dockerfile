FROM python:3.12-slim
WORKDIR /app
COPY etl_plog/requirements.txt /app/etl_plog/requirements.txt
RUN pip install --no-cache-dir -r /app/etl_plog/requirements.txt
COPY etl_plog /app/etl_plog
COPY sql /app/sql
ENV PYTHONUNBUFFERED=1 TZ=America/Monterrey PLOG_SCHEMA=plog
EXPOSE 8000
CMD ["sh","-c","uvicorn etl_plog.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
