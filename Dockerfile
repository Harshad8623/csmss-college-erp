# Dockerfile for CSMSS ERP — Fly.io deployment
FROM python:3.10-slim

# System deps needed by psycopg2, Pillow, cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Fly.io sets PORT env var automatically
ENV PORT=8080
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Run DB migrations then start Gunicorn
CMD python fix_db_migration.py ; flask db upgrade ; gunicorn -c gunicorn.conf.py "run:app"
