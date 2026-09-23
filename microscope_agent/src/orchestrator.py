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

    # -- logging ----------------------------------------------------------- #

    def record(self, **fields) -> dict:
        event = {"t_mono": self.clock.offset(), "time_base": SOFTWARE, **fields}
        with self._log_lock:
            self.log.append(event)
        return event

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
        elif channel.automatable == "none" or not channel.verifiable:
            name = "manual"
        else:
            name = self.driver_module(channel)
        if name not in self._modules:
            path = DEVICES / f"{name}.py"
            if not path.exists():
                raise GapError(
                    f"channel {channel_id!r} needs devices/{name}.py, which does not exist. "
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

    def dispatch(self, commands: list[Command], timeout: float = 30.0) -> list[dict]:
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
                            self.record(event="apply", channel=cid, element=command.element,
                                        action=command.action, params=command.params,
                                        verification=verification, verification_note=why,
                                        **detail, **{"from": command.from_field})
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
        for cid in self.channels:
            element = found.get(cid)
            if element is None:
                report["shutters"].append({
                    "channel": cid, "element": None, "identified": False, "closed": None,
                    "note": ("no element of this channel was recognised as a fast cut-off, by "
                             f"the test `'shutter' in element_id` over {self.channels[cid].element_ids()}. "
                             "Whether this channel needs one is NOT decided here: nothing in the "
                             "registry says which channels emit, and inferring it from a role "
                             "string would be the same guess this record exists to expose")})
                continue
            try:
                self.module_for(cid).apply({"element": element, "state": "closed"})
                report["shutters"].append({"channel": cid, "element": element,
                                           "identified": True, "closed": True})
            except Exception as exc:                            # noqa: BLE001 - keep going, record it
                report["shutters"].append({"channel": cid, "element": element,
                                           "identified": True, "closed": False,
                                           "error": str(exc)})

        identified = [r for r in report["shutters"] if r["identified"]]
        report["shutter_coverage"] = {
            "channels": len(self.channels), "identified": len(identified),
            "without": sorted(r["channel"] for r in report["shutters"] if not r["identified"]),
            "note": ("the denominator, so a partial miss is as visible as a total one. This "
                     "counts channels with a RECOGNISED cut-off and not channels that need "
                     "one -- the second number is not knowable from the registry today")}
        self.record(event="abort_shutter_coverage", **report["shutter_coverage"])

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
