"""Isolated PixlStash setup and foreground server, called by Pinokio's Python 3.12 venv."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib.metadata
import json
import os
from pathlib import Path
import runpy
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONFIG = DATA / "server-config.json"
MARKER = ROOT / "env" / "pixlstash-installed.json"
TORCH_VERSION = "2.12.1"
VISION_VERSION = "0.27.1"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def environment() -> None:
    # Set before importing any ML libraries. Do not share another app's model cache.
    for key, folder in {
        "HF_HOME": "huggingface", "TORCH_HOME": "torch", "XDG_CACHE_HOME": "xdg",
        "PIXLSTASH_BUILTIN_MODEL_DIR": "models",
        "PIXLSTASH_HUGGINGFACE_CACHE_DIR": "huggingface/hub",
    }.items():
        os.environ[key] = str(ROOT / "cache" / folder)
    home = ROOT / "cache" / "home"
    home.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(home)
    os.environ["USERPROFILE"] = str(home)
    # platformdirs uses Windows known-folder APIs, not HOME/LOCALAPPDATA alone.
    # These documented overrides keep model pointers and telemetry local too.
    os.environ["WIN_PD_OVERRIDE_LOCAL_APPDATA"] = str(ROOT / "cache" / "appdata")
    os.environ["WIN_PD_OVERRIDE_APPDATA"] = str(ROOT / "cache" / "appdata")
    os.environ["XDG_DATA_HOME"] = str(ROOT / "cache" / "appdata")
    os.environ["XDG_CONFIG_HOME"] = str(ROOT / "cache" / "config")
    os.environ["PYTHONNOUSERSITE"] = "1"
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PIXLSTASH_HOST"] = "127.0.0.1"


@contextmanager
def lifecycle_lock():
    """Wait for Pinokio's asynchronous tree stop; exclude concurrent repairs/servers."""
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (DATA / "lifecycle.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + 45
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Another PixlStash action is still running. Stop it before retrying.")
                time.sleep(0.5)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def prepare() -> dict:
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    if CONFIG.exists():
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError(f"Expected an object in {CONFIG}; restore a valid configuration.")
        return config
    config = {
        "host": "127.0.0.1", "port": 9537, "require_ssl": False,
        "cookie_secure": False, "cookie_samesite": "Lax", "log_level": "info",
        "log_file": None, "image_root": str(DATA / "images"), "default_device": "cpu",
        "cors_origins": [], "watch_folders": [],
    }
    write_json(CONFIG, config)
    return config


def selected_backend() -> str:
    if MARKER.exists():
        return json.loads(MARKER.read_text(encoding="utf-8"))["backend"]
    return "cpu"


def check_nvidia() -> None:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
        capture_output=True, text=True, check=True, timeout=20,
    )
    drivers = [int(line.strip().split(".")[0]) for line in result.stdout.splitlines() if line.strip()]
    if not drivers or min(drivers) < 580:
        raise RuntimeError("CUDA 13 requires an NVIDIA driver from branch 580 or newer. Update your driver or use CPU.")


def install(backend: str | None) -> None:
    if sys.prefix == sys.base_prefix or Path(sys.prefix).resolve() != (ROOT / "env").resolve():
        raise RuntimeError("Installation must run in this launcher's env virtual environment.")
    backend = backend or selected_backend()
    if backend not in {"cpu", "nvidia"}:
        raise ValueError("Unknown backend")
    if backend == "nvidia":
        check_nvidia()  # Validate before touching a working environment.
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("Pinokio's uv tool is missing. Complete Pinokio's required tools setup first.")
    config = prepare()
    # A failed or interrupted repair must never advertise a completed install.
    MARKER.unlink(missing_ok=True)
    index = "cu130" if backend == "nvidia" else "cpu"
    subprocess.run([
        uv, "pip", "install", "--python", sys.executable, "--reinstall-package", "torch",
        "--reinstall-package", "torchvision", f"torch=={TORCH_VERSION}", f"torchvision=={VISION_VERSION}",
        "--index-url", f"https://download.pytorch.org/whl/{index}",
    ], check=True)
    subprocess.run([
        uv, "pip", "install", "--python", sys.executable, "--upgrade", "--only-binary", ":all:",
        "-r", str(ROOT / "requirements.txt"),
    ], check=True)
    subprocess.run([uv, "pip", "check", "--python", sys.executable], check=True)
    subprocess.run([sys.executable, str(Path(__file__).resolve()), "verify", "--backend", backend], check=True)
    config["default_device"] = "cuda" if backend == "nvidia" else "cpu"
    write_json(CONFIG, config)
    write_json(MARKER, {"backend": backend, "pixlstash": importlib.metadata.version("pixlstash")})
    print(f"Installed PixlStash ({backend}). Click Start, then Open WebUI.", flush=True)


