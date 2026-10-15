"""Sample operations (F3, WP-H): choose a sample, enter its geometry, confirm the loading,
and mark the hole boundary. Op names follow docs/screens/sample.md section 4.

    sample_open{sample_id}          choose the sample for the next session; nothing moves
    sample_new{}                    reserve a new id and its legacy folder; no event
    sample_geometry_set{sample_id, values}
    loading_confirm_person{sample_id}
    loading_check_image{sample_id}  brightfield on, one 4x frame, light off; classical check
    boundary_mark{sample_id, x_um, y_um} / boundary_undo{sample_id} / boundary_reset{sample_id}

Storage (manager decision): the truth is the open experiment session's sample events
(T-019 `records/sample_events.jsonl`), written through `session.sample_event()` and read
back through `engine.sample.read_sample`, which projects the one fold. The legacy sample
folder keeps the derived sample.json / map.json and the image-check frames.

One sample per experiment session: sample_open and sample_new run with no session open, or
with the session of that same sample, and refuse otherwise; every other op needs the open
session of its sample. A refusal writes nothing.

Two ways to run, one code path: `_prepare` does every check and returns the work, which runs
either under the T-002 lifecycle (`run_sample_op`, record folder in the legacy sample
folder) or under the T-011 runner (the registered `Operation` classes below; the runner
owns the record, the permission table, the lights' exit path and the events). The runner
reaches the records store and the open session through `install_sample_seat`.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .. import guards
from ..backend import Backend
from ..events import Event, EventSink, fan_out, null_sink
from ..guards import GuardError, operation, plain, registry_key
from ..records import OpRecord
from ..runner import Operation, register_operation
from ..sample import (
    BOUNDARY_UNDO,
    GEOMETRY_SET,
    LOADING_STEP,
    SAMPLE_CREATED,
    SAMPLES_ROOT,
    GeometryError,
    Sample,
    read_sample,
    validate_geometry,
    write_derived_views,
)

SAMPLE_OPEN, SAMPLE_NEW = "sample_open", "sample_new"
GEOMETRY_SET_OP = "sample_geometry_set"
CONFIRM_PERSON, CHECK_IMAGE = "loading_confirm_person", "loading_check_image"
BOUNDARY_MARK, BOUNDARY_UNDO_OP, BOUNDARY_RESET = "boundary_mark", "boundary_undo", "boundary_reset"
OPS = (SAMPLE_OPEN, SAMPLE_NEW, GEOMETRY_SET_OP, CONFIRM_PERSON, CHECK_IMAGE, BOUNDARY_MARK,
       BOUNDARY_UNDO_OP, BOUNDARY_RESET)

# loading_check_image: the frame must be readable and show structure (the hole edge, the
# chamber) rather than a flat field. Unmeasured provisional (checklist: brightfield 4x).
CHECK_OBJECTIVE = "4x"
MAX_SATURATED_FRACTION = 0.001  # same limit as focus.classical
MIN_RANGE_ADU = 20.0  # p99.9 - p0.1; focus.verdict's MIN_DYNAMIC_RANGE_ADU
MIN_STRUCTURE_RATIO = 3.0  # image spread / pixel noise; ~1 for a flat or dark field
FRAMES_DIR = "loading_check"  # in the legacy sample folder

NO_LIGHT = {"switched_off": False, "why": "record-only operation; no light was touched",
            "verified": None}


class Refused(Exception):
    """A preflight refusal: reported as preflight_failed, nothing written."""


@dataclass
class SampleContext:
    """What the sample ops need: the records store, the legacy root, the open experiment
    session object (or None) and the user."""

    store: Any  # records.store.RecordsStore
    samples_root: Path = SAMPLES_ROOT
    session: Any = None  # records.session.ExperimentSession, open, or None
    user_id: str | None = None

    @property
    def session_id(self) -> str | None:
        return self.session.session_id if self._open() else None

    def _open(self) -> bool:
        return self.session is not None and bool(self.session.writable)

    def open_sample(self) -> str | None:
        return self.session.info.sample_id if self._open() else None


@dataclass
class _IO:
    """What a prepared op's work may do besides writing sample events."""

    emit: Callable[[str, dict], None]  # (event kind, data)
    backend: Any = None
    lamp_on: Callable[[], Any] | None = None
    set_current_sample: Callable[[str, bool], None] | None = None


