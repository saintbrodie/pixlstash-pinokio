# PixlStash for Pinokio

Windows-first Pinokio launcher for [PixlStash](https://github.com/Pikselkroken/pixlstash), a local image library with AI search, tagging and ComfyUI integration. Installs the published Python wheel, including its built WebUI; no frontend build, Docker, system Python or standalone PixlStash installer is needed.

## Install and run

1. In Pinokio, choose **Download** and enter `https://github.com/saintbrodie/pixlstash-pinokio`.
2. Open the downloaded app and choose **Install PixlStash (CPU)**. Allow Pinokio to install its required tools if prompted. This launcher needs Pinokio's Node and uv tools.
3. Choose **Start**, follow the server log, then choose **Open WebUI** when it appears. Complete PixlStash's initial account setup in the WebUI.

The first install downloads a private, managed Python 3.12 and the Python dependencies. First startup/inference can also download several GB of AI models and take time. Internet access and sufficient free disk space are required. Windows x64 is the validated target; macOS, Linux, AMD and Intel GPU acceleration have not been validated.

The server listens on `127.0.0.1`, normally port `9537`. If the configured port is occupied, Start selects an available port, saves it, and supplies the actual WebUI link. Wait for **Open WebUI**; a download URL in the log does not count as readiness. The link is exposed only after the server API and HTML both respond.

## Stop, update and repair

- **Stop** stops this launcher's foreground server through Pinokio. Pinokio's own script stop control is also available.
- **Update** stops the server, fast-forwards this launcher with `git pull --ff-only`, then installs the maintained, tested package versions. The selected CPU/NVIDIA backend is retained. Updates do not automatically start the server.
- **Use CPU / repair installation** reinstalls the CPU backend and verifies the application. An interrupted install returns to the installation menu; run it again to repair.

PixlStash is currently pinned to **2.0.1**. Updates adopt newer application releases when the launcher's requirements are updated and tested, rather than silently tracking untested PyPI releases. Local conflicting edits or diverged Git history cause Update to stop with an error. Logs remain available in Pinokio.

## NVIDIA acceleration (optional)

After the CPU installation, choose **Enable NVIDIA (CUDA 13)**, then Start. This downloads the larger PyTorch CUDA wheels and verifies an actual CUDA tensor operation before declaring installation complete. Requires an NVIDIA GPU and a working **580-series or newer** NVIDIA driver. Install an appropriate current driver for your GPU; no separate CUDA Toolkit is required. The launcher never installs or changes GPU drivers.

PyTorch-based inference uses NVIDIA acceleration. ONNX Runtime remains the CPU distribution, so ONNX face processing uses CPU. The maintained PyTorch 2.12 wheels require CUDA 13; this launcher does not substitute incompatible CUDA 12.8 wheels. Choose CPU repair if your GPU/driver cannot run this backend. A failed driver preflight leaves the completed CPU installation intact; failures during package replacement require repair.

## Storage and configuration

Everything below is relative to the downloaded launcher, with no hardcoded drive or username:

| Directory | Contents |
| --- | --- |
| `env/` | Private Python environment and successful-install marker |
| `data/server-config.json` | Server settings, including image storage and selected device |
| `data/` | Hub database, libraries, imported images and other application state |
| `cache/` | Managed Python, package downloads, models and app-specific user directories |

Installation preserves existing server settings. The backend actions change only the device setting; port fallback updates only the port. `data/`, `cache/` and `env/` are excluded from Git. Model downloads use this app's caches. No other Pinokio app or Python environment is modified. Pinokio may provision shared tools during its own first-run requirements setup.

For a different library location, stop the server and edit `image_root` in `data/server-config.json` **before first startup**, or use PixlStash's library management after creating a library. Keep the local HTTP/loopback configuration when using this launcher. Remote hosting and custom HTTPS are outside its tested scope.

Back up `data/` and any libraries stored elsewhere while the server is stopped before upgrading. Repair/update preserves data, but a newer upstream release can migrate databases. Deleting the downloaded app directory also deletes any libraries stored inside it. For migration to another machine, back up the libraries/config, clone the launcher there and reinstall its environment; generated configs can contain absolute library paths that need adjusting.

## Development and verification

```powershell
node --test tests/launcher.test.js
python -m unittest discover -s tests -p 'test_*.py' -v
# With uv on PATH:
node scripts/run.js install --backend cpu
env/Scripts/python.exe -s -u tests/smoke.py
```

The smoke test uses a temporary library under `.test-data/`, disables background ML workers, tests an occupied port, fetches the real WebUI and its assets, checks first-run database creation, and stops the server. It never opens your actual library. A GitHub Actions Windows workflow performs the CPU installation and smoke test on each push/PR. See [TESTING.md](TESTING.md) for local results and limitations.

When upgrading dependencies, update `requirements.txt` and regenerate `constraints.txt` from a verified clean Windows environment, excluding the backend-specific torch/torchvision local versions. Retest CPU and NVIDIA; upstream's native dependencies and packaged frontend can change independently.
