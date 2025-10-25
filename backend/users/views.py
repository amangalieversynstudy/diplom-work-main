"""API viewsets for user management."""

from rest_framework import viewsets

from .models import User
from .serializers import UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for listing and modifying users."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
