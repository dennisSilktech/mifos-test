from rest_framework.routers import DefaultRouter

from .views import DomainViewSet, TenantViewSet

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("domains", DomainViewSet, basename="domain")

urlpatterns = router.urls
