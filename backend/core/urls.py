"""URL configuration for the backend project."""

from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from .health import healthz

schema_view = get_schema_view(
    openapi.Info(
        title="RPG API",
        default_version="v1",
        description="API документация",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("healthz", healthz),
    path("admin/", admin.site.urls),
    # Swagger / OpenAPI
    path("swagger.json", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path(
        "docs/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path("api/", include("users.urls")),
    path("api/", include("users.urls_auth")),
    path("api/", include("users.urls_password")),
    path("api/", include("game.urls")),
]
