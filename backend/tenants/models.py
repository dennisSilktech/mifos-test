import uuid

from django.db import models


class Tenant(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROVISIONING = "PROVISIONING", "Provisioning"
        INITIALIZING = "INITIALIZING", "Initializing"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"
        SUSPENDED = "SUSPENDED", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="tenants"
    )
    tenant_code = models.SlugField(max_length=32, unique=True)
    db_name = models.CharField(max_length=63, unique=True)
    db_user = models.CharField(max_length=63, blank=True)
    db_host = models.CharField(max_length=255, default="localhost")
    db_port = models.PositiveIntegerField(default=5432)
    fineract_tenant_identifier = models.CharField(max_length=63, unique=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    is_active = models.BooleanField(default=False)

    provisioned_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["tenant_code"]),
        ]

    def __str__(self):
        return self.tenant_code

    @property
    def primary_domain(self):
        return self.domains.filter(is_primary=True).first()


class Domain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="domains")
    hostname = models.CharField(max_length=255, unique=True)
    is_primary = models.BooleanField(default=True)
    is_custom = models.BooleanField(default=False)
    ssl_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["hostname"])]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant"],
                condition=models.Q(is_primary=True),
                name="uniq_primary_domain_per_tenant",
            )
        ]

    def __str__(self):
        return self.hostname


class EncryptedCredential(models.Model):
    """Per-tenant Postgres role password, envelope-encrypted (see tenant_manager.crypto)."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="credential")
    db_password_encrypted = models.BinaryField()
    updated_at = models.DateTimeField(auto_now=True)

    def set_password(self, raw: str):
        from tenant_manager.crypto import encrypt_secret

        self.db_password_encrypted = encrypt_secret(raw)

    def get_password(self) -> str:
        from tenant_manager.crypto import decrypt_secret

        return decrypt_secret(self.db_password_encrypted)
