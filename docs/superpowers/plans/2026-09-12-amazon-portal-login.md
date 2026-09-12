# Amazon Portal Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent, production-ready login page and signed session that protects the Amazon portal, every proxied Amazon project, and their APIs.

**Architecture:** FastAPI owns credentials, signed sessions, login/logout, and direct-port enforcement. The shared Nginx gateway delegates every `/amazon/` authorization decision to FastAPI through an internal `auth_request` endpoint while leaving the stock login untouched. A dedicated login surface extends the current portal's dark operational visual language and removes the redundant administrator-token prompt.

**Tech Stack:** Python 3, FastAPI, Uvicorn, stdlib PBKDF2/HMAC, python-dotenv, Nginx `auth_request`, pytest, FastAPI TestClient, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-12-amazon-portal-login-design.md`

## Global Constraints

- `/stock/` routes and stock authentication must remain unchanged.
- `/amazon` returns `308 /amazon/`; unauthenticated `/amazon/` returns `302 /amazon/login?next=/amazon/`.
- All Amazon pages and APIs require the independent Amazon session except login, login submission, logout, and the internal auth subrequest.
- Initial username is `howgo`; the supplied password must only exist as a PBKDF2 hash in ignored server configuration.
- Session cookies expire after 12 hours and use `HttpOnly`, `SameSite=Lax`, `Secure` over HTTPS, and the narrowest usable path.
- Login redirects accept only local paths within the active Amazon prefix.
- Successful login grants service-control access; the second administrator-token dialog is removed.
- Existing same-origin and `X-Portal-Control` checks remain required for state-changing service operations.

---

### Task 1: Authentication Core

**Files:**
- Create: `portal_auth.py`
- Create: `tests/test_portal_auth.py`
- Create: `tests/conftest.py`
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Create: `.env.example`

**Interfaces:**
- Produces: `AuthSettings.from_environment() -> AuthSettings`
- Produces: `hash_password(password: str, *, salt: bytes | None = None, iterations: int = 600_000) -> str`
- Produces: `verify_password(password: str, encoded: str) -> bool`
- Produces: `PortalAuth.issue_session(username: str, now: int | None = None) -> str`
- Produces: `PortalAuth.verify_session(token: str | None, now: int | None = None) -> str | None`
- Produces: `LoginLimiter.check(client_id: str, now: float | None = None) -> tuple[bool, int]`, `record_failure(...)`, and `clear(...)`

- [ ] **Step 1: Write failing authentication unit tests**

```python
def test_password_hash_round_trip():
    encoded = hash_password("test-password", salt=b"0123456789abcdef", iterations=10_000)
    assert verify_password("test-password", encoded)
    assert not verify_password("wrong", encoded)
    assert "test-password" not in encoded


def test_signed_session_rejects_tampering_and_expiry(auth):
    token = auth.issue_session("howgo", now=1_000)
    assert auth.verify_session(token, now=1_001) == "howgo"
    assert auth.verify_session(token + "x", now=1_001) is None
    assert auth.verify_session(token, now=1_000 + 43_201) is None


def test_login_limiter_blocks_sixth_failure():
    limiter = LoginLimiter(max_failures=5, window_seconds=900)
    for offset in range(5):
        assert limiter.check("203.0.113.8", now=offset)[0]
        limiter.record_failure("203.0.113.8", now=offset)
    allowed, retry_after = limiter.check("203.0.113.8", now=5)
    assert not allowed
    assert retry_after > 0
