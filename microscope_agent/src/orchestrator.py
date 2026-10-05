"""The single entry point for everything that reaches the instrument (4.6.8).

Every command to a device passes through here. Device modules under devices/
know only themselves: each exposes preflight / apply / read / abort and nothing
else (4.6.5). Ordering, locking, synchronisation, timeouts and the abort
fan-out live in this one file, because an interlock scattered across twelve
device modules is not an interlock.

What this file does not do: decide whether a value is allowed. Limits are
policy and live in envelope/safety.json (4.3.2). This file enforces sequence,
not magnitude. A backend that judged its own parameters would put the envelope
in two places.

Parallelism here overlaps waiting -- lamp warm-up, stage travel, disk spin-up.
It is not a way to get timing precision. Anything needing tight coincidence is
bound by a hardware trigger, and software concurrency that pretends otherwise
produces quietly wrong data (4.6.8, 4.6.9).
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent
DEVICES = Path(__file__).resolve().parent / "devices"

# The device registry is knowledge and the librarian owns it (4.3.2), so its
# reading position moves as the librarian lands while its owner does not. The
# microscope reads the store directly only until then, which 4.3.0 allows and
# 11.1 records.
REGISTRY_LOOKUP = [
    AGENT / "envelope" / "snapshot.json",
    REPO / "librarian_agent" / "kb" / "exports" / "devices.json",
    REPO / "librarian_agent" / "kb" / "staging" / "devices.v0.json",
]


class InterlockError(RuntimeError):
    """Raised before anything moves.

    Every interlock in this file fails closed: an unverifiable state is not a
    state, and ambiguity stops rather than proceeds (2.1 rule 2).
    """


class GapError(InterlockError):
    """The registry does not answer a question an interlock has to ask.

    Distinct from a violated interlock: nothing is known to be wrong, and that
    is exactly the problem. Filling the gap with a guess is what P2 forbids.
    """


# --------------------------------------------------------------------------- #
# time base (4.6.9)
# --------------------------------------------------------------------------- #

SOFTWARE, DEVICE, TRIGGER = "software", "device", "trigger"


@dataclass
class Clock:
    """One t0 for every worker, so events from different channels sort.

    Software offsets carry OS scheduling jitter of milliseconds, so they order
    the log and nothing else. A number that physics depends on -- a lag between
    two frames, a correlation time -- has to come from a trigger counter or a
    device timestamp, and the log says which (check 37).
    """

    t0_wall: str
    t0_mono: float

    @classmethod
    def start(cls) -> "Clock":
        return cls(datetime.now(timezone.utc).isoformat(timespec="milliseconds"), time.monotonic())

    def offset(self) -> float:
        return round(time.monotonic() - self.t0_mono, 6)


# --------------------------------------------------------------------------- #
# what a channel is
# --------------------------------------------------------------------------- #


@dataclass
class Channel:
    """One control channel = one worker = one file under devices/ (4.6.8).

    The body drives ten elements over one SDK, so those ten serialise; two
    cameras are two channels and run in parallel. That is not an optimisation,
    it is what the hardware already does.
    """

    id: str
    automatable: str          # full | partial | none | unknown
    read_back: object         # True | False | "unknown"
    lock_group: str
    elements: dict[str, dict] = field(default_factory=dict)
    module_name: str = "mock"
    raw: dict = field(default_factory=dict)

    @property
    def verifiable(self) -> bool:
        """An automation that cannot be checked is not an automation (4.6.6-5)."""
        return self.read_back is True

    def element_ids(self) -> list[str]:
        """Every element this channel declares, by id."""
        return list(self.elements)

    def element_lock_group(self, element: str) -> str:
        """A lock group belongs to an element, not only to a channel.

        The body carries both: its optical elements lock with the path, while
        the motor stage locks with the piezo that rides on it.
        """
        return (self.elements.get(element) or {}).get("lock_group", self.lock_group)


def _rows_and_provenance(data: dict, source: Path) -> tuple[list, dict]:
    """The channel table, out of either shape the lookup can land on.

    Two files answer to "registry". The flat table the librarian stages is a
    JSON object with `channels[]` at the top level. This agent's
    envelope/snapshot.json is not that shape: it is a published export copied
    here (4.3.2), and it carries each table as the exact bytes under
    `tables.<name>.text` beside the sha256 that proves them. Bytes rather than
    a parsed object is the point -- a copy that had been re-serialised could
    not be read back against the commit it names -- so the snapshot has to be
    unwrapped before it looks like a registry.

    Until 2026-09-20 this function read `channels[]` and nothing else, while
    the snapshot sits FIRST in REGISTRY_LOOKUP. So the day the envelope gained
    a snapshot, every run raised GapError on the file that is supposed to be
    the normal source. It failed closed, which is the right direction and not
    a defence: what stopped was the normal path.
    """
    if isinstance(data.get("channels"), list):
        return data["channels"], {}
    table = ((data.get("tables") or {}).get("devices") or {})
    text = table.get("text")
    if text is None:
        raise GapError(f"{source} carries neither channels[] nor tables.devices")
    rows = json.loads(text).get("channels")
    if not isinstance(rows, list):
        raise GapError(f"{source} carries tables.devices and that table has no channels[]")
    return rows, {
        "kb_version": data.get("kb_version"),
        "built_from_commit": data.get("built_from_commit"),
        "table_from": table.get("from"),
    }


def _name_index(channels: dict[str, Channel]) -> dict[str, tuple[str, str | None]]:
    """Every name a plan may write, pointing at the channel that answers it.

    A plan names a channel OR an element: "set the dia lamp" is the true
    statement, and "set stand_ti2e" would lose which of that channel's ten
    elements was meant. Check 38 accepts both against this same table, so the
    two have to agree on what a name is -- this is built the way that check
    builds it, every channel id plus every elements[].id pointing at its
    channel.

    A name that means two things is not resolved by preferring one of them. It
    stops here, at load, before any command has been derived from it (2.1
    rule 2).
    """
    index: dict[str, tuple[str, str | None]] = {cid: (cid, None) for cid in channels}
    for channel in channels.values():
        for element_id in channel.elements:
            held = index.get(element_id)
            if held is not None:
                owner = held[0]
                was = "a channel" if held[1] is None else f"an element of {owner!r}"
                raise GapError(
                    f"the name {element_id!r} is an element of {channel.id!r} and also {was}. "
                    "An ambiguous name is not resolved by picking one of its meanings"
                )
            index[element_id] = (channel.id, element_id)
    return index


def load_registry(path: Path | None = None) -> tuple[dict[str, Channel], str, dict]:
    source = None
    if path is not None:
        source = path
    else:
        for candidate in REGISTRY_LOOKUP:
            if candidate.exists():
                source = candidate
                break
    if source is None:
        raise GapError(
            "no device registry found. Looked for " + ", ".join(str(p) for p in REGISTRY_LOOKUP)
        )
    data = json.loads(source.read_text())
    rows, provenance = _rows_and_provenance(data, source)

    channels: dict[str, Channel] = {}
    for row in rows:
        elements = {}
        for el in row.get("elements", []) or []:
            elements[el["id"]] = el
        channels[row["id"]] = Channel(
            id=row["id"],
            automatable=row.get("automatable", "unknown"),
            read_back=row.get("read_back", "unknown"),
            lock_group=row.get("lock_group", row["id"]),
            elements=elements,
            raw=row,
        )
    return channels, str(source.relative_to(REPO)), provenance


# --------------------------------------------------------------------------- #
# what a command is
# --------------------------------------------------------------------------- #


@dataclass
class Command:
    """One instruction to one channel, derived mechanically from a plan.

    `from_field` is the path in plan.json the parameters came from. The model
    does not compose commands (4.6.1); check 14 reads this field to prove it.
    """

    channel: str
    action: str
    params: dict = field(default_factory=dict)
    from_field: str = ""
    element: str | None = None
    raises_power: bool = False
    lowers_power: bool = False
    acquires: bool = False
    tier: int = 1

    def __post_init__(self) -> None:
        if not self.from_field:
            raise InterlockError(
                f"command {self.action!r} on {self.channel} has no `from`; "
                "every parameter is traceable to a plan field or it does not go out (4.6.1)"
            )


#: Card 040 item 4: the one device whose operation moves the software-motion
#: allow-list does not bind, and only on these axes. Z is absent on purpose:
#: objective_clearance_min binds piezo Z and nothing compares a Z target
#: against it at the moment of the move yet.
OPERATION_EXEMPT_DEVICE = "piezo_stage"
OPERATION_EXEMPT_AXES = ("x", "y")

#: Card 040 item 3 and plan.md 4.6.6 rule 5: the two channels with no read-back
#: that the PERSON named as exceptions, routed to their wrappers with
#: verification `none`. Named here rather than read from the registry because
#: the exception is the person's statement, not a property of the channel: any
#: other unreadable channel still goes to the manual sheet whatever its row says.
BLIND_BY_PERSONS_EXCEPTION = ("laser_combiner", "optical_tweezers")

#: Every light source on this instrument, DECLARED, for abort()'s power-down
#: step (card 054). The registry has no role field a program may read -- its
#: `role` is prose, and check 80 forbids deciding a role from how an
#: identifier is spelled -- so which elements emit is written here, one entry
#: per source, and abort() iterates this table rather than testing registry
#: ids against it. An emitter not in this table is not turned off; one found
#: is reported up, not added in passing.
#:
#: `channel` is the registry channel the write routes through. The pairing
#: Aura III = `widefield_source_a` comes from micromanager.py's header and card
#: 033, not from the registry, which leaves the branch assignment unconfirmed
#: (lapp_branch_assignment) -- so the Aura row may route through the channel
#: that is really the Spectra III's. On mock and through micromanager.apply
#: that changes no write (the `settings` name the device, Aura), only which
#: channel the row says.
#:
#: The Aura's off property is `State` = 0, its master switch. It was read off
#: the device: `getDevicePropertyNames("Aura")` as recorded in
#: runs/run-20260924-002/log.json (`light_engine_properties`) lists `State`
#: beside the per-line CYAN/GREEN/NIR/RED/UV switches, and session_033 turns
#: the light off with that same write. The per-line switches are left as they
#: are: the master is the one property that is off whatever the lines say.
#:
#: The three `software_commandable: False` rows exist to be READ. They write
#: nothing and claim nothing; their whole content is that a person turns them
#: off, and the abort record has to show it.
#: How abort() closes each shutter `shutters()` recognises, DECLARED per
#: element (card 056 part 1), because each backend takes a different command
#: and one shape sent to all of them was the defect: `{"element", "state"}`
#: is ignored by micromanager (`_settings()` reads only `settings`) and
#: refused by lunf, and the row said `closed: True` on the first anyway.
#:
#: Recognition is unchanged -- which rows exist is still `shutters()` and
#: replacing that is check 80's backlog. This table decides only what a row
#: SENDS and what it may CLAIM. A recognised shutter with no entry here is
#: not commanded and its row says so; nothing guesses a command for it.
#:
#: `verify` names the (device, property) whose read-back decides `closed`.
#: None means the backend reads nothing back, and then `closed` is None --
#: never True on a call returning.
SHUTTER_CLOSES: tuple[dict, ...] = (
    {"element": "laser_shutter", "commandable": True, "command": {"enable": []},
     "verify": None,
     "why": ("lunf `{\"enable\": []}` blanks every mapped line and is already permitted; lunf "
             "reads nothing back")},
    {"element": "csuw1_shutter", "commandable": False, "command": None, "verify": None,
     "why": ("CSUW1-Shutter is refused to software by name (NAMED_REFUSALS in micromanager.py). "
             "The person allowed an abort-only close of it on 2026-10-04, and it is not built: "
             "no closed value for it is recorded, so no call is sent")},
    # The two filter-turret shutters (card 056 part 2). They are not registry
    # elements, so `shutters()` never recognises them: they are DECLARED here
    # with the device they are and the channel the close routes through, and
    # abort() closes them FIRST, before the recognised ones, because
    # interlock 1 names them first. `abort_close` goes through
    # micromanager.close_for_abort, the only path the person opened; every
    # other path still refuses these devices by name.
    {"element": None, "device": "Turret1Shutter", "channel": "stand_ti2e", "commandable": True,
     "command": None, "abort_close": ("Turret1Shutter", "State", "0"),
     "verify": ("Turret1Shutter", "State"),
     "why": "the abort-only close the person allowed on 2026-10-04, State 0 being closed"},
    {"element": None, "device": "Turret2Shutter", "channel": "stand_ti2e", "commandable": True,
     "command": None, "abort_close": ("Turret2Shutter", "State", "0"),
     "verify": ("Turret2Shutter", "State"),
     "why": "the abort-only close the person allowed on 2026-10-04, State 0 being closed"},
)

LIGHT_SOURCES: tuple[dict, ...] = (
    {"source": "Aura III", "channel": "widefield_source_a", "device": "Aura",
     "property": "State", "off": "0", "software_commandable": True},
    {"source": "DiaLamp", "channel": "stand_ti2e", "device": "DiaLamp",
     "property": "State", "off": "0", "software_commandable": True},
    {"source": "optical tweezers", "channel": "optical_tweezers", "device": None,
     "property": None, "off": None, "software_commandable": False,
     "why": ("refused to software by policy, not by physics: LASER_ON stays refused and "
             "the laser's power dial is the person's; the TCP "
             "interface reads nothing back, so an off written there could not be confirmed")},
    {"source": "Spectra III (LightEngine)", "channel": "widefield_source_b", "device": None,
     "property": None, "off": None, "software_commandable": False,
     "why": ("refused to software by name (NAMED_REFUSALS in micromanager.py), a policy and "
             "not a physical inability, and card 054 does not lift "
             "that refusal")},
    {"source": "confocal laser lines", "channel": "laser_combiner", "device": None,
     "property": None, "off": None, "software_commandable": False,
     "why": ("refused to software by name (LUNF-Blanking in NAMED_REFUSALS), and not "
             "commanded by card 054: its fast cut-off is laser_shutter, which is in the "
             "shutter rows; the per-line power is not lowered here")},
)


def operation_exemptions(plan: dict | None, commands: list["Command"]) -> dict[int, str]:
    """Which commands the software-motion allow-list does not bind, from the PLAN's structure.

    Decided from the plan and the command's `from`, never from anything the
    command carries about itself: a flag on a command would be a claim the
    command makes, and this is a question about where the command came from.
    Exempt means ALL of: the plan has `operation`; `operation.device` is
    piezo_stage; the command's `from` is `operation.moves[<id>]` of a move in
    that plan; that move's axis is x or y; the command is on that device.
    Returns {index into commands: the plan field}, for logging.
    """
    op = (plan or {}).get("operation")
    if not isinstance(op, dict) or op.get("device") != OPERATION_EXEMPT_DEVICE:
        return {}
    moves = {m.get("id"): (i, m) for i, m in enumerate(op.get("moves") or []) if m.get("id")}
    out = {}
    for n, command in enumerate(commands):
        field_ = command.from_field
        if not (field_.startswith("operation.moves[") and field_.endswith("]")):
            continue
        mid = field_[len("operation.moves["):-1]
        if mid not in moves:
            continue
        index, move = moves[mid]
        if (move.get("axis") in OPERATION_EXEMPT_AXES
                and command.channel == OPERATION_EXEMPT_DEVICE):
            out[n] = f"operation.moves[{index}]"
    return out


#: Card 049 item 2: the second exemption, for an approved plan's trap steps.
TRAP_EXEMPT_DEVICE = "optical_tweezers"


def trap_step_exemptions(plan: dict | None, commands: list["Command"]) -> dict[int, str]:
    """Which commands are an approved plan's trap steps, from the PLAN's structure.

    The same shape as operation_exemptions: exempt means the plan has
    `trap_steps` on optical_tweezers, the command's `from` is
    `trap_steps.steps[<id>]` of a step in that plan, and the command is on that
    device. Nothing the command says about itself enters it.
    """
    ts = (plan or {}).get("trap_steps")
    if not isinstance(ts, dict) or ts.get("device") != TRAP_EXEMPT_DEVICE:
        return {}
    steps = {s.get("id"): i for i, s in enumerate(ts.get("steps") or []) if s.get("id")}
    out = {}
    for n, command in enumerate(commands):
        field_ = command.from_field
        if not (field_.startswith("trap_steps.steps[") and field_.endswith("]")):
            continue
        sid = field_[len("trap_steps.steps["):-1]
        if sid in steps and command.channel == TRAP_EXEMPT_DEVICE:
            out[n] = f"trap_steps.steps[{steps[sid]}]"
    return out


def from_operation_move(command: "Command") -> bool:
    return command.from_field.startswith("operation.moves[")


# --------------------------------------------------------------------------- #
# the focus search (card 055, plan.md 11-24)
# --------------------------------------------------------------------------- #

#: The third exemption, for an approved plan's focus search on the Z drive.
#: ZDrive stays refused by name everywhere else; nothing here lifts it.
FOCUS_EXEMPT_CHANNEL, FOCUS_EXEMPT_ELEMENT = "stand_ti2e", "z_drive"

#: What each branch does to Z, from the last ENCODER READ: +1 or -1 step_um.
#: The three branches absent here move nothing. The decider names a branch
#: and never a number; the target is derived here.
FOCUS_STEPS = {"step_up": +1, "step_down": -1}
FOCUS_NO_MOVE = ("in_focus", "no_sample_here", "unsure")

#: The only keys a decision may carry. A decision carrying anything else --
#: a target, a position, an offset -- is a decider supplying a number, which
#: the card refuses, so it is refused rather than ignored.
FOCUS_DECISION_KEYS = frozenset({"branch", "confidence", "note"})

#: Which reading of which device means PFS is NOT engaged, as (device,
#: property, value). PFS is in NAMED_REFUSALS, so software cannot switch it
#: off; the search reads it and refuses while it is engaged, and the person
#: switches it off. **Nothing on disk records the value**: no run has read a
#: PFS property, and the loaded configuration declares the device and no
#: values. A reading inferred from the property's name would be a spelling
#: deciding a safety guard (check 80), so until a person states it this stays
#: None and EVERY focus search refuses here. That is the correct default.
PFS_NOT_ENGAGED: tuple[str, str, str] | None = None


def focus_search_exemptions(plan: dict | None, commands: list["Command"]) -> dict[int, str]:
    """Which commands are candidates for the focus-search exemption, from the PLAN's structure.

    The shape of operation_exemptions and trap_step_exemptions: the plan has
    `focus_search` on stand_ti2e / z_drive, the command's `from` names a
    focus_search field, and the command is on that channel and element.
    Being a candidate grants nothing; `_focus_gate` decides.
    """
    fs = (plan or {}).get("focus_search")
    if not isinstance(fs, dict) or fs.get("channel") != FOCUS_EXEMPT_CHANNEL \
            or fs.get("element") != FOCUS_EXEMPT_ELEMENT:
        return {}
    return {n: c.from_field for n, c in enumerate(commands)
            if c.from_field.startswith("focus_search.")
            and c.channel == FOCUS_EXEMPT_CHANNEL and c.element == FOCUS_EXEMPT_ELEMENT}


def focus_limits(safety: dict, objective: str) -> dict:
    """The person's focus_z_<objective>_{min,max}, read fresh. A missing key refuses.

    `max` is the closest that lens may ever come to the coverslip, written by
    the person per lens (plan.md 11-24 at 250a138). Nothing derives it, and
    nothing here combines it with a coverslip position, a working distance or
    objective_clearance_min. A dry lens the person has released carries wide
    values and is never absent; an absent key is never read as unlimited.
    """
    limits: dict[str, dict] = {}
    for target in safety.get("targets") or []:
        limits.update({k: v for k, v in (target.get("limits") or {}).items()
                       if k.startswith("focus_z_")})
    out = {}
    for end in ("min", "max"):
        name = f"focus_z_{objective}_{end}"
        lim = limits.get(name)
        if not isinstance(lim, dict) or lim.get("value") is None or lim.get("unit") != "um":
            raise InterlockError(
                f"envelope/safety.json has no {name} in um. A missing focus limit refuses the "
                "search for every lens, dry or immersion; the person writes it")
        out[end] = float(lim["value"])
    if not out["min"] < out["max"]:
        raise InterlockError(f"focus_z_{objective}_min {out['min']} is not below _max {out['max']}")
    return out


_OPERATOR = None


def _operator():
    """operator.py, loaded by path at the moment of use, for its approval and point checks.

    One implementation of each: authorise() is the gate every plan meets, and
    check_operation_points() is card 040 item 1. Loaded lazily because
    operator.py loads this file, and by path because `operator` shadows the
    standard module (see operator.py's header).
    """
    global _OPERATOR
    if _OPERATOR is None:
        spec = importlib.util.spec_from_file_location(
            "_mic_operator_for_gate", Path(__file__).resolve().parent / "operator.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)                        # type: ignore[union-attr]
        _OPERATOR = module
    return _OPERATOR


class _StopChannel(threading.Thread):
    """A loopback socket for one run that accepts a stop and nothing else (card 057).

    Bound to 127.0.0.1 only, on a port the OS chooses, and announced only in
    the run's `run_started` line. Each connection is read to one message of
    at most STOP_MAX_BYTES (+1, so an oversized one is seen as oversized),
    judged by Orchestrator._stop_request, answered only if it was a valid
    stop, and closed. A valid stop calls the same abort() every other path
    calls, from this thread, so it does not wait for the run's next check.
    """

    def __init__(self, orchestrator, run_id: str) -> None:
        super().__init__(name=f"stop-channel:{run_id}", daemon=True)
        self._o = orchestrator
        self._closed = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(4)
        self._sock.settimeout(0.05)
        host, port = self._sock.getsockname()[:2]
        self._addr = {"host": host, "port": port}       # what the socket IS bound to

    def address(self) -> dict:
        return dict(self._addr)

    def run(self) -> None:
        while not self._closed.is_set():
            try:
                conn, _ = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            with conn:
                try:
                    conn.settimeout(2.0)
                    cap = self._o.STOP_MAX_BYTES + 1
                    raw = b""
                    while len(raw) < cap and b"\n" not in raw:
                        chunk = conn.recv(cap - len(raw))
                        if not chunk:
                            break
                        raw += chunk
                    if b"\n" in raw and len(raw) < cap:
                        # Anything after the first line makes it not one line;
                        # look briefly rather than wait for a close that may
                        # never come.
                        conn.settimeout(0.05)
                        try:
                            raw += conn.recv(cap - len(raw))
                        except (socket.timeout, OSError):
                            pass
                    reply = self._o._stop_request(raw)
                    if reply is not None:
                        conn.sendall(reply)
                except OSError as exc:
                    self._o.record(event="stop_refused", reason=f"connection failed: {exc}")

    def close(self) -> None:
        self._closed.set()
        try:
            self._sock.close()
        except OSError:
            pass
        if self.is_alive():
            self.join(2.0)


# --------------------------------------------------------------------------- #
# the orchestrator
# --------------------------------------------------------------------------- #


class Orchestrator:
    def __init__(self, registry_path: Path | None = None, backend: str = "mock") -> None:
        self.channels, self.registry_source, self.registry_provenance = load_registry(registry_path)
        self.names = _name_index(self.channels)
        self.backend = backend
        self.clock = Clock.start()
        self.log: list[dict] = []
        self._log_lock = threading.Lock()
        self._channel_locks = {cid: threading.Lock() for cid in self.channels}
        self._group_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._manual_open: dict[str, str] = {}      # lock_group -> sheet id
        # What preflight read back, kept so an interlock can ask whether a
        # write actually changes anything. It was discarded before, so the
        # turret check had no way to tell a rotation from a no-op.
        self._preflight_state: dict[str, dict] = {}
        # Elements this dispatch has commanded AND READ BACK. Membership is
        # what an interlock requires: a retract that was issued and not
        # verified is an assumption, and 2.1 says an unverified state does
        # not proceed.
        self._completed: set[str] = set()
        self._aborted = threading.Event()
        self._modules: dict[str, object] = {}
        # The person's hand-over statements, as answered in the seat's window.
        # The trap-step gate reads `objective` from here and nowhere else: the
        # tweezers' calibration belongs to one objective and nothing reads it.
        self.handover: dict = {}

    # -- logging ----------------------------------------------------------- #

    def record(self, **fields) -> dict:
        event = {"t_mono": self.clock.offset(), "time_base": SOFTWARE, **fields}
        with self._log_lock:
            self.log.append(event)
            # The same event, the same order, written as it happens (card
            # 057): under the log lock, so the file's order is the list's.
            if getattr(self, "_stream", None) is not None:
                self._stream_line(event)
        return event

    # -- the run a viewer can follow, and stop (card 057) -------------------- #

    #: The longest stop message accepted, in bytes. A stop is two short
    #: fields; anything longer is not a stop.
    STOP_MAX_BYTES = 1024

    def _stream_line(self, event: dict) -> None:
        """Append one line and flush. Never seeks, never truncates: append mode only."""
        self._stream.write(json.dumps(event, default=str) + "\n")
        self._stream.flush()

    def begin_run(self, folder: Path, run_id: str, plan_id, revision) -> dict:
        """Open runs/<run_id>/events.jsonl and the stop channel; announce both in one line.

        The first line is `run_started`, carrying the stop channel's address,
        which is written NOWHERE else. Events recorded before this call are
        written next, in order, so the file between its first and last line is
        always exactly `self.log`.
        """
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        self._stop_run_id = run_id
        self.stopped_from_outside = False
        self._stop = _StopChannel(self, run_id)
        addr = self._stop.address()
        with self._log_lock:
            self._stream = open(folder / "events.jsonl", "a", encoding="utf-8")
            self._stream_line({"event": "run_started", "run_id": run_id, "plan_id": plan_id,
                               "revision": revision, "t0_wall": self.clock.t0_wall,
                               "stop_channel": addr})
            for event in self.log:
                self._stream_line(event)
        self._stop.start()
        return addr

    def end_run(self, how: str, **detail) -> None:
        """Close the stop channel, then write `run_ended` as the last line and close the file.

        `how` is completed, aborted_by_monitor, stopped_from_outside or failed.
        The channel closes first, so nothing can be stopped once the run says
        it has ended.
        """
        stop = getattr(self, "_stop", None)
        if stop is not None:
            stop.close()
            self._stop = None
        with self._log_lock:
            if getattr(self, "_stream", None) is not None:
                self._stream_line({"event": "run_ended", "how": how,
                                   "t_mono": self.clock.offset(), **detail})
                self._stream.close()
                self._stream = None

    def stop_channel_address(self) -> dict | None:
        stop = getattr(self, "_stop", None)
        return None if stop is None else stop.address()

    def _stop_request(self, raw: bytes) -> bytes | None:
        """Judge one message on the stop channel. A reply for a valid stop, None for a refusal.

        One form only: one line of JSON, exactly {"stop": <this run>,
        "reason": <text>}. No status, no pause, nothing that sets a value,
        and nothing that names a file. A stop can only stop.
        """
        def refuse(why: str) -> None:
            self.record(event="stop_refused", reason=why, bytes=len(raw))
            return None

        if len(raw) > self.STOP_MAX_BYTES:
            return refuse(f"longer than {self.STOP_MAX_BYTES} bytes")
        text = raw.decode("utf-8", errors="replace")
        if text.endswith("\n"):
            text = text[:-1]
        if "\n" in text or "\r" in text:
            return refuse("not one line")
        try:
            message = json.loads(text)
        except ValueError:
            return refuse("not JSON")
        if not isinstance(message, dict) or set(message) != {"stop", "reason"}:
            return refuse("not exactly the keys stop and reason")
        if not isinstance(message["reason"], str):
            return refuse("reason is not text")
        if message["stop"] != self._stop_run_id:
            return refuse(f"names run {message['stop']!r}, not this run")
        self.stopped_from_outside = True
        self.record(event="stop_requested", reason=message["reason"])
        self.abort(reason=f"stop from outside the process: {message['reason']}")
        return b'{"abort": "begun"}\n'

    def log_header(self) -> dict:
        return {
            "t0_wall": self.clock.t0_wall,
            "t0_mono": self.clock.t0_mono,
            "backend": self.backend,
            "registry_source": self.registry_source,
            "time_base_note": (
                "software offsets order the log and nothing else. A value physics depends on "
                "comes from a trigger counter or a device timestamp (4.6.9)"
            ),
        }

    # -- device modules ----------------------------------------------------- #

    def driver_module(self, channel) -> str:
        """Which module drives this channel, resolved from the registry's `driver`.

        This was `dev_<channel_id>`, and devices/ holds manual.py,
        micromanager.py and mock.py -- so every channel asked for a filename
        that was never going to exist and card 012's work was complete and
        unreachable. Six channels name a Micro-Manager driver and one module
        wraps them.

        THE REGISTRY IS THE RIGHT SIDE TO ASK, which is card 012's own split:
        the backend knows how to address MMCore and the channel row knows
        what to address. Naming modules per channel would put ten files where
        one control path exists, and the duplication would be the thing that
        drifts.

        The driver column is prose in two rows -- "micromanager, device
        adapter MightexPolygon1000 ..." and "split: blanking and line select
        over DAQ, per-line power over SPI" -- so the head token is taken
        before any comma or space, and then `_`-separated prefixes are tried
        longest first: `micromanager_pvcam` finds micromanager.py that way.
        That is a declared chain and not a guess, and every step of it is
        recorded.

        NOTHING FALLS BACK TO MOCK. A real run that quietly became a mock run
        is the worst failure available here, and today's mock writes a log
        that looks exactly like a real one.

        Routing a channel to a module does not mean the module will drive it:
        micromanager.py carries its own WRAPPED tuple and refuses a channel
        it was never exercised on. That refusal is the module's to make.
        """
        driver = str(channel.raw.get("driver") or "")
        head = driver.split(",")[0].split(" ")[0].strip()
        tried = []
        candidate = head
        while candidate:
            tried.append(candidate)
            if (DEVICES / f"{candidate}.py").exists():
                self.record(event="driver_resolved", channel=channel.raw.get("id"),
                            driver=driver, module=candidate, tried=tried)
                return candidate
            if "_" not in candidate:
                break
            candidate = candidate.rsplit("_", 1)[0]
        raise GapError(
            f"channel {channel.raw.get('id')!r} declares driver {driver!r} and no module in "
            f"devices/ answers to it; tried {tried}. A channel with no module is not driven by "
            "guessing at one, and it is not quietly handed to the mock either"
        )

    def module_for(self, channel_id: str):
        """Which file drives this channel.

        A channel that cannot be read back is not automated, whatever its
        driver claims, so it goes to the instruction sheet (4.6.6 rules 2, 5).
        """
        channel = self.channels[channel_id]
        if self.backend == "mock":
            name = "mock"
        elif channel_id in BLIND_BY_PERSONS_EXCEPTION and channel.automatable != "none":
            # The person's named exception (card 040 item 3). verification_of
            # still answers `none` for these, because their rows say read_back
            # false -- routing to a wrapper does not make a blind channel see.
            name = self.driver_module(channel)
        elif channel.automatable == "none" or not channel.verifiable:
            name = "manual"
        else:
            name = self.driver_module(channel)
        return self._device_module(name, needed_by=f"channel {channel_id!r}")

    def _device_module(self, name: str, needed_by: str):
        """Load devices/<name>.py once, by path, and check it has the interface."""
        if name not in self._modules:
            path = DEVICES / f"{name}.py"
            if not path.exists():
                raise GapError(
                    f"{needed_by} needs devices/{name}.py, which does not exist. "
                    "A channel with no module is not driven by guessing at one"
                )
            spec = importlib.util.spec_from_file_location(f"_dev_{name}", path)
            module = importlib.util.module_from_spec(spec)
            # Registered before execution: a module loaded this way is absent from
            # sys.modules while its own body runs, and dataclasses resolves
            # annotations through sys.modules. A device module using one would
            # fail here for a reason that has nothing to do with the device.
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)                     # type: ignore[union-attr]
            missing = [f for f in ("preflight", "apply", "read", "abort") if not hasattr(module, f)]
            if missing:
                raise GapError(f"devices/{name}.py does not implement {missing} (4.6.5)")
            self._modules[name] = module
        return self._modules[name]

    # -- interlocks (2.1, 4.6.8) -------------------------------------------- #

    def check_software_motion(self, commands: list[Command]) -> None:
        """Refuse the WHOLE plan if any command reaches outside what software may command.

        Card 033: today the person moves the microscope by hand and software
        commands the excitation and the camera and nothing else. The list is
        micromanager.py's `SOFTWARE_MAY_COMMAND`, loaded here by path on every
        backend -- the one copy, so a plan refuses on mock exactly as it
        would on the instrument, and a plan refused here never reaches the
        call-level guard at all.

        It runs over every command BEFORE the first goes out, and before names
        are resolved against the registry: a plan that names `ZDrive` must fail
        as a plan that commands the focus drive, not as a name the registry
        does not know. Every refusal in the plan is collected, so a person
        reading it sees all of what is wrong at once rather than the first.

        What a command reaches is the name the plan wrote, the element if one
        was named, and every device under `params.settings`; the verb is also
        asked, because `setConfig` or `setPosition` moves things whatever the
        device.
        """
        mm = self._device_module("micromanager", needed_by="the software-motion check")
        refused = []
        for command in commands:
            reached = [command.channel]
            if command.element and command.element != command.channel:
                reached.append(command.element)
            settings = (command.params or {}).get("settings") or {}
            why = mm.refusal(None, None, command.action)
            if why:
                refused.append(f"{command.from_field}: {why}")
            for name in reached:
                why = mm.refusal(name, None, "setProperty")
                if why:
                    refused.append(f"{command.from_field}: {why}")
            for device, props in settings.items():
                for prop, value in (props or {}).items():
                    why = mm.refusal(str(device), str(prop), "setProperty", value)
                    if why:
                        refused.append(f"{command.from_field}: settings {device}.{prop}: {why}")
        if refused:
            self.record(event="software_motion_refused", commands=len(commands),
                        refusals=refused)
            raise InterlockError(
                f"refusing the whole plan before any command goes out: {len(refused)} "
                "refusal(s). " + " | ".join(refused))
        self.record(event="software_motion_checked", commands=len(commands),
                    allowed=sorted(mm.SOFTWARE_MAY_COMMAND))

    def shutters(self) -> list[tuple[str, str]]:
        """Every shutter the registry knows, as (channel, element).

        Interlock 1 closes these before any power comes down, because a shutter
        beats a ramp. The list is read from the registry rather than written
        here: a shutter this file believes in but the instrument does not have
        is worse than no list at all.
        """
        found = []
        for channel in self.channels.values():
            for element_id in channel.elements:
                if "shutter" in element_id:
                    found.append((channel.id, element_id))
        return found

    def check_manual_lockout(self, command: Command) -> None:
        """No automatic command to a group while a person has their hands in it.

        The software half of lockout/tagout (2.1 rule 5). The sheet is closed by
        a human confirmation, never by a timeout.
        """
        group = self.channels[command.channel].element_lock_group(command.element or "")
        sheet = self._manual_open.get(group)
        if sheet is not None:
            raise InterlockError(
                f"manual sheet {sheet!r} is open on lock group {group!r}; "
                f"no automatic command goes to it until a person closes the sheet (2.1 rule 5)"
            )

    def open_manual_sheet(self, lock_group: str, sheet_id: str) -> None:
        self._manual_open[lock_group] = sheet_id
        self.record(event="manual_sheet_opened", lock_group=lock_group, sheet=sheet_id)

    def close_manual_sheet(self, lock_group: str, confirmed_by: str) -> None:
        sheet = self._manual_open.pop(lock_group, None)
        self.record(event="manual_sheet_closed", lock_group=lock_group, sheet=sheet,
                    confirmed_by=confirmed_by)

    # A turret rotation is a collision hazard and the plan must clear it first
    # (2.1, microscope_agent/CLAUDE.md). Two things have to have happened:
    # focus stabilisation off, and the objective retracted AND VERIFIED.
    #
    # The retract element is looked up rather than named, so the day the
    # registry gains a focus drive this interlock starts passing on its own.
    # Today it finds none: stand_ti2e's `role` says the body carries "objective
    # and filter turrets, output port, intermediate magnification, FOCUS,
    # transmitted lamp" and its nine elements are nosepiece, filter_turret_1,
    # filter_turret_2, light_path_port, intermediate_magnification, pfs,
    # dia_lamp, lapp_branch, motor_stage. The channel row names focus and the
    # element list has no such row, so a plan has nothing to name.
    # THERE IS A SECOND COPY OF BOTH OF THESE, in plan_card.py: the same five
    # hints written inline at its `retract = next(...)`, in a different order,
    # and `"pfs" in elements` twice. Nothing compares the two, so the first
    # edit to either is silent drift -- and the edit is coming. When the
    # element row gains a `role` field, migrating only this file leaves the
    # planner guessing, and the plan then names an element the interlock
    # approves on different grounds.
    #
    # They are NOT unified by importing one from the other: that would make
    # the wrong thing shared instead of removing it. Both die with `role`,
    # and this comment dies with them. A comment is a poor guard; it is the
    # honest one here, because nothing at commit time can compare two
    # literals in two files.
    #
    # AND THE TWO DO NOT SELECT ALIKE. `retract_elements()` returns sorted()
    # of EVERY match; the planner's `next(...)` returns the FIRST in its own
    # order. With z_drive and focus both present the planner picks one and
    # this sees two. One element matches today, so the difference is
    # invisible rather than absent.
    RETRACT_HINTS = ("focus", "z_drive", "z_axis", "objective_z", "z")
    STABILISER = "pfs"

    def retract_elements(self) -> list[str]:
        """Every element in the registry that could perform an objective retract."""
        return sorted(
            e for channel in self.channels.values()
            for e in channel.element_ids()
            if e in self.RETRACT_HINTS or e.startswith("focus") or e.endswith("_focus")
        )

    def check_turret_rotation_allowed(self, command: Command) -> None:
        """No nosepiece write until the objective is clear of the sample.

        `nosepiece_write_runs_no_escape` (E3): the stand runs its own escape
        when a person rotates at the stand or in NIS, and runs NONE for a
        Micro-Manager write -- Z does not move, so the incoming objective
        arrives at whatever height the outgoing one was left at, against a
        working distance of 0.13 mm at 100x oil. CLAUDE.md says the retract
        is a step a plan ISSUES AND VERIFIES and not a property it may
        assume; nothing was enforcing that.

        A WRITE IS TREATED AS A ROTATION UNLESS THE READ-BACK PROVES
        OTHERWISE. The commanded position may equal the seated one, in which
        case nothing turns -- but that is a fact about the instrument, not
        about the plan, and only preflight can supply it. When preflight
        returned no position the operator does not know, and 2.1 rule 2 makes
        not-knowing stop rather than proceed. The mock returns none, so on
        mock this always refuses, which is the correct thing for a mock to
        do about a hazard it cannot model.
        """
        element = command.element or command.channel
        if element != "nosepiece":
            return

        state = self._preflight_state.get(command.channel) or {}
        seated = state.get("nosepiece")
        commanded = next((p.get("value") for p in command.params.values()), None)
        if seated is not None and commanded is not None and seated == commanded:
            self.record(event="turret_no_rotation", channel=command.channel,
                        element=element, seated=seated, commanded=commanded,
                        note="the commanded position is the seated one, so nothing rotates")
            return

        done = self._completed
        missing = []
        if self.STABILISER not in done:
            missing.append(
                f"{self.STABILISER} is not disabled. PFS is a collision device alongside the Z "
                "drive and the nosepiece, and 2.1 requires it off across a turret change and "
                "re-acquired after. The element exists and reads back, so a plan can issue this")
        retracts = self.retract_elements()
        if not retracts:
            # WHAT IT SEARCHED FOR, NOT ONLY THAT IT FOUND NOTHING. This used
            # to assert "No element in the device registry drives focus ...
            # the registry is the librarian's", and that sentence is a
            # CONCLUSION drawn from an empty match. When a row exists under a
            # spelling the predicate misses -- `ZDrive`, `z_stage`,
            # `nosepiece_z` all miss, measured -- every clause of it is false
            # and it reads as true, sending the reader to the seat that
            # already did the work. The row for this instrument arrived as
            # `z_drive` and matched; that was luck, not a property of the
            # lookup.
            #
            # So the message states the predicate and the ids it walked past,
            # and draws no conclusion about whose the problem is. A reader can
            # then tell `the row is missing` from `the row is there under a
            # name I do not recognise` from the refusal alone.
            walked = sorted(e for channel in self.channels.values()
                            for e in channel.element_ids())
            missing.append(
                "the objective is not retracted, and no element was recognised as the one that "
                f"retracts it. SEARCHED FOR: an id in {list(self.RETRACT_HINTS)}, or one "
                "starting `focus` or ending `_focus`. WALKED PAST these "
                f"{len(walked)} element ids: {', '.join(walked)}. Two different situations end "
                "here and this message cannot tell them apart for you: the registry may carry "
                "no focus element at all, which is the librarian's and not fixable in this "
                "agent -- or it may carry one under a spelling this predicate misses, which is "
                "ours. Compare the list against the names above before deciding whose it is. "
                "The predicate is a tuple in orchestrator.py, which is a rule about a device's "
                "role stated where the registry cannot see it; the fix is a field on the "
                "element row saying it drives objective Z, and then the tuple is deleted "
                "rather than widened")
        elif not (set(retracts) & done):
            missing.append(
                f"the objective is not retracted; {' or '.join(retracts)} must be commanded and "
                "VERIFIED before this write. A retract that was issued and not read back is an "
                "assumption, and stand_ti2e reads back, so here there is no excuse for one")

        if missing:
            raise InterlockError(
                "refusing to rotate the nosepiece"
                + (f" from {seated!r} to {commanded!r}" if seated is not None
                   else f" to {commanded!r}, and preflight returned no seated position, so "
                        "whether this rotates at all is unknown")
                + ". The stand runs no escape on a Micro-Manager write, so the incoming "
                  "objective arrives at the outgoing one's height. "
                + " ALSO: ".join(missing)
            )

    def check_acquisition_allowed(self, command: Command) -> None:
        """Nothing acquires while the optical path is being switched (4.6.8-4)."""
        if not command.acquires:
            return
        if self._group_locks["optical_path"].locked():
            raise InterlockError(
                "the optical path lock is held; no detector starts an acquisition during a switch"
            )

    # -- ordering (2.1 rule 4) ---------------------------------------------- #

    @staticmethod
    def order(commands: list[Command]) -> list[Command]:
        """Power down first, power up last, everything else in between.

        The rule is asymmetric on purpose: raising output is the last thing that
        happens and lowering it is the first, so an abort that stops halfway has
        stopped on the safe side.
        """
        def rank(c: Command) -> int:
            if c.lowers_power:
                return 0
            if c.raises_power:
                return 2
            return 1
        return sorted(commands, key=rank)

    # -- running ------------------------------------------------------------ #

    def resolve(self, name: str) -> tuple[str, str | None]:
        """A name the plan wrote -> the channel that answers it, and the element if it named one.

        Resolving element to channel is this layer's job (4.6.7). Until
        2026-09-20 it was nobody's: preflight looked names up in
        self.channels only, so a plan naming `dia_lamp` or `nosepiece` --
        which check 38 accepts against the same table -- raised GapError on a
        perfectly good card.

        A name in neither is still a GapError and stays one. The gap that was
        closed is the one between two correct tables, not the one between a
        card and the instrument.
        """
        try:
            return self.names[name]
        except KeyError:
            raise GapError(
                f"the plan names {name!r}, which is neither a channel nor an element in "
                f"{self.registry_source}"
            ) from None

    def preflight(self, names: list[str]) -> list[dict]:
        """Ask every channel the plan reaches for its state before anything moves (O1).

        Takes the names the plan wrote, channels or elements, and asks the
        channel behind each. Two names on one channel ask it once: the
        question is about the channel, and asking twice would put two answers
        for one state into the log.

        One failure stops the run here, with the instrument untouched.
        """
        results = []
        reached: dict[str, list[str]] = {}
        for name in names:
            cid, element = self.resolve(name)
            named_as = reached.setdefault(cid, [])
            if element is not None and element not in named_as:
                named_as.append(element)
        for cid, named_as in reached.items():
            channel = self.channels[cid]
            module = self.module_for(cid)
            state = module.preflight(channel.raw)
            verified = channel.verifiable and state.get("read_back") is not False
            self._preflight_state[cid] = state
            results.append({"channel": cid, "named_as": named_as, "state": state,
                            "verified": verified})
            self.record(event="preflight", channel=cid, named_as=named_as,
                        verified=verified, state=state)
            if not verified:
                self.record(event="preflight_unverified", channel=cid,
                            note="state cannot be read back; this channel goes to a manual sheet")
        return results

    def verification_of(self, channel_id: str, returned: object) -> tuple[str, str]:
        """Did anything query this channel after the command and see what was commanded?

        4.6.6.1 rule 3, and check 66 reads the answer off the log. Three
        things are being kept apart:

          - the channel cannot report at all. `laser_combiner` and
            `optical_tweezers` are the pair that rule was written about
          - the backend answered the write and nothing was queried after it.
            **A return code is not a read-back**: on the Tweez 300 a zero
            means the GUI accepted the text, and six distinct ways a command
            can be ignored all return zero (tweez300_reports_nothing_back, E3)
          - the state was queried after the write and matched what was sent

        Only the third is `readback`. Everything else is `none`, which is a
        statement rather than a silence -- 2.1 rule 8, no signal does not
        permit, and check 66 fails an absent field harder than a `none`.

        A DISAGREEMENT IS ALSO `none`, and is the loudest of them: the query
        happened and the answer was no. It reads the backend's own report
        rather than calling read() again here, because the backend that can
        tell the difference is the one that already queried -- a second read
        one step later answers a different question, about a state that has
        had time to change.
        """
        channel = self.channels[channel_id]
        if channel.read_back is not True:
            return "none", (f"the channel table marks {channel_id} read_back "
                            f"{channel.read_back!r}, so there is nothing to query")
        if not isinstance(returned, dict) or "verified" not in returned:
            return "none", ("the backend reported no read-back. What came back is the write's "
                            "own return value, which says the command was accepted and not "
                            "that the state holds")
        disagreed = returned.get("disagreed") or []
        if disagreed:
            return "none", (f"{len(disagreed)} setting(s) read back different from what was "
                            f"commanded")
        verified = returned.get("verified") or []
        if not verified:
            return "none", "the backend was given no setting to verify, so it read nothing back"
        return "readback", f"{len(verified)} setting(s) queried after the write and matched"

    def _resolved(self, command: Command) -> Command:
        """The same command, addressed to a channel instead of to whatever the plan named.

        `channel` after this is always a channel id, because the locks, the
        workers and the device modules are all per channel. `element` keeps
        what the plan named, because a lock group can belong to the element
        rather than to the channel -- the body's optics lock with the path
        while its motor stage locks with the piezo that rides on it.
        """
        cid, element = self.resolve(command.channel)
        if cid == command.channel and element is None:
            return command
        return replace(command, channel=cid, element=command.element or element)

    def check_software_motion_for(self, plan: dict | None, commands: list[Command]) -> None:
        """check_software_motion over every command card 040 item 4 does not exempt.

        The check itself is unchanged; what changes is what it is applied to,
        and only for a plan whose structure qualifies. Each exemption is its
        own event naming the plan field, so the log shows where the allow-list
        did not bind and why. What replaces it for those commands is the
        derived-point envelope check the operator runs before dispatch.
        """
        exempt = operation_exemptions(plan, commands)
        if exempt:
            exempt = self._operation_gate(plan, commands, exempt)
        for n, plan_field in sorted(exempt.items()):
            self.record(event="software_motion_exempt", plan_field=plan_field,
                        channel=commands[n].channel, action=commands[n].action,
                        reason=("card 040 item 4: an operation move of piezo_stage on x or y; the "
                                "derived-point envelope check binds it instead of the allow-list"))
        traps = trap_step_exemptions(plan, commands)
        if traps:
            traps = self._trap_gate(plan, commands, traps)
        for n, plan_field in sorted(traps.items()):
            self.record(event="software_motion_exempt", plan_field=plan_field,
                        channel=commands[n].channel, action=commands[n].action,
                        verification="none",
                        reason=("card 049 item 2: a trap step of an approved plan on "
                                "optical_tweezers; the derived position, strength and step checks "
                                "against the envelope bind it instead of the allow-list. The "
                                "channel is blind: nothing it returns is a verification"))
        focus = focus_search_exemptions(plan, commands)
        if focus:
            focus = self._focus_gate(plan, commands, focus)
        for n, plan_field in sorted(focus.items()):
            self.record(event="software_motion_exempt", plan_field=plan_field,
                        channel=commands[n].channel, action=commands[n].action,
                        reason=("card 055: a focus-search move of an approved plan, equal to "
                                "what the plan, the last encoder read and the decided branch "
                                "derive; the range, the person's limits and the live clearance "
                                "comparison bind it instead of the allow-list"))
        exempt = {**exempt, **traps, **focus}
        self.check_software_motion([c for n, c in enumerate(commands) if n not in exempt])

    def _focus_gate(self, plan: dict, commands: list[Command],
                    candidates: dict[int, str]) -> dict[int, str]:
        """The focus-search exemption's conditions, checked in the call that grants it.

        (a) a plan_approval covers this revision, or nothing is exempt; (b)
        each candidate equals the ONE command the running search derived for
        this step -- from the plan, the last encoder read and the branch, all
        held here and none taken from the command. A command built anywhere
        else, or a second command riding the first, is not exempt and meets
        the allow-list, which refuses ZDrive.
        """
        decision = _operator().authorise(plan)
        if not decision.permitted:
            self.record(event="software_motion_exemption_refused",
                        reason="no approval covers this plan revision: " + "; ".join(decision.reasons))
            return {}
        expected = getattr(self, "_focus_expected", None)
        kept = {}
        for n, plan_field in candidates.items():
            c = commands[n]
            if expected is None or (c.channel, c.element, c.action, c.params, c.from_field) != (
                    expected.channel, expected.element, expected.action, expected.params,
                    expected.from_field):
                self.record(event="software_motion_exemption_refused", plan_field=plan_field,
                            reason=("the command is not what the running focus search derived "
                                    "for this step"))
                continue
            kept[n] = plan_field
        return kept

    def run_focus_search(self, plan: dict, decide, load_safety=None) -> dict:
        """Walk Z from the retract, one decided branch at a time, refusing at every gate.

        `decide(last_read_um)` returns `{"branch", "confidence"}` and nothing
        else; it never supplies a number. Every target is derived here from
        the plan and the last ENCODER READ, sent ABSOLUTE, and read back. The
        envelope is re-read at every step through `load_safety`, so a limit
        the person changes or removes mid-search binds the next step.

        Returns {"outcome": found | not_found | no_sample_here | unsure,
        "z_um": the last encoder read, "moves": n}. Any refusal raises
        InterlockError after recording it; nothing moves after a refusal.
        """
        load_safety = load_safety or _operator().load_safety
        try:
            return self._focus_search(plan, decide, load_safety)
        except InterlockError as exc:
            self.record(event="focus_search_refused", reason=str(exc))
            raise
        finally:
            self._focus_expected = None

    def _focus_search(self, plan: dict, decide, load_safety) -> dict:
        fs = plan.get("focus_search")
        if not isinstance(fs, dict) or fs.get("channel") != FOCUS_EXEMPT_CHANNEL \
                or fs.get("element") != FOCUS_EXEMPT_ELEMENT:
            raise InterlockError("the plan carries no focus_search on stand_ti2e / z_drive")
        actions = {a.get("id"): a for a in plan.get("actions") or []}
        action = actions.get(fs.get("action"))
        if not action or action.get("device") != FOCUS_EXEMPT_CHANNEL \
                or action.get("reversible") is not True:
            raise InterlockError(f"focus_search.action {fs.get('action')!r} is not a reversible "
                                 "action on stand_ti2e in this plan")

        # -- before the first Z command ------------------------------------ #
        objective = self.handover.get("objective")
        if not objective:
            raise InterlockError("no objective stated at hand-over; a focus search waits for the "
                                 "person to say which lens is in place, and nothing fills it in")
        if objective != fs.get("objective"):
            raise InterlockError(f"the plan's focus search is for {fs.get('objective')!r} and the "
                                 f"person states {objective!r} is in place")
        limits = focus_limits(load_safety(), objective)
        rng = fs.get("range_um") or {}
        lo, hi = float(rng.get("min")), float(rng.get("max"))
        if not (lo < hi and limits["min"] <= lo and hi <= limits["max"]):
            raise InterlockError(f"range_um {lo} to {hi} is not a range inside the person's "
                                 f"focus_z_{objective} limits {limits['min']} to {limits['max']}")
        if not any(c.get("target") == "position_readback_error"
                   or c.get("metric") == "position_readback_error"
                   for c in plan.get("stop_criteria") or []):
            raise InterlockError("the plan has no stop criterion on position_readback_error, so "
                                 "\"read back within tolerance\" would mean nothing")
        try:
            tolerance = float(_operator().readback_tolerance(plan)["value"])
        except Exception as exc:                                # noqa: BLE001 - a refusal either way
            raise InterlockError(f"no read-back tolerance: {exc}") from exc
        module = self.module_for(FOCUS_EXEMPT_CHANNEL)
        if PFS_NOT_ENGAGED is None:
            raise InterlockError(
                "which PFS reading means not engaged is recorded nowhere, so PFS cannot be "
                "confirmed off and the search refuses. PFS is refused to software; a person "
                "switches it off and states the reading that shows it")
        device, prop, off = PFS_NOT_ENGAGED
        reading = module.read_property(device, prop)
        self.record(event="focus_search_pfs_read", device=device, property=prop,
                    read=reading, required=off)
        if reading is None or str(reading) != off:
            raise InterlockError(f"PFS reads {device}.{prop} = {reading!r}, not {off!r}: it may "
                                 "be engaged, and a held focus fights a sweep. The person "
                                 "switches PFS off")

        step = float(fs["step_um"])
        max_moves = int(fs["max_moves"])
        branches = list(fs.get("branches") or [])

        # -- the retract: the search never starts from wherever Z was left -- #
        last = self._focus_move(plan, fs, objective, load_safety, tolerance,
                                target=lo, from_field="focus_search.range_um.min",
                                branch="retract")
        self._completed.add(FOCUS_EXEMPT_ELEMENT)
        moves = 0
        while True:
            decision = decide(last)
            if not isinstance(decision, dict):
                raise InterlockError(f"the decider returned {decision!r}, not a decision")
            extra = sorted(set(decision) - FOCUS_DECISION_KEYS)
            branch = decision.get("branch")
            self.record(event="focus_search_decision", branch=branch,
                        confidence=decision.get("confidence"), last_read_um=last,
                        abstention=branch == "unsure", extra_keys=extra)
            if extra:
                raise InterlockError(f"the decision carries {extra}; the decider names a branch "
                                     "and never a number, and the target is derived here")
            if branch not in branches:
                raise InterlockError(f"branch {branch!r} is not in this plan's branches {branches}")
            if branch in FOCUS_NO_MOVE:
                outcome = {"in_focus": "found", "no_sample_here": "no_sample_here",
                           "unsure": "unsure"}[branch]
                break
            if moves >= max_moves:
                outcome = "not_found"
                break
            target = last + FOCUS_STEPS[branch] * step
            last = self._focus_move(plan, fs, objective, load_safety, tolerance,
                                    target=target, from_field=f"focus_search.{branch}",
                                    branch=branch)
            moves += 1
        result = {"outcome": outcome, "z_um": last, "moves": moves,
                  "note": ("z_um is the encoder read after the last move; for found it is the Z "
                           "found, and never a number the decider gave")}
        self.record(event="focus_search_end", **result)
        return result

    def _focus_move(self, plan: dict, fs: dict, objective: str, load_safety, tolerance: float,
                    target: float, from_field: str, branch: str) -> float:
        """One derived Z move: every check before it goes out, the encoder read after.

        The order is the card's: the live clearance comparison against the
        person's focus_z_<objective>_max, re-read now and recorded whether or
        not it can be made; then range_um and the person's whole range; then
        the exemption, which compares this exact command against what was
        derived; then the move; then the read-back against the tolerance.
        """
        command = Command(channel=FOCUS_EXEMPT_CHANNEL, element=FOCUS_EXEMPT_ELEMENT,
                          action="focus_z_move", params={"target_um": target},
                          from_field=from_field)
        self.record(event="focus_search_command", branch=branch, target_um=target,
                    **{"from": from_field})
        try:
            limits = focus_limits(load_safety(), objective)
        except InterlockError:
            self.record(event="focus_clearance_compared", target=target, limit=None,
                        compared=False, within=None,
                        note=f"focus_z_{objective}_max is absent now, so nothing was compared")
            raise
        within = target <= limits["max"]
        self.record(event="focus_clearance_compared", target=target, limit=limits["max"],
                    compared=True, within=within)
        if not within:
            raise InterlockError(f"{from_field}: target {target} um is above "
                                 f"focus_z_{objective}_max {limits['max']} um, the closest the "
                                 "person allows this lens to the coverslip")
        rng = fs["range_um"]
        if not (float(rng["min"]) <= target <= float(rng["max"])):
            raise InterlockError(f"{from_field}: target {target} um is outside range_um "
                                 f"{rng['min']} to {rng['max']}")
        if not limits["min"] <= target:
            raise InterlockError(f"{from_field}: target {target} um is below "
                                 f"focus_z_{objective}_min {limits['min']}")
        self._focus_expected = command
        self.check_software_motion_for(plan, [command])
        returned = self.module_for(FOCUS_EXEMPT_CHANNEL).focus_z_move(target)
        self._focus_expected = None
        read = returned.get("read_um") if isinstance(returned, dict) else None
        ok = read is not None and abs(float(read) - target) <= tolerance
        self.record(event="focus_search_readback", branch=branch, target_um=target,
                    read_um=read, tolerance_um=tolerance, within=ok,
                    verification="readback" if ok else "none", **{"from": from_field})
        if not ok:
            self._aborted.set()
            self.record(event="stop_criterion_violated", criterion="position_readback_error",
                        plan_field=from_field, target_um=target, read_um=read,
                        tolerance_um=tolerance)
            raise InterlockError(f"{from_field}: the encoder reads {read} um after a move to "
                                 f"{target} um, outside {tolerance} um; the search stops before "
                                 "the next move")
        return float(read)

    def _trap_gate(self, plan: dict, commands: list[Command],
                   candidates: dict[int, str]) -> dict[int, str]:
        """The trap-step exemption's conditions, checked in the call that grants it.

        Built exactly like _operation_gate: (a) a plan_approval covers this
        revision and hash, or nothing is exempt; (b) each candidate is exactly
        what the approved plan derives for that step, so a hand-built command
        cannot ride it; (c) every derived position, strength and step is
        checked against the envelope, a missing limit or a limit for another
        objective refusing the whole plan here.
        """
        op = _operator()
        decision = op.authorise(plan)
        if not decision.permitted:
            self.record(event="software_motion_exemption_refused",
                        reason="no approval covers this plan revision: " + "; ".join(decision.reasons))
            return {}
        # THE GUI'S MICROMETRES ARE A CALIBRATION NOBODY READS. On
        # run-20260925-008 a trap commanded to +6 um was reported by the person
        # at 2 um, so every um sent -- and the person's limits, in the same
        # unit -- may mean a third of what it says. No position goes out until
        # the person has stated the GUI's calibration for the objective in
        # place. Nothing here rescales to compensate: a factor in code is a
        # limit nobody wrote, and the remedy is the person re-calibrating in the GUI.
        cal = self.handover.get("tweezers_calibration") or {}
        positions = [c for c in op.derive_trap_steps(plan)
                     if any(l[0] == "TRAP_POSITION" for l in c.params["commands"])]
        if positions and not (cal.get("stated_by") and cal.get("pixel_to_um")
                              and cal.get("objective") == self.handover.get("objective")):
            self.record(event="software_motion_exemption_refused",
                        reason="the tweezers' calibration for the objective in place is not stated")
            raise InterlockError(
                "refusing every trap position: the person has not stated the Tweez300's "
                "pixel-to-um calibration for the objective in place "
                f"({self.handover.get('objective')!r}); stated: {cal or 'nothing'}. The GUI's um "
                "are its own calibration, which nothing reads, and a stale one moves every trap "
                "by a factor nobody wrote")
        derived = {c.from_field: c for c in op.derive_trap_steps(plan)}
        kept = {}
        for n, plan_field in candidates.items():
            c = commands[n]
            d = derived.get(c.from_field)
            if d is None or d.params != c.params or d.channel != c.channel or d.action != c.action:
                self.record(event="software_motion_exemption_refused", plan_field=plan_field,
                            reason="the command is not what the approved plan derives for this step")
                continue
            kept[n] = plan_field
        if kept:
            # Every derived step, not only the kept ones: a step's size is
            # measured from the same trap's previous position in the plan.
            for comparison in op.check_trap_steps(plan, list(derived.values()), op.load_safety(),
                                                  self.handover.get("objective")):
                self.record(event="trap_step_checked", **comparison)
        return kept

    def _operation_gate(self, plan: dict, commands: list[Command],
                        candidates: dict[int, str]) -> dict[int, str]:
        """The three things an exemption stands on, checked in the call that grants it.

        Architecture's conditions on card 040 item 4 (9ac69dc): (a) the plan's
        REVISION carries the person's approval -- `operation` present is not
        enough, anyone can write that; (b) the derived-point envelope check is
        on this path and nothing can skip it. And one this seat adds, so a
        hand-built command cannot ride an approved plan: each candidate must be
        exactly what the plan derives for that move.

        No approval, or a command that is not the derivation: the candidate is
        not exempt, and meets the allow-list like anything else -- which
        refuses piezo_stage. A derived point outside the envelope: Refusal of
        the whole plan, raised here.
        """
        op = _operator()
        decision = op.authorise(plan)
        if not decision.permitted:
            self.record(event="software_motion_exemption_refused",
                        reason="no approval covers this plan revision: " + "; ".join(decision.reasons))
            return {}
        derived = {c.from_field: c for c in op.derive_operation(plan)}
        kept = {}
        for n, plan_field in candidates.items():
            c = commands[n]
            d = derived.get(c.from_field)
            if d is None or d.params != c.params or d.channel != c.channel or d.action != c.action:
                self.record(event="software_motion_exemption_refused", plan_field=plan_field,
                            reason="the command is not what the approved plan derives for this move")
                continue
            kept[n] = plan_field
        if kept:
            for comparison in op.check_operation_points(plan, [commands[n] for n in kept],
                                                        op.load_safety()):
                self.record(event="operation_points_checked", **comparison)
        return kept

    def dispatch(self, commands: list[Command], timeout: float = 30.0,
                 plan: dict | None = None) -> list[dict]:
        """One worker per channel, ordered by the power rule, locks held.

        Commands for the same channel run in sequence because the channel is one
        machine. Different channels overlap, which is the only thing the
        parallelism is for.

        AN ACQUIRING COMMAND RANKS LAST, after everything on every other
        channel. The first mock run of a real plan showed why: the acquire
        sat at the neutral rank, so camera_red's acquisition overlapped
        stand_ti2e's nosepiece and magnification, and the frames were taken
        while the objective was still changing. Each command was correct, the
        channel locks all held, and the run was meaningless -- the failure is
        between channels, which is exactly where the parallelism lives.

        It ranks after `raises_power` too, and that is the point rather than
        an accident: illumination has to be up before the light is collected.
        """
        # Before resolution and before any worker starts, so a refused plan
        # leaves the instrument untouched. run() asks it earlier still, ahead
        # of preflight; asking again here covers a caller that skips run().
        self.check_software_motion_for(plan, commands)
        ordered = self.order([self._resolved(c) for c in commands])
        by_rank: dict[int, list[Command]] = defaultdict(list)
        for c in ordered:
            by_rank[3 if c.acquires else
                    0 if c.lowers_power else 2 if c.raises_power else 1].append(c)

        outcomes: list[dict] = []
        for rank in sorted(by_rank):
            batch = by_rank[rank]
            per_channel: dict[str, list[Command]] = defaultdict(list)
            for c in batch:
                per_channel[c.channel].append(c)

            threads, results = [], {}

            def work(cid: str, queue: list[Command]) -> None:
                out = []
                with self._channel_locks[cid]:
                    for command in queue:
                        if self._aborted.is_set():
                            out.append({"command": command.action, "skipped": "aborted"})
                            continue
                        try:
                            self.check_manual_lockout(command)
                            self.check_turret_rotation_allowed(command)
                            self.check_acquisition_allowed(command)
                            module = self.module_for(cid)
                            value = module.apply(command.params)
                            verification, why = self.verification_of(cid, value)
                            out.append({"command": command.action, "ok": True, "returned": value,
                                        "verification": verification})
                            if verification == "readback":
                                self._completed.add(command.element or cid)
                            detail = {}
                            if isinstance(value, dict) and value.get("disagreed"):
                                # On the apply event and not on one of its own:
                                # a disagreement is a property of this dispatch,
                                # and a second event carrying the same `from`
                                # would be read as a second dispatch -- check 66
                                # would report one command twice.
                                detail["disagreed"] = value["disagreed"]
                            if from_operation_move(command) and isinstance(value, dict):
                                # Where the stage WAS, beside where it was told to go.
                                # The params already carry the commanded points; the
                                # measured ones exist only in what the device returned,
                                # and the dispatch outcomes are read by nobody -- so
                                # without this the run log could not show the one thing
                                # an operation plan's result is made of.
                                detail["measured"] = {k: value.get(k) for k in (
                                    "before_um", "after_um", "points_planned", "points_sent",
                                    "late_points", "dt_s", "samples", "settle",
                                    "settle_wait_s")}
                            self.record(event="apply", channel=cid, element=command.element,
                                        action=command.action, params=command.params,
                                        verification=verification, verification_note=why,
                                        **detail, **{"from": command.from_field})
                            if from_operation_move(command) and verification != "readback":
                                # Card 040 item 2: an operation move whose read-back
                                # is not within the plan's tolerance stops the run
                                # BEFORE the next move -- the next move would start
                                # from a place nobody confirmed. Marked failed so
                                # run() aborts, exactly as a refused command does.
                                self._aborted.set()
                                out[-1]["ok"] = False
                                out[-1]["error"] = (f"read-back not within tolerance after "
                                                    f"{command.from_field}: {why}")
                                self.record(event="stop_criterion_violated",
                                            criterion="position_readback_error",
                                            plan_field=command.from_field,
                                            disagreed=(value.get("disagreed")
                                                       if isinstance(value, dict) else None),
                                            note=why)
                        except Exception as exc:                # noqa: BLE001 - recorded, and it stops the run
                            # A FAILED COMMAND STOPS EVERYTHING AFTER IT. This
                            # said "re-raised by the caller" and the caller did
                            # not: `run()` discards dispatch's return value, so
                            # a refused interlock was written to the log and
                            # stepped over. The first run with a turret check
                            # in it refused the nosepiece and then set the
                            # magnification and acquired -- a P0 guard that
                            # fired and changed nothing.
                            #
                            # The flag is set here rather than calling abort()
                            # here: this runs inside the channel lock, and
                            # abort() reaches every channel. The remaining
                            # commands in this queue and every later rank see
                            # the flag at the top of the loop and skip; run()
                            # performs the actual abort once, outside.
                            self._aborted.set()
                            out.append({"command": command.action, "ok": False,
                                        "error": f"{type(exc).__name__}: {exc}",
                                        "verification": "none"})
                            # A command that raised was never confirmed either, and the
                            # field says so rather than going absent: check 66 reads an
                            # absent `verification` as a run that does not stand, and a
                            # failed dispatch is a fact about the run, not a gap in it.
                            self.record(event="apply_failed", channel=cid, element=command.element,
                                        action=command.action, error=str(exc),
                                        verification="none",
                                        verification_note=("the command raised; whether it took "
                                                           "effect was never asked"),
                                        **{"from": command.from_field})
                results[cid] = out

            for cid, queue in per_channel.items():
                thread = threading.Thread(target=work, args=(cid, queue), name=f"worker:{cid}")
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join(timeout)
                if thread.is_alive():
                    self.record(event="timeout", worker=thread.name, timeout_s=timeout)
                    self.abort(reason=f"{thread.name} exceeded {timeout} s")
            outcomes.append({"rank": rank, "results": results})
        return outcomes

    def abort(self, reason: str) -> dict:
        """Shutters first, then power down, then everyone else -- all of them.

        A device that fails to abort does not stop the fan-out. The point is to
        reach every channel and to record what each one did, including the ones
        that refused (4.6.8).
        """
        self._aborted.set()
        self.record(event="abort_begin", reason=reason)
        report: dict[str, object] = {"reason": reason, "shutters": [], "channels": []}

        # ONE ROW PER CHANNEL, NOT ONE BOOLEAN FOR THE INSTRUMENT.
        #
        # The gap test was `if not self.shutters()`, which is global: the list
        # is collected across every channel by `"shutter" in element_id`, so
        # ONE channel with a recognised name suppressed the warning for every
        # channel without one. Measured: two recognised -> 0 warnings; one
        # recognised and one spelled `*_blanking` -> still 0 warnings and half
        # the cut-offs left open; none recognised -> 1 warning. A total miss
        # left a record and a partial miss left nothing.
        #
        # That is the one spelling dependence here that fails PERMISSIVE.
        # A missed retract makes the turret interlock refuse -- wrong, loud,
        # safe. A missed shutter makes 4.6.8 interlock 1 close what it
        # recognised and carry on, so what it missed stays open while the
        # power ramps, and the ramp is the slow path the shutter exists to
        # beat. `blanking` is not a hypothetical spelling: the store's
        # lunf_per_line_power_is_not_transmittable says the combiner's lines
        # are reachable only as blanking.
        #
        # P0 says ambiguity stops rather than proceeds, and ON THE ABORT PATH
        # "stops" cannot mean refusing to abort -- that is worse than the gap.
        # So it means the record names what it could not do.
        #
        # AND IT INFERS NOTHING ABOUT WHICH CHANNELS EMIT LIGHT. Deciding
        # "this one needed a cut-off" from a role string is the same spelling
        # judgement one level up, and a model choosing where a P0 guard
        # applies is what P0 forbids. The denominator is every channel; the
        # reader draws the conclusion, and the reader is a person.
        found = dict(self.shutters())            # channel -> element, at most one per channel
        closes = {entry["element"]: entry for entry in SHUTTER_CLOSES if entry["element"]}
        for entry in SHUTTER_CLOSES:
            if entry["element"] is None:
                report["shutters"].append(self._close_shutter(entry["channel"], None, entry))
        for cid in self.channels:
            element = found.get(cid)
            if element is None:
                report["shutters"].append({
                    "channel": cid, "element": None, "identified": False,
                    "commanded": None, "read_back": None, "closed": None,
                    "note": ("no element of this channel was recognised as a fast cut-off, by "
                             f"the test `'shutter' in element_id` over {self.channels[cid].element_ids()}. "
                             "Whether this channel needs one is NOT decided here: nothing in the "
                             "registry says which channels emit, and inferring it from a role "
                             "string would be the same guess this record exists to expose")})
                continue
            report["shutters"].append(self._close_shutter(cid, element, closes.get(element)))

        recognised = [r for r in report["shutters"] if not r.get("declared")]
        identified = [r for r in recognised if r["identified"]]
        report["shutter_coverage"] = {
            "channels": len(self.channels), "identified": len(identified),
            "without": sorted(r["channel"] for r in recognised if not r["identified"]),
            "declared": sorted(r["device"] for r in report["shutters"] if r.get("declared")),
            "note": ("the denominator, so a partial miss is as visible as a total one. This "
                     "counts channels with a RECOGNISED cut-off and not channels that need "
                     "one -- the second number is not knowable from the registry today. "
                     "`declared` lists the shutters closed from SHUTTER_CLOSES by device, "
                     "which recognition does not see and this count does not include")}
        self.record(event="abort_shutter_coverage", **report["shutter_coverage"])

        # POWER DOWN, BETWEEN THE SHUTTERS AND THE FAN-OUT, and the second
        # half of that is not just order (card 054). After the shutters,
        # because a shutter beats a ramp (4.6.8 interlock 1). BEFORE every
        # channel's abort(), because both mock.apply and micromanager.apply
        # refuse every command once their module's abort() has set
        # `_ABORTED` -- a power-down placed after the fan-out would be refused
        # by the very abort it belongs to, and would record that refusal as
        # the lamp's state.
        report["light_sources"] = self._power_down()
        self.record(event="abort_light_sources", rows=report["light_sources"])

        # `aborted` IS A THIRD BOOLEAN CARRYING MORE THAN IT KNOWS, and it is
        # the answer to 028's last question. `module.abort()` returning means
        # the command was ACCEPTED, and on optical_tweezers that is all it can
        # ever mean -- tweez300_reports_nothing_back (E3): no read-back of any
        # kind, and a return code of 0 on six distinct ways of being ignored.
        # `aborted: true` there asserts the instrument stopped; what happened
        # is that a GUI took the text. Same shape as `verification`, so it
        # takes the same three-way answer rather than a wider boolean.
        for cid in self.channels:
            channel = self.channels[cid]
            confirmable = channel.read_back is True
            try:
                self.module_for(cid).abort()
                report["channels"].append({
                    "channel": cid, "accepted": True,
                    # `accepted_only` and not a bare `accepted`: the shorter
                    # word reads as the stronger claim and belongs to the
                    # channel that can say least. I wrote it the other way
                    # round first and the probe printed optical_tweezers --
                    # which reports nothing at all -- with the confident
                    # label. Neither state is verified; they differ in
                    # whether anything MORE was ever available.
                    "aborted": "accepted_only" if not confirmable else "accepted_unverified",
                    "note": ("the channel reports nothing back, so acceptance is the whole of "
                             "what is known (2.1: an unverified state does not proceed -- here "
                             "it is recorded, because refusing to abort is worse than the gap)"
                             if not confirmable else
                             "the command was accepted; nothing queried the channel afterwards, "
                             "so this is not a confirmation that it stopped")})
            except Exception as exc:                            # noqa: BLE001 - keep going, record it
                report["channels"].append({"channel": cid, "accepted": False, "aborted": "refused",
                                           "error": str(exc)})

        self.record(event="abort_end", report=report)
        return report

    def _close_shutter(self, cid: str, element: str, entry: dict | None) -> dict:
        """One recognised shutter's row: what was sent, what came back, what that shows.

        `closed` is True or False only from the backend's own read-back of
        the declared pair, the way `_power_down()` judges `matched`. A call
        that returned with nothing read back gives `closed: None`, never
        True -- the defect this replaces wrote True on the call returning,
        including through micromanager, where the call wrote nothing.
        A failure is recorded and the abort goes on.
        """
        row = {"channel": cid, "element": element, "identified": True,
               "commanded": None, "read_back": None, "closed": None}
        if element is None:
            row.update(device=entry["device"], declared=True)
        if entry is None:
            row["note"] = ("not commanded: no close command is declared for this shutter in "
                           "SHUTTER_CLOSES, and none is guessed. A person closes it")
            return row
        if not entry["commandable"]:
            row["note"] = f"not commanded: {entry['why']}. A person closes it"
            return row
        try:
            if entry.get("abort_close"):
                # The person's abort-only close. Its refusal is asked from
                # micromanager on EVERY backend, so a close the instrument
                # would refuse is refused on mock as well; the backend asks it
                # again before writing.
                device, prop, value = entry["abort_close"]
                mm = self._device_module("micromanager", needed_by="the abort-only shutter close")
                why = mm.abort_close_refusal(device, prop, value)
                if why is not None:
                    row["error"] = f"refused before sending: {why}"
                    return row
                returned = self.module_for(cid).close_for_abort(device, prop, value)
                row["commanded"] = value
            else:
                returned = self.module_for(cid).apply(entry["command"])
                row["commanded"] = entry["command"]
        except Exception as exc:                                # noqa: BLE001 - keep going, record it
            row["error"] = str(exc)
            return row
        returned = returned if isinstance(returned, dict) else {}
        verify = entry["verify"]
        pair = [] if verify is None else [
            r for r in (returned.get("verified") or []) + (returned.get("disagreed") or [])
            if (r.get("device"), r.get("property")) == tuple(verify)]
        if not pair:
            row["note"] = (f"close sent and not confirmed: {entry['why']}, so whether the "
                           "shutter is closed was never asked")
        else:
            row["read_back"] = None if pair[0].get("read") is None else str(pair[0]["read"])
            row["closed"] = pair[0] in (returned.get("verified") or [])
        return row

    def _power_down(self) -> list[dict]:
        """One row per declared light source: off written, read back, compared.

        `matched` is judged from the backend's own read-back -- the
        `verified` / `disagreed` lists apply returns -- and never from the
        call returning. The shutter rows above record `closed: True` on the
        call returning, and on micromanager that call sends `element`/`state`,
        which `_settings()` does not read, so it writes nothing; these rows
        go through `settings` so that they cannot repeat that.

        Nothing here stops the abort: a source that raises, refuses or reads
        back wrong is recorded, and the next source is tried.
        """
        rows = []
        for src in LIGHT_SOURCES:
            row = {"source": src["source"], "channel": src["channel"],
                   "commanded": None, "read_back": None, "matched": None}
            if not src["software_commandable"]:
                row["note"] = (f"not software-controllable: {src['why']}. This abort writes nothing to "
                               "it, so if a person switched it on by hand it is STILL ON; a "
                               "person turns it off")
                rows.append(row)
                continue
            device, prop, off = src["device"], src["property"], src["off"]
            try:
                returned = self.module_for(src["channel"]).apply(
                    {"settings": {device: {prop: off}}})
                row["commanded"] = off
            except Exception as exc:                            # noqa: BLE001 - keep going, record it
                row["error"] = str(exc)
                rows.append(row)
                continue
            returned = returned if isinstance(returned, dict) else {}
            pair = [r for r in (returned.get("verified") or []) + (returned.get("disagreed") or [])
                    if r.get("device") == device and r.get("property") == prop]
            if not pair:
                row["note"] = ("the backend reported no read-back for this pair, so the write "
                               "was accepted and whether the source is off was never asked")
            else:
                row["read_back"] = None if pair[0].get("read") is None else str(pair[0]["read"])
                row["matched"] = pair[0] in (returned.get("verified") or [])
            rows.append(row)
        return rows

    def snapshot(self, label: str) -> dict:
        """read() from every channel, gathered into the log around each step."""
        states = {}
        for cid in self.channels:
            try:
                states[cid] = self.module_for(cid).read()
            except Exception as exc:                            # noqa: BLE001 - an unreadable channel is a fact
                states[cid] = {"error": str(exc)}
        self.record(event="snapshot", label=label, states=states)
        return states
