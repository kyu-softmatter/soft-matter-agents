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

# --------------------------------------------------------------------------- #
# what software may command (card 033 section 1)
# --------------------------------------------------------------------------- #
#
# AN ALLOW-LIST, NOT A DENY-LIST. The request that produced card 033 named ten
# devices to keep software away from; the configuration loaded on this
# instrument declares more motorised or light-emitting hardware than that --
# the spinning-disk unit's wheels, dichroic, port and shutter, a SECOND light
# engine labelled `Aura`, the DMD, the dia lamp, the Lapp branch, both turret
# shutters and the Ti2 hub itself. A deny-list written from the request would
# have passed every one of them. A device nobody thought about is refused,
# not permitted (2.1 rule 2).
#
# Keys are Micro-Manager labels, because that is the vocabulary a call into
# MMCore uses. `None` means every property of that device; a set names the
# only properties allowed. `Core` is here for the three role properties only:
# AutoShutter, which must be set to 0 after loading (see load_configuration),
# and the Camera / Shutter roles if they have to be named at all.
#
# This is the ONE copy. The orchestrator loads this file by path and asks
# `refusal()` before any command of a plan goes out, whatever the backend --
# so a plan fails whole on mock exactly as it would here -- and GuardedCore
# asks the same function at every call, as the backstop for a path that does
# not go through a plan. Two enforcement points, one list.
#
# Lifting it is a card's decision and not an edit made in passing: the
# retract and clearance interlocks block the first software-driven motion,
# and this list is what keeps today's session from being that motion.
SOFTWARE_MAY_COMMAND: dict[str, frozenset[str] | None] = {
    "LightEngine": None,
    "Kinetix_red": None,
    "Core": frozenset({"AutoShutter", "Camera", "Shutter"}),
}

#: The Core role properties are allowed ONLY at these values. A property on
#: the list is not enough: `AutoShutter` back at 1 makes every snap switch the
#: shutter device on by itself, and `Shutter` pointed at `Aura` would make that
#: shutter the second light engine -- light on the sample from a device that is
#: refused by name everywhere else.
CORE_VALUES = {"AutoShutter": frozenset({"0"}), "Camera": frozenset({"Kinetix_red"}),
               "Shutter": frozenset({"LightEngine"})}

#: Calls refused on EVERY device, allowed or not. Each of them moves something
#: or can: a group preset (`setConfig`) can set any property of any device,
#: and the focus calls drive Z on a stand that runs no escape for software.
REFUSED_CALLS = frozenset({
    "setPosition", "setRelativePosition", "setXYPosition", "setRelativeXYPosition",
    "setOriginXY", "setOriginX", "setOriginY", "setOrigin", "setAdapterOrigin",
    "setAdapterOriginXY", "home",
    "setState", "setStateLabel", "setConfig", "setSystemState", "setPixelSizeConfig",
    "fullFocus", "incrementalFocus", "enableContinuousFocus", "setAutoFocusOffset",
    "setFocusDevice", "setXYStageDevice", "setAutoFocusDevice",
    "setShutterOpen", "setGalvoPosition", "setSLMImage", "setSLMPixelsTo",
    "displaySLMImage", "loadGalvoPolygons", "runGalvoPolygons", "runGalvoSequence",
    "startStageSequence", "startXYStageSequence", "startPropertySequence",
    "loadStageSequence", "loadXYStageSequence", "loadPropertySequence",
    "mda", "run_mda", "snap", "setChannelGroup", "definePixelSizeConfig",
    "defineConfig", "defineConfigGroup", "loadDevice", "unloadDevice",
    "unloadAllDevices", "initializeDevice", "initializeAllDevices",
    "setParentLabel", "setSerialPortCommand", "writeToSerialPort",
    "setShutterDevice", "setCameraDevice",
})

#: The camera calls that write. Each is checked against the camera it would
#: act on -- the current Core camera when the call does not name one.
_CAMERA_CALLS = frozenset({
    "setExposure", "snapImage", "startSequenceAcquisition", "stopSequenceAcquisition",
    "startContinuousSequenceAcquisition", "prepareSequenceAcquisition",
    "clearCircularBuffer", "initializeCircularBuffer", "setCircularBufferMemoryFootprint",
    "setROI", "clearROI",
})

