from django.contrib.auth.backends import ModelBackend

from .models import User


class PlatformStaffBackend(ModelBackend):
    """
    Used only by the session-based staff dashboard login (dashboard app).
    Scoped to tenant=None so it can never collide with a tenant user who
    happens to share an email with platform staff. The JWT-based tenant
    login path (authentication.services.AuthenticationService) does its
    own tenant-scoped lookup and never goes through Django's authenticate()
    /AUTHENTICATION_BACKENDS at all, so this backend has no effect on it.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        try:
            user = User.objects.get(tenant__isnull=True, email__iexact=username)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
