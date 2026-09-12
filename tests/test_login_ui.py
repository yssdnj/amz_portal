from pathlib import Path

import pytest


playwright = pytest.importorskip("playwright.sync_api")
expect = playwright.expect


@pytest.fixture
def page():
    with playwright.sync_playwright() as engine:
        try:
            browser = engine.chromium.launch(channel="chrome", headless=True)
        except playwright.Error as exc:
            pytest.skip(f"Chrome unavailable: {exc}")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        yield page
        browser.close()


def render_login(next_path="/amazon/"):
    try:
        from login_page import render_login_page
    except ImportError:
        pytest.fail("login_page renderer is missing")
    return render_login_page(next_path, "/amazon")


def open_login(page, html):
    page.route(
        "https://example.test/amazon/login",
        lambda route: route.fulfill(body=html, content_type="text/html"),
    )
    page.goto("https://example.test/amazon/login")


def test_login_form_submits_with_enter_and_reveals_password(page):
    html = render_login()
    requests = []
    page.route(
        "https://example.test/amazon/",
        lambda route: route.fulfill(body="signed in", content_type="text/plain"),
    )

    def login(route):
        requests.append(route.request.post_data_json)
        route.fulfill(json={"redirect": "/amazon/"})

    page.route("**/api/auth/login", login)
    open_login(page, html)

    expect(page.get_by_role("heading", name="登录 Amazon 工具中心")).to_be_visible()
    page.get_by_label("账号").fill("test-user")
    password = page.get_by_label("密码", exact=True)
    password.fill("test-password")
    page.get_by_role("button", name="显示密码").click()
    expect(password).to_have_attribute("type", "text")
    expect(page.get_by_role("button", name="隐藏密码")).to_be_visible()
    password.press("Enter")
    expect(page).to_have_url("https://example.test/amazon/")
    assert requests == [{
        "username": "test-user",
        "password": "test-password",
        "next": "/amazon/",
    }]


def test_login_shows_loading_and_generic_invalid_credentials_error(page):
    html = render_login()
    page.add_init_script("""
        window.fetch = () => new Promise((resolve) => {
          window.resolveLogin = resolve;
        });
    """)
    open_login(page, html)
    page.get_by_label("账号").fill("test-user")
    password = page.get_by_label("密码", exact=True)
    password.fill("test-password")
    page.get_by_role("button", name="登录").click()

    submit = page.get_by_role("button", name="登录中")
    expect(submit).to_be_disabled()
    page.evaluate("""
        window.resolveLogin(new Response(
          JSON.stringify({detail: '账号或密码不正确'}),
          {status: 401, headers: {'Content-Type': 'application/json'}}
        ));
    """)
    expect(page.get_by_role("alert")).to_have_text("账号或密码不正确")
    expect(page.get_by_role("button", name="登录")).to_be_enabled()
    expect(password).to_have_value("")


@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844), (320, 720)])
def test_login_layout_has_no_overflow(page, width, height):
    html = render_login()
    page.set_viewport_size({"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    open_login(page, html)

    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    form = page.locator("form").bounding_box()
    assert form["x"] >= 0
    assert form["x"] + form["width"] <= width
    assert not errors
    output = Path(__file__).resolve().parents[1] / ".test-runs" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / f"login-{width}.png"), full_page=True)
