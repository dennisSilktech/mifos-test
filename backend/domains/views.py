from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsTenantCEOOrAdmin
from tenants.services import DomainManager

from .tasks import verify_custom_domain


@api_view(["POST"])
@permission_classes([IsTenantCEOOrAdmin])
def add_custom_domain(request):
    hostname = request.data.get("hostname")
    if not hostname:
        return Response({"error": {"code": "HOSTNAME_REQUIRED", "message": "hostname is required."}}, status=400)

    tenant = request.tenant
    from tenants.models import Tenant

    tenant_obj = Tenant.objects.get(id=tenant.id)
    domain = DomainManager.add_custom_domain(tenant_obj, hostname)
    verify_custom_domain.delay(str(domain.id))
    return Response({"id": str(domain.id), "hostname": domain.hostname, "status": "verification_pending"}, status=202)
