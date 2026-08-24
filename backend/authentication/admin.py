from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import APIKey, LoginSession, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    list_display = ("email", "role", "tenant", "is_active", "mfa_enabled", "created_at")
    list_filter = ("role", "is_platform_staff", "is_active", "mfa_enabled")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone_number")}),
        ("Tenant & Role", {"fields": ("tenant", "role", "branch_id", "is_platform_staff")}),
        ("Security", {"fields": ("mfa_enabled", "is_email_verified", "failed_login_attempts", "locked_until")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "role", "tenant")}),
    )


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "key_prefix", "is_active", "last_used_at", "created_at")
    list_filter = ("is_active", "tenant")
    search_fields = ("name", "key_prefix")


@admin.register(LoginSession)
class LoginSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "ip_address", "is_revoked", "created_at", "expires_at")
    list_filter = ("is_revoked",)
    search_fields = ("user__email", "ip_address")
