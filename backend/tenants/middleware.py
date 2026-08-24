import json
from types import SimpleNamespace

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render

DOMAIN_CACHE_TTL = 300  # seconds


class TenantResolverMiddleware:
    """
    Resolves the request's Host header to a Tenant via the Domain table,
    caches the result in Redis, and attaches `request.tenant`.

    admin.<PLATFORM_BASE_DOMAIN> and bare API/health probes are exempt from
    tenant resolution (request.tenant stays None => platform staff scope).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0].lower()

        from django.conf import settings

        if (
            host.startswith("admin.")
            or host in ("localhost", "127.0.0.1", "0.0.0.0")
            or host == settings.PLATFORM_BASE_DOMAIN  # bare platform domain, no subdomain
        ):
            request.tenant = None
            return self.get_response(request)

        cache_key = f"domain:{host}"
        cached = cache.get(cache_key)

        if cached:
            tenant_data = json.loads(cached) if isinstance(cached, str) else cached
        else:
            from .models import Domain

            domain = Domain.objects.select_related("tenant").filter(hostname=host).first()
            if not domain:
                return self._error_response(request, 404, "TENANT_NOT_FOUND", "Organization not found.")

            tenant_data = {
                "id": str(domain.tenant.id),
                "tenant_code": domain.tenant.tenant_code,
                "status": domain.tenant.status,
                "db_name": domain.tenant.db_name,
                "db_user": domain.tenant.db_user,
                "db_host": domain.tenant.db_host,
                "db_port": domain.tenant.db_port,
                "fineract_tenant_identifier": domain.tenant.fineract_tenant_identifier,
            }
            cache.set(cache_key, json.dumps(tenant_data), DOMAIN_CACHE_TTL)

        if tenant_data["status"] == "SUSPENDED":
            return self._error_response(
                request, 403, "TENANT_SUSPENDED", "This organization's account is suspended."
            )

        if tenant_data["status"] != "READY":
            return self._error_response(
                request, 503, "TENANT_NOT_READY", "This organization is still being set up."
            )

        request.tenant = SimpleNamespace(**tenant_data)
        return self.get_response(request)

    @staticmethod
    def _error_response(request, status_code, code, message):
        if request.path.startswith("/api/"):
            return JsonResponse({"error": {"code": code, "message": message}}, status=status_code)
        return render(request, "tenants/error.html", {"message": message}, status=status_code)
