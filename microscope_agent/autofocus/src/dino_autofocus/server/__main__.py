"""`uv run python -m dino_autofocus.server [--backend mock] [--records-root DIR] [--port N] ...`
`uv run python -m dino_autofocus.server --dump-openapi PATH` writes the OpenAPI JSON and exits.

The server starts the real engine (T-009i): the T-011 runner over the chosen backend, built by
`app.build_runner` with every operation and the hardware gates, plus the records store,
login and the sample seat.

- `--backend mock` (default), `mm-demo` (Micro-Manager's demo devices), `replay
  --replay-source PATH` (saved z-stacks, T-034: anything `stacks.load_stacks` reads),
  `mm-real` (the stand; bench motion stays locked, T-036): a backend that cannot open exits
  with the reason, and nothing falls back to another backend. `placeholder` moves nothing and
  needs no records (tests and the OpenAPI dump).
- Operation records: an op run in the open experiment session is recorded in that session
  (committed with it); any other goes to `<data root>/engine_records`, outside git.
- Records (director, T-009i): only a bench backend (mm-real) uses the real records
  `D:\\AutoFocus\\records` (and `data`, `samples`). Every other backend defaults to the
  `*-mock` folders beside them, and an explicit `--records-root` at the real root is refused
  for it, so a simulated run never writes into the real records git.
"""

from __future__ import annotations

import argparse
import atexit
import contextlib
import json
import logging
import os
import shutil
import signal
import socket
import sys
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .api import AuthSeat, SessionSeat
from .api.patterns import PatternStore
from .app import build_runner, create_app, session_records
from .schemas import Command, Event

DEFAULT_PORT = 8765
REMOTE_VIEW_ENV = "DINO_AF_REMOTE_VIEW"
BACKENDS = ("mock", "mm-demo", "replay", "mm-real", "placeholder")
DEFAULT_BACKEND = "mock"
MOCK_SUFFIX = "-mock"

log = logging.getLogger("dino_autofocus.server")


