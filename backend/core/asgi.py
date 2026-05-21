"""ASGI application entrypoint for the Django project.

Serves both HTTP (Django) and WebSocket (Channels) protocols.
HTTP is delegated to the standard Django ASGI app; WebSocket connections
are JWT-authenticated and routed via ``game.routing.websocket_urlpatterns``.
"""

import os

from django.core.asgi import get_asgi_application

# Initialise Django settings BEFORE importing channels/routes, so model
# imports inside consumers see a fully-configured Django.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.production")
django_asgi_app = get_asgi_application()

# These imports must happen after Django is initialised.
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from core.middleware import JWTAuthMiddleware  # noqa: E402
from game.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
    ),
})
