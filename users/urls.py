from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import DoctorViewSet, PatientViewSet, MonitoringSessionViewSet

router = SimpleRouter()
router.register('doctors', DoctorViewSet)
router.register('patients', PatientViewSet, basename='patient')
router.register("monitoring-sessions", MonitoringSessionViewSet, basename="monitoring-session")

urlpatterns = [
    path('token/', TokenObtainPairView.as_view()),
    path('token/refresh/', TokenRefreshView.as_view()),
]

urlpatterns += router.urls