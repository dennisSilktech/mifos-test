import logging
import secrets

import psycopg2
from django.conf import settings
from django.utils import timezone
from psycopg2 import sql

from audit.services import AuditService
from fineract_gateway.admin_client import FineractAdminClient
from tenants.models import EncryptedCredential, Tenant
from tenants.services import DomainManager

from .models import ProvisionJob

logger = logging.getLogger(__name__)


def get_superuser_connection():
    """
    Short-lived connection to the Ubuntu-hosted PostgreSQL instance using the
    platform superuser role. Only ever used by the provisioning engine —
    never by application request handlers.
    """
    logger.debug(
        "[DB_SUPERUSER_CONNECT] Connecting to Postgres instance host='%s' port='%s' db='postgres' as user='%s'",
        settings.PG_SUPERUSER_HOST,
        settings.PG_SUPERUSER_PORT,
        settings.PG_SUPERUSER_NAME,
    )
    conn = psycopg2.connect(
        host=settings.PG_SUPERUSER_HOST,
        port=settings.PG_SUPERUSER_PORT,
        dbname="postgres",
        user=settings.PG_SUPERUSER_NAME,
        password=settings.PG_SUPERUSER_PASSWORD,
    )
    conn.autocommit = True
    return conn


class DatabaseCreator:
    """Creates the per-tenant PostgreSQL role + database on the Ubuntu host."""

    def __init__(self, tenant: Tenant):
        self.tenant = tenant

    def create_database(self):
        role_name = f"{self.tenant.db_name}_role"
        password = secrets.token_urlsafe(32)

        logger.info(
            "--> [DB_CREATE_START] Initiating Database & Role setup | Tenant Code: '%s' | Target DB: '%s' | Role: '%s'",
            self.tenant.tenant_code,
            self.tenant.db_name,
            role_name,
        )

        conn = get_superuser_connection()
        try:
            with conn.cursor() as cur:
                # 1. Role Check & Creation
                cur.execute(
                    sql.SQL("SELECT 1 FROM pg_roles WHERE rolname = %s"), [role_name]
                )
                if not cur.fetchone():
                    logger.debug("[DB_CREATE_ROLE] Creating Postgres Role: '%s'", role_name)
                    cur.execute(
                        sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE")
                        .format(sql.Identifier(role_name)),
                        [password],
                    )
                    logger.info("--> [DB_CREATE_ROLE_SUCCESS] Created role: '%s'", role_name)
                else:
                    logger.debug("[DB_CREATE_ROLE_SKIP] Role '%s' already exists.", role_name)

                # 2. Database Check & Creation
                cur.execute(
                    sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"), [self.tenant.db_name]
                )
                if not cur.fetchone():
                    logger.debug("[DB_CREATE_DATABASE] Creating Postgres Database: '%s' with owner '%s'", self.tenant.db_name, role_name)
                    cur.execute(
                        sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'")
                        .format(sql.Identifier(self.tenant.db_name), sql.Identifier(role_name))
                    )
                    logger.info("--> [DB_CREATE_DATABASE_SUCCESS] Database '%s' successfully created.", self.tenant.db_name)
                else:
                    logger.debug("[DB_CREATE_DATABASE_SKIP] Database '%s' already exists.", self.tenant.db_name)
        except Exception as e:
            logger.exception("--> [DB_CREATE_FAILED] Error creating database/role for Tenant '%s': %s", self.tenant.tenant_code, str(e))
            raise
        finally:
            conn.close()

        self.tenant.db_user = role_name
        self.tenant.db_host = settings.PG_SUPERUSER_HOST
        self.tenant.save(update_fields=["db_user", "db_host"])
        logger.debug("[DB_CREATE_RECORD_UPDATED] Tenant model saved with db_user='%s' and db_host='%s'", role_name, settings.PG_SUPERUSER_HOST)

        credential, _ = EncryptedCredential.objects.get_or_create(tenant=self.tenant)
        credential.set_password(password)
        credential.save()
        logger.debug("[DB_CREATE_CREDENTIAL_STORED] Encrypted credentials generated and stored.")

    def grant_permissions(self):
        role_name = self.tenant.db_user
        logger.info(
            "--> [DB_GRANT_START] Granting privileges on Database '%s' to Role '%s'",
            self.tenant.db_name,
            role_name,
        )
        conn = get_superuser_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}")
                    .format(sql.Identifier(self.tenant.db_name), sql.Identifier(role_name))
                )
            logger.info("--> [DB_GRANT_SUCCESS] Privileges granted successfully.")
        except Exception as e:
            logger.exception("--> [DB_GRANT_FAILED] Failed to grant permissions on '%s' to '%s': %s", self.tenant.db_name, role_name, str(e))
            raise
        finally:
            conn.close()

    def drop_all(self):
        """Compensating action used by RollbackManager."""
        role_name = f"{self.tenant.db_name}_role"
        logger.warning(
            "--> [DB_ROLLBACK_DROP] Compensating action: Dropping Database '%s' and Role '%s'",
            self.tenant.db_name,
            role_name,
        )
        conn = get_superuser_connection()
        try:
            with conn.cursor() as cur:
                logger.debug("[DB_ROLLBACK_DROP] Terminating active connections to '%s' if present...", self.tenant.db_name)
                cur.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(self.tenant.db_name))
                )
                logger.info("--> [DB_ROLLBACK_DROP_DB_SUCCESS] Database '%s' dropped.", self.tenant.db_name)

                cur.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role_name)))
                logger.info("--> [DB_ROLLBACK_DROP_ROLE_SUCCESS] Role '%s' dropped.", role_name)
        except Exception as e:
            logger.exception("--> [DB_ROLLBACK_DROP_FAILED] Failed during DB/Role cleanup: %s", str(e))
        finally:
            conn.close()


