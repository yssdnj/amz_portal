from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_project_file(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_portal_shows_sp_api_card_between_xiyou_and_ads_api():
    source = read_project_file("portal.py")

    xiyou_index = source.index("西柚关键词")
    sp_api_index = source.index("亚马逊官方SP API")
    ads_api_index = source.index("亚马逊官方广告API")

    assert xiyou_index < sp_api_index < ads_api_index
    assert 'href="/amazon-official-sp/"' in source
    assert 'data-service="amazon_official_sp"' in source
    assert '"amazon_official_sp": {"name": "亚马逊官方SP API", "port": 8015}' in source
    assert "Amazon Selling Partner API" in source


def test_nginx_proxies_sp_api_and_rewrites_absolute_asset_paths():
    config = read_project_file("nginx.conf")

    assert "location = /amazon-official-sp" in config
    assert "return 301 /amazon-official-sp/;" in config
    assert "location /amazon-official-sp/" in config
    assert "proxy_pass http://127.0.0.1:8015/;" in config
    assert "sub_filter_once off;" in config
    assert "sub_filter_types application/javascript text/css;" in config
    assert """sub_filter "'/api/" "'/amazon-official-sp/api/";""" in config
    assert """sub_filter '\"/api/' '\"/amazon-official-sp/api/';""" in config
    assert """sub_filter "'/static/" "'/amazon-official-sp/static/";""" in config
    assert """sub_filter '\"/static/' '\"/amazon-official-sp/static/';""" in config


def test_nginx_places_sp_api_route_between_xiyou_and_ads_api():
    config = read_project_file("nginx.conf")

    assert (
        config.index("location /xiyou/")
        < config.index("location /amazon-official-sp/")
        < config.index("location /amazon-official-ads/")
    )
