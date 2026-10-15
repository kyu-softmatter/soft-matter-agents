"""Engine runner: commands in, one hardware operation at a time, events out.

The server hands every `Command` to `Runner.submit` and listens through `subscribe`; it
decides nothing. The runner owns dispatch, op ids, worker threads, abort / confirm / update
routing, the lights-off pre-emption, rule 12 (PLAN.md 6) and the shutdown path. Operations
(WP-C) register a class and see only their `OpContext`.

Single ownership: one `exclusive` operation holds the core at a time. Exceptions:
- `lights_off` pre-empts: it aborts the running operation, waits for that operation's exit
  path, then switches everything off and reads it back (T-002 appendix 3).
- record-only operations (`exclusive = False`: boundary mark, undo, tare, sample open) run
  alongside the running one and still leave their record.
- the acquisition stream is engine-owned, not an operation (T-004 4.4). An operation that
  snaps itself (`snaps = True`) pauses the stream and puts it back on every exit path.

Command states: `proposed -> confirmed -> running -> finished | aborted | error`, and
`proposed -> rejected`. A human `start` enters `confirmed` directly. An assistant `start`
enters `confirmed` only when it carries `confirmed_by` (T-013 holds the card and submits it
once a person confirms); without it the runner holds it as a proposal until a human
`approve`s it. Nothing touches hardware before `confirmed`, and confirmed work still passes
the same preflight, gates and guards.

Rule 12: `PERMISSIONS` says, per operation, whether it needs the control grant and an open
experiment session. The grant is attached to the Command by the server (`control_grant`)
and checked against the injected `Control` (T-018); the session is the one the server set
with `set_experiment_session`. Stops (`abort`, `lights_off`) need neither. Light commands
(`light_set`, D15) are gated like motion.

D13 / D14 (PLAN v1.0): a `remote` command may only be `abort`. Operations declared
`watched` abort `local_gone_abort_s` after the server reports no loopback viewer through
`set_local_viewers(0)`; a viewer coming back inside the window cancels it.

Shutdown: `shutdown(reason)` switches the lights off first, then aborts and finishes the
records, stops the stream and keeps the final readback for the next start. A running mark in
`state_dir` that survives to the next start is reported as an unclean shutdown.

A refused command raises `CommandRefused` from `submit` and is also sent as a `refused`
event, so the caller gets the reason at once and every screen sees it.
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import threading
import time
import traceback
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, ClassVar, Protocol, runtime_checkable

from . import live_dz
from . import records as op_records
from .backend import AURA_LINES, Frame, Positions, is_bench
from .events import Command, Event, EventSink
from .piezo import piezo_state_of
from .tweezers import state_of

log = logging.getLogger(__name__)

LIGHTS_OFF = "lights_off"
ACTIVE = ("confirmed", "running")
ENDED = ("finished", "aborted", "error", "rejected")
YES = ("yes", "ok", "done", "true")
RUNNING_MARK = "running.json"
LAST_SHUTDOWN = "last_shutdown_lights.json"
UNCLEAN_LOG = "unclean_shutdowns.jsonl"
AWAITING_WHY = "the stage is away from the sample; return it first"


@runtime_checkable
class EngineAPI(Protocol):
    """What the server (T-009) talks to. abort / confirm / lights_off are Commands too.

    Sinks are called in order under one lock, from engine threads (also the lights-off
    path): a sink must hand the event on and return at once, never block or wait."""

    def submit(self, cmd: Command) -> str: ...  # op_id; raises CommandRefused
    def subscribe(self, sink: EventSink) -> Callable[[], None]: ...  # returns unsubscribe
    def snapshot(self) -> dict: ...  # JSON-native current state


class CommandRefused(ValueError):
    """`submit` refused the command; the same reason went out as a `refused` event."""

    def __init__(self, op_id: str, why: str):
        super().__init__(why)
        self.op_id, self.why = op_id, why


class Aborted(Exception):
    """Raised inside an operation by `OpContext.check / sleep / confirm` once abort is asked."""


# -- rule 12: who may run what ------------------------------------------------------------


@dataclass(frozen=True)
class Permission:
    action: str  # "motion" | "light" | "read" | "record" | "stop"
    control: bool  # needs the operator's control grant (checked here)
    session: bool  # needs an open experiment session (checked here)
    operator: bool = False  # needs a logged-in local operator (the server checks the role)


MOTION = Permission("motion", True, True)
_MARK = Permission("record", False, True, operator=True)  # beside a hardware op (D16)
PERMISSIONS: dict[str, Permission] = {
    # manager-confirmed classes (T-011 card); the server reads this table
    "hardware_scan": Permission("read", True, False),  # detection only, before a session
    "status": Permission("read", True, False),
    "hardware_confirm": Permission("record", True, False, operator=True),
    # pick the sample for the next session; with a session open the operation's preflight
    # refuses any sample but the session's own (one sample per session, T-019)
    "sample_open": Permission("record", True, False),
    "sample_new": Permission("record", True, False),
    "sample_geometry_set": Permission("record", True, True),
    "loading_confirm_person": Permission("record", True, True),
    "loading_check_image": Permission("record", True, True),
    "boundary_mark": _MARK,
    "boundary_undo": _MARK,
    "boundary_reset": _MARK,
    "map_flag": _MARK,
    "map_flag_retire": _MARK,
    "candidate_confirm": _MARK,
    "candidate_reject": _MARK,
    "score_tare": Permission("record", True, True),  # not in the card's table yet
    "score_tare_clear": Permission("record", True, True),
    "frame_save": Permission("record", True, True),
    "light_set": Permission("light", True, True),  # D15
    "edge_trace": MOTION,
    "scan_4x": MOTION,
    "sample_map": MOTION,
    "goto_xy": MOTION,
    "focus_100x": MOTION,
    "objective_change": MOTION,
    "trap_move": MOTION,  # optical tweezers (card T-20261002-2205): like any stage move
    "trap_set": MOTION,
    "pattern_run": MOTION,  # the piezo and the traps over time (card T-20261002-2205 stage 4)
    # command kinds, listed so the server's table is complete (D13: remote abort only)
    "abort": Permission("stop", False, False),
    LIGHTS_OFF: Permission("stop", False, False),
}


def permission(op: str) -> Permission:
    """Anything not in the table is treated as motion: the strict default."""
    return PERMISSIONS.get(op, MOTION)


def permission_table() -> dict[str, dict]:
    return {op: asdict(p) for op, p in PERMISSIONS.items()}


# -- injected seats ---------------------------------------------------------------------


class Control(Protocol):
    """T-018 `auth/control.py`: does this grant give `user_id` the equipment right now?"""

    def check(self, user_id: str | None, grant: str | None) -> bool: ...


class DenyAll:
    """Default until login exists: only stops get through."""

    def check(self, user_id: str | None, grant: str | None) -> bool:
        return False


class AllowAll:
    """Mock and tests only: every user holds control."""

    def check(self, user_id: str | None, grant: str | None) -> bool:
        return True


class DeviceControlSeat:
    """T-018 `auth.DeviceControl` behind the Control seat: the grant must be the live one
    and belong to the user who sends the command. Duck-typed, so the engine imports no
    auth code; `DeviceControl.check` raises a PermissionError (`ControlError`) when not."""

    def __init__(self, control: Any):
        self._control = control

    def check(self, user_id: str | None, grant: str | None) -> bool:
        """Fails closed: no grant, no user, a refused grant. Any other error from the
        control object propagates, and the runner refuses with it as the reason."""
        if not grant or not user_id:
            return False
        try:
            g = self._control.check(grant)
        except PermissionError:
            return False
        owner = getattr(g, "user_id", None)
        return isinstance(owner, str) and owner.lower() == user_id.lower()


class AcquisitionStream(Protocol):
    """The engine-owned continuous acquisition (live view). Not an operation."""

    def running(self) -> bool: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def stop(self) -> None: ...


class NoStream:
    def running(self) -> bool:
        return False

    def pause(self) -> None:
        return None

    def resume(self) -> None:
        return None

    def stop(self) -> None:
        return None


class OpRecord(Protocol):
    """One operation's record (T-002 records): every event, then the end summary."""

    dir: str | None  # the record folder, None when nothing is written

    def event(self, ev: Event) -> None: ...
    def close(self, end: dict) -> None: ...


