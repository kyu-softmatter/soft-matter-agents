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
            name = f"dev_{channel_id}"
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
        """
        ordered = self.order([self._resolved(c) for c in commands])
        by_rank: dict[int, list[Command]] = defaultdict(list)
        for c in ordered:
            by_rank[0 if c.lowers_power else 2 if c.raises_power else 1].append(c)

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
                            self.check_acquisition_allowed(command)
                            module = self.module_for(cid)
                            value = module.apply(command.params)
                            verification, why = self.verification_of(cid, value)
                            out.append({"command": command.action, "ok": True, "returned": value,
                                        "verification": verification})
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
                        except Exception as exc:                # noqa: BLE001 - recorded, then re-raised by the caller
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

        shutters = self.shutters()
        if not shutters:
            report["shutter_gap"] = (
                "the registry lists no shutter element. plan.md 4.6.8 interlock 1 closes shutters "
                "before ramping power down; with none declared there is no fast cut-off to use, so "
                "the ramp is all that is left and that is slower. Confirm the shutters on the "
                "instrument and record them before this path is trusted"
            )
            self.record(event="abort_shutter_gap", note=report["shutter_gap"])

        for cid, element in shutters:
            try:
                self.module_for(cid).apply({"element": element, "state": "closed"})
                report["shutters"].append({"channel": cid, "element": element, "closed": True})
            except Exception as exc:                            # noqa: BLE001 - keep going, record it
                report["shutters"].append({"channel": cid, "element": element, "closed": False,
                                           "error": str(exc)})

        for cid in self.channels:
            try:
                self.module_for(cid).abort()
                report["channels"].append({"channel": cid, "aborted": True})
            except Exception as exc:                            # noqa: BLE001 - keep going, record it
                report["channels"].append({"channel": cid, "aborted": False, "error": str(exc)})

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
