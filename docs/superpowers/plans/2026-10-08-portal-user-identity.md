# Portal User Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the verified portal account as a stable user ID for SP preference storage without changing the browser login flow.

**Architecture:** The portal adds its configured account ID to the signed session only after successful credential validation. SP sends the original browser Cookie to a fixed loopback portal endpoint and trusts only its validated JSON response. Existing Nginx routes and auth checks remain compatible.

**Tech Stack:** Python, FastAPI, Starlette SessionMiddleware, standard-library UUID5, itsdangerous, pytest, HTTPX TestClient, Uvicorn.

**Spec:** `D:/python/amz_portal/docs/superpowers/specs/2026-10-08-portal-user-identity-design.md`

## Global Constraints

- Account ID formula: `str(uuid5(NAMESPACE_URL, "urn:amz-portal:user:" + LOGIN_USERNAME))`.
- New endpoint: `GET /api/auth/user`; success 200 with only `user_id`; invalid identity 401.
- Set `Cache-Control: no-store` for both success and failure.
- Preserve `/api/auth/check` 204/401, session Cookie name, Path, lifetime and security attributes.
- Legacy authenticated sessions without user_id continue passing the original check, but cannot resolve identity until login.
- Ignore client identity headers; do not expose credentials or signing keys.
- No new dependencies, multi-user system, preference database or SP code changes.
- No changes to Nginx, production credentials, secrets, startup scripts or other projects.
- Do not restart the current portal, deploy, commit or push automatically.
- Preserve the unrelated untracked `windows_startup.ps1`.

## Review Focus

- A valid legacy Cookie lacks user_id: identity must fail while the original auth check remains compatible.
- A copied Cookie has an edited signature or is older than 12 hours: it must not return an identity.
- A signed session contains a different user_id or false authenticated flag: it must fail identity resolution.
- A request contains forged identity headers: it must neither create a login nor replace a verified identity.
- A password changes or two browsers log in separately: the verified account ID must remain stable.

---

### Task 1: Implement and Test the Identity Contract

**Files:**
- Modify: `D:/python/amz_portal/portal.py` (imports, settings, login, new endpoint after auth_check).
- Create: `D:/python/amz_portal/tests/test_portal_identity.py`.
- Modify: `D:/python/amz_portal/README.md` (identity integration section after portal login section).

**Interfaces:**
- Consumes: `LOGIN_USERNAME`, `SESSION_SECRET`, `request.session`, existing `LoginRequest` and login routes.
- Produces: `LOGIN_USER_ID: str`, `current_user(request: Request) -> Response` at `/api/auth/user`.
- Identity response: `200 {"user_id": LOGIN_USER_ID}` or `401 {"detail": "请先登录"}`, with no-store.

- [x] **Step 1: Create the complete contract tests below.**

```python
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
    assert client.get("/api/auth/check").status_code == 204


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
```

- [x] **Step 2: Run tests before implementation and confirm failure is caused by the missing endpoint.**

Run from `D:/python/amz_portal`:

`python -m pytest tests/test_portal_identity.py -q -p no:cacheprovider --basetemp .test-runs/identity-red`

Expected: new identity tests fail with 404 instead of expected 200/401. Existing login test credentials are supplied only by conftest.

- [x] **Step 3: Apply the production code below.**

Add imports:

```python
from fastapi.responses import JSONResponse
from uuid import NAMESPACE_URL, uuid5
```

After reading `LOGIN_USERNAME`, initialize:

```python
LOGIN_USER_ID = str(uuid5(NAMESPACE_URL, "urn:amz-portal:user:" + LOGIN_USERNAME))
```

After setting authenticated in the successful login handler, add:

```python
request.session["user_id"] = LOGIN_USER_ID
```

After `auth_check`, add the endpoint without changing auth_check:

```python
@app.get("/api/auth/user")
def current_user(request: Request) -> Response:
    headers = {"Cache-Control": "no-store"}
    if (
        request.session.get("authenticated") is not True
        or request.session.get("user_id") != LOGIN_USER_ID
    ):
        return JSONResponse(
            {"detail": "请先登录"}, status_code=401, headers=headers
        )
    return JSONResponse({"user_id": LOGIN_USER_ID}, headers=headers)
```

