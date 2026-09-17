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
    """Accept a parameter set and remember it, so read() can return it."""
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    with _LOCK:
        _STATE.update(params)
    return {"applied": dict(params)}


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
    _ABORTED = False
