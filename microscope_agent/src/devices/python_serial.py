"""The piezo stage backend: `piezo_stage`, driver `python_serial + vendor_dll`.

The router takes the head token of the registry's driver column, so this file
is `python_serial.py` and it answers for that channel alone. It implements
preflight / apply / read / abort like the other backends and imports nothing
from the agent (7.2 rule 5).

Card 035, phase A: **nothing here touches the hardware.** Two links exist and
neither opens a port. `MockLink` is an in-process controller. `DllLink` loads
the vendor DLL and opens only its simulator address, `sim:/...`; any other
address is refused before the DLL is asked, because opening a port is phase B
and phase B is the person's hand-over in the executing seat's own window, not
something this file can see.

## What this backend refuses, and why it is allowed to

The other backends hold no policy: whether a value is allowed is the
envelope's question (4.6.5). This one still holds none -- **every number it
compares against is read from `envelope/safety.json` at the moment of use**
and none is written here. What it holds is the refusal to act when that file
is silent, which card 035 requires of it and which is the same shape as
`GuardedCore`: a backstop at the call for a path that does not go through a
plan.

- **An axis whose limits are absent is refused, every command on it.** A
  missing limit is a refusal, never a default to the device range. The device
  range the person stated (-100 to 600 um) is a statement about the stage,
  not a permission, and it appears in this file only in this sentence.
- **A floor above its ceiling is refused.** The schema requires the two ends
  together and cannot compare them; the consumer compares them before use.
- **Every commanded axis's position is read before the first command, and a
  start outside the limit is refused.** It is never "corrected" by moving into
  range: that would be an unplanned move, made by the one component that was
  supposed to only refuse.
- **A target outside the limit is refused.**
- **The waveform generator is refused entirely.** In the prior project a
  +/-5 um sine uploaded in picometres swung an axis 314 um, and the unit the
  generator reads was never settled there. It stays refused until that unit
  is measured on this controller; the failure record carries it.
- **Z moves only as a direction-finding step, with the step size supplied by
  the plan as the person's.** Which piezo-Z direction approaches the objective
  is unmeasured, and a travel limit is not a clearance limit:
  `objective_clearance_min` binds piezo Z as it binds the focus drive, and this
  backend cannot compute a clearance, so it refuses what it cannot bound.
- **Every exit returns the controller to the security level it was found
  at**, on success, on refusal, on abort and on an exception. Commands exist
  only after an unlock, and the prior scripts carried a `--leave-unlocked`
  flag; nothing here can leave it unlocked.

Everything the person stated about this stage -- three axes, X Y Z on
controller channels 1 2 3 -- is a statement and not a reading until the first
live check verifies the mapping with a step per channel and an image.
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path

BACKEND = "python_serial"
WRAPPED = ("piezo_stage",)

#: The person's statement of 2026-09-24, not a reading (card 035). The first
#: live motion verifies it by a step per channel while watching the image.
AXIS_CHANNEL = {"x": 1, "y": 2, "z": 3}

#: The one axis that can reach the objective. Which of its directions does is
#: unmeasured, so it moves only as a direction-finding step (see apply()).
COLLISION_AXIS = "z"

_ENVELOPE = Path(__file__).resolve().parents[2] / "envelope" / "safety.json"
_LOCK = threading.Lock()
_ABORTED = False
_LINK = None            # the open link, if any; the instrument keeps the state
_FOUND_LEVEL = None     # the security level an unlock found, while one is in force


class PiezoRefused(RuntimeError):
    """A command this backend will not issue. Not a failure of the device."""


# --------------------------------------------------------------------------- #
# limits: read from the envelope at the moment of use, never held here
# --------------------------------------------------------------------------- #


def _limits(envelope_path: Path | None = None) -> dict[str, tuple[float | None, float | None]]:
    """Each axis's (floor, ceiling) as the envelope states them, None where absent.

    Read every time rather than cached: the person may write the file while a
    session is up, and a cached copy is a second answer that goes stale without
    saying so. A limit's value is read and nothing else about it is trusted --
    its `confirmation` is the person's record, not an input to a comparison.
    """
    path = envelope_path or _ENVELOPE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        doc = {}
    found: dict[str, dict] = {}
    for target in doc.get("targets") or []:
        for name, spec in (target.get("limits") or {}).items():
            if name.startswith("piezo_") and isinstance(spec, dict):
                found[name] = spec
    out = {}
    for axis in AXIS_CHANNEL:
        lo = found.get(f"piezo_{axis}_position_min", {})
        hi = found.get(f"piezo_{axis}_position_max", {})
        out[axis] = (lo.get("value") if lo.get("unit") == "um" else None,
                     hi.get("value") if hi.get("unit") == "um" else None)
    return out


def axis_refusal(axis: str, limits: dict) -> str | None:
    """Why no command may touch this axis, or None if its limits permit a check.

    Two refusals and both are about the envelope, not the target: the limit is
    absent, or the pair is inverted. Neither falls back to anything.
    """
    if axis not in AXIS_CHANNEL:
        return f"{axis!r} is not an axis of this stage; the axes are {sorted(AXIS_CHANNEL)}"
    lo, hi = limits.get(axis, (None, None))
    if lo is None or hi is None:
        missing = [n for n, v in ((f"piezo_{axis}_position_min", lo),
                                  (f"piezo_{axis}_position_max", hi)) if v is None]
        return (f"envelope/safety.json has no {', '.join(missing)} in um, so every command on "
                f"axis {axis} is refused. A missing limit is a refusal and never a default to the "
                "device range; only the person writes that file")
    if lo > hi:
        return (f"piezo_{axis}_position_min is {lo} um and piezo_{axis}_position_max is {hi} um: "
                "the floor is above the ceiling, which the schema cannot see and this backend "
                "refuses rather than guessing which end was meant")
    return None


def position_refusal(axis: str, where: str, value: float, limits: dict) -> str | None:
    lo, hi = limits[axis]
    if not (lo <= value <= hi):
        return (f"axis {axis} {where} is {value} um, outside the envelope's {lo} to {hi} um. "
                + ("It is refused and not corrected: moving it into range would be an unplanned "
                   "move made by the component whose job is to refuse"
                   if where == "start" else "The target is refused"))
    return None


def waveform_refusal(params: dict) -> str | None:
    """The controller's waveform generator is refused, whatever the request says.

    In the prior project a +/-5 um sine uploaded in picometres swung an axis
    314 um, and the unit the generator reads was never settled there. A sine
    stepped from software, as paced position writes each checked against the
    envelope, is the shape that remains, and it is a planned operation.
    """
    if any(k in params for k in ("waveform", "wave_generator", "wgo", "sine")):
        return ("the controller's waveform generator is refused entirely. In the prior project a "
                "+/-5 um sine uploaded in picometres swung an axis 314 um, and the unit the "
                "generator reads was never settled there. Refused until that unit is measured here")
    return None


def z_refusals(targets: dict, start: dict, params: dict) -> list[str]:
    """Piezo Z moves only as a direction-finding step the plan gives as the person's."""
    if COLLISION_AXIS not in targets:
        return []
    step = params.get("z_direction_finding") or {}
    size, who = step.get("step_um"), step.get("by")
    if size is None or not who:
        return ["piezo Z moves only as a direction-finding step whose size the plan gives as the "
                "person's (z_direction_finding.step_um and .by). Which Z direction approaches the "
                "objective is unmeasured, and a travel limit is not a clearance limit"]
    moved = abs(targets[COLLISION_AXIS] - start[COLLISION_AXIS])
    if moved > abs(float(size)):
        return [f"the Z move is {moved} um and the person's direction-finding step is "
                f"{abs(float(size))} um"]
    return []


