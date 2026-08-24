import logging

from .services import log_action_async

logger = logging.getLogger(__name__)

SENSITIVE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SKIP_PATH_PREFIXES = ("/api/v1/auth/login", "/api/v1/auth/refresh")


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class AuditLoggingMiddleware:
    """
    Fires an async audit-log write for every sensitive mutating request.
    Login/refresh are excluded here since AuthenticationService already
    writes explicit LOGIN_SUCCESS/LOGIN_FAILED entries with better context.

    Audit logging is best-effort: if Redis/Celery is unreachable, the
    primary request must still succeed. A broker hiccup should never turn
    into a 500 for the person clicking a button.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = getattr(request, "user", None)
        if (
            request.method in SENSITIVE_METHODS
            and user is not None
            and getattr(user, "is_authenticated", False)
            and not request.path.startswith(SKIP_PATH_PREFIXES)
        ):
            tenant = getattr(request, "tenant", None)
            try:
                log_action_async.delay(
                    actor_id=str(user.id),
                    tenant_id=str(tenant.id) if tenant else None,
                    action=f"{request.method} {request.path}",
                    actor_ip=_client_ip(request),
                    target_type="HTTPRequest",
                    target_id=request.path,
                    metadata={"status_code": response.status_code},
                )
            except Exception:  # noqa: BLE001 — never let audit logging break the request
                logger.warning(
                    "Failed to enqueue audit log for %s %s (broker unreachable?)",
                    request.method, request.path, exc_info=True,
                )
        return response
