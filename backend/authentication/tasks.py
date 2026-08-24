from celery import shared_task
from django.utils import timezone

from .models import LoginSession


@shared_task
def purge_expired_sessions():
    LoginSession.objects.filter(expires_at__lt=timezone.now()).delete()


@shared_task
def revoke_tenant_sessions(tenant_id):
    LoginSession.objects.filter(user__tenant_id=tenant_id, is_revoked=False).update(is_revoked=True)
