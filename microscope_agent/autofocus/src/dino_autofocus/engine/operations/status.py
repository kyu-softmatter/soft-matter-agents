"""`status`: read the microscope's state, change nothing (operations-spec 2, launcher Step 0).

Reads the backend info, positions, objective, PFS and lights. A read that fails becomes an
`"unreadable: ..."` string in its field, so one missing device never hides the rest.

Periodic status comes from the runner's `position` events, not from this operation. A record
folder `status_<stamp>/` is written only when the user asked for the status (`keep_record`),
so a status bar refresh never creates folders.

Nothing is switched: the lights stay as they are (a `light_set` before it keeps its light).
`StatusOp` is the runner's `status` (registered with T-011); `run_status` drives the T-002
record lifecycle directly for callers without a runner. Under the runner a finished status
keeps every light as it was (the runner's `restore` exit rule).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..backend import Backend
from ..events import Event, EventSink, fan_out, null_sink
from ..guards import snapshot
from ..records import OpRecord
from ..runner import Operation, register_operation

NAME = "status"


def _read(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a failed read is a field, not a stop
        return f"unreadable: {type(exc).__name__}: {exc}"


def _nosepiece_state(backend: Backend, label: Any) -> Any:
    """The nosepiece position (0-based) whose label matches; labels start at 1."""
    if not isinstance(label, str):
        return label
    for o in backend.info().objectives:
        if o.label == label:
            return o.state
    return f"unreadable: no objective labelled {label!r} in the backend info"


def read_status(backend: Backend) -> dict:
    """Every field of operations-spec 2 run table, rows 1-7. JSON-native."""
    info = _read(backend.info)
    pos = _read(backend.positions)
    label = _read(backend.nosepiece)
    pfs = _read(backend.pfs)
    out: dict[str, Any] = {
        "info": info.to_dict() if hasattr(info, "to_dict") else info,
        "positions": asdict(pos) if hasattr(pos, "errors") else pos,
        "nosepiece_label": label,
        "nosepiece_state": _read(lambda: _nosepiece_state(backend, label)),
        "lights": _read(backend.light_state),
    }
    if hasattr(pos, "errors"):
        out["z_um"] = None if pos.z_um is None else round(pos.z_um, 3)
    else:
        out["z_um"] = pos
    if hasattr(pfs, "enabled"):
        out.update(pfs_enabled=pfs.enabled, pfs_locked=pfs.locked, pfs_in_range=pfs.in_range)
    else:
        out.update(pfs_enabled=pfs, pfs_locked=pfs, pfs_in_range=pfs)
    if hasattr(info, "ceiling_adu"):
        out["bit_depth"], out["ceiling_adu"] = info.bit_depth, info.ceiling_adu
    return out


def run_status(backend: Backend, parent: Path | None = None, sink: EventSink = null_sink, *,
               keep_record: bool = False, user_id: str | None = None,
               session_id: str | None = None) -> dict:
    """Read the status and emit one `reading` event (`source: "status"`).

    With `keep_record` (the user pressed "Show objective / Z / PFS") the reading also lands in
    `<parent>/status_<stamp>/` with log.jsonl and summary.json. The summary's lights entry says
    the lights were left as they were, with the state read at the end."""
    if not keep_record:
        st = read_status(backend)
        sink(Event("reading", "", {"op": NAME, "source": "status", "value": st}))
        return st
    if parent is None:
        raise ValueError("keep_record needs a parent folder for the record")
    rec = OpRecord(parent, NAME, start_state=snapshot(backend), user_id=user_id,
                   session_id=session_id)
    emit = fan_out(rec.sink, sink)
    emit(Event("started", rec.op_id, {"op": NAME, "args": {}, "user_id": user_id,
                                      "session_id": session_id}))
    status, error, st = "finished", None, None
    try:
        st = read_status(backend)
        emit(Event("reading", rec.op_id, {"op": NAME, "source": "status", "value": st}))
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"
        emit(Event("error", rec.op_id, {"error": error}))
        raise
    finally:
        lights = {"switched_off": False, "why": "status is read-only; lights left as they were",
                  "state": _read(backend.light_state), "verified": None}
        if status == "finished":
            emit(Event("finished", rec.op_id, {"error": None}))
        rec.finish(status, lights=lights, end_state=snapshot(backend), result=st, error=error)
    return st


@register_operation
class StatusOp(Operation):
    """`start("status")`: one `reading` event; the summary carries the same fields."""

    name = NAME
    motion = False

    def plan(self) -> dict:
        return {"op": NAME, "text": "Read objective, Z, PFS and lights. Nothing moves."}

    def run(self) -> dict:
        st = read_status(self.ctx.backend)
        self.ctx.emit("reading", op=NAME, source="status", value=st)
        return {"status": st}
