"""Simple health endpoint for the Django backend.

This exposes a lightweight endpoint used by docker / orchestrators
to check that the application is up and can respond to HTTP requests.
"""

from django.http import JsonResponse


def healthz(request):
    """Return a minimal OK response for health checks.

    This handler intentionally keeps dependencies minimal.
    """
    return JsonResponse({"status": "ok"})
