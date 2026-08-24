from celery import shared_task
from django.utils import timezone

from .models import Subscription


@shared_task
def sweep_expired_subscriptions():
    """Marks TRIAL/ACTIVE subscriptions past their period end as PAST_DUE."""
    expired = Subscription.objects.filter(
        current_period_end__lt=timezone.now(),
        status__in=[Subscription.Status.TRIAL, Subscription.Status.ACTIVE],
    )
    for sub in expired:
        sub.status = Subscription.Status.PAST_DUE
        sub.save(update_fields=["status"])
