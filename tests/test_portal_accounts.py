import pytest
from fastapi.testclient import TestClient

import portal
from test_portal_identity import COOKIE_NAME, EXPECTED_ID, signed_session


@pytest.mark.parametrize("value", [None, "", "{}"])
def test_optional_extra_users(value):
    assert portal.load_extra_users(value, "test-user") == {}


def test_extra_users_keep_exact_names():
    assert portal.load_extra_users('{"Other":"fake-secret"," spaced ":"fake"}', "test-user") == {
        "Other": "fake-secret", " spaced ": "fake"
    }


@pytest.mark.parametrize("value", [
    '{', '[]', 'null', '42', '"fake-secret"',
    '{"":"fake-secret"}', '{"other":""}', '{"other":null}',
    '{"other":42}', '{"other":false}', '{"other":[]}',
    '{"other":"fake-secret","other":"another-fake"}',
    '{"test-user":"fake-secret"}',
])
def test_invalid_extra_users_do_not_disclose_values(value):
    with pytest.raises(RuntimeError) as error:
        portal.load_extra_users(value, "test-user")
    assert str(error.value) == "Invalid PORTAL_EXTRA_USERS configuration"
    assert error.value.__suppress_context__ is True


@pytest.fixture
def extras(monkeypatch):
    monkeypatch.setattr(portal, "EXTRA_USERS", {"other-user": "other-password"})


def test_accounts_have_distinct_stable_ids(client, extras):
    ids = []
    for username, password in [("test-user", "test-password"), ("other-user", "other-password"), ("other-user", "other-password")]:
        with TestClient(portal.app, base_url="https://testserver") as browser:
            assert browser.post("/api/auth/login", json={"username": username, "password": password}).status_code == 200
            result = browser.get("/api/auth/user")
            assert result.json() == {"user_id": portal.user_id_for(username)}
            assert result.headers["cache-control"] == "no-store"
            assert browser.get("/api/auth/check").status_code == 204
            home = browser.get("/")
            assert home.status_code == 200
            assert home.headers["cache-control"] == "no-store"
            assert f'title="{username}"' in home.text
            assert password not in home.text
            assert result.json()["user_id"] not in home.text
            ids.append(result.json()["user_id"])
    assert ids[0] == EXPECTED_ID
    assert ids[0] != ids[1] == ids[2]


@pytest.mark.parametrize("username,password", [
    ("other-user", "test-password"), ("test-user", "other-password"),
    ("unknown", "other-password"), ("other-user", "wrong"), ("未知", "错误"),
])
def test_wrong_credentials_share_generic_error(client, extras, username, password):
    result = client.post("/api/auth/login", json={"username": username, "password": password})
    assert result.status_code == 401
    assert result.json() == {"detail": "账号或密码不正确"}


def test_both_comparisons_for_all_accounts(client, extras, monkeypatch):
    compare = portal.secrets.compare_digest
    calls = []
    def recording(left, right):
        calls.append((left, right))
        return compare(left, right)
    monkeypatch.setattr(portal.secrets, "compare_digest", recording)
    assert client.post("/api/auth/login", json={"username": "other-user", "password": "other-password"}).status_code == 200
    assert calls == [(b"other-user", b"test-user"), (b"other-password", b"test-password"),
                     (b"other-user", b"other-user"), (b"other-password", b"other-password")]


def test_removed_account_rejected_everywhere(client, extras, monkeypatch):
    client.cookies.set(COOKIE_NAME, signed_session({"authenticated": True, "user_id": portal.user_id_for("other-user")}))
    assert client.get("/api/auth/check").status_code == 204
    monkeypatch.setattr(portal, "EXTRA_USERS", {})
    for path in ["/api/auth/user", "/api/auth/check", "/api/status"]:
        assert client.get(path).status_code == 401
    assert client.post("/api/services/ads/start", headers={"X-Portal-Control": "1"}).status_code == 401
    assert client.get("/", follow_redirects=False).status_code == 302


def test_existing_primary_cookie_survives(client, extras):
    client.cookies.set(COOKIE_NAME, signed_session({"authenticated": True, "user_id": EXPECTED_ID}))
    assert client.get("/api/auth/check").status_code == 204
    assert client.get("/api/auth/user").json() == {"user_id": EXPECTED_ID}


def test_username_is_escaped():
    result = portal.render_portal_page('<img src=x onerror=alert(1)>"&')
    assert '<img src=x onerror=alert(1)>' not in result
    assert '&lt;img src=x onerror=alert(1)&gt;&quot;&amp;' in result


def test_extra_headers_cannot_switch_identity(client, extras):
    client.post("/api/auth/login", json={"username": "other-user", "password": "other-password"})
    result = client.get("/api/auth/user", headers={"X-User-ID": EXPECTED_ID, "X-Portal-User-ID": EXPECTED_ID})
    assert result.json() == {"user_id": portal.user_id_for("other-user")}
