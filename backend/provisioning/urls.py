from rest_framework.routers import DefaultRouter

from .views import ProvisionJobViewSet

router = DefaultRouter()
router.register("provision-jobs", ProvisionJobViewSet, basename="provision-job")

urlpatterns = router.urls
