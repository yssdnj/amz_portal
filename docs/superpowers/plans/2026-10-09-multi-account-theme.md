# Multi-Account and Portal Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. The user previously selected Inline; preserve that choice.

**Goal:** Add the approved second account, render the current username, and provide persistent light/dark appearance on the portal and login page.

**Architecture:** Keep environment-configured accounts and signed cookies. Resolve every authenticated request against currently configured account IDs, while preserving the existing identity API response. Share only theme styles, bootstrap script, and icon markup between the two existing inline HTML renderers.

**Tech Stack:** Python, FastAPI, Starlette SessionMiddleware, python-dotenv, pytest, Playwright with local Chrome, inline CSS/JavaScript, locally embedded Lucide icons.

**Spec:** `D:/python/amz_portal/docs/superpowers/specs/2026-10-09-multi-account-theme-design.md` (confirmed by the user on 2026-10-09).

## Global Constraints

- Preserve `howgo`; add `howgo04` with the user-provided password only in ignored `.env`. Never reproduce real credentials in code, tests, documentation, logs, or this plan.
- Both accounts have the same existing rights. No registration, database, role management, or additional login steps.
- Stable ID formula remains `str(uuid5(NAMESPACE_URL, "urn:amz-portal:user:" + username))`.
- `/api/auth/user` returns only `user_id`, with `Cache-Control: no-store` on both success and failure. `/api/auth/check` remains 204/401.
- Keep the signing secret and existing Cookie name, path, lifetime, SameSite, HttpOnly, and Secure settings.
- Existing valid primary-account cookies remain valid; authenticated-only legacy cookies require a new login.
- Default appearance is dark. Browser preference applies to the portal and its login page, not child projects.
- Do not alter Nginx, SP project code, startup scripts, unrelated changes, or existing card order and service interactions.
- Actual isolated runtime and local HTTPS gateway verification are mandatory. Restart only this project's portal process after tests pass.
- Do not commit or push without a new explicit instruction.

## Review Focus

- Duplicate JSON account keys or a main-account collision must fail startup without disclosing the configuration. Task 1 pins both.
- Removing a configured account must invalidate its signed cookie for pages and APIs, not only the identity endpoint. Task 1 pins the protected paths.
- Long or HTML-special usernames must be escaped and must not push icon controls outside a 320px screen. Tasks 1 and 2 pin rendering and bounds.
- Disabled or corrupt browser storage must leave theme switching and login functional. Task 2 pins both read/write failures and invalid preferences.
- Cross-tab changes, logout/login navigation, and light-theme dialogs must remain coherent. Task 2 pins storage events, navigation, and modal appearance.

## File Map

| Absolute path | Responsibility |
| --- | --- |
| `D:/python/amz_portal/portal.py` | Configuration parsing, multi-account login, session identity, escaped username rendering, theme integration |
| `D:/python/amz_portal/login_page.py` | Shared theme integration and login palette |
| `D:/python/amz_portal/portal_theme.py` | New shared theme tokens, head bootstrap, and offline icon control |
| `D:/python/amz_portal/tests/conftest.py` | Isolate tests from local extra-account credentials |
| `D:/python/amz_portal/tests/test_portal_accounts.py` | New account/configuration/session/rendering tests |
| `D:/python/amz_portal/tests/test_portal_identity.py` | Stricter legacy identity expectation |
| `D:/python/amz_portal/tests/test_portal_ui.py` | Rendered username in existing UI fixture |
| `D:/python/amz_portal/tests/test_portal_theme_ui.py` | New browser theme, persistence, accessibility, layout, and screenshot tests |
| `D:/python/amz_portal/.env.example` | Empty optional extra-account JSON setting |
| `D:/python/amz_portal/README.md` | Configuration, identity compatibility, and theme notes |
| `D:/python/amz_portal/.env` | Local account secret only; ignored and never staged |
| `D:/python/amz_portal/.test-runs/check_multi_account_runtime.py` | Ignored, isolated real HTTP verifier |
| `D:/python/amz_portal/.test-runs/check_live_accounts.py` | Ignored local gateway verifier; credentials read without printing |

## Task 1: Account Configuration and Authenticated Identity

**Files:** `portal.py`, `tests/conftest.py`, `tests/test_portal_accounts.py`, `tests/test_portal_identity.py`, `.env.example`, `README.md` from the file map.

**Interfaces:**
- Produce `load_extra_users(value: str | None, primary_username: str) -> dict[str, str]`.
- Produce `EXTRA_USERS: dict[str, str]`, `configured_accounts() -> dict[str, str]`, and `user_id_for(username: str) -> str`.
- Produce `session_username(request: Request) -> str | None` and change `require_session(request: Request) -> str` to return the resolved username or raise generic 401.
- Produce `render_portal_page(username: str) -> str` for Task 2 and browser fixtures.

