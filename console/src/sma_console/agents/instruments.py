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
  Each is "sent" or "read back", as the event says, and from that run alone;
* the optical path (card 017): the elements the run's latest snapshot read back, each in exactly one of four
  states -- read back, sent, not open, not read -- or, outside a run, the same from the status file.
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
ORDER_KEY = "light_path_order"
ORDER_REF = "#/$defs/light_path_order"
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
        # an order the shape refuses does not make the rest of the file unreadable: the readings are still
        # the file's, and the order is shown as not understood (card 023). Anything else wrong is the file's.
        if isinstance(data, dict) and ORDER_KEY in data:
            rest = {k: v for k, v in data.items() if k != ORDER_KEY}
            try:
                if not Schemas(root / "contracts" / "schemas").validate(rest, "idle_status.schema.json"):
                    return IdleRead("present", data=data)
            except SchemaError:
                pass
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
    """`_latest_run_readings`, with the sample's example drawing beside the order when there is one to give (console card
    025): only the sample store has `example_path`, and only an order whose state is `none` leaves room for it. The
    example is never inside the order and never passes through `order_state`."""
    got = _latest_run_readings(store)
    path = got.get("path")
    if isinstance(path, dict):
        order = path.get("order")
        fn = getattr(store, "example_path", None)
        path["example"] = fn() if fn is not None and isinstance(order, dict) and order.get("state") == "none" else None
    return got


