import subprocess
from datetime import date

from celery import shared_task
from django.conf import settings

from .models import Tenant


@shared_task
def backup_tenant_database(tenant_id):
    tenant = Tenant.objects.get(id=tenant_id)
    if tenant.status != Tenant.Status.READY:
        return

    out_dir = f"/backups/{tenant.tenant_code}"
    out_file = f"{out_dir}/{date.today().isoformat()}_{tenant.tenant_code}.dump"
    subprocess.run(["mkdir", "-p", out_dir], check=True)
    subprocess.run(
        [
            "pg_dump", "-Fc",
            "-h", tenant.db_host, "-p", str(tenant.db_port),
            "-U", settings.PG_SUPERUSER_NAME,
            "-f", out_file,
            tenant.db_name,
        ],
        check=True,
        env={"PGPASSWORD": settings.PG_SUPERUSER_PASSWORD},
    )


@shared_task
def backup_all_tenant_databases():
    for tenant_id in Tenant.objects.filter(status=Tenant.Status.READY).values_list("id", flat=True):
        backup_tenant_database.delay(str(tenant_id))
