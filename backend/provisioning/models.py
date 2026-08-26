import uuid
from django.db import models


class ProvisionJob(models.Model):
    class Step(models.TextChoices):
        VALIDATE = "VALIDATE", "Validate"
        CREATE_DB = "CREATE_DB", "Create Database"
        CREATE_DB_USER = "CREATE_DB_USER", "Create DB User"
        GRANT_PERMISSIONS = "GRANT_PERMISSIONS", "Grant Permissions"
        RUN_FINERACT_SCHEMA = "RUN_FINERACT_SCHEMA", "Run Fineract Schema"
        REGISTER_FINERACT_TENANT = "REGISTER_FINERACT_TENANT", "Register Fineract Tenant"
        SAVE_REGISTRY = "SAVE_REGISTRY", "Save Tenant Registry"
        CREATE_ADMIN_USER = "CREATE_ADMIN_USER", "Create Admin User"
        SEND_WELCOME_EMAIL = "SEND_WELCOME_EMAIL", "Send Welcome Email"
        ACTIVATE = "ACTIVATE", "Activate Tenant"
        DONE = "DONE", "Done"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="provision_jobs",
    )
    current_step = models.CharField(
        max_length=32,
        choices=Step.choices,
        default=Step.VALIDATE,
    )
    is_success = models.BooleanField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=155, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "current_step"])]

    def __str__(self):
        return f"{self.tenant.tenant_code} :: {self.current_step}"