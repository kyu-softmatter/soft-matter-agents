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
    out: dict[str, object] = {"applied": dict(params)}
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


def snap():
    """micromanager.snap's shape: one frame and its metadata. The frame is synthetic bytes."""
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    return bytes(64), {"camera": "mock", "exposure_ms": None, "ImageNumber": "0"}


def sequence(n: int, sink, timeout_s: float | None = None) -> dict:
    """micromanager.sequence's shape: `n` synthetic frames, each handed to `sink(i, image, md)`.

    Counted by integer, as the real one is. The frames are bytes, not sensor
    data; each carries the ImageNumber the real metadata would.
    """
    import time as _time
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    numbers = []
    for i in range(int(n)):
        if FRAME_DELAY_S:
            _time.sleep(FRAME_DELAY_S)
        meta = {"Camera": "mock", "ImageNumber": str(i)}
        numbers.append(meta["ImageNumber"])
        sink(i, bytes([i % 256]) * FRAME_BYTES, meta)
    return {"wanted": int(n), "received": len(numbers), "image_numbers": numbers,
            "gaps": [], "overflowed": False}


def read() -> dict:
    """Return the state this backend was last told to hold.

    The real instrument is the authority on its own state and a device keeps no
    copy of it (4.6.8 constraint 4). Here there is no instrument, so this dict
    stands in for one -- the one place the mock is not like the thing it stands
    for, and worth saying out loud.
    """
    with _LOCK:
        return {"state": dict(_STATE), "aborted": _ABORTED, "backend": "mock"}


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
    _ABORTED = False
