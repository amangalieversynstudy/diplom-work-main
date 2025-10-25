from rest_framework import viewsets
from .models import Location, Mission, Progress
from .serializers import LocationSerializer, MissionSerializer, ProgressSerializer

class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all().order_by('order')
    serializer_class = LocationSerializer

class MissionViewSet(viewsets.ModelViewSet):
    queryset = Mission.objects.all().order_by('order')
    serializer_class = MissionSerializer

class ProgressViewSet(viewsets.ModelViewSet):
    queryset = Progress.objects.all()
    serializer_class = ProgressSerializer
