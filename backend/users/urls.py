"""URL routes for user viewsets and endpoints."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProfileMeView, UserViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet)


urlpatterns = [
    path("", include(router.urls)),
    path("profile", ProfileMeView.as_view(), name="profile"),
    path("profile/me/", ProfileMeView.as_view(), name="profile-me"),
]
