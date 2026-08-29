from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsPlatformSupportOrAbove, IsSuperAdmin
from provisioning.models import ProvisionJob
from provisioning.tasks import provision_tenant_database_task

from .models import Domain, Tenant
from .serializers import DomainSerializer, SuspendTenantSerializer, TenantSerializer
from .services import TenantService

from django.conf import settings
from django.shortcuts import redirect, render
from .models import Tenant as TenantModel



class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.select_related("organization").prefetch_related("domains").all()
    serializer_class = TenantSerializer
    permission_classes = [IsPlatformSupportOrAbove]
    filterset_fields = ["status", "organization"]
    http_method_names = ["get", "post"]

    @action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def suspend(self, request, pk=None):
        tenant = self.get_object()
        serializer = SuspendTenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        TenantService.suspend(tenant, serializer.validated_data["reason"], actor=request.user)
        return Response(TenantSerializer(tenant).data)

    @action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def activate(self, request, pk=None):
        tenant = self.get_object()
        TenantService.activate(tenant, actor=request.user)
        return Response(TenantSerializer(tenant).data)

    @action(detail=True, methods=["post"], permission_classes=[IsSuperAdmin])
    def provision(self, request, pk=None):
        tenant = self.get_object()
        job = ProvisionJob.objects.create(tenant=tenant)
        provision_tenant_database_task.delay(str(job.id))
        return Response({"job_id": str(job.id), "status": "queued"}, status=202)


class DomainViewSet(viewsets.ModelViewSet):
    queryset = Domain.objects.select_related("tenant").all()
    serializer_class = DomainSerializer
    permission_classes = [IsPlatformSupportOrAbove]
    filterset_fields = ["tenant", "is_custom"]



def landing(request):
    """
    Landing page for both platform and tenant hosts.

    Platform:
        banking.silktechagency.com

    Tenant:
        dennis.banking.silktechagency.com
    """

    tenant = getattr(request, "tenant", None)
    host = request.get_host().split(":")[0].lower()

    # Platform homepage
    if tenant is None:
        return render(
            request,
            "platform/index.html",
            {
                "platform_domain": settings.PLATFORM_BASE_DOMAIN,
            },
        )

    # Always send tenant hosts to the Angular frontend login page.
    return redirect(f"http://{host}:4200/#/login")
