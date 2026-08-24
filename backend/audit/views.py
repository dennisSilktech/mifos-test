from rest_framework import serializers, viewsets

from authentication.permissions import IsAuditorOrSuperAdmin

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor_user.email", read_only=True, default=None)
    tenant_code = serializers.CharField(source="tenant.tenant_code", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id", "tenant", "tenant_code", "actor_user", "actor_email", "actor_ip",
            "action", "target_type", "target_id", "metadata", "created_at",
        ]
        read_only_fields = fields


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("tenant", "actor_user").all().order_by("-created_at")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuditorOrSuperAdmin]
    filterset_fields = ["tenant", "action", "actor_user"]
