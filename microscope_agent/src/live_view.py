"""The live-view host: the person starts it, and the console asks it for "live on" (card 062).

    python microscope_agent/src/live_view.py [--backend mock] [--approvals DIR] [--runs-root DIR]

A live view is a preparatory run (operator.run_live_view) that runs one list
the person wrote and approved in approvals/. This host is the only way to
start one from the console, and it can do nothing else:

- it listens only while the person keeps it running, on 127.0.0.1 only, on a
  port the OS chooses, and holds no Micro-Manager core while no live view is
  running;
- it accepts one message, one line of JSON, exactly {"live_on": "<sha256>"},
  where the sha256 is of an approved list file's raw bytes. The console
  cannot send a list, a path or a value; it can only name a list the person
  already approved;
- it replies {"live_on": "started", "run_id": ...} once that run's
  `run_started` is written, or {"live_on": "refused", "reason": ...};
- it cannot stop, set, read or move anything. "Live off" is the run's own
  stop channel, announced in its run_started like every run's.

Its address is written to %LOCALAPPDATA%\\soft-matter-agents\\live_host.json,
outside this tree, atomically on start and deleted on stop: exactly
{"host", "port", "pid", "started_at"}. The interface is settled with the
console session ("AF 화면 · SMA 실행 보기와 멈춤 연결") in card 062; a change to
it goes there first.

Every request it refuses, and every run it starts, is recorded in its own
log beside the address file. No run exists for a refusal, so that log is the
only place one could be written.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
AGENT = _HERE.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                             # type: ignore[union-attr]
    return module


op = _load("_mic_operator_for_live_view", _HERE / "operator.py")
run_lock = op.run_lock

#: The longest request accepted, in bytes. A live_on is one key and a sha256.
MAX_REQUEST_BYTES = 256
#: How long the host waits for a started run to write run_started.
START_TIMEOUT_S = 15.0


def app_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "soft-matter-agents" if base else Path.home() / ".soft-matter-agents"


def _pid_running(pid) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _answers(port) -> bool:
    try:
        socket.create_connection(("127.0.0.1", int(port)), timeout=1).close()
        return True
    except (OSError, ValueError, TypeError):
        return False


class LiveHost:
    def __init__(self, approvals_dir: Path, runs_root: Path, address_file: Path | None = None,
                 log_path: Path | None = None, backend: str = "mock",
                 run_lock_path: Path | None = None, on_orchestrator=None) -> None:
        self.approvals_dir = Path(approvals_dir)
        self.runs_root = Path(runs_root)
        self.address_file = Path(address_file) if address_file else app_dir() / "live_host.json"
        self.log_path = Path(log_path) if log_path else app_dir() / "live_host_log.jsonl"
        self.backend = backend
        self.run_lock_path = run_lock_path
        self.on_orchestrator = on_orchestrator
        self._sock = None
        self._thread = None
        self._closed = threading.Event()
        self._addr = None
        self._runs: list[threading.Thread] = []

    # -- the record --------------------------------------------------------- #

    def record(self, **fields) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = {"at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **fields}
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, default=str) + "\n")

    # -- lifetime ----------------------------------------------------------- #

    def address(self) -> dict | None:
        return None if self._addr is None else dict(self._addr)

    def start(self) -> dict:
        """Bind, write the address file atomically, and serve. Refuses if a host already answers."""
        if self._sock is not None:
            raise RuntimeError("this host is already started")
        try:
            existing = json.loads(self.address_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = None
        if isinstance(existing, dict) and _pid_running(existing.get("pid")) \
                and _answers(existing.get("port")):
            raise RuntimeError(f"a live-view host already runs: {existing}. One host at a time")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(4)
        sock.settimeout(0.05)
        host, port = sock.getsockname()[:2]
        self._sock, self._addr = sock, {"host": host, "port": port}
        info = {"host": host, "port": port, "pid": os.getpid(),
                "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self.address_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.address_file.with_name(self.address_file.name + ".tmp")
        tmp.write_text(json.dumps(info), encoding="utf-8")
        os.replace(tmp, self.address_file)
        self._closed.clear()
        self._thread = threading.Thread(target=self._serve, name="live-view-host", daemon=True)
        self._thread.start()
        self.record(event="host_started", **info, approvals=str(self.approvals_dir),
                    runs_root=str(self.runs_root), backend=self.backend)
        return dict(self._addr)

    def stop(self) -> None:
        """Stop listening and delete the address file. A live view already running goes on:
        its own stop channel, or its frame ceiling, ends it."""
        if self._sock is None:
            return
        self._closed.set()
        try:
            self._sock.close()
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(3.0)
        try:
            self.address_file.unlink(missing_ok=True)
        except OSError:
            pass
        self.record(event="host_stopped", port=self._addr["port"] if self._addr else None)
        self._sock = self._addr = self._thread = None
        for t in self._runs:
            t.join(30.0)

    # -- serving ------------------------------------------------------------ #

    def _serve(self) -> None:
        while not self._closed.is_set():
            try:
                conn, _ = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            with conn:
                try:
                    conn.settimeout(2.0)
                    cap = MAX_REQUEST_BYTES + 1
                    raw = b""
                    while len(raw) < cap and b"\n" not in raw:
                        chunk = conn.recv(cap - len(raw))
                        if not chunk:
                            break
                        raw += chunk
                    if b"\n" in raw and len(raw) < cap:
                        conn.settimeout(0.05)
                        try:
                            raw += conn.recv(cap - len(raw))
                        except (socket.timeout, OSError):
                            pass
                    reply = self._handle(raw)
                    conn.settimeout(2.0)
                    conn.sendall(json.dumps(reply).encode() + b"\n")
                except OSError:
                    pass

    def _refuse(self, reason: str, raw: bytes) -> dict:
        self.record(event="live_on_refused", reason=reason, bytes=len(raw))
        return {"live_on": "refused", "reason": reason}

    def _find(self, sha: str):
        for path in sorted(self.approvals_dir.glob("*.json")):
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if hashlib.sha256(data).hexdigest() == sha:
                return path, data
        return None

    def _handle(self, raw: bytes) -> dict:
        if len(raw) > MAX_REQUEST_BYTES:
            return self._refuse(f"longer than {MAX_REQUEST_BYTES} bytes", raw)
        text = raw.decode("utf-8", errors="replace")
        if text.endswith("\n"):
            text = text[:-1]
        if "\n" in text or "\r" in text:
            return self._refuse("not one line", raw)
        try:
            message = json.loads(text)
        except ValueError:
            return self._refuse("not JSON", raw)
        if not isinstance(message, dict) or set(message) != {"live_on"} \
                or not isinstance(message["live_on"], str):
            return self._refuse('not the one request this host answers, {"live_on": "<sha256>"}',
                                raw)
        sha = message["live_on"].lower()
        found = self._find(sha)
        if found is None:
            return self._refuse("no approved live-view list has that sha256", raw)
        path, data = found
        try:
            op.check_live_view_list(json.loads(data.decode("utf-8-sig")))
        except (op.Refusal, ValueError) as exc:
            return self._refuse(f"{path.name}: {exc}", raw)
        run_id = "run-" + datetime.now().strftime("%Y%m%d") + "-live-" + \
                 datetime.now().strftime("%H%M%S%f")[:9]
        lock = run_lock.RunLock(self.run_lock_path if self.run_lock_path is not None
                                else op.RUN_LOCK_PATH)
        try:
            lock.acquire({"kind": "live_view", "run_id": run_id})
        except run_lock.RunLockHeld as exc:
            holder = exc.holder or {}
            return self._refuse(f"a run holds the lock: {holder.get('run_id') or 'unknown run'}"
                                f" ({holder.get('kind') or 'unknown kind'})", raw)
        started, box = threading.Event(), {}

        def go():
            try:
                op.run_live_view(path, run_id, runs_root=self.runs_root, backend=self.backend,
                                 lock=lock, started=started, on_orchestrator=self.on_orchestrator)
            except Exception as exc:                            # noqa: BLE001 - reported below
                box["error"] = f"{type(exc).__name__}: {exc}"
                started.set()
            finally:
                if lock.held:
                    lock.release()
        thread = threading.Thread(target=go, name=f"live-view:{run_id}", daemon=True)
        self._runs.append(thread)
        thread.start()
        if not started.wait(START_TIMEOUT_S):
            return self._refuse(f"the run did not start within {START_TIMEOUT_S:g} s", raw)
        if "error" in box:
            return self._refuse(f"the run did not start: {box['error']}", raw)
        self.record(event="live_on_started", run_id=run_id, list=path.name, sha256=sha)
        return {"live_on": "started", "run_id": run_id}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="the live-view host (card 062)")
    parser.add_argument("--backend", default="mock",
                        help="mock unless the person runs it on the instrument")
    parser.add_argument("--approvals", type=Path, default=AGENT / "approvals")
    parser.add_argument("--runs-root", type=Path, default=AGENT / "runs")
    parser.add_argument("--address-file", type=Path, default=None)
    args = parser.parse_args(argv)
    host = LiveHost(args.approvals, args.runs_root, address_file=args.address_file,
                    backend=args.backend)
    addr = host.start()
    print(f"live-view host on {addr['host']}:{addr['port']}, address in {host.address_file}. "
          "Ctrl-C stops it.", flush=True)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        host.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
