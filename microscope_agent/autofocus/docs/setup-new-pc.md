# Setting up dino-autofocus on another PC

## 1. Clone

```
git clone https://github.com/kyu-softmatter/dino-autofocus
```

Any folder works; the launcher exe is built for the clone it is built from.

## 2. Python

Two interpreters are used:

| Interpreter | Runs | Install |
|---|---|---|
| System Python 3.12 (`%LOCALAPPDATA%\Programs\Python\Python312`, or on PATH) | nothing in this repository any more: the old hardware scripts were deleted in R-05 (in git history), and the launcher and the app use the uv env, see section 4 | python.org installer, then `python -m pip install numpy pillow opencv-python pymmcore==12.5.0.75.0 pymmcore-plus==0.18.1` |
| Repo uv env (`.venv`) | plots, the DINO focus scorer, dataset generation, training, and Node 22 for the web UI build | `uv sync` in the repo (pulls torch cu126 and, via the `web` group, Node; run it as `uv run npm ...`) |

## 3. DINOv2 backbone (only for the focus scorer / training)

`dino_autofocus.backbone` loads a pinned local clone, by default `../dinov2` next to
the repo (override with the `DINOV2_REPO` environment variable):

```
git clone https://github.com/facebookresearch/dinov2 ../dinov2
git -C ../dinov2 checkout 7764ea0f912e53c92e82eb78a2a1631e92725fc8
```

## 4. Build the desktop launcher

Needs `uv` and a finished `uv sync` in this clone; no system Python.

```
powershell -ExecutionPolicy Bypass -File tools\launcher\build.ps1
```

Writes `DINO Autofocus.exe` to the Desktop using the .NET Framework compiler that ships
with Windows. If an exe is already there, the build stops and prints its size and date;
check whether it is a build you want to keep before adding `-Force` to replace it. `-Force`
first copies the old exe to `DINO Autofocus.prev.exe` next to it (a timestamped name if that
exists) and prints the path.

The exe starts the web app server from this clone's uv env
(`uv run python -m dino_autofocus.server`) and opens the browser at `http://127.0.0.1:8765/`.
Server code changes need no rebuild; moving the clone or changing the port (`-Port`) does.
If `autofocus.ico` is missing, `uv run python tools\launcher\make_icon.py` redraws it.
Tests and the review gates: [`docs/runbooks/tests.md`](runbooks/tests.md).

Run, stop and troubleshooting: [`docs/runbooks/launcher.md`](runbooks/launcher.md).

## 5. Trained focus head

`models/heads/head_k100x_dinov2_vits14_L1.npz` (+ `.json` metrics) is the head trained
on the synthetic 100x set. Pass it to the live view with
`--head models/heads/head_k100x_dinov2_vits14_L1.npz`.

## Microscope-PC only (not needed to build or open the UI)

These are hard-coded for the Ti2 bench and only matter where the hardware is attached:

- `C:\agentic_microscope` -- the Micro-Manager config
  `config\micromanager\single_cam_red_noDMD_nocom10.cfg` (`BENCH_CONFIG` in
  `src/dino_autofocus/engine/backends/mm_real.py`)
- `C:\Program Files (x86)\NanoBench 6000` -- stage controller DLL and config
- `D:\AutoFocus\records`, `D:\AutoFocus\data`, `D:\AutoFocus\samples` -- the app's bench
  record folders (`records/layout.py`; `--records-root` overrides them)

Generated data (`data/`, `outputs/`, `*.npz`, `*.npy`, `*.tif`) is not in git; regenerate
it with `scripts/farm_p5.py` / `scripts/make_dataset.py`.
