"""The client's address, the same way for DRF throttles and django-ratelimit.

With ``REST_FRAMEWORK["NUM_PROXIES"]`` set (production: the Railway edge is one hop) it is the right-most
X-Forwarded-For entry that the edge appended, which a client cannot forge; without it, REMOTE_ADDR.
"""

from rest_framework.throttling import BaseThrottle


def client_ip(request):
    """``RATELIMIT_IP_META_KEY`` callable: django-ratelimit's ``key="ip"`` reads the address through it."""
    return BaseThrottle().get_ident(request)
