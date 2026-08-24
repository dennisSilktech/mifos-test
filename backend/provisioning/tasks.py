from celery import shared_task


@shared_task(bind=True, max_retries=0)
def run_provisioning(self, job_id):
    from .models import ProvisionJob
    from .services import ProvisioningService

    job = ProvisionJob.objects.select_related("tenant", "tenant__organization").get(id=job_id)
    job.celery_task_id = self.request.id
    job.save(update_fields=["celery_task_id"])

    ProvisioningService(job).run()
