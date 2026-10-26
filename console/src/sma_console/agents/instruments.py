"""What the Instruments screens read from the runtime's files (console card 012; plan.md 15, 15.1).

Reads only. The console writes nothing here, builds **no stand-in** for a runtime piece that is not
built, and sends no command to any instrument:

* the idle status file the runtime writes, `microscope_runtime/.runtime_status/idle_status.json`, as data,
  validated against `contracts/schemas/idle_status.schema.json` read from the tree. Absent, it is "no
  status yet", which is not "nothing connected". Nothing is carried forward from an older file;
* the person's limits, `microscope_runtime/envelope/safety.json`, for the piezo range and the tweezers
  ranges. A range is **read from the file and never written into code**; a limit the file does not hold is
  shown as missing;
* the latest run's events (`log.json`): the tweezers commands that were sent, and the piezo's snapshots.
  Each is "sent" or "read back", as the event says, and from that run alone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .schema_lite import SchemaError, Schemas

IDLE_PARTS = ("microscope_runtime", ".runtime_status", "idle_status.json")
SAFETY_PARTS = ("microscope_runtime", "envelope", "safety.json")
OBJECTIVES = ("40x", "60x", "100x")
AXES = ("x", "y", "z")


@dataclass
class IdleRead:
    state: str  # "none" | "present" | "invalid" | "unreadable"
    data: dict[str, Any] | None = None
    problems: list[str] = field(default_factory=list)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_idle_status(root: Path | None) -> IdleRead:
    """The idle status file, if it is there and is what its schema says. Data that fails its schema
    is not shown as a status: the screen says it cannot be read, and why."""
    if root is None:
        return IdleRead("none")
    path = root.joinpath(*IDLE_PARTS)
    if not path.is_file():
        return IdleRead("none")
    try:
        data = _json(path)
    except (OSError, ValueError) as e:
        return IdleRead("unreadable", problems=[f"the file cannot be read: {e}"])
    try:
        problems = Schemas(root / "contracts" / "schemas").validate(data, "idle_status.schema.json")
    except SchemaError as e:
        return IdleRead("invalid", problems=[f"it cannot be checked against its schema: {e}"])
    if problems:
        return IdleRead("invalid", problems=problems[:8])
    return IdleRead("present", data=data)


@dataclass
class LimitsRead:
    state: str  # "none" | "present" | "unreadable" | "invalid"
    policy_version: str | None = None
    written_by: str | None = None
    written_at: str | None = None
    limits: dict[str, dict[str, Any]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def read_limits(root: Path | None) -> LimitsRead:
    """The person's safety file: every limit by name, with its value, unit and bounds. Checked against
    envelope_safety.schema.json when the tree holds it."""
    if root is None:
        return LimitsRead("none")
    path = root.joinpath(*SAFETY_PARTS)
    if not path.is_file():
        return LimitsRead("none")
    try:
        data = _json(path)
    except (OSError, ValueError) as e:
        return LimitsRead("unreadable", problems=[f"the file cannot be read: {e}"])
    schemas = root / "contracts" / "schemas"
    if (schemas / "envelope_safety.schema.json").is_file():
        try:
            problems = Schemas(schemas).validate(data, "envelope_safety.schema.json")
        except SchemaError as e:
            return LimitsRead("invalid", problems=[f"it cannot be checked against its schema: {e}"])
        if problems:
            return LimitsRead("invalid", problems=problems[:8])
    limits: dict[str, dict[str, Any]] = {}
    for target in data.get("targets", []) if isinstance(data, dict) else []:
        for name, spec in (target.get("limits") or {}).items():
            if isinstance(spec, dict) and name not in limits:
                limits[name] = spec
    return LimitsRead(
        "present", policy_version=str(data.get("policy_version")) if isinstance(data, dict) else None,
        written_by=data.get("written_by") if isinstance(data, dict) else None,
        written_at=data.get("written_at") if isinstance(data, dict) else None, limits=limits)


def _bound(limits: dict[str, dict[str, Any]], name: str) -> dict[str, Any] | None:
    spec = limits.get(name)
    if not isinstance(spec, dict) or not isinstance(spec.get("value"), (int, float)) or isinstance(spec.get("value"), bool):
        return None
    return {"value": spec["value"], "unit": spec.get("unit")}


def piezo_range(limits: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    """`{axis: {min, max}}` for x, y, z; an axis whose limit the file does not hold has None."""
    out: dict[str, dict[str, Any] | None] = {}
    for a in AXES:
        lo, hi = _bound(limits, f"piezo_{a}_position_min"), _bound(limits, f"piezo_{a}_position_max")
        out[a] = {"min": lo, "max": hi} if lo is not None and hi is not None else None
    return out


def tweezers_ranges(limits: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The tweezers limits the file holds: a position range per objective, the step ceiling and the strength range."""
    positions: dict[str, dict[str, Any] | None] = {}
    for o in OBJECTIVES:
        lo, hi = _bound(limits, f"tweezers_trap_position_{o}_min"), _bound(limits, f"tweezers_trap_position_{o}_max")
        positions[o] = {"min": lo, "max": hi} if lo is not None and hi is not None else None
    s_lo, s_hi = _bound(limits, "tweezers_trap_strength_min"), _bound(limits, "tweezers_trap_strength_max")
    return {"positions": positions, "step_max": _bound(limits, "tweezers_trap_step_max"),
            "strength": {"min": s_lo, "max": s_hi} if s_lo is not None and s_hi is not None else None}


