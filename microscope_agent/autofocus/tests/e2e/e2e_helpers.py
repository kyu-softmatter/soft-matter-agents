"""Helpers of the M1 mock bench (T-035); the fixtures are in tests/e2e/conftest.py.

Test modules import from here (`from e2e_helpers import ...`), never from a conftest
module: several test directories have one, so importing it by name depended on load
order (T-015d).

The M1 mock bench (T-035): MockBackend, the T-011 runner, auth, records; temp folders only.

`Bench` is one engine as the server will hold it: the runner owns the backend (opened by
`exclusive`), device control from T-018 sits behind its control seat, records go to a fresh
local git repository and to the sample folder. Commands go in through `Bench.submit`, events
come out on a queue, and a test waits on them as a screen would.

Operations come from the runner's registry (`engine.runner.OPERATIONS`). The ones merged as
plain `run_*` functions but not registered yet (status, light_set, edge_trace: T-030, to be
registered with T-032's op stage) get a thin stand-in here, and each stand-in is dropped as
soon as the real class is registered (`Bench.stand_ins` says which are in use).

`need(module, task)` skips a step whose operation is not on main and names the task that
brings it, so `pytest tests/e2e -rs` reads as M1's progress. No windows, no network.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import pkgutil
import queue
import shutil
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from dino_autofocus.auth import AccountStore, AuditLog, DeviceControl, LoginSessions
from dino_autofocus.engine import operations as operations_pkg
from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.backends.mock_world import Faults, MockWorld
from dino_autofocus.engine.events import Command, Event, queue_sink
from dino_autofocus.engine.guards import OperationAborted, OpScope, exclusive
from dino_autofocus.engine.operations import edge_trace, light_set
from dino_autofocus.engine.operations.status import read_status
from dino_autofocus.engine.runner import (
    OPERATIONS,
    Aborted,
    DeviceControlSeat,
    Operation,
    Registry,
    Runner,
    RunnerConfig,
    folder_records,
)
from dino_autofocus.engine.sample import Sample, new_sample_id
from dino_autofocus.records import ExperimentSession, FolderStore, GitFolderStore, RecordsConfig

#: test accounts on the example.test domain; every one gets PASSWORD (a test value)
USERS = [
    {"name": "Ada Admin", "email": "admin@example.test", "role": "admin"},
    {"name": "Otto Operator", "email": "otto@example.test", "role": "operator"},
    {"name": "Olga Operator", "email": "olga@example.test", "role": "operator"},
    {"name": "Vera Viewer", "email": "vera@example.test", "role": "viewer"},
]
PASSWORD = "e2e-test-pass-2468"

# every operations module on main registers its classes with the runner on import (as the
# server will load them); a module that is not on main yet simply is not there
for _m in pkgutil.iter_modules(operations_pkg.__path__):
    importlib.import_module(f"{operations_pkg.__name__}.{_m.name}")
try:  # T-027: the runner reaches the records store and the open session through this seat
    from dino_autofocus.engine.operations import sample_ops
except ImportError:  # pragma: no cover - before T-027
    sample_ops = None
OPERATOR = "otto@example.test"
ENDS = ("finished", "aborted", "error")
#: inner lifecycle events of a T-030 run_* function; the runner announces its own
_INNER_LIFECYCLE = ("started", "finished", "aborted", "error")


def need(module: str, task: str) -> None:
    """Skip unless `module` is on main; the reason names the task that brings it."""
    try:
        found = importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:  # a parent package is missing too
        found = False
    if not found:
        pytest.skip(f"{task}: {module} is not on main yet")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class SimClock:
    """Simulated time for pacing (edge_trace sleeps): costs no wall time."""

    def __init__(self, t: float = 1_800_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += max(s, 0.0)


# -- stand-ins for merged operations the runner has no class for yet ---------------------

def stand_ins(bench: Bench) -> list[type[Operation]]:
    """Thin Operation classes over the T-030 `run_*` code. They add nothing of their own:
    the runner does permissions, records, exit-path lights; the T-030 code does the work."""

    def forward(ctx) -> Callable[[Event], None]:
        def sink(ev: Event) -> None:
            if ev.kind not in _INNER_LIFECYCLE:
                ctx.emit(ev.kind, **ev.data)
        return sink

    class StatusStandIn(Operation):
        name = "status"
        motion = False

        def run(self) -> dict:
            st = read_status(self.ctx.backend)
            self.ctx.emit("reading", op="status", source="status", value=st)
            return {"status": st}

    class LightSetStandIn(Operation):
        name = "light_set"
        motion = False
        keep_lights_on_finish = True

        def preflight(self) -> list[dict]:
            try:
                light_set.parse(self.args)
            except ValueError as e:
                return [{"name": "args", "ok": False, "why": str(e)}]
            return [{"name": "args", "ok": True}]

        def run(self) -> dict:
            req = light_set.parse(self.args)
            scope = OpScope(self.ctx.op_id, None, forward(self.ctx), backend=self.ctx.backend)
            rbs = light_set.switch(self.ctx.backend, scope, req)
            return {"mode": req.mode, "line": req.line, "percent": req.percent,
                    "verified": all(r.verified for r in rbs)}

    class EdgeTraceStandIn(Operation):
        name = "edge_trace"
        watched = edge_trace.WATCHED
        updatable = edge_trace.UPDATABLE
        _tracer = None

        def preflight(self) -> list[dict]:
            return edge_trace.preflight(self.ctx.backend, self.args)

        def update(self, args: dict) -> None:
            super().update(args)
            if self._tracer is not None and "speed_um_s" in args:
                self._tracer.set_speed(float(args["speed_um_s"]))

        def _check(self) -> None:
            try:
                self.ctx.check()
            except Aborted as e:
                raise OperationAborted(str(e)) from e

        def run(self) -> dict:
            ctx = self.ctx
            try:
                return edge_trace.run_edge_trace(
                    ctx.backend, bench.sample, dict(self.args), forward(ctx),
                    confirm=lambda key, text: bool(ctx.confirm(key, text)["ok"]),
                    check=self._check, sleep=bench.clock.sleep, clock=bench.clock,
                    wall=bench.clock, on_tracer=lambda t: setattr(self, "_tracer", t),
                    user_id=ctx.user_id, session_id=ctx.session_id)
            except OperationAborted as e:
                raise Aborted(str(e)) from e

    return [StatusStandIn, LightSetStandIn, EdgeTraceStandIn]


# -- the bench -------------------------------------------------------------------------------

#: default wait for one event; a test that needs longer passes `timeout=` and says why
WAIT_S = 30.0


def _brief(ev: Event) -> str:
    d = ev.data if isinstance(ev.data, dict) else {}
    detail = d.get("key") or d.get("status") or d.get("why") or d.get("message") or ""
    return f"{ev.kind}:{ev.op_id}" + (f" ({str(detail)[:60]})" if detail else "")


def records_store(root: Path) -> FolderStore:
    """The records repository as on the microscope PC (local git; plain folders when this
    machine has no git). One per test module: `git init` once, not per test (T-035b)."""
    cfg = RecordsConfig(records_root=root / "records", data_root=root / "data")
    return GitFolderStore(cfg) if shutil.which("git") else FolderStore(cfg)


class SharedWorld:
    """One MockWorld for a module's benches, put back to its first state for each one, so
    the virtual sample is built once (T-035b). Faults and state are reset; the sample and
    its particles are the same seeded ones a fresh MockWorld would draw."""

    def __init__(self, seed: int = 0):
        self.world = MockWorld(seed=seed)
        self._first = self.world.state_dict()

    def fresh(self) -> MockWorld:
        self.world.faults = Faults()
        self.world.load_state(self._first)
        return self.world


class Bench:
    """One engine on the mock with its auth and records, for one test module or one test.
    `store` and `world` may be shared with other benches of the same module."""

    def __init__(self, root: Path, *, seed: int = 0, local_gone_abort_s: float = 10.0,
                 store: FolderStore | None = None, world: MockWorld | None = None):
        self.root = root
        self.clock = SimClock()
        self.session: ExperimentSession | None = None
        self.sample: Sample | None = None
        self.login_token: str | None = None
        self.control_token: str | None = None
        self.events: list[Event] = []
        self._q: queue.Queue = queue.Queue()

        self.audit = AuditLog(root / "config" / "audit.jsonl",
                              session_id_provider=lambda: self.open_session_id)
        self.accounts = AccountStore(root / "config" / "accounts.json", audit=self.audit)
        self.accounts.seed(USERS, PASSWORD)
        self.logins = LoginSessions(self.accounts, audit=self.audit)
        self.control = DeviceControl(self.logins, audit=self.audit)

        self.store = store if store is not None else records_store(root)
        self.samples_root = root / "samples"
        self.samples_root.mkdir(parents=True, exist_ok=True)

        self.backend = MockBackend(world) if world is not None else MockBackend(seed=seed)
        self.registry = registry = Registry()
        self.stand_ins: list[str] = []
        for cls in stand_ins(self):
            real = OPERATIONS.get(cls.name)
            registry.register(real or cls)
            if real is None:
                self.stand_ins.append(cls.name)
        for name in OPERATIONS.names():  # everything else that is registered on main
            if registry.get(name) is None:
                registry.register(OPERATIONS.get(name))
        self.runner = Runner(
            self.backend, registry=registry, control=DeviceControlSeat(self.control),
            records=folder_records(self._record_parent), state_dir=root / "engine_state",
            config=RunnerConfig(position_interval_s=None,
                                local_gone_abort_s=local_gone_abort_s))
        self.runner.subscribe(queue_sink(self._q))
        if sample_ops is not None:
            sample_ops.install_sample_seat(self.runner, sample_ops.SampleSeat(
                self.store, self.samples_root, session_for=self._session_for))

    def _session_for(self, session_id: str):
        s = self.session
        return s if s is not None and s.session_id == session_id else None

    # -- ids
    @property
    def open_session_id(self) -> str | None:
        s = self.session
        return s.session_id if s is not None and s.writable else None

    def _record_parent(self, meta: dict) -> Path:
        return self.sample.dir if self.sample is not None else self.root / "engine_records"

    # -- the operator's day, short forms
    def login(self, email: str = OPERATOR) -> str:
        r = self.logins.login(email, PASSWORD)
        assert r.ok, r.outcome
        return r.token

    def take_control(self, email: str = OPERATOR) -> None:
        self.login_token = self.login(email)
        self.control_token = self.control.acquire(self.login_token, local=True).token

    def open_session(self, user: str = OPERATOR) -> ExperimentSession:
        """Pick a new sample (T-027 `sample_new` through the runner when it is registered),
        then open the experiment session for it as the server will."""
        if self.registry.get("sample_new") is not None:
            end = self.run("sample_new")
            assert end.kind == "finished", end.data
            self.sample = Sample(end.data["summary"]["sample_id"], self.samples_root)
        else:
            self.sample = Sample(new_sample_id(self.samples_root), self.samples_root)
            self.sample.dir.mkdir()
            self.runner.set_current_sample(self.sample.id)
        self.session = ExperimentSession.open(self.store, user, self.sample.id)
        if sample_ops is not None:
            sample_ops.ensure_sample_created(self.session, self.store)
        self.runner.set_experiment_session(self.session.session_id, time.time())
        return self.session

    def ready(self) -> Bench:
        """Logged in, holding control, session open, one local viewer: ready to operate."""
        self.take_control()
        self.open_session()
        self.runner.set_local_viewers(1)
        return self

    # -- commands and events
    def command(self, kind: str, op: str = "", op_id: str = "", args: dict | None = None, *,
                user: str | None = OPERATOR, grant: Any = "mine", remote: bool = False,
                session_id: Any = "open") -> Command:
        return Command(kind, op=op, op_id=op_id, args=dict(args or {}), user_id=user,
                       session_id=self.open_session_id if session_id == "open" else session_id,
                       control_grant=self.control_token if grant == "mine" else grant,
                       remote=remote)

    def submit(self, kind: str, op: str = "", op_id: str = "", args: dict | None = None,
               **kw: Any) -> str:
        return self.runner.submit(self.command(kind, op, op_id, args, **kw))

    def start(self, op: str, args: dict | None = None, **kw: Any) -> str:
        return self.submit("start", op, args=args, **kw)

    def answer(self, op_id: str, key: str, ok: bool = True, **kw: Any) -> str:
        return self.submit("confirm", op_id=op_id, args={"key": key, "ok": ok}, **kw)

    def wait(self, pred: Callable[[Event], bool], timeout: float = WAIT_S,
             what: str | None = None) -> Event:
        """The first event matching `pred`. Fails after `timeout` s naming what it waited
        for (`what`, else the predicate's name) and the last events seen, so a predicate
        that never matches costs 30 s, not minutes (T-035b)."""
        for ev in self.events:
            if pred(ev):
                return ev
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                name = what or getattr(pred, "__qualname__", repr(pred))
                last = [_brief(e) for e in self.events[-12:]]
                raise AssertionError(f"waited {timeout:g} s for {name}; nothing matched. "
                                     f"Last events: {last}")
            try:
                ev = self._q.get(timeout=left)
            except queue.Empty:
                continue
            self.events.append(ev)
            if pred(ev):
                return ev

    def wait_for(self, kind: str, op_id: str, **kw: Any) -> Event:
        return self.wait(lambda e: e.kind == kind and e.op_id == op_id,
                         what=f"{kind} of {op_id}", **kw)

    def wait_end(self, op_id: str, **kw: Any) -> Event:
        return self.wait(lambda e: e.kind in ENDS and e.op_id == op_id,
                         what=f"the end of {op_id}", **kw)

    def run(self, op: str, args: dict | None = None, *, answers: dict[str, bool] | None = None,
            timeout: float = WAIT_S, **kw: Any) -> Event:
        """Start `op`, answer its confirms from `answers` (default yes), wait for its end
        (at most `timeout` s between two of its events that matter)."""
        op_id = self.start(op, args, **kw)
        answers = dict(answers or {})
        while True:
            ev = self.wait(lambda e: e.op_id == op_id
                           and (e.kind in ENDS or e.kind == "confirm_required"),
                           timeout=timeout, what=f"a confirm or the end of {op_id}")
            if ev.kind in ENDS:
                return ev
            self.events.remove(ev)  # answered: a later wait must not find it again
            self.answer(op_id, ev.data["key"], answers.get(ev.data["key"], True))

    def lights(self) -> dict[str, str]:
        return self.backend.light_state()

    def close(self) -> None:
        self.runner.shutdown("end of the test")


OFF = {"DiaLamp": "0", "Aura": "0"}


def engine_on(bench: Bench) -> Iterator[Bench]:
    """The engine owns the backend for the bench's life; leaving switches everything off."""
    with exclusive(bench.backend):
        bench.runner.start()
        try:
            yield bench
        finally:
            bench.close()
    assert bench.lights() == OFF



def after(day: Bench, *steps: str) -> None:
    """Skip unless the named earlier steps of the day finished."""
    missing = [s for s in steps if s not in day.done]
    if missing:
        pytest.skip(f"needs the earlier step(s) {missing}")
