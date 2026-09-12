# Amazon Portal Login Design

## Goal

Add an independent login experience to `amz_portal`. Public requests under
`/amazon/` must use the Amazon portal session and must never depend on the
stock portal session. The existing `/stock/` routes and authentication remain
unchanged.

The initial administrator account is `howgo`. The supplied password is used
only to generate a server-side password hash and is never embedded in HTML,
JavaScript, committed configuration, or logs.

## URL Contract

| Request | Result |
| --- | --- |
| `/amazon` | `308` to `/amazon/` |
| `/amazon/` without a valid session | `302` to `/amazon/login?next=/amazon/` |
| `/amazon/login` | Amazon login page |
| successful login | `302` to the validated `next` path, default `/amazon/` |
| `/amazon/` with a valid session | Amazon tools portal |
| logout | clear the session and `302` to `/amazon/login` |

Every Amazon project page and API route is protected. Direct public access to
`/amazon/products/`, `/amazon/ads/`, `/amazon/toolkit/`, `/amazon/xiyou/`,
`/amazon/official-sp/`, and `/amazon/official-ads/` requires the same session.

## Application Authentication

`portal.py` owns the authentication lifecycle:

- `GET /login` renders the login page.
- `POST /api/auth/login` validates JSON credentials and creates a signed,
  time-limited session cookie.
- `GET /api/auth/check` returns `204` for a valid session and `401` otherwise.
- `POST /api/auth/logout` clears the cookie.
- The portal page, status endpoint, and service-control endpoints also verify
  the session, so direct access to port 5000 is not an authentication bypass.

The session cookie is named specifically for this portal and uses `HttpOnly`,
`SameSite=Lax`, and `Secure` on HTTPS requests. Its path is `/amazon` behind
the gateway and `/` for direct local development. Sessions expire after 12
hours. Redirect targets accept only local paths under `/amazon/` to prevent
open redirects.

Credentials and the session signing secret are loaded from an ignored `.env`
file or process environment:

- `PORTAL_LOGIN_USERNAME`
- `PORTAL_LOGIN_PASSWORD_HASH`
- `PORTAL_SESSION_SECRET`

Password verification uses PBKDF2-HMAC-SHA256 with a random salt and constant-
time comparison. Repeated failed logins from one client are temporarily rate
limited. The repository includes only a `.env.example` with placeholders.

The authenticated session authorizes project start, stop, and restart actions.
The existing administrator-token dialog and browser-held control token are
removed to avoid a second login step. Existing same-origin and custom-header
checks remain in place for state-changing requests.

## Gateway Authentication

`amazon.conf` defines an internal `/_amazon_session` subrequest that proxies to
the portal's `/api/auth/check`. Login, login API, and logout routes are public;
all other Amazon page and API locations use `auth_request /_amazon_session`.
Unauthorized page requests are redirected by an Amazon-specific named location
to `/amazon/login?next=$uri`. Unauthorized API requests retain HTTP `401` and
are never redirected to HTML.

The stock gateway's `/_session`, `@stock_login_required`, and `/stock/` routes
are not changed.

## Login Experience

The login page extends the portal's established dark operational interface. It
uses a compact, centered form with the Amazon Tools identity, clear account and
password labels, a password visibility icon, an inline error region, a loading
state, and keyboard submission. It avoids decorative marketing content and
keeps the task immediately visible at desktop and mobile sizes.

Errors do not reveal whether the username or password was wrong. Focus states,
autocomplete attributes, reduced-motion behavior, and a live status region are
included. The password is cleared after failed submission.

## Verification

Automated FastAPI tests cover redirects, successful and failed login, signed
cookie validation, expiry, logout, protected APIs, open-redirect rejection,
and authenticated service control. Playwright tests cover desktop and mobile
layout, keyboard submission, error presentation, and overflow.

Deployment verification consists of the full test suite, Impeccable's UI
detector, `nginx -t`, a smooth Nginx reload, and gateway requests confirming:

- `/stock/` still follows the stock login flow.
- `/amazon` canonicalizes to `/amazon/`.
- `/amazon/` redirects to `/amazon/login` while logged out.
- `/amazon/login` returns `200`.
- a valid Amazon session reaches `/amazon/` and all configured child routes.