- [x] **Step 1: Add failing configuration tests.** Set `os.environ["PORTAL_EXTRA_USERS"] = "{}"` in `tests/conftest.py` before importing the app, to avoid loading real extra credentials through dotenv. Use only fictional accounts in tests.

```python
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
```

- [x] **Step 2: Run the new tests red.** Run `C:/Users/Windows/AppData/Local/Python/bin/python.exe -m pytest tests/test_portal_accounts.py -q` from `D:/python/amz_portal`. Expected: failures because `load_extra_users` is absent; no secrets printed.
- [x] **Step 3: Implement configuration and derived IDs.** Use `json.loads` with an `object_pairs_hook` that rejects duplicates before constructing the dict. Reject every value class in Step 1. Translate parsing/validation failures to the exact generic RuntimeError with `from None`. Initialize extras after the primary username. `configured_accounts()` builds from current primary globals plus extras so password-change tests remain meaningful.

```python
def user_id_for(username: str) -> str:
    return str(uuid5(NAMESPACE_URL, "urn:amz-portal:user:" + username))

def configured_accounts() -> dict[str, str]:
    return {LOGIN_USERNAME: LOGIN_PASSWORD, **EXTRA_USERS}

def session_username(request: Request) -> str | None:
    if request.session.get("authenticated") is not True:
        return None
    user_id = request.session.get("user_id")
    if not isinstance(user_id, str):
        return None
    for username in configured_accounts():
        if user_id == user_id_for(username):
            return username
    return None
```

- [x] **Step 4: Add failing login/identity tests.** Fixture extras: `{"other-user": "other-password"}` via monkeypatch. Assert primary and extra credentials return 200; wrong username, wrong password, cross-account password, and non-ASCII wrong input return the same 401 detail. Assert both UTF-8 credential comparisons run for every configured account using `secrets.compare_digest`; preserve the existing no-extra two-comparison test.
- [x] **Step 5: Pin the session boundary.** Use the existing `signed_session` test helper. Test that primary existing cookie yields check204 and the unchanged identity object; extra cookie gives a distinct uuid5 ID, identical across two clients. Remove extras with monkeypatch and assert old extra cookie gives user401/check401/status401/control401 and homepage302. Verify unauthenticated, missing/wrong/non-string ID, expired, tampered, and spoofed identity headers remain rejected. Update the old missing/wrong-ID test from check204 to check401. Password changes retain the same ID. Assert `no-store` on identity responses and authenticated homepage.
- [x] **Step 6: Implement login and protected paths.** For each configured account compute both `compare_digest` results before testing their conjunction; do not mix credentials from different entries. Only successful login clears and rewrites the session with strict auth True and that account's derived ID. Have index/check/status/service control use `session_username` or `require_session`; `/api/auth/user` resolves the same identity and keeps its existing one-field JSON and no-store401 behavior. Keep redirects, cookie settings, and logout unchanged.
- [x] **Step 7: Add escaped server-side username rendering.** Put `__CURRENT_USERNAME__` in the topbar text and title and substitute using `html.escape(username, quote=True)`. Do substitution after static theme insertion. Test `render_portal_page('<img src=x onerror=alert(1)>"&')` contains escaped text and not executable markup. Verify authenticated homepage shows the correct account and never a password or UUID.
- [x] **Step 8: Document configuration.** Add `PORTAL_EXTRA_USERS={}` to `.env.example`. Explain JSON object syntax with fictional values in README, same permissions, stable per-name identities, restart after config edits, legacy cookies requiring login, and the unchanged SP identity API.
- [x] **Step 9: Run the account regression suite green.** Run `C:/Users/Windows/AppData/Local/Python/bin/python.exe -m pytest tests/test_portal_accounts.py tests/test_portal_identity.py tests/test_portal_login.py tests/test_dynamic_module_status.py tests/test_service_controls.py -q`. Expected: all pass, with at most the existing dependency deprecation warning. Record counts in ignored `.test-runs/multi-account-progress.md`; no commit.

## Task 2: Shared Theme and Header Layout

**Files:** `portal_theme.py`, `portal.py`, `login_page.py`, `tests/test_portal_ui.py`, `tests/test_portal_theme_ui.py`, `README.md` from the file map.

**Interfaces:**
- Consume `render_portal_page(username: str) -> str` and existing `render_login_page(next_path: str, prefix: str) -> str`.
- Produce `apply_theme(page: str) -> str`, replacing static `__THEME_CSS__`, `__THEME_INIT__`, and `__THEME_BUTTON__` markers.
- Theme control selector: `[data-theme-toggle]`. Root state: `data-theme="dark"` or `"light"`. Storage key: `amazon-portal-theme`.

