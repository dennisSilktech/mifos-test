import logging
from celery import shared_task
from django.db import connection, connections
from django.utils import timezone
from django.conf import settings

from tenants.models import Tenant
from .models import ProvisionJob

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def provision_tenant_database_task(self, job_id):
    try:
        job = ProvisionJob.objects.select_related("tenant").get(id=job_id)
    except ProvisionJob.DoesNotExist:
        logger.error("ProvisionJob ID %s not found.", job_id)
        return

    tenant = job.tenant
    job.celery_task_id = self.request.id or ""
    job.save(update_fields=["celery_task_id"])

    try:
        # Step 1: Validate Tenant Config
        job.current_step = ProvisionJob.Step.VALIDATE
        job.save(update_fields=["current_step"])
        if not tenant.db_name:
            raise ValueError(f"Tenant '{tenant.tenant_code}' has no db_name defined.")

        # Step 2: Create PostgreSQL Database
        job.current_step = ProvisionJob.Step.CREATE_DB
        job.save(update_fields=["current_step"])
        _create_postgresql_database(tenant.db_name)

        # Step 3: Run Fineract Schema / Migrations
        job.current_step = ProvisionJob.Step.RUN_FINERACT_SCHEMA
        job.save(update_fields=["current_step"])
        # TODO: Trigger Fineract tenant schema initialization / Liquibase scripts here

        # Step 4: Register Fineract Tenant
        job.current_step = ProvisionJob.Step.REGISTER_FINERACT_TENANT
        job.save(update_fields=["current_step"])
        # TODO: Register tenant in Fineract tenant server registry

        # Step 5: Activate Tenant
        job.current_step = ProvisionJob.Step.ACTIVATE
        job.save(update_fields=["current_step"])
        
        tenant.status = getattr(Tenant.Status, "ACTIVE", "ACTIVE")
        tenant.is_active = True
        tenant.provisioned_at = timezone.now()
        tenant.save(update_fields=["status", "is_active", "provisioned_at"])

        # Mark Job complete
        job.current_step = ProvisionJob.Step.DONE
        job.is_success = True
        job.finished_at = timezone.now()
        job.save(update_fields=["current_step", "is_success", "finished_at"])

    except Exception as exc:
        logger.exception("Provisioning failed for job %s", job_id)
        job.is_success = False
        job.error_message = str(exc)
        job.retry_count = self.request.retries
        job.save(update_fields=["is_success", "error_message", "retry_count"])

        tenant.status = getattr(Tenant.Status, "FAILED", "FAILED")
        tenant.is_active = False
        tenant.save(update_fields=["status", "is_active"])

        raise self.retry(exc=exc, countdown=15)


def _create_postgresql_database(db_name: str):
    """Executes CREATE DATABASE using isolated autocommit mode required by PostgreSQL."""
    with connections["default"].cursor() as cursor:
        raw_conn = cursor.connection
        old_autocommit = getattr(raw_conn, "autocommit", False)
        
        try:
            raw_conn.autocommit = True
            with raw_conn.cursor() as raw_cursor:
                raw_cursor.execute(f'CREATE DATABASE "{db_name}";')
                logger.info("Successfully created database '%s'.", db_name)
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.warning("Database '%s' already exists. Skipping creation.", db_name)
            else:
                raise e
        finally:
            raw_conn.autocommit = old_autocommit


# Backward compatibility alias
run_provisioning = provision_tenant_database_task