"""
Registers a Django database connection alias for a tenant on demand, so
`SomeTenantScopedModel.objects.using(tenant.db_alias)` works without every
tenant database needing a static entry in settings.DATABASES.
"""
from django.conf import settings
from django.db import connections


def db_alias_for(tenant) -> str:
    return f"tenant_{tenant.tenant_code}"


def ensure_registered(tenant):
    alias = db_alias_for(tenant)
    if alias in settings.DATABASES:
        return alias

    from .models import EncryptedCredential

    try:
        credential = EncryptedCredential.objects.get(tenant=tenant)
        password = credential.get_password()
    except EncryptedCredential.DoesNotExist:
        password = ""

    settings.DATABASES[alias] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": tenant.db_name,
        "USER": tenant.db_user,
        "PASSWORD": password,
        "HOST": tenant.db_host,
        "PORT": tenant.db_port,
        "CONN_MAX_AGE": 60,
        "TIME_ZONE": None,
    }
    connections.databases = settings.DATABASES
    return alias
