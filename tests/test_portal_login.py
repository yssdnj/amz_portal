import pytest


def test_logged_out_page_redirects_to_prefix_login(client):
    direct = client.get("/", follow_redirects=False)
    assert direct.status_code == 302
    assert direct.headers["location"] == "/login?next=/"

    prefixed = client.get(
        "/",
        headers={"X-Forwarded-Prefix": "/amazon"},
        follow_redirects=False,
    )
    assert prefixed.status_code == 302
    assert prefixed.headers["location"] == "/amazon/login?next=/amazon/"


@pytest.mark.parametrize("path", ["/api/status", "/api/services/ads/stop"])
def test_logged_out_apis_return_401(client, path):
    response = client.request("POST" if path.endswith("/stop") else "GET", path)
    assert response.status_code == 401


def test_valid_login_sets_hardened_session_cookie(client):
    response = client.post(
        "/api/auth/login",
        headers={"X-Forwarded-Prefix": "/amazon"},
        json={
            "username": "test-user",
            "password": "test-password",
            "next": "/amazon/products/",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"redirect": "/amazon/products/"}
    cookie = response.headers["set-cookie"]
    assert "amazon_portal_session=" in cookie
    lower_cookie = cookie.lower()
    assert "httponly" in lower_cookie
    assert "max-age=43200" in lower_cookie
    assert "path=/" in lower_cookie
    assert "samesite=lax" in lower_cookie
    assert "secure" in lower_cookie


def test_login_compares_both_credentials_with_compare_digest(client, monkeypatch):
    import portal

    calls = []
    real_compare = portal.secrets.compare_digest

    def compare(left, right):
        calls.append((left, right))
        return real_compare(left, right)

    monkeypatch.setattr(portal.secrets, "compare_digest", compare)
    response = client.post(
        "/api/auth/login",
        json={"username": "test-user", "password": "test-password", "next": "/"},
    )

    assert response.status_code == 200
    assert calls == [
        ("test-user", "test-user"),
        ("test-password", "test-password"),
    ]


def test_invalid_username_and_password_share_one_error(client):
    responses = [
        client.post(
            "/api/auth/login",
            json={"username": "wrong", "password": "test-password", "next": "/"},
        ),
        client.post(
            "/api/auth/login",
            json={"username": "test-user", "password": "wrong", "next": "/"},
        ),
    ]

    assert [response.status_code for response in responses] == [401, 401]
    assert responses[0].json() == responses[1].json()
    assert all("set-cookie" not in response.headers for response in responses)


def test_auth_check_and_logout_clear_the_session(client):
    login = client.post(
        "/api/auth/login",
        json={"username": "test-user", "password": "test-password", "next": "/"},
    )
    assert login.status_code == 200
    assert client.get("/api/auth/check").status_code == 204

    response = client.post(
        "/api/auth/logout",
        headers={"X-Forwarded-Prefix": "/amazon"},
    )

    assert response.status_code == 200
    assert response.json() == {"redirect": "/amazon/login"}
    assert "amazon_portal_session=null" in response.headers["set-cookie"]
    assert client.get("/api/auth/check").status_code == 401


@pytest.mark.parametrize(
    "next_path",
    [
        "https://evil.example/",
        "//evil.example/",
        "/stock/",
        "/amazon-elsewhere/",
        "amazon/products/",
        "\\\\evil.example\\share",
    ],
)
def test_login_rejects_nonlocal_or_out_of_prefix_next(client, next_path):
    response = client.post(
        "/api/auth/login",
        headers={"X-Forwarded-Prefix": "/amazon"},
        json={
            "username": "test-user",
            "password": "test-password",
            "next": next_path,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"redirect": "/amazon/"}


def test_login_page_uses_a_sanitized_next_path(client):
    response = client.get(
        "/login?next=https://evil.example/",
        headers={"X-Forwarded-Prefix": "/amazon"},
    )

    assert response.status_code == 200
    assert "https://evil.example/" not in response.text
    assert '"/amazon/"' in response.text
