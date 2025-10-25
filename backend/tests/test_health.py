import pytest


def test_healthz_endpoint(client):
    """Ensure /healthz returns 200 and expected payload."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
