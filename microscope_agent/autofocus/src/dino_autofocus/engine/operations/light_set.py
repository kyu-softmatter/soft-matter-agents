"""`light_set{mode, line, percent}`: switch the light by meaning, nothing moves (ui-spec 4.3, D15).

Modes (ui-spec 7.2 "Brightfield on" / "Aura <line> <pct> % on"):

- `brightfield`: Aura off, DiaLamp on (`lamp_on`).
- `aura`: DiaLamp off, the Aura line at `percent` % (per-mille inside the backend), master on.
- `off`: everything off (`all_off`). The pre-emptive stop is the runner's `lights_off` command
  kind; this mode is the same switch-off asked for as a setting.

Allow-list: the four Aura lines and the DiaLamp, through the backend's meaning-level methods
only, never `set_property`. Every switch is read back; a readback that does not verify switches
everything off again and the operation ends in `error`. On success the light stays as set
(the runner's `keep_lights_on_finish`); every other exit path switches off.

Who may run it (D15: M3, operator with the control grant, open session) is the runner's
permission table (`light_set` is a light action there), not this module. `LightSetOp` is the
runner's `light_set` (`keep_lights_on_finish`); `run_light_set` is the same switch on the
T-002 record lifecycle for callers without a runner.

Light-on takes the control token (T-015), which only `engine.guards` may hold, so `switch`
goes through the operation scope's helpers `OpScope.lamp_on()` / `OpScope.aura_line_on()`
(T-002-4). They record the readback (`light_changed`) and raise GuardError when it does not
verify. Switching off needs no token.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path

from ..backend import AURA_LINES, Backend, Readback
from ..events import Event, EventSink, fan_out, null_sink
from ..guards import GuardError, OpScope, lights_off, snapshot
from ..records import OpRecord
from ..runner import OpContext, Operation, register_operation

NAME = "light_set"
MODES = ("brightfield", "aura", "off")
MAX_PERCENT = 100.0


@dataclass(frozen=True)
class LightRequest:
    mode: str
    line: str | None = None
    percent: float | None = None

    def describe(self) -> str:
        if self.mode == "brightfield":
            return "Aura off, DiaLamp on. Nothing moves."
        if self.mode == "aura":
            return f"DiaLamp off, Aura {self.line} at {self.percent:g} %. Nothing moves."
        return "Aura off, DiaLamp off. Nothing moves."


def parse(args: dict) -> LightRequest:
    """Check `args` against the allow-list; ValueError says what is wrong."""
    extra = sorted(set(args) - {"mode", "line", "percent"})
    if extra:
        raise ValueError(f"unknown light_set arguments: {extra}")
    mode = args.get("mode")
    if mode not in MODES:
        raise ValueError(f"mode {mode!r} is not one of {MODES}")
    if mode != "aura":
        if args.get("line") is not None or args.get("percent") is not None:
            raise ValueError(f"mode {mode!r} takes no line or percent")
        return LightRequest(mode)
    line = str(args.get("line") or "").upper()
    if line not in AURA_LINES:
        raise ValueError(f"Aura line {args.get('line')!r} is not one of {AURA_LINES}")
    try:
        pct = float(args.get("percent"))
    except (TypeError, ValueError):
        raise ValueError(f"percent {args.get('percent')!r} is not a number") from None
    if not math.isfinite(pct) or not 0 < pct <= MAX_PERCENT:
        raise ValueError(f"percent {pct} must be in (0, {MAX_PERCENT:g}]")
    return LightRequest("aura", line, pct)


def plan(args: dict) -> dict:
    req = parse(args)
    return {"op": NAME, "text": req.describe(), "request": asdict(req)}


def switch(backend: Backend, scope: OpScope, req: LightRequest) -> list[Readback]:
    """The one place lights are switched by meaning: on through the scope's guarded helpers
    (they carry the token), off through the backend (a stop needs no token). Every readback is
    recorded on the scope; one that does not verify raises GuardError."""
    if req.mode == "brightfield":
        return scope.lamp_on()
    if req.mode == "aura":
        return scope.aura_line_on(req.line, req.percent)
    rbs = backend.all_off()
    if not rbs:
        raise GuardError("light not verified: the backend returned no readback")
    return scope.lights(rbs)


def run_light_set(backend: Backend, parent: Path, args: dict, sink: EventSink = null_sink, *,
                  user_id: str | None = None, session_id: str | None = None) -> dict:
    """Switch, read back, record `<parent>/light_set_<stamp>/`. Returns the result dict.

    Raises ValueError before anything is switched if `args` fail the allow-list."""
    req = parse(args)
    rec = OpRecord(parent, NAME, start_state=snapshot(backend), user_id=user_id,
                   session_id=session_id)
    emit = fan_out(rec.sink, sink)
    # a scope without operation(): its exit path would switch the light straight off again
    scope = OpScope(rec.op_id, rec, emit, backend=backend)
    emit(Event("started", rec.op_id, {"op": NAME, "args": dict(args), "user_id": user_id,
                                      "session_id": session_id}))
    status, error, result, lights = "error", None, None, None
    try:
        rbs = switch(backend, scope, req)
        status = "finished"
        result = {"mode": req.mode, "line": req.line, "percent": req.percent,
                  "readbacks": [asdict(r) for r in rbs], "verified": True}
    except GuardError as exc:  # a readback that did not verify: an error result, no raise
        error = str(exc)
        emit(Event("error", rec.op_id, {"error": error}))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        emit(Event("error", rec.op_id, {"error": error}))
        raise
    finally:
        if status == "finished":
            lights = {"switched_off": False, "why": "light_set leaves the light as set",
                      "state": backend.light_state(), "verified": None}
        else:
            lights = {"switched_off": True, **lights_off(backend)}
        emit(Event("light_changed", rec.op_id, lights))
        if status == "finished":
            emit(Event("finished", rec.op_id, {"error": None}))
        rec.finish(status, lights=lights, end_state=snapshot(backend), result=result,
                   error=error)
    return {"status": status, "error": error, "result": result, "record": str(rec.dir)}


def scope_for(ctx: OpContext) -> OpScope:
    """An OpScope over a runner context, so an operation can use the guards' light helpers
    (they carry the token). Its events go out through the context; the record and the exit
    path stay the runner's."""
    return OpScope(ctx.op_id, None, lambda ev: ctx.emit(ev.kind, **ev.data),
                   backend=ctx.backend)


@register_operation
class LightSetOp(Operation):
    """`start("light_set", {mode, line, percent})`. An unverified readback raises GuardError:
    the runner ends the operation in error and switches everything off."""

    name = NAME
    motion = False
    keep_lights_on_finish = True

    def plan(self) -> dict:
        try:
            return plan(self.args)
        except ValueError as exc:  # preflight reports it as a failed check
            return {"op": NAME, "text": f"not allowed: {exc}", "request": None}

    def preflight(self) -> list[dict]:
        try:
            req = parse(self.args)
        except ValueError as exc:
            return [{"name": "args", "ok": False, "want": "allow-listed light",
                     "read": dict(self.args), "why": str(exc)}]
        return [{"name": "args", "ok": True, "want": "allow-listed light", "read": asdict(req),
                 "why": ""}]

    def run(self) -> dict:
        req = parse(self.args)
        rbs = switch(self.ctx.backend, scope_for(self.ctx), req)
        return {"mode": req.mode, "line": req.line, "percent": req.percent,
                "readbacks": [asdict(r) for r in rbs], "verified": True}
