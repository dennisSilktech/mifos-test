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


def get_superuser_connection():
    """
    Short-lived connection to the Ubuntu-hosted PostgreSQL instance using the
    platform superuser role. Only ever used by the provisioning engine —
    never by application request handlers.
    """
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

        conn = get_superuser_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SELECT 1 FROM pg_roles WHERE rolname = %s"), [role_name]
                )
                if not cur.fetchone():
                    cur.execute(
                        sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE")
                        .format(sql.Identifier(role_name)),
                        [password],
                    )
                cur.execute(
                    sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"), [self.tenant.db_name]
                )
                if not cur.fetchone():
                    cur.execute(
                        sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'")
                        .format(sql.Identifier(self.tenant.db_name), sql.Identifier(role_name))
                    )
        finally:
            conn.close()

        self.tenant.db_user = role_name
        self.tenant.db_host = settings.PG_SUPERUSER_HOST
        self.tenant.save(update_fields=["db_user", "db_host"])

        credential, _ = EncryptedCredential.objects.get_or_create(tenant=self.tenant)
        credential.set_password(password)
        credential.save()

    def grant_permissions(self):
        role_name = self.tenant.db_user
        conn = get_superuser_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}")
                    .format(sql.Identifier(self.tenant.db_name), sql.Identifier(role_name))
                )
        finally:
            conn.close()

    def drop_all(self):
        """Compensating action used by RollbackManager."""
        role_name = f"{self.tenant.db_name}_role"
        conn = get_superuser_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(self.tenant.db_name))
                )
                cur.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role_name)))
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
        # Fineract auto-provisions its own tenant DB schema the first time
        # /tenants is called with a not-yet-known tenantIdentifier, so this
        # step is effectively a no-op placeholder kept for observability
        # parity with the documented state machine (Section 5).
        pass

    def register_in_fineract(self):
        """
        Best-effort: Fineract runs in a separate, independently-managed
        container. If it's briefly unreachable, that shouldn't block the
        core "create tenant DB + subdomain + admin login" flow — we record
        the failure and let it be retried later rather than rolling back
        the whole provisioning job over it.
        """
        identifier = self.tenant.tenant_code
        try:
            self.admin_client.create_tenant(
                identifier=identifier,
                name=self.tenant.organization.trading_name or self.tenant.organization.legal_name,
                db_host=self.tenant.db_host,
                db_name=self.tenant.db_name,
            )
            self.tenant.fineract_tenant_identifier = identifier
            self.tenant.save(update_fields=["fineract_tenant_identifier"])
        except Exception as exc:  # noqa: BLE001
            self.fineract_registration_error = str(exc)
            # Still record the intended identifier so a later retry knows
            # what to register under.
            self.tenant.fineract_tenant_identifier = identifier
            self.tenant.save(update_fields=["fineract_tenant_identifier"])

    def create_admin_user(self):
        from authentication.models import User

        org = self.tenant.organization
        temp_password = secrets.token_urlsafe(12)
        User.objects.create_user(
            email=org.contact_email,
            password=temp_password,
            tenant=self.tenant,
            role=User.Role.CEO,
            first_name=org.trading_name or org.legal_name,
        )
        self.last_created_password = temp_password

        if not self.fineract_registration_error:
            try:
                self.admin_client.create_tenant_user(
                    tenant_identifier=self.tenant.fineract_tenant_identifier,
                    username=org.contact_email,
                    password=temp_password,
                )
            except Exception as exc:  # noqa: BLE001
                self.fineract_registration_error = str(exc)

    def undo_fineract_registration(self):
        if self.tenant.fineract_tenant_identifier:
            self.admin_client.delete_tenant(self.tenant.fineract_tenant_identifier)


class RollbackManager:
    """Walks backward through completed steps, undoing each one, on failure."""

    def __init__(self, tenant: Tenant, job: ProvisionJob):
        self.tenant = tenant
        self.job = job
        self.db_creator = DatabaseCreator(tenant)
        self.registrar = TenantRegistrar(tenant)

    def execute_from(self, failed_step: str):
        order = list(ProvisionJob.Step)
        idx = order.index(ProvisionJob.Step(failed_step))

        for step in reversed(order[: idx + 1]):
            handler = getattr(self, f"_undo_{step.value.lower()}", None)
            if handler:
                handler()

        AuditService.log(
            actor=None, tenant=self.tenant, action="PROVISIONING_ROLLED_BACK",
            target_type="Tenant", target_id=str(self.tenant.id),
            metadata={"failed_step": failed_step},
        )

    def _undo_create_admin_user(self):
        from authentication.models import User

        User.objects.filter(tenant=self.tenant).delete()

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
        self.tenant.status = Tenant.Status.PROVISIONING
        self.tenant.save(update_fields=["status"])

        if not self.tenant.db_name:
            self.tenant.db_name = f"tenant_{self.tenant.tenant_code}"
            self.tenant.save(update_fields=["db_name"])

        try:
            self._step(ProvisionJob.Step.CREATE_DB, self.db_creator.create_database)
            self._step(ProvisionJob.Step.CREATE_DB_USER, lambda: None)  # created atomically above
            self._step(ProvisionJob.Step.GRANT_PERMISSIONS, self.db_creator.grant_permissions)

            self.tenant.status = Tenant.Status.INITIALIZING
            self.tenant.save(update_fields=["status"])

            self._step(ProvisionJob.Step.RUN_FINERACT_SCHEMA, self.registrar.bootstrap_fineract_schema)
            self._step(ProvisionJob.Step.REGISTER_FINERACT_TENANT, self.registrar.register_in_fineract)
            self._step(ProvisionJob.Step.CREATE_ADMIN_USER, self.registrar.create_admin_user)
            self._step(ProvisionJob.Step.SEND_WELCOME_EMAIL, self._send_welcome_email)

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

        except Exception as exc:  # noqa: BLE001
            self.job.is_success = False
            self.job.error_message = str(exc)
            self.job.finished_at = timezone.now()
            self.job.save()

            self.tenant.status = Tenant.Status.FAILED
            self.tenant.save(update_fields=["status"])

            self.rollback.execute_from(self.job.current_step)
            raise

    def _step(self, step, fn):
        self.job.current_step = step
        self.job.save(update_fields=["current_step"])
        fn()

    def _send_welcome_email(self):
        from notifications.tasks import send_welcome_email

        send_welcome_email.delay(str(self.tenant.organization_id))
