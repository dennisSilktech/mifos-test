from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Tenant
from .services import DomainManager


@receiver(post_save, sender=Tenant)
def create_primary_domain_on_tenant_create(sender, instance: Tenant, created: bool, **kwargs):
    """Ensure a primary Domain exists for newly-created Tenants.

    This makes adding tenants via admin or shell immediately visible as a
    subdomain in the system without running the full provisioning flow.
    Creating the Domain is safe to do without creating the tenant's DB.
    """
    if not created:
        return

    # avoid dupes in concurrent scenarios
    if instance.domains.exists():
        return

    try:
        DomainManager.create_primary_domain(instance)
    except Exception:
        # don't raise — domain creation shouldn't block tenant record creation
        pass
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Tenant


@receiver(post_save, sender=Tenant)
def on_tenant_status_change(sender, instance: Tenant, created, **kwargs):
    if created:
        return
    if instance.status == Tenant.Status.READY:
        from notifications.tasks import send_tenant_activated_email

        send_tenant_activated_email.delay(str(instance.id))
    if instance.status == Tenant.Status.SUSPENDED:
        from authentication.tasks import revoke_tenant_sessions

        revoke_tenant_sessions.delay(str(instance.id))
