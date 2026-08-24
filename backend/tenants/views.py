from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsPlatformSupportOrAbove, IsSuperAdmin
from provisioning.models import ProvisionJob
from provisioning.tasks import run_provisioning

from .models import Domain, Tenant
from .serializers import DomainSerializer, SuspendTenantSerializer, TenantSerializer
from .services import TenantService


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
        run_provisioning.delay(str(job.id))
        return Response({"job_id": str(job.id), "status": "queued"}, status=202)


class DomainViewSet(viewsets.ModelViewSet):
    queryset = Domain.objects.select_related("tenant").all()
    serializer_class = DomainSerializer
    permission_classes = [IsPlatformSupportOrAbove]
    filterset_fields = ["tenant", "is_custom"]


def landing(request):
    """Simple tenant-facing landing page.

    If `request.tenant` has been attached by the middleware this returns a
    friendly welcome page with the organization's name. Otherwise it falls
    through to the dashboard (which is mounted at the same root for staff).
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        # let the dashboard handle non-tenant hosts
        from django.shortcuts import redirect

        return redirect("dashboard:tenant-list")

    # load richer organization info from the registry
    from .models import Tenant as TenantModel

    try:
        t = TenantModel.objects.select_related("organization").get(id=tenant.id)
        org_name = t.organization.trading_name or t.organization.legal_name
    except Exception:
        org_name = tenant.tenant_code

    from django.shortcuts import render

    return render(request, "tenants/welcome.html", {"org_name": org_name, "tenant_code": tenant.tenant_code})
