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
- it also answers {"check_now": "<sha256>"} (card 085) and {"run": "<sha256>"} (card 090), each
  the same way: the sha256 of a file the person approved, and no other key. A run request
  names a plan_approval; the plan it names is started through operator.run, under the approval
  reader and the run lock, and on any backend but the mock only after the person types the
  bench hand-over on THIS host's own terminal at the microscope;
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
import queue
import re
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
#: How long a run request on the instrument waits for the hand-over typed at the microscope. The
#: person has to walk to the microscope computer, look at the instrument and type, so a minute
#: is too short; the wait holds the run lock, which keeps every other run and live view out, so
#: an hour would leave a forgotten request blocking the bench. Ten minutes covers the walk and
#: lapses before anyone mistakes a stale request for a live one (card 090).
BENCH_LAPSE_S = 600.0
#: What a run request's `run` must be: the sha256 of an approval file's bytes, lowercase hex.
_SHA256 = re.compile(r"[0-9a-f]{64}")


class TerminalBench:
    """The hand-over, read from the host's own terminal and from nowhere else (card 090).

    One reader thread feeds every line typed on `stream` into a queue. A request drains the queue
    first, so words typed before the request was shown can never stand in for the hand-over, then
    prints its prompt and waits up to `lapse_s` for one line. Returns the words, "" for a blank
    line (the person declining), or None when the wait lapsed, the host stopped or the terminal
    closed. Nothing on the socket reaches this object.
    """

    def __init__(self, stream=None, out=None) -> None:
        self._stream = stream if stream is not None else sys.stdin
        self._out = out if out is not None else sys.stdout
        self._lines: queue.Queue = queue.Queue()
        self._reader = None
        self._mutex = threading.Lock()

    def _read(self) -> None:
        try:
            for line in iter(self._stream.readline, ""):
                self._lines.put(line)
        except (OSError, ValueError):
            pass
        self._lines.put(None)                                   # the terminal closed

    def begin(self) -> None:
        """Start reading. The host calls this when it starts listening, so a line typed long before a
        request arrives is already in the queue when the request drains it."""
        with self._mutex:
            self._begin()

    def _begin(self) -> None:
        if self._reader is None:
            self._reader = threading.Thread(target=self._read, name="bench-terminal", daemon=True)
            self._reader.start()

    def __call__(self, prompt: str, lapse_s: float, cancel: threading.Event) -> str | None:
        with self._mutex:
            self._begin()
            while True:
                try:
                    self._lines.get_nowait()
                except queue.Empty:
                    break
            print(prompt, file=self._out, flush=True)
            deadline = time.monotonic() + lapse_s
            while not cancel.is_set():
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                try:
                    line = self._lines.get(timeout=min(0.2, left))
                except queue.Empty:
                    continue
                return None if line is None else line.rstrip("\r\n").strip()
            return None


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
                 run_lock_path: Path | None = None, on_orchestrator=None,
                 mm_config: Path | None = None, config_loader=None,
                 status_dir: Path | None = None, questions_dir: Path | None = None,
                 ask_bench=None, bench_lapse_s: float = BENCH_LAPSE_S) -> None:
        self.approvals_dir = Path(approvals_dir)
        #: Where the plan an approval names is looked for (card 090). Never named by a request.
        self.questions_dir = (Path(questions_dir) if questions_dir
                              else AGENT.parent / "microscope_agent" / "questions")
        #: Reads the hand-over: (prompt, lapse_s, cancel) -> words | "" | None. The host's own
        #: terminal by default (made when the host starts, on an instrument backend); a test hands
        #: one in. It is never fed from the socket.
        self.ask_bench = ask_bench
        self.bench_lapse_s = float(bench_lapse_s)
        self.status_dir = Path(status_dir) if status_dir else None
        self.runs_root = Path(runs_root)
        self.address_file = Path(address_file) if address_file else app_dir() / "live_host.json"
        self.log_path = Path(log_path) if log_path else app_dir() / "live_host_log.jsonl"
        self.backend = backend
        self.run_lock_path = run_lock_path
        self.on_orchestrator = on_orchestrator
        self.mm_config = Path(mm_config) if mm_config else None
        self.config_loader = config_loader
        self._mm_state: dict = {}                               # what this host loaded, if it did
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
        if self.mm_config is not None:
            # Judged before the host binds or answers anything (card 069): a configuration that is
            # not approved, or whose focus direction is wrong, never starts a host that would load it.
            if self.backend == "mock":
                raise op.Refusal("a configuration is refused with the mock backend, not ignored: "
                                 "the mock loads none")
            op._check_mm_config(self.mm_config, self.approvals_dir)
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
        if self.ask_bench is None and self.backend != "mock":
            self.ask_bench = TerminalBench()
        if hasattr(self.ask_bench, "begin"):
            self.ask_bench.begin()
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
        if isinstance(message, dict) and "check_now" in message:
            return self._handle_check_now(message, raw)
        if isinstance(message, dict) and "run" in message:
            return self._handle_run(message, raw)
        if not isinstance(message, dict) or set(message) != {"live_on"} \
                or not isinstance(message["live_on"], str):
            return self._refuse('not a request this host answers: {"live_on": "<sha256>"}, '
                                '{"check_now": "<sha256>"} or {"run": "<sha256>"}', raw)
        sha = message["live_on"].lower()
        found = self._find(sha)
        if found is None:
            return self._refuse("no approved live-view list has that sha256", raw)
        path, data = found
        try:
            op.check_live_view_list(json.loads(data.decode("utf-8-sig")))
        except (op.Refusal, ValueError) as exc:
            return self._refuse(f"{path.name}: {exc}", raw)
        try:
            run_id = self._next_run_id()
        except RuntimeError as exc:
            return self._refuse(str(exc), raw)
        lock = run_lock.RunLock(self.run_lock_path if self.run_lock_path is not None
                                else op.RUN_LOCK_PATH)
        try:
            lock.acquire({"kind": "live_view", "run_id": run_id})
        except run_lock.RunLockHeld as exc:
            return self._refuse(self._held_reason(exc), raw)
        started, box = threading.Event(), {}

        def go():
            try:
                op.run_live_view(path, run_id, runs_root=self.runs_root, backend=self.backend,
                                 lock=lock, started=started, on_orchestrator=self.on_orchestrator,
                                 mm_config=self.mm_config, mm_approvals=self.approvals_dir,
                                 mm_state=self._mm_state, config_loader=self.config_loader,
                                 status_dir=self.status_dir)
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

    # -- check now (card 085) ----------------------------------------------- #

    @staticmethod
    def _held_reason(exc) -> str:
        holder = exc.holder or {}
        return (f"a run holds the lock: {holder.get('run_id') or 'unknown run'}"
                f" ({holder.get('kind') or 'unknown kind'})")

    def _next_run_id(self) -> str:
        """`run-YYYYMMDD-NNN` with NNN in 900..999: the range a host-started run takes, so it never
        meets an id the person or a plan gave, and the id is one the console's interface accepts."""
        today = datetime.now().strftime("%Y%m%d")
        taken = set()
        if self.runs_root.is_dir():
            for entry in self.runs_root.iterdir():
                if entry.name.startswith(f"run-{today}-") and entry.name[-3:].isdigit():
                    taken.add(int(entry.name[-3:]))
        free = [n for n in range(900, 1000) if n not in taken]
        if not free:
            raise RuntimeError(f"all 100 host run ids of {today} (run-{today}-900 to -999) are taken")
        return f"run-{today}-{free[0]:03d}"

    def _refuse_check_now(self, reason: str, raw: bytes) -> dict:
        self.record(event="check_now_refused", reason=reason, bytes=len(raw))
        return {"check_now": "refused", "reason": reason}

    def _handle_check_now(self, message: dict, raw: bytes) -> dict:
        """{"check_now": "<sha256>"} and nothing else: find the approved list, run it, say who started."""
        if set(message) != {"check_now"} or not isinstance(message["check_now"], str):
            return self._refuse_check_now('not the one check-now request this host answers, '
                                          '{"check_now": "<sha256>"}', raw)
        sha = message["check_now"].lower()
        found = self._find(sha)
        if found is None:
            return self._refuse_check_now("no approved check-now list has that sha256", raw)
        path, data = found
        try:
            op.check_check_now_list(json.loads(data.decode("utf-8-sig")))
        except (op.Refusal, ValueError) as exc:
            return self._refuse_check_now(f"{path.name}: {exc}", raw)
        try:
            run_id = self._next_run_id()
        except RuntimeError as exc:
            return self._refuse_check_now(str(exc), raw)
        lock = run_lock.RunLock(self.run_lock_path if self.run_lock_path is not None
                                else op.RUN_LOCK_PATH)
        try:
            lock.acquire({"kind": "check_now", "run_id": run_id})
        except run_lock.RunLockHeld as exc:
            return self._refuse_check_now(self._held_reason(exc), raw)
        started, box = threading.Event(), {}

        def go():
            try:
                op.run_check_now(path, run_id, runs_root=self.runs_root, backend=self.backend,
                                 lock=lock, started=started, on_orchestrator=self.on_orchestrator,
                                 status_dir=self.status_dir)
            except Exception as exc:                            # noqa: BLE001 - reported below
                box["error"] = str(exc) if isinstance(exc, op.Refusal) else f"{type(exc).__name__}: {exc}"
                started.set()
            finally:
                if lock.held:
                    lock.release()
        thread = threading.Thread(target=go, name=f"check-now:{run_id}", daemon=True)
        self._runs.append(thread)
        thread.start()
        if not started.wait(START_TIMEOUT_S):
            return self._refuse_check_now(f"the run did not start within {START_TIMEOUT_S:g} s", raw)
        if "error" in box:
            return self._refuse_check_now(f"the run did not start: {box['error']}", raw)
        self.record(event="check_now_started", run_id=run_id, list=path.name, sha256=sha)
        return {"check_now": "started", "run_id": run_id}

    # -- run (card 090) ------------------------------------------------------ #

    def _find_plan(self, plan_id, revision, plan_hash):
        """The one plan file under questions/ with this id and revision, as (path, plan, why_not).

        Several files may carry the same id and revision (a copy kept beside a rewrite); the
        approval's plan_hash then picks, and a pick that is still not one file is refused
        rather than guessed at.
        """
        found = []
        if self.questions_dir.is_dir() and isinstance(plan_id, str):
            for path in sorted(self.questions_dir.glob("*/*.json")):
                try:
                    text = path.read_text(encoding="utf-8-sig")
                    if f'"{plan_id}"' not in text:
                        continue
                    plan = json.loads(text)
                except (OSError, ValueError):
                    continue
                if isinstance(plan, dict) and plan.get("card") == "plan" and plan.get("id") == plan_id \
                        and plan.get("revision") == revision:
                    found.append((path, plan))
        if len(found) > 1:
            validate = op._contracts_validate()
            found = [f for f in found if validate.plan_hash(f[1]) == plan_hash] or found
        if not found:
            return None, None, (f"no plan {plan_id!r} at revision {revision} is under "
                                f"{self.questions_dir}. The approval names a plan that cannot be found")
        if len(found) > 1:
            return None, None, (f"{len(found)} plan files carry {plan_id!r} at revision {revision} "
                                f"({', '.join(f[0].name for f in found)}) and none is singled out by the "
                                "approval's plan_hash, so no one of them is the approved plan")
        return found[0][0], found[0][1], None

    def _handle_run(self, message: dict, raw: bytes) -> dict:
        """{"run": "<sha256>"} and nothing else: start the plan a plan_approval names, as a command would.

        The hash is of the approval file's raw bytes. Everything the run needs comes from files
        the person put in place: the approval, the plan it names, the safety policy. Nothing in
        the request can add to them, and on the instrument nothing in it can stand in for the
        bench hand-over, which is typed on this host's terminal.
        """
        def refuse(reason, **seen):
            self.record(event="run_refused", reason=reason, bytes=len(raw), **seen)
            return {"run": "refused", "reason": reason}

        if set(message) != {"run"}:
            return refuse('not the one run request this host answers, {"run": "<sha256>"}. It takes no '
                          "other key: no plan, path, value, backend or bench hand-over can ride with it, "
                          f"and this one carries {sorted(set(message) - {'run'})}")
        sha = message["run"]
        if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
            return refuse("`run` is not the sha256 of an approval file's bytes (64 lowercase hex digits). "
                          "A path or a name is never accepted in its place")
        self.record(event="run_requested", sha256=sha)
        try:
            op.approvals_source(self.approvals_dir, self.backend)
        except op.Refusal as exc:
            return refuse(str(exc), sha256=sha)
        found = self._find(sha)
        if found is None:
            return refuse("no approval in the approvals folder has that sha256", sha256=sha)
        approval_path, data = found
        try:
            approval = json.loads(data.decode("utf-8-sig"))
        except ValueError:
            approval = None
        if not isinstance(approval, dict) or approval.get("card") != "plan_approval":
            return refuse(f"{approval_path.name} is not a plan_approval. A run starts only from the "
                          "approval of one plan revision", sha256=sha)
        plan_id, revision = approval.get("plan_id"), approval.get("plan_revision")
        plan_path, plan, why_not = self._find_plan(plan_id, revision, approval.get("plan_hash"))
        if why_not:
            return refuse(why_not, sha256=sha, approval=approval_path.name)
        # The gate is judged here, before a run id is taken or the lock is held, with the same
        # reader operator.run applies again when it starts: a plan the approval does not cover
        # is refused with the reason and nothing has opened.
        try:
            approvals = op.approvals_on_disk(None, self.approvals_dir)
            decision = op.authorise(plan, approvals)
            if decision.permitted:
                op.console_gate(plan, decision)
        except op.Refusal as exc:
            return refuse(str(exc), sha256=sha, approval=approval_path.name, plan_id=plan_id)
        if not decision.permitted:
            return refuse(f"{approval_path.name} does not cover plan {plan_id} revision {revision}: "
                          + "; ".join(decision.reasons), sha256=sha, plan_id=plan_id)
        covering = (decision.approval_file or {}).get("sha256")
        if covering != sha:
            return refuse(f"plan {plan_id} revision {revision} is covered first by another approval file "
                          f"({(decision.approval_file or {}).get('path')}), not by the one named. Two "
                          "approvals for one revision leave a request unable to say which signed it",
                          sha256=sha, plan_id=plan_id)
        try:
            run_id = self._next_run_id()
        except RuntimeError as exc:
            return refuse(str(exc), sha256=sha)
        lock = run_lock.RunLock(self.run_lock_path if self.run_lock_path is not None
                                else op.RUN_LOCK_PATH)
        try:
            lock.acquire({"kind": "plan", "plan_id": plan_id, "run_id": run_id})
        except run_lock.RunLockHeld as exc:
            return refuse(self._held_reason(exc), sha256=sha, plan_id=plan_id)
        seen = {"sha256": sha, "approval": approval_path.name, "plan_id": plan_id, "revision": revision,
                "plan_path": op.plan_path_of(plan_path)}
        mock = self.backend == "mock"
        started, box = threading.Event(), {}

        def go():
            try:
                if mock:
                    handover = {"bench": None, "no_bench_because": "the backend is the mock, so there is no "
                                "instrument to hand over", "stated_by": "the live-view host, for a run request"}
                else:
                    words = self._await_bench(plan, approval_path.name, run_id)
                    if not words:
                        self.record(event="run_not_started", run_id=run_id, **seen,
                                    why=("the person declined: a blank line was typed" if words == ""
                                         else f"no hand-over was typed on this terminal within "
                                              f"{self.bench_lapse_s:g} s, or the host stopped, "
                                              "so the request lapsed"))
                        return
                    handover = {"bench": words, "stated_by": "the person, typed on the live-view host's own "
                                "terminal at the microscope", "typed_at": datetime.now(timezone.utc)
                                .isoformat(timespec="seconds")}
                    self.record(event="run_bench_handed_over", run_id=run_id, bench=words,
                                typed_at=handover["typed_at"], **seen)
                record = op.run(plan_path, run_id, backend=self.backend, runs_root=self.runs_root,
                                handover=handover, approvals_dir=self.approvals_dir, lock=lock,
                                started=started, on_orchestrator=self.on_orchestrator,
                                status_dir=self.status_dir)
                self.record(event="run_ended", run_id=run_id, ended=record.get("ended"), **seen)
            except Exception as exc:                            # noqa: BLE001 - reported below
                box["error"] = str(exc) if isinstance(exc, op.Refusal) else f"{type(exc).__name__}: {exc}"
                if not mock or started.is_set():
                    self.record(event="run_failed" if started.is_set() else "run_not_started",
                                run_id=run_id, reason=box["error"], **seen)
            finally:
                started.set()
                if lock.held:
                    lock.release()
        thread = threading.Thread(target=go, name=f"run:{run_id}", daemon=True)
        self._runs.append(thread)
        thread.start()
        if not mock:
            self.record(event="run_waiting_for_bench", run_id=run_id, **seen)
            return {"run": "waiting_for_bench", "run_id": run_id}
        if not started.wait(START_TIMEOUT_S):
            return refuse(f"the run did not start within {START_TIMEOUT_S:g} s", run_id=run_id, **seen)
        if "error" in box:
            return refuse(f"the run did not start: {box['error']}", run_id=run_id, **seen)
        self.record(event="run_started", run_id=run_id, **seen)
        return {"run": "started", "run_id": run_id}

    def _await_bench(self, plan: dict, approval_name: str, run_id: str):
        """Ask for the hand-over on this host's own terminal: the words, "" if declined, None if lapsed."""
        prompt = (f"\nA run was asked for from the console: plan {plan.get('id')} revision "
                  f"{plan.get('revision')}, approved in {approval_name}, as {run_id}, on the {self.backend} "
                  "instrument. It starts only when you hand the bench over here, at the microscope. Type the "
                  "words that hand it over and press Enter; a blank line declines. "
                  f"This request lapses in {self.bench_lapse_s:g} s.")
        if self.ask_bench is None:
            self.ask_bench = TerminalBench()
        return self.ask_bench(prompt, self.bench_lapse_s, self._closed)


