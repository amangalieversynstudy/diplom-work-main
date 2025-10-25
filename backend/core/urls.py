"""URL configuration for the backend project."""

from django.contrib import admin
from django.urls import include, path

from .health import healthz

urlpatterns = [
    path("healthz", healthz),
    path("admin/", admin.site.urls),
    path("api/", include("users.urls")),
    path("api/", include("users.urls_auth")),
    path("api/", include("users.urls_password")),
    path("api/", include("game.urls")),
]
