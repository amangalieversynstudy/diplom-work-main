"""API viewsets for game models."""

from rest_framework import viewsets

from .models import Location, Mission, Progress
from .serializers import LocationSerializer, MissionSerializer, ProgressSerializer


class LocationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing locations."""

    queryset = Location.objects.all().order_by("order")
    serializer_class = LocationSerializer


class MissionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing missions."""

    queryset = Mission.objects.all().order_by("order")
    serializer_class = MissionSerializer


class ProgressViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user progress on missions."""

    queryset = Progress.objects.all()
    serializer_class = ProgressSerializer
