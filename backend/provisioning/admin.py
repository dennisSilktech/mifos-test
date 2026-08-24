from django.contrib import admin

from .models import ProvisionJob


@admin.register(ProvisionJob)
class ProvisionJobAdmin(admin.ModelAdmin):
    list_display = ("tenant", "current_step", "is_success", "retry_count", "started_at", "finished_at")
    list_filter = ("current_step", "is_success")
    search_fields = ("tenant__tenant_code",)
    readonly_fields = [f.name for f in ProvisionJob._meta.fields]