class PlaceholderEngine:
    """Stands in for the engine runner. No hardware, no backend, no decisions. Two cameras, as
    on the dual-camera stand: the red one sees blobs 0-2 of the blue one plus two of its own,
    so a merged view shows both overlap and difference."""

    frame_hz = 10.0
    position_every_s = 1.0
    #: sample-plane size of one camera pixel, um: Kinetix 6.5 um behind a 60x objective
    pixel_um = 0.108
    #: camera label -> blob indices it shows (0-4 shared phases, 5-6 red only)
    CAMERAS = {"Kinetix_blue": (0, 1, 2, 3, 4), "Kinetix_red": (0, 1, 2, 5, 6)}

    def __init__(self, shape: tuple[int, int] = (1200, 1600)) -> None:
        self._sinks: list[Callable[[Event], None]] = []
        self._lock = threading.Lock()
        self._ticker: threading.Thread | None = None
        self._frame: tuple[np.ndarray, dict[str, Any]] | None = None
        self._frames: dict[str, tuple[np.ndarray, dict[str, Any]]] = {}
        # the runner's one light shape (engine/runner.py `_light_payload`)
        self._lights = {"dialamp": {"state": "off", "intensity": None},
                        "aura": {"state": "off", "lines": {}}, "verified": True, "records": []}
        self.local_viewers: int | None = None
        self._positions = {"x_um": 0.0, "y_um": 0.0, "z_um": 3000.0}
        self._shape = shape
        # a fresh noise field per frame costs more than the 10 Hz budget; cycle two
        rng = np.random.default_rng(0)
        self._noise = [np.clip(rng.normal(400, 30, shape), 0, 4095).astype(np.uint16)
                       for _ in range(2)]
        self._n = 0

    def _emit(self, kind: str, op_id: str = "", **data: Any) -> None:
        ev = Event(kind=kind, op_id=op_id, data=data)
        with self._lock:
            sinks = list(self._sinks)
        for s in sinks:
            try:
                s(ev)
            except Exception:
                log.exception("sink failed")

    def submit(self, cmd: Command) -> str:
        if cmd.kind == "start":
            op_id = uuid.uuid4().hex[:8]
            self._emit("started", op_id, op=cmd.op, placeholder=True)
            self._emit("finished", op_id, op=cmd.op, placeholder=True,
                       note="placeholder engine: nothing was run")
            return op_id
        if cmd.kind == "abort":
            self._emit("aborted", cmd.op_id)
        elif cmd.kind == "confirm":
            self._emit("confirmed", cmd.op_id, **cmd.args)
        elif cmd.kind == "lights_off":
            self._emit("light_changed", **self._lights)
        return cmd.op_id

    def check(self, ops: list[str] | None = None, context: dict | None = None) -> dict:
        """Stops are always allowed; nothing else exists here."""
        return {op: ({"allowed": True, "reason": None} if op in ("abort", "lights_off") else
                     {"allowed": False, "reason": "placeholder engine: no operations"})
                for op in (ops or [])}

    def set_local_viewers(self, count: int) -> None:
        self.local_viewers = count

    def subscribe(self, sink: Callable[[Event], None]) -> Callable[[], None]:
        with self._lock:
            self._sinks.append(sink)
            if self._ticker is None:
                self._ticker = threading.Thread(target=self._tick, daemon=True)
                self._ticker.start()

        def unsubscribe() -> None:
            with self._lock:
                if sink in self._sinks:
                    self._sinks.remove(sink)

        return unsubscribe

    def shutdown(self, reason: str) -> None:
        self._emit("light_changed", **self._lights)  # already off: nothing was ever lit
        self._emit("log", msg=f"placeholder engine stopped: {reason}")

    def snapshot(self) -> dict[str, Any]:
        return {"engine": "placeholder", "positions": dict(self._positions),
                "lights": dict(self._lights), "owner": None, "running": [], "operations": []}

    def latest_frame(self) -> tuple[np.ndarray, dict[str, Any]] | None:
        return self._frame

    def latest_frames(self) -> dict[str, tuple[np.ndarray, dict[str, Any]]]:
        return dict(self._frames)

    def _tick(self) -> None:
        last_position = 0.0
        while True:
            with self._lock:
                if not self._sinks:
                    self._ticker = None
                    return
            now = time.time()
            frames = {cam: (self._picture(now, blobs), {
                "t": now, **self._positions, "bit_depth": 12, "placeholder": True,
                "camera": cam, "pixel_um": self.pixel_um}) for cam, blobs in self.CAMERAS.items()}
            self._frames = frames
            self._frame = frames["Kinetix_red"]
            self._emit("frame_ready")
            if now - last_position >= self.position_every_s:
                self._emit("position", **self._positions)
                last_position = now
            time.sleep(max(0.0, now + 1.0 / self.frame_hz - time.time()))

    def _picture(self, t: float, blobs: tuple[int, ...] = (0, 1, 2, 3, 4)) -> np.ndarray:
        h, w = self._shape
        self._n += 1
        img = self._noise[self._n % 2].copy()
        sigma, r = 40.0, 160  # each drifting blob is drawn only within 4 sigma of its centre
        for k in blobs:
            cy = int(h * (0.5 + 0.3 * np.sin(0.3 * t + 1.3 * k)))
            cx = int(w * (0.5 + 0.3 * np.cos(0.2 * t + 1.7 * k)))
            y0, y1, x0, x1 = max(cy - r, 0), min(cy + r, h), max(cx - r, 0), min(cx + r, w)
            gy = np.exp(-((np.arange(y0, y1) - cy) ** 2) / (2 * sigma**2))
            gx = np.exp(-((np.arange(x0, x1) - cx) ** 2) / (2 * sigma**2))
            patch = img[y0:y1, x0:x1] + 3000.0 * np.outer(gy, gx)
            img[y0:y1, x0:x1] = np.minimum(patch, 4095)
        return img


