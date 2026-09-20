"""The Micro-Manager backend: the brightness path's three channels.

`widefield_source_a` (excitation), `camera_red` (605-band collection) and
`stand_ti2e` (objective and filter) all reach the instrument through
Micro-Manager, and all three are `automatable: full` with `read_back: true`.
No read-back-less channel is on this path, which is why it is the one to wrap
first (4.6.6.1, card 012).

It implements preflight / apply / read / abort and nothing else, it knows only
itself, and **it holds no policy** -- whether a value is allowed is the
envelope's question, and a backend that judged its own parameters would put the
limits in two places (4.6.5). It imports nothing from the agent (7.2 rule 5).

## What crossed from the prior project, and what did not

Ruled under 10.2.1 before being written; the lines are in
`microscope_agent/rulings.jsonl`. Three pieces of structure:

**MMCore is reached as `(device, property, value)` triples** --
`getProperty` / `setProperty` / `setConfig` -- and read-back is
`getProperty(device, property)` on the same pair that was set. That is the
whole mechanism and it carries no number.

**`pymmcore-plus` is imported at each use site, never at module top.** In the
prior project that was load-bearing rather than stylistic: a top-level import
made test modules fail *collection* on a machine without Micro-Manager
installed. Here it matters more, because 4.6.5 requires the whole pipeline to
run without hardware and `mock.py` is a first-class backend rather than a
double. A module that cannot be imported without the instrument cannot be
checked without the instrument.

**Apply, then read, then compare** is the verification primitive, and their
`diff(wanted)` is exactly it. 2.1 makes an unverified state one that does not
proceed, so `apply` here returns what it read back and what disagreed rather
than reporting success on the strength of the write returning. A write that
returns is not a state that holds -- the same rule the tweezers taught, met
where read-back does exist.

**What did not cross: which device and which property.** Those are per
configuration and they are the registry's, not this file's. This backend knows
*how* to address MMCore and the channel row knows *what* to address -- so a
re-cabling or a new configuration file changes an entry and not this code. The
prior project put its labels in the module and paid for it in a config whose
label-to-state mapping was inverted for weeks.

**Also did not cross: their `focus.py` sweep machinery.** ZSpan, FocusCurve and
FocusAxis are focus-sweep logic, which is A5's and A6's question rather than a
control path, and the file carries working distances and an emission default
that 10.3 does not let across. One thing in it is a sequencing rule rather than
a limit and is reported up rather than taken here: **PFS must not be servoing
during a Z sweep.** A held focus fights the sweep -- the stage is commanded to
Z, PFS drives it back, and the recorded curve is of a plane that was never
visited. They lost a session to it. 2.1 already disables PFS across turret and
path changes; the sweep is a third case and adding it is the manager's.
"""

from __future__ import annotations

import threading

BACKEND = "micromanager"

#: The channels this backend is wrapped for. Not a permission -- the registry
#: says what is automatable and the envelope says what is allowed -- but a
#: refusal to be used somewhere it was never exercised (card 012: wrapping all
#: ten would produce control paths nothing runs).
WRAPPED = ("widefield_source_a", "camera_red", "stand_ti2e")

_LOCK = threading.Lock()
_ABORTED = False


class MicroManagerUnavailable(RuntimeError):
    """The driver is not installed or no configuration is loaded.

    Its own class because the orchestrator's next action differs: this is not a
    device refusing a command, it is the control path being absent, and a plan
    cannot proceed on the manual sheet either until a person loads a
    configuration.
    """


def _core():
    """The MMCore handle, imported here and not at module top.

    The import site is the point -- see the module docstring. Anything that
    needs the driver goes through this function, so there is one place where a
    machine without Micro-Manager turns into a legible error instead of an
    ImportError at collection time.
    """
    try:
        from pymmcore_plus import CMMCorePlus
    except ImportError as exc:                                  # pragma: no cover
        raise MicroManagerUnavailable(
            "pymmcore-plus is not installed, so this control path does not exist on "
            "this machine. mock.py is a first-class backend and is what runs here (4.6.5)"
        ) from exc
    core = CMMCorePlus.instance()
    if not core.getLoadedDevices():                             # pragma: no cover
        raise MicroManagerUnavailable(
            "no Micro-Manager configuration is loaded; a person loads one, and until then "
            "there is nothing to preflight against"
        )
    return core


