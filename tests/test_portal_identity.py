import base64
import json
import time
from uuid import NAMESPACE_URL, uuid5

import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

import portal


EXPECTED_ID = str(uuid5(NAMESPACE_URL, "urn:amz-portal:user:test-user"))
COOKIE_NAME = "amazon_portal_session"


def signed_session(payload, age=0):
    signer = TimestampSigner(portal.SESSION_SECRET)
    signer.get_timestamp = lambda: int(time.time()) - age
    value = base64.b64encode(json.dumps(payload).encode("utf-8"))
    return signer.sign(value).decode("utf-8")


def assert_rejected(response):
    assert response.status_code == 401
    assert response.json() == {"detail": "请先登录"}
    assert response.headers["cache-control"] == "no-store"


def test_two_browsers_receive_the_same_account_identity(client):
    identities = []
    with TestClient(portal.app, base_url="https://testserver") as second:
        for browser in (client, second):
            result = browser.post(
                "/api/auth/login",
                json={"username": "test-user", "password": "test-password"},
            )
            assert result.status_code == 200
            response = browser.get("/api/auth/user")
            assert response.status_code == 200
            assert response.json() == {"user_id": EXPECTED_ID}
            assert response.headers["cache-control"] == "no-store"
            assert browser.get("/api/auth/check").status_code == 204
            identities.append(response.json()["user_id"])
    assert identities == [EXPECTED_ID, EXPECTED_ID]


def test_anonymous_identity_headers_cannot_create_a_login(client):
    response = client.get(
        "/api/auth/user",
        headers={"X-User-ID": EXPECTED_ID, "X-Portal-User-ID": EXPECTED_ID},
    )
    assert_rejected(response)


def test_authenticated_identity_headers_cannot_replace_account(authenticated_client):
    response = authenticated_client.get(
        "/api/auth/user",
        headers={"X-User-ID": "another-account", "Authorization": "Bearer forged"},
    )
    assert response.status_code == 200
    assert response.json() == {"user_id": EXPECTED_ID}


@pytest.mark.parametrize("user_id", [None, "another-account", 42, []])
def test_missing_or_wrong_signed_identity_is_rejected(client, user_id):
    payload = {"authenticated": True}
    if user_id is not None:
        payload["user_id"] = user_id
    client.cookies.set(COOKIE_NAME, signed_session(payload))
    assert_rejected(client.get("/api/auth/user"))
    assert client.get("/api/auth/check").status_code == 401


@pytest.mark.parametrize("authenticated", [False, "true", 1, None])
def test_identity_requires_strict_authenticated_flag(client, authenticated):
    client.cookies.set(
        COOKIE_NAME,
        signed_session({"authenticated": authenticated, "user_id": EXPECTED_ID}),
    )
    assert_rejected(client.get("/api/auth/user"))
    assert client.get("/api/auth/check").status_code == 401


def test_tampered_signature_does_not_return_identity(client):
    cookie = signed_session({"authenticated": True, "user_id": EXPECTED_ID})
    data, timestamp, signature = cookie.rsplit(".", 2)
    signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    client.cookies.set(COOKIE_NAME, ".".join((data, timestamp, signature)))
    assert_rejected(client.get("/api/auth/user"))


def test_expired_session_does_not_return_identity(client):
    client.cookies.set(
        COOKIE_NAME,
        signed_session({"authenticated": True, "user_id": EXPECTED_ID}, age=43260),
    )
    assert_rejected(client.get("/api/auth/user"))


def test_logout_clears_identity(authenticated_client):
    assert authenticated_client.get("/api/auth/user").status_code == 200
    response = authenticated_client.post("/api/auth/logout")
    assert response.status_code == 200
    assert_rejected(authenticated_client.get("/api/auth/user"))
    assert authenticated_client.get("/api/auth/check").status_code == 401


def test_password_change_preserves_identity(client, monkeypatch):
    monkeypatch.setattr(portal, "LOGIN_PASSWORD", "changed-test-password")
    response = client.post(
        "/api/auth/login",
        json={"username": "test-user", "password": "changed-test-password"},
    )
    assert response.status_code == 200
    assert client.get("/api/auth/user").json() == {"user_id": EXPECTED_ID}
