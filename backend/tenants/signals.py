import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Tenant

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Tenant)
def on_tenant_status_change(sender, instance: Tenant, created, **kwargs):
    """
    IMPORTANT: this runs synchronously, inline, inside every Tenant.save()
    call — including the one ProvisioningService.run() makes at the very
    end of a successful provisioning run. If a .delay() call here raises
    (broker unreachable), that exception propagates straight out of
    .save() and gets caught by ProvisioningService's try/except, which
    marks the job FAILED and rolls back the database/admin user/Fineract
    registration that had already succeeded. Notification side-effects
    must never be able to do that — always best-effort here.
    """
    if created:
        return

    if instance.status == Tenant.Status.READY:
        from notifications.tasks import send_tenant_activated_email

        try:
            send_tenant_activated_email.delay(str(instance.id))
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to enqueue activation email for tenant %s (broker unreachable?)",
                instance.tenant_code, exc_info=True,
            )

    if instance.status == Tenant.Status.SUSPENDED:
        from authentication.tasks import revoke_tenant_sessions

        try:
            revoke_tenant_sessions.delay(str(instance.id))
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to enqueue session revocation for suspended tenant %s (broker unreachable?)",
                instance.tenant_code, exc_info=True,
            )