- [x] **Step 4: Add the following exact README section.**

```markdown
### 后续项目的用户身份校验

后续项目后端可向固定地址 `http://127.0.0.1:5000/api/auth/user` 发送 GET，并携带浏览器原请求的 Cookie。有效登录返回 `200` 和仅含字符串 `user_id` 的 JSON；未登录、无效签名、过期、缺少身份或身份不匹配返回 `401`。响应设置 `Cache-Control: no-store`。

用户 ID 来自已验证的配置账号，与密码、浏览器和会话密钥无关；修改账号名称会产生新的 ID。旧版本登录状态需重新登录一次才能获取身份。原 `/api/auth/check` 的 `204/401` 约定不变。

调用地址必须由后续项目服务端固定配置，不能由前端请求指定。后续项目只信任门户成功校验后的 `user_id`，不信任客户端身份头，也不共享门户签名密钥。Cookie 不写入日志；不缓存其他用户的身份，也不向浏览器转发身份接口返回的 Set-Cookie。校验超时、连接失败或响应格式不正确时，不得保存账户偏好。

通过 HTTPS 网关访问 `/amazon/official-sp/` 时，门户 Cookie 的 `/` 或 `/amazon/` Path 均覆盖 SP 路由，浏览器会自动携带 Cookie，前端无需读取它。直连 HTTP `127.0.0.1:8015` 通常没有适用的门户 Secure Cookie，未验证身份时只允许临时调整，不保存账户偏好。跨主机部署需另行配置受保护的身份校验传输。

退出登录清除浏览器 Cookie。本项目继续使用原有签名会话，不提供复制保存的旧 Cookie 的服务端即时撤销。
```

- [x] **Step 5: Run focused and existing tests.**

Run:

`python -m pytest tests/test_portal_identity.py tests/test_portal_login.py tests/test_amazon_nginx_config.py -q -p no:cacheprovider --basetemp .test-runs/identity-focused`

Expected: all pass, including unchanged Cookie attributes and auth check compatibility.

Run:

`python -m pytest tests -q -p no:cacheprovider --basetemp .test-runs/identity-all`

Expected: all existing and new tests pass. Report any warning without claiming it was fixed.

- [x] **Step 6: Review the task against the spec and code quality.**

Confirm user_id is written only after both credential checks, no extra response fields, no-store on 401, exact strict True check, no identity-header lookup, no changes to auth_check or Cookie settings, no production credentials in tests, and no Nginx or other project modifications. Do not commit automatically.

### Task 2: Verify an Actual Isolated Runtime and Deliver the Contract

**Files:**
- Create temporary verification script: `D:/python/amz_portal/.test-runs/check_identity_runtime.py` (ignored; never commit).
- Update task checkboxes in this plan as work completes.

**Interfaces:**
- Consumes: Task 1 `/api/auth/login`, `/api/auth/user`, `/api/auth/check`, `/api/auth/logout`.
- Produces: evidence of actual Uvicorn requests using two independently issued session Cookies, and the final SP integration contract.

- [x] **Step 1: Create the complete runtime verifier below.**

```python
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import NAMESPACE_URL, uuid5


ROOT = Path(__file__).resolve().parents[1]
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]

env = dict(os.environ)
env.update(
    PORTAL_LOGIN_USERNAME="identity-runtime-user",
    PORTAL_LOGIN_PASSWORD="identity-runtime-password",
    PORTAL_SESSION_SECRET="identity-runtime-secret-not-for-production",
    PORTAL_COOKIE_SECURE="true",
)
expected_id = str(uuid5(NAMESPACE_URL, "urn:amz-portal:user:identity-runtime-user"))


