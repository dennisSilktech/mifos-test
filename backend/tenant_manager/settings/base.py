"""
Base settings for the tenant_manager control-plane project.
Loads secrets from environment (see /etc/tenant-manager/secrets.env in production).
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "corsheaders",
    # local apps
    "organizations",
    "tenants",
    "provisioning",
    "subscriptions",
    "audit",
    "authentication",
    "domains",
    "fineract_gateway",
    "billing",
    "notifications",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "tenants.middleware.TenantResolverMiddleware",
    "authentication.middleware.RateLimitMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "audit.middleware.AuditLoggingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "tenant_manager.security_headers.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "tenant_manager.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "tenant_manager.wsgi.application"
ASGI_APPLICATION = "tenant_manager.asgi.application"

# ---------------------------------------------------------------------------
# Database — control-plane "tenant_registry" DB.
# Per-tenant databases (tenant_imara, tenant_unity, ...) are registered
# dynamically at runtime by tenants.db_router / tenants.connection_registry.
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("REGISTRY_DB_NAME", "tenant_registry"),
        "USER": os.environ.get("REGISTRY_DB_USER", "registry_app_role"),
        "PASSWORD": os.environ.get("REGISTRY_DB_PASSWORD", ""),
        "HOST": os.environ.get("REGISTRY_DB_HOST", "localhost"),
        "PORT": os.environ.get("REGISTRY_DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

DATABASE_ROUTERS = ["tenants.db_router.TenantDatabaseRouter"]

AUTH_USER_MODEL = "authentication.User"

AUTHENTICATION_BACKENDS = ["authentication.backends.PlatformStaffBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "authentication.validators.PasswordStrengthValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# email is unique *per tenant* (see authentication.User.Meta.constraints),
# not globally — Django's default auth.E003 check assumes a globally unique
# USERNAME_FIELD, which doesn't apply to our multi-tenant login model since
# AuthenticationService always scopes lookups by (tenant, email).
SILENCED_SYSTEM_CHECKS = ["auth.E003"]

# ---------------------------------------------------------------------------
# DRF / JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {"login": "5/min"},
    "EXCEPTION_HANDLER": "tenant_manager.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "RS256",
    "SIGNING_KEY": os.environ.get("JWT_SIGNING_KEY", ""),
    "VERIFYING_KEY": os.environ.get("JWT_VERIFYING_KEY", ""),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGIN_REGEXES = [r"^https:\/\/([\w-]+\.)?banking\.com$"]
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Redis / Cache / Celery
# ---------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
# Every task here is fire-and-forget (provisioning/audit/notifications all
# report their own state via models, not task return values) — nothing
# ever calls .get() on a result. Ignoring results means .delay() never has
# to touch the result backend, so a slow/unreachable Redis can't turn into
# a multi-second hang (or a 20s retry loop) on every mutating request.
CELERY_TASK_IGNORE_RESULT = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_TIMEOUT = 2

# ---------------------------------------------------------------------------
# Platform-specific settings
# ---------------------------------------------------------------------------
PLATFORM_BASE_DOMAIN = os.environ.get("PLATFORM_BASE_DOMAIN", "localhost")

PLATFORM_ADMIN_HOSTS = {
    PLATFORM_BASE_DOMAIN,
    f"admin.{PLATFORM_BASE_DOMAIN}",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
} | {
    h.strip() for h in os.environ.get("PLATFORM_EXTRA_ADMIN_HOSTS", "").split(",") if h.strip()
}

CREDENTIAL_ENCRYPTION_KEY = os.environ.get("CREDENTIAL_ENCRYPTION_KEY", "")

FINERACT_BASE_URL = os.environ.get(
    "FINERACT_BASE_URL", 
    "https://fineract:8443/fineract-provider/api/v1"
)
FINERACT_ADMIN_USERNAME = os.environ.get("FINERACT_ADMIN_USERNAME", "mifos")
FINERACT_ADMIN_PASSWORD = os.environ.get("FINERACT_ADMIN_PASSWORD", "")
FINERACT_VERIFY_SSL = os.environ.get("FINERACT_VERIFY_SSL", "true").lower() == "true"

PG_SUPERUSER_HOST = os.environ.get("PG_SUPERUSER_HOST", "localhost")
...


# Postgres superuser connection used ONLY by the provisioning service
PG_SUPERUSER_HOST = os.environ.get("PG_SUPERUSER_HOST", "localhost")
PG_SUPERUSER_PORT = os.environ.get("PG_SUPERUSER_PORT", "5432")
PG_SUPERUSER_NAME = os.environ.get("PG_SUPERUSER_NAME", "postgres")
PG_SUPERUSER_PASSWORD = os.environ.get("PG_SUPERUSER_PASSWORD", "")

RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "120"))
LOGIN_RATE_LIMIT_PER_MINUTE = int(os.environ.get("LOGIN_RATE_LIMIT_PER_MINUTE", "5"))

EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@banking.silktechagency.com")

LOGIN_URL = "dashboard:login"
LOGIN_REDIRECT_URL = "dashboard:tenant-list"
LOGOUT_REDIRECT_URL = "dashboard:login"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "structured"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        # 1. Root logger (catches everything default)
        "": {
            "handlers": ["console"],
            "level": "INFO",
        },
        # 2. Provisioning pipeline (catches DB creation & Mifos/Fineract setup)
        "provisioning": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        # 3. Tenant routing & Resolver (catches Subdomain/Domain parsing)
        "tenants": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        # 4. Domain & Subdomain specific operations
        "domains": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        # 5. Core Database SQL Queries (Logs every raw SQL query)
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        # 6. Celery Workers (if provisioning runs asynchronously)
        "celery": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "celery.task": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        # 7. Gateway calls (if Mifos/Fineract schema tenant is provisioned)
        "fineract_gateway": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Prevents Celery from overriding Django's logging settings
CELERY_WORKER_HIJACK_ROOT_LOGGER = False