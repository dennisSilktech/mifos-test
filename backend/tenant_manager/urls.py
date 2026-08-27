from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from tenants import views as tenant_views
from portal.views import TenantLoginView, TenantLogoutView


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    # tenant landing page (matches bare root on tenant hostnames)
    path("", tenant_views.landing, name="tenant-landing"),
    path("login/", TenantLoginView.as_view(), name="portal-login"),
    path("logout/", TenantLogoutView.as_view(), name="portal-logout"),
    path("portal/", include("portal.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("api/v1/health/", health, name="health"),
    path("api/v1/auth/", include("authentication.urls")),
    path("api/v1/", include("organizations.urls")),
    path("api/v1/", include("tenants.urls")),
    path("api/v1/", include("provisioning.urls")),
    path("api/v1/", include("subscriptions.urls")),
    path("api/v1/", include("audit.urls")),
    path("api/v1/", include("domains.urls")),
]