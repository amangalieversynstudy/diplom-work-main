"""Unit tests for health endpoint.

This module contains a minimal test that verifies the `/healthz`
endpoint returns a successful status and expected JSON payload.
"""

import pytest


def test_healthz_endpoint(client):
    """Ensure /healthz returns 200 and expected payload."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