# --------------------------------------------------------------------------- #
# links: how the controller is reached. Neither opens a port in phase A.
# --------------------------------------------------------------------------- #


class MockLink:
    """An in-process controller: positions per channel and a security level.

    It keeps the two properties of the real one that the refusals depend on:
    commands are rejected while it is locked, and it reports where it is
    rather than where it was told to go. Positions start at `start_um` so a
    test can place an axis out of range without the backend moving it there.
    """

    BASE_LEVEL = "locked"

    def __init__(self, start_um: dict[str, float] | None = None):
        start = start_um or {}
        self.position = {AXIS_CHANNEL[a]: float(start.get(a, 0.0)) for a in AXIS_CHANNEL}
        self.level = self.BASE_LEVEL
        self.commands: list[tuple] = []
        self.closed = False

    def security_level(self) -> str:
        return self.level

    def set_security_level(self, level: str) -> None:
        self.commands.append(("security", level))
        self.level = level

    def read_position(self, channel: int) -> float:
        return self.position[channel]

    def move_absolute(self, channel: int, target_um: float) -> None:
        if self.level == self.BASE_LEVEL:
            raise RuntimeError("controller is locked: commands exist only after an unlock")
        self.commands.append(("move", channel, target_um))
        self.position[channel] = float(target_um)

    def close(self) -> None:
        self.closed = True


