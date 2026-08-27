from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView

from tenants import views as tenant_views
from portal.views import TenantLoginView, TenantLogoutView

from django.conf import settings
from django.conf.urls.static import static


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    # tenant landing page (matches bare root on tenant hostnames)
    path('', RedirectView.as_view(url='/portal/', permanent=False)),
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

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)