def request(method, path, cookie=None, payload=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    supplied = dict(headers or {})
    if cookie:
        supplied["Cookie"] = cookie
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        supplied["Content-Type"] = "application/json"
    connection.request(method, path, body=body, headers=supplied)
    response = connection.getresponse()
    data = response.read()
    result = (
        response.status,
        dict(response.getheaders()),
        json.loads(data) if data else None,
    )
    connection.close()
    return result


with (ROOT / ".test-runs" / "identity-runtime.log").open("w") as log:
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "portal:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 15
        while True:
            if process.poll() is not None:
                raise RuntimeError("Isolated portal exited; inspect identity-runtime.log")
            try:
                assert request("GET", "/api/auth/check")[0] == 401
                break
            except (OSError, http.client.HTTPException):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Isolated portal did not become ready")
                time.sleep(0.1)

        anonymous = request("GET", "/api/auth/user", headers={"X-User-ID": expected_id})
        assert anonymous[0] == 401
        assert anonymous[1]["cache-control"] == "no-store"
        cookies = []
        for _ in range(2):
            login = request(
                "POST", "/api/auth/login",
                payload={"username": env["PORTAL_LOGIN_USERNAME"], "password": env["PORTAL_LOGIN_PASSWORD"]},
            )
            assert login[0] == 200
            cookie = login[1]["set-cookie"].split(";", 1)[0]
            attributes = login[1]["set-cookie"].lower()
            assert "httponly" in attributes and "secure" in attributes and "path=/" in attributes
            identity = request("GET", "/api/auth/user", cookie, headers={"X-User-ID": "another-account"})
            assert identity[0] == 200 and identity[2] == {"user_id": expected_id}
            assert identity[1]["cache-control"] == "no-store"
            assert request("GET", "/api/auth/check", cookie)[0] == 204
            cookies.append(cookie)
        assert request("GET", "/api/auth/user", "amazon_portal_session=invalid")[0] == 401
        logout = request("POST", "/api/auth/logout", cookies[0])
        assert logout[0] == 200
        cleared_cookie = logout[1]["set-cookie"].split(";", 1)[0]
        assert request("GET", "/api/auth/user", cleared_cookie)[0] == 401
        assert request("GET", "/api/auth/check", cleared_cookie)[0] == 401
        assert request("GET", "/api/auth/user", cookies[1])[0] == 200
        print("identity_runtime=passed; two_sessions=stable; forged_headers=ignored; invalid_and_logged_out=401; auth_check=compatible")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
```

The verifier explicitly forwards Cookie over HTTP to the loopback API, just like the SP backend; it does not simulate a browser sending a Secure Cookie to HTTP. The production portal and Nginx remain untouched.

- [x] **Step 2: Run the real runtime verification.**

Run: `python .test-runs/check_identity_runtime.py`

Expected: `identity_runtime=passed; two_sessions=stable; forged_headers=ignored; invalid_and_logged_out=401; auth_check=compatible` and exit 0. The verifier must terminate its own child process before finishing.

- [x] **Step 3: Perform final review and deliver the integration contract.**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors; changes only in planned source/tests/docs plus pre-existing untracked startup script. Explicitly state that the endpoint is implemented in source and verified in an isolated instance, but the running port 5000 instance must be restarted before SP can use it. Do not claim deployed status.

Final handoff must specify fixed endpoint, forwarded Cookie, 200 user_id/401 contract, ignored identity headers, no cache/secret sharing, old-session re-login and 8015 temporary-only behavior. Do not send messages to another task without human authorization in this chat.

## Execution Selection

The plan is ready for user review. This is one small authentication change plus isolated verification; Inline/Native execution is recommended because all work depends on the same existing login flow. Subagent-driven execution remains available if selected and supported by the current tools.

## Execution Results

User selected Inline. All planned steps are complete: 15 expected RED failures, 45 focused tests passed, 77 full-suite tests passed with one existing Starlette deprecation warning. Actual isolated Uvicorn verification passed and its child process was terminated. Independent final read-only review found no actionable defects. Signing-key rotation and account-name changes were not exercised in dedicated runtime tests. Changes are uncommitted in the existing dev checkout; the production port 5000 process was not restarted and still returns 404 for the new endpoint.