#: The camera calls that take a frame, and so would open the shutter device
#: by themselves if AutoShutter were on.
_EXPOSES = frozenset({"snapImage", "startSequenceAcquisition",
                      "startContinuousSequenceAcquisition"})

#: Anything else that does not write. Reading is not motion (card 033 section 1):
#: getProperty / getState / getStateLabel / getPosition on the stand are how a
#: session records what the person set by hand.
_READ_PREFIXES = ("get", "is", "has", "wait", "device", "supports", "pop")


#: Devices card 033 names as refused. They are refused already, because they
#: are not in SOFTWARE_MAY_COMMAND -- this tuple adds no permission and no
#: refusal. It exists so the names a person was told about can be checked
#: against the list mechanically (`named_refusals_hold()`), instead of trusting
#: that an allow-list covers them.
NAMED_REFUSALS = (
    "ZDrive", "Nosepiece", "XYStage", "PFS", "PFSOffset", "IntermediateMagnification",
    "FilterTurret1", "FilterTurret2", "LightPath", "CondenserTurret",
    "CSUW1-Filter_Red", "CSUW1-Filter_Blue", "CSUW1-Dichroic", "CSUW1-Port",
    "CSUW1-Bright", "CSUW1-Shutter", "Aura", "MightexPolygon1000", "DiaLamp",
    "LappMainBranch1", "Turret1Shutter", "Turret2Shutter", "Ti2-E__0",
    "NIDAQHub", "LUNF-Blanking",
)


def named_refusals_hold() -> list[str]:
    """Every name in NAMED_REFUSALS that the allow-list would NOT refuse. Empty is correct."""
    return [d for d in NAMED_REFUSALS if refusal(d, "State", "setProperty") is None]


class SoftwareMotionRefused(RuntimeError):
    """A call outside what software may command today, refused before it is sent."""


def refusal(device: str | None, prop: str | None = None,
            call: str = "setProperty", value: object = None) -> str | None:
    """Why this write is refused, or None if software may make it.

    Pure: it imports no driver, so the orchestrator can ask it on mock and on
    a machine without Micro-Manager. The reason is returned rather than raised
    so a plan check can collect every refusal in a plan and report them all.
    """
    if call in REFUSED_CALLS:
        return (f"{call}({device!r}) is refused on every device: it moves something or can. "
                "Software moves nothing today; the person moves the microscope by hand")
    if device is None:
        return None
    if device not in SOFTWARE_MAY_COMMAND:
        return (f"{device!r} is not a device software may command today. Allowed: "
                f"{sorted(SOFTWARE_MAY_COMMAND)}. Every other device is refused by name, "
                "including ones nobody listed -- a device nobody thought about is refused, "
                "not permitted")
    props = SOFTWARE_MAY_COMMAND[device]
    if props is not None and prop is not None and prop not in props:
        return (f"{device}.{prop} is refused: on {device} software may set only "
                f"{sorted(props)}")
    if device == "Core" and prop in CORE_VALUES and value is not None             and str(int(value) if isinstance(value, bool) else value) not in CORE_VALUES[prop]:
        return (f"Core.{prop} = {value!r} is refused: it may be set only to "
                f"{sorted(CORE_VALUES[prop])}")
    return None


