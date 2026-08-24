#!/bin/sh
set -e

echo "Waiting for PostgreSQL at ${REGISTRY_DB_HOST}:${REGISTRY_DB_PORT}..."
until nc -z "${REGISTRY_DB_HOST}" "${REGISTRY_DB_PORT}"; do
  sleep 1
done
echo "PostgreSQL is up."

echo "Waiting for Redis..."
REDIS_HOST=$(echo "${REDIS_URL}" | sed -E 's#redis://([^:/]+).*#\1#')
REDIS_PORT=$(echo "${REDIS_URL}" | sed -E 's#redis://[^:]+:([0-9]+).*#\1#')
until nc -z "${REDIS_HOST:-localhost}" "${REDIS_PORT:-6379}"; do
  sleep 1
done
echo "Redis is up."

# Only the web process runs migrations/collectstatic; celery containers set
# RUN_MIGRATIONS=false so they don't race the web container on startup.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running migrations..."
  python manage.py migrate --noinput

  echo "Collecting static files..."
  python manage.py collectstatic --noinput
fi

exec "$@"
