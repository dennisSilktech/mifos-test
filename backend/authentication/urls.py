from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import (
    APIKeyViewSet,
    LoginSessionViewSet,
    LoginView,
    LogoutAllView,
    MFAConfirmView,
    MFAEnrollView,
    RefreshView,
)

router = DefaultRouter()
router.register("sessions", LoginSessionViewSet, basename="login-session")
router.register("api-keys", APIKeyViewSet, basename="api-key")

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout-all/", LogoutAllView.as_view(), name="auth-logout-all"),
    path("mfa/enroll/", MFAEnrollView.as_view(), name="auth-mfa-enroll"),
    path("mfa/confirm/", MFAConfirmView.as_view(), name="auth-mfa-confirm"),
] + router.urls
