import hashlib

import pyotp
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from audit.services import AuditService
from tenant_manager.crypto import decrypt_secret, encrypt_secret

from .models import LoginSession, User


class AuthenticationError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


class AuthenticationService:
    """Handles credential verification, lockout, MFA, and session issuance."""

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @classmethod
    def authenticate(cls, *, email, password, tenant, ip_address, user_agent,
                      device_fingerprint="", mfa_code=None):
        try:
            user = User.objects.get(tenant=tenant, email__iexact=email)
        except User.DoesNotExist:
            raise AuthenticationError("INVALID_CREDENTIALS", "Invalid email or password.")

        if user.is_locked:
            raise AuthenticationError("ACCOUNT_LOCKED", "Account temporarily locked. Try again later.")

        if not user.check_password(password):
            user.register_failed_login()
            AuditService.log(
                actor=None, tenant=tenant, action="LOGIN_FAILED", actor_ip=ip_address,
                target_type="User", target_id=str(user.id),
            )
            raise AuthenticationError("INVALID_CREDENTIALS", "Invalid email or password.")

        if user.mfa_enabled:
            if not mfa_code or not cls.verify_mfa(user, mfa_code):
                raise AuthenticationError("MFA_REQUIRED", "A valid MFA code is required.")

        user.register_successful_login(ip_address=ip_address)
        AuditService.log(
            actor=user, tenant=tenant, action="LOGIN_SUCCESS", actor_ip=ip_address,
            target_type="User", target_id=str(user.id),
        )
        return cls.issue_session(user, ip_address, user_agent, device_fingerprint)

    @classmethod
    def issue_session(cls, user, ip_address, user_agent, device_fingerprint=""):
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
        refresh["role"] = user.role

        LoginSession.objects.create(
            user=user,
            refresh_token_hash=cls._hash_token(str(refresh)),
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=timezone.now() + refresh.lifetime,
        )
        return {"access": str(refresh.access_token), "refresh": str(refresh)}

    @classmethod
    def rotate_refresh_token(cls, raw_refresh_token, ip_address, user_agent):
        token_hash = cls._hash_token(raw_refresh_token)
        session = LoginSession.objects.filter(refresh_token_hash=token_hash).first()

        if session is None or session.is_revoked:
            # Reuse of a revoked/unknown token => possible theft. Nuke all sessions for safety.
            if session:
                cls.revoke_all_sessions(session.user)
                AuditService.log(
                    actor=session.user, tenant=session.user.tenant, action="REFRESH_TOKEN_REUSE_DETECTED",
                    actor_ip=ip_address, target_type="User", target_id=str(session.user.id),
                )
            raise AuthenticationError("TOKEN_INVALID", "Refresh token is invalid or has been revoked.")

        try:
            old_token = RefreshToken(raw_refresh_token)
            old_token.blacklist()
        except TokenError:
            pass

        session.revoke()
        return cls.issue_session(session.user, ip_address, user_agent, session.device_fingerprint)

    @staticmethod
    def revoke_all_sessions(user):
        LoginSession.objects.filter(user=user, is_revoked=False).update(is_revoked=True)

    # -- MFA -----------------------------------------------------------
    @staticmethod
    def enroll_mfa(user) -> str:
        secret = pyotp.random_base32()
        user.mfa_secret_encrypted = encrypt_secret(secret)
        user.save(update_fields=["mfa_secret_encrypted"])
        return pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Banking SaaS")

    @staticmethod
    def verify_mfa(user, code: str) -> bool:
        if not user.mfa_secret_encrypted:
            return False
        secret = decrypt_secret(user.mfa_secret_encrypted)
        return pyotp.TOTP(secret).verify(code, valid_window=1)

    @staticmethod
    def confirm_mfa_enrollment(user, code: str) -> bool:
        if AuthenticationService.verify_mfa(user, code):
            user.mfa_enabled = True
            user.save(update_fields=["mfa_enabled"])
            return True
        return False
