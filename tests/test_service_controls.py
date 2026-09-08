import socket
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

import portal


@pytest.fixture
def client():
    return TestClient(portal.app, client=("127.0.0.1", 12345))


def test_control_endpoints_reject_unknown_services(client):
    response = client.post("/api/services/unknown/start", headers={"X-Portal-Control": "1"})
    assert response.status_code == 404


def test_restart_is_rejected_on_windows(client, monkeypatch):
    monkeypatch.setattr(portal.platform, "system", lambda: "Windows")
    response = client.post("/api/services/ads/restart", headers={"X-Portal-Control": "1"})
    assert response.status_code == 409


def test_control_requires_same_origin_custom_header(client):
    assert client.post("/api/services/ads/stop").status_code == 403
    response = client.post("/api/services/ads/stop", headers={
        "X-Portal-Control": "1", "Origin": "https://untrusted.example",
    })
    assert response.status_code == 403


def test_remote_control_requires_configured_token(monkeypatch):
    monkeypatch.delenv("PORTAL_CONTROL_TOKEN", raising=False)
    client = TestClient(portal.app, client=("203.0.113.1", 12345))
    assert client.post("/api/services/ads/stop", headers={"X-Portal-Control": "1"}).status_code == 403
    monkeypatch.setenv("PORTAL_CONTROL_TOKEN", "test-admin-key")
    assert client.post("/api/services/ads/stop", headers={"X-Portal-Control": "1"}).status_code == 401
    response = client.post("/api/services/unknown/stop", headers={
        "X-Portal-Control": "1", "Authorization": "Bearer test-admin-key",
    })
    assert response.status_code == 404


def test_nginx_forwarded_client_is_not_treated_as_local(client, monkeypatch):
    monkeypatch.delenv("PORTAL_CONTROL_TOKEN", raising=False)
    response = client.post("/api/services/ads/stop", headers={
        "X-Portal-Control": "1", "X-Forwarded-For": "203.0.113.5",
    })
    assert response.status_code == 403


def make_controller(tmp_path, port, command):
    from service_control import ServiceController

    project = tmp_path / "example"
    project.mkdir()
    return ServiceController({"example": {
        "name": "Example", "port": port, "project": "example", "command": command,
    }}, tmp_path, tmp_path / "runtime", startup_timeout=5)


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_operation(controller):
    deadline = time.monotonic() + 10
    while controller.details("example")["busy"] and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not controller.details("example")["busy"]
    return controller.details("example")


def test_switch_starts_and_stops_real_owned_service(tmp_path):
    port = unused_port()
    controller = make_controller(tmp_path, port, ["-m", "http.server", str(port), "--bind", "127.0.0.1"])
    try:
        controller.submit("example", "start")
        result = wait_for_operation(controller)
        assert result["error"] is None
        assert controller.online("example")
        controller.submit("example", "stop")
        result = wait_for_operation(controller)
        assert result["error"] is None
        assert not controller.online("example")
    finally:
        controller.stop_processes("example")


def test_pause_refuses_process_from_another_project(tmp_path):
    port = unused_port()
    controller = make_controller(tmp_path, port, ["missing.py"])
    foreign = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                               cwd=tmp_path, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 5
        while not controller.online("example") and time.monotonic() < deadline:
            time.sleep(0.05)
        controller.submit("example", "stop")
        result = wait_for_operation(controller)
        assert result["error"]
        assert foreign.poll() is None
    finally:
        foreign.terminate()
        foreign.wait(timeout=5)


def test_failed_start_is_reported_and_unlocks_controls(tmp_path):
    controller = make_controller(tmp_path, unused_port(), ["missing.py"])
    controller.submit("example", "start")
    result = wait_for_operation(controller)
    assert result["error"]
    assert not controller.online("example")


def test_concurrent_operations_on_same_service_are_rejected(tmp_path):
    controller = make_controller(tmp_path, unused_port(), ["-c", "import time; time.sleep(2)"])
    controller.submit("example", "start")
    with pytest.raises(RuntimeError, match="正在"):
        controller.submit("example", "stop")
    wait_for_operation(controller)


def test_missing_deploy_script_is_rejected_before_stopping_service(tmp_path, monkeypatch):
    import service_control

    monkeypatch.setattr(service_control.platform, "system", lambda: "Linux")
    controller = make_controller(tmp_path, unused_port(), ["missing.py"])
    with pytest.raises(RuntimeError, match="deploy.sh"):
        controller.submit("example", "restart")


def test_api_returns_accepted_and_actual_operation_result(client, tmp_path, monkeypatch):
    controller = make_controller(tmp_path, unused_port(), ["missing.py"])
    monkeypatch.setattr(portal, "controller", controller)
    monkeypatch.setattr(portal, "SERVICES", controller.services)
    response = client.post("/api/services/example/start", headers={"X-Portal-Control": "1"})
    assert response.status_code == 202
    wait_for_operation(controller)
    result = client.get("/api/status").json()["services"]["example"]
    assert result["busy"] is False
    assert result["online"] is False
    assert result["error"]


@pytest.mark.parametrize("exit_code", [0, 1])
def test_linux_restart_runs_project_deploy_and_reports_exit_code(tmp_path, monkeypatch, exit_code):
    import service_control

    controller = make_controller(tmp_path, unused_port(), ["missing.py"])
    project = tmp_path / "example"
    (project / "deploy.sh").write_text("#!/bin/bash\nexit 0\n")
    monkeypatch.setattr(service_control.platform, "system", lambda: "Linux")
    commands = []
    online = {"value": False}

    class Deployment:
        def wait(self, timeout):
            online["value"] = exit_code == 0
            return exit_code

    def spawn(command, **kwargs):
        commands.append((command, kwargs["cwd"]))
        return Deployment()

    monkeypatch.setattr(service_control.subprocess, "Popen", spawn)
    monkeypatch.setattr(service_control.psutil, "net_connections", lambda **kwargs: [])
    monkeypatch.setattr(controller, "online", lambda key: online["value"])
    controller.submit("example", "restart")
    result = wait_for_operation(controller)
    assert commands == [(["bash", "-c", "chmod +x deploy.sh && ./deploy.sh"], project)]
    assert bool(result["error"]) == (exit_code != 0)


def test_systemd_pause_stops_unit_and_remembers_it_for_start(tmp_path, monkeypatch):
    import service_control

    controller = make_controller(tmp_path, unused_port(), ["missing.py"])
    monkeypatch.setattr(service_control.platform, "system", lambda: "Linux")
    monkeypatch.setenv("PORTAL_EXAMPLE_UNIT", "example.service")
    monkeypatch.setattr(service_control.psutil, "net_connections", lambda **kwargs: [])
    active = {"value": True}
    commands = []

    def systemctl(command, **kwargs):
        commands.append(command)
        if command[1] == "show":
            return subprocess.CompletedProcess(command, 0, str(tmp_path / "example") + "\n", "")
        active["value"] = command[1] == "start"
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(service_control.subprocess, "run", systemctl)
    monkeypatch.setattr(controller, "online", lambda key: active["value"])
    controller.submit("example", "stop")
    assert wait_for_operation(controller)["error"] is None
    assert not active["value"]
    monkeypatch.delenv("PORTAL_EXAMPLE_UNIT")
    controller.submit("example", "start")
    assert wait_for_operation(controller)["error"] is None
    assert active["value"]
    assert [command[:3] for command in commands if command[1] != "show"] == [
        ["systemctl", "stop", "example.service"], ["systemctl", "start", "example.service"],
    ]
