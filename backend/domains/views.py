import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsTenantCEOOrAdmin
from tenants.services import DomainManager
from .tasks import verify_custom_domain

# Logger configured under the "domains" app hierarchy
logger = logging.getLogger("domains")


@api_view(["POST"])
@permission_classes([IsTenantCEOOrAdmin])
def add_custom_domain(request):
    hostname = request.data.get("hostname")
    
    if not hostname:
        logger.warning(
            "[ADD_DOMAIN_FAILED] Hostname missing in request | User ID: %s",
            getattr(request.user, "id", "Anonymous")
        )
        return Response(
            {"error": {"code": "HOSTNAME_REQUIRED", "message": "hostname is required."}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Note: request.tenant is already attached via TenantResolverMiddleware
    tenant_obj = request.tenant

    logger.info(
        "--> [ADD_DOMAIN_START] Request received | Hostname: '%s' | Tenant ID: %s | User ID: %s",
        hostname,
        tenant_obj.id,
        getattr(request.user, "id", "Unknown"),
    )

    try:
        # 1. Create/register custom domain record
        domain = DomainManager.add_custom_domain(tenant_obj, hostname)
        logger.info(
            "--> [ADD_DOMAIN_SUCCESS] Domain record created | Domain ID: %s | Hostname: '%s' | Tenant ID: %s",
            domain.id,
            domain.hostname,
            tenant_obj.id,
        )

        # 2. Dispatch background verification task via Celery
        task_result = verify_custom_domain.delay(str(domain.id))
        logger.debug(
            "[ADD_DOMAIN_CELERY] Verification task dispatched | Task ID: %s | Target Domain ID: %s",
            task_result.id,
            domain.id,
        )

        return Response(
            {
                "id": str(domain.id),
                "hostname": domain.hostname,
                "status": "verification_pending",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    except Exception as e:
        logger.exception(
            "--> [ADD_DOMAIN_ERROR] Unhandled exception adding domain '%s' for Tenant ID: %s | Error: %s",
            hostname,
            tenant_obj.id,
            str(e),
        )
        return Response(
            {
                "error": {
                    "code": "DOMAIN_ADDITION_FAILED",
                    "message": "Failed to add domain due to an internal server error.",
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )