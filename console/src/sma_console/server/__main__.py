"""`uv run python -m sma_console.server [--store sma] [--port N] ...`
`uv run python -m sma_console.server --dump-openapi PATH` writes the OpenAPI JSON and exits.

The server shows; it runs no engine (soft-matter-agents card 077). Its one engine is the
placeholder, which moves nothing, lights nothing and records nothing. dino's engine, its
backends (mock, mm-demo, replay, mm-real), its records and the live focus gauge stay in
`microscope_agent/autofocus/` and are not reachable from here: they were cut from the
console with dino's engine command path. `--backend placeholder` is still accepted, so the
command lines the console's runbooks give keep working.
"""

from __future__ import annotations

import argparse
import atexit
import contextlib
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .api import AuthSeat
from .app import create_app
from .schemas import Event

DEFAULT_PORT = 8765
REMOTE_VIEW_ENV = "DINO_AF_REMOTE_VIEW"
BACKENDS = ("placeholder",)
DEFAULT_BACKEND = "placeholder"

log = logging.getLogger("dino_autofocus.server")


class PlaceholderEngine:
    """The console's one engine: no hardware, no backend, no decisions, and no command intake
    (card 077). Two cameras, as on the dual-camera stand: the red one sees blobs 0-2 of the
    blue one plus two of its own, so a merged view shows both overlap and difference."""

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


class Built:
    """What `build` made for one server run, and how to take it down again (once)."""

    def __init__(self, app: Any, engine: Any, name: str) -> None:
        self.app, self.engine, self.name = app, engine, name
        self._closed = False
        self._lock = threading.Lock()

    def close(self, reason: str = "server exit") -> None:
        """Stop the engine. Never raises."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.app.state.stop_engine.quietly(reason)


def agent_store_of(args: argparse.Namespace) -> Any:
    """The console's agent store: the mock sample (default), or the soft-matter-agents files
    at --sma-root (else $DINO_AF_SMA_ROOT, else the repository this console sits in), read only.
    A root that holds no seat folder, or no repository to default to, stops the start-up with
    the reason rather than showing nothing."""
    from ..agents import open_store
    from ..agents.sma_files import RootNotFoundError

    kind = getattr(args, "store", "mock")
    if kind != "sma":
        return None  # create_app's own MockStore
    try:
        store = open_store("sma", getattr(args, "sma_root", None))
    except RootNotFoundError as e:
        raise SystemExit(f"--store sma: {e}") from e
    if not store.available():  # type: ignore[attr-defined]
        raise SystemExit(f"--store sma: no microscope_agent/ or simulation_agent/ under "
                         f"{store.root}")  # type: ignore[attr-defined]
    return store


def build(args: argparse.Namespace, *, remote_view: bool = False,
          hosts: list[str] | None = None) -> Built:
    """Make what the server shows with. Nothing listens yet."""
    if args.backend != "placeholder":
        raise SystemExit(f"unknown backend {args.backend!r}: the console runs only the "
                         f"placeholder (soft-matter-agents card 077)")
    engine = PlaceholderEngine()
    app = create_app(engine, auth=AuthSeat.from_config(args.config_dir),
                     engine_name="placeholder", remote_view=remote_view,
                     remote_abort=not args.no_remote_abort, allowed_hosts=hosts or [],
                     dev_origins=args.dev_origin, web_dist=args.web_dist,
                     agent_store=agent_store_of(args),
                     live_host_file=getattr(args, "live_host_file", None),
                     live_host=getattr(args, "live_host", None))
    return Built(app, engine, "placeholder")


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
    p = argparse.ArgumentParser(prog="python -m sma_console.server", description=__doc__,
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
    p.add_argument("--backend", default=DEFAULT_BACKEND, choices=BACKENDS,
                   help="the console's engine: only the placeholder, which moves nothing "
                        "(soft-matter-agents card 077)")
    p.add_argument("--config-dir", type=Path, default=None,
                   help="accounts and audit log folder (default: the local config folder, "
                        "see auth/config.py)")
    p.add_argument("--store", choices=("mock", "sma"), default="mock",
                   help="the console's agent store: mock (a copied sample, default) or sma "
                        "(the soft-matter-agents files, read only)")
    p.add_argument("--sma-root", type=Path, default=None, metavar="DIR",
                   help="soft-matter-agents folder for --store sma (default: "
                        "$DINO_AF_SMA_ROOT, else the repository this console sits in)")
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