class TenantRegistrar:
    """Registers the tenant inside Apache Fineract and creates its admin user."""

    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.admin_client = FineractAdminClient()
        self.last_created_password = None
        self.fineract_registration_error = None

    def bootstrap_fineract_schema(self):
        logger.info("--> [FINERACT_SCHEMA] Schema auto-provisioning step triggered (placeholder for tenant '%s').", self.tenant.tenant_code)

    def register_in_fineract(self):
        identifier = self.tenant.tenant_code
        trading_or_legal_name = self.tenant.organization.trading_name or self.tenant.organization.legal_name
        
        logger.info(
            "--> [FINERACT_REGISTER_START] Registering tenant in Fineract | Identifier: '%s' | Name: '%s'",
            identifier,
            trading_or_legal_name,
        )
        try:
            self.admin_client.create_tenant(
                identifier=identifier,
                name=trading_or_legal_name,
                db_host=self.tenant.db_host,
                db_name=self.tenant.db_name,
            )
            self.tenant.fineract_tenant_identifier = identifier
            self.tenant.save(update_fields=["fineract_tenant_identifier"])
            logger.info("--> [FINERACT_REGISTER_SUCCESS] Tenant '%s' successfully registered in Fineract.", identifier)
        except Exception as exc:  # noqa: BLE001
            self.fineract_registration_error = str(exc)
            logger.warning(
                "--> [FINERACT_REGISTER_WARNING] Non-blocking registration failure for Tenant '%s': %s",
                identifier,
                str(exc),
            )
            # Record intended identifier so later retry works
            self.tenant.fineract_tenant_identifier = identifier
            self.tenant.save(update_fields=["fineract_tenant_identifier"])

    def create_admin_user(self):
        from authentication.models import User

        org = self.tenant.organization
        temp_password = secrets.token_urlsafe(12)
        
        logger.info(
            "--> [ADMIN_USER_CREATE] Creating local CEO/Admin user | Email: '%s' | Tenant Code: '%s'",
            org.contact_email,
            self.tenant.tenant_code,
        )

        user = User.objects.create_user(
            email=org.contact_email,
            password=temp_password,
            tenant=self.tenant,
            role=User.Role.CEO,
            first_name=org.trading_name or org.legal_name,
        )
        self.last_created_password = temp_password
        logger.info("--> [ADMIN_USER_CREATE_SUCCESS] User created locally with ID: %s", user.id)

        if not self.fineract_registration_error:
            logger.info("--> [FINERACT_USER_CREATE] Registering admin user in Fineract for Identifier '%s'", self.tenant.fineract_tenant_identifier)
            try:
                self.admin_client.create_tenant_user(
                    tenant_identifier=self.tenant.fineract_tenant_identifier,
                    username=org.contact_email,
                    password=temp_password,
                )
                logger.info("--> [FINERACT_USER_CREATE_SUCCESS] User '%s' registered in Fineract.", org.contact_email)
            except Exception as exc:  # noqa: BLE001
                self.fineract_registration_error = str(exc)
                logger.warning(
                    "--> [FINERACT_USER_CREATE_WARNING] Non-blocking failure registering user in Fineract: %s",
                    str(exc),
                )

    def undo_fineract_registration(self):
        if self.tenant.fineract_tenant_identifier:
            logger.warning("--> [FINERACT_UNDO] Rollback: Deleting tenant '%s' from Fineract", self.tenant.fineract_tenant_identifier)
            try:
                self.admin_client.delete_tenant(self.tenant.fineract_tenant_identifier)
                logger.info("--> [FINERACT_UNDO_SUCCESS] Fineract tenant deleted.")
            except Exception as e:
                logger.exception("--> [FINERACT_UNDO_FAILED] Error removing tenant from Fineract: %s", str(e))


