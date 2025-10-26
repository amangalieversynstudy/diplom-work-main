"""URL routes for user viewsets and endpoints."""

from django.urls import include, path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from .views import UserViewSet


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile_view(request):
    profile = request.user.profile
    return Response(
        {
            "id": request.user.id,
            "username": request.user.username,
            "display_name": request.user.display_name,
            "xp": profile.xp,
            "level": profile.level,
        }
    )


router = DefaultRouter()
router.register(r"users", UserViewSet)


urlpatterns = [
    path("", include(router.urls)),
    path("profile", profile_view, name="profile"),
]
