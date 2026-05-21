"""ASGI middlewares for the project.

JWTAuthMiddleware authenticates a WebSocket connection by reading a
SimpleJWT access token from the query string (``?token=<jwt>``) and
populating ``scope['user']``. Anonymous connections are still allowed
to pass through — it is the consumer's job to ``close()`` them with
an appropriate code (e.g. 4401 Unauthorized).
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


@database_sync_to_async
def _resolve_user(token_str: str):
    """Decode the JWT and fetch the User. Return AnonymousUser on any failure."""
    try:
        token = AccessToken(token_str)
        return User.objects.get(id=token["user_id"])
    except (TokenError, User.DoesNotExist, KeyError, ValueError):
        return AnonymousUser()


class JWTAuthMiddleware:
    """Populate scope['user'] from a ``?token=`` query-string JWT."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get("token", [])
        if token_list and token_list[0]:
            scope["user"] = await _resolve_user(token_list[0])
        else:
            scope["user"] = AnonymousUser()
        return await self.inner(scope, receive, send)