# -- the latest run's events -------------------------------------------------------------------------


def _events(detail: Any) -> tuple[list[dict[str, Any]], str | None]:
    log = detail.records.get("log.json") if isinstance(getattr(detail, "records", None), dict) else None
    if not isinstance(log, dict):
        return [], None
    events = [e for e in log.get("events", []) if isinstance(e, dict)]
    t0 = log.get("t0_wall")
    return events, t0 if isinstance(t0, str) else None


def _wall(t0: str | None, t_mono: Any) -> str | None:
    if t0 is None or not isinstance(t_mono, (int, float)) or isinstance(t_mono, bool):
        return None
    try:
        base = datetime.fromisoformat(t0.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (base + timedelta(seconds=float(t_mono))).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def tweezers_sent(events: list[dict[str, Any]]) -> dict[str, Any]:
    """What the run sent to the tweezers, from its `apply` events on the optical_tweezers channel: the traps
    (last position and strength sent, and whether it was last sent on or off), every position as a series in
    run time, and the strength last sent. The tweezers report nothing back, so all of it is "sent"."""
    traps: dict[str, dict[str, Any]] = {}
    series: list[dict[str, Any]] = []
    strength_last: float | None = None
    for e in events:
        if e.get("event") != "apply" or e.get("channel") != "optical_tweezers":
            continue
        params = e.get("params") if isinstance(e.get("params"), dict) else {}
        for cmd in params.get("commands", []):
            if not isinstance(cmd, list) or len(cmd) < 2:
                continue
            verb, name = str(cmd[0]), str(cmd[1])
            trap = traps.setdefault(name, {"trap": name, "x_um": None, "y_um": None, "strength": None, "on": None})
            if verb == "TRAP_POSITION" and len(cmd) >= 4:
                trap["x_um"], trap["y_um"] = _num(cmd[2]), _num(cmd[3])
                series.append({"t_s": _num(e.get("t_mono")), "trap": name, "x_um": trap["x_um"], "y_um": trap["y_um"]})
            elif verb == "TRAP_STRENGTH" and len(cmd) >= 3:
                trap["strength"] = _num(cmd[2])
                strength_last = trap["strength"]
            elif verb == "TRAP_ON":
                trap["on"] = True
            elif verb == "TRAP_OFF":
                trap["on"] = False
    return {"traps": list(traps.values()), "series": series, "strength_last_sent": strength_last}


def piezo_snapshots(events: list[dict[str, Any]], t0: str | None) -> list[dict[str, Any]]:
    """The piezo stage's read-back positions, one per snapshot event of the run that carries one, with
    run time and wall time. A snapshot that holds no reading of the piezo (an error, not opened) is skipped."""
    out: list[dict[str, Any]] = []
    for e in events:
        if e.get("event") != "snapshot":
            continue
        states = e.get("states") if isinstance(e.get("states"), dict) else {}
        piezo = states.get("piezo_stage") if isinstance(states.get("piezo_stage"), dict) else {}
        pos = piezo.get("position_um") if isinstance(piezo.get("position_um"), dict) else None
        if pos is None:
            continue
        x, y, z = _num(pos.get("x")), _num(pos.get("y")), _num(pos.get("z"))
        if x is None and y is None and z is None:
            continue
        out.append({"t_s": _num(e.get("t_mono")), "t_wall": _wall(t0, e.get("t_mono")), "x_um": x, "y_um": y, "z_um": z,
                    "label": e.get("label") if isinstance(e.get("label"), str) else None})
    return out


def latest_run_readings(store: Any) -> dict[str, Any]:
    """The newest microscope run and what its events say about the tweezers and the piezo stage. The
    runs folder not being there is its own answer, not an empty one."""
    from .store import RunsFolderNotFoundError  # local: keeps this module importable without the store

    try:
        runs = store.list_runs("microscope")
    except RunsFolderNotFoundError as e:
        return {"state": "runs_not_found", "message": str(e)}
    if not runs:
        return {"state": "no_run"}
    # the screens follow the newest run that is still running; with none running, the newest run there is
    latest = next((r for r in runs if r.status == "running"), runs[0])
    stream = _followed_stream(store, latest.run_id)
    if stream is not None:
        events, t0 = [e for e in stream.events if isinstance(e, dict)], stream.t0_wall
        running, how, plan_id = stream.running, stream.ended_how, stream.plan_id
        ended_at = _wall(t0, stream.ended.get("t_mono")) if stream.ended is not None else None
        frame_tap = stream.running and stream.frame_tap is not None
    else:
        detail = store.get_run("microscope", latest.run_id)
        events, t0 = _events(detail)
        running, how, plan_id, ended_at, frame_tap = False, latest.status, latest.plan_id, latest.finished_at, False
    tw = tweezers_sent(events)
    return {"state": "ok", "run_id": latest.run_id, "started_at": latest.created_at or t0, "traps": tw["traps"],
            "trap_series": tw["series"], "strength_last_sent": tw["strength_last_sent"],
            "piezo": piezo_snapshots(events, t0), "running": running, "ended_how": how, "ended_at": ended_at,
            "plan_id": plan_id, "frame_tap": frame_tap, "channels": channel_states(events, t0),
            "path": path_state(events, t0),
            "events_seen": len(events)}


def _followed_stream(store: Any, run_id: str) -> Any:
    """The run's events.jsonl as written so far, or None when the run was not followed (it then has its
    `log.json` only, which is a finished run's record)."""
    from .sma_run import NotFollowedError, SmaRunError
    from .store import NotFoundError

    reader = getattr(store, "run_stream", None)
    if reader is None:
        return None
    try:
        return reader("microscope", run_id)
    except (NotFollowedError, SmaRunError, NotFoundError):
        return None


def channel_states(events: list[dict[str, Any]], t0: str | None) -> dict[str, Any]:
    """What the run's last snapshot says about each channel it tried to open: opened (with the backend the
    reading came from) or not opened (with the reason it gives). This is the connection state, read from the
    run's own events; nothing is asked of any instrument. `None` when the run took no snapshot."""
    last: dict[str, Any] | None = None
    for e in events:
        if e.get("event") == "snapshot" and isinstance(e.get("states"), dict):
            last = e
    if last is None:
        return {"t_s": None, "t_wall": None, "label": None, "rows": []}
    rows: list[dict[str, Any]] = []
    for channel, state in last["states"].items():
        st = state if isinstance(state, dict) else {}
        err = st.get("error")
        backend = st.get("backend")
        rows.append({"channel": str(channel), "opened": err is None,
                     "detail": str(err) if err is not None else None,
                     "backend": backend if isinstance(backend, str) else None})
    return {"t_s": _num(last.get("t_mono")), "t_wall": _wall(t0, last.get("t_mono")),
            "label": last.get("label") if isinstance(last.get("label"), str) else None, "rows": rows}


def path_state(events: list[dict[str, Any]], t0: str | None) -> list[dict[str, Any]]:
    """The optical path's present state as the run read it back: for each Micro-Manager device a channel's
    snapshot reports (`states[<channel>]["state"][<device>]`, the shape `micromanager.read` gives), the
    properties it read, when, and which backend answered (`mock` is the mock's own state, labelled as
    such by the screen). A device keeps the latest snapshot that reported it; one no snapshot reported is
    absent, and the screen says "not built yet" for it. Nothing here is filled from anywhere else."""
    latest: dict[str, dict[str, Any]] = {}
    for e in events:
        if e.get("event") != "snapshot" or not isinstance(e.get("states"), dict):
            continue
        for channel_state in e["states"].values():
            devices = channel_state.get("state") if isinstance(channel_state, dict) else None
            if not isinstance(devices, dict):
                continue
            backend = channel_state.get("backend")
            for device, props in devices.items():
                if isinstance(props, dict):
                    latest[str(device)] = {
                        "device": str(device), "props": {str(k): "" if v is None else str(v) for k, v in props.items()},
                        "t_s": _num(e.get("t_mono")), "t_wall": _wall(t0, e.get("t_mono")),
                        "backend": backend if isinstance(backend, str) else None}
    return list(latest.values())
