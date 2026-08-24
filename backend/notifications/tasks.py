from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_welcome_email(self, organization_id):
    from organizations.models import Organization

    org = Organization.objects.select_related().get(id=organization_id)
    tenant = org.tenants.first()
    domain = tenant.primary_domain.hostname if tenant and tenant.primary_domain else ""

    try:
        send_mail(
            subject="Welcome to Banking SaaS",
            message=(
                f"Hello {org.trading_name or org.legal_name},\n\n"
                f"Your organization has been created. Your portal is available at "
                f"https://{domain}\n\nThe Banking SaaS Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[org.contact_email],
        )
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


@shared_task
def send_tenant_activated_email(tenant_id):
    from tenants.models import Tenant

    tenant = Tenant.objects.select_related("organization").get(id=tenant_id)
    domain = tenant.primary_domain.hostname if tenant.primary_domain else ""
    send_mail(
        subject="Your organization is now active",
        message=f"Your portal is live at https://{domain}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[tenant.organization.contact_email],
    )