Work = Callable[[_IO], dict]


def ensure_sample_created(session: Any, store: Any) -> bool:
    """Write `sample_created` as the first event when a session opens for a sample with no
    events yet. Whoever opens the session (server / set_experiment_session) calls it."""
    from dino_autofocus.records.session import sample_state

    if session is None or not session.writable:
        return False
    if sample_state(store, session.info.sample_id).n_events:
        return False
    session.sample_event(SAMPLE_CREATED)
    return True


# -- checks ---------------------------------------------------------------------------------
def _sample_id(args: dict) -> str:
    from dino_autofocus.records.layout import check_id

    sid = args.get("sample_id")
    try:
        return check_id(sid)
    except ValueError:
        raise Refused(f"not a valid sample id: {sid!r}") from None


def _only(args: dict, allowed: set[str]) -> None:
    extra = sorted(set(args) - allowed)
    if extra:
        raise Refused(f"unknown arguments: {extra}")


def _no_other_session(env: SampleContext, sample_id: str | None) -> None:
    open_for = env.open_sample()
    if open_for is not None and open_for != sample_id:
        raise Refused(f"an experiment session is open for sample {open_for}; close it first "
                      "(one sample per session)")


def _need_session(env: SampleContext, sample_id: str) -> Any:
    open_for = env.open_sample()
    if open_for is None:
        raise Refused("needs an open experiment session for this sample")
    if open_for != sample_id:
        raise Refused(f"the open experiment session is for sample {open_for}, not {sample_id}")
    return env.session


def _view(env: SampleContext, sample_id: str):
    return read_sample(env.store, sample_id, env.samples_root, env.session_id)


def structure_check(img: np.ndarray, ceiling: int) -> dict:
    """Classical loading check on one brightfield frame: readable (not clipped, some range)
    and showing structure, measured as the frame's spread over its pixel noise (the noise
    from neighbouring-pixel differences). grade "computed", never a model number."""
    a = np.asarray(img, dtype=np.float64)
    sat = float(np.mean(a >= ceiling))
    lo, hi = np.percentile(a, (0.1, 99.9))
    d = np.diff(a, axis=1)
    noise = float(1.4826 * np.median(np.abs(d - np.median(d))) / math.sqrt(2.0))
    ratio = float(a.std() / max(noise, 1e-6))
    why = None
    if sat > MAX_SATURATED_FRACTION:
        why = f"{100 * sat:.2f} % of pixels clipped; lower the exposure"
    elif hi - lo < MIN_RANGE_ADU:
        why = f"brightness range {hi - lo:.0f} ADU < {MIN_RANGE_ADU:.0f}: no light or no sample"
    elif ratio < MIN_STRUCTURE_RATIO:
        why = (f"structure ratio {ratio:.2f} < {MIN_STRUCTURE_RATIO:.1f}: a flat field, "
               "nothing in view")
    return {"ok": why is None, "metric": "structure_ratio", "value": round(ratio, 3),
            "grade": "computed", "why": why, "saturated_fraction": sat,
            "range_adu": float(hi - lo),
            "thresholds": {"min_structure_ratio": MIN_STRUCTURE_RATIO,
                           "min_range_adu": MIN_RANGE_ADU,
                           "basis": "unmeasured provisional"}}