class BackendUnavailable(SystemExit):
    """The chosen backend cannot run here; the message says why. Never a fallback."""


def open_backend(kind: str, *, mm_config: str | None = None,
                 replay_source: str | None = None) -> tuple[Any, Any]:
    """Open the backend the operator chose and return `(backend, info)`."""
    if kind not in BACKENDS or kind == "placeholder":
        raise BackendUnavailable(f"unknown backend {kind!r}; choose one of "
                                 f"{', '.join(b for b in BACKENDS if b != 'placeholder')}")
    if kind == "replay" and not replay_source:
        raise BackendUnavailable("backend 'replay' needs --replay-source PATH: saved z-stacks "
                                 "(anything engine/backends/stacks.load_stacks reads)")
    try:
        if kind == "mock":
            from ..engine.backends.mock import MockBackend

            backend = MockBackend(seed=0)
        elif kind == "mm-demo":
            from ..engine.backends.mm_demo import MmDemoBackend

            backend = MmDemoBackend()
        elif kind == "replay":
            from ..engine.backends.replay import ReplayBackend

            backend = ReplayBackend(replay_source)
        else:
            from ..engine.backends.mm_real import MmRealBackend

            backend = MmRealBackend(mm_config)
        info = backend.open()
    except Exception as e:
        raise BackendUnavailable(
            f"backend {kind!r} cannot open on this PC: {type(e).__name__}: {e}. "
            f"Nothing was started and no other backend is used in its place.") from e
    return backend, info


def simulated_extras(kind: str, backend: Any, bench: bool) -> tuple[Any, Any, Any]:
    """`(tweezers, piezo, live stream)` for this backend. Simulated backends get mock tweezers
    and a mock XYZ piezo; only the mock gets a live stream (its frames shifted by the piezo, the
    traps drawn in, and a second camera with the trap laser spots). The bench gets none: the
    Tweez300 adapter is not wired yet, the stand's piezo is read only until M5, and the stand's
    live stream is a separate decision (card T-20261002-2205)."""
    if bench:
        return None, None, None
    from ..engine.piezo import MockPiezo
    from ..engine.stream import BackendStream
    from ..engine.tweezers import MockTweezers, mock_views

    tweezers, piezo = MockTweezers(), MockPiezo()
    if kind != "mock":
        return tweezers, piezo, None
    stream = BackendStream.for_backend(backend, decorate=mock_views(tweezers, piezo=piezo),
                                       pixel_um=lambda: backend.info().pixel_um)
    return tweezers, piezo, stream


def open_dz_reader(head: Path | None, info: Any, camera: str | None = None) -> Any:
    """The live gauge's DINO reader over `head`, or None without one. The head loads now (a
    bad path stops the start-up); the camera's clip level comes from its bit depth (the
    Kinetix 'Standard' readout is 12-bit and clips at 4095)."""
    if head is None:
        return None
    from ..engine.live_dz import DzReader
    from ..live import FocusScorer

    try:
        scorer = FocusScorer(head, saturated=2 ** int(info.bit_depth) - 1)
    except Exception as e:
        raise BackendUnavailable(f"--head {head}: {type(e).__name__}: {e}") from e
    return DzReader(scorer, camera=camera)


def record_roots(records_root: Path | None, bench: bool) -> tuple[Path, Path, Path]:
    """`(records, data, samples)`. The real folders are for the bench only."""
    from ..engine.sample import SAMPLES_ROOT
    from ..records.layout import DEFAULT_DATA_ROOT, DEFAULT_RECORDS_ROOT

    real = (DEFAULT_RECORDS_ROOT, DEFAULT_DATA_ROOT, Path(SAMPLES_ROOT))
    if records_root is None:
        chosen = real if bench else tuple(r.with_name(r.name + MOCK_SUFFIX) for r in real)
    else:
        root = Path(records_root)
        chosen = (root, root.with_name(root.name + "-data"), root.with_name(root.name + "-samples"))
    if not bench:
        _refuse_real_roots(chosen, real)
    return chosen  # type: ignore[return-value]


