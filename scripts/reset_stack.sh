#!/bin/bash
# Full clean wipe + restart of the Dockerized stack (web/worker/beat/fineract)
# plus the host-side Postgres databases they depend on.
set -euo pipefail

echo "Stopping containers..."
docker compose down

echo "Dropping host Postgres databases..."
sudo -u postgres psql -c "DROP DATABASE IF EXISTS tenant_registry;"
sudo -u postgres psql -c "DROP USER IF EXISTS registry_app_role;"
sudo -u postgres psql -c "DROP DATABASE IF EXISTS fineract_tenants;"
sudo -u postgres psql -c "DROP DATABASE IF EXISTS fineract_default;"

echo "Recreating databases..."
REGISTRY_DB_PASSWORD="${REGISTRY_DB_PASSWORD:?Set REGISTRY_DB_PASSWORD}" ./scripts/setup_postgres.sh
sudo -u postgres psql -c "CREATE USER fineract WITH PASSWORD '${FINERACT_DB_PASSWORD:?Set FINERACT_DB_PASSWORD}';"
sudo -u postgres psql -c "ALTER USER fineract WITH SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE fineract_tenants OWNER fineract;"
sudo -u postgres psql -c "CREATE DATABASE fineract_default OWNER fineract;"

echo "Rebuilding and starting containers..."
docker compose up -d --build

echo "Done."
