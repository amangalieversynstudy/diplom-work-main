"""Contract tests using Schemathesis against the live API (swagger.json).

Run preconditions:
- Backend is running locally (deploy-local) and exposes swagger.json on BASE_URL.
- BASE_URL env (default http://localhost:8000).

Usage:
    pytest -q diagnostics/contract/test_openapi_schemathesis.py

CI note:
- This test suite is disabled by default in CI to avoid network calls & extra deps.
    To enable, set the env var RUN_CONTRACT_TESTS=1 and ensure `schemathesis` is
    installed and the backend is reachable via BASE_URL.
"""

import os
import random
import string

import pytest

# Skip entire module unless explicitly enabled
if os.getenv("RUN_CONTRACT_TESTS") != "1":
    pytest.skip(
        "Skipping contract tests (set RUN_CONTRACT_TESTS=1 to enable)",
        allow_module_level=True,
    )

# Import schemathesis only when enabled; skip if not installed
schemathesis = pytest.importorskip("schemathesis")
from schemathesis import DataGenerationMethod  # noqa: E402

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
SCHEMA_URI = f"{BASE_URL.rstrip('/')}/swagger.json"

schema = schemathesis.from_uri(SCHEMA_URI, base_url=BASE_URL)


def _random_login():
    return "u_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


@pytest.fixture(scope="session")
def auth_headers(request):
    import requests

    username = os.getenv("API_USERNAME")
    password = os.getenv("API_PASSWORD")

    if not username or not password:
        # Try to register a random user and then login
        username = _random_login()
        password = "Passw0rd!" + _random_login()
        try:
            requests.post(
                f"{BASE_URL}/api/auth/register/",
                json={"username": username, "password": password},
                timeout=10,
            )
        except Exception:
            pass

    # obtain JWT
    r = requests.post(
        f"{BASE_URL}/api/auth/login/",
        json={"username": username, "password": password},
        timeout=10,
    )
    if r.ok and "access" in r.json():
        access = r.json()["access"]
        return {"Authorization": f"Bearer {access}"}
    # Fallback: no auth
    return {}


@schema.parametrize(endpoint="^/api/.*")
@pytest.mark.parametrize(
    "data_generation_method",
    [DataGenerationMethod.positive],
)
def test_api_contract(case, auth_headers, data_generation_method):
    # Attach auth if available
    if auth_headers:
        case.headers.update(auth_headers)
    # Execute and validate response against schema
    response = case.call()
    case.validate_response(response)
