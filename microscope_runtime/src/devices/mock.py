"""A first-class backend, not a test double (4.6.5).

The whole pipeline has to run without hardware, and M1-M3 are verified here
before any real device is wired. So this file is held to the same rule as the
others: it implements preflight / apply / read / abort, it knows only itself,
and it holds no policy. Whether a value is allowed is the envelope's question,
never the backend's -- a backend that judged its own parameters would put the
limits in two places (4.6.5).

It imports nothing from the agent. Device modules do not import siblings and do
not import upward (7.2 rule 5); the four functions are a convention the
orchestrator checks at load time, not a base class to inherit.
"""

from __future__ import annotations

import threading

_STATE: dict[str, object] = {}
_PROPS: dict[tuple[str, str], str] = {}     # (device, property) -> value, as MMCore stores it
_LOCK = threading.Lock()
_ABORTED = False


def preflight(channel: dict | None = None) -> dict:
    """Report what this channel would report, including what it cannot.

    The mock copies one property of the real instrument deliberately: a channel
    whose registry row says read_back is false answers false here too. Code that
    only ever met a fully readable mock would meet the manual path for the first
    time on the instrument.
    """
    channel = channel or {}
    return {
        "channel": channel.get("id", "mock"),
        "ready": True,
        "read_back": channel.get("read_back", True),
        "automatable": channel.get("automatable", "full"),
        "backend": "mock",
    }


def apply(params: dict) -> dict:
    """Accept a parameter set and remember it, so read() can return it.

    `settings` -- `{device: {property: value}}`, the shape micromanager.apply
    takes -- is also kept per (device, property) and read back from there,
    and reported as `verified` / `disagreed` the way that backend reports it.
    Without it a caller that judges a write by its read-back (card 054's
    power-down) could only ever meet the "no read-back" branch here and would
    meet the real one for the first time on the instrument.
    """
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    out: dict[str, object] = {"applied": dict(params), "backend": "mock"}
    with _LOCK:
        _STATE.update(params)
        settings = params.get("settings") or {}
        if settings:
            verified, disagreed = [], []
            for device, props in settings.items():
                for prop, value in (props or {}).items():
                    _PROPS[(str(device), str(prop))] = str(value)
            for device, props in settings.items():
                for prop, value in (props or {}).items():
                    got = _PROPS[(str(device), str(prop))]
                    record = {"device": str(device), "property": str(prop),
                              "wanted": value, "read": got}
                    (verified if got == str(value) else disagreed).append(record)
            out.update(verified=verified, disagreed=disagreed)
    return out


def close_for_abort(device: str, prop: str, value: object) -> dict:
    """micromanager.close_for_abort's shape: write one pair, read it back.

    Holds no policy, like the rest of this file. Which closes are allowed is
    micromanager.abort_close_refusal(), and the orchestrator asks it before
    calling this on any backend.
    """
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    with _LOCK:
        _PROPS[(str(device), str(prop))] = str(value)
        got = _PROPS[(str(device), str(prop))]
    record = {"device": str(device), "property": str(prop), "wanted": value, "read": got}
    ok = got == str(value)
    return {"applied": [{"device": device, "property": prop, "value": value}],
            "verified": [record] if ok else [], "disagreed": [] if ok else [record],
            "backend": "mock"}


def focus_z_move(target_um: float) -> dict:
    """micromanager.focus_z_move's shape: one ABSOLUTE Z target, then the encoder read.

    No policy: which Z moves may be made is the orchestrator's focus-search
    gate (card 055). The mock's encoder reads back exactly what was sent;
    a test that needs a drift replaces this function.
    """
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    with _LOCK:
        _PROPS[("ZDrive", "Position")] = str(float(target_um))
        got = float(_PROPS[("ZDrive", "Position")])
    return {"target_um": float(target_um), "read_um": got, "backend": "mock"}


def read_z() -> float | None:
    """The mock encoder, or None if nothing has moved Z: the mock does not invent a position."""
    with _LOCK:
        value = _PROPS.get(("ZDrive", "Position"))
    return None if value is None else float(value)


