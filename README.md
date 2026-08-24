# Banking SaaS — Multi-Tenant Platform

Django control plane + Apache Fineract core banking engine. Django and
Fineract run in Docker; PostgreSQL and Redis run natively on the Ubuntu
host. See `docs/architecture/` (or the original blueprint doc) for the full
design rationale.

## Standard Setup Workflow (Post-Clone)

### 1. Install host dependencies

PostgreSQL and Redis must already be running natively on the Ubuntu host —
neither is containerized.

```bash
sudo apt install postgresql redis-server
sudo systemctl enable --now postgresql redis-server
```

### 2. Create the control-plane database (Django)

```bash
REGISTRY_DB_PASSWORD='StrongPassword123' ./scripts/setup_postgres.sh
```

This creates the `registry_app_role` role and the `tenant_registry`
database. Per-tenant databases (`tenant_imara`, `tenant_unity`, ...) are
**not** created here — they're provisioned automatically by
`ProvisioningService` when an organization completes onboarding (see
Section 5/13 of the architecture doc).

The platform superuser used by the provisioning engine to run
`CREATE DATABASE` / `CREATE ROLE` on demand is the existing Postgres
`postgres` superuser (or a dedicated role with `CREATEDB`/`CREATEROLE`) —
set via `PG_SUPERUSER_NAME` / `PG_SUPERUSER_PASSWORD` in `.env`.

### 3. Create the Fineract databases

Same as running Fineract standalone — these also live on the host Postgres:

```bash
sudo -u postgres psql -c "CREATE USER fineract WITH PASSWORD 'StrongPassword123';"
sudo -u postgres psql -c "ALTER USER fineract WITH SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE fineract_tenants OWNER fineract;"
sudo -u postgres psql -c "CREATE DATABASE fineract_default OWNER fineract;"
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Fill in at minimum:

- `DJANGO_SECRET_KEY`
- `REGISTRY_DB_PASSWORD` (matches step 2)
- `PG_SUPERUSER_PASSWORD`
- `CREDENTIAL_ENCRYPTION_KEY` — generate with:
  ```bash
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `JWT_SIGNING_KEY` / `JWT_VERIFYING_KEY` — an RSA keypair (RS256), e.g.:
  ```bash
  openssl genrsa -out jwt_private.pem 2048
  openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
  ```
  Paste the PEM contents (with literal `\n` line breaks or use a `.env`
  multi-line value) into `JWT_SIGNING_KEY` / `JWT_VERIFYING_KEY`.
- `FINERACT_ADMIN_PASSWORD` — Fineract's own super-admin (`mifos`) password
- `FINERACT_DB_PASSWORD` — matches step 3's `StrongPassword123`

### 5. Launch the stack

```bash
docker compose up -d --build
```

This starts four containers:

| Container | Role |
|---|---|
| `banking-django-web` | Gunicorn + Django control plane, port 8000 |
| `banking-celery-worker` | Provisioning jobs, emails, backups |
| `banking-celery-beat` | Scheduled sweeps (billing, sessions, backups) |
| `fineract-server` | Apache Fineract, port 8443 |

Django and Fineract both reach the host's PostgreSQL/Redis via
`host.docker.internal` (mapped through `extra_hosts: host-gateway`), the
same pattern used for running Fineract standalone.

The `web` container runs migrations and `collectstatic` automatically on
startup (`docker/entrypoint.sh`); the worker/beat containers skip that step
(`RUN_MIGRATIONS=false`) so they don't race the web container.

### 6. Create a platform superuser (Super Admin)

```bash
docker compose exec web python manage.py createsuperuser
```

### 7. Point Apache (host) at the containers

Once you're ready to expose this beyond localhost, configure the wildcard
reverse proxy on the Ubuntu host (see Section 4/17 of the architecture doc)
to forward `*.banking.silktechagency.com` → `127.0.0.1:8000` (Django) and, if Fineract
needs to be reachable directly, `fineract.banking.silktechagency.com` → `127.0.0.1:8443`.

## Quick Reset

Full wipe and restart of both the Django/Fineract containers and their
host Postgres databases:

```bash
REGISTRY_DB_PASSWORD='StrongPassword123' FINERACT_DB_PASSWORD='StrongPassword123' \
  ./scripts/reset_stack.sh
```

## Local development without Docker

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements/base.txt
export DJANGO_SECRET_KEY=devkey USE_SQLITE=true
python manage.py migrate
python manage.py runserver
```

`USE_SQLITE=true` swaps the control-plane DB to a local SQLite file so you
can iterate without a live Postgres connection — the per-tenant Postgres
provisioning path is unaffected since it always talks to
`PG_SUPERUSER_HOST` directly, not the Django `default` connection.

## Project Layout

```
banking-saas/
├── backend/            # Django control plane (this is what gets Dockerized)
│   ├── Dockerfile
│   ├── requirements/
│   ├── tenant_manager/ # settings, urls, celery app
│   └── <apps>/         # organizations, tenants, provisioning, subscriptions,
│                        # audit, authentication, domains, fineract_gateway,
│                        # billing, notifications
├── docker/
│   └── entrypoint.sh
├── docker-compose.yml
├── .env.example
└── scripts/
    ├── setup_postgres.sh
    └── reset_stack.sh
```
# mifos-test
# mifos-test
