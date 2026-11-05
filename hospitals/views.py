from rest_framework import viewsets
from .models import Hospital, Location
from .serializers import HospitalSerializer, LocationSerializer
from users.permissions import IsAdminOrReadOnly


class HospitalViewSet(viewsets.ModelViewSet):
    queryset = Hospital.objects.all()
    serializer_class = HospitalSerializer
    permission_classes = [IsAdminOrReadOnly]


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.select_related('hospital')
    serializer_class = LocationSerializer
    permission_classes = [IsAdminOrReadOnly]