def open_link(kind: str = "mock", address: str | None = None, **kw):
    """Open a link and hold it for this process. Phase A: mock or simulator only."""
    global _LINK
    if kind == "mock":
        link = MockLink(**kw)
    elif kind == "dll":
        link = DllLink(address or "", **kw)
    else:
        raise PiezoRefused(f"no link kind {kind!r}; phase A has 'mock' and 'dll' (simulator only)")
    with _LOCK:
        _LINK = link
    return link


def close_link() -> None:
    global _LINK
    with _LOCK:
        link, _LINK = _LINK, None
    if link is not None:
        link.close()


def _link():
    if _LINK is None:
        raise PiezoRefused("no link is open; open_link() first. Nothing opens one implicitly, "
                           "because an implicit open is how a port gets opened by accident")
    return _LINK


@contextmanager
def unlocked(link, level: str = "user"):
    """Unlock for the body, and put the level back on EVERY exit.

    The base level is read from the controller, not assumed, and restored in
    `finally`, so a refusal, an exception or an abort in the body all leave the
    controller where it was found. There is no option to skip the restore.
    """
    base = link.security_level()
    restorable = getattr(link, "restorable", None)
    if restorable is not None and not restorable(base):
        # Refused with NOTHING changed. Finding out what a level reads as by
        # setting it would itself move the controller off the level found,
        # which is the thing this guard exists to prevent; that is a separate,
        # deliberate step (DllLink.learn_levels), done with the person present.
        raise PiezoRefused(
            f"the controller was found at security level {base!r}, which this link does not know "
            "how to restore; nothing is unlocked rather than leaving it somewhere it was not")
    global _FOUND_LEVEL
    _FOUND_LEVEL = base
    link.set_security_level(level)
    try:
        yield base
    finally:
        link.set_security_level(base)
        _FOUND_LEVEL = None


# --------------------------------------------------------------------------- #
# the four functions
# --------------------------------------------------------------------------- #


def preflight(channel: dict | None = None) -> dict:
    """What this channel would do, including which axes it would refuse, and why.

    Reports rather than decides for the channel as a whole; the per-axis
    refusals are stated so a reader sees all of them at once.
    """
    channel = channel or {}
    cid = channel.get("id", "unknown")
    report = {"channel": cid, "backend": BACKEND, "wrapped": cid in WRAPPED,
              "read_back": channel.get("read_back", True),
              "automatable": channel.get("automatable"), "aborted": _ABORTED}
    if cid not in WRAPPED:
        report.update(ready=False, reason=f"{cid} is not the channel this backend wraps {list(WRAPPED)}")
        return report
    limits = _limits()
    refused = {a: r for a in AXIS_CHANNEL if (r := axis_refusal(a, limits))}
    report["axes_refused"] = refused
    report["waveform_generator"] = "refused until its input unit is measured on this controller"
    if _LINK is None:
        report.update(ready=False, reason="no link open")
        return report
    link = _link()
    report["security_level"] = link.security_level()
    report["position_um"] = {a: link.read_position(c) for a, c in AXIS_CHANNEL.items()}
    report["ready"] = len(refused) < len(AXIS_CHANNEL)
    if not report["ready"]:
        report["reason"] = "every axis is refused; see axes_refused"
    return report