def _refuse_real_roots(chosen: tuple[Path, ...], real: tuple[Path, ...]) -> None:
    """A simulated backend writes nowhere in the real tree: no chosen folder may be a real
    folder, lie inside one, or hold one (director, T-009i; review 검토보조4)."""
    names = ("records", "data", "samples")
    for what, path in zip(names, chosen, strict=True):
        for real_name, real_root in zip(names, real, strict=True):
            if _overlaps(path, real_root):
                raise BackendUnavailable(
                    f"the {what} folder {path} overlaps the real {real_name} folder "
                    f"{real_root}; a simulated backend never writes into the real records, "
                    f"data or samples. Leave --records-root out (simulated runs default to "
                    f"the *{MOCK_SUFFIX} folders) or pick a folder outside them.")


def _norm(p: Path) -> str:
    try:
        p = p.resolve()
    except OSError:
        p = p.absolute()
    return os.path.normcase(os.path.normpath(str(p)))


def _overlaps(a: Path, b: Path) -> bool:
    """`a` and `b` are the same folder, or one lies inside the other."""
    x, y = _norm(a), _norm(b)
    try:
        common = os.path.commonpath([x, y])
    except ValueError:  # different drives
        return False
    return common in (x, y)


class Built:
    """What `build` made for one server run, and how to take it down again (once)."""

    def __init__(self, app: Any, engine: Any, name: str, backend: Any = None,
                 roots: tuple[Path, Path, Path] | None = None) -> None:
        self.app, self.engine, self.name, self.backend, self.roots = (
            app, engine, name, backend, roots)
        self._closed = False
        self._lock = threading.Lock()

    def close(self, reason: str = "server exit") -> None:
        """Stop the engine (lights off first), then close the backend. Never raises."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.app.state.stop_engine.quietly(reason)
        if self.backend is not None:
            try:
                self.backend.close()
            except Exception:
                log.exception("closing the %s backend failed", self.name)


def agent_store_of(args: argparse.Namespace) -> Any:
    """The console's agent store: the mock sample (default), or the soft-matter-agents files
    at --sma-root (else $DINO_AF_SMA_ROOT, else the desktop checkout), read only. A root that
    holds no seat folder stops the start-up with the reason rather than showing nothing."""
    from ..agents import open_store

    kind = getattr(args, "store", "mock")
    if kind != "sma":
        return None  # create_app's own MockStore
    store = open_store("sma", getattr(args, "sma_root", None))
    if not store.available():  # type: ignore[attr-defined]
        raise SystemExit(f"--store sma: no microscope_agent/ or simulation_agent/ under "
                         f"{store.root}")  # type: ignore[attr-defined]
    return store


def build(args: argparse.Namespace, *, remote_view: bool = False,
          hosts: list[str] | None = None) -> Built:
    """Open the backend and make everything the server owns. Nothing listens yet."""
    common = dict(remote_view=remote_view, remote_abort=not args.no_remote_abort,
                  allowed_hosts=hosts or [], dev_origins=args.dev_origin,
                  web_dist=args.web_dist, agent_store=agent_store_of(args),
                  live_host_file=getattr(args, "live_host_file", None),
                  live_host=getattr(args, "live_host", None))
    auth = AuthSeat.from_config(args.config_dir)
    from ..auth import config as auth_config
    # designs, not records: one folder for the mock and the bench alike
    common["patterns_root"] = auth_config.config_dir(args.config_dir) / "patterns"
    if args.backend == "placeholder":
        engine = PlaceholderEngine()
        return Built(create_app(engine, auth=auth, engine_name="placeholder", **common),
                     engine, "placeholder")
    from ..engine.backend import is_bench
    from ..engine.runner import RunnerConfig
    from ..records import AutoCommitter, FolderStore, GitFolderStore, RecordsConfig

    backend, info = open_backend(args.backend, mm_config=args.mm_config,
                                 replay_source=args.replay_source)
    runner = None
    try:
        bench = is_bench(info)
        tweezers, piezo, stream = simulated_extras(args.backend, backend, bench)
        records, data, samples = roots = record_roots(args.records_root, bench)
        cfg = RecordsConfig(records_root=records, data_root=data)
        if shutil.which("git"):
            store = GitFolderStore(cfg)
        else:
            log.warning("git not found: records under %s are written without commits", records)
            store = FolderStore(cfg)
        state_dir = auth_config.config_dir(args.config_dir) / "engine_state" / args.backend
        sessions = SessionSeat()
        dz_reader = open_dz_reader(getattr(args, "head", None), info,
                                   getattr(args, "head_camera", None))
        runner, hardware = build_runner(
            backend, records_root=records, auth=auth, state_dir=state_dir,
            records=session_records(sessions, data / "engine_records"), config=RunnerConfig(),
            tweezers=tweezers, piezo=piezo, stream=stream,
            patterns=PatternStore(common["patterns_root"]).get, dz_reader=dz_reader)
        runner.start()
        app = create_app(runner, auth=auth, records=store, committer=AutoCommitter(store),
                         samples_root=samples, hardware=hardware, sessions=sessions,
                         engine_name=args.backend, **common)
        if stream is not None:  # render only while someone has /ws/frames open
            stream.wanted = lambda: app.state.frames.watching > 0
            stream.attach(runner.publish_frame)
    except BaseException:
        if runner is not None:  # started: lights off and its threads stopped first
            try:
                runner.shutdown("server start-up failed")
            except Exception:
                log.exception("stopping the engine after a failed start-up failed")
        backend.close()
        raise
    log.info("engine: %s (bench=%s); records %s, data %s, samples %s",
             args.backend, bench, *roots)
    return Built(app, runner, args.backend, backend, roots)


def this_pc_hosts() -> list[str]:
    """Names other PCs may use to reach this one: host name, FQDN and IPv4 addresses."""
    name = socket.gethostname()
    hosts = {name, socket.getfqdn()}
    with contextlib.suppress(OSError):
        hosts.update(socket.gethostbyname_ex(name)[2])
    return sorted(h for h in hosts if h)


def install_exit_hooks(app: Any, server: Any) -> Callable[[], None]:
    """Hardware must not depend on `POST /api/shutdown` alone. Lights go off on every way out:
    the route, a signal (uvicorn traps SIGINT, SIGTERM and on Windows SIGBREAK; we start the
    engine stop at once instead of after open connections drain), the app's lifespan end, the
    `finally` around `server.run()`, and `atexit`. The engine is stopped once; returns the
    atexit hook."""
    stop = app.state.stop_engine

    def request_exit() -> None:
        server.should_exit = True

    app.state.request_exit = request_exit
    trap = server.handle_exit

    def handle_exit(sig: int, frame: Any) -> None:
        trap(sig, frame)  # graceful exit, or forced on a second Ctrl+C
        name = signal.Signals(sig).name
        threading.Thread(target=stop.quietly, args=(f"signal {name}",), name="engine-stop").start()

    server.handle_exit = handle_exit

    def at_exit() -> None:
        stop.quietly("process exit")

    atexit.register(at_exit)
    return at_exit


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m dino_autofocus.server", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--remote-view", action="store_true",
                   help=f"listen on 0.0.0.0 so other PCs can view (also {REMOTE_VIEW_ENV}=1); "
                        "commands are still accepted from this PC only")
    p.add_argument("--no-remote-abort", action="store_true",
                   help="refuse abort from remote viewers too (D13 default: allowed)")
    p.add_argument("--allow-host", action="append", default=[], metavar="NAME",
                   help="extra Host header name to accept (repeatable); under --remote-view "
                        "this PC's host name and addresses are added automatically")
    p.add_argument("--dev-origin", action="append", default=[], metavar="URL",
                   help="a page origin besides this server's own that may write, e.g. the "
                        "Vite dev server http://localhost:5173 (repeatable; default none)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--backend", default=DEFAULT_BACKEND, metavar="{" + ",".join(BACKENDS) + "}",
                   help=f"the engine's backend (default {DEFAULT_BACKEND}); one that cannot "
                        "open exits with the reason, never falling back to another")
    p.add_argument("--records-root", type=Path, default=None,
                   help="records git folder (data and samples go beside it as <dir>-data and "
                        "<dir>-samples); default: the real folders for mm-real, the *-mock "
                        "folders for every other backend")
    p.add_argument("--replay-source", default=None, metavar="PATH",
                   help="saved z-stacks for --backend replay (a synth shard folder, a sample "
                        "folder, a stack_*.npy, a find_particle_*_field*.npz, a scan.json)")
    p.add_argument("--mm-config", default=None,
                   help="Micro-Manager .cfg for mm-real (default: see engine/backends/mm_real.py)")
    p.add_argument("--config-dir", type=Path, default=None,
                   help="accounts and audit log folder (default: the local config folder, "
                        "see auth/config.py)")
    p.add_argument("--head", type=Path, default=None, metavar="NPZ",
                   help="trained DINO head (.npz) for the live view's -10..+10 focus gauge; "
                        "without it the gauge shows the mock's truth (mock) or nothing")
    p.add_argument("--head-camera", default=None, metavar="LABEL",
                   help="score only this camera's frames with --head (e.g. Kinetix_red)")
    p.add_argument("--store", choices=("mock", "sma"), default="mock",
                   help="the console's agent store: mock (a copied sample, default) or sma "
                        "(the soft-matter-agents files, read only)")
    p.add_argument("--sma-root", type=Path, default=None, metavar="DIR",
                   help="soft-matter-agents folder for --store sma (default: "
                        "$DINO_AF_SMA_ROOT, else the desktop checkout)")
    p.add_argument("--live-host-file", type=Path, default=None, metavar="FILE",
                   help="where soft-matter-agents' live-view host announces its address "
                        "(default: $DINO_AF_SMA_LIVE_HOST_FILE, else "
                        "%%LOCALAPPDATA%%\\soft-matter-agents\\live_host.json)")
    p.add_argument("--live-host", default=None, metavar="127.0.0.1:PORT",
                   help="the live-view host's address as the person reads it off the host "
                        "(instead of the file)")
    p.add_argument("--web-dist", type=Path, default=None,
                   help="built web app to serve (default: <repo>/web/dist)")
    p.add_argument("--dump-openapi", metavar="PATH",
                   help="write the OpenAPI JSON to PATH ('-' for stdout) and exit")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    remote_view = args.remote_view or os.environ.get(REMOTE_VIEW_ENV, "") == "1"
    hosts = [*args.allow_host, *(this_pc_hosts() if remote_view else ())]
    if args.dump_openapi:  # the API is the same for every backend: describe it without one
        app = create_app(PlaceholderEngine(), engine_name="placeholder", web_dist=args.web_dist)
        text = json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"
        if args.dump_openapi == "-":
            sys.stdout.write(text)
        else:
            Path(args.dump_openapi).write_text(text, encoding="utf-8")
        return 0

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
    built = build(args, remote_view=remote_view, hosts=hosts)
    atexit.register(built.close, "process exit")
    try:
        serve(built, port=args.port, remote_view=remote_view)
    finally:
        built.close("server exit")
    return 0


def serve(built: Built, *, port: int, remote_view: bool) -> None:
    import uvicorn

    host = "0.0.0.0" if remote_view else "127.0.0.1"
    print(f"dino-autofocus server, engine={built.name}: open http://127.0.0.1:{port} on this PC"
          + (" (other PCs: view only)" if remote_view else ""))
    # proxy headers off: the client address must be the socket's, it decides who may command
    server = uvicorn.Server(uvicorn.Config(built.app, host=host, port=port, proxy_headers=False,
                                           log_level="info"))
    install_exit_hooks(built.app, server)
    server.run()


if __name__ == "__main__":
    raise SystemExit(main())
