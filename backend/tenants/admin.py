from django.contrib import admin

from .models import Tenant, Domain


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("tenant_code", "organization", "status", "db_name", "created_at")
    search_fields = ("tenant_code", "organization__legal_name")


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("hostname", "tenant", "is_primary", "is_custom", "created_at")
    search_fields = ("hostname", "tenant__tenant_code")
