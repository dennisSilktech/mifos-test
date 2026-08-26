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
            # Initial state setup
            obj.status = getattr(Tenant.Status, "PENDING", "PENDING")
            obj.is_active = False

            with transaction.atomic():
                super().save_model(request, obj, form, change)

                job = ProvisionJob.objects.create(
                    tenant=obj,
                    current_step=ProvisionJob.Step.VALIDATE,
                )
                job_id = str(job.id)

            # Queue task after Postgres transaction finishes
            transaction.on_commit(
                lambda: provision_tenant_database_task.delay(job_id=job_id)
            )

            messages.info(
                request,
                f"Tenant '{obj.tenant_code}' queued for provisioning (Job ID: {job_id}).",
            )
        else:
            super().save_model(request, obj, form, change)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("hostname", "tenant", "is_primary", "is_custom", "created_at")
    list_filter = ("is_primary", "is_custom", "created_at")
    search_fields = ("hostname", "tenant__tenant_code", "tenant__db_name")
    raw_id_fields = ("tenant",)