def read_property(device: str, prop: str) -> str | None:
    """One stored (device, property), or None if nothing set it."""
    with _LOCK:
        return _PROPS.get((str(device), str(prop)))


#: Seconds between mock frames. 0 by default; a test that needs a sequence
#: with a duration sets it.
FRAME_DELAY_S = 0.0

#: Bytes in one mock frame. Small by default; a test that needs a frame too big
#: for a socket buffer sets it.
FRAME_BYTES = 64

#: (rows, cols) for frames a viewer can draw, or None for the byte frames
#: above. With a shape, and numpy importable, each frame is a 2-D uint16
#: array whose diagonal stripes move with the frame index, so a live view on
#: mock visibly changes. The values are synthetic: no camera's counts, and
#: no full-scale count is implied by them.
FRAME_SHAPE: tuple[int, int] | None = None


#: Channel -> (the camera's device name in its metadata, a stripe phase), for the two cameras. The
#: phase only makes one camera's frames differ from the other's, so a screen showing both can be
#: seen to show both. Synthetic, like every frame here: no sensor, no count and no image of anything.
CAMERAS = {"camera_red": ("Kinetix_red", 0), "camera_blue": ("Kinetix_blue", 32)}


def _camera(channel_id):
    return CAMERAS.get(channel_id, ("mock", 0))


def _frame(i: int, phase: int = 0):
    if FRAME_SHAPE is None:
        return bytes([(i + phase) % 256]) * FRAME_BYTES
    import numpy as np
    rows, cols = FRAME_SHAPE
    stripes = (np.add.outer(np.arange(rows), np.arange(cols)) + 4 * i + phase) % 64
    return (stripes * 1000).astype(np.uint16)


#: The Z, in um of the mock encoder, at which mock snapshots are sharpest, or
#: None for no focus at all. With it and FRAME_SHAPE set, snap() returns a
#: frame whose structure fades into a fixed noise floor away from it, so a
#: focus search on mock has something to find. Synthetic: no objective's
#: depth of field and no sample is implied.
FOCUS_Z_UM: float | None = None
#: How far from FOCUS_Z_UM, in um, the structure has faded to 1/e.
FOCUS_WIDTH_UM = 8.0
_SNAPS = [0]


def snap():
    """micromanager.snap's shape: one frame and its metadata.

    Synthetic bytes by default. With FRAME_SHAPE set, a 2-D uint16 frame;
    with FOCUS_Z_UM set too, its structure depends on the mock encoder's Z.
    """
    return _snap(None)


def snap_for(channel_id: str):
    """snap(), for a channel that is a camera: its frames carry its own name and stripe phase (card 084)."""
    return _snap(channel_id)


def _snap(channel_id):
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    name, phase = _camera(channel_id)
    n = _SNAPS[0]
    _SNAPS[0] += 1
    meta = {"camera": name, "exposure_ms": None, "ImageNumber": str(n)}
    if FRAME_SHAPE is None:
        return bytes([phase % 256]) * 64, meta
    if FOCUS_Z_UM is None:
        return _frame(n, phase), meta
    import math
    import numpy as np
    with _LOCK:
        z = _PROPS.get(("ZDrive", "Position"))
    z = float(z) if z is not None else float("inf")
    sharp = math.exp(-((z - FOCUS_Z_UM) / FOCUS_WIDTH_UM) ** 2)
    rows, cols = FRAME_SHAPE
    rng = np.random.default_rng(1234)                   # the same noise floor in every frame
    noise = rng.normal(0.0, 1.0, (rows, cols))
    yy, xx = np.mgrid[0:rows, 0:cols]
    blobs = np.sin((xx + phase) / 3.0) * np.sin(yy / 3.0)    # structure that blur would remove
    image = 2000 + 300 * noise + 1500 * sharp * blobs
    meta["z_um_mock"] = z
    return np.clip(image, 0, 65535).astype(np.uint16), meta


