from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsPlatformSupportOrAbove

from .models import ProvisionJob
from .tasks import run_provisioning


class ProvisionJobSerializer(serializers.ModelSerializer):
    tenant_code = serializers.CharField(source="tenant.tenant_code", read_only=True)

    class Meta:
        model = ProvisionJob
        fields = [
            "id", "tenant", "tenant_code", "current_step", "is_success",
            "error_message", "retry_count", "started_at", "finished_at",
        ]
        read_only_fields = fields


class ProvisionJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProvisionJob.objects.select_related("tenant").all().order_by("-started_at")
    serializer_class = ProvisionJobSerializer
    permission_classes = [IsPlatformSupportOrAbove]
    filterset_fields = ["tenant", "current_step", "is_success"]

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        job = self.get_object()
        job.retry_count += 1
        job.is_success = None
        job.error_message = ""
        job.save(update_fields=["retry_count", "is_success", "error_message"])
        run_provisioning.delay(str(job.id))
        return Response({"status": "requeued", "retry_count": job.retry_count})