```

- [ ] **Step 2: Run the tests and verify they fail because `portal_auth` does not exist**

Run: `python -m pytest tests/test_portal_auth.py -q -p no:cacheprovider`

Expected: collection fails with `ModuleNotFoundError: No module named 'portal_auth'`.

- [ ] **Step 3: Implement the authentication primitives**

Use `hashlib.pbkdf2_hmac("sha256", ...)`, URL-safe base64, JSON payloads containing `username` and `expires_at`, and `hmac.compare_digest`. Parse password hashes in the exact form:

```text
pbkdf2_sha256$600000$<urlsafe-base64-salt>$<urlsafe-base64-digest>
```

`AuthSettings.from_environment()` must reject missing or malformed `PORTAL_LOGIN_USERNAME`, `PORTAL_LOGIN_PASSWORD_HASH`, or `PORTAL_SESSION_SECRET` with a clear startup error. `PortalAuth` must never log credentials, hashes, cookies, or signing secrets.

- [ ] **Step 4: Add configuration support**

Add `python-dotenv>=1.0,<2` to `requirements.txt`, add `.env` to `.gitignore`, and create `.env.example` containing only:

```dotenv
PORTAL_LOGIN_USERNAME=replace-me
PORTAL_LOGIN_PASSWORD_HASH=pbkdf2_sha256$600000$replace-me$replace-me
PORTAL_SESSION_SECRET=replace-with-at-least-32-random-bytes
```

Create `tests/conftest.py` to set a deterministic test username, test-password
hash, and signing secret before test modules import `portal`. Never use the
real supplied password in committed tests or fixtures.

- [ ] **Step 5: Run the unit tests**

Run: `python -m pytest tests/test_portal_auth.py -q -p no:cacheprovider`

Expected: all authentication unit tests pass.

- [ ] **Step 6: Commit the authentication core**

```bash
git add portal_auth.py tests/test_portal_auth.py requirements.txt .gitignore .env.example
git commit -m "feat: add Amazon portal session authentication"
```

---

### Task 2: FastAPI Login and Protected Endpoints

**Files:**
- Modify: `portal.py`
- Create: `tests/test_portal_login.py`
- Modify: `tests/test_service_controls.py`
- Modify: `tests/test_dynamic_module_status.py`

**Interfaces:**
- Consumes: `PortalAuth.issue_session()` and `PortalAuth.verify_session()` from Task 1.
- Produces: `GET /login`, `POST /api/auth/login`, `GET /api/auth/check`, and `POST /api/auth/logout`.
- Produces: `require_session(request: Request) -> str` and `session_cookie_options(request: Request) -> dict[str, object]`.

- [ ] **Step 1: Write failing endpoint tests**

```python
def test_unauthenticated_page_redirects_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=/"


def test_login_sets_hardened_cookie(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "howgo", "password": "test-password", "next": "/amazon/"},
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Prefix": "/amazon"},
    )
    assert response.status_code == 200
    assert response.json() == {"redirect": "/amazon/"}
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/amazon" in cookie


def test_auth_check_and_logout(client, login_cookie):
    assert client.get("/api/auth/check", cookies=login_cookie).status_code == 204
    response = client.post("/api/auth/logout", cookies=login_cookie)
    assert response.status_code == 200
    assert response.json() == {"redirect": "/login"}


def test_external_redirect_is_rejected(client):
    response = client.post("/api/auth/login", json={
        "username": "howgo", "password": "test-password", "next": "https://evil.example/",
    })
    assert response.status_code == 200
    assert response.json()["redirect"] == "/"
```

- [ ] **Step 2: Run endpoint tests and verify the new routes fail**

Run: `python -m pytest tests/test_portal_login.py -q -p no:cacheprovider`

Expected: failures for missing login routes and unprotected `/`.

- [ ] **Step 3: Implement session helpers and auth routes in `portal.py`**

Load `.env` before constructing `AuthSettings`. Set and delete the `amazon_portal_session` cookie with a path derived from `X-Forwarded-Prefix`; use `/` for direct local access. Return the same generic `401` message for an invalid username or password. Return `429` with `Retry-After` after five failures within 15 minutes.

Protect `/`, `/api/status`, and `/api/services/{service_id}/{action}` at the application layer. Preserve the custom control header and same-origin validation, but remove `PORTAL_CONTROL_TOKEN`, bearer-token handling, and local-network authorization bypasses. A valid login session becomes the authorization requirement.

- [ ] **Step 4: Update existing service tests to authenticate**

Provide a fixture that installs a deterministic `PortalAuth` instance and logs in before requests. Retain explicit tests proving unauthenticated status and control requests return `401` or redirect as appropriate.

- [ ] **Step 5: Run all backend tests**

Run: `python -m pytest tests/test_portal_auth.py tests/test_portal_login.py tests/test_service_controls.py tests/test_dynamic_module_status.py -q -p no:cacheprovider`

Expected: all selected tests pass.

- [ ] **Step 6: Commit FastAPI authentication**

```bash
git add portal.py tests/test_portal_login.py tests/test_service_controls.py tests/test_dynamic_module_status.py
git commit -m "feat: protect Amazon portal with login sessions"
```

---

### Task 3: Login Page and Authenticated Portal UI

**Files:**
- Create: `login_page.py`
- Modify: `portal.py`
- Modify: `tests/test_portal_ui.py`
- Create: `tests/test_login_ui.py`

**Interfaces:**
- Produces: `render_login_page(next_path: str, prefix: str) -> str`.
- Consumes: `POST api/auth/login` relative to the login page URL.
- Consumes: `POST /api/auth/logout` from the portal top bar.

- [ ] **Step 1: Write failing Playwright tests**

```python
def test_login_form_is_accessible_and_submits(page):
    requests = []
    page.route("https://example.test/amazon/login", lambda route: route.fulfill(
        body=render_login_page("/amazon/", "/amazon"), content_type="text/html",
    ))
    page.route("**/api/auth/login", lambda route: (
        requests.append(route.request.post_data_json),
        route.fulfill(json={"redirect": "/amazon/"}),
    ))
    page.goto("https://example.test/amazon/login")
    page.get_by_label("账号").fill("howgo")
    page.get_by_label("密码").fill("test-password")
    page.get_by_role("button", name="登录").click()
    assert requests == [{"username": "howgo", "password": "test-password", "next": "/amazon/"}]


