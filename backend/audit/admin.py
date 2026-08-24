from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "tenant", "actor_user", "actor_ip", "created_at")
    list_filter = ("action",)
    search_fields = ("action", "target_type", "target_id", "actor_ip")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