class NoRecord:
    dir = None

    def event(self, ev: Event) -> None:
        return None

    def close(self, end: dict) -> None:
        return None


RecordFactory = Callable[[dict], OpRecord]  # gets the op's meta (op, op_id, origin, ids)


class _FolderRecord:
    """`records.OpRecord` (T-002) behind the runner's record seat."""

    def __init__(self, parent: Path, meta: dict):
        self._rec = op_records.OpRecord(parent, meta["op"], prefix=meta["record_prefix"],
                                        user_id=meta["user_id"],
                                        session_id=meta["session_id"])
        self.dir = str(self._rec.dir)

    def event(self, ev: Event) -> None:
        self._rec.sink(ev)

    def close(self, end: dict) -> None:
        state = end["state"]
        end_state = dict(end.get("end_state") or {})
        lights = end_state.pop("lights", None) or {}
        result = {k: end.get(k) for k in ("op_id", "origin", "proposal_id", "conversation_id",
                                          "confirmed_by", "confirmed_at", "summary",
                                          "manual_steps", "why")}
        self._rec.finish(state, lights=lights, end_state=end_state, result=result,
                         error=end.get("message"))


def folder_records(parent_for: Callable[[dict], str | Path]) -> RecordFactory:
    """Record seat writing `<parent>/<prefix or op>_<stamp>/{log.jsonl,summary.json}`.
    `parent_for(meta)` picks the folder, e.g. the open sample's or the session's records."""
    return lambda meta: _FolderRecord(Path(parent_for(meta)), meta)


@dataclass
class RunnerConfig:
    position_interval_s: float | None = 0.5  # periodic `position` events; None = off
    preempt_wait_s: float = 15.0  # lights_off waits this long for the aborted op's exit
    keep_ended: int = 50  # ended ops kept for `snapshot()["recent"]`
    # PLAN v1.0: D13 remote abort, D14 abort watched operations when local viewers drop
    allow_remote_abort: bool = True
    abort_when_local_gone: bool = True
    local_gone_abort_s: float = 10.0


# -- operations -------------------------------------------------------------------------


class Operation:
    """Base for WP-C operations: `plan -> preflight -> run`, `abort` and `update` hooks.

    `run` returns the summary dict. It may end in `awaiting_return` by returning
    `{"state": "awaiting_return", ...}` or by `ctx.set_end_state(state="awaiting_return")`
    before raising / being aborted. `plan` must not touch the backend: `Runner.plan` calls
    it with no hardware behind `ctx.backend`.
    """

    name: ClassVar[str] = ""
    exclusive: ClassVar[bool] = True  # holds the core; False = record-only, runs alongside
    motion: ClassVar[bool] = True  # refused while a sample awaits return
    snaps: ClassVar[bool] = False  # pauses the acquisition stream while it runs
    watched: ClassVar[bool] = False  # D14: needs a person watching locally (edge_trace)
    keep_lights_on_finish: ClassVar[bool] = False  # light_set: on success lights stay as set
    updatable: ClassVar[frozenset[str]] = frozenset()  # args `update` may change mid-run
    record_prefix: ClassVar[str | None] = None  # e.g. "scan4x" keeps scan4x_<stamp>/
    approaches: ClassVar[bool] = False  # calls FocusAxis.approach(); see `clearance`

    def __init__(self, ctx: OpContext):
        self.ctx = ctx

    @property
    def args(self) -> dict:
        return self.ctx.args

    def plan(self) -> dict:
        return {}

    def preflight(self) -> list[dict]:
        """Checks as `{name, ok, want, read, why}`; any `ok` false stops before `started`."""
        return []

    def run(self) -> dict:
        raise NotImplementedError

    def abort(self) -> None:
        """Called on the command thread after `ctx.aborted` is set (e.g. to stop a wait)."""

    def update(self, args: dict) -> None:
        """Called on the command thread; keys are already checked against `updatable`."""
        self.ctx.args.update(args)

    def returns_to_sample(self) -> bool:
        """True for the one motion allowed while awaiting return (ui-spec 7.5:
        `objective_change` with `resume: true`); finishing it clears the state."""
        return False

    def clearance(self) -> Callable[[float], bool] | None:
        """The callback an `approaches` operation hands to `approach(clearance=...)`. On a
        bench backend the runner refuses the operation in preflight while this is None."""
        return None


class Registry:
    def __init__(self) -> None:
        self._ops: dict[str, type[Operation]] = {}

    def register(self, cls: type[Operation]) -> type[Operation]:
        if not cls.name or cls.name == LIGHTS_OFF:
            raise ValueError(f"operation name {cls.name!r} is empty or reserved")
        if self._ops.get(cls.name, cls) is not cls:
            raise ValueError(f"operation {cls.name!r} is already registered")
        self._ops[cls.name] = cls
        return cls

    def get(self, name: str) -> type[Operation] | None:
        return self._ops.get(name)

    def names(self) -> list[str]:
        return sorted(self._ops)


OPERATIONS = Registry()  # WP-C modules register here with @register_operation
register_operation = OPERATIONS.register


class LightsOff(Operation):
    """Built in: it is the exit path, so it cannot depend on what is registered. Reached by
    the `lights_off` command kind, not by `start`."""

    name = LIGHTS_OFF
    motion = False

    def plan(self) -> dict:
        return {"text": "Aura State -> 0, DiaLamp State -> 0. Nothing moves."}

    def preflight(self) -> list[dict]:
        try:
            self.ctx.emit("reading", source="lights", value=self.ctx.backend.light_state())
        except Exception as e:  # a failed read never blocks switching off
            self.ctx.log(f"light state read failed: {e}", level="warning")
        return []

    def run(self) -> dict:
        records = self.ctx.runner._switch_off(self.ctx._op)
        verified = _verified(records)
        if not verified:
            self.ctx.emit("error", op=LIGHTS_OFF, message="lights off not verified",
                          where="readback")
        state = {r["device"]: r["read"] for r in records}
        return {"ok": verified, "aura_state": state.get("Aura"),
                "dialamp_state": state.get("DiaLamp"), "verified": verified}


# -- internals --------------------------------------------------------------------------


class SerializedBackend:
    """Every backend call under one lock, so the position poller, record-only operations and
    lights-off share one core with the running operation."""

    def __init__(self, backend: Any):
        self._backend = backend
        self.lock = threading.RLock()

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._backend, name)
        if not callable(attr):
            return attr

        def call(*a: Any, **k: Any) -> Any:
            with self.lock:
                return attr(*a, **k)

        return call


class _NoHardware:
    """`ctx.backend` during `Runner.plan`: any use is a bug in the operation."""

    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(f"plan() must not use the backend (called {name!r})")


@dataclass
class _Op:
    op_id: str
    op: str
    cls: type[Operation]
    args: dict
    origin: str
    user_id: str | None
    session_id: str | None
    proposal_id: str | None = None
    conversation_id: str | None = None
    state: str = "confirmed"
    confirmed_by: str | None = None
    confirmed_at: float | None = None
    why: str = ""
    quiet: bool = False  # plan-only: events go nowhere
    lights_before: dict | None = None  # light payload at start: what `restore` keeps
    hand_back: _Op | None = None  # lights_off: an owner that did not exit keeps the core
    last_progress: dict | None = None
    end_state: dict = field(default_factory=dict)
    manual_steps: list = field(default_factory=list)
    pending: dict = field(default_factory=dict)  # key -> confirm_required data
    answers: dict = field(default_factory=dict)  # key -> the confirm record
    abort_evt: threading.Event = field(default_factory=threading.Event)
    cond: threading.Condition = field(default_factory=lambda: threading.Condition(
        threading.RLock()))
    record: Any = None
    instance: Operation | None = None
    thread: threading.Thread | None = None

    def meta(self) -> dict:
        return {"op_id": self.op_id, "op": self.op, "origin": self.origin,
                "user_id": self.user_id, "session_id": self.session_id,
                "proposal_id": self.proposal_id, "conversation_id": self.conversation_id,
                "confirmed_by": self.confirmed_by, "confirmed_at": self.confirmed_at,
                "record_prefix": self.cls.record_prefix}

    def public(self) -> dict:
        return {**self.meta(), "state": self.state, "args": dict(self.args), "why": self.why,
                "last_progress": self.last_progress}