def parse_shape(text: str) -> tuple[int, int]:
    """'ROWSxCOLS' -> (rows, cols), both whole numbers >= 1."""
    parts = text.lower().split("x")
    if len(parts) != 2 or not all(p.isdigit() for p in parts) or min(int(p) for p in parts) < 1:
        raise ValueError(f"{text!r} is not ROWSxCOLS")
    return int(parts[0]), int(parts[1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="the live-view host (card 062)")
    parser.add_argument("--backend", default="mock",
                        help="mock unless the person runs it on the instrument")
    parser.add_argument("--approvals", type=Path, default=AGENT / "approvals")
    parser.add_argument("--runs-root", type=Path, default=AGENT / "runs")
    parser.add_argument("--address-file", type=Path, default=None)
    parser.add_argument("--mm-config", type=Path, default=None,
                        help="hardware only: a Micro-Manager configuration the person approved by "
                             "sha256 under --approvals, loaded at the first live view (card 069)")
    # MOCK ONLY: what the mock's frames look like and how fast they come, so a
    # person can watch a live view on mock. Refused with any other backend.
    parser.add_argument("--mock-frame-shape", default=None,
                        help="ROWSxCOLS: 2-D uint16 synthetic frames instead of byte frames")
    parser.add_argument("--mock-frame-delay", type=float, default=None,
                        help="seconds between mock frames")
    args = parser.parse_args(argv)
    mock_flags = args.mock_frame_shape is not None or args.mock_frame_delay is not None
    if args.mm_config is not None and args.backend == "mock":
        parser.error("--mm-config is refused with --backend mock, not ignored: the mock loads "
                     "no configuration")
    if mock_flags and args.backend != "mock":
        parser.error("--mock-frame-shape and --mock-frame-delay work only with --backend mock: "
                     "they shape synthetic frames, and no real camera takes them")
    shape = None
    if args.mock_frame_shape is not None:
        try:
            shape = parse_shape(args.mock_frame_shape)
        except ValueError as exc:
            parser.error(str(exc))
    if args.mock_frame_delay is not None and not args.mock_frame_delay >= 0:
        parser.error("--mock-frame-delay must be >= 0")

    def configure_mock(o):
        camera = o.module_for(op.LIVE_VIEW_ROUTES["Kinetix_red"])
        if shape is not None:
            camera.FRAME_SHAPE = shape
        if args.mock_frame_delay is not None:
            camera.FRAME_DELAY_S = args.mock_frame_delay
    host = LiveHost(args.approvals, args.runs_root, address_file=args.address_file,
                    backend=args.backend, on_orchestrator=configure_mock if mock_flags else None,
                    mm_config=args.mm_config, status_dir=AGENT / ".runtime_status")
    try:
        addr = host.start()
    except op.Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
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
