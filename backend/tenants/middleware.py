# import json
# from types import SimpleNamespace

# from django.core.cache import cache
# from django.http import JsonResponse
# from django.shortcuts import render

# DOMAIN_CACHE_TTL = 300  # seconds


# class TenantResolverMiddleware:
#     """
#     Resolves the request's Host header to a Tenant via the Domain table,
#     caches the result in Redis, and attaches `request.tenant`.

#     admin.<PLATFORM_BASE_DOMAIN> and bare API/health probes are exempt from
#     tenant resolution (request.tenant stays None => platform staff scope).
#     """

#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):
#         host = request.get_host().split(":")[0].lower()

#         from django.conf import settings

#         if (
#             host.startswith("admin.")
#             or host in ("localhost", "127.0.0.1", "0.0.0.0")
#             or host == settings.PLATFORM_BASE_DOMAIN  # bare platform domain, no subdomain
#         ):
#             request.tenant = None
#             return self.get_response(request)

#         cache_key = f"domain:{host}"
#         cached = cache.get(cache_key)

#         if cached:
#             tenant_data = json.loads(cached) if isinstance(cached, str) else cached
#         else:
#             from .models import Domain

#             domain = Domain.objects.select_related("tenant").filter(hostname=host).first()
#             if not domain:
#                 return self._error_response(request, 404, "TENANT_NOT_FOUND", "Organization not found.")

#             tenant_data = {
#                 "id": str(domain.tenant.id),
#                 "tenant_code": domain.tenant.tenant_code,
#                 "status": domain.tenant.status,
#                 "db_name": domain.tenant.db_name,
#                 "db_user": domain.tenant.db_user,
#                 "db_host": domain.tenant.db_host,
#                 "db_port": domain.tenant.db_port,
#                 "fineract_tenant_identifier": domain.tenant.fineract_tenant_identifier,
#             }
#             cache.set(cache_key, json.dumps(tenant_data), DOMAIN_CACHE_TTL)

#         if tenant_data["status"] == "SUSPENDED":
#             return self._error_response(
#                 request, 403, "TENANT_SUSPENDED", "This organization's account is suspended."
#             )

#         if tenant_data["status"] != "READY":
#             return self._error_response(
#                 request, 503, "TENANT_NOT_READY", "This organization is still being set up."
#             )

#         request.tenant = SimpleNamespace(**tenant_data)
#         return self.get_response(request)

#     @staticmethod
#     def _error_response(request, status_code, code, message):
#         if request.path.startswith("/api/"):
#             return JsonResponse({"error": {"code": code, "message": message}}, status=status_code)
#         return render(request, "tenants/error.html", {"message": message}, status=status_code)





import json
import logging
from types import SimpleNamespace

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)

DOMAIN_CACHE_TTL = 300  # seconds


class TenantResolverMiddleware:
    """
    Resolves the request's Host header to a Tenant via the Domain table,
    caches the result in Redis, and attaches `request.tenant`.

    Any host in settings.PLATFORM_ADMIN_HOSTS (which always includes
    PLATFORM_BASE_DOMAIN, "admin.<PLATFORM_BASE_DOMAIN>", and the usual
    local-dev hosts) is exempt from tenant resolution — request.tenant
    stays None, i.e. platform-staff scope.
    """

    def __init__(self, get_response):
        self.get_response = get_response


    def __call__(self, request):
        if request.path.startswith("/admin/") or request.path.startswith("/api/v1/health"):
            request.tenant = None
            return self.get_response(request)

        host = self._normalize(request.get_host())

        from django.conf import settings
        admin_hosts = {self._normalize(h) for h in settings.PLATFORM_ADMIN_HOSTS}

        if host in admin_hosts or host.startswith("admin."):
            request.tenant = None
            return self.get_response(request)

        # 1. Fetch from DB (or get cached domain/tenant ID)
        from .models import Domain, Tenant

        cache_key = f"domain:{host}"
        tenant_id = cache.get(cache_key)

        if not tenant_id:
            domain = Domain.objects.select_related("tenant").filter(hostname=host).first()
            if not domain:
                logger.warning(
                    "TenantResolverMiddleware: no Domain row for host=%r.", host
                )
                return self._error_response(request, 404, "TENANT_NOT_FOUND", "Organization not found.")
            
            tenant = domain.tenant
            cache.set(cache_key, str(tenant.id), DOMAIN_CACHE_TTL)
        else:
            tenant = Tenant.objects.filter(id=tenant_id).first()
            if not tenant:
                return self._error_response(request, 404, "TENANT_NOT_FOUND", "Organization not found.")

        # 2. Check Status
        if tenant.status == "SUSPENDED":
            return self._error_response(
                request, 403, "TENANT_SUSPENDED", "This organization's account is suspended."
            )

        if tenant.status != "READY":
            return self._error_response(
                request, 503, "TENANT_NOT_READY", "This organization is still being set up."
            )

        # 3. Attach actual Model instance
        request.tenant = tenant
        return self.get_response(request)

    @staticmethod
    def _normalize(host: str) -> str:
        # Strip port, trailing dot (some clients/DNS send FQDNs with one),
        # surrounding whitespace, and lowercase — so a stray difference in
        # any of those can't cause a false "organization not found".
        return host.split(":")[0].strip().rstrip(".").lower()

    @staticmethod
    def _error_response(request, status_code, code, message):
        if request.path.startswith("/api/"):
            return JsonResponse({"error": {"code": code, "message": message}}, status=status_code)
        return render(request, "tenants/error.html", {"message": message}, status=status_code)