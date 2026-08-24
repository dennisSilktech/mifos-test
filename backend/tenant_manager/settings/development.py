from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Local/dev convenience: SQLite for the control-plane DB when Postgres isn't
# available yet. Per-tenant databases still use the dynamic Postgres router
# in production; for local dev, DatabaseCreator can be pointed at a local
# Postgres instance via env vars.
if os.environ.get("USE_SQLITE", "true").lower() == "true":
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CORS_ALLOW_ALL_ORIGINS = True

# Don't 500 the whole app if Redis isn't up yet while poking around locally
# outside the docker-compose stack (rate limiting/caching just no-ops).
CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
