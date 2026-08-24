import uuid

from django.db import models


class Organization(models.Model):
    class OrgType(models.TextChoices):
        SACCO = "SACCO", "SACCO"
        CHAMA = "CHAMA", "Chama"
        MFI = "MFI", "Microfinance Institution"
        LENDER = "LENDER", "Lending Organization"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_name = models.CharField(max_length=255)
    trading_name = models.CharField(max_length=255, blank=True)
    org_type = models.CharField(max_length=32, choices=OrgType.choices)
    registration_number = models.CharField(max_length=100, unique=True)
    country = models.CharField(max_length=2, default="KE")
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    kyc_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["org_type"]), models.Index(fields=["country"])]

    def __str__(self):
        return self.trading_name or self.legal_name
