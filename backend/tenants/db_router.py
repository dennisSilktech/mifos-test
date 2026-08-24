CONTROL_PLANE_APPS = {
    "organizations", "tenants", "provisioning", "subscriptions",
    "audit", "authentication", "domains", "admin", "auth",
    "contenttypes", "sessions", "token_blacklist",
}


class TenantDatabaseRouter:
    """
    Keeps all control-plane models on the 'default' (tenant_registry) DB.
    Tenant-local banking/reporting models (if any live in Django rather than
    Fineract) declare `app_label` outside CONTROL_PLANE_APPS and are routed
    explicitly via `.using(tenant.db_alias)` at the call site instead of
    through this router, since the target alias is only known per-request.
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label in CONTROL_PLANE_APPS:
            return "default"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in CONTROL_PLANE_APPS:
            return "default"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in CONTROL_PLANE_APPS:
            return db == "default"
        # Tenant-local app migrations are applied explicitly per tenant alias
        # by the provisioning service, not by the default `migrate` command.
        return db == "default" if db == "default" else None
