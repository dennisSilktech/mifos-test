import uuid

from django.db import models


class Subscription(models.Model):
    class Plan(models.TextChoices):
        STARTER = "STARTER", "Starter"
        GROWTH = "GROWTH", "Growth"
        ENTERPRISE = "ENTERPRISE", "Enterprise"

    class Status(models.TextChoices):
        TRIAL = "TRIAL", "Trial"
        ACTIVE = "ACTIVE", "Active"
        PAST_DUE = "PAST_DUE", "Past Due"
        CANCELED = "CANCELED", "Canceled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField("tenants.Tenant", on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField(max_length=16, choices=Plan.choices, default=Plan.STARTER)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIAL)
    max_members = models.PositiveIntegerField(default=500)
    max_branches = models.PositiveIntegerField(default=1)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status"]), models.Index(fields=["current_period_end"])]

    def __str__(self):
        return f"{self.tenant.tenant_code} :: {self.plan}"
