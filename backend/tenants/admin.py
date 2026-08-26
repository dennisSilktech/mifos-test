import logging
from django.contrib import admin, messages
from django.db import transaction

from .models import Tenant, Domain
from provisioning.models import ProvisionJob
from provisioning.tasks import provision_tenant_database_task

logger = logging.getLogger(__name__)


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1
    fields = ("hostname", "is_primary", "is_custom")


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        "tenant_code",
        "organization",
        "db_name",
        "fineract_tenant_identifier",
        "status",
        "is_active",
        "created_at",
    )
    list_filter = ("status", "is_active", "created_at")
    search_fields = (
        "tenant_code",
        "db_name",
        "fineract_tenant_identifier",
        "organization__legal_name",
        "organization__trading_name",
    )
    readonly_fields = ("provisioned_at", "suspended_at", "created_at", "updated_at")
    inlines = [DomainInline]

    def save_model(self, request, obj, form, change):
        if not change:
            # Set defaults for initial tenant creation
            obj.status = getattr(Tenant.Status, "PENDING", "PENDING")
            obj.is_active = False

            if not obj.db_name and obj.tenant_code:
                obj.db_name = f"fineract_{obj.tenant_code}"
            if not obj.fineract_tenant_identifier and obj.tenant_code:
                obj.fineract_tenant_identifier = obj.tenant_code

        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        # Trigger domain creation and background provisioning ONLY for new tenants
        if not change:
            tenant = form.instance

            with transaction.atomic():
                # Fallback: Auto-create primary domain if no inline domain was added
                if not tenant.domains.exists():
                    default_hostname = f"{tenant.tenant_code}.lvh.me"
                    Domain.objects.create(
                        tenant=tenant,
                        hostname=default_hostname,
                        is_primary=True,
                        is_custom=False,
                    )
                    logger.info(
                        "Auto-created default domain '%s' for tenant '%s'.",
                        default_hostname,
                        tenant.tenant_code,
                    )

                # Create ProvisionJob after tenant and domain records exist
                job = ProvisionJob.objects.create(
                    tenant=tenant,
                    current_step=ProvisionJob.Step.VALIDATE,
                )
                job_id = str(job.id)

            # Queue task once the entire atomic transaction completes
            transaction.on_commit(
                lambda: provision_tenant_database_task.delay(job_id=job_id)
            )

            messages.info(
                request,
                f"Tenant '{tenant.tenant_code}' queued for provisioning (Job ID: {job_id}).",
            )


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("hostname", "tenant", "is_primary", "is_custom", "created_at")
    list_filter = ("is_primary", "is_custom", "created_at")
    search_fields = ("hostname", "tenant__tenant_code", "tenant__db_name")
    raw_id_fields = ("tenant",)