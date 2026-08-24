# syntax=docker/dockerfile:1

# ---------- base ----------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        postgresql-client \
        curl \
        netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

WORKDIR $APP_HOME

# ---------- deps ----------
FROM base AS deps
COPY backend/requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/production.txt

# ---------- runtime ----------
FROM deps AS runtime

RUN useradd -m -u 1000 appuser

COPY backend/ .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && \
    mkdir -p $APP_HOME/staticfiles $APP_HOME/logs && \
    chown -R appuser:appuser $APP_HOME

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]