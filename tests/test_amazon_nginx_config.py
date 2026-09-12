from pathlib import Path


CONFIG = Path(__file__).resolve().parents[1] / "amazon.conf"


def location_block(config, signature):
    start = config.index(signature)
    end = config.index("\n}", start)
    return config[start:end]


def test_amazon_gateway_uses_an_independent_session_check():
    config = CONFIG.read_text(encoding="utf-8")
    block = location_block(config, "location = /_amazon_session {")

    assert "internal;" in block
    assert "proxy_pass http://127.0.0.1:5000/api/auth/check;" in block
    assert "proxy_pass_request_body off;" in block
    assert "proxy_set_header Content-Length \"\";" in block
    assert "proxy_set_header Cookie $http_cookie;" in block
    assert "auth_request /_session;" not in config
    assert "@stock_login_required" not in config


def test_login_routes_are_public_exact_locations_before_protected_api():
    config = CONFIG.read_text(encoding="utf-8")
    protected_api = config.index("location ^~ /amazon/api/")

    for signature in [
        "location = /amazon/login {",
        "location = /amazon/api/auth/login {",
        "location = /amazon/api/auth/logout {",
    ]:
        assert config.index(signature) < protected_api
        assert "auth_request" not in location_block(config, signature)


def test_amazon_page_and_api_prefixes_have_their_own_auth_behavior():
    config = CONFIG.read_text(encoding="utf-8")
    api_locations = [
        "/amazon/api/",
        "/amazon/products/api/",
        "/amazon/ads/api/",
        "/amazon/toolkit/api/",
        "/amazon/xiyou/api/",
        "/amazon/official-sp/api/",
        "/amazon/official-ads/api/",
    ]
    page_locations = [
        "/amazon/products/",
        "/amazon/ads/",
        "/amazon/toolkit/",
        "/amazon/xiyou/",
        "/amazon/official-sp/",
        "/amazon/official-ads/",
        "/amazon/",
    ]

    for path in api_locations:
        block = location_block(config, f"location ^~ {path} {{")
        assert "auth_request /_amazon_session;" in block
        assert "error_page 401" not in block
    for path in page_locations:
        block = location_block(config, f"location ^~ {path} {{")
        assert "auth_request /_amazon_session;" in block
        assert "error_page 401 = @amazon_login_required;" in block


def test_amazon_login_redirect_and_canonical_root_are_prefix_aware():
    config = CONFIG.read_text(encoding="utf-8")

    assert "location = /amazon { return 308 /amazon/; }" in config
    redirect = location_block(config, "location @amazon_login_required {")
    assert "return 302 /amazon/login?next=$uri;" in redirect
