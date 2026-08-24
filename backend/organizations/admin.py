from django.contrib import admin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "org_type", "country", "kyc_verified", "created_at")
    list_filter = ("org_type", "country", "kyc_verified")
    search_fields = ("legal_name", "trading_name", "registration_number")
