from pathlib import Path

import pytest

import portal

playwright = pytest.importorskip("playwright.sync_api")
expect = playwright.expect


@pytest.fixture
def page():
    with playwright.sync_playwright() as engine:
        try:
            browser = engine.chromium.launch(channel="chrome", headless=True)
        except playwright.Error as exc:
            pytest.skip(f"Chrome unavailable: {exc}")
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        yield page
        browser.close()


def setup_page(page, system="Windows"):
    state = {"services": {
        key: {**service, "online": key == "ads", "busy": False, "error": None,
              "action": None, "can_start": True, "can_restart": system == "Linux",
              "restart_warning": True}
        for key, service in portal.SERVICES.items()
    }, "controls": {"platform": system, "enabled": True, "requires_token": False}}
    requests = []
    page.route("http://127.0.0.1:5000/", lambda route: route.fulfill(body=portal.HTML, content_type="text/html"))
    page.route("**/api/status", lambda route: route.fulfill(json=state))

    def operate(route):
        key, action = route.request.url.split("/")[-2:]
        requests.append((key, action))
        state["services"][key]["online"] = action != "stop"
        route.fulfill(status=202, json={"accepted": True})

    page.route("**/api/services/**", operate)
    page.goto("http://127.0.0.1:5000/")
    expect(page.locator('.service-card[data-service="ads"] .service-switch')).to_be_enabled()
    return state, requests


def test_single_switch_starts_and_pauses_without_opening_project(page):
    _, requests = setup_page(page)
    toggle = page.locator('.service-card[data-service="ads"] .service-switch')
    expect(toggle).to_have_attribute("aria-checked", "true")
    toggle.click()
    expect(toggle).to_have_attribute("aria-checked", "false")
    expect(toggle).to_be_enabled()
    toggle.click()
    expect(toggle).to_have_attribute("aria-checked", "true")
    assert requests == [("ads", "stop"), ("ads", "start")]
    assert len(page.context.pages) == 1
    expect(page.locator('a[data-local-url="http://127.0.0.1:5001/"]')).to_have_attribute("href", "http://127.0.0.1:5001/")
    assert page.get_by_role("switch").count() == 6
    for button in page.locator(".restart-button").all():
        expect(button).to_be_disabled()


def test_linux_restart_requires_confirmation_and_cancel_sends_nothing(page):
    _, requests = setup_page(page, system="Linux")
    button = page.locator('.service-card[data-service="ads"] .restart-button')
    button.click()
    expect(page.locator("#restart-dialog")).to_be_visible()
    page.locator('#restart-dialog button[value="cancel"]').click()
    assert requests == []
    button.click()
    with page.expect_response("**/api/services/ads/restart") as response:
        page.locator('#restart-dialog button[value="confirm"]').click()
    assert response.value.status == 202
    expect(page.locator("#restart-dialog")).not_to_be_visible()
    expect(button).to_be_enabled()
    assert requests == [("ads", "restart")]


def test_busy_and_unknown_status_disable_controls(page):
    state, _ = setup_page(page)
    state["services"]["ads"].update(busy=True, action="stop")
    page.evaluate("refreshStatuses()")
    card = page.locator('.service-card[data-service="ads"]')
    expect(card.get_by_role("switch")).to_be_disabled()
    expect(card.locator("[data-status-badge]")).to_contain_text("暂停中")
    page.route("**/api/status", lambda route: route.fulfill(status=503, body="unavailable"))
    page.evaluate("refreshStatuses()")
    expect(card.locator("[data-status-badge]")).to_contain_text("状态未知")
    expect(card.get_by_role("switch")).to_be_disabled()


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844), (320, 720)])
def test_controls_fit_desktop_and_mobile(page, width, height):
    page.set_viewport_size({"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    setup_page(page)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for card in page.locator(".service-card").all():
        bounds = card.bounding_box()
        toggle = card.locator(".service-switch").bounding_box()
        restart = card.locator(".restart-button").bounding_box()
        link = card.locator(".card-link").bounding_box()
        assert bounds["x"] <= toggle["x"] < restart["x"]
        assert toggle["x"] + toggle["width"] <= restart["x"]
        assert restart["x"] + restart["width"] <= bounds["x"] + bounds["width"]
        assert link["y"] + link["height"] <= toggle["y"]
    assert not errors
    output = Path(__file__).resolve().parents[1] / ".test-runs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / f"portal-{width}.png"), full_page=True)
