"""A stand-in for a run soft-matter-agents' orchestrator follows (its plan.md 11-25), for the
console's tests. It writes events.jsonl the way Orchestrator.begin_run / record / end_run do
and serves the two loopback sockets with the same rules as its _StopChannel and _FrameTap
(origin/feature/autofocus-ui f6c0996, 0c6452d): one line, exact keys, at most 1024 bytes for
a stop; exactly {"get": "latest_frame"} for a frame; anything else closed unanswered. No
soft-matter-agents code is imported: the console must work against the files and sockets.
"""

from __future__ import annotations

import contextlib
import json
import socket
import threading
import time
from pathlib import Path
from typing import Any

STOP_MAX_BYTES = 1024
T0_WALL = "2026-10-05T10:00:00-07:00"


def sma_tree(root: Path) -> Path:
    """An empty soft-matter-agents layout: the two seats' runs/ folders."""
    for seat in ("microscope", "simulation"):
        (root / f"{seat}_agent" / "runs").mkdir(parents=True, exist_ok=True)
    return root


class _Server(threading.Thread):
    def __init__(self, judge) -> None:
        super().__init__(daemon=True)
        self._judge = judge
        self._closed = threading.Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.sock.settimeout(0.05)
        self.connections = 0

    def address(self) -> dict[str, Any]:
        host, port = self.sock.getsockname()[:2]
        return {"host": host, "port": port}

    def run(self) -> None:
        while not self._closed.is_set():
            try:
                conn, _ = self.sock.accept()
            except (TimeoutError, OSError):
                continue
            self.connections += 1
            with conn:
                try:
                    conn.settimeout(2.0)
                    cap = STOP_MAX_BYTES + 1
                    raw = b""
                    while len(raw) < cap and b"\n" not in raw:
                        chunk = conn.recv(cap - len(raw))
                        if not chunk:
                            break
                        raw += chunk
                    if b"\n" in raw and len(raw) < cap:
                        conn.settimeout(0.05)
                        with contextlib.suppress(TimeoutError, OSError):
                            raw += conn.recv(cap - len(raw))
                    reply = self._judge(raw)
                    if reply is not None:
                        conn.settimeout(2.0)
                        conn.sendall(reply)
                except OSError:
                    pass

    def close(self) -> None:
        self._closed.set()
        with contextlib.suppress(OSError):
            self.sock.close()
        self.join(2.0)


class FakeSmaRun:
    """`runs/<run_id>/events.jsonl` plus a stop channel and a frame tap, until `end()`."""

    def __init__(self, root: Path, run_id: str = "run-20261005-001",
                 plan_id: str = "plan_microscope_mic-20261005-001", *, tap: bool = True,
                 stop_reply_delay_s: float = 0.0) -> None:
        self.run_id = run_id
        self.folder = Path(root) / "microscope_agent" / "runs" / run_id
        self.folder.mkdir(parents=True)
        self.stops: list[str] = []  # reasons of the valid stops received
        self.refused: list[str] = []
        self.frame: tuple[Any, dict[str, Any], float] | None = None
        self._delay = stop_reply_delay_s
        self._lock = threading.Lock()
        self.stop_server = _Server(self._stop)
        self.tap_server = _Server(self._tap) if tap else None
        self._stream = open(self.folder / "events.jsonl", "a", encoding="utf-8")  # noqa: SIM115 - open for the run, like begin_run
        self._line({"event": "run_started", "run_id": run_id, "plan_id": plan_id,
                    "revision": 1, "t0_wall": T0_WALL,
                    "stop_channel": self.stop_server.address(),
                    "frame_tap": self.tap_server.address() if self.tap_server else None})
        self.stop_server.start()
        if self.tap_server:
            self.tap_server.start()
        self.ended = False

    # -- the file ------------------------------------------------------------------------

    def _line(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._stream.write(json.dumps(event) + "\n")
            self._stream.flush()

    def record(self, **fields: Any) -> None:
        self._line({"t_mono": round(time.monotonic(), 6), "time_base": "software", **fields})

    def end(self, how: str = "completed") -> None:
        if self.ended:
            return
        self.stop_server.close()
        if self.tap_server:
            self.tap_server.close()
        self._line({"event": "run_ended", "how": how, "t_mono": 1.0})
        self._stream.close()
        self.ended = True

    # -- the stop channel ----------------------------------------------------------------

    def _stop(self, raw: bytes) -> bytes | None:
        def refuse(why: str) -> None:
            self.refused.append(why)
            self.record(event="stop_refused", reason=why, bytes=len(raw))
            return None

        if len(raw) > STOP_MAX_BYTES:
            return refuse(f"longer than {STOP_MAX_BYTES} bytes")
        text = raw.decode("utf-8", errors="replace")
        if text.endswith("\n"):
            text = text[:-1]
        if "\n" in text or "\r" in text:
            return refuse("not one line")
        try:
            message = json.loads(text)
        except ValueError:
            return refuse("not JSON")
        if not isinstance(message, dict) or set(message) != {"stop", "reason"}:
            return refuse("not exactly the keys stop and reason")
        if not isinstance(message["reason"], str):
            return refuse("reason is not text")
        if message["stop"] != self.run_id:
            return refuse(f"names run {message['stop']!r}, not this run")
        self.stops.append(message["reason"])
        self.record(event="stop_requested", reason=message["reason"])
        self.record(event="abort_begin", reason="stop from outside the process")
        if self._delay:
            time.sleep(self._delay)
        return b'{"abort": "begun"}\n'

    # -- the frame tap -------------------------------------------------------------------

    def put(self, image: Any, metadata: dict[str, Any], t_mono: float) -> None:
        self.frame = (image.copy(), dict(metadata), t_mono)

    def _tap(self, raw: bytes) -> bytes | None:
        text = raw.decode("utf-8", errors="replace").rstrip("\n")
        try:
            message = json.loads(text)
        except ValueError:
            message = None
        if message != {"get": "latest_frame"}:
            self.record(event="frame_tap_refused", reason="not the one request")
            return None
        if self.frame is None:
            return json.dumps({"frame": False, "note": "no frame yet"}).encode() + b"\n"
        image, metadata, t_mono = self.frame
        body = image.tobytes()
        head = {"frame": True, "metadata": metadata, "t_mono": t_mono, "bytes": len(body),
                "shape": list(image.shape), "dtype": str(image.dtype)}
        return json.dumps(head).encode() + b"\n" + body


# the shape of soft-matter-agents contracts/schemas/live_view_list.schema.json (48242a2)
LIVE_LIST = {"artifact": "live_view_list", "schema_version": "0.1", "written_by": "kyuhwan",
             "written_at": "2026-10-07", "label": "finding the sample in transmitted light",
             "transmitted_lamp": {"device": "DiaLamp", "intensity": {"value": 12}},
             "camera": {"device": "Kinetix_red", "exposure_ms": 20, "frame_ceiling": 3000}}


def write_live_list(root: Path, name: str = "live-view-brightfield.json",
                    data: dict[str, Any] | None = None) -> str:
    """A live-view list as the person would leave it in approvals/; returns its sha256."""
    import hashlib

    folder = Path(root) / "microscope_agent" / "approvals"
    folder.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data or LIVE_LIST, indent=2).encode()
    (folder / name).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