class GuardedCore:
    """The MMCore handle with every write checked against the allow-list.

    AN ALLOW-LIST AT THE CALL LEVEL TOO. Reads pass through; `setProperty`,
    the camera calls and `setAutoShutter` are checked; every other method is
    refused because nobody listed it. pymmcore-plus adds convenience writes
    on top of MMCore -- `snap()`, `mda`, `setPosition` overloads -- and a
    wrapper that forwarded unknown names would forward those.
    """

    def __init__(self, core) -> None:
        object.__setattr__(self, "_core", core)

    def _check(self, device, prop=None, call="setProperty", value=None) -> None:
        why = refusal(device, prop, call, value)
        if why is not None:
            raise SoftwareMotionRefused(why)

    def setProperty(self, device, prop, value):
        self._check(str(device), str(prop), value=value)
        return self._core.setProperty(device, prop, value)

    def setAutoShutter(self, state):
        self._check("Core", "AutoShutter", value=int(bool(state)))
        return self._core.setAutoShutter(state)

    def __getattr__(self, name):
        attr = getattr(self._core, name)
        if name in REFUSED_CALLS:
            def refused(*args, **_kw):
                self._check(str(args[0]) if args else None, None, name)
            return refused
        if name in _CAMERA_CALLS:
            def camera_call(*args, **kw):
                # The overloads that name a camera take it first as a string;
                # the rest act on the Core camera, which is checked instead.
                named = args[0] if args and isinstance(args[0], str) else None
                self._check(named or self._core.getCameraDevice(), None, name)
                # And no exposure while AutoShutter is on: with it on, the
                # shutter device opens for the frame by itself, which is light
                # on the sample that no logged command put there.
                if name in _EXPOSES and self._core.getAutoShutter():
                    raise SoftwareMotionRefused(
                        f"{name} refused: Core AutoShutter is on, so this frame would switch "
                        "the light engine on by itself. Set it to 0 and read it back first")
                return attr(*args, **kw)
            return camera_call
        if name.startswith(_READ_PREFIXES) or not callable(attr):
            return attr
        def unlisted(*_args, **_kw):
            raise SoftwareMotionRefused(
                f"{name} is not on the list of calls software may make today, so it is refused "
                "rather than forwarded. Reads, setProperty on an allowed device, the camera "
                "calls and setAutoShutter are the whole of what passes")
        return unlisted

    def __setattr__(self, name, value):
        raise SoftwareMotionRefused(f"setting {name!r} on the core is not a listed call")


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
    # Guarded, always: nothing in this file reaches the unguarded handle
    # except load_configuration, which has to set AutoShutter before any
    # other call can be made.
    return GuardedCore(core)


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


# --------------------------------------------------------------------------- #
# loading, and acquisition (card 033 sections 2 and 3)
# --------------------------------------------------------------------------- #
#
# NO BACKEND ACQUIRED ANYTHING until these were written: no snapImage, no
# sequence, no setExposure anywhere in src/. They are primitives -- set, read
# back, report -- and hold no policy. Which order the light goes off in, and
# what counts as dark, is the session's and is written there.


def load_configuration(path: str, mm_dir: str | None = None) -> dict:
    """Load a configuration file IN PLACE, and set AutoShutter to 0 before anything else.

    THE AUTOSHUTTER LINE IS THE REASON THIS FUNCTION EXISTS. The file card
    033 names ends `Property,Core,Shutter,LightEngine` and
    `Property,Core,AutoShutter,1`, so as loaded every snap switches the light
    engine on by itself -- light on the sample that no logged command put
    there, and a dark frame that is lit by the very act of taking it. This is
    the one place that touches the unguarded handle, because it runs before
    the guard's own AutoShutter check could pass.

    Returns the sha256 of the bytes loaded, so the run log can name the exact
    file. A hash is taken before and after loading; a file that changed under
    the load is reported, not reconciled.

    `loadSystemConfiguration` is the ONE call made on the unguarded handle --
    the guard does not list it and is right to refuse it (card 033 3b
    condition 2). Everything after it, AutoShutter first, goes through
    GuardedCore. The load also applies the file's System/Startup preset, which
    is a command the file issues and not this function; the caller logs it.
    """
    import hashlib
    from pathlib import Path as _Path
    try:
        from pymmcore_plus import CMMCorePlus, find_micromanager
    except ImportError as exc:                                  # pragma: no cover
        raise MicroManagerUnavailable("pymmcore-plus is not installed") from exc

    def digest() -> str:
        return hashlib.sha256(_Path(path).read_bytes()).hexdigest()

    before = digest()
    core = CMMCorePlus.instance()
    mm_dir = mm_dir or find_micromanager()
    if not mm_dir:
        raise MicroManagerUnavailable("no Micro-Manager installation found for the adapters")
    core.setDeviceAdapterSearchPaths([str(mm_dir)])
    core.loadSystemConfiguration(str(path))                     # the one unguarded call
    guarded = GuardedCore(core)
    guarded.setAutoShutter(False)                               # first call after the load
    guarded.waitForSystem()
    auto_core = guarded.getAutoShutter()
    auto_prop = guarded.getProperty("Core", "AutoShutter")
    after = digest()
    return {
        "path": str(path), "sha256": before, "sha256_after_load": after,
        "changed_during_load": before != after, "mm_dir": str(mm_dir),
        "api": guarded.getAPIVersionInfo(), "mmcore": guarded.getVersionInfo(),
        "loaded_devices": list(guarded.getLoadedDevices()),
        "autoshutter": {"wanted": "0", "read_getAutoShutter": bool(auto_core),
                        "read_property": auto_prop,
                        "verified": (not auto_core) and str(auto_prop) == "0"},
        "core_shutter": guarded.getShutterDevice(), "core_camera": guarded.getCameraDevice(),
    }