# -- prepare: every check, then the work -----------------------------------------------------
def _prepare(op: str, env: SampleContext, args: dict, backend: Any) -> tuple[str, Work]:
    """(sample_id, work) for `op`, or Refused. Nothing is written before the work runs."""
    if op not in OPS:
        raise ValueError(f"unknown sample op {op!r}; known: {list(OPS)}")
    if op == SAMPLE_NEW:
        _only(args, set())
        _no_other_session(env, None)

        def new(io: _IO) -> dict:
            s = Sample.create(env.samples_root)  # reserves the id and folder; no event
            if io.set_current_sample:
                io.set_current_sample(s.id, True)
            io.emit("sample_opened", {"sample_id": s.id, "reserved": True})
            return {"sample_id": s.id, "dir": str(s.dir)}

        return "", new

    sid = _sample_id(args)
    if op == SAMPLE_OPEN:
        _only(args, {"sample_id"})
        _no_other_session(env, sid)
        if not _view(env, sid).exists:
            raise Refused(f"no sample {sid} (no legacy folder and no session)")

        def open_(io: _IO) -> dict:
            reserved = env.open_sample() is None
            if io.set_current_sample:
                io.set_current_sample(sid, reserved)
            io.emit("sample_opened", {"sample_id": sid, "reserved": reserved})
            return _view(env, sid).summary()

        return sid, open_

    session = _need_session(env, sid)
    if op == GEOMETRY_SET_OP:
        _only(args, {"sample_id", "values"})
        try:
            values = validate_geometry(args.get("values"))
        except GeometryError as exc:
            raise Refused(str(exc)) from None

        def geometry(io: _IO) -> dict:
            session.sample_event(GEOMETRY_SET, values=values)
            view = _view(env, sid)
            write_derived_views(view, env.samples_root)
            return {"sample_id": sid, "geometry": view.geometry, "loading": view.loading}

        return sid, geometry

    if op == CONFIRM_PERSON:
        _only(args, {"sample_id"})

        def person(io: _IO) -> dict:
            session.manual_step(CONFIRM_PERSON, sample_id=sid)
            session.sample_event(LOADING_STEP, step="person", ok=True)
            return {"sample_id": sid, "loading": _view(env, sid).loading}

        return sid, person

    if op == CHECK_IMAGE:
        _only(args, {"sample_id"})
        if backend is None:
            raise Refused("loading_check_image needs the microscope backend")
        try:
            key = registry_key(backend.nosepiece())
        except Exception as exc:  # noqa: BLE001 - unreadable objective: refuse, do not turn
            raise Refused(f"objective unreadable ({exc}); {CHECK_OBJECTIVE} must be in place"
                          ) from None
        if key != CHECK_OBJECTIVE:
            raise Refused(f"the {CHECK_OBJECTIVE} objective must be in place (reads {key}); "
                          "the image check does not change the objective")

        def image(io: _IO) -> dict:
            io.lamp_on()
            frame = io.backend.snap()
            result = structure_check(frame.image, io.backend.info().ceiling_adu)
            folder = Sample(sid, env.samples_root).dir / FRAMES_DIR
            folder.mkdir(parents=True, exist_ok=True)
            n = len(list(folder.glob("frame_*.npy"))) + 1
            name = f"frame_{n:04d}.npy"
            np.save(folder / name, np.asarray(frame.image))
            result["frame_ref"] = f"{FRAMES_DIR}/{name}"  # relative to the sample folder
            result["frame"] = frame.meta()
            session.sample_event(LOADING_STEP, step="image", ok=result["ok"],
                                 why=result["why"], result_ref=result["frame_ref"],
                                 metric=result["metric"], value=result["value"],
                                 grade="computed")
            result["loading"] = _view(env, sid).loading
            return result

        return sid, image

    if op in (BOUNDARY_MARK, BOUNDARY_UNDO_OP, BOUNDARY_RESET):
        _only(args, {"sample_id", "x_um", "y_um"} if op == BOUNDARY_MARK else {"sample_id"})
        if op == BOUNDARY_MARK:
            try:
                x, y = plain(args.get("x_um"), "x_um"), plain(args.get("y_um"), "y_um")
            except (GuardError, TypeError, ValueError) as exc:
                raise Refused(f"boundary point: {exc}") from None
        elif op == BOUNDARY_UNDO_OP and not _view(env, sid).boundary:
            raise Refused("no boundary point to undo")

        def boundary(io: _IO) -> dict:
            if op == BOUNDARY_MARK:
                session.sample_event("boundary_point", x_um=x, y_um=y)
            elif op == BOUNDARY_UNDO_OP:
                session.sample_event(BOUNDARY_UNDO)
            else:
                session.sample_event("boundary_clear")
            view = _view(env, sid)
            write_derived_views(view, env.samples_root, with_map=True)
            pts = [[p["x_um"], p["y_um"]] for p in view.boundary]
            io.emit("map_changed", {"sample_id": sid, "what": "boundary", "n_points": len(pts)})
            return {"sample_id": sid, "n_points": len(pts), "boundary": pts}

        return sid, boundary

    raise AssertionError(f"{op} is in OPS but has no branch")  # pragma: no cover