def verify(backend: str) -> None:
    import torch
    import torchvision  # noqa: F401
    import onnxruntime  # noqa: F401
    import insightface  # noqa: F401
    from pixlstash.app import build_parser

    build_parser().parse_args(["--server-config", str(CONFIG)])
    import importlib.resources
    frontend = importlib.resources.files("pixlstash").joinpath("frontend/dist/index.html")
    if not frontend.is_file():
        raise RuntimeError("Installed PixlStash wheel is missing the WebUI.")
    if backend == "nvidia":
        if not torch.cuda.is_available():
            raise RuntimeError("PyTorch cannot use CUDA. Check the driver, then retry NVIDIA or choose CPU repair.")
        print("CUDA tensor test:", (torch.ones(2, device="cuda") + 1).cpu().tolist())
    print("Imports and packaged WebUI verified.", flush=True)


def available_port(preferred: int) -> int:
    if not 1 <= preferred <= 65535:
        raise ValueError("Server port must be between 1 and 65535")
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
        except OSError:
            sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def report_ready(port: int) -> None:
    url = f"http://127.0.0.1:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        try:
            with opener.open(url + "/version", timeout=3) as response:
                json.load(response)
            with opener.open(url + "/", timeout=3) as response:
                if response.status == 200 and b"<html" in response.read().lower():
                    print(f"\nPIXLSTASH_READY={url}", flush=True)
                    return
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(1)
    print("WebUI did not become ready within 15 minutes. Check the server log and model downloads.", file=sys.stderr, flush=True)


def serve() -> None:
    if not MARKER.exists():
        raise RuntimeError("Install PixlStash before starting the server.")
    config = prepare()
    port = available_port(int(config.get("port", 9537)))
    # Upstream's startup checks inspect the config before applying the environment
    # override. Persist the fallback so the checks and the listener use one port.
    if config.get("port") != port:
        config["port"] = port
        write_json(CONFIG, config)
    os.environ["PIXLSTASH_PORT"] = str(port)
    os.environ["PIXLSTASH_DEFAULT_DEVICE"] = "cuda" if selected_backend() == "nvidia" else "cpu"
    threading.Thread(target=report_ready, args=(port,), daemon=True).start()
    print(f"Starting PixlStash on loopback port {port}. First launch may download AI models.", flush=True)
    # Run in the foreground so Pinokio owns the server process and can stop its tree.
    sys.argv = ["pixlstash-server", "--server-config", str(CONFIG)]
    runpy.run_module("pixlstash.app", run_name="__main__")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "serve", "verify", "prepare", "update-code"])
    parser.add_argument("--backend", choices=["cpu", "nvidia"])
    args = parser.parse_args()
    environment()
    if args.action == "verify":
        verify(args.backend or selected_backend())
    else:
        with lifecycle_lock():
            if args.action == "install":
                install(args.backend)
            elif args.action == "serve":
                serve()
            elif args.action == "update-code":
                subprocess.run(["git", "-C", str(ROOT), "pull", "--ff-only"], check=True)
            else:
                prepare()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"PIXLSTASH_ERROR: {exc}", file=sys.stderr, flush=True)
        raise
