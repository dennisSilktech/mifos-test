from .base import *  # noqa

DEBUG = False

SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 63072000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = False

if not SECRET_KEY or SECRET_KEY == "insecure-dev-key-change-me":
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production")
if not SIMPLE_JWT["SIGNING_KEY"]:
    raise RuntimeError("JWT_SIGNING_KEY must be set in production")