class FakeLiveHost:
    """soft-matter-agents' live-view host as card 062 and the console agreed it (2026-10-07):
    127.0.0.1 on an OS port, announced in an address file outside the tree; exactly one line
    {"live_on": <sha256>}; replies {"live_on": "started", "run_id"} once run_started is
    written, or {"live_on": "refused", "reason"}. One run at a time (the lock)."""

    def __init__(self, root: Path, address_file: Path, *, silent: bool = False) -> None:
        self.root = Path(root)
        self.address_file = Path(address_file)
        self.silent = silent
        self.requests: list[bytes] = []
        self.runs: list[FakeSmaRun] = []
        self.server = _Server(self._judge)
        self.server.start()
        addr = self.server.address()
        self.address_file.parent.mkdir(parents=True, exist_ok=True)
        self.address_file.write_text(json.dumps({**addr, "pid": 4242,
                                                 "started_at": T0_WALL}), encoding="utf-8")

    def approved(self) -> set[str]:
        import hashlib

        folder = self.root / "microscope_agent" / "approvals"
        return {hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob("*.json")
                if json.loads(p.read_bytes()).get("artifact") == "live_view_list"} \
            if folder.is_dir() else set()

    def _judge(self, raw: bytes) -> bytes | None:
        self.requests.append(raw)
        if self.silent:
            return None

        def refuse(why: str) -> bytes:
            return json.dumps({"live_on": "refused", "reason": why}).encode() + b"\n"

        try:
            message = json.loads(raw.decode("utf-8").rstrip("\n"))
        except ValueError:
            return refuse("not JSON")
        if not isinstance(message, dict) or set(message) != {"live_on"}:
            return refuse("not exactly the key live_on")
        if message["live_on"] not in self.approved():
            return refuse("no approved live-view list has that sha256")
        if any(not r.ended for r in self.runs):
            return refuse("a run holds the lock")
        run = FakeSmaRun(self.root, run_id=f"run-live-{len(self.runs) + 1:03d}",
                         plan_id=None)  # type: ignore[arg-type]
        self.runs.append(run)
        return json.dumps({"live_on": "started", "run_id": run.run_id}).encode() + b"\n"

    def close(self) -> None:
        for r in self.runs:
            r.end()
        self.server.close()
        self.address_file.unlink(missing_ok=True)


def tree_state(root: Path) -> dict[str, tuple[int, int]]:
    """Every file under `root` with its size and mtime, to show the console wrote nothing."""
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}