- [x] **Step 1: Add failing browser interaction tests.** Use installed local Chrome headlessly as existing UI tests do. Route portal/login HTML and mock status/auth endpoints without real services. Assert initial dark and target label `切换到浅色`; click sets light and label `切换到深色`; reload, login-to-home navigation, and logout-to-login retain light. A second same-origin tab updates after the first changes storage. Illegal saved value and deleted preference fall back to dark.
- [x] **Step 2: Add failing resilience and accessibility tests.** Override Storage read/write to throw through `page.add_init_script`; assert dark initial state, successful click to light, working login submission, no pageerror. Reach theme control by keyboard and activate with Enter; assert target label/title and visible focus. Check no remote icon or font requests.
- [x] **Step 3: Run UI tests red.** Run `C:/Users/Windows/AppData/Local/Python/bin/python.exe -m pytest tests/test_portal_theme_ui.py -q`. Expected: missing theme selector/attributes, not infrastructure failures.
- [x] **Step 4: Read Impeccable craft-floor immediately before UI edits.** Preserve incumbent typography scale, layout, module assets, and service card semantics. Do not add marketing text or explanatory feature copy.
- [x] **Step 5: Implement shared theme initialization.** Put the bootstrap before page-specific CSS in the head, after theme variables. Execute immediately, guard storage access, set `document.documentElement.dataset.theme` and `style.colorScheme` before first paint. Register button synchronization on DOMContentLoaded and a delegated click handler; only legal light/dark values are applied. Catch write failures without rolling back visual state. On matching storage events apply the new legal value, otherwise dark. Keep all identifiers inside an IIFE to avoid collisions with existing page scripts.
- [x] **Step 6: Implement shared button and tokens.** Embed Lucide sun/moon path markup locally; never fetch a CDN. Use a native `type="button"` with stable 34x34 dimensions, title, aria-label, and focus ring; show sun in dark (target light), moon in light (target dark). Use the following semantic variable values, rather than parallel page-specific hardcoded palettes:

| Variable | Dark | Light |
| --- | --- | --- |
| `--page-bg` | `#0d0d1a` | `#f4f6f9` |
| `--surface` | `#13131f` | `#ffffff` |
| `--topbar-bg` | `#191c2c` | `#ffffff` |
| `--dialog-bg` | `#191a26` | `#ffffff` |
| `--text` | `#e2e8f0` | `#243244` |
| `--heading` | `#f1f5f9` | `#142235` |
| `--muted` | `#a8b2c3` | `#536174` |
| `--subtle` | `#8792a4` | `#647185` |
| `--border` | `#45485d` | `#cbd3df` |
| `--soft-border` | `#252637` | `#dfe5ed` |
| `--hover-bg` | `#303345` | `#edf1f7` |
| `--button-bg` | `#2a2d3a` | `#eef2f7` |
| `--blue` | `#60a5fa` | `#1d5fbb` |
| `--blue-bg` | `rgba(59,130,246,.12)` | `#edf4ff` |
| `--red` | `#fca5a5` | `#a92535` |
| `--red-bg` | `rgba(239,68,68,.10)` | `#fff0f1` |
| `--gold` | `#efc178` | `#805512` |
| `--gold-bg` | `rgba(212,168,67,.08)` | `#fff7e6` |
| `--success-bg` | `#16805d` | `#107451` |
| `--success-border` | `#33ba90` | `#168560` |
| `--on-success` | `#ffffff` | `#ffffff` |
| `--switch-off` | `#363b49` | `#d1d8e3` |

- [x] **Step 7: Integrate both pages.** Replace color literals on body, topbar, headings, descriptions, borders, arrows, inputs, placeholders, reveal/submit/restart/logout buttons, status badges, switches, errors, dialogs, and modal actions with semantic variables. Preserve current layout instead of appending duplicate override sheets. Keep shadows/background opacity appropriate to both themes; the text-bearing disabled states must remain readable. Shared controls have letter-spacing 0. Keep a stable focus outline in both themes.
- [x] **Step 8: Lay out identity controls.** In the topbar use `.topbar-actions` containing `.current-user`, theme button, logout. Username is single-line ellipsis with escaped full title; controls never shrink. Desktop actions align right; at widths <=540 hide the decorative topbar subtitle, use 12px/16px topbar padding and constrain username flex width with min-width0. Place login's theme button in a top-right toolbar with reserved body top padding so it cannot overlap brand/form, even at 320px. Change existing portal UI fixture to call `render_portal_page("test-user")` instead of serving raw template.
- [x] **Step 9: Pin visual bounds and capture one batched screenshot round.** Parametrize both themes across 1440x1000, 390x844, and 320x720, on homepage and login. Assert no horizontal overflow; header username/control boxes do not overlap; controls inside viewport; long username ellipsizes. Open the Linux restart modal using mocked status, assert modal/action bounds and contrasting text/surface colors, then cancel and assert no restart request. Screenshots go to ignored `.test-runs/screenshots/theme-{page}-{theme}-{width}.png`. Inspect desktop/mobile screenshots together; at most one further repair/capture round.
- [x] **Step 10: Run browser regressions and detector once.** Run `C:/Users/Windows/AppData/Local/Python/bin/python.exe -m pytest tests/test_portal_theme_ui.py tests/test_portal_ui.py tests/test_login_ui.py -q`. Expected: all pass, with local Chrome actually running. Execute the Impeccable detector against the final changed page targets using its documented CLI after reading the help; classify existing unrelated issues separately and fix new issues. Document theme behavior in README. No commit.