def _latest_run_readings(store: Any) -> dict[str, Any]:
    """The newest microscope run and what its events say about the tweezers and the piezo stage. The
    runs folder not being there is its own answer, not an empty one."""
    from .store import RunsFolderNotFoundError  # local: keeps this module importable without the store

    try:
        runs = store.list_runs("microscope")
    except RunsFolderNotFoundError as e:
        return {"state": "runs_not_found", "message": str(e), "path": _status_path(store) or NONE_PATH}
    if not runs:
        return {"state": "no_run", "path": _status_path(store) or NONE_PATH}
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
    from_status = None if running else _status_path(store)  # outside a run the runtime's own status file is read first
    path = from_status or {"source": "run" if running else "last_snapshot", "run_id": latest.run_id, "ended_at": ended_at,
                           "ended_how": None if running else how, **path_from_events(events, t0),
                           "order": _order_in_events(store, events)}
    return {"state": "ok", "run_id": latest.run_id, "started_at": latest.created_at or t0, "traps": tw["traps"],
            "trap_series": tw["series"], "strength_last_sent": tw["strength_last_sent"],
            "piezo": piezo_snapshots(events, t0), "running": running, "ended_how": how, "ended_at": ended_at,
            "plan_id": plan_id, "frame_tap": frame_tap, "channels": channel_states(events, t0),
            "path": path,
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


LASER = "laser_combiner"
#: The elements no draft is offered for yet (console card 024), each with the words the person is shown. A run cannot take
#: either: a plan will name the light engine by its model, which nothing the console may read gives; and the lamp's
#: brightness has no recorded quantity and its on and off states no table.
NO_DRAFT = {
    "Aura": ("No draft is offered for the Aura yet. A plan will name the light engine by its model, and the console has "
             "nowhere to read that model from yet, so it guesses none."),
    "DiaLamp": ("No draft is offered for the transmitted lamp yet. The run has no recorded quantity for its brightness, and "
                "no table of its on and off states."),
}
ASSUMED_ON = "assumed on"
LASER_REASON = ("It reports nothing back, so it is shown at the most dangerous state its commands allow -- on -- "
                "until something readable shows the beam blocked. What was sent never shows it off.")
NO_POSITION = "the read returned no position for it"
NO_STATUS_SNAPSHOT = "That run took no snapshot (a live view takes none), so no element was read."
NO_ORDER: dict[str, Any] = {"state": "none", "data": None, "problems": []}
NONE_PATH: dict[str, Any] = {"source": "none", "elements": [], "order": NO_ORDER}


def order_state(store: Any, present: bool, raw: Any) -> dict[str, Any]:
    """The light-path order a source gave, judged by the schema's own definition of it (`light_path_order` in
    idle_status.schema.json): `{state, data, problems}` with state `none` (the source has no such key),
    `read`, `not_in_snapshot` (the file says why it has none), or `not_understood` (the shape refuses it, and
    nothing of it is given). A source that is not understood is never drawn in part."""
    if not present:
        return {"state": "none", "data": None, "problems": []}
    fn = getattr(store, "runtime_root", None)
    root = fn() if fn is not None else None
    if root is None:
        from .sma_files import repository_root  # local: the mock store reads the repository's own schemas

        root = repository_root()
    try:
        problems = Schemas(Path(root) / "contracts" / "schemas").validate_def(raw, "idle_status.schema.json", ORDER_REF)
    except (SchemaError, OSError, ValueError) as e:
        return {"state": "not_understood", "data": None, "problems": [f"it cannot be checked against its schema: {e}"]}
    if problems:
        return {"state": "not_understood", "data": None, "problems": problems[:8]}
    return {"state": raw["status"], "data": raw, "problems": []}


def _text(v: Any) -> str | None:
    if v is None:
        return None
    return v if isinstance(v, str) else json.dumps(v, sort_keys=True)


def _row(name: str, channel: str, state: str, *, value: Any = None, t_wall: str | None = None, reason: str | None = None,
         backend: str | None = None, sent: str | None = None, sent_at: str | None = None) -> dict[str, Any]:
    """One element of the path. Exactly one state; a laser has no control; every light-path selector and the
    objective is moved by hand; the Aura and the transmitted lamp are not drafted, and say why in `words`."""
    words = None
    if channel == LASER:
        control, draft = None, None
    elif name in NO_DRAFT:
        control, draft, words = "no_draft", None, NO_DRAFT[name]
    else:
        control, draft = "hand", None
    return {"key": f"{channel}/{name}", "name": name, "channel": channel, "state": state, "value": _text(value),
            "t_wall": t_wall, "reason": reason, "backend": backend, "sent": sent, "sent_at": sent_at,
            "control": control, "draft": draft, "words": words}


def _elements_of(state: Any) -> dict[str, Any] | None:
    els = state.get("elements") if isinstance(state, dict) else None
    return els if isinstance(els, dict) else None


def _last_apply(events: list[dict[str, Any]], channel: str, after: float | None, t0: str | None) -> tuple[str, str | None] | None:
    """The newest `apply` on `channel` (and, when `after` is given, only one strictly later than that run time):
    its parameters as compact text, and when. Equal times are not later."""
    found = None
    for e in events:
        if e.get("event") != "apply" or e.get("channel") != channel:
            continue
        t = _num(e.get("t_mono"))
        if after is not None and (t is None or t <= after):
            continue
        found = e
    if found is None:
        return None
    params = found.get("params") if isinstance(found.get("params"), dict) else {}
    return json.dumps(params, sort_keys=True), _wall(t0, found.get("t_mono"))


def _channel_rows(channel: str, ids: list[str], state: Any, wall: str | None, later: tuple[str, str | None] | None) -> list[dict[str, Any]]:
    """The rows one channel gives for a snapshot: what it read back, or why it has nothing to show."""
    if not isinstance(state, dict):
        return [_row(i, channel, "not_open", reason="the run's last read did not include this channel") for i in ids]
    if state.get("error") is not None:
        return [_row(i, channel, "not_open", reason=str(state["error"])) for i in ids]
    if state.get("not_read"):
        return [_row(i, channel, "not_read", reason=str(state.get("why") or "it was busy at the read")) for i in ids]
    els = _elements_of(state)
    if els is None:
        return [_row(i, channel, "not_read", reason="the last read carried no elements for this channel") for i in ids]
    backend = state.get("backend") if isinstance(state.get("backend"), str) else None
    note = state.get("note") if isinstance(state.get("note"), str) and state.get("note") else None
    rows = []
    for i, v in els.items():
        if v is None:
            rows.append(_row(str(i), channel, "not_read", reason=NO_POSITION + (f"; {note}" if note else ""), backend=backend))
        elif later is not None:
            rows.append(_row(str(i), channel, "sent", value=v, t_wall=wall, backend=backend, sent=later[0], sent_at=later[1]))
        else:
            rows.append(_row(str(i), channel, "read_back", value=v, t_wall=wall, backend=backend))
    return rows


def _laser_row(state: Any, present: bool, sent: tuple[str, str | None] | None) -> dict[str, Any]:
    """The blind channel. Nothing readable is the blocked-beam evidence here, so it is never shown off."""
    if not present:
        return _row(LASER, LASER, "not_open", reason="the run did not open it")
    if isinstance(state, dict) and state.get("error") is not None:
        return _row(LASER, LASER, "not_open", reason=f"the run did not open it: {state['error']}")
    if isinstance(state, dict) and state.get("not_read"):
        return _row(LASER, LASER, "not_read", reason=str(state.get("why") or "it was busy at the read"))
    return _row(LASER, LASER, "sent", value=ASSUMED_ON, reason=LASER_REASON,
                sent=sent[0] if sent else None, sent_at=sent[1] if sent else None)


def path_from_events(events: list[dict[str, Any]], t0: str | None) -> dict[str, Any]:
    """The optical path as a run read it back: `{t_wall, elements}`.

    The element names are the read-back's own (`states[<channel>]["elements"]`, `{id: value | None}`): none comes
    from a table here, and an element the read-back omits does not appear. A channel that reads nothing now keeps
    the names it gave earlier, without a value. An `apply` to a channel later than the latest snapshot makes
    its rows "sent", with what was read still beside its own time. The laser combiner is a row of its own once a
    snapshot exists, and is never shown off."""
    snaps = [e for e in events if e.get("event") == "snapshot" and isinstance(e.get("states"), dict)]
    if not snaps:
        return {"t_wall": None, "elements": []}
    last = snaps[-1]
    known: dict[str, list[str]] = {}
    for s in snaps:
        for channel, state in s["states"].items():
            els = _elements_of(state)
            if els is not None:
                ids = known.setdefault(str(channel), [])
                ids.extend(str(i) for i in els if str(i) not in ids)
    wall, t_last = _wall(t0, last.get("t_mono")), _num(last.get("t_mono"))
    rows: list[dict[str, Any]] = []
    for channel, ids in known.items():
        rows += _channel_rows(channel, ids, last["states"].get(channel), wall, _last_apply(events, channel, t_last, t0))
    rows.append(_laser_row(last["states"].get(LASER), LASER in last["states"], _last_apply(events, LASER, None, t0)))
    return {"t_wall": wall, "elements": rows}


def path_from_status(data: dict[str, Any]) -> dict[str, Any]:
    """The same path from the idle status file's last snapshot, outside a run: each reading with its own time.
    A run that took no snapshot (a live view) is shown as the file has it: the run, when it ended and its
    outcome text, unparsed."""
    last_run = data["last_run"]
    snap = last_run.get("last_snapshot")
    out: dict[str, Any] = {"source": "status_file", "run_id": last_run["run_id"], "kind": last_run.get("kind"),
                           "written_at": data.get("written_at"), "ended_at": last_run.get("ended_at"),
                           "ended_how": last_run.get("outcome"), "t_wall": None, "elements": []}
    if not isinstance(snap, dict):
        out["detail"] = NO_STATUS_SNAPSHOT
        return out
    out["t_wall"] = snap.get("t_wall")
    check = data.get("check_now") if isinstance(data.get("check_now"), dict) else {}
    errors = {c.get("channel"): c.get("error") for c in check.get("channels", []) if isinstance(c, dict) and c.get("error")} \
        if check.get("run_id") == last_run["run_id"] else {}
    rows, laser = [], None
    for r in snap.get("channels", []):
        channel, how, value, t = r.get("channel"), r.get("how"), r.get("value"), r.get("t_wall")
        if channel == LASER:
            if how == "not_read":
                laser = _row(LASER, LASER, "not_read", reason=str(errors.get(LASER) or "busy at the read, or not reached by the run (the status file gives no reason)"))
            else:
                laser = _row(LASER, LASER, "sent", value=ASSUMED_ON, reason=LASER_REASON,
                             sent=_text(value) if value is not None else None, sent_at=t if value is not None else None)
        elif how == "read_back" and _elements_of(value) is not None:
            backend = value.get("backend") if isinstance(value.get("backend"), str) else None
            note = value.get("note") if isinstance(value.get("note"), str) and value.get("note") else None
            for i, v in value["elements"].items():
                if v is None:
                    rows.append(_row(str(i), str(channel), "not_read", reason=NO_POSITION + (f"; {note}" if note else ""), backend=backend))
                else:
                    rows.append(_row(str(i), str(channel), "read_back", value=v, t_wall=t, backend=backend))
    rows.append(laser or _row(LASER, LASER, "not_open", reason="the run did not open it"))
    out["elements"] = rows
    return out


def _order_in_events(store: Any, events: list[dict[str, Any]]) -> dict[str, Any]:
    """The order of the latest snapshot only. An older snapshot's order is never carried forward: it was true of
    its own moment and the page says nothing it was not told."""
    snaps = [e for e in events if e.get("event") == "snapshot" and isinstance(e.get("states"), dict)]
    if not snaps:
        return order_state(store, False, None)
    return order_state(store, ORDER_KEY in snaps[-1], snaps[-1].get(ORDER_KEY))


def _status_path(store: Any) -> dict[str, Any] | None:
    fn = getattr(store, "runtime_root", None)
    read = read_idle_status(fn() if fn is not None else None)
    if read.state == "present" and read.data is not None and isinstance(read.data.get("last_run"), dict):
        path = path_from_status(read.data)
        path["order"] = order_state(store, ORDER_KEY in read.data, read.data.get(ORDER_KEY))
        return path
    return None
