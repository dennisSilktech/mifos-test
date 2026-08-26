import os
import logging
import subprocess
from datetime import date
from typing import Optional

from celery import shared_task
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from .models import Tenant
from provisioning.models import ProvisionJob

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def provision_tenant_database_task(self, job_id: str) -> None:
    """
    Asynchronously provisions a PostgreSQL database for a given ProvisionJob.
    Updates the Tenant and ProvisionJob statuses upon success or failure.
    """
    try:
        job = ProvisionJob.objects.select_related("tenant").get(id=job_id)
    except ProvisionJob.DoesNotExist:
        logger.error("ProvisionJob with ID %s does not exist.", job_id)
        return

    tenant = job.tenant

    # Update ProvisionJob state to IN_PROGRESS
    job.status = getattr(ProvisionJob.Status, "IN_PROGRESS", "IN_PROGRESS")
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    try:
        # 1. Create target PostgreSQL database (Quote identifier to prevent SQL injection)
        logger.info("Creating database '%s' for tenant %s...", tenant.db_name, tenant.tenant_code)
        with connection.cursor() as cursor:
            # Postgres doesn't support parameterized DB names in CREATE DATABASE
            cursor.execute(f'CREATE DATABASE "{tenant.db_name}";')

        # 2. Mark tenant active and ready
        now = timezone.now()
        ready_status = getattr(Tenant.Status, "READY", "ACTIVE")
        tenant.status = ready_status
        tenant.is_active = True
        tenant.provisioned_at = now
        tenant.save(update_fields=["status", "is_active", "provisioned_at"])

        # 3. Complete job record
        completed_status = getattr(ProvisionJob.Status, "COMPLETED", "COMPLETED")
        job.status = completed_status
        job.completed_at = now
        job.save(update_fields=["status", "completed_at"])

        logger.info("Successfully provisioned database '%s' for job %s.", tenant.db_name, job_id)

    except Exception as exc:
        logger.exception("Failed to provision database '%s' for job %s", tenant.db_name, job_id)

        # Revert tenant status on error
        failed_tenant_status = getattr(Tenant.Status, "FAILED", "FAILED")
        tenant.status = failed_tenant_status
        tenant.is_active = False
        tenant.save(update_fields=["status", "is_active"])

        # Update ProvisionJob status on error
        failed_job_status = getattr(ProvisionJob.Status, "FAILED", "FAILED")
        job.status = failed_job_status
        job.error_message = str(exc)
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])

        raise exc


@shared_task
def backup_tenant_database(tenant_id: str) -> None:
    """
    Executes a binary PostgreSQL dump (`pg_dump`) for an individual active tenant.
    """
    try:
        ready_status = getattr(Tenant.Status, "READY", "ACTIVE")
        tenant = Tenant.objects.get(id=tenant_id, status=ready_status)
    except Tenant.DoesNotExist:
        logger.warning("Tenant %s not found or not in READY status. Skipping backup.", tenant_id)
        return

    out_dir = f"/backups/{tenant.tenant_code}"
    out_file = os.path.join(out_dir, f"{date.today().isoformat()}_{tenant.tenant_code}.dump")

    os.makedirs(out_dir, exist_ok=True)

    # Inherit current OS env and inject PGPASSWORD securely
    env = os.environ.copy()
    env["PGPASSWORD"] = getattr(settings, "PG_SUPERUSER_PASSWORD", "")

    db_user = getattr(settings, "PG_SUPERUSER_NAME", "postgres")

    cmd = [
        "pg_dump",
        "-Fc",
        "-h", str(tenant.db_host),
        "-p", str(tenant.db_port),
        "-U", str(db_user),
        "-f", out_file,
        str(tenant.db_name),
    ]

    try:
        logger.info("Starting backup for tenant %s to %s", tenant.tenant_code, out_file)
        subprocess.run(cmd, check=True, env=env, capture_output=True, text=True)
        logger.info("Backup successfully created for tenant %s", tenant.tenant_code)
    except subprocess.CalledProcessError as exc:
        logger.error("pg_dump failed for tenant %s: %s", tenant.tenant_code, exc.stderr)
        raise exc


@shared_task
def backup_all_tenant_databases() -> None:
    """
    Fan-out task to dispatch backup jobs for all active tenants.
    """
    ready_status = getattr(Tenant.Status, "READY", "ACTIVE")
    tenant_ids = Tenant.objects.filter(status=ready_status).values_list("id", flat=True)

    logger.info("Queuing database backups for %d tenants.", len(tenant_ids))
    for tenant_id in tenant_ids:
        backup_tenant_database.delay(str(tenant_id))