from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class RateLimitMiddleware:
    """
    Redis-backed sliding-window rate limiter, keyed by tenant+IP.
    Login endpoint gets a tighter limit than general traffic.
    """

    LOGIN_PATHS = ("/api/v1/auth/login/",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = getattr(getattr(request, "tenant", None), "id", "anon")
        ip = get_client_ip(request)

        is_login = request.path in self.LOGIN_PATHS
        limit = settings.LOGIN_RATE_LIMIT_PER_MINUTE if is_login else settings.RATE_LIMIT_PER_MINUTE
        cache_key = f"rl:{'login' if is_login else 'req'}:{tenant_id}:{ip}"

        count = cache.get(cache_key, 0)
        if count >= limit:
            return JsonResponse(
                {"error": {"code": "RATE_LIMITED", "message": "Too many requests. Please slow down."}},
                status=429,
            )
        cache.set(cache_key, count + 1, timeout=60)
        return self.get_response(request)
