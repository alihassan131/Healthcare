from rest_framework.routers import SimpleRouter
from .views import HospitalViewSet, LocationViewSet

router = SimpleRouter()
router.register('hospitals', HospitalViewSet)
router.register('locations', LocationViewSet)

urlpatterns = router.urls