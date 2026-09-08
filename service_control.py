import json
import logging
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys
import threading
import time

import psutil


PROJECT_CONFIG = {
    "products": {"project": "product_catalog", "command": ["start.py"]},
    "ads": {"project": "ads_dashboard", "cwd": "ads_funnel", "command": [
        "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "5001",
    ]},
    "toolkit": {"project": "amazon_toolkit", "command": ["app.py"]},
    "xiyou": {"project": "xiyou_api", "command": ["start.py"]},
    "amazon_official_sp": {"project": "amazon_sp_api", "command": ["start.py"]},
    "amazon_official_ads": {"project": "amazon_ads_api", "command": [
        "-m", "flask", "--app", "app", "run", "--host", "127.0.0.1", "--port", "5010",
    ]},
}


class ServiceController:
    def __init__(self, services, projects_root, runtime_dir, startup_timeout=30):
        self.services = services
        self.projects_root = Path(projects_root).resolve()
        self.runtime_dir = Path(runtime_dir)
        self.startup_timeout = startup_timeout
        self.lock = threading.Lock()
        self.states = {key: {"busy": False, "action": None, "error": None} for key in services}
        self.processes = {}

    def project_dir(self, key):
        override = os.environ.get(f"PORTAL_{key.upper()}_DIR")
        return Path(override or self.projects_root / self.services[key]["project"]).resolve()

    def online(self, key):
        try:
            with socket.create_connection(("127.0.0.1", self.services[key]["port"]), timeout=0.2):
                return True
        except OSError:
            return False

    def details(self, key):
        project = self.project_dir(key)
        script = project / "deploy.sh"
        with self.lock:
            result = self.states[key].copy()
        result.update({
            "can_start": project.is_dir() and platform.system() in {"Linux", "Windows"},
            "can_restart": platform.system() == "Linux" and script.is_file(),
        })
        try:
            result["restart_warning"] = "pkill -f" in script.read_text(encoding="utf-8") if script.is_file() else False
        except OSError:
            result["can_restart"] = False
            result["restart_warning"] = False
        return result

    def submit(self, key, action):
        if key not in self.services:
            raise KeyError(key)
        if action not in {"start", "stop", "restart"}:
            raise ValueError("不支持的操作")
        if platform.system() not in {"Linux", "Windows"}:
            raise RuntimeError("当前系统不支持服务控制")
        if action == "restart":
            if platform.system() != "Linux":
                raise RuntimeError("重启仅支持 Linux 服务端")
            if not (self.project_dir(key) / "deploy.sh").is_file():
                raise RuntimeError("项目目录下未找到 deploy.sh")
        if not self.project_dir(key).is_dir():
            raise RuntimeError("未找到项目目录，请检查服务配置")
        with self.lock:
            if self.states[key]["busy"]:
                raise RuntimeError("项目正在执行操作，请稍后再试")
            self.states[key] = {"busy": True, "action": action, "error": None}
        threading.Thread(target=self._execute, args=(key, action), daemon=True).start()

    def _execute(self, key, action):
        error = None
        try:
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            if action == "start":
                self.start(key)
            elif action == "stop":
                self.stop(key)
            else:
                self.restart(key)
        except (RuntimeError, ValueError) as exc:
            error = str(exc)
        except Exception:
            logging.exception("Service operation failed: %s %s", key, action)
            error = "操作失败，请检查门户日志及运行权限"
        finally:
            with self.lock:
                self.states[key].update(busy=False, action=None, error=error)

    def _owned(self, process, key):
        if process.pid == os.getpid():
            return False
        try:
            cwd = Path(process.cwd()).resolve()
            return cwd.is_relative_to(self.project_dir(key))
        except psutil.NoSuchProcess:
            return False
        except psutil.AccessDenied:
            raise RuntimeError("无法核对进程所属目录，请检查门户进程权限") from None

    def _listeners(self, key):
        port = self.services[key]["port"]
        pids = {conn.pid for conn in psutil.net_connections(kind="tcp")
                if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port}
        if None in pids:
            raise RuntimeError("无法识别监听进程，请检查门户进程权限")
        processes = []
        for pid in pids:
            try:
                process = psutil.Process(pid)
                if not self._owned(process, key):
                    raise RuntimeError("端口被其他项目占用，已取消操作")
                processes.append(process)
            except psutil.NoSuchProcess:
                continue
        return processes

    def stop_processes(self, key):
        roots = self._listeners(key)
        tracked = self.processes.get(key)
        if tracked and tracked.poll() is None:
            roots.append(psutil.Process(tracked.pid))
        targets = {}
        for process in roots:
            try:
                # Include Python launcher/reloader parents, but never a user's shell.
                parent = process.parent()
                while parent and parent.name().lower().startswith(("python", "uvicorn", "gunicorn")) and self._owned(parent, key):
                    process, parent = parent, parent.parent()
                for child in [process, *process.children(recursive=True)]:
                    if self._owned(child, key):
                        targets[child.pid] = child
            except psutil.NoSuchProcess:
                continue
        for process in targets.values():
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(list(targets.values()), timeout=5)
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(alive, timeout=3)
        if tracked:
            try:
                tracked.wait(timeout=3)
            except subprocess.TimeoutExpired:
                raise RuntimeError("项目启动进程未能停止") from None

    def _unit(self, key):
        if platform.system() != "Linux":
            return None
        saved = self.runtime_dir / f"{key}.unit.json"
        unit = os.environ.get(f"PORTAL_{key.upper()}_UNIT")
        if not unit and saved.is_file():
            unit = json.loads(saved.read_text(encoding="utf-8"))
        if not unit:
            for process in self._listeners(key):
                try:
                    cgroup = Path(f"/proc/{process.pid}/cgroup").read_text()
                except FileNotFoundError:
                    continue
                match = re.search(r"/system.slice/([^/\n]+\.service)(?:/|$)", cgroup, re.MULTILINE)
                if match:
                    unit = match.group(1)
                    break
        if unit:
            if not re.fullmatch(r"[A-Za-z0-9_.@:-]+\.service", unit) or unit.startswith("-"):
                raise RuntimeError("systemd 服务名配置无效")
            result = subprocess.run(["systemctl", "show", unit, "--property=WorkingDirectory", "--value"],
                                    capture_output=True, text=True, check=True, timeout=10)
            cwd = result.stdout.strip()
            if not cwd or not Path(cwd).resolve().is_relative_to(self.project_dir(key)):
                raise RuntimeError("systemd 服务目录与项目不匹配，已取消操作")
            saved.write_text(json.dumps(unit), encoding="utf-8")
        return unit

    def _systemctl(self, action, unit):
        subprocess.run(["systemctl", action, unit], check=True, capture_output=True, timeout=60)

    def _spawn(self, key, command, cwd):
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        with (self.runtime_dir / f"{key}.log").open("ab") as log:
            return subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, **options)

    def _wait_online(self, key, process=None):
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if process and process.poll() is not None:
                raise RuntimeError("启动进程已退出，请检查项目运行日志")
            if self.online(key):
                self._listeners(key)
                return
            time.sleep(0.25)
        raise RuntimeError("等待服务启动超时，请检查项目运行日志")

    def start(self, key):
        if self.online(key):
            self._listeners(key)
            return
        unit = self._unit(key)
        if unit:
            self._systemctl("start", unit)
            self._wait_online(key)
            return
        project = self.project_dir(key)
        cwd = project / self.services[key].get("cwd", "")
        suffix = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        candidates = [base / env / suffix for base in (cwd, project) for env in (".venv", "venv")]
        python = next((str(path) for path in candidates if path.is_file()), sys.executable)
        process = self._spawn(key, [python, *self.services[key]["command"]], cwd)
        self.processes[key] = process
        try:
            self._wait_online(key, process)
        except Exception:
            self.stop_processes(key)
            raise

    def stop(self, key):
        unit = self._unit(key)
        if unit:
            self._systemctl("stop", unit)
        self.stop_processes(key)
        deadline = time.monotonic() + 5
        while self.online(key) and time.monotonic() < deadline:
            time.sleep(0.25)
        if self.online(key):
            raise RuntimeError("服务仍在运行，请检查是否有其他进程守护程序自动拉起")

    def restart(self, key):
        unit = self._unit(key)
        self.stop(key)
        process = self._spawn(key, ["bash", "-c", "chmod +x deploy.sh && ./deploy.sh"], self.project_dir(key))
        try:
            code = process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            # Cancel the deployment process tree so a failed job cannot deploy later.
            parent = psutil.Process(process.pid)
            children = parent.children(recursive=True)
            for child in [*reversed(children), parent]:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            process.wait(timeout=5)
            raise RuntimeError("部署脚本执行超时，请检查项目运行日志") from None
        if code:
            raise RuntimeError("部署脚本执行失败，请检查项目运行日志")
        if unit:
            self.stop_processes(key)
            self._systemctl("start", unit)
        self._wait_online(key)
