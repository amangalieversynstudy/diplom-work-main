import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_register_login_logout():
    client = APIClient()
    register_url = '/api/auth/register/'
    login_url = '/api/auth/login/'
    logout_url = '/api/auth/logout/'

    # Register
    resp = client.post(register_url, {'username': 'u1', 'password': 'p1'})
    assert resp.status_code == 201

    # Login
    resp = client.post(login_url, {'username': 'u1', 'password': 'p1'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'access' in data and 'refresh' in data

    # Logout (blacklist refresh)
    refresh = data['refresh']
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {data['access']}")
    resp = client.post(logout_url, {'refresh': refresh})
    assert resp.status_code in (205, 200)