class RollbackManager:
    """Walks backward through completed steps, undoing each one, on failure."""

    def __init__(self, tenant: Tenant, job: ProvisionJob):
        self.tenant = tenant
        self.job = job
        self.db_creator = DatabaseCreator(tenant)
        self.registrar = TenantRegistrar(tenant)

    def execute_from(self, failed_step: str):
        logger.error(
            "==> [ROLLBACK_INITIATED] Provisioning job failed at step '%s'. Starting cascade cleanup for Tenant '%s'...",
            failed_step,
            self.tenant.tenant_code,
        )
        order = list(ProvisionJob.Step)
        idx = order.index(ProvisionJob.Step(failed_step))

        for step in reversed(order[: idx + 1]):
            handler = getattr(self, f"_undo_{step.value.lower()}", None)
            if handler:
                logger.info("--> [ROLLBACK_STEP] Executing cleanup handler for step: '%s'", step.value)
                handler()

        AuditService.log(
            actor=None, tenant=self.tenant, action="PROVISIONING_ROLLED_BACK",
            target_type="Tenant", target_id=str(self.tenant.id),
            metadata={"failed_step": failed_step},
        )
        logger.info("==> [ROLLBACK_COMPLETED] Rollback sequence finished for Tenant ID: %s", self.tenant.id)

    def _undo_create_admin_user(self):
        from authentication.models import User

        logger.warning("--> [ROLLBACK_UNDO_ADMIN] Deleting provisioned users for Tenant '%s'", self.tenant.tenant_code)
        deleted_count, _ = User.objects.filter(tenant=self.tenant).delete()
        logger.info("--> [ROLLBACK_UNDO_ADMIN_SUCCESS] Deleted %d user(s).", deleted_count)

    def _undo_register_fineract_tenant(self):
        self.registrar.undo_fineract_registration()

    def _undo_create_db_user(self):
        self.db_creator.drop_all()

    def _undo_create_db(self):
        self.db_creator.drop_all()


