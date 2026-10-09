from pathlib import Path

import pytest

import portal
from login_page import render_login_page
from test_portal_ui import page, setup_page

playwright = pytest.importorskip("playwright.sync_api")
expect = playwright.expect
KEY = "amazon-portal-theme"


def route_login(page):
    page.route("http://127.0.0.1:5000/login", lambda route: route.fulfill(
        body=render_login_page("/", ""), content_type="text/html"))
    page.route("**/api/auth/login", lambda route: route.fulfill(json={"redirect": "/"}))
    page.route("**/api/auth/logout", lambda route: route.fulfill(json={"redirect": "/login"}))


def theme_button(page):
    return page.locator("[data-theme-toggle]")


def test_theme_persists_refresh_login_and_logout(page):
    setup_page(page)
    route_login(page)
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(theme_button(page)).to_have_attribute("aria-label", "切换到浅色")
    theme_button(page).click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    expect(theme_button(page)).to_have_attribute("title", "切换到深色")
    assert page.evaluate(f"localStorage.getItem('{KEY}')") == "light"
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    page.locator("#logout-button").click()
    expect(page).to_have_url("http://127.0.0.1:5000/login")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    page.get_by_label("账号").fill("test-user")
    page.get_by_label("密码", exact=True).fill("test-password")
    page.get_by_role("button", name="登录", exact=True).click()
    expect(page).to_have_url("http://127.0.0.1:5000/")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")


def test_storage_events_sync_tabs_and_removal(page):
    setup_page(page)
    second = page.context.new_page()
    try:
        setup_page(second)
        theme_button(page).click()
        expect(second.locator("html")).to_have_attribute("data-theme", "light")
        page.evaluate(f"localStorage.removeItem('{KEY}')")
        expect(second.locator("html")).to_have_attribute("data-theme", "dark")
        page.evaluate(f"localStorage.setItem('{KEY}', 'invalid')")
        expect(second.locator("html")).to_have_attribute("data-theme", "dark")
        second.reload()
        expect(second.locator("html")).to_have_attribute("data-theme", "dark")
    finally:
        second.close()


def test_storage_failure_does_not_break_login_or_theme(page):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script("""
        Storage.prototype.getItem = function() { throw new Error('disabled'); };
        Storage.prototype.setItem = function() { throw new Error('disabled'); };
    """)
    setup_page(page)
    route_login(page)
    page.goto("http://127.0.0.1:5000/login")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    theme_button(page).click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    page.get_by_label("账号").fill("test-user")
    page.get_by_label("密码", exact=True).fill("test-password")
    page.get_by_role("button", name="登录", exact=True).click()
    expect(page).to_have_url("http://127.0.0.1:5000/")
    assert not errors


def test_theme_keyboard_focus_and_offline_icons(page):
    external = []
    page.on("request", lambda req: external.append(req.url) if not req.url.startswith("http://127.0.0.1:5000") else None)
    setup_page(page)
    page.keyboard.press("Tab")
    expect(theme_button(page)).to_be_focused()
    assert theme_button(page).evaluate("el => getComputedStyle(el).outlineStyle") != "none"
    page.keyboard.press("Enter")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    assert theme_button(page).locator("svg").count() == 2
    assert not external


def test_long_configured_account_submits_without_truncation(page, client, monkeypatch):
    username = "long-account-name-" * 8
    password = "fake-long-password-" * 20
    monkeypatch.setattr(portal, "EXTRA_USERS", {username: password})
    setup_page(page)
    route_login(page)
    results = []

    def authenticate(route):
        payload = route.request.post_data_json
        result = client.post("/api/auth/login", json=payload)
        results.append((payload == {"username": username, "password": password, "next": "/"}, result.status_code))
        route.fulfill(status=result.status_code, json=result.json())

    page.route("**/api/auth/login", authenticate)
    page.goto("http://127.0.0.1:5000/login")
    page.get_by_label("账号").fill(username)
    page.get_by_label("密码", exact=True).fill(password)
    expect(page.get_by_label("账号")).to_have_value(username)
    expect(page.get_by_label("密码", exact=True)).to_have_value(password)
    page.get_by_role("button", name="登录", exact=True).click()
    expect(page).to_have_url("http://127.0.0.1:5000/")
    assert results == [(True, 200)]
    assert client.get("/api/auth/user").json() == {"user_id": portal.user_id_for(username)}


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844), (320, 720)])
def test_theme_layout_and_dialog(page, theme, width, height):
    page.set_viewport_size({"width": width, "height": height})
    page.add_init_script(f"localStorage.setItem('{KEY}', '{theme}')")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _, requests = setup_page(page, system="Linux")
    long_name = "long-account-name-" * 8
    page.route("http://127.0.0.1:5000/", lambda route: route.fulfill(
        body=portal.render_portal_page(long_name), content_type="text/html"))
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", theme)
    user = page.locator(".current-user")
    expect(user).to_have_text(long_name)
    expect(user).to_have_attribute("title", long_name)
    assert user.evaluate("el => getComputedStyle(el).textOverflow") == "ellipsis"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    bounds = [page.locator(selector).bounding_box() for selector in [".topbar-title", ".current-user", "[data-theme-toggle]", "#logout-button"]]
    for left, right in zip(bounds, bounds[1:]):
        assert left["x"] + left["width"] <= right["x"] + 1
    assert bounds[-1]["x"] + bounds[-1]["width"] <= width
    output = Path(__file__).resolve().parents[1] / ".test-runs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / f"theme-portal-{theme}-{width}.png"), full_page=True)
    page.locator('.service-card[data-service="ads"] .restart-button').click()
    dialog = page.locator("#restart-dialog")
    expect(dialog).to_be_visible()
    box = dialog.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= width
    assert box["y"] >= 0 and box["y"] + box["height"] <= height
    assert dialog.evaluate("el => getComputedStyle(el).color !== getComputedStyle(el).backgroundColor")
    page.screenshot(path=str(output / f"theme-dialog-{theme}-{width}.png"))
    dialog.locator('button[value="cancel"]').click()
    assert requests == []
    route_login(page)
    page.goto("http://127.0.0.1:5000/login")
    expect(page.locator("html")).to_have_attribute("data-theme", theme)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    toolbar = theme_button(page).bounding_box()
    brand = page.locator(".brand").bounding_box()
    assert toolbar["y"] + toolbar["height"] <= brand["y"] or toolbar["x"] >= brand["x"] + brand["width"]
    page.screenshot(path=str(output / f"theme-login-{theme}-{width}.png"), full_page=True)
    assert not errors
