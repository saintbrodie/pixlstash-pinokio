"""Exercise the real launcher server using a disposable library and no model downloads.

Run with env/Scripts/python.exe tests/smoke.py (Windows) or env/bin/python tests/smoke.py.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def load_manager(directory):
    spec = importlib.util.spec_from_file_location("manage", ROOT / "scripts/manage.py")
    manage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manage)
    manage.ROOT = directory
    manage.DATA = directory
    manage.CONFIG = directory / "server-config.json"
    return manage


def child(directory):
    manage = load_manager(directory)
    manage.environment()
    os.environ["PIXLSTASH_TELEMETRY_DEV"] = "1"
    with manage.lifecycle_lock():
        manage.serve()


def run():
    parent = ROOT / ".test-data"
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="Smoke with spaces ", dir=parent) as temporary:
        directory = Path(temporary)
        # Occupy the requested port to exercise the launcher's automatic fallback.
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            config = {
                "host": "127.0.0.1", "port": port, "require_ssl": False,
                "cookie_secure": False, "cookie_samesite": "Lax", "log_level": "info",
                "log_file": None, "image_root": str(directory / "images"),
                "default_device": "cpu", "disable_background_workers": True,
                "cors_origins": [], "watch_folders": [],
            }
            (directory / "server-config.json").write_text(json.dumps(config), encoding="utf-8")
            log = directory / "server.log"
            with log.open("w", encoding="utf-8") as output:
                process = subprocess.Popen(
                    [sys.executable, "-s", "-u", str(Path(__file__).resolve()), "--child", str(directory)],
                    cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
                try:
                    deadline = time.monotonic() + 240
                    url = None
                    while time.monotonic() < deadline:
                        text = log.read_text(encoding="utf-8", errors="replace")
                        match = re.search(r"PIXLSTASH_READY=(http://127\.0\.0\.1:(\d+))", text)
                        if match:
                            url = match[1]
                            assert int(match[2]) != port, "Occupied port was reused"
                            break
                        if process.poll() is not None:
                            raise RuntimeError(f"Server exited with {process.returncode}\n{text}")
                        time.sleep(1)
                    if not url:
                        raise RuntimeError("Readiness timed out\n" + text)
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    with opener.open(url + "/version", timeout=10) as response:
                        version = json.load(response)
                    with opener.open(url + "/", timeout=10) as response:
                        html = response.read().decode("utf-8")
                    assert '<div id="app"' in html, "Missing SPA mount point"
                    assets = re.findall(r'(?:src|href)="(/assets/[^" ]+)"', html)
                    assert assets, "No frontend assets found"
                    for asset in assets:
                        with opener.open(url + asset, timeout=10) as response:
                            assert response.status == 200 and response.read(), asset
                    assert (directory / "hub.db").exists(), "Hub database was not created"
                    with opener.open(url + "/api/v1/login", timeout=10) as response:
                        assert json.load(response)["needs_registration"] is True
                    registration = urllib.request.Request(
                        url + "/api/v1/login", method="POST",
                        data=json.dumps({"username": "smoke-user", "password": "Disposable-smoke-test-123"}).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    with opener.open(registration, timeout=10) as response:
                        assert response.status == 200
                    with opener.open(url + "/api/v1/login", timeout=10) as response:
                        assert json.load(response)["needs_registration"] is False
                    print("PASS: first-run account registration through the WebUI API")
                    print("PASS: readiness, occupied port fallback, version, WebUI, assets, first-run database:", version)
                    load_manager(directory).stop_server()
                    process.wait(timeout=45)
                    stopped_log = log.read_text(encoding="utf-8", errors="replace")
                    assert process.returncode == 0, stopped_log
                    assert "Application shutdown complete" in stopped_log, stopped_log
                    assert "PixlStash shut down on request." in stopped_log, stopped_log
                    assert "PIXLSTASH_FATAL:" not in stopped_log, stopped_log
                    print("PASS: Stop request ran Uvicorn shutdown and exited successfully")
                    try:
                        opener.open(url + "/version", timeout=2)
                    except OSError:
                        print("PASS: stopped server no longer accepts requests")
                    else:
                        raise RuntimeError("Server still reachable after stop")
                finally:
                    if process.poll() is None:
                        try:
                            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
                            process.wait(timeout=45)
                        except (OSError, subprocess.TimeoutExpired):
                            if os.name == "nt":
                                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False, capture_output=True)
                            else:
                                process.kill()
                            process.wait(timeout=20)
                    # Retain a log outside the temporary library for troubleshooting.
                    (parent / "last-smoke.log").write_text(log.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(Path(sys.argv[2]))
    else:
        run()