class ProvisioningService:
    """Orchestrates Section 5's onboarding workflow with checkpointed steps."""

    def __init__(self, job: ProvisionJob):
        self.job = job
        self.tenant = job.tenant
        self.db_creator = DatabaseCreator(self.tenant)
        self.registrar = TenantRegistrar(self.tenant)
        self.rollback = RollbackManager(self.tenant, job)

    def run(self):
        logger.info(
            "================================================================================\n"
            "--> [PROVISION_START] Starting Provisioning Pipeline | Job ID: %s | Tenant: '%s' (ID: %s)",
            self.job.id,
            self.tenant.tenant_code,
            self.tenant.id,
        )

        self.tenant.status = Tenant.Status.PROVISIONING
        self.tenant.save(update_fields=["status"])

        if not self.tenant.db_name:
            self.tenant.db_name = f"tenant_{self.tenant.tenant_code}"
            self.tenant.save(update_fields=["db_name"])
            logger.debug("[PROVISION_INIT] Set default db_name: '%s'", self.tenant.db_name)

        try:
            self._step(ProvisionJob.Step.CREATE_DB, self.db_creator.create_database)
            self._step(ProvisionJob.Step.CREATE_DB_USER, lambda: None)  # created atomically above
            self._step(ProvisionJob.Step.GRANT_PERMISSIONS, self.db_creator.grant_permissions)

            logger.info("--> [PROVISION_STATUS_UPDATE] Tenant status advancing to INITIALIZING.")
            self.tenant.status = Tenant.Status.INITIALIZING
            self.tenant.save(update_fields=["status"])

            self._step(ProvisionJob.Step.RUN_FINERACT_SCHEMA, self.registrar.bootstrap_fineract_schema)
            self._step(ProvisionJob.Step.REGISTER_FINERACT_TENANT, self.registrar.register_in_fineract)
            self._step(ProvisionJob.Step.CREATE_ADMIN_USER, self.registrar.create_admin_user)
            self._step(ProvisionJob.Step.SEND_WELCOME_EMAIL, self._send_welcome_email)

            # Subdomain & Primary Domain creation
            logger.info("--> [PROVISION_SUBDOMAIN] Creating primary subdomain/domain for tenant...")
            self._step(ProvisionJob.Step.ACTIVATE, lambda: DomainManager.create_primary_domain(self.tenant))

            self.tenant.status = Tenant.Status.READY
            self.tenant.is_active = True
            self.tenant.provisioned_at = timezone.now()
            self.tenant.save(update_fields=["status", "is_active", "provisioned_at"])

            self.job.current_step = ProvisionJob.Step.DONE
            self.job.is_success = True
            if self.registrar.fineract_registration_error:
                self.job.error_message = (
                    f"Tenant is READY, but Fineract registration failed and can be retried later: "
                    f"{self.registrar.fineract_registration_error}"
                )
            self.job.finished_at = timezone.now()
            self.job.save()

            logger.info(
                "==> [PROVISION_SUCCESS] Tenant '%s' provisioned successfully in %s status!\n"
                "================================================================================",
                self.tenant.tenant_code,
                self.tenant.status,
            )

        except Exception as exc:  # noqa: BLE001
            logger.exception("==> [PROVISION_CRITICAL_FAILURE] Provisioning pipeline halted on Step '%s': %s", self.job.current_step, str(exc))
            
            self.job.is_success = False
            self.job.error_message = str(exc)
            self.job.finished_at = timezone.now()
            self.job.save()

            self.tenant.status = Tenant.Status.FAILED
            self.tenant.save(update_fields=["status"])

            self.rollback.execute_from(self.job.current_step)
            raise

    def _step(self, step, fn):
        logger.info("--> [PIPELINE_STEP_START] Executing Step: '%s'", step.value)
        self.job.current_step = step
        self.job.save(update_fields=["current_step"])
        fn()
        logger.info("--> [PIPELINE_STEP_COMPLETE] Finished Step: '%s'", step.value)

    def _send_welcome_email(self):
        from notifications.tasks import send_welcome_email

        logger.info("--> [NOTIFY_WELCOME_EMAIL] Enqueuing welcome email for Org ID: %s", self.tenant.organization_id)
        try:
            send_welcome_email.delay(str(self.tenant.organization_id))
            logger.debug("[NOTIFY_WELCOME_EMAIL_QUEUED] Celery task dispatched.")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to enqueue welcome email for tenant %s (broker unreachable?): %s",
                self.tenant.tenant_code,
                exc,
            )