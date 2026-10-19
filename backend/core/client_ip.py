"""The client's address and per-account keys, the same way for DRF throttles and django-ratelimit.

With ``REST_FRAMEWORK["NUM_PROXIES"]`` set (production: the Railway edge is one hop) the address is the right-most
X-Forwarded-For entry that the edge appended, which a client cannot forge. Without it (local runs, tests) it is
REMOTE_ADDR: a client-sent X-Forwarded-For is never trusted.
"""

from rest_framework.settings import api_settings
from rest_framework.throttling import BaseThrottle


def client_ip(request):
    """``RATELIMIT_IP_META_KEY`` callable: django-ratelimit's ``key="ip"`` reads the address through it."""
    if api_settings.NUM_PROXIES is None:
        return request.META.get("REMOTE_ADDR", "")
    return BaseThrottle().get_ident(request)


def _field(request, *names):
    """A field of the request body: JSON (DRF ``request.data``) or a form (``request.POST``)."""
    data = getattr(request, "data", None)
    if data is None or not hasattr(data, "get"):
        data = request.POST
    for name in names:
        value = data.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def login_key(group, request):
    """Login attempts per account name (falls back to the address when the body has none).

    django-ratelimit's ``post:username`` reads only form fields; the site sends JSON, so that key was one shared
    counter for every login on the platform."""
    name = _field(request, "username", "email")
    return f"login:{name}" if name else f"ip:{client_ip(request)}"


def reset_key(group, request):
    """Password-reset requests per e-mail address (falls back to the client address)."""
    email = _field(request, "email")
    return f"reset:{email}" if email else f"ip:{client_ip(request)}"