## Task 3: Real Runtime, Local Account Activation, and Review

**Files:** ignored runtime scripts, progress record, `.env`, screenshots from the file map. No startup/Nginx edits.

**Interfaces:** Consume Task 1 account/session APIs and Task 2 browser renderers. Produce verified live account access and local theme controls.

- [x] **Step 1: Run an isolated real process.** Build `.test-runs/check_multi_account_runtime.py` using subprocess Uvicorn on a free loopback port with test-only main and extra credentials and a test signing secret. Use requests with two separate cookie sessions. Assert anonymous401, successful logins200, distinct expected IDs, stable repeated IDs, check204, correct escaped homepage names/no-store, invalid credentials401, logout401. Terminate only its subprocess in finally. Print only named checks and status codes, never cookie/config/body credentials. Expected: every named check PASS and process cleanup complete.
- [x] **Step 2: Run the whole regression suite.** Run `C:/Users/Windows/AppData/Local/Python/bin/python.exe -m pytest -q` and `git diff --check` in the project. Expected: all tests pass, no new whitespace errors. Record red/green and full-suite counts, screenshot paths, detector result, and actual runtime check results.
- [x] **Step 3: Obtain independent final review.** Fresh reviewer reads the approved spec, changed source, and desktop/mobile screenshots. Request scrutiny of config failures/no secret leakage, all authenticated paths, old primary-cookie compatibility, stable IDs, escaped username, storage failures, palette completeness, and header/modal overlap. Reviewer must not edit unrelated code or expose `.env`. Fix actionable findings, rerun affected tests plus the full suite if auth changed, and update the execution record.
- [x] **Step 4: Update the local ignored account configuration.** Confirm `.env` is ignored with `git check-ignore .env`. Inspect only whether the extra setting exists without printing its value. Apply the exact JSON mapping for `howgo04` using the user's supplied password, preserving the main credentials, signing secret, and all other settings. If there are other configured accounts, preserve them; do not overwrite their mapping. Do not print or stage the file.
- [x] **Step 5: Restart only this portal.** Inspect the process listening on 5000 and verify its executable/command line belongs to `D:/python/amz_portal/portal.py`. Stop that verified process, then start the same Python/runtime launch arrangement hidden, with logs in `.portal-runtime/`; check readiness. Never stop unidentified processes, Nginx, stock, or child projects. If no portal is running, start it normally. Do not end the turn with a verification shell process still running.
- [x] **Step 6: Verify the real local HTTPS gateway.** `.test-runs/check_live_accounts.py` reads both accounts from dotenv without printing secrets. Through `https://www.lovekaiming.com:8443/amazon/`, independently log in as each approved user and assert check204, identity200 with stable distinct expected IDs, rendered username, logout401, and anonymous302 to Amazon login. Check direct loopback access where applicable using the current Secure cookie configuration, without weakening production cookies. Gateway JSON parsing must handle HTML errors and header case safely. Print only named outcomes/statuses.
- [x] **Step 7: Verify live browser interaction.** Using local Chrome, log in through the real gateway; verify header account name, toggle light/dark, refresh, and logout back to themed login. Use credentials only from local config; do not take screenshots with visible password fields. Confirm service status refresh works and avoid actually stopping/restarting child services. Close verification browser sessions and record results.
- [x] **Step 8: Close out.** Confirm Git shows only intended source/tests/docs plus pre-existing untracked files; `.env`, logs, runtime scripts, screenshots stay ignored. Summarize both accounts working, header display, theme persistence and default, actual runtime/restart verification, and no GitHub push. Link only relevant non-secret source/docs as needed.

## Self-Review and Approval Gate

Spec coverage checked: configuration/identity in Task 1, header and shared appearance in Task 2, actual restart/runtime and independent review in Task 3. All five review-focus conditions have corresponding tests. Shared names/types and unchanged API/Cookie contracts are specified above. No unresolved product decision or real password is present.

Design and plan confirmed. Executed Inline: Tasks 1 and 2 complete; final independent review found a form/config length mismatch, fixed with a RED-to-GREEN browser regression. Full suite: 116 passed, one existing dependency warning. Actual isolated runtime and restarted local HTTPS gateway verified for both accounts. No commit or push.
