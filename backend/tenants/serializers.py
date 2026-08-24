from rest_framework import serializers

from .models import Domain, Tenant


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ["id", "tenant", "hostname", "is_primary", "is_custom", "ssl_verified", "created_at"]
        read_only_fields = ["id", "created_at"]


class TenantSerializer(serializers.ModelSerializer):
    domains = DomainSerializer(many=True, read_only=True)

    class Meta:
        model = Tenant
        fields = [
            "id", "organization", "tenant_code", "db_name", "fineract_tenant_identifier",
            "status", "is_active", "provisioned_at", "suspended_at", "suspension_reason",
            "domains", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "db_name", "fineract_tenant_identifier", "status", "is_active",
            "provisioned_at", "suspended_at", "created_at", "updated_at",
        ]


class SuspendTenantSerializer(serializers.Serializer):
    reason = serializers.CharField()
