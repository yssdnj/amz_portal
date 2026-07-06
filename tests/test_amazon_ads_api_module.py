from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_project_file(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_portal_shows_amazon_ads_api_card_after_xiyou_keyword():
    html = read_project_file("portal.py")

    xiyou_index = html.index("西柚关键词")
    api_index = html.index("亚马逊官方广告API")

    assert xiyou_index < api_index
    assert 'href="/amazon-official-ads/"' in html
    assert "Amazon Ads API" in html
    assert "官方广告接口授权、报表拉取、广告数据同步与管理" in html


def test_nginx_proxies_amazon_ads_api_to_port_5010():
    config = read_project_file("nginx.conf")

    assert "location = /amazon-official-ads" in config
    assert "return 301 /amazon-official-ads/;" in config
    assert "location /amazon-official-ads/" in config
    assert "proxy_pass http://127.0.0.1:5010/;" in config
    assert "sub_filter_once off;" in config
    assert "sub_filter_types application/javascript text/css;" in config
    assert """sub_filter "'/api/" "'/amazon-official-ads/api/";""" in config
    assert """sub_filter '"/api/' '"/amazon-official-ads/api/';""" in config