class OpContext:
    """What an operation sees: its args, the shared backend, events, abort and confirm."""

    def __init__(self, runner: Runner, op: _Op, backend: Any = None):
        self.runner, self._op = runner, op
        self.backend = runner._backend if backend is None else backend
        self.stream = runner._stream
        # the optical tweezers (engine/tweezers.py), None when there are none; operations
        # move them through guards.TrapAxis only
        self.tweezers = runner.tweezers if backend is None else None
        # the XYZ piezo for patterns (engine/piezo.py), None when none may move
        self.piezo = runner.piezo if backend is None else None

    op_id = property(lambda self: self._op.op_id)
    op = property(lambda self: self._op.op)
    args = property(lambda self: self._op.args)
    user_id = property(lambda self: self._op.user_id)
    session_id = property(lambda self: self._op.session_id)

    def set_current_sample(self, sample_id: str | None, *, reserved: bool = False) -> None:
        self.runner.set_current_sample(sample_id, reserved=reserved)

    @property
    def record_dir(self) -> Path | None:
        """This operation's record folder (e.g. scan_4x writes its scan.json there), or None
        when the record seat writes no folder (or during `Runner.plan`)."""
        d = getattr(self._op.record, "dir", None)
        return None if d is None else Path(d)

    @property
    def backend_info(self) -> Any:
        """The `BackendInfo` read once at `start()` (stage limits, objectives, bench), so
        `plan()` can use it without touching hardware. None if that read failed."""
        return self.runner._info

    @property
    def session_started_at(self) -> float | None:
        """Start of the open experiment session: the "re-trace every session" check."""
        return (self.runner._session or {}).get("started_at")

    @property
    def aborted(self) -> bool:
        return self._op.abort_evt.is_set()

    def check(self) -> None:
        if self.aborted:
            raise Aborted(self._op.why)

    def sleep(self, s: float) -> None:
        if self._op.abort_evt.wait(s):
            raise Aborted(self._op.why)

    def emit(self, kind: str, /, **data: Any) -> Event:  # data may hold its own "kind"
        return self.runner._emit_op(self._op, kind, data)

    def progress(self, status: str, *, step: int | None = None, n_steps: int | None = None,
                 **data: Any) -> None:
        p = {"op": self.op, "status": status, "step": step, "n_steps": n_steps, "data": data}
        self._op.last_progress = p
        self.runner._emit_op(self._op, "progress", p)

    def log(self, text: str, level: str = "info") -> None:
        self.emit("log", level=level, text=text)

    def publish_frame(self, frame: Frame) -> int:
        """Make this the newest frame (server preview) and emit `frame_ready` for it."""
        if self._op.quiet:
            return 0
        return self.runner.publish_frame(frame, source_op=self.op, op_id=self.op_id)

    def set_end_state(self, **kv: Any) -> None:
        self._op.end_state.update(kv)

    def confirm(self, key: str, prompt: str, *, options: tuple[str, ...] = ("yes", "no"),
                kind: str = "question", context: dict | None = None) -> dict:
        """Emit `confirm_required` and wait, with no time limit, for the matching `confirm`.
        Returns the confirm record (`ok`, `answer`, `by`, `at`); raises Aborted on abort.
        `kind="manual_step"` (F5 "Loading done") also lands in the summary's `manual_steps`."""
        op = self._op
        req = {"key": key, "prompt": prompt, "options": list(options), "kind": kind,
               "context": dict(context or {})}
        with op.cond:
            if key in op.pending:
                raise ValueError(f"already waiting for {key!r}")
            self.check()
            op.pending[key] = req
        self.emit("confirm_required", **req)
        with op.cond:
            while key not in op.answers and not op.abort_evt.is_set():
                op.cond.wait()
            op.pending.pop(key, None)
            if key in op.answers:
                return op.answers.pop(key)
        raise Aborted(op.why)


# -- the runner -------------------------------------------------------------------------


