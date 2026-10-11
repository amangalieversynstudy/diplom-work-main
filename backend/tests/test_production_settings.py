"""Production settings must refuse to load without explicit hosts."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def _load(extra):
    env = {k: v for k, v in os.environ.items() if k not in ("ALLOWED_HOSTS", "RAILWAY_PUBLIC_DOMAIN")}
    env.update(DJANGO_SETTINGS_MODULE="core.settings.production", DJANGO_SECRET_KEY="x" * 50)
    env.update(extra)
    code = "import django.conf as c; s=c.settings; print(s.ALLOWED_HOSTS, s.CSRF_TRUSTED_ORIGINS, s.SECURE_SSL_REDIRECT)"
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True)


def test_production_requires_allowed_hosts():
    r = _load({})
    assert r.returncode != 0
    assert "ALLOWED_HOSTS" in r.stderr


def test_production_rejects_wildcard():
    assert _load({"ALLOWED_HOSTS": "*"}).returncode != 0


def test_production_defaults():
    r = _load({"ALLOWED_HOSTS": "a.example.com", "RAILWAY_PUBLIC_DOMAIN": "b.up.railway.app"})
    assert r.returncode == 0, r.stderr
    assert "b.up.railway.app" in r.stdout and "[] True" in r.stdout