def set_and_read(device: str, prop: str, value) -> dict:
    """One guarded write, waited for, read back. The read is the return value."""
    core = _core()
    core.setProperty(device, prop, value)
    core.waitForDevice(device)
    got = core.getProperty(device, prop)
    return {"device": device, "property": prop, "wanted": str(value), "read": got,
            "verified": str(got) == str(value)}


def set_exposure(ms: float) -> dict:
    """Exposure through the core call, read back with getExposure.

    It is a core call and not a property, so it publishes no allowed values
    (card 018 4e): the read-back is the only check that the camera took it.
    Compared as floats because MMCore returns a double; the camera may round
    to its own clock, and that difference is reported, not hidden.
    """
    core = _core()
    core.setExposure(float(ms))
    core.waitForDevice(core.getCameraDevice())
    got = core.getExposure()
    return {"wanted_ms": float(ms), "read_ms": got, "verified": abs(got - float(ms)) < 1e-6}


def _metadata(md) -> dict:
    """pymmcore-plus's Metadata as a plain dict, whatever shape this version returns."""
    if md is None:
        return {}
    try:
        return {str(k): str(v) for k, v in dict(md).items()}
    except Exception:                                           # pragma: no cover
        try:
            return {k: str(md.GetSingleTag(k).GetValue()) for k in md.GetKeys()}
        except Exception:
            return {"unreadable": repr(md)}


def snap():
    """One frame. Refused by the guard if AutoShutter is on."""
    core = _core()
    core.snapImage()
    image = core.getImage()
    return image, {"camera": core.getCameraDevice(), "exposure_ms": core.getExposure()}


def sequence(n: int, sink, timeout_s: float | None = None) -> dict:
    """`n` frames through the sequence calls, each handed to `sink(i, image, metadata)`.

    `n` is an integer and the loop counts popped frames against it -- never an
    accumulated time (card 018 4c): a boundary comparison is a decision, and a
    running sum lands a hair either side of it depending on the step.

    Frames go to the sink as they arrive rather than into a list: a full
    sensor frame is tens of MB and a series of hundreds would not fit. Each
    frame's metadata is kept because ImageNumber is the only evidence of a
    dropped frame (card 018 4b).
    """
    import time as _time
    n = int(n)
    core = _core()
    exposure_s = core.getExposure() / 1000.0
    timeout_s = timeout_s if timeout_s is not None else 30.0 + 3.0 * n * exposure_s
    numbers = []
    core.startSequenceAcquisition(n, 0.0, True)
    started = _time.monotonic()
    got = 0
    try:
        while got < n:
            if core.getRemainingImageCount() > 0:
                image, md = core.popNextImageAndMD()
                meta = _metadata(md)
                numbers.append(meta.get("ImageNumber"))
                sink(got, image, meta)
                got += 1
                continue
            if not core.isSequenceRunning() and core.getRemainingImageCount() == 0:
                break
            if _time.monotonic() - started > timeout_s:
                break
            _time.sleep(0.001)
    finally:
        if core.isSequenceRunning():
            core.stopSequenceAcquisition()
    return {"wanted": n, "received": got, "image_numbers": numbers,
            "gaps": image_number_gaps(numbers), "overflowed": bool(core.isBufferOverflowed())}


def image_number_gaps(numbers: list) -> list:
    """Every missing ImageNumber between consecutive frames, or a note that none could be read."""
    ints = []
    for value in numbers:
        try:
            ints.append(int(value))
        except (TypeError, ValueError):
            return [{"unreadable": value}]
    return [{"after": a, "before": b} for a, b in zip(ints, ints[1:]) if b != a + 1]