def sequence(n: int, sink, timeout_s: float | None = None) -> dict:
    """micromanager.sequence's shape: `n` synthetic frames, each handed to `sink(i, image, md)`.

    Counted by integer, as the real one is. The frames are bytes, not sensor
    data; each carries the ImageNumber the real metadata would.
    """
    return _sequence(None, n, sink)


def sequence_for(channel_id: str, n: int, sink, timeout_s: float | None = None) -> dict:
    """sequence(), for a channel that is a camera: its frames carry its own name and stripe phase (card 084)."""
    return _sequence(channel_id, n, sink)


def _sequence(channel_id, n: int, sink) -> dict:
    import time as _time
    name, phase = _camera(channel_id)
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    numbers = []
    for i in range(int(n)):
        if _ABORTED:
            # An abort ends the sequence at the next frame, as it does on the
            # instrument: a stop that waited for n frames would not be a stop.
            break
        if FRAME_DELAY_S:
            _time.sleep(FRAME_DELAY_S)
        meta = {"Camera": name, "ImageNumber": str(i)}
        numbers.append(meta["ImageNumber"])
        sink(i, _frame(i, phase), meta)
    return {"wanted": int(n), "received": len(numbers), "image_numbers": numbers,
            "gaps": [], "overflowed": False, "aborted": _ABORTED}


class ReadWouldWait(RuntimeError):
    """A read asked not to wait found the device busy (card 076 part E, plan.md 13.4 item 2).

    The caller records the channel as not read at that tick, with this reason, and never gives
    it its last value.
    """

    would_wait = True


def read(wait: bool = True) -> dict:
    """Return the state this backend was last told to hold.

    The real instrument is the authority on its own state and a device keeps no
    copy of it (4.6.8 constraint 4). Here there is no instrument, so this dict
    stands in for one -- the one place the mock is not like the thing it stands
    for, and worth saying out loud.
    """
    if not _LOCK.acquire(blocking=wait):
        raise ReadWouldWait(f"mock: a command, a sequence or another read holds this device's lock, and this read was asked not to wait")
    try:
        return {"state": dict(_STATE), "aborted": _ABORTED, "backend": "mock"}
    finally:
        _LOCK.release()


# --- the channel-aware pair (card 086 items 2-4 and 6) ------------------------ #
#
# The three functions above take no channel, so every channel reads the same dict. The Instruments
# tab needs the piezo to be somewhere between two positions while it moves, the tweezers to say they
# cannot be read, and an element nobody set to read as unset. The orchestrator calls apply_for /
# read_for when this file has them and falls back to apply / read for any other module, so a
# channel with nothing special here behaves exactly as it always did.
#
# What these add is behaviour a reader will meet on the instrument, never a number. Every constant
# below is synthetic, and the mock still holds no policy: a position is not refused here, and an
# element is not allowed or disallowed here -- the allow-list and the envelope are the orchestrator's.

#: How fast the mock stage moves toward a commanded position, um per second. Synthetic: no stage's
#: slew rate is implied. A test that needs a slow or a fast one sets it.
PIEZO_RATE_UM_PER_S = 2000.0

#: Seconds between a point being sent and the mock stage starting toward it. Synthetic: no
#: controller's latency is implied.
PIEZO_LAG_S = 0.01

#: Seconds a move polls for the mock stage to settle within the tolerance before it gives up and
#: reports a disagreement. Synthetic: not the instrument's settle wait.
PIEZO_SETTLE_WAIT_S = 2.0

#: Where each axis stands before anything has moved it, um. Synthetic: not a rest position of any
#: stage, and not a value inside or outside anyone's envelope.
PIEZO_START_UM = 0.0

#: Held only for an instant to read or advance the mock stage, never across a move, so a watcher's
#: read that is asked not to wait still gets a position while a move is under way.
_PIEZO_LOCK = threading.Lock()
_PIEZO: dict[str, dict] = {}                    # axis -> {pos, t, target, queue[(t_effective, target)]}
_PIEZO_AXES = ("x", "y", "z")

#: (channel, element) -> what a hand set it to. Written only by set_by_hand, which stands for the
#: person turning something at the instrument; no command ever writes it.
_HAND: dict[tuple[str, str], object] = {}