class Runner:
    """The engine body behind `EngineAPI`. The backend is opened once by the caller; the
    runner never opens or closes it. Call `start()` before submitting (it checks for an
    unclean last shutdown) and `shutdown(reason)` at the end."""

    def __init__(self, backend: Any, *, registry: Registry = OPERATIONS,
                 control: Control | None = None, records: RecordFactory | None = None,
                 stream: AcquisitionStream | None = None, config: RunnerConfig | None = None,
                 state_dir: str | Path | None = None,
                 hardware: Callable[[], dict] | None = None,
                 awaiting_return: dict | None = None,
                 on_awaiting_return: Callable[[dict | None], None] | None = None,
                 tweezers: Any = None, piezo: Any = None,
                 patterns: Callable[[str], Any] | None = None,
                 dz_reader: live_dz.DzReader | None = None):
        self._backend = SerializedBackend(backend)
        #: the live gauge's DINO reader (a trained head); None: frames carry no model dz
        self.dz_reader = dz_reader
        self.tweezers = tweezers  # engine/tweezers.py; None: no tweezers on this setup
        self.piezo = piezo  # engine/piezo.py; None: no piezo that may move (the stand, < M5)
        #: pattern id -> engine.patterns.Pattern or None (the server's pattern folder)
        self.patterns = patterns
        self._registry = registry
        self._control = control or DenyAll()
        self._records = records or (lambda meta: NoRecord())
        self._stream = stream or NoStream()
        self.config = config or RunnerConfig()
        self._state_dir = Path(state_dir) if state_dir else None
        # snapshot()["hardware"] provider; with a `check(op, args)` it also gates preflight
        # (T-028 register_hardware returns one)
        self._hardware = hardware
        self._awaiting = awaiting_return  # from the sample record at engine start
        self._on_awaiting = on_awaiting_return
        self._lock = threading.RLock()  # ops, owner, awaiting, session, life
        self._idle = threading.Condition(self._lock)
        self._emit_lock = threading.RLock()
        self._lights_lock = threading.Lock()  # one lights_off at a time
        self._sinks: list[EventSink] = []
        self._ops: OrderedDict[str, _Op] = OrderedDict()
        self._owner: _Op | None = None
        self._ids = itertools.count(1)
        self._session: dict | None = None  # {"session_id", "started_at"} from the server
        self._sample: dict = {"sample_id": None, "reserved": False}  # set by sample ops
        self._last_pos: dict | None = None
        self._last_lights: dict | None = None  # last state seen (readback or read)
        self._last_off: dict | None = None  # last all_off: records, verified, error
        self._last_status: dict | None = None
        self._info: Any = None  # BackendInfo, read once at start()
        self._info_dict: dict | None = None
        self._latest: tuple[Any, dict] | None = None  # newest frame (image, meta)
        self._latest_by_camera: dict[str, tuple[Any, dict]] = {}  # newest per camera
        self._frame_ids = itertools.count(1)
        self._last_shutdown = self._read_state(LAST_SHUTDOWN)  # ui-spec 5.2, first screen
        self._unclean: dict | None = None
        self._shutdown_rec: dict | None = None
        self._started = self._closed = False
        self._stop = threading.Event()
        self._poller: threading.Thread | None = None
        self._viewers: int | None = None  # unknown until the server reports (D14)
        self._viewers_gone_at: float | None = None
        self._gone_timer: threading.Timer | None = None

    # -- life

    def start(self) -> Runner:
        """Check the running mark (unclean shutdown), set it, start the position poller.
        Commands other than stops are refused until this has run."""
        with self._lock:
            if self._started:
                return self
            self._check_unclean()
            self._read_info()
            self._write_state(RUNNING_MARK, {"started_at": time.time(), "pid": os.getpid()})
            iv = self.config.position_interval_s
            if iv:
                self._poller = threading.Thread(target=self._poll, args=(iv,), daemon=True,
                                                name="engine-position")
                self._poller.start()
            self._started = True
        return self

    def shutdown(self, reason: str = "shutdown", timeout: float = 15.0) -> dict:
        """Lights off first, then abort and finish the records, stop the stream, keep the
        final readback for the next start and clear the running mark. Returns that record."""
        with self._lock:
            if self._closed:
                return self._shutdown_rec or {}
            self._closed = True
        t0 = time.time()
        self._emit(Event("log", data={"level": "info", "rule": "shutdown", "reason": reason,
                                      "t": t0, "text": f"engine shutdown: {reason}"}))
        off = self._new_op(LightsOff, Command("lights_off", args={"why": reason}))
        self._lights_off(off, timeout, preempt=False)  # the owner keeps running for now
        self._abort_all(f"shutdown: {reason}")
        self.wait_idle(timeout)
        try:
            self._stream.stop()
        except Exception:
            log.exception("stream stop failed")
        if self.dz_reader is not None:
            self.dz_reader.stop()
        # once more after everything ended: an op finishing in the window (light_set) may
        # have switched a light on again; this readback is the one the next start shows
        final = self._new_op(LightsOff, Command("lights_off", args={"why": reason}))
        self._lights_off(final, timeout, preempt=False)
        last = final.end_state.get("lights") or {}
        rec = {"t": time.time(), "reason": reason, "all_off": last.get("verified") is True,
               "records": last.get("records", []), "error": last.get("error")}
        self._write_state(LAST_SHUTDOWN, rec)
        self._shutdown_rec = rec
        self._stop.set()
        with self._lock:
            if self._gone_timer is not None:
                self._gone_timer.cancel()
                self._gone_timer = None
        if self._poller is not None:
            self._poller.join(timeout)
        self._clear_state(RUNNING_MARK)
        return rec

    def close(self, timeout: float = 15.0) -> None:
        self.shutdown("engine closing", timeout)

    def __enter__(self) -> Runner:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()

    def wait_idle(self, timeout: float | None = None) -> bool:
        """True once nothing is confirmed or running (tests, shutdown)."""
        with self._idle:
            return self._idle.wait_for(
                lambda: not any(o.state in ACTIVE for o in self._ops.values()), timeout)

    # -- EngineAPI

    def subscribe(self, sink: EventSink) -> Callable[[], None]:
        with self._emit_lock:
            self._sinks.append(sink)

        def unsubscribe() -> None:
            with self._emit_lock:
                if sink in self._sinks:
                    self._sinks.remove(sink)

        return unsubscribe

    def snapshot(self) -> dict:
        with self._lock:
            ops = list(self._ops.values())
            pending = []
            for o in ops:
                with o.cond:
                    pending += [{"op_id": o.op_id, **req} for req in o.pending.values()]
            return {
                "positions": self._last_pos,
                "lights": self._last_lights,
                "owner": self._owner.op_id if self._owner else None,
                "running": [o.public() for o in ops if o.state in ACTIVE],
                "proposals": [o.public() for o in ops if o.state == "proposed"],
                "pending_confirms": pending,
                "awaiting_return": self._awaiting,
                "session": self._session,
                "sample": {**self._sample,
                           "session_id": (self._session or {}).get("session_id")},
                "last_shutdown_lights": self._last_shutdown,
                "unclean_shutdown": self._unclean,
                "hardware": self._hardware_state(),
                "backend_info": self._info_dict,
                "stream": {"running": bool(self._stream.running())},
                "tweezers": state_of(self.tweezers),
                "piezo": piezo_state_of(self.piezo),
                "recent": [o.public() for o in ops if o.state in ENDED],
                "operations": self._registry.names(),
                "permissions": permission_table(),
                "config": asdict(self.config),
            }

    def submit(self, cmd: Command) -> str:
        stop = cmd.kind in ("abort", LIGHTS_OFF)
        if cmd.origin != "human" and cmd.kind != "start":
            raise self._refuse(cmd, cmd.op_id, "an assistant only proposes; a person decides")
        if cmd.remote and not (cmd.kind == "abort" and self.config.allow_remote_abort):
            why = ("a remote client may send abort only (D13)" if cmd.kind != "abort"
                   else "remote abort is switched off")
            raise self._refuse(cmd, cmd.op_id, why)
        if not stop and not self._started:
            raise self._refuse(cmd, cmd.op_id, "the engine has not started")
        if not stop and self._closed:
            raise self._refuse(cmd, cmd.op_id, "the engine is shutting down")
        return getattr(self, f"_on_{cmd.kind}")(cmd)

    # -- calls from the server

    def set_experiment_session(self, session_id: str | None,
                               started_at: float | None = None) -> None:
        """Open, close (None) or continue an experiment session (T-019). Rule 12 and the
        re-trace check read it."""
        with self._lock:
            prev = self._session
            self._session = ({"session_id": session_id, "started_at": started_at}
                             if session_id else None)
        sid = session_id or (prev or {}).get("session_id")
        self._emit(Event("session_changed", data={
            "session_id": sid, "started_at": started_at if session_id else None,
            "state": "open" if session_id else "closed"}, session_id=session_id))
        if prev and not session_id and self._started and not self._closed:
            # closing a session is a stop: abort what runs and switch everything off
            self.submit(Command("lights_off", args={"why": "session closed"}))

    def set_current_sample(self, sample_id: str | None, *, reserved: bool = False) -> None:
        """The sample on the stage (`sample_open` / `sample_new` call it through their
        context). `reserved`: picked with no session open, for the next session (T-019)."""
        with self._lock:
            self._sample = {"sample_id": sample_id, "reserved": bool(reserved and sample_id)}

    def set_local_viewers(self, count: int) -> None:
        """The server reports how many loopback browser connections are open (D14). At zero
        a timer starts; when it fires, running `watched` operations abort. Any viewer
        coming back first cancels it."""
        with self._lock:
            self._viewers = count
            if count > 0:
                self._viewers_gone_at = None
                if self._gone_timer is not None:
                    self._gone_timer.cancel()
                    self._gone_timer = None
                return
            if self._viewers_gone_at is None:
                self._viewers_gone_at = time.time()
        self._arm_gone_timer()

    def latest_frame(self) -> tuple[Any, dict] | None:
        """FrameSource for the server's `/ws/frames`: the newest frame only (uint16 ndarray,
        meta with `frame_id`), or None before the first one. Nothing is queued."""
        return self._latest

    def latest_frames(self) -> dict[str, tuple[Any, dict]]:
        """MultiFrameSource for `/ws/frames`: the newest frame of each camera, keyed by the
        camera label ("" for a frame that names none). Dual-camera setups send both."""
        with self._lock:
            return dict(self._latest_by_camera)

    def publish_frame(self, frame: Frame, source_op: str = "", op_id: str = "") -> int:
        """Called by operations (`ctx.publish_frame`) and the acquisition stream: keep it as
        the newest frame and announce it with a `frame_ready` carrying meta, never pixels.
        `piezo_z_um` is the piezo's z read now (None with no piezo), so stage z + piezo z is
        the focus height of the frame, with the same read-at-pop lag as `z_um`. `focus_dz` is
        the live gauge's signed reading (engine/live_dz.py), None when there is none."""
        piezo_z = self._piezo_z()
        dz = self._focus_dz(frame)
        with self._lock:
            frame_id = next(self._frame_ids)
            meta = {"frame_id": frame_id, **frame.meta(), "piezo_z_um": piezo_z,
                    "focus_dz": dz, "source_op": source_op}
            self._latest = (frame.image, meta)
            self._latest_by_camera[frame.camera or ""] = self._latest
        self._emit(Event("frame_ready", op_id, dict(meta)))
        return frame_id

    def _focus_dz(self, frame: Frame) -> dict | None:
        """The mock's truth when the frame has one, else the head's reading (the reader gets
        the frame and scores the newest on its own thread), else None. Display only."""
        if frame.dz_truth_dof is not None:
            return live_dz.truth_dz(frame.dz_truth_dof)
        rd = self.dz_reader
        if rd is None or (rd.camera is not None and frame.camera != rd.camera):
            return None
        return rd.feed(frame.image)

    def _piezo_z(self) -> float | None:
        """The piezo's z position (a read; nothing moves), None with no piezo or a failed read."""
        if self.piezo is None:
            return None
        try:
            return float(self.piezo.position().z_um)
        except Exception:  # noqa: BLE001 - a frame is never lost to a piezo read
            return None

    def plan(self, cmd: Command) -> dict:
        """Only the operation's `plan` step, with no hardware behind it (screen GET plan)."""
        cls = self._registry.get(cmd.op)
        if cls is None:
            raise CommandRefused("", f"unknown operation {cmd.op!r}")
        op = _Op(op_id=f"{cls.name}_plan", op=cls.name, cls=cls, args=dict(cmd.args),
                 origin=cmd.origin, user_id=cmd.user_id, session_id=cmd.session_id,
                 quiet=True)
        return {"op": cls.name, "args": dict(op.args),
                "plan": cls(OpContext(self, op, backend=_NoHardware())).plan()}

    # -- command handlers

    def _on_start(self, cmd: Command) -> str:
        if cmd.op == LIGHTS_OFF:
            raise self._refuse(cmd, "", "lights_off is a command kind, not an operation")
        cls = self._registry.get(cmd.op)
        if cls is None:
            raise self._refuse(cmd, "", f"unknown operation {cmd.op!r}")
        op = self._new_op(cls, cmd)
        if cmd.origin == "assistant" and not cmd.confirmed_by:
            op.state = "proposed"
            self._keep(op)
            self._emit_op(op, "proposed", {"op": op.op, "args": dict(op.args),
                                           "proposal_id": op.proposal_id,
                                           "conversation_id": op.conversation_id})
            return op.op_id
        if cmd.confirmed_by and cmd.confirmed_by != cmd.user_id:
            raise self._refuse(cmd, op.op_id, "confirmed_by must be the user who sends it")
        if why := self._unauthorized(cmd, op.op):
            raise self._refuse(cmd, op.op_id, why)
        # an assistant command here was confirmed on its T-013 card by `confirmed_by`
        op.confirmed_by, op.confirmed_at = cmd.confirmed_by or cmd.user_id, cmd.t
        return self._launch(op, cmd, approved=cmd.origin == "assistant")

    def _on_lights_off(self, cmd: Command) -> str:
        op = self._new_op(LightsOff, cmd)
        op.confirmed_by, op.confirmed_at = cmd.user_id, cmd.t
        return self._launch(op, cmd)

    def _on_approve(self, cmd: Command) -> str:
        op = self._ops.get(cmd.op_id)
        if op is None or op.state != "proposed":
            raise self._refuse(cmd, cmd.op_id, "no proposal with that op_id")
        if why := self._unauthorized(cmd, op.op):
            raise self._refuse(cmd, op.op_id, why)
        with self._lock:  # two approves at once: only one launches
            taken = op.state == "proposed"
            if taken:
                op.state = "approving"
        if not taken:
            raise self._refuse(cmd, op.op_id, "no proposal with that op_id")
        op.confirmed_by, op.confirmed_at = cmd.user_id, cmd.t
        op.user_id, op.session_id = cmd.user_id, self._session_of(cmd) or op.session_id
        try:
            return self._launch(op, cmd, approved=True)
        except CommandRefused:
            op.state = "proposed"  # busy: the card stays and can be approved again
            raise

    def _on_reject(self, cmd: Command) -> str:
        op = self._ops.get(cmd.op_id)
        if op is None or op.state != "proposed":
            raise self._refuse(cmd, cmd.op_id, "no proposal with that op_id")
        self._reject(op, cmd)
        return op.op_id

    def _on_abort(self, cmd: Command) -> str:
        why = str(cmd.args.get("why") or "abort")
        with self._lock:
            if cmd.op_id:
                op = self._ops.get(cmd.op_id)
                targets = [op] if op is not None and op.state not in ENDED else []
            else:
                targets = [o for o in self._ops.values() if o.state in ACTIVE]
        if cmd.op_id and not targets:
            raise self._refuse(cmd, cmd.op_id, "nothing to abort with that op_id")
        for op in targets:
            if cmd.remote:
                self._emit_op(op, "log", {"level": "warning", "rule": "D13",
                                          "trigger": cmd.user_id or "remote client",
                                          "t": cmd.t, "text": "abort from a remote client"})
            if op.state == "proposed":
                self._reject(op, cmd)
            else:
                self._request_abort(op, why)
        return cmd.op_id

    def _on_confirm(self, cmd: Command) -> str:
        op, key = self._ops.get(cmd.op_id), cmd.args.get("key")
        if op is None:
            raise self._refuse(cmd, cmd.op_id, "no operation with that op_id")
        ok = _is_yes(cmd.args)
        if ok and (why := self._unauthorized(cmd, op.op)):  # "no" is a stop: always taken
            raise self._refuse(cmd, op.op_id, why)
        with op.cond:
            req = op.pending.pop(key, None)  # taken here, so a second answer finds nothing
        if req is None:
            raise self._refuse(cmd, op.op_id, f"no confirm_required {key!r} waiting")
        rec = {"key": key, "kind": req["kind"], "ok": ok,
               "answer": str(cmd.args.get("answer", "yes" if ok else "no")),
               "by": cmd.user_id, "at": cmd.t, "session_id": cmd.session_id}
        if req["kind"] == "manual_step":
            rec["manual_step"] = {"step": req["context"].get("step", key), **req["context"],
                                  "ok": ok, "confirmed_at": cmd.t, "by": cmd.user_id}
            op.manual_steps.append(rec["manual_step"])
        # announce first, then wake the operation, so `confirmed` precedes what follows
        self._emit_op(op, "confirmed", rec)
        with op.cond:
            op.answers[key] = rec
            op.cond.notify_all()
        return op.op_id

    def _on_update(self, cmd: Command) -> str:
        op = self._ops.get(cmd.op_id)
        if op is None or op.state not in ACTIVE or op.instance is None:
            raise self._refuse(cmd, cmd.op_id, "no running operation with that op_id")
        if why := self._unauthorized(cmd, op.op):
            raise self._refuse(cmd, op.op_id, why)
        bad = sorted(set(cmd.args) - op.cls.updatable)
        if bad:
            raise self._refuse(cmd, op.op_id, f"{op.op} cannot update {bad}; "
                                               f"updatable: {sorted(op.cls.updatable)}")
        op.instance.update(dict(cmd.args))
        self._emit_op(op, "updated", {"op": op.op, "args": dict(cmd.args), "by": cmd.user_id})
        return op.op_id

    # -- dispatch

    def _session_of(self, cmd: Command) -> str | None:
        return cmd.session_id or (self._session or {}).get("session_id")

    def _new_op(self, cls: type[Operation], cmd: Command) -> _Op:
        return _Op(op_id=f"{cls.name}_{next(self._ids)}", op=cls.name, cls=cls,
                   args=dict(cmd.args), origin=cmd.origin, user_id=cmd.user_id,
                   session_id=self._session_of(cmd), proposal_id=cmd.proposal_id,
                   conversation_id=cmd.conversation_id)

    def _keep(self, op: _Op) -> None:
        with self._lock:
            self._ops[op.op_id] = op
            ended = [k for k, o in self._ops.items() if o.state in ENDED]
            for k in ended[: max(0, len(ended) - self.config.keep_ended)]:
                del self._ops[k]

    def _prepare(self, op: _Op) -> None:
        op.state = "confirmed"
        op.record = self._records(op.meta())
        op.instance = op.cls(OpContext(self, op))
        self._keep(op)

    def _launch(self, op: _Op, cmd: Command, approved: bool = False) -> str:
        if op.cls is not LightsOff:  # lights_off pre-empts; it takes the core in its thread
            with self._lock:
                busy = self._owner.op_id if op.cls.exclusive and self._owner else None
                if op.cls.exclusive and busy is None:
                    self._owner = op
            if busy:
                raise self._refuse(cmd, op.op_id, f"busy: {busy} holds the core")
        self._prepare(op)
        if approved:
            self._emit_op(op, "approved", {"op": op.op, "proposal_id": op.proposal_id,
                                           "conversation_id": op.conversation_id,
                                           "by": op.confirmed_by, "at": op.confirmed_at})
        target = self._lights_off if op.cls is LightsOff else self._work
        op.thread = threading.Thread(target=target, args=(op,), daemon=True, name=op.op_id)
        op.thread.start()
        if op.cls.watched:
            self._arm_gone_timer()  # started with no local viewer left: D14 still applies
        return op.op_id

    def _reject(self, op: _Op, cmd: Command) -> None:
        with self._lock:
            op.state = "rejected"
            self._idle.notify_all()
        self._emit_op(op, "rejected", {"op": op.op, "proposal_id": op.proposal_id,
                                       "conversation_id": op.conversation_id,
                                       "by": cmd.user_id, "at": cmd.t})

    def _abort_all(self, why: str) -> None:
        with self._lock:
            targets = [o for o in self._ops.values() if o.state in ACTIVE]
        for op in targets:
            self._request_abort(op, why)

    def _request_abort(self, op: _Op, why: str) -> None:
        if op.cls is LightsOff:
            return  # switching off is the stop itself; it always runs to the end
        with op.cond:
            if not op.abort_evt.is_set():
                op.why = why
            op.abort_evt.set()
            op.cond.notify_all()
        if op.instance is not None:
            try:
                op.instance.abort()
            except Exception:
                log.exception("abort hook of %s failed", op.op_id)

    def _lights_off(self, op: _Op, timeout: float | None = None, preempt: bool = True) -> None:
        """Pre-emption: abort the core's owner, wait for its exit path, then switch off.
        `preempt=False` (shutdown) switches off at once and leaves the owner to its abort."""
        if op.instance is None:  # shutdown builds it directly
            self._prepare(op)
        with self._lights_lock:
            if preempt:
                with self._lock:
                    prev, self._owner = self._owner, op
                if prev is not None and prev is not op:
                    self._request_abort(prev, LIGHTS_OFF)
                    if prev.thread is not None:
                        prev.thread.join(self.config.preempt_wait_s if timeout is None
                                         else timeout)
                        if prev.thread.is_alive():
                            op.hand_back = prev  # it may still drive hardware: keep it owned
                            self._emit_op(op, "log", {"level": "warning",
                                                      "text": f"{prev.op_id} did not exit; "
                                                              "switching off anyway"})
            self._work(op)

    def _work(self, op: _Op) -> None:
        inst, cls = op.instance, op.cls
        assert inst is not None
        state, summary, err = "error", {}, None
        touched = paused = False
        try:
            inst.ctx.check()
            self._emit_op(op, "planned", {"op": op.op, "plan": inst.plan(), "args": op.args})
            checks = self._runner_checks(op) + list(inst.preflight() or [])
            if not all(c.get("ok") for c in checks):
                self._emit_op(op, "preflight_failed", {"op": op.op, "checks": checks})
                err = ("preflight failed", "preflight")
                return
            self._emit_op(op, "preflight_ok", {"op": op.op, "checks": checks})
            inst.ctx.check()
            if cls.snaps and self._stream.running():
                self._stream.pause()
                paused = True
            op.state = "running"
            touched = cls.exclusive
            start_state = self._state_now(cls)
            op.lights_before = start_state.get("lights")
            self._emit_op(op, "started", {**op.meta(), "args": dict(op.args),
                                          "start_state": start_state})
            summary = dict(inst.run() or {})
            # abort asked while run() was returning: it ends aborted, lights off
            state = "aborted" if op.abort_evt.is_set() else "finished"
        except Aborted:
            state = "aborted"
        except Exception as e:
            err = (f"{type(e).__name__}: {e}", _where(e))
            log.exception("%s failed", op.op_id)
        finally:
            self._end(op, state, summary, err, touched=touched, paused=paused)

    def _end(self, op: _Op, state: str, summary: dict, err: tuple | None, *, touched: bool,
             paused: bool) -> None:
        cls, end = op.cls, dict(op.end_state)
        if summary.get("state") == "awaiting_return":  # e.g. return_xy goes with it
            end = {**summary, **end}
        if cls.exclusive:
            end["lights"] = self._exit_lights(op, state, touched)
        if paused:
            try:
                self._stream.resume()
            except Exception as e:
                self._emit_op(op, "error", {"op": op.op, "where": "exit",
                                            "message": f"stream resume failed: {e}"})
        self._track_awaiting(op, state, end)
        if op.op == "status" and state == "finished":
            self._last_status = {"op_id": op.op_id, "t": time.time(), "summary": summary}
        op.end_state = end
        with self._lock:
            op.state = state
            if self._owner is op:
                back = op.hand_back
                self._owner = back if back is not None and back.state not in ENDED else None
            self._idle.notify_all()
        record_dir = getattr(op.record, "dir", None)
        if state == "finished":
            data = {"op": op.op, "summary": summary, "end_state": end,
                    "manual_steps": op.manual_steps, "record_dir": record_dir}
        elif state == "aborted":
            data = {"op": op.op, "why": op.why, "end_state": end, "record_dir": record_dir}
        else:
            message, where = err or ("error", "")
            data = {"op": op.op, "message": message, "where": where, "end_state": end,
                    "record_dir": record_dir}
        # the record is complete before anyone hears the operation ended
        ev = Event(state, op.op_id, data, user_id=op.user_id, session_id=op.session_id)
        try:
            op.record.event(ev)
            op.record.close({**op.meta(), "state": state, **data})
        except Exception:
            log.exception("record close of %s failed", op.op_id)
        self._emit(ev)

    def _exit_lights(self, op: _Op, state: str, touched: bool) -> dict:
        """The exit-path light rule, recorded as `rule`:
        - `restore`: a normal finish turns off only what this operation turned on, so a
          light_set survives a following status;
        - `keep`: light_set (`keep_lights_on_finish`) finishing leaves its light as set;
        - `all_off`: abort, error, lights_off, shutdown, D14 and session close;
        - `untouched`: the operation never started, so nothing was commanded.
        Every rule ends with a readback of the end state (`records`, `verified`), also when
        nothing was switched here, e.g. scan_4x switching off in its own finally."""
        cls = op.cls
        if cls is LightsOff and state == "finished":
            return {**(self._last_off or {}), "off": True, "rule": "all_off"}
        if not touched:
            return {**self._read_back([], set()), "rule": "untouched"}
        if state == "finished" and cls.keep_lights_on_finish:
            return {**self._read_back([], set()), "rule": "keep"}
        if state == "finished":
            try:
                return {**self._restore_lights(op), "rule": "restore"}
            except Exception as e:  # cannot tell what to keep: switch everything off
                self._emit_op(op, "log", {"level": "warning",
                                          "text": f"light restore failed ({e}); all off"})
        try:
            self._switch_off(op)
            return {**self._last_off, "off": True, "rule": "all_off"}
        except Exception as e:
            self._emit_op(op, "error", {"op": op.op, "where": "exit",
                                        "message": f"lights off failed: {e}"})
            self._last_off = {**self._light_payload([], False), "error": str(e)}
            return {**self._last_off, "off": False, "rule": "all_off"}

    def _restore_lights(self, op: _Op) -> dict:
        before = op.lights_before or {}
        now = dict(self._backend.light_state())
        recs: list[dict] = []
        for device, off in (("Aura", self._backend.aura_off), ("DiaLamp", self._backend.lamp_off)):
            was_on = (before.get(device.lower()) or {}).get("state") == "on"
            if _on_off(now.get(device)) != "off" and not was_on:
                recs += [asdict(r) for r in off()]
        for r in recs:
            self._emit_op(op, "property_set", {"device": r["device"], "property": r["prop"],
                                               "wanted": r["wanted"], "read": r["read"],
                                               "verified": r["verified"]})
        off_wanted = {d for d in ("Aura", "DiaLamp")
                      if (before.get(d.lower()) or {}).get("state") != "on"}
        lights = self._read_back(recs, off_wanted)
        if recs:
            self._emit_op(op, "light_changed", lights)
        return lights

    def _read_back(self, switched: list[dict], off_wanted: set[str]) -> dict:
        """The end state as read: one State record per light (`source: end_read`), wanted
        off for the lights in `off_wanted` and as found for the others, after the readbacks
        of anything switched here. `verified` is True only if every record verifies; a
        failed read is False with the error."""
        try:
            now = dict(self._backend.light_state())
        except Exception as e:
            payload = self._light_payload(switched, False)
            return {**payload, "error": payload.get("error") or str(e)}
        reads = []
        for device in ("Aura", "DiaLamp"):
            read = str(now.get(device, ""))
            off = device in off_wanted
            ok = _on_off(read) == "off" if off else _on_off(read) != "unknown"
            reads.append({"device": device, "prop": "State", "wanted": "0" if off else read,
                          "read": read, "verified": ok, "t": time.time(),
                          "source": "end_read"})
        recs = switched + reads
        lights = self._light_payload(recs, _verified(recs))
        self._last_lights = lights
        return lights

    def _runner_checks(self, op: _Op) -> list[dict]:
        checks = []
        aw = self._awaiting
        if aw and op.cls.motion and not op.instance.returns_to_sample():
            checks.append({"name": "awaiting_return", "ok": False, "want": "sample returned",
                           "read": aw.get("op_id"), "why": AWAITING_WHY})
        if op.cls.approaches and op.instance.clearance() is None and self._on_bench():
            checks.append({"name": "approach_clearance", "ok": False,
                           "want": "a clearance callback", "read": {"bench": True},
                           "why": "on the bench an approach needs a clearance check"})
        gate = self._gate_check(op)
        if gate is not None:
            checks.append(gate)
        return checks

    def _gate_check(self, op: _Op) -> dict | None:
        """The hardware gates (T-028): the `hardware` provider's `check(op, args) -> (ok,
        reasons)`. No provider, or one without `check` (tests, mock without a profile), keeps
        the runner as it was. A provider that raises or answers nonsense fails closed with
        the error as the reason. lights_off is a stop and is never gated."""
        check = getattr(self._hardware, "check", None)
        if check is None or op.cls is LightsOff:
            return None
        try:
            ok, reasons = check(op.op, dict(op.args))
            reasons = [str(r) for r in (reasons or [])]
        except Exception as e:
            return {"name": "hardware_gate", "ok": False, "want": "the gate's answer",
                    "read": f"{type(e).__name__}: {e}",
                    "why": f"hardware gate check failed ({type(e).__name__}: {e}); refused"}
        if ok is True:
            return None
        return {"name": "hardware_gate", "ok": False, "want": "gate open", "read": reasons,
                "why": "; ".join(reasons) or f"the hardware gate refuses {op.op}"}

    def _on_bench(self) -> bool:
        """The shared rule `backend.is_bench` (T-015b) on the start() info or, if that read
        failed, a fresh one. No info, an unknown kind or a missing flag is the bench: the
        strict side."""
        return is_bench(self._info or self._read_info())

    def _read_info(self) -> Any:
        try:
            info = self._backend.info()
            self._info, self._info_dict = info, info.to_dict()
        except Exception:
            log.exception("backend info() failed")
            return None
        return info

    def check(self, ops: list[str] | None = None, context: dict | None = None) -> dict:
        """`{op: {allowed, reason}}` for the screens (T-009b `GET /api/permissions`), from
        the permission table and the engine state. `context`: `user_id`, `control_grant`,
        `session_id` of the asking person, and optional `args` per op (e.g. objective_change
        `{"resume": true}`). The server adds remote and login state on top."""
        ctx = context or {}
        probe = Command("start", user_id=ctx.get("user_id"), session_id=ctx.get("session_id"),
                        control_grant=ctx.get("control_grant"))
        names = ops if ops is not None else sorted(set(PERMISSIONS) | set(self._registry.names()))
        with self._lock:
            owner = self._owner.op_id if self._owner else None
        out = {}
        for name in names:
            out[name] = {"allowed": False, "reason": self._why_not(name, probe, owner, ctx)}
            out[name]["allowed"] = out[name]["reason"] is None
        return out

    def _why_not(self, name: str, probe: Command, owner: str | None, ctx: dict) -> str | None:
        if permission(name).action == "stop":
            return None  # abort and lights_off: always
        if not self._started or self._closed:
            return "the engine is not running"
        cls = self._registry.get(name)
        if cls is None:
            return f"{name} is not available yet"
        if why := self._unauthorized(probe, name):
            return why
        if cls.exclusive and owner:
            return f"busy: {owner} holds the core"
        if self._awaiting and cls.motion:
            op = _Op(op_id=f"{name}_check", op=name, cls=cls,
                     args=dict((ctx.get("args") or {}).get(name, {})), origin="human",
                     user_id=probe.user_id, session_id=probe.session_id, quiet=True)
            if not cls(OpContext(self, op, backend=_NoHardware())).returns_to_sample():
                return AWAITING_WHY
        return None

    def _track_awaiting(self, op: _Op, state: str, end: dict) -> None:
        if end.get("state") == "awaiting_return":
            new = {"op": op.op, "op_id": op.op_id, "t": time.time(),
                   **{k: v for k, v in end.items() if k not in ("lights", "state")}}
        elif op.instance.returns_to_sample() and state == "finished":
            new = None
        else:
            return
        with self._lock:
            self._awaiting = new
        if self._on_awaiting is not None:
            try:
                self._on_awaiting(new)
            except Exception:
                log.exception("awaiting_return hook failed")

    # -- D14

    def _arm_gone_timer(self) -> None:
        with self._lock:
            if (not self.config.abort_when_local_gone or self._viewers != 0
                    or self._gone_timer is not None or self._stop.is_set()):
                return
            if not any(o.cls.watched and o.state in ACTIVE for o in self._ops.values()):
                return
            t = threading.Timer(self.config.local_gone_abort_s, self._viewers_gone)
            t.daemon = True
            self._gone_timer = t
        t.start()

    def _viewers_gone(self) -> None:
        with self._lock:
            self._gone_timer = None
            if self._viewers != 0:
                return
            gone_at = self._viewers_gone_at
            targets = [o for o in self._ops.values() if o.cls.watched and o.state in ACTIVE]
        for op in targets:
            self._emit_op(op, "log", {
                "level": "warning", "rule": "D14", "trigger": "no local viewer",
                "t": time.time(), "last_viewer_dropped_at": gone_at,
                "text": f"no microscope-PC viewer for {self.config.local_gone_abort_s:g} s"})
            self._request_abort(op, "D14: no local viewer")

    # -- hardware helpers (all through the serialized backend)

    def _switch_off(self, op: _Op) -> list[dict]:
        recs = [asdict(r) for r in self._backend.all_off()]
        for r in recs:
            self._emit_op(op, "property_set", {"device": r["device"], "property": r["prop"],
                                               "wanted": r["wanted"], "read": r["read"],
                                               "verified": r["verified"]})
        lights = self._light_payload(recs, _verified(recs))
        self._last_lights = self._last_off = lights
        self._emit_op(op, "light_changed", lights)
        return recs

    def _read_lights(self) -> dict:
        lights = self._light_payload([], None)
        if "error" not in lights:
            self._last_lights = lights
        return lights

    def _light_payload(self, recs: list[dict], verified: bool | None) -> dict:
        """The one light shape (light_changed, snapshot, records): `{dialamp: {state,
        intensity}, aura: {state, lines: {LINE: percent}}, verified, records}`. States are
        "on" / "off" / "unknown"; a read that fails leaves its field None or unknown."""
        state = {r["device"]: r["read"] for r in recs if r.get("prop") == "State"}
        error = None
        try:
            state = {**dict(self._backend.light_state()), **state}
        except Exception as e:
            error = str(e)
        out = _light_shape(state, self._prop, recs, verified)
        if error is not None:
            out["error"] = error
        return out

    def _normalise_light(self, data: dict) -> dict:
        """Any `light_changed` payload in the one shape (T-011e). guards and light_set emit
        `{readbacks, verified, error}` or `{switched_off, state, why, ...}`; their readbacks
        become `records` and the states come from what they read. Nothing is read from the
        hardware here, so an emit never waits behind a long backend call."""
        if "dialamp" in data and "aura" in data:
            return data
        recs = [dict(r) for r in (data.get("readbacks") or data.get("records") or [])]
        state = {k: str(v) for k, v in (data.get("state") or {}).items()}
        state.update({r["device"]: r["read"] for r in recs if r.get("prop") == "State"})
        props = {(r.get("device"), r.get("prop")): r.get("read") for r in recs}
        verified = data.get("verified", _verified(recs) if recs else None)
        out = _light_shape(state, lambda d, p: props.get((d, p)), recs, verified)
        for key in ("error", "why", "switched_off"):
            if data.get(key) is not None:
                out[key] = data[key]
        return out

    def _prop(self, device: str, prop: str) -> str | None:
        try:
            return self._backend.read_property(device, prop)
        except Exception:
            return None

    def _state_now(self, cls: type[Operation]) -> dict:
        if not cls.exclusive:
            return {}
        try:
            pos = asdict(self._backend.positions())
        except Exception as e:
            pos = {"errors": {"read": str(e)}}
        return {"positions": pos, "lights": self._read_lights()}

    def _hardware_state(self) -> dict:
        hw: dict = {"profile": None, "profile_path": None, "gates": {}}
        if self._hardware is not None:
            try:
                hw.update(self._hardware())
            except Exception as e:
                hw["error"] = str(e)
        return {**hw, "last_status": self._last_status}

    def _poll(self, interval: float) -> None:
        lock = self._backend.lock
        while not self._stop.wait(interval):
            if not lock.acquire(timeout=interval):
                continue  # the running operation holds the core; skip this tick
            try:
                pos = self._backend.positions()
            except Exception as e:
                pos = Positions(errors={"read": str(e)})
            finally:
                lock.release()
            self._last_pos = asdict(pos)
            self._emit(Event("position", data=dict(self._last_pos)))

    # -- state files (running mark, last shutdown)

    def _check_unclean(self) -> None:
        mark = self._read_state(RUNNING_MARK)
        if mark is None:
            return
        self._unclean = {"detected_at": time.time(), "mark": mark,
                         "lights": self._read_lights()}
        try:
            with (self._state_dir / UNCLEAN_LOG).open("a", encoding="utf-8") as f:
                f.write(json.dumps(self._unclean) + "\n")
        except OSError:
            log.exception("could not record the unclean shutdown")
        self._emit(Event("log", data={"level": "warning", "rule": "unclean_shutdown",
                                      "text": "the engine did not shut down cleanly last time",
                                      **self._unclean}))

    def _read_state(self, name: str) -> dict | None:
        if self._state_dir is None:
            return None
        path = self._state_dir / name
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.exception("could not read %s", path)
            return {"unreadable": str(path)}

    def _write_state(self, name: str, data: dict) -> None:
        if self._state_dir is None:
            return
        path = self._state_dir / name
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            log.exception("could not write %s", path)

    def _clear_state(self, name: str) -> None:
        if self._state_dir is not None:
            (self._state_dir / name).unlink(missing_ok=True)

    # -- rule 12 and events

    def _unauthorized(self, cmd: Command, op: str) -> str | None:
        """The grant comes from `cmd.control_grant`, set by the server; anything token-like
        inside `cmd.args` is never looked at."""
        perm = permission(op)
        if perm.control:
            try:  # fail closed: a control seat that breaks refuses, with the reason
                held = self._control.check(cmd.user_id, cmd.control_grant) is True
            except Exception as e:
                return f"control check failed ({type(e).__name__}: {e}); refused"
            if not held:
                return f"user {cmd.user_id!r} does not hold equipment control"
        if perm.session:
            open_id = (self._session or {}).get("session_id")
            if open_id is None:
                return "no open experiment session"
            if cmd.session_id not in (None, open_id):
                return f"session {cmd.session_id!r} is not the open session {open_id!r}"
        return None

    def _refuse(self, cmd: Command, op_id: str, why: str) -> CommandRefused:
        self._emit(Event("refused", op_id, {"command": cmd.kind, "op": cmd.op, "why": why,
                                            "origin": cmd.origin, "remote": cmd.remote},
                         user_id=cmd.user_id, session_id=cmd.session_id))
        return CommandRefused(op_id, why)

    def _emit_op(self, op: _Op, kind: str, data: dict) -> Event:
        ev = Event(kind, op.op_id, data, user_id=op.user_id, session_id=op.session_id)
        if not op.quiet:
            self._emit(ev, op.record)
        return ev

    def _emit(self, ev: Event, record: Any = None) -> None:
        if ev.kind == "light_changed":  # one shape on the wire and in the records (T-011e)
            ev = replace(ev, data=self._normalise_light(ev.data))
            self._last_lights = ev.data
        with self._emit_lock:
            if record is not None:
                try:
                    record.event(ev)
                except Exception:
                    log.exception("record write failed for %s", ev.op_id)
            for sink in list(self._sinks):
                try:
                    sink(ev)
                except Exception:
                    log.exception("event sink failed")


