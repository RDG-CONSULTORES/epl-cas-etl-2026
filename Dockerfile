FROM python:3.11-slim

WORKDIR /app

# Install Node.js for frontend build (minification)
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Build frontend (minify JS/CSS)
RUN python3 build.py

# Remove unnecessary files from image
RUN rm -rf .git .github .env* backups/ fotos_proteccion_civil/ \
    __pycache__ *.md node_modules/

# Create non-root user
RUN useradd --create-home appuser
USER appuser

# Expose port
EXPOSE 5000

# Run with hardened gunicorn config
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "2", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "warning", \
     "app:app"]
