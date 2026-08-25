from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

# PostgreSQL configuration for Docker/local execution
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('REGISTRY_DB_NAME', 'tenant_registry'),
        'USER': os.environ.get('REGISTRY_DB_USER', 'registry_app_role'),
        'PASSWORD': os.environ.get('REGISTRY_DB_PASSWORD'),
        'HOST': os.environ.get('REGISTRY_DB_HOST', 'host.docker.internal'),  # Updated variable key
        'PORT': os.environ.get('REGISTRY_DB_PORT', '5432'),
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CORS_ALLOW_ALL_ORIGINS = True

# Don't 500 the whole app if Redis isn't up yet while poking around locally
# outside the docker-compose stack (rate limiting/caching just no-ops).
CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True