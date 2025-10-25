"""URL routes for game API viewsets."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LocationViewSet, MissionViewSet, ProgressViewSet

router = DefaultRouter()
router.register(r"locations", LocationViewSet)
router.register(r"missions", MissionViewSet)
router.register(r"progress", ProgressViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