def _settings(params: dict) -> tuple[tuple[str, str, object], ...]:
    """`{device: {property: value}}` into the triples MMCore stores.

    The shape the plan carries is the registry's, and flattening it here rather
    than in the caller keeps every backend taking the same `params`.
    """
    out = []
    for device, props in (params.get("settings") or {}).items():
        for prop, value in props.items():
            out.append((str(device), str(prop), value))
    return tuple(out)


def preflight(channel: dict | None = None) -> dict:
    """Whether this channel can be addressed, and whether it can be verified.

    Reports rather than decides. A channel the registry marks unreadable comes
    back `read_back: false` and the orchestrator routes it to a manual sheet
    (4.6.6 rule 5) -- this backend does not make that choice, and none of its
    three channels is in that state anyway.
    """
    channel = channel or {}
    cid = channel.get("id", "unknown")
    report = {
        "channel": cid,
        "backend": BACKEND,
        "wrapped": cid in WRAPPED,
        "read_back": channel.get("read_back", True),
        "automatable": channel.get("automatable"),
    }
    if cid not in WRAPPED:
        report.update(ready=False, reason=(
            f"{cid} is not one of the channels this backend was wrapped and exercised for "
            f"{list(WRAPPED)}; a control path nothing has run is not one to run first here"))
        return report
    try:
        core = _core()
    except MicroManagerUnavailable as exc:
        report.update(ready=False, reason=str(exc))
        return report
    loaded = set(core.getLoadedDevices())
    wanted = {d for d, _, _ in _settings(channel.get("params") or {})}
    missing = sorted(wanted - loaded)
    report.update(
        ready=not missing,
        devices_loaded=sorted(loaded),
        devices_missing=missing,
        aborted=_ABORTED,
    )
    if missing:
        report["reason"] = (
            f"the loaded configuration has no device named {missing}; the plan names an "
            "element the configuration does not, which is a gap and not a retry")
    return report


def apply(params: dict) -> dict:
    """Set the triples, read them back, and report what disagreed.

    **The read-back is the return value, not a courtesy.** A `setProperty` that
    returns has been accepted, which is not the same as a state that holds --
    2.1 makes an unverified state non-proceedable, and here read-back exists,
    so there is no reason to report success on the write alone.

    Values are compared as the strings MMCore stores them as. Comparing as
    numbers would need a tolerance, a tolerance is a policy, and policy does not
    live in a backend (4.6.5).
    """
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    core = _core()
    triples = _settings(params)
    if not triples:
        return {"applied": [], "verified": [], "disagreed": [], "backend": BACKEND}
    applied, verified, disagreed = [], [], []
    with _LOCK:
        for device, prop, value in triples:
            core.setProperty(device, prop, value)
            applied.append({"device": device, "property": prop, "value": value})
        core.waitForSystem()
        for device, prop, value in triples:
            got = core.getProperty(device, prop)
            record = {"device": device, "property": prop, "wanted": value, "read": got}
            (verified if str(got) == str(value) else disagreed).append(record)
    return {"applied": applied, "verified": verified, "disagreed": disagreed,
            "backend": BACKEND}


def read() -> dict:
    """Every settable property of the wrapped channels' loaded devices.

    Read from the instrument each time. This backend keeps no copy of the
    state: the instrument is the authority on its own state (4.6.8 constraint
    4), and a cached copy is a second answer that goes stale without saying so.
    """
    core = _core()
    state: dict[str, dict[str, object]] = {}
    for device in core.getLoadedDevices():
        props = {}
        for prop in core.getDevicePropertyNames(device):
            try:
                props[prop] = core.getProperty(device, prop)
            except Exception:                                   # pragma: no cover
                props[prop] = None                              # unreadable, and said so
        if props:
            state[device] = props
    return {"state": state, "aborted": _ABORTED, "backend": BACKEND}


def abort() -> dict:
    """Stop issuing, and stay stopped until reset().

    **It does not drive anything to a safe state**, and that is deliberate.
    Which state is safe is the envelope's and the orchestrator's -- shutters
    before power, z before the turret (2.1) -- and a backend that chose one
    would be holding policy and would be a second place the order is written.
    What this owes is to stop and to say it stopped.
    """
    global _ABORTED
    _ABORTED = True
    return {"aborted": True, "backend": BACKEND,
            "note": ("issuing stopped. Bringing the instrument to a safe state is the "
                     "orchestrator's sequence against envelope/safety.json, not this "
                     "backend's choice (4.6.5)")}


def reset() -> None:
    """Not part of the interface. Scaffolding, and only that."""
    global _ABORTED
    _ABORTED = False
