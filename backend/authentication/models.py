import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_platform_staff", True)
        extra_fields.setdefault("role", User.Role.SUPER_ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Control-plane user. tenant=None means platform staff (admin.<domain>)."""

    class Role(models.TextChoices):
        # platform roles
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        SUPPORT = "SUPPORT", "Support"
        AUDITOR = "AUDITOR", "Auditor"
        FINANCE = "FINANCE", "Finance"
        # tenant roles
        CEO = "CEO", "CEO / Org Admin"
        BRANCH_MANAGER = "BRANCH_MANAGER", "Branch Manager"
        LOAN_OFFICER = "LOAN_OFFICER", "Loan Officer"
        CASHIER = "CASHIER", "Cashier"
        MEMBER = "MEMBER", "Member"

    PLATFORM_ROLES = {Role.SUPER_ADMIN, Role.SUPPORT, Role.AUDITOR, Role.FINANCE}
    TENANT_ROLES = {Role.CEO, Role.BRANCH_MANAGER, Role.LOAN_OFFICER, Role.CASHIER, Role.MEMBER}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="users"
    )
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.MEMBER)
    branch_id = models.UUIDField(null=True, blank=True)  # scoping for Branch Manager/Loan Officer/Cashier

    is_platform_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)

    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_encrypted = models.BinaryField(null=True, blank=True)

    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "role"]),
            models.Index(fields=["email"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "email"], name="uniq_email_per_tenant"),
            models.UniqueConstraint(
                fields=["email"], condition=models.Q(tenant__isnull=True),
                name="uniq_email_for_platform_staff",
            ),
        ]

    def __str__(self):
        return self.email

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_failed_login(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def register_successful_login(self, ip_address=None):
        self.failed_login_attempts = 0
        self.locked_until = None
        if ip_address:
            self.last_login_ip = ip_address
        self.save(update_fields=["failed_login_attempts", "locked_until", "last_login_ip"])


class APIKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=100)
    key_prefix = models.CharField(max_length=12, unique=True)
    key_hash = models.CharField(max_length=128)
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["key_prefix"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"


class LoginSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    refresh_token_hash = models.CharField(max_length=128)
    device_fingerprint = models.CharField(max_length=128, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    is_revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_revoked"]),
            models.Index(fields=["expires_at"]),
        ]

    def revoke(self):
        self.is_revoked = True
        self.save(update_fields=["is_revoked"])