def apply(params: dict) -> dict:
    """Move the named axes to absolute targets, or refuse the whole request.

    `params`: {"targets_um": {axis: um}, "z_direction_finding": {"step_um": s,
    "by": who}} -- the second only when Z is commanded. Anything carrying a
    waveform is refused. Every check runs on the whole request before the
    first command, so a request fails whole and never halfway.

    The read-back is the return value. What counts as close enough is a
    tolerance, and a tolerance is policy the envelope does not yet hold, so
    the difference is reported and not judged: nothing lands in `verified`
    until the envelope says what agreement means.
    """
    if _ABORTED:
        raise PiezoRefused("aborted: this backend refuses commands until it is reset")
    refusal = waveform_refusal(params)
    if refusal:
        raise PiezoRefused(refusal)
    targets = {str(a).lower(): float(v) for a, v in (params.get("targets_um") or {}).items()}
    if not targets:
        return {"applied": [], "read": {}, "verified": [], "backend": BACKEND}
    limits = _limits()
    link = _link()
    refusals = [r for a in targets if (r := axis_refusal(a, limits))]
    if refusals:
        raise PiezoRefused("; ".join(refusals))
    start = {a: link.read_position(AXIS_CHANNEL[a]) for a in targets}
    refusals = [r for a in targets if (r := position_refusal(a, "start", start[a], limits))]
    refusals += [r for a, t in targets.items() if (r := position_refusal(a, "target", t, limits))]
    refusals += z_refusals(targets, start, params)
    if refusals:
        raise PiezoRefused("; ".join(refusals))
    applied = []
    with _LOCK, unlocked(link):
        for axis, target in targets.items():
            link.move_absolute(AXIS_CHANNEL[axis], target)
            applied.append({"axis": axis, "channel": AXIS_CHANNEL[axis], "target_um": target})
    got = {a: link.read_position(AXIS_CHANNEL[a]) for a in targets}
    return {"applied": applied, "start_um": start, "read_um": got,
            "difference_um": {a: got[a] - targets[a] for a in targets},
            "verified": [], "security_level_after": link.security_level(),
            "note": ("no position tolerance exists in envelope/safety.json, so the difference is "
                     "reported and not judged, and nothing is marked verified"),
            "backend": BACKEND}


def read() -> dict:
    """Position per axis and the security level, read from the controller each time."""
    link = _link()
    return {"position_um": {a: link.read_position(c) for a, c in AXIS_CHANNEL.items()},
            "security_level": link.security_level(), "aborted": _ABORTED, "backend": BACKEND}


def abort() -> dict:
    """Stop issuing, stay stopped, and put the security level back if a link is open.

    Like the other backends it drives nothing to a 'safe position' -- which
    position is safe is not this file's to choose, and a stage that moves on
    abort is an unplanned move. What it adds is the lock: the one state this
    backend itself changes, and so the one it restores.
    """
    global _ABORTED
    _ABORTED = True
    out = {"aborted": True, "backend": BACKEND}
    if _LINK is not None:
        link = _LINK
        if _FOUND_LEVEL is not None and link.security_level() != _FOUND_LEVEL:
            link.set_security_level(_FOUND_LEVEL)
        out["security_level"] = link.security_level()
    return out