# -- the T-002 lifecycle (before / without the runner) ---------------------------------------
def run_sample_op(op: str, env: SampleContext, args: dict | None = None,
                  sink: EventSink = null_sink, backend: Backend | None = None) -> dict:
    """Run one sample op. Returns {status, op_id, summary, record} ("finished"), or
    {status: "refused", why} after a preflight_failed event (nothing written)."""
    args = dict(args or {})
    try:
        sid, work = _prepare(op, env, args, backend)
    except Refused as exc:
        why = str(exc)
        sink(Event("preflight_failed", "", {"op": op, "why": why, "args": args}))
        return {"status": "refused", "why": why}
    if op == CHECK_IMAGE:
        with operation(backend, Sample(sid, env.samples_root).dir, op, sink, args=args,
                       user_id=env.user_id, session_id=env.session_id) as scope:
            io = _IO(lambda k, d: scope.emit(Event(k, scope.op_id, d)), backend, scope.lamp_on)
            scope.result = work(io)
        return {"status": "finished", "op_id": scope.op_id, "summary": scope.result,
                "record": str(scope.record.dir)}
    return _record_only(env, op, sid, args, sink, work)


def _record_only(env: SampleContext, op: str, sid: str, args: dict, sink: EventSink,
                 work: Work) -> dict:
    parent = Sample(sid, env.samples_root).dir if sid else env.samples_root / "_reserved"
    rec = OpRecord(parent, op, user_id=env.user_id, session_id=env.session_id)
    emit = fan_out(rec.sink, sink)
    emit(Event("started", rec.op_id, {"op": op, "args": dict(args), "user_id": env.user_id,
                                      "session_id": env.session_id}))
    status, error, summary = "error", None, None
    try:
        summary = work(_IO(lambda k, d: emit(Event(k, rec.op_id, d))))
        status = "finished"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        emit(Event("error", rec.op_id, {"error": error}))
        raise
    finally:
        if status == "finished":
            emit(Event("finished", rec.op_id, {"op": op, "error": None, "summary": summary}))
        rec.finish(status, lights=NO_LIGHT, result=summary, error=error)
    return {"status": status, "op_id": rec.op_id, "summary": summary, "record": str(rec.dir)}


# -- the T-011 runner ------------------------------------------------------------------------
@dataclass
class SampleSeat:
    """Installed on the runner by the server: the records store, the legacy root, and the
    open ExperimentSession object for a session id (the server holds it)."""

    store: Any
    samples_root: Path = SAMPLES_ROOT
    session_for: Callable[[str], Any] = lambda session_id: None


def install_sample_seat(runner: Any, seat: SampleSeat) -> None:
    runner.sample_seat = seat


class _SampleOperation(Operation):
    exclusive = False  # record-only: runs beside a hardware op (T-011)
    motion = False

    def _env(self) -> SampleContext:
        seat = getattr(self.ctx.runner, "sample_seat", None)
        if seat is None:
            raise Refused("the sample store is not installed on the engine")
        sid = self.ctx.session_id
        session = seat.session_for(sid) if sid else None
        return SampleContext(seat.store, Path(seat.samples_root), session, self.ctx.user_id)

    def preflight(self) -> list[dict]:
        try:
            self._prepared = _prepare(self.name, self._env(), dict(self.args), self.ctx.backend)
        except Refused as exc:
            return [{"name": "sample", "ok": False, "want": self.name, "read": None,
                     "why": str(exc)}]
        return [{"name": "sample", "ok": True, "want": self.name, "read": None, "why": ""}]

    def run(self) -> dict:
        ctx = self.ctx

        def emit_event(ev: Event) -> None:
            ctx.emit(ev.kind, **ev.data)

        io = _IO(lambda k, d: ctx.emit(k, **d), ctx.backend,
                 lambda: guards.lamp_on(ctx.backend, emit_event, ctx.op_id),
                 lambda sid, reserved: ctx.set_current_sample(sid, reserved=reserved))
        return self._prepared[1](io)


def _register(op: str, **flags: Any) -> type[Operation]:
    cls = type(f"SampleOp_{op}", (_SampleOperation,), {"name": op, **flags})
    return register_operation(cls)


for _op in (SAMPLE_OPEN, SAMPLE_NEW, GEOMETRY_SET_OP, CONFIRM_PERSON, BOUNDARY_MARK,
            BOUNDARY_UNDO_OP, BOUNDARY_RESET):
    _register(_op)
# the image check holds the core and pauses the stream; the runner switches the lamp off
_register(CHECK_IMAGE, exclusive=True, snaps=True)
