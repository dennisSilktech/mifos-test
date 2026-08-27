import logging
import secrets
import string
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.utils.text import slugify

from .models import Tenant, Domain
from authentication.models import User
from provisioning.models import ProvisionJob
from provisioning.tasks import provision_tenant_database_task

logger = logging.getLogger(__name__)


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1
    fields = ("hostname", "is_primary", "is_custom")


class TenantAdminForm(forms.ModelForm):
    # Additional form fields for tenant admin credentials
    admin_email = forms.EmailField(
        required=False,
        label="Admin Email",
        help_text="Primary CEO email used to log in at the subdomain (e.g., admin@tenant.com). Defaults to admin@<tenant_code>.com if left blank.",
    )
    admin_password = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False,
        label="Admin Password",
        help_text="Password for the subdomain login. Defaults to 'ChangeMe123!' if left blank.",
    )

    class Meta:
        model = Tenant
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        tenant_code = cleaned_data.get("tenant_code")
        organization = cleaned_data.get("organization")

        # Fallback tenant code if left empty
        if not tenant_code and organization:
            tenant_code = slugify(organization.legal_name)[:24] or "org"
            cleaned_data["tenant_code"] = tenant_code

        # Populate required DB fields before model validation
        if tenant_code:
            if not cleaned_data.get("db_name"):
                cleaned_data["db_name"] = f"fineract_{tenant_code}"
                self.errors.pop("db_name", None)

            if not cleaned_data.get("fineract_tenant_identifier"):
                cleaned_data["fineract_tenant_identifier"] = tenant_code
                self.errors.pop("fineract_tenant_identifier", None)

        return cleaned_data


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    form = TenantAdminForm

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

    fieldsets = (
        ("Tenant Basics", {
            "fields": (
                "organization",
                "tenant_code",
                "db_name",
                "fineract_tenant_identifier",
                "is_active",
                "suspension_reason",
            )
        }),
        ("Subdomain Login Credentials", {
            "description": "Specify initial admin account credentials for accessing the tenant portal.",
            "fields": (
                "admin_email",
                "admin_password",
            ),
        }),
        ("Advanced DB Parameters (Optional Override)", {
            "classes": ("collapse",),
            "fields": (
                "db_user",
                "db_host",
                "db_port",
                "status",
                "provisioned_at",
                "suspended_at",
            ),
        }),
    )

    readonly_fields = ("status", "provisioned_at", "suspended_at", "created_at", "updated_at")
    inlines = [DomainInline]

    def save_model(self, request, obj, form, change):
        if not change:
            if not obj.db_host:
                obj.db_host = getattr(settings, "DATABASES", {}).get("default", {}).get("HOST", "localhost")
            if not obj.db_port:
                obj.db_port = getattr(settings, "DATABASES", {}).get("default", {}).get("PORT", 5432)

            obj.status = getattr(Tenant.Status, "PENDING", "PENDING")

        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        # Execute only during initial tenant creation
        if not change:
            tenant = form.instance
            admin_email = form.cleaned_data.get("admin_email") or f"admin@{tenant.tenant_code}.com"
            admin_password = form.cleaned_data.get("admin_password") or "ChangeMe123!"

            with transaction.atomic():
                # 1. Create primary CEO user with hashed password
                user = User.objects.filter(email=admin_email, tenant=tenant).first()
                if not user:
                    user = User.objects.create_user(
                        email=admin_email,
                        password=admin_password,
                        tenant=tenant,
                        role=getattr(User.Role, "CEO", "CEO"),
                        first_name=f"{tenant.tenant_code.capitalize()} Admin",
                        is_active=True,
                    )
                else:
                    user.set_password(admin_password)
                    user.save()

                # 2. Auto-create primary domain if missing
                if not tenant.domains.exists():
                    base_domain = getattr(settings, "PLATFORM_BASE_DOMAIN", "lvh.me")
                    default_hostname = f"{tenant.tenant_code}.{base_domain}"
                    
                    Domain.objects.create(
                        tenant=tenant,
                        hostname=default_hostname,
                        is_primary=True,
                        is_custom=False,
                    )

                # 3. Queue Provisioning Job
                job = ProvisionJob.objects.create(
                    tenant=tenant,
                    current_step=ProvisionJob.Step.VALIDATE,
                )
                job_id = str(job.id)

            transaction.on_commit(
                lambda: provision_tenant_database_task.delay(job_id=job_id)
            )

            messages.success(
                request,
                f"Tenant '{tenant.tenant_code}' created with admin '{user.email}'. Queued for provisioning (Job ID: {job_id}).",
            )

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("hostname", "tenant", "is_primary", "is_custom", "created_at")
    list_filter = ("is_primary", "is_custom", "created_at")
    search_fields = ("hostname", "tenant__tenant_code", "tenant__db_name")
    raw_id_fields = ("tenant",)