def _is_yes(args: dict) -> bool:
    if "ok" in args:
        return bool(args["ok"])
    return str(args.get("answer", "")).lower() in YES


def _where(e: BaseException) -> str:
    tb = traceback.extract_tb(e.__traceback__)
    return f"{tb[-1].filename}:{tb[-1].lineno}" if tb else ""


def _verified(recs: list[dict]) -> bool:
    return bool(recs) and all(r["verified"] for r in recs)  # an empty readback proves nothing


def _light_shape(state: dict, prop: Callable[[str, str], str | None], recs: list[dict],
                 verified: bool | None) -> dict:
    """`{dialamp: {state, intensity}, aura: {state, lines: {LINE: percent}}, verified,
    records}` from device states and a property reader. Aura lines are read only while Aura
    is not off; a line counts when its switch reads on or, without a switch, has power."""
    out = {"dialamp": {"state": _on_off(state.get("DiaLamp")),
                       "intensity": _number(prop("DiaLamp", "Intensity"))},
           "aura": {"state": _on_off(state.get("Aura")), "lines": {}},
           "verified": verified, "records": recs}
    if out["aura"]["state"] == "off":
        return out
    for line in AURA_LINES:
        on = _on_off(prop("Aura", line))
        if on == "off":
            continue
        permille = _number(prop("Aura", f"{line}_Intensity"))
        if on == "on" or permille:
            out["aura"]["lines"][line] = None if permille is None else permille / 10
    return out


def _on_off(v: object) -> str:
    v = None if v is None else str(v).strip().lower()
    return {"1": "on", "on": "on", "open": "on", "0": "off", "off": "off",
            "closed": "off"}.get(v, "unknown")


def _number(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
