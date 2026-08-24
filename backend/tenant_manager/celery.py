import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tenant_manager.settings.production")

app = Celery("tenant_manager")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "sweep-expired-subscriptions": {
        "task": "subscriptions.tasks.sweep_expired_subscriptions",
        "schedule": crontab(hour=1, minute=0),
    },
    "sweep-expired-login-sessions": {
        "task": "authentication.tasks.purge_expired_sessions",
        "schedule": crontab(hour=2, minute=0),
    },
    "nightly-tenant-backups": {
        "task": "tenants.tasks.backup_all_tenant_databases",
        "schedule": crontab(hour=3, minute=0),
    },
}
