# Startup lifecycle verification — November 17, 2026

Pinokio 8.3.7 injects `/error:/i` and `/errno /i` break handlers in its bundled `kernel/shells.js`. It scans both the terminal stream and the response collected when the shell detaches. The failed Start reported `input.event = ["error:"]` immediately after the INFO line from the `uvicorn.error` logger. Pinokio stopped the script before the `local.set` step could record the WebUI URL.

| Check | Result |
| --- | --- |
| Windows 11, Pinokio 8.3.7, PixlStash 2.0.1 | Started through `pterm` with the existing managed Python 3.12 CPU installation. The normal Uvicorn INFO line remained in the log. |
| Running sidebar and sustained uptime | Pinokio reported an online server and rendered **Open WebUI**, **Server Log**, and **Stop**. The actual URL responded to HTTP after more than 60 seconds. |
| Stop and restart | Ran the launcher’s Stop script through Pinokio. The server logged `Application shutdown complete` and `PixlStash shut down on request`. Pinokio returned to the stopped menu, and both the server process and listener exited. A subsequent Pinokio launch served the WebUI again. |
| Regression suites | JavaScript and Python tests cover menu states, Uvicorn logs, fatal output, HTTP readiness, port fallback, readiness timeout, and unexpected returns from the server. |
| Isolated smoke | Real WebUI and assets, account registration, automatic port fallback, and cooperative shutdown with a disposable library and cache. |

Fatal startup and unexpected-exit cases were exercised by the regression suites using controlled failures. The live Pinokio test used the existing CPU installation.

## Earlier installer verification — November 16, 2026

## Environment inspected before implementation

- Existing Pinokio home: `F:\AI\pinokio`, desktop version **8.3.7**, confirmed from its configuration and bundled application code.
- Home contains `api`, `bin`, `cache`, `checkpoints`, `config`, `drive`, `logs`, `plugin`, `scripts`, `skills`, and `tasks`.
- Both `api` and `bin` were empty. No unrelated apps or Python environments were altered. They remained empty after testing.
- Pinokio's local HTTP service responded, but `GET /pinokio/path/pterm` returned **404**. No pterm executable existed in the configured home or on PATH. Consequently a full install/start/stop run through Pinokio's live control plane was unavailable. The installer was exercised in isolated workspace directories instead.

## Passed

| Check | Result |
| --- | --- |
| Launcher menu tests | 5 passed: fresh install, Start, readiness/WebUI, Stop, and busy menus |
| Python setup tests | 8 passed: config creation/preservation, invalid config, occupied port, venv isolation, interrupted install, failed GPU preflight, lifecycle lock, Git update/conflict behavior |
| Installed Pinokio API compatibility | Executed bundled 8.3.7 `script.stop` implementation with the generated absolute URI and an instrumented kernel; verified the stop target |
| CPU installation | Published PixlStash 2.0.1 wheel, imports, packaged frontend, and dependency consistency passed |
| NVIDIA installation | RTX 4090, driver 610.88; torch 2.12.1+cu130 and torchvision 0.27.1+cu130 installed; `torch.cuda.is_available()` and actual CUDA tensor calculation passed |
| CPU recovery | Switched NVIDIA back to torch/torchvision CPU wheels; imports and dependency checks passed |
| Clean portable installation | Fresh managed CPython **3.12.16**, no system Python dependency; install succeeded in a directory named `Portable install with spaces` |
| Real server smoke | CPU and NVIDIA environments served PixlStash's actual WebUI, `/version`, and referenced frontend assets from disposable libraries |
| First-run setup | Created/migrated fresh hub and vault databases, confirmed registration required, registered a disposable owner through `/api/v1/login`, confirmed registration complete |
| Port conflict | Held the requested port open; launcher selected and saved another port, passed startup checks, and emitted the correct WebUI URL |
| Stop | Sent Windows CTRL_BREAK to the isolated server group; log confirmed application shutdown and database disposal; listener became unreachable |
| Paths containing spaces | Fresh managed-Python installation also passed real server startup, assets, database creation, port fallback, and shutdown |
| Update behavior | Local Git repositories verified successful fast-forward and refusal to overwrite conflicting local edits |

Windows CTRL_BREAK produced process exit code **3**, with `Application shutdown complete` and database disposal in the log. The smoke test checks process exit and listener closure rather than assuming a POSIX exit code.

## Issues found and fixed

1. Pinokio 8.3.7's `script.stop` forwards its URI without caller-relative resolution. All stop actions now derive an absolute `start.js` path from the current checkout.
2. Its Windows venv activation constructs unquoted paths. The launcher instead spawns uv and Python with argument arrays and explicit interpreter paths.
3. PixlStash startup port checks run before its environment overrides. Port fallback now saves the selected port before invoking the server.
4. Lifecycle actions could overlap while asynchronous Pinokio stopping completed. A file lock now excludes concurrent serving/installing and waits for the old process to release the environment.
5. Older InsightFace releases require compilation on Windows. The launcher pins the available 2.1 wheel, verifies imports, and rejects source-only dependency installs.
6. Windows platformdirs uses known-folder APIs. Process-local documented platformdirs overrides keep PixlStash's model pointers/user directories inside this launcher.

## Remaining limits

- The referenced handoff attachment was not present in the received chat or workspace. Implementation follows the explicit user requirements and upstream interfaces; exact attachment conformance cannot be certified.
- Pinokio UI clicks, shared-tool first-run provisioning, and live Pinokio process-tree stopping remain unverified because this installation has no shared tools/pterm. The Pinokio home was inspected and its bundled APIs were checked, but this is not a completed live Pinokio lifecycle test.
- Smoke tests disable background ML workers, following upstream's install-smoke approach. Large model downloads, image import, face recognition, captioning, search quality, and ComfyUI workflows were not exercised. CUDA arithmetic verifies device execution, not those model workflows.
- ONNX Runtime stays on CPU; optional NVIDIA support applies to PyTorch inference.
- Windows x64 was tested. Other operating systems, GPUs, custom HTTPS and remote hosting were not tested.
- Package constraints capture the tested Windows dependency set. Future upstream releases require explicit pin maintenance and another smoke test.
- GitHub Actions was added but its hosted result must be checked after pushing. Tests do not claim a real application-version upgrade/database migration from an existing user's library.

All test servers were stopped. The workspace's installed backend was returned to CPU. Test environments, downloads and logs are ignored by Git and are not part of the launcher repository.
