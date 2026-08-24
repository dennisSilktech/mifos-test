from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from audit.services import AuditService

from .models import Domain, Tenant


class TenantService:
    @staticmethod
    @transaction.atomic
    def suspend(tenant: Tenant, reason: str, actor=None):
        tenant.status = Tenant.Status.SUSPENDED
        tenant.suspended_at = timezone.now()
        tenant.suspension_reason = reason
        tenant.save(update_fields=["status", "suspended_at", "suspension_reason"])
        AuditService.log(
            actor=actor, tenant=tenant, action="TENANT_SUSPENDED",
            target_type="Tenant", target_id=str(tenant.id), metadata={"reason": reason},
        )
        DomainManager.bust_cache(tenant)

    @staticmethod
    @transaction.atomic
    def activate(tenant: Tenant, actor=None):
        tenant.status = Tenant.Status.READY
        tenant.is_active = True
        tenant.suspended_at = None
        tenant.suspension_reason = ""
        tenant.save(update_fields=["status", "is_active", "suspended_at", "suspension_reason"])
        AuditService.log(
            actor=actor, tenant=tenant, action="TENANT_ACTIVATED",
            target_type="Tenant", target_id=str(tenant.id),
        )
        DomainManager.bust_cache(tenant)


class DomainManager:
    @staticmethod
    def generate_subdomain(tenant_code: str) -> str:
        from django.conf import settings

        return f"{tenant_code}.{settings.PLATFORM_BASE_DOMAIN}"

    @staticmethod
    def create_primary_domain(tenant: Tenant) -> Domain:
        hostname = DomainManager.generate_subdomain(tenant.tenant_code)
        return Domain.objects.create(tenant=tenant, hostname=hostname, is_primary=True)

    @staticmethod
    def bust_cache(tenant: Tenant):
        for domain in tenant.domains.all():
            cache.delete(f"domain:{domain.hostname}")

    @staticmethod
    def add_custom_domain(tenant: Tenant, hostname: str) -> Domain:
        return Domain.objects.create(tenant=tenant, hostname=hostname, is_primary=False, is_custom=True)