def _axis(axis: str, now: float) -> dict:
    """The state of one axis, created at the start position the first time anything asks."""
    state = _PIEZO.get(axis)
    if state is None:
        state = _PIEZO[axis] = {"pos": PIEZO_START_UM, "t": now, "target": None, "queue": []}
    return state


def _advance(axis: str, now: float) -> dict:
    """Move one axis to `now`: toward the active target at the rate, switching targets as each lag ends.

    Exact between events rather than stepped, so a read at any instant sees where a stage with
    this rate and this lag would be, and never a position beyond the target it was last sent.
    Call with _PIEZO_LOCK held.
    """
    state = _axis(axis, now)
    t = state["t"]
    while t < now or (state["queue"] and state["queue"][0][0] <= now):
        nxt = state["queue"][0][0] if state["queue"] else None
        end = now if nxt is None or nxt > now else max(nxt, t)
        if state["target"] is not None and end > t:
            reach = PIEZO_RATE_UM_PER_S * (end - t)
            error = state["target"] - state["pos"]
            state["pos"] += max(-reach, min(reach, error))
        t = end
        if nxt is not None and nxt <= now:
            state["target"] = state["queue"].pop(0)[1]
    state["t"] = now
    return state


def _piezo_pos(axis: str) -> float:
    import time
    with _PIEZO_LOCK:
        return _advance(axis, time.monotonic())["pos"]


def _piezo_trajectory(params: dict) -> dict:
    """python_serial._run_trajectory's shape, run against the mock stage in real time.

    Point i goes out at t0 + (i - first) * dt, the stage starts toward it PIEZO_LAG_S later, and
    each sample's `measured_um` is read right after the send, so it lags the target as a real
    read does. The move then polls for the last target within the plan's tolerance for at most
    PIEZO_SETTLE_WAIT_S. With no tolerance neither `verified` nor `disagreed` has anything in it:
    the mock does not pick one. Every axis is treated alike -- whether Z may move is not asked here.
    """
    import time
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    trajectory = params["trajectory"]
    axis, dt = str(trajectory["axis"]), float(trajectory["dt_s"])
    points = [(int(p[0]), float(p[1])) for p in trajectory["points"]]
    tolerance = (params.get("tolerance_um") or {}).get("value")
    before = _piezo_pos(axis)
    first = points[0][0]
    t0 = time.monotonic()
    samples, late = [], 0
    for i, target in points:
        planned = (i - first) * dt
        wait = t0 + planned - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        if _ABORTED:
            break
        sent = time.monotonic()
        with _PIEZO_LOCK:
            state = _advance(axis, sent)
            state["queue"].append((sent + PIEZO_LAG_S, target))
            state["queue"].sort(key=lambda e: e[0])
        sample = {"i": i, "t_planned_s": planned, "t_sent_s": sent - t0, "target_um": target,
                  "measured_um": _piezo_pos(axis)}
        if sent - t0 > planned + dt:
            sample["late"] = True
            late += 1
        samples.append(sample)
    final = points[-1][1]
    settle, read = [], _piezo_pos(axis)
    sent_all = time.monotonic()
    if tolerance is not None:
        deadline = sent_all + PIEZO_SETTLE_WAIT_S
        while True:
            read = _piezo_pos(axis)
            settle.append({"t_s": time.monotonic() - t0, "measured_um": read})
            if abs(read - final) <= float(tolerance) or time.monotonic() >= deadline or _ABORTED:
                break
            time.sleep(max(dt, 0.001))
    out: dict[str, object] = {
        "move": trajectory.get("move_id"), "axis": axis, "channel": "piezo_stage",
        "before_um": before, "after_um": read, "points_sent": len(samples),
        "points_planned": len(points), "late_points": late, "dt_s": dt, "samples": samples,
        "settle": settle, "settle_wait_s": PIEZO_SETTLE_WAIT_S, "verified": [], "disagreed": [],
        "backend": "mock"}
    if tolerance is not None and len(samples) == len(points):
        record = {"axis": axis, "target_um": final, "read_um": read, "tolerance_um": tolerance,
                  "settled_after_s": time.monotonic() - sent_all}
        (out["verified"] if abs(read - final) <= float(tolerance) else out["disagreed"]).append(record)
    elif tolerance is not None:
        out["disagreed"].append({"axis": axis, "target_um": final, "read_um": read,
                                 "tolerance_um": tolerance, "note": "stopped before every point was sent"})
    return out


