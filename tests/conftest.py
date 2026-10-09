import os

import pytest
from fastapi.testclient import TestClient


os.environ["PORTAL_LOGIN_USERNAME"] = "test-user"
os.environ["PORTAL_LOGIN_PASSWORD"] = "test-password"
os.environ["PORTAL_EXTRA_USERS"] = "{}"
os.environ["PORTAL_SESSION_SECRET"] = "test-session-secret-at-least-32-characters"
os.environ["PORTAL_COOKIE_SECURE"] = "true"


@pytest.fixture
def client():
    import portal

    with TestClient(
        portal.app,
        base_url="https://testserver",
        client=("127.0.0.1", 12345),
    ) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "test-user", "password": "test-password", "next": "/"},
    )
    assert response.status_code == 200
    return client
