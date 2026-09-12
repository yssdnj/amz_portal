# Simplified Amazon Portal Login Implementation Plan

**Goal:** Protect the Amazon portal with one configured account and one signed
12-hour session, independently of stock portal authentication.

**Scope rule:** Implement only direct credential comparison, Starlette session
middleware, the login/logout/check routes, FastAPI route protection, the login
page, and Amazon-specific Nginx auth requests. Do not add password hashing,
rate limiting, registration, roles, recovery, or custom session cryptography.

## 1. Specify Behavior With Tests

- Add shared test credentials using only `test-password`.
- Add endpoint tests for logged-out behavior, valid and invalid login, cookie
  flags, auth check, logout, prefix handling, and open-redirect rejection.
- Update service and portal tests to operate through an authenticated session.
- Add Playwright tests for reveal, keyboard submission, loading, generic error,
  and desktop/mobile overflow.
- Add config tests for public auth routes and independent page/API auth blocks.
- Record one focused red run before production implementation.

## 2. Implement the Session Flow

- Load `.env` with python-dotenv and require `PORTAL_LOGIN_USERNAME`,
  `PORTAL_LOGIN_PASSWORD`, and `PORTAL_SESSION_SECRET`.
- Configure `SessionMiddleware` with cookie name `amazon_portal_session`, path
  `/`, 12-hour max age, `HttpOnly`, `SameSite=Lax`, and optional Secure.
- Add login, auth-check, and logout endpoints plus prefix-aware local redirect
  validation.
- Protect the portal page, status API, and service API in FastAPI.
- Remove administrator-token browser state, bearer handling, local bypasses,
  and `PORTAL_CONTROL_TOKEN`.

## 3. Add the Login Surface

- Adapt the existing dark operational login structure to Amazon branding.
- Keep the form focused and accessible with labels, autocomplete, password
  reveal icon, loading state, keyboard submission, and generic error copy.
- Add a compact logout action to the authenticated portal.

## 4. Isolate Gateway Authentication

- Keep `/amazon` canonicalization.
- Add exact public locations for login, login submission, and logout.
- Add internal `/_amazon_session` and Amazon-specific login redirect handling.
- Apply the auth subrequest independently to every Amazon page and API prefix.
- Do not modify or deploy the stock project.

## 5. Verify and Commit

- Run focused green tests.
- Run the full suite with `--basetemp .test-runs/pytest-simple-login`.
- Run the required Impeccable detector once against `login_page.py` and
  `portal.py`.
- Review the complete tracked diff, write the closeout report, and commit all
  tracked changes as one focused implementation.