@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844), (320, 720)])
def test_login_layout_has_no_overflow(page, width, height):
    page.set_viewport_size({"width": width, "height": height})
    page.route("https://example.test/amazon/login", lambda route: route.fulfill(
        body=render_login_page("/amazon/", "/amazon"), content_type="text/html",
    ))
    page.goto("https://example.test/amazon/login")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.get_by_role("heading", name="登录 Amazon 工具中心").is_visible()
```

- [ ] **Step 2: Run UI tests and verify they fail because the renderer does not exist**

Run: `python -m pytest tests/test_login_ui.py -q -p no:cacheprovider`

Expected: collection fails because `login_page.render_login_page` does not exist.

- [ ] **Step 3: Build the login surface**

Immediately before editing the UI, read `C:/Users/Windows/.agents/skills/impeccable/reference/craft-floor.md`. Create a full-height graphite workspace with a compact form no wider than 420px. Reuse the portal's white text, blue status accents, teal action color, square 6-8px radii, and work-focused density. Include visible labels, username and password autocomplete, a Lucide eye/eye-off icon button with tooltip, inline generic error text, disabled loading state, Enter submission, and reduced-motion CSS. Do not include credentials, feature instructions, decorative cards, gradients, or remote assets.

- [ ] **Step 4: Simplify the authenticated portal controls**

Add a compact logout icon button to the top bar. Remove the administrator-token dialog, `controlToken`, bearer authorization, and token-prompt branch. When a status or control request returns `401`, navigate to the prefix-aware login URL instead of displaying an unknown status indefinitely.

- [ ] **Step 5: Run the login and existing portal UI tests**

Run: `python -m pytest tests/test_login_ui.py tests/test_portal_ui.py -q -p no:cacheprovider`

Expected: all UI tests pass at desktop and mobile viewports.

- [ ] **Step 6: Commit the login UI**

```bash
git add login_page.py portal.py tests/test_login_ui.py tests/test_portal_ui.py
git commit -m "feat: add Amazon portal login experience"
```

---

### Task 4: Independent Amazon Gateway Authentication

**Files:**
- Modify: `amazon.conf`
- Create: `tests/test_amazon_nginx_config.py`

**Interfaces:**
- Consumes: `GET http://127.0.0.1:5000/api/auth/check`.
- Produces: internal Nginx location `/_amazon_session`.
- Produces: named Nginx location `@amazon_login_required`.

- [ ] **Step 1: Write failing configuration tests**

```python
def test_amazon_gateway_uses_independent_auth():
    config = Path("amazon.conf").read_text(encoding="utf-8")
    assert "location = /_amazon_session" in config
    assert "proxy_pass http://127.0.0.1:5000/api/auth/check;" in config
    assert "location @amazon_login_required" in config
    assert "@stock_login_required" not in config


def test_login_routes_are_declared_before_protected_api_prefix():
    config = Path("amazon.conf").read_text(encoding="utf-8")
    assert config.index("location = /amazon/login") < config.index("location ^~ /amazon/api/")
    assert config.index("location = /amazon/api/auth/login") < config.index("location ^~ /amazon/api/")
```

- [ ] **Step 2: Run the configuration tests and verify they fail on stock auth references**

Run: `python -m pytest tests/test_amazon_nginx_config.py -q -p no:cacheprovider`

Expected: failures because `amazon.conf` still uses `/_session` and `@stock_login_required`.

