# PixlStash for Pinokio

PixlStash is a self-hosted image manager for photographers and AI creators. Use it to organize large libraries, find images by meaning, prepare LoRA training sets, and reuse the ComfyUI workflows that produced your images. AI processing runs on your hardware. [Official PixlStash site](https://pikselkroken.github.io/pixlstash/)

## What you can do

- **Find images** with CLIP semantic search, face recognition, and text extracted from pictures.
- **Curate your library** with automatic tags and captions, image quality and anomaly scores, and a queue for reviewing AI labels. [PixlStash AI features](https://pikselkroken.github.io/pixlstash/ai.html)
- **Develop LoRAs from your library** by curating an image set and reviewing its tags and captions. Select a person or set and choose **Train LoRA**. PixlStash attaches the trained adapter to that person or set when the run finishes. [PixlStash 2.0 release notes](https://pikselkroken.github.io/pixlstash/whatsnew.html)
- **Reuse ComfyUI workflows** by collecting them from your images and running them from your library. [ComfyUI integration](https://pikselkroken.github.io/pixlstash/comfyui.html)

This Windows-first Pinokio launcher installs the published PixlStash 2.0.1 Python package and its bundled WebUI in a private environment. The official site tracks upstream releases and may describe features added after this version.

## Install and run

Choose a launcher action to run it. Opening PixlStash in Pinokio leaves installation and startup under your control.

1. In Pinokio, choose **Download** and enter `https://github.com/saintbrodie/pixlstash-pinokio`.
2. Open the downloaded app and choose **Install PixlStash (CPU)** or **Install PixlStash (NVIDIA CUDA 13)**. Allow Pinokio to install its required Node and uv tools if prompted.
3. Choose **Start** to see startup progress. When **Open WebUI** appears, select it to open PixlStash in your default browser. Complete initial account setup there.

Use the browser opened by **Open WebUI** for sign-in. Pinokio's embedded view can block the session cookie when it loads PixlStash across sites, which sends you back to the sign-in page.

The first install downloads a private, managed Python 3.12 and the Python dependencies. First startup/inference can also download several GB of AI models and take time. Internet access and sufficient free disk space are required. Windows x64 is the validated target; macOS, Linux, AMD and Intel GPU acceleration have not been validated.

The server listens on `127.0.0.1`, normally port `9537`. If the configured port is occupied, Start selects an available port, saves it, and supplies the actual WebUI link after the PixlStash API and HTML both respond.

If startup ends early or the server exits unexpectedly, Pinokio returns to the stopped menu. Look for `PIXLSTASH_FATAL` in the Start log for the failure category. Readiness times out after about 15 minutes. The preceding log preserves the application's warnings, model download progress, and error details.

## Stop, update and repair

- **Stop** asks the foreground server to shut down and close its databases. Pinokio stops the process tree if the server does not finish within 20 seconds.
- **Update** stops the server, fast-forwards this launcher with `git pull --ff-only`, then installs the maintained, tested package versions. The selected CPU/NVIDIA backend is retained. Updates do not automatically start the server.
- **Use CPU / repair installation** reinstalls the CPU backend and verifies the application. An interrupted install returns to the installation menu; run it again to repair.

PixlStash is currently pinned to **2.0.1**. Updates adopt newer application releases when the launcher's requirements are updated and tested, rather than silently tracking untested PyPI releases. Local conflicting edits or diverged Git history cause Update to stop with an error. Logs remain available in Pinokio.

For launcher-only updates, stop PixlStash and run `git pull --ff-only` from the launcher folder on its `main` branch. Reload the app in Pinokio and select **Start**. Your Python environment, library, and downloaded models stay in place.

## Check the server API

Use the URL shown in **Open WebUI** in place of `http://127.0.0.1:9537` if Pinokio chose a different port. `GET /version` returns a JSON document with the PixlStash version.

```powershell
curl.exe http://127.0.0.1:9537/version
```

```javascript
const response = await fetch("http://127.0.0.1:9537/version");
console.log(await response.json());
```

```python
import json
from urllib.request import urlopen

with urlopen("http://127.0.0.1:9537/version") as response:
    print(json.load(response))
```

## NVIDIA acceleration (optional)

Choose **Install PixlStash (NVIDIA CUDA 13)** during setup, or **Enable NVIDIA (CUDA 13)** from an existing installation. Then choose **Start**. NVIDIA setup downloads the larger PyTorch CUDA wheels and verifies a CUDA tensor operation before declaring installation complete. It requires an NVIDIA GPU and a working **580-series or newer** NVIDIA driver. The launcher uses your installed GPU driver and the CUDA libraries in PyTorch.

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
node --test tests/launcher.test.js tests/uv-bootstrap.test.js
python -m unittest discover -s tests -p 'test_*.py' -v
# With uv on PATH:
node scripts/run.js install --backend cpu
env/Scripts/python.exe -s -u tests/smoke.py
```

The smoke test uses a temporary library under `.test-data/`, disables background ML workers, tests an occupied port, fetches the real WebUI and its assets, checks first-run database creation, and verifies that the Stop request closes the listener after a graceful shutdown. A GitHub Actions Windows workflow performs the CPU installation and smoke test on each push/PR. See [TESTING.md](TESTING.md) for local results and limitations.

When upgrading dependencies, update `requirements.txt` and regenerate `constraints.txt` from a verified clean Windows environment, excluding the backend-specific torch/torchvision local versions. Retest CPU and NVIDIA; upstream's native dependencies and packaged frontend can change independently.
