# Simplified Amazon Portal Login Design

## Scope

The Amazon portal uses one configured account and one signed Starlette session.
This design replaces the earlier multi-part authentication proposal. It does
not include registration, roles, password recovery, password hashing helpers,
custom cookie cryptography, or login rate limiting.

## Application Contract

- `GET /login` renders the dark Amazon Tools login page.
- `POST /api/auth/login` accepts `username`, `password`, and `next`, compares
  both credentials with `secrets.compare_digest`, records
  `authenticated=True` in the session, and returns a local redirect path.
- `GET /api/auth/check` returns `204` for an authenticated session and `401`
  otherwise.
- `POST /api/auth/logout` clears the session and returns the prefix-aware login
  URL.
- `/`, `/api/status`, and `/api/services/...` enforce the session inside
  FastAPI. Page requests redirect to login; API requests return `401`.
- Service mutations retain the same-origin and `X-Portal-Control: 1` checks.
  The former administrator token, bearer header, local bypass, and
  `PORTAL_CONTROL_TOKEN` dependency are removed.

The application loads `PORTAL_LOGIN_USERNAME`, `PORTAL_LOGIN_PASSWORD`, and
`PORTAL_SESSION_SECRET` from `.env` through python-dotenv and refuses to start
when any are missing. `PORTAL_COOKIE_SECURE` is optional. SessionMiddleware
uses the `amazon_portal_session` cookie with a 12-hour maximum age, `HttpOnly`,
`SameSite=Lax`, path `/`, and the configured Secure flag.

`next` is accepted only when it is an absolute local path inside the active
`X-Forwarded-Prefix`. Invalid values fall back to `/amazon/` behind the gateway
or `/` for direct access.

## Gateway Contract

`amazon.conf` owns Amazon authentication independently of the stock portal.
Public exact locations proxy the login page, login submission, and logout.
The internal `/_amazon_session` location forwards the request cookie to
FastAPI's auth check without a request body.

Every Amazon page prefix uses `auth_request /_amazon_session` and redirects a
`401` through `@amazon_login_required` to `/amazon/login?next=$uri`. Every
Amazon API prefix uses the same auth request and leaves `401` unchanged.
`/amazon` continues to return `308 /amazon/`. No stock auth locations or stock
project files are changed.

## Login Experience

The login page adapts the established dark operational structure: Amazon Tools
identity and context beside a compact labeled form, collapsing to one column on
small screens. It includes username and password autocomplete, a password
reveal icon, Enter-key submission, disabled loading state, and one generic
invalid-credentials error. No credentials are embedded in the page.

## Verification

FastAPI tests cover redirects and API denial, valid and invalid login, hardened
cookie attributes, auth check, logout, redirect validation, and authenticated
controls. Playwright covers submission, reveal/loading/error states, and
desktop/mobile overflow. Nginx tests verify public auth routes and independent
page/API authorization locations.
