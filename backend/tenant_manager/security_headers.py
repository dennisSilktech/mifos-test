class SecurityHeadersMiddleware:
    """Adds hardening headers not already covered by Django's SecurityMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response.setdefault(
            "X-Content-Type-Options",
            "nosniff",
        )

        response.setdefault(
            "X-Frame-Options",
            "DENY",
        )

        response.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
                
            ),
        )

        response.setdefault(
            "Referrer-Policy",
            "strict-origin-when-cross-origin",
        )

        response.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )

        return response