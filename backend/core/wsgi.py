"""WSGI application entrypoint for the Django project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.production")
application = get_wsgi_application()