- [ ] **Step 3: Implement the Nginx auth flow**

Add exact public locations for `/amazon/login`, `/amazon/api/auth/login`, and `/amazon/api/auth/logout`. Add internal `/_amazon_session` with no request body and the original cookies forwarded to FastAPI. Every Amazon API prefix uses `auth_request /_amazon_session` and keeps a raw `401`. Every Amazon page prefix uses the same auth request plus `error_page 401 = @amazon_login_required`. The named location returns `302 /amazon/login?next=$uri`.

- [ ] **Step 4: Run config tests and isolated syntax validation**

Run: `python -m pytest tests/test_amazon_nginx_config.py -q -p no:cacheprovider`

Run: `D:\Personal\investment\stock\stock-portal\runtime\nginx\nginx.exe -p D:/Personal/investment/stock/stock-portal/nginx/ -e stderr -c D:/python/amz_portal/.test-runs/amazon-nginx-wrapper.conf -t`

Expected: tests pass and Nginx reports syntax successful.

- [ ] **Step 5: Commit the gateway changes**

```bash
git add amazon.conf tests/test_amazon_nginx_config.py
git commit -m "feat: route Amazon gateway through independent login"
```

---

### Task 5: Provision, Deploy, and Verify

**Files:**
- Modify: `deploy.sh`
- Modify: `README.md`
- Create locally but do not commit: `.env`
- Deploy copy: `D:/Personal/investment/stock/stock-portal/nginx/conf.d/amazon.conf`

**Interfaces:**
- Consumes: `.env` variables from Task 1.
- Produces: a restarted portal on `127.0.0.1:5000` and reloaded shared Nginx on `8443`.

- [ ] **Step 1: Update deployment and operator documentation**

Make `deploy.sh` preserve and load `.env` before starting `portal.py`. Document one-time credential generation, the 12-hour session, logout, and the independent `/amazon/login` flow. Remove obsolete instructions that describe `PORTAL_CONTROL_TOKEN` as the remote control mechanism.

- [ ] **Step 2: Generate local secrets without printing them**

Generate a random 16-byte password salt, hash the supplied password with 600,000 PBKDF2 iterations, and generate a random 48-byte session secret. Write only username, password hash, and session secret to ignored `.env`; never echo the password or resulting secret to terminal output.

- [ ] **Step 3: Run the complete test suite**

Run: `python -m pytest tests -q -p no:cacheprovider`

Expected: all tests pass with no failures.

- [ ] **Step 4: Run bounded visual QA**

Run Playwright screenshots for the login page at `1440x900`, `390x844`, and `320x720`. Inspect the desktop and mobile outputs once, fix all observed overflow, contrast, focus, alignment, and loading/error-state issues in one batch, then perform at most one confirmation pass.

Run: `node C:\Users\Windows\.agents\skills\impeccable\scripts\detect.mjs --json login_page.py portal.py`

Expected: no blocking Impeccable detector findings.

- [ ] **Step 5: Restart the local portal and deploy the gateway config**

Restart the single portal process on port 5000 so it loads `.env`. Copy `amazon.conf` to the shared gateway's `nginx/conf.d/amazon.conf`, run the full gateway `nginx -t`, and only then issue `nginx -s reload`. Do not modify `stock.conf` or any generated stock route.

- [ ] **Step 6: Verify the live route contract**

Using an HTTPS client with the host header `www.lovekaiming.com`:

```text
GET /stock/ without a stock session       -> 302 /stock/login
GET /amazon                               -> 308 /amazon/
GET /amazon/ without an Amazon session    -> 302 /amazon/login?next=/amazon/
GET /amazon/login                         -> 200
POST valid credentials                    -> 200 plus hardened session cookie
GET /amazon/ with the Amazon cookie       -> 200
GET every configured child page           -> not 401/302 and not a gateway 404/502
POST /amazon/api/auth/logout              -> clears cookie
GET /amazon/ after logout                 -> 302 /amazon/login?next=/amazon/
```

- [ ] **Step 7: Commit deployment documentation**

```bash
git add deploy.sh README.md
git commit -m "docs: document Amazon portal login deployment"
```

- [ ] **Step 8: Review final repository state**

Run: `git status --short`, `git log -5 --oneline`, and `git diff HEAD~4..HEAD --check`.

Expected: only intentionally ignored runtime files remain untracked; the implementation consists of focused commits with no whitespace errors.
