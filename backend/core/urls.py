"""URL configuration for the backend project."""

from django.contrib import admin
from django.urls import include, path
from django_ratelimit.decorators import ratelimit
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

# The admin's own login form had no limit at all (the API login has one): per address and per account name.
_admin_login = ratelimit(key="ip", rate="20/m", method="POST", block=True)(
    ratelimit(key="core.client_ip.login_key", rate="10/m", method="POST", block=True)(admin.site.login)
)

urlpatterns = [
    path("healthz", healthz),
    path("admin/login/", _admin_login),
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