def _piezo_read() -> dict:
    """Where the mock stage is now, and whether it is still on its way.

    The position is the mock's: it says nothing about where any stage is, and it is observed on
    the mock only.
    """
    import time
    now = time.monotonic()
    with _PIEZO_LOCK:
        states = {a: _advance(a, now) for a in _PIEZO_AXES}
        moving = any(s["queue"] or (s["target"] is not None and abs(s["target"] - s["pos"]) > 1e-9)
                     for s in states.values())
        position = {a: s["pos"] for a, s in states.items()}
    return {"position_um": position, "moving": moving, "aborted": _ABORTED, "backend": "mock",
            "note": "a synthetic position, observed on the mock only"}


def apply_for(channel_id: str, params: dict) -> dict:
    """apply(), for a channel that behaves differently from the generic one; apply() for the rest.

    The piezo moves in time and reports as python_serial does. The tweezers echo the commands as
    sent and say nothing about them having been seen: the Tweez 300 interface has no query of any
    kind, and an echo that carried `verified` would give a screen a read-back the instrument
    cannot give.
    """
    if channel_id == "piezo_stage" and isinstance(params.get("trajectory"), dict):
        return _piezo_trajectory(params)
    if channel_id == "optical_tweezers":
        if _ABORTED:
            raise RuntimeError("aborted: this backend refuses commands until it is reset")
        return {"applied": dict(params), "commands_sent": [list(c) for c in params.get("commands") or []],
                "backend": "mock"}
    return apply(params)


def read_for(channel_id: str, wait: bool = True, elements=()) -> dict:
    """read(), for a channel that is not the generic one; read() plus `elements` for the rest.

    `elements` is the channel's registry ids. Each is reported with what a hand set it to, or
    None if nothing did: the mock never invents a position for a turret, a wheel or a splitter,
    and a position read from it would not say which element is in the beam. The piezo is read
    without waiting even during a move, and the tweezers' read is empty on purpose -- no
    `state`, no `position_um`, so what was sent is never offered back as what is there.
    """
    if channel_id == "piezo_stage":
        return _piezo_read()
    if channel_id == "optical_tweezers":
        return {"read_back": False, "verification": "none", "aborted": _ABORTED, "backend": "mock",
                "note": "the Tweez 300 interface has no query of any kind; this is not a state"}
    if not _LOCK.acquire(blocking=wait):
        raise ReadWouldWait("mock: a command, a sequence or another read holds this device's lock, and this read was asked not to wait")
    try:
        out: dict[str, object] = {"state": dict(_STATE), "aborted": _ABORTED, "backend": "mock"}
        if elements:
            out["elements"] = {str(e): _HAND.get((channel_id, str(e))) for e in elements}
            out["note"] = ("an element reads as None until a hand set it on the mock; a position "
                           "read from the mock is the mock's and does not establish which element "
                           "is in the beam")
        return out
    finally:
        _LOCK.release()


def set_by_hand(channel_id: str, element_id: str, value: object) -> None:
    """Stand for the person turning one element at the instrument. Never reached by a command."""
    with _LOCK:
        _HAND[(str(channel_id), str(element_id))] = value


def abort() -> dict:
    """Stop, and stay stopped until reset(), so nothing quietly continues."""
    global _ABORTED
    _ABORTED = True
    return {"aborted": True, "backend": "mock"}


def reset() -> None:
    """Not part of the interface. Test scaffolding, and only that."""
    global _ABORTED
    with _LOCK:
        _STATE.clear()
        _PROPS.clear()
        _HAND.clear()
        _SNAPS[0] = 0
    with _PIEZO_LOCK:
        _PIEZO.clear()
    _ABORTED = False
