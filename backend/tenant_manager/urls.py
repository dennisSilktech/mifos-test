from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from tenants import views as tenant_views


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Root entry point: dynamically routes tenants to /portal/ or serves main site
    path("", tenant_views.landing, name="tenant-landing"),
    
    # App inclusions (handles /portal/login/, /portal/logout/, /portal/, etc.)
    path("portal/", include("portal.urls")),
    path("dashboard/", include("dashboard.urls")),
    
    # API Endpoints
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