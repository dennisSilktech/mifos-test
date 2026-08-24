#!/bin/bash
# Run this once on the Ubuntu host after cloning, before `docker compose up`.
# Mirrors the Fineract setup workflow: creates the roles/databases that
# live on the host Postgres instance and that the Django containers reach
# via host.docker.internal.
#
# Usage: REGISTRY_DB_PASSWORD=... ./scripts/setup_postgres.sh
set -euo pipefail

REGISTRY_DB_PASSWORD="${REGISTRY_DB_PASSWORD:?Set REGISTRY_DB_PASSWORD}"

echo "Creating control-plane role and database..."
sudo -u postgres psql -c "CREATE USER registry_app_role WITH PASSWORD '${REGISTRY_DB_PASSWORD}';"
sudo -u postgres psql -c "CREATE DATABASE tenant_registry OWNER registry_app_role;"

echo "Done. The per-tenant databases (tenant_imara, tenant_unity, ...) are"
echo "created automatically by the ProvisioningService when an organization"
echo "is onboarded — no manual step needed for those."
echo
echo "Note: the platform superuser role used by the provisioning engine"
echo "(PG_SUPERUSER_NAME / PG_SUPERUSER_PASSWORD in .env) should be the"
echo "existing 'postgres' superuser, or a dedicated role granted CREATEDB"
echo "and CREATEROLE."
