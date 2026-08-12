import socket

from fastapi.testclient import TestClient

import portal


def test_service_status_marks_open_and_closed_ports(monkeypatch):
    open_ports = {5001, 5010}

    def fake_create_connection(address, timeout):
        host, port = address
        assert host == "127.0.0.1"
        assert timeout == 0.2
        if port not in open_ports:
            raise OSError("connection refused")
        return DummySocket()

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)

    statuses = portal.get_service_statuses()

    assert statuses["ads"]["online"] is True
    assert statuses["ads"]["port"] == 5001
    assert statuses["toolkit"]["online"] is False
    assert statuses["products"]["port"] == 5003
    assert statuses["xiyou"]["port"] == 5004
    assert statuses["amazon_official_sp"]["online"] is False
    assert statuses["amazon_official_sp"]["port"] == 8015
    assert statuses["amazon_official_ads"]["online"] is True
    assert statuses["amazon_official_ads"]["port"] == 5010


def test_status_api_returns_module_statuses(monkeypatch):
    monkeypatch.setattr(
        portal,
        "get_service_statuses",
        lambda: {
            "ads": {"name": "广告漏斗分析", "port": 5001, "online": True},
            "toolkit": {"name": "运营工具箱", "port": 5002, "online": False},
        },
    )

    response = TestClient(portal.app).get("/api/status")

    assert response.status_code == 200
    assert response.json() == {
        "services": {
            "ads": {"name": "广告漏斗分析", "port": 5001, "online": True},
            "toolkit": {"name": "运营工具箱", "port": 5002, "online": False},
        }
    }


def test_portal_badges_are_updated_by_status_script():
    html = portal.HTML

    assert 'data-service="products"' in html
    assert 'data-local-url="http://127.0.0.1:5003/"' in html
    assert 'data-service="ads"' in html
    assert 'data-local-url="http://127.0.0.1:5001/"' in html
    assert 'data-service="toolkit"' in html
    assert 'data-local-url="http://127.0.0.1:5002/"' in html
    assert 'data-service="xiyou"' in html
    assert 'data-local-url="http://127.0.0.1:5004/"' in html
    assert 'data-service="amazon_official_sp"' in html
    assert 'data-local-url="http://127.0.0.1:8015/"' in html
    assert 'data-service="amazon_official_ads"' in html
    assert 'data-local-url="http://127.0.0.1:5010/"' in html
    assert "检测中" in html
    assert "fetch('/api/status')" in html
    assert "useLocalModuleLinks" in html
    assert "未启动" in html


class DummySocket:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