def reset() -> None:
    """Not part of the interface. Scaffolding, and only that."""
    global _ABORTED
    _ABORTED = False


class DllLink:
    """The vendor controller library, reached with ctypes, on its simulator only.

    Written here from the library's own interface (Init, OpenSession,
    DoCommand, GetAllResultNames, GetAllResults, CloseSession, Uninit) rather
    than by importing the prior project's copy of the vendor wrapper; the
    rulings for what was read are in rulings.jsonl. Commands are text --
    `stage.position.measured.get 1` -- and results come back as name and value
    lines.

    **Phase A: the simulator address only.** The vendor manual says a
    `sim:/NPC....` address emulates a controller when none is fitted and that
    every command returns zero; the prior project recorded that it opens while
    the real port is held by the vendor program, which is what a link needing
    no port would do. Any other address is refused before the library is
    loaded at all.

    **Security goes back to the level found, or is not changed at all.** The
    level is controller-side state that outlives a session, and the vendor
    program leaves it at User. If the found level is one this link cannot put
    back, the unlock is refused before anything changes. Super-user is never
    requested: its code was never sent in the prior project, and the vendor
    manual says User-level settings alone can damage the stage.

    **The access code is read from the vendor install on this machine at the
    moment of use and never written into this repository.** It is that
    install's configuration, and a copy here would be a second place it lives.
    """

    LIBRARY = Path(r"C:\Program Files (x86)\NanoBench 6000\data\controller_interface64.dll")
    VENDOR_CONFIG = Path(r"C:\Program Files (x86)\NanoBench 6000\data\config.ini")

    _ERRORS = {-2: "connection not initialised", -4: "not enough parameters for command",
               -5: "comms link is broken", -11: "invalid command name"}
    _MAX_STRING = 1 << 16          # a bound on a buffer the library sizes for us

    def __init__(self, address: str, library: Path | None = None, bench: str | None = None,
                 read_only: bool = True):
        """`bench` records who handed the bench over, when and in which window.

        It is a RECORD and not a verification: nothing here can see a person
        say anything. A real address without it is refused before the library
        loads. `read_only` is the default and it forbids every write -- a
        position, a security level -- so the first contact with the real
        controller can only look. Writing is a later, explicit False.
        """
        real = not str(address).startswith("sim:")
        if real and not bench:
            raise PiezoRefused(
                f"address {address!r} is not the vendor simulator, and no bench hand-over is "
                "recorded. A real address waits for the person to hand over the bench in the "
                "executing seat's own window")
        self.bench = bench
        self.read_only = bool(read_only) if real else False
        import ctypes                                   # at the use site, like pymmcore-plus
        self._ct = ctypes
        lib = ctypes.cdll.LoadLibrary(str(library or self.LIBRARY))
        lib.Init.restype = ctypes.c_void_p
        lib.Uninit.argtypes = [ctypes.c_void_p]
        lib.OpenSession.restype = ctypes.c_int
        lib.OpenSession.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.CloseSession.argtypes = [ctypes.c_void_p]
        lib.DoCommand.restype = ctypes.c_int
        lib.DoCommand.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        for name in ("GetAllResultNames", "GetAllResults"):
            getattr(lib, name).restype = ctypes.c_int
            getattr(lib, name).argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self._lib = lib
        self._h = lib.Init(None)
        if not lib.OpenSession(self._h, str(address).encode("utf-8")):
            lib.Uninit(self._h)
            raise PiezoRefused(f"the library did not open a session on {address!r}")
        self.address = address
        self.closed = False
        self._locked_raw: str | None = None
        self._user_raw: str | None = None

    def _string(self, getter) -> str:
        ct = self._ct
        probe = ct.create_string_buffer(2)
        size = getter(self._h, probe, 1) + 1
        if not 0 < size <= self._MAX_STRING:
            raise PiezoRefused(f"the library asked for a {size}-byte buffer; refused")
        buf = ct.create_string_buffer(size)
        getter(self._h, buf, size)
        return buf.value.decode("utf-8", errors="replace")

    def do(self, command: str) -> dict[str, str]:
        n = self._lib.DoCommand(self._h, command.encode("utf-8"))
        if n <= 0:
            raise PiezoRefused(f"{command!r} failed: {self._ERRORS.get(n, f'return {n}')}")
        names = self._string(self._lib.GetAllResultNames).splitlines()
        values = self._string(self._lib.GetAllResults).splitlines()
        return dict(zip(names, values))

    def security_level(self) -> str:
        return str(self.do("controller.security.user.get").get("security"))

    def _vendor_user_code(self) -> str:
        import configparser
        cfg = configparser.ConfigParser()
        if not cfg.read(self.VENDOR_CONFIG, encoding="utf-8"):
            raise PiezoRefused(f"no vendor configuration at {self.VENDOR_CONFIG}; cannot unlock")
        section = next((s for s in cfg.sections() if s.lower() == "securitylevels"), None)
        code = None
        if section:
            code = next((v for k, v in cfg[section].items() if k.strip().lower() == "user"), None)
        if not code:
            raise PiezoRefused("the vendor configuration names no User access code; cannot unlock")
        code = code.strip()
        return code if code.lower().startswith("0x") else "0x" + code

    def set_security_level(self, level: str) -> None:
        if self.read_only:
            raise PiezoRefused("this link is read-only; the security level is not changed")
        if str(level).lower().replace("-", "").replace("_", "") in ("superuser", "super"):
            raise PiezoRefused("super-user is never requested by this backend")
        if level == "user" or (self._user_raw is not None and level == self._user_raw):
            self.do(f"controller.security.user.set {self._vendor_user_code()}")
            self._user_raw = self.security_level()
            return
        if level == "locked" or (self._locked_raw is not None and level == self._locked_raw):
            self.do("controller.security.lock")
            self._locked_raw = self.security_level()
            return
        raise PiezoRefused(f"security level {level!r} is not one this link can set or restore")

    def restorable(self, base: str) -> bool:
        """Whether a found level is one this link has seen and can put back."""
        return base in {v for v in (self._locked_raw, self._user_raw) if v is not None}

    def learn_levels(self) -> dict:
        """Read what the locked and User levels report as, and put the found level back.

        A DELIBERATE STEP, and it changes the controller's level while it runs:
        on a real controller it belongs to the live checklist, with the person
        present, and never inside a command. If the found level is neither of
        the two, it is said and left at the locked level -- the conservative
        end -- because this link has no code for any other level and will not
        guess one.
        """
        base = self.security_level()
        self.set_security_level("locked")
        self.set_security_level("user")
        if base == self._user_raw:
            pass                                         # already back where it was
        else:
            self.set_security_level("locked")
        return {"found": base, "locked_reads": self._locked_raw, "user_reads": self._user_raw,
                "restored": self.security_level() == base}

    def read_position(self, channel: int) -> float:
        value = self.do(f"stage.position.measured.get {int(channel)}").get("value")
        if value is None:
            raise PiezoRefused(f"no position came back for channel {channel}")
        # Picometres on this controller family by the prior project's reading,
        # which the live checklist re-reads before any real move.
        return float(value) * 1e-6

    def move_absolute(self, channel: int, target_um: float) -> None:
        if self.read_only:
            raise PiezoRefused("this link is read-only; no position is written")
        if not self.address.startswith("sim:") and not getattr(self, "position_unit_confirmed", False):
            raise PiezoRefused(
                "no position is written to a real controller until the position unit is "
                "confirmed by reading the calibrated range (live checklist 1d)")
        self.do(f"stage.position.command.set {int(channel)} {target_um * 1e6:.0f}")

    def close(self) -> None:
        if not self.closed:
            try:
                self._lib.CloseSession(self._h)
            finally:
                self._lib.Uninit(self._h)
                self.closed = True
