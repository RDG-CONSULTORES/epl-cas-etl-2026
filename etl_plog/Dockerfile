FROM python:3.12-slim
WORKDIR /app

# pg_dump 18 (coincide con el servidor Postgres 18) para el respaldo off-site.
# Repo PGDG, detectando el codename de Debian de la imagen base.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg lsb-release \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update && apt-get install -y --no-install-recommends postgresql-client-18 \
 && apt-get purge -y lsb-release && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY etl_plog/requirements.txt /app/etl_plog/requirements.txt
RUN pip install --no-cache-dir -r /app/etl_plog/requirements.txt
COPY etl_plog /app/etl_plog
COPY sql /app/sql
ENV PYTHONUNBUFFERED=1 TZ=America/Monterrey PLOG_SCHEMA=plog
EXPOSE 8000
# --proxy-headers + forwarded-allow-ips: respeta X-Forwarded-Proto del proxy Railway
# para que los redirects (barra final) usen https:// y no filtren la X-API-Key en claro.
CMD ["sh","-c","uvicorn etl_plog.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*"]
