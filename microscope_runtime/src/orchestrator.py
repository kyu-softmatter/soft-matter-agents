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

import hashlib
import importlib.util
import json
import re
import socket
import sys
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent
DEVICES = Path(__file__).resolve().parent / "devices"
#: The knowledge snapshot stays in microscope_agent/envelope/, one copy read by both folders
#: (plan.md 15). AGENT is microscope_runtime/ now, so the snapshot is not beside the policy.
SNAPSHOT_PATH = REPO / "microscope_agent" / "envelope" / "snapshot.json"

# The device registry is knowledge and the librarian owns it (4.3.2), so its
# reading position moves as the librarian lands while its owner does not. The
# microscope reads the store directly only until then, which 4.3.0 allows and
# 11.1 records.
REGISTRY_LOOKUP = [
    SNAPSHOT_PATH,
    REPO / "librarian_agent" / "kb" / "exports" / "devices.json",
    REPO / "librarian_agent" / "kb" / "staging" / "devices.v0.json",
]


def is_light_command(event: dict) -> bool:
    """Whether a log event is a command to a light source software may command (card 076).

    The sources are the declared LIGHT_SOURCES table's, matched by the device names it declares: a
    command's params carry them as `Device.Property` keys or as a key of a nested settings dict. Only an
    `apply` event can be one, and a source the table does not declare commandable never is.
    """
    if event.get("event") != "apply":
        return False
    params = event.get("params")
    if not isinstance(params, dict):
        return False
    devices = {s["device"] for s in LIGHT_SOURCES if s["software_commandable"] and s["device"]}

    def hit(mapping: dict, depth: int) -> bool:
        for key, value in mapping.items():
            if str(key).split(".")[0] in devices:
                return True
            if depth < 2 and isinstance(value, dict) and hit(value, depth + 1):
                return True
        return False
    return hit(params, 0)


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


#: The field a registry row (a channel or one of its elements) carries its Micro-Manager label in, and
#: the keys of that field (librarian card 061, plan.md 15.1 item 9). Read here and nowhere else.
MM_LABEL_FIELD = "mm_label"
MM_LABEL_KEYS = {"label", "entry_ref", "config_sha256"}
#: Where the CITED ENTRY carries the same label, and the configuration it was read under, in its
#: `identifiers`. The grade is the entry's own `grade`.
ENTRY_LABEL_IDENTIFIERS = ("mm_label", "mm_device")
ENTRY_DIGEST_IDENTIFIER = "mm_config_sha256"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _entry_facts(entries: dict | None, entry_ref: str) -> dict:
    """What the snapshot's entry says about itself: its grade and the configuration it names.

    Nothing is decided here. An entry the file does not carry (the flat staging form has none) gives
    no grade and no digest, and the check refuses on that and says so.
    """
    held = (entries or {}).get(entry_ref)
    if held is None:
        return {"found": False, "grade": None, "digest": None, "label": None, "identifiers": {}}
    try:
        entry = json.loads(held["text"]) if isinstance(held.get("text"), str) else held
    except (ValueError, AttributeError):
        return {"found": False, "grade": None, "digest": None, "label": None, "identifiers": {}}
    identifiers = entry.get("identifiers") or {}
    label = next((identifiers[k] for k in ENTRY_LABEL_IDENTIFIERS if identifiers.get(k)), None)
    return {"found": True, "grade": entry.get("grade"),
            "digest": identifiers.get(ENTRY_DIGEST_IDENTIFIER), "label": label,
            "identifiers": identifiers}


def _mm_labels(channels: dict[str, Channel], entries: dict | None, source: str) -> dict[str, dict]:
    """Every registry name that carries a label, with the entry it cites. Decides nothing.

    One label per row and one row per label. A malformed field or a label on two rows is not
    resolved by picking one: the registry stops here, at load (2.1 rule 2).
    """
    found: dict[str, dict] = {}
    owner: dict[str, str] = {}
    for channel in channels.values():
        rows = [(channel.id, channel.raw)] + [(eid, el) for eid, el in channel.elements.items()]
        for name, row in rows:
            if MM_LABEL_FIELD not in row:
                continue
            field = row[MM_LABEL_FIELD]
            if (not isinstance(field, dict) or not set(field) <= MM_LABEL_KEYS
                    or not isinstance(field.get("label"), str) or not field["label"]
                    or not isinstance(field.get("entry_ref"), str) or not field["entry_ref"]):
                raise GapError(
                    f"{source}: {name!r} carries {MM_LABEL_FIELD!r} and it is not an object of "
                    f"{sorted(MM_LABEL_KEYS)} with a label and an entry_ref")
            label = field["label"]
            if label in owner:
                raise GapError(
                    f"{source}: the label {label!r} sits on both {owner[label]!r} and {name!r}. "
                    "A label that means two rows is not resolved by choosing one")
            owner[label] = name
            facts = _entry_facts(entries, field["entry_ref"])
            row_digest = field.get("config_sha256")
            if row_digest is not None and not (isinstance(row_digest, str) and _SHA256.match(row_digest)):
                raise GapError(f"{source}: {name!r} carries a config_sha256 that is not 64 lowercase hex")
            if row_digest is not None and facts["digest"] is not None and row_digest != facts["digest"]:
                raise GapError(
                    f"{source}: {name!r} carries config_sha256 {row_digest} and its entry "
                    f"{field['entry_ref']!r} carries {facts['digest']}. The row's digest is a copy "
                    "of the entry's, and two that differ are not resolved by choosing one")
            found[name] = {"name": name, "label": label, "entry_ref": field["entry_ref"],
                           "entry_found": facts["found"], "grade": facts["grade"],
                           "config_sha256": facts["digest"]}
    return found


#: The two lists a registry row may carry beside its label (librarian card 062, plan.md 15.1 item 9):
#: bindings, which say which property of the label a quantity is written to and in what unit, and
#: states, which say which state label of a device a plan's word for it means. Each item cites its
#: entry; the row is a copy of the entry and the entry decides.
MM_BINDINGS_FIELD = "mm_bindings"
MM_STATES_FIELD = "mm_states"
_MM_ITEM_SHAPES = {
    MM_BINDINGS_FIELD: {"required": ("quantity", "property", "unit", "entry_ref"),
                        "optional": ("config_sha256", "step"), "unique": ("quantity", "property")},
    MM_STATES_FIELD: {"required": ("word", "state_label", "entry_ref"),
                      "optional": ("config_sha256",), "unique": ("word", "state_label")},
}
#: A count of frames is what a sequence returned, never a property of a device.
NEVER_A_BINDING = ("frame_count",)


def _mm_row_lists(channels: dict[str, Channel], entries: dict | None, source: str,
                  field: str) -> dict[str, list[dict]]:
    """Every registry name's `mm_bindings` or `mm_states`, with the facts of the entry each item cites.

    Decides nothing about whether an item may be used; that is asked where it is used. A malformed
    list, a repeated quantity, property, word or state label on one row, or a row digest that
    differs from its entry's is not resolved by choosing one: the registry stops here, at load.
    """
    shape = _MM_ITEM_SHAPES[field]
    allowed = set(shape["required"]) | set(shape["optional"])
    found: dict[str, list[dict]] = {}
    for channel in channels.values():
        rows = [(channel.id, channel.raw)] + [(eid, el) for eid, el in channel.elements.items()]
        for name, row in rows:
            if field not in row:
                continue
            items = row[field]
            if not isinstance(items, list) or not items:
                raise GapError(f"{source}: {name!r} carries {field!r} and it is not a non-empty list")
            seen = {key: set() for key in shape["unique"]}
            kept = []
            for item in items:
                if (not isinstance(item, dict) or not set(item) <= allowed
                        or not all(isinstance(item.get(k), str) and item[k] for k in shape["required"])):
                    raise GapError(
                        f"{source}: an item of {field!r} on {name!r} is not an object with "
                        f"{list(shape['required'])} (and optionally {list(shape['optional'])})")
                if field == MM_BINDINGS_FIELD and item["quantity"] in NEVER_A_BINDING:
                    raise GapError(f"{source}: {name!r} binds {item['quantity']!r}, which is never a "
                                   "binding: it is counted from what the sequence returned")
                for key in shape["unique"]:
                    if item[key] in seen[key]:
                        raise GapError(f"{source}: {name!r} carries two {field!r} items with the "
                                       f"{key} {item[key]!r}. Two that differ are not resolved by "
                                       "choosing one")
                    seen[key].add(item[key])
                facts = _entry_facts(entries, item["entry_ref"])
                row_digest = item.get("config_sha256")
                if row_digest is not None and not (isinstance(row_digest, str) and _SHA256.match(row_digest)):
                    raise GapError(f"{source}: {name!r} carries a config_sha256 that is not 64 lowercase hex")
                if row_digest is not None and facts["digest"] is not None and row_digest != facts["digest"]:
                    raise GapError(
                        f"{source}: {name!r} carries config_sha256 {row_digest} and its entry "
                        f"{item['entry_ref']!r} carries {facts['digest']}. The row's digest is a copy "
                        "of the entry's, and two that differ are not resolved by choosing one")
                kept.append({**item, "name": name, "entry_found": facts["found"],
                             "grade": facts["grade"], "config_sha256": facts["digest"],
                             "identifiers": facts["identifiers"]})
            found[name] = kept
    return found


def _units() -> dict:
    """contracts/units.json's `units`, read from the file each time: no factor is written in code (card 095)."""
    return json.loads((REPO / "contracts" / "units.json").read_text(encoding="utf-8"))["units"]


_DECIMAL = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def _exact_number(x) -> Fraction | None:
    """A number as an exact fraction of its decimal text, or None when it is not a finite number (card 098).

    A float is read through `str`, the way the exact-factor route always did, so 0.1 is one tenth and
    not the double nearest to it; a string counts only when it is a decimal. A bool is not a number.
    """
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return Fraction(x)
    if isinstance(x, float):
        return None if x != x or x in (float("inf"), float("-inf")) else Fraction(str(x))
    if isinstance(x, str) and _DECIMAL.match(x.strip()):
        return Fraction(x.strip())
    return None


def _number_out(x: Fraction):
    """A whole number as an int and any other as a float: what a property is handed and a log records."""
    return int(x) if x.denominator == 1 else float(x)


def _exact_factor(from_unit, to_unit) -> Fraction | None:
    """The exact factor from one unit to another of the same dimension, from contracts/units.json, or None."""
    if from_unit == to_unit:
        return Fraction(1)
    if not (isinstance(from_unit, str) and isinstance(to_unit, str)):
        return None
    units = _units()
    a, b = units.get(from_unit), units.get(to_unit)
    if (a is not None and b is not None and a.get("dim") == b.get("dim")
            and a.get("si_factor") and b.get("si_factor")):
        return Fraction(str(a["si_factor"])) / Fraction(str(b["si_factor"]))
    return None


def _read_registry(path: Path | None = None) -> tuple[dict[str, Channel], str, dict, dict | None]:
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
    entries = data.get("entries") if isinstance(data.get("entries"), dict) else None

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
    # Written with forward slashes, the way plan_path is, on every platform. A registry outside this
    # tree (a test's) is written as it is.
    try:
        written = source.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        written = source.as_posix()
    return channels, written, provenance, entries


def load_registry(path: Path | None = None) -> tuple[dict[str, Channel], str, dict]:
    channels, written, provenance, _entries = _read_registry(path)
    return channels, written, provenance


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
    #: What the derivation wrote for the device, `{label: {property: value}}`, from bindings (card 095).
    #: Kept apart from `params`, which carry the plan's numbers each with its `from`: a settings
    #: dict has no `from` and the run log's `params` need one. Dispatch sends both.
    settings: dict = field(default_factory=dict)
    #: One row per written value: the plan's number with its `from`, the value written, the binding
    #: and any calibration. It goes on the apply event.
    written: list = field(default_factory=list)
    #: Frames the plan asked for, when the verb counts them (a verb argument, card 095).
    frame_count: int | None = None

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



def pfs_not_engaged(safety: dict) -> dict:
    """The envelope's `pfs_not_engaged` (0e3eff1): {device, property, values[]}, read fresh.

    PFS is in NAMED_REFUSALS, so software cannot switch it off; the search
    reads it and refuses while it is engaged, and the person switches it off.
    WHICH READING MEANS OFF IS THE PERSON'S, written in envelope/safety.json
    from the bench record of each state. It was a constant here, left None on
    purpose until it had that home, and every search refused. A reading
    inferred from a property's name would be a spelling deciding a safety
    guard (check 80), so nothing here supplies one: an absent key refuses.
    """
    found = None
    for target in safety.get("targets") or []:
        entry = (target.get("limits") or {}).get("pfs_not_engaged")
        if entry is not None:
            found = entry
    if not isinstance(found, dict) or not isinstance(found.get("device"), str)             or not isinstance(found.get("property"), str)             or not isinstance(found.get("values"), list) or not found["values"]:
        raise InterlockError(
            "envelope/safety.json has no pfs_not_engaged: which focus-hold reading means not "
            "engaged is the person's to write, and without it PFS cannot be confirmed off, so "
            "the search refuses. PFS is refused to software; a person switches it off")
    return {"device": found["device"], "property": found["property"],
            "values": [str(v) for v in found["values"]]}


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


class _PreStopBuffer:
    """The last `length_s` seconds of the frames a run already acquired, kept for a stop (card 082).

    IT COMMANDS NOTHING AND HOLDS NO CORE. It is handed frames by the orchestrator's tee, after the run's
    own sink has had each one, keeps a COPY with the frame's `t_mono`, and drops what has aged out by that
    clock and not by a count -- the rate is the run's own, so a faster camera simply keeps more frames.
    It never triggers an acquisition, a snap or a light: with no frame arriving it holds nothing new.

    A stop freezes it (`stop_at`): nothing offered afterwards is kept, so a frame still in flight when the
    abort began can neither join the window nor push an older frame out of it. `window()` is then the frames
    from `stop_t - length_s` to `stop_t`, both ends inside. `put` takes its copy before the lock and swaps
    under it, so the run's thread never waits on anything slower than a deque append.
    """

    def __init__(self, length_s: float) -> None:
        self._length_s = float(length_s)
        self._lock = threading.Lock()
        self._ring: deque = deque()
        self._next = 0
        self._stop_t: float | None = None

    @property
    def length_s(self) -> float:
        return self._length_s

    def put(self, image, metadata, t_mono: float) -> None:
        if self._stop_t is not None:
            return
        copy = None
        if self._length_s > 0:
            copy = image.copy() if hasattr(image, "copy") else bytes(image)
        with self._lock:
            if self._stop_t is not None:
                return
            index = self._next
            self._next += 1
            if copy is None:
                return
            self._ring.append((index, float(t_mono), copy, dict(metadata or {})))
            cutoff = float(t_mono) - self._length_s
            while self._ring and self._ring[0][1] < cutoff:
                self._ring.popleft()

    def stop_at(self, t_mono: float) -> None:
        with self._lock:
            if self._stop_t is None:
                self._stop_t = float(t_mono)

    def kept(self) -> int:
        with self._lock:
            return len(self._ring)

    def window(self) -> list:
        """(index, t_mono, frame copy, metadata) for each frame inside the window, oldest first."""
        with self._lock:
            entries = list(self._ring)
            stop_t = self._stop_t
        if stop_t is None:
            return entries
        low = stop_t - self._length_s
        return [e for e in entries if low <= e[1] <= stop_t]


class _FrameTap(threading.Thread):
    """The latest frame of each camera a run takes, served on loopback (cards 058 and 084).

    IT COMMANDS NOTHING, AND IT HOLDS NO CORE. It is handed frames by the
    orchestrator's tee on the run's own sink and snap(), keeps a COPY of the
    most recent one of each camera, and serves that copy. There is no
    reference here to any device module or core, so it cannot start, stop,
    configure or even read an acquisition; when no frame is arriving it says
    so and never snaps.

    The camera a frame belongs to is the one the orchestrator's own call
    served (`put(..., camera)`), never a name read out of the frame's
    metadata. Only the cameras `run_started` lists as `tap_cameras` are kept
    or answered for.

    `put()` is the only thing the run's thread calls: it copies the frame,
    swaps one reference under a lock and returns. Serving -- serialising the
    copy and writing it to the socket -- happens on a thread of its own per
    connection, so a reader that is slow, never sends, or never reads holds
    up its own thread and nothing else: not the run, and not a reader of
    another camera.

    Two request forms, one line of JSON each: {"get": "latest_frame"}, which
    answers for the first camera listed, and the same with "camera": <name>.
    The reply is one header line, then the frame's bytes; or a header saying
    there is no frame (yet), or that the run does not take that camera.
    Anything else is refused, recorded, and closed unanswered.
    """

    MAX_REQUEST_BYTES = 256
    #: Readers served at once. The tap is on loopback and its readers are the console's own; a
    #: connection past this is closed unanswered, so a flood cannot grow threads without bound.
    MAX_READERS = 16
    #: run_interface.schema.json $defs/camera_name
    CAMERA_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

    def __init__(self, orchestrator, run_id: str, cameras=()) -> None:
        super().__init__(name=f"frame-tap:{run_id}", daemon=True)
        self._o = orchestrator
        self._cameras = tuple(cameras)
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._latest: dict[str, tuple] = {}
        self._readers: set[threading.Thread] = set()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(4)
        self._sock.settimeout(0.05)
        host, port = self._sock.getsockname()[:2]
        self._addr = {"host": host, "port": port}       # what the socket IS bound to

    def address(self) -> dict:
        return dict(self._addr)

    def cameras(self) -> list[str]:
        return list(self._cameras)

    def put(self, image, metadata: dict, t_mono: float, camera: str | None = None) -> None:
        """Copy one frame in, replacing that camera's last. Nothing queues.

        A camera the run does not list is not kept: nothing would ever serve it.
        """
        if camera not in self._cameras:
            return
        copy = image.copy() if hasattr(image, "copy") else bytes(image)
        latest = (copy, dict(metadata or {}), t_mono)
        with self._lock:
            self._latest[camera] = latest

    def _no_frame(self, asked: str | None, note: str) -> bytes:
        head = {"frame": False, "note": note}
        if asked is not None:
            head["camera"] = asked
        return json.dumps(head).encode() + b"\n"

    def _unlabelled(self) -> str:
        """What was not tapped for want of a label, said in the reply that has no frame (card 091)."""
        why = list(self._o.tap_unlabelled.values())
        return "; " + "; ".join(why) if why else ""

    def _reply(self, asked: str | None) -> bytes:
        camera = asked if asked is not None else (self._cameras[0] if self._cameras else None)
        if camera is None:
            return self._no_frame(asked, "no frame: this run takes no camera, so nothing is "
                                  "acquired in it, and the tap never acquires" + self._unlabelled())
        with self._lock:
            latest = self._latest.get(camera)
        if latest is None:
            return self._no_frame(asked, "no frame yet: nothing has been "
                                  "acquired in this run, and the tap never acquires" + self._unlabelled())
        image, metadata, t_mono = latest
        if hasattr(image, "tobytes"):
            body = image.tobytes()
            shape, dtype = list(getattr(image, "shape", [])), str(getattr(image, "dtype", ""))
        else:
            body, shape, dtype = bytes(image), [len(image)], "bytes"
        head = {"frame": True, "metadata": metadata, "t_mono": t_mono, "bytes": len(body),
                "shape": shape, "dtype": dtype, "camera": camera}
        return json.dumps(head, default=str).encode() + b"\n" + body

    def _judge(self, raw: bytes) -> bytes | None:
        def refuse(why: str) -> None:
            self._o.record(event="frame_tap_refused", reason=why, bytes=len(raw))
            return None
        if len(raw) > self.MAX_REQUEST_BYTES:
            return refuse(f"longer than {self.MAX_REQUEST_BYTES} bytes")
        text = raw.decode("utf-8", errors="replace")
        if text.endswith("\n"):
            text = text[:-1]
        if "\n" in text or "\r" in text:
            return refuse("not one line")
        try:
            message = json.loads(text)
        except ValueError:
            return refuse("not JSON")
        if (not isinstance(message, dict) or message.get("get") != "latest_frame"
                or set(message) not in ({"get"}, {"get", "camera"})):
            return refuse('not one of the two requests this tap answers, {"get": "latest_frame"} '
                          'and the same with "camera"')
        asked = message.get("camera")
        if "camera" in message and not (isinstance(asked, str) and self.CAMERA_NAME.match(asked)):
            return refuse("camera is not a camera name")
        if asked is not None and asked not in self._cameras:
            # Well formed, and not one this run takes: said by name, and recorded. No device is asked.
            taken = ", ".join(self._cameras) if self._cameras else "none"
            why = f"{asked} is not a camera this run takes (it takes: {taken}); the tap never acquires"
            self._o.record(event="frame_tap_refused", reason=why, camera=asked, bytes=len(raw))
            return self._no_frame(asked, f"this run does not take {asked}: the tap answers "
                                  f"for {taken} and never acquires" + self._unlabelled())
        return self._reply(asked)

    def _serve(self, conn) -> None:
        with conn:
            try:
                conn.settimeout(1.0)
                cap = self.MAX_REQUEST_BYTES + 1
                raw = b""
                while len(raw) < cap and b"\n" not in raw:
                    chunk = conn.recv(cap - len(raw))
                    if not chunk:
                        break
                    raw += chunk
                if b"\n" in raw and len(raw) < cap:
                    conn.settimeout(0.05)
                    try:
                        raw += conn.recv(cap - len(raw))
                    except (socket.timeout, OSError):
                        pass
                reply = self._judge(raw)
                if reply is not None:
                    conn.settimeout(1.0)
                    conn.sendall(reply)
            except OSError:
                # A reader that went away or never read: its loss, and not
                # a fact about the run, so nothing is recorded.
                pass

    def run(self) -> None:
        while not self._closed.is_set():
            try:
                conn, _ = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            with self._lock:
                self._readers = {t for t in self._readers if t.is_alive()}
                full = len(self._readers) >= self.MAX_READERS
            if full:
                conn.close()
                continue
            reader = threading.Thread(target=self._serve, args=(conn,),
                                      name=f"{self.name}:reader", daemon=True)
            with self._lock:
                self._readers.add(reader)
            reader.start()

    def close(self) -> None:
        self._closed.set()
        try:
            self._sock.close()
        except OSError:
            pass
        if self.is_alive():
            self.join(3.0)
        with self._lock:
            readers = list(self._readers)
        deadline = time.monotonic() + 3.0
        for reader in readers:
            reader.join(max(0.0, deadline - time.monotonic()))


# --------------------------------------------------------------------------- #
# the orchestrator
# --------------------------------------------------------------------------- #


class _WatcherSampler(threading.Thread):
    """The orchestrator's half of the run-time watcher (card 076 part C, plan.md 13.4 item 2).

    At the plan's cadence it takes the snapshot (`Orchestrator.watcher_snapshot`: `read(wait=False)` on the
    channels this run opened, and nothing else) and hands the watcher DATA: the snapshot, the log since
    the last tick and which channels have a read-back. It also moves the watcher's events into the run's
    log. The watcher holds nothing of this object, so it cannot command or stop; this thread is what
    reads, and it reads nothing once an abort has begun.
    """

    def __init__(self, orchestrator, watcher, cadence_s: float) -> None:
        super().__init__(name="watcher-sampler", daemon=True)
        self._o, self._w, self._cadence = orchestrator, watcher, float(cadence_s)
        self._done = threading.Event()
        self._seen = 0

    def run(self) -> None:
        next_due = self._o.clock.offset() + self._cadence
        while not self._done.wait(0.01):
            self.drain()
            now = self._o.clock.offset()
            if now < next_due:
                continue
            next_due = now + self._cadence
            if self._o._aborted.is_set():
                continue                                # no reads once an abort has begun
            try:
                self._tick(now)
            except Exception as exc:                    # noqa: BLE001 - recorded, never silent, never fatal
                self._o.record(event="snapshot", label="watcher", t_mono=now, states={"sampler": {
                    "not_read": True, "why": f"the watcher's sampling failed: {type(exc).__name__}: {exc}"}})

    def _tick(self, now: float) -> None:
        states = self._o.watcher_snapshot(now)
        with self._o._log_lock:
            new = list(self._o.log[self._seen:])
            self._seen = len(self._o.log)
        channels = {cid: {"read_back": ch.read_back} for cid, ch in self._o.channels.items()}
        self._w.tick({"t_mono": now, "states": states}, new, channels, now)

    def drain(self) -> None:
        for event in self._w.drain():
            self._o.record(**event)

    def stop(self) -> None:
        self._done.set()
        if self is not threading.current_thread():
            self.join(3.0)


class Orchestrator:
    def __init__(self, registry_path: Path | None = None, backend: str = "mock") -> None:
        self.channels, self.registry_source, self.registry_provenance, entries = _read_registry(registry_path)
        self.names = _name_index(self.channels)
        #: Each registry name's Micro-Manager label with the entry it cites (card 091). Read from the
        #: registry file this run loaded, and nowhere else; a name not in it has no label.
        self.mm_labels = _mm_labels(self.channels, entries, self.registry_source)
        #: The snapshot's entries as the registry file carried them, for what a binding, a state or a
        #: calibration cites (card 095). Read from the same file as the labels and nowhere else.
        self.entries = entries or {}
        self.mm_bindings = _mm_row_lists(self.channels, entries, self.registry_source, MM_BINDINGS_FIELD)
        self.mm_states = _mm_row_lists(self.channels, entries, self.registry_source, MM_STATES_FIELD)
        #: The sha256 of the APPROVED ORIGINAL configuration this run loaded (card 069's gate), which a
        #: label's entry has to name for the label to command anything. None until one is loaded. On
        #: the instrument the operator sets it; on mock only a test does, by hand.
        self.loaded_config_sha256: str | None = None
        #: Cameras the frame tap could not serve for want of a label, with why (card 091).
        self.tap_unlabelled: dict[str, str] = {}
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
        # The pre-stop buffer's length, as the plan wrote it, and whether a stop has dealt with it
        # (card 082). `None` means the plan carries no buffer; the operator sets it before begin_run.
        self.pre_stop_length_s: float | None = None
        self._pre_stop_handled = False
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

    def begin_run(self, folder: Path, run_id: str, plan_id, revision, tap_cameras, watcher=None,
                  watcher_event: dict | None = None, judgements=None,
                  judgements_event: dict | None = None) -> dict:
        """Open runs/<run_id>/events.jsonl and the stop channel; announce both in one line.

        `tap_cameras` is what the frame tap answers for, in order (card 084): the cameras the run
        will acquire, derived by the caller from the plan or the live-view list, never from a
        frame's metadata. It is required, so a caller that has not decided cannot leave it out;
        a run that acquires nothing passes `[]`.

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
        self._tap = _FrameTap(self, run_id, tap_cameras)
        self._folder = folder
        self._pre_stop = None if self.pre_stop_length_s is None else _PreStopBuffer(self.pre_stop_length_s)
        addr = self._stop.address()
        with self._log_lock:
            self._stream = open(folder / "events.jsonl", "a", encoding="utf-8")
            self._stream_line({"event": "run_started", "run_id": run_id, "plan_id": plan_id,
                               "revision": revision, "t0_wall": self.clock.t0_wall,
                               "stop_channel": addr, "frame_tap": self._tap.address(),
                               "tap_cameras": self._tap.cameras()})
            for event in self.log:
                self._stream_line(event)
        self._stop.start()
        self._tap.start()
        # RIGHT AFTER run_started, the run says whether it is watched (plan.md 13.4 item 7): either
        # watcher_started or watcher_off. A watcher that did not start never stops the run.
        if watcher_event is not None:
            self.record(**watcher_event)
        if watcher is not None:
            self._watcher = watcher
            watcher.start()
            self._sampler = _WatcherSampler(self, watcher, watcher.cadence_s)
            self._sampler.start()
        # THE JUDGEMENTS (plan.md 13.5, card 081) say they are on or off in the same breath: DM-1, DM-2 and
        # DM-4 record only, and a block that cannot be asked never stops the run.
        if judgements_event is not None:
            self.record(**judgements_event)
        if judgements is not None:
            self._judgements = judgements
            judgements.start()
        return addr

    def end_run(self, how: str, **detail) -> None:
        """Close the stop channel, then write `run_ended` as the last line and close the file.

        `how` is completed, aborted_by_monitor, stopped_from_outside or failed.
        The channel closes first, so nothing can be stopped once the run says
        it has ended.
        """
        # The watcher closes first and its last events (a question still open becomes
        # watcher_unanswered, run_ended) are in the log before run_ended is written.
        sampler, watcher = getattr(self, "_sampler", None), getattr(self, "_watcher", None)
        if sampler is not None:
            sampler.stop()
        if watcher is not None:
            watcher.close()
            for event in watcher.drain():
                self.record(**event)
            if getattr(watcher, "failure", None):
                detail["watcher_failure"] = watcher.failure
        self._sampler = self._watcher = None
        judgements = getattr(self, "_judgements", None)
        if judgements is not None:
            try:
                judgements.close()
                self._drain_judgements()
                detail["judgements"] = {"reached": dict(judgements.reached), "unreached": judgements.unreached()}
            except Exception as exc:                    # noqa: BLE001 - said, never raised
                self._judgements_failure = f"{type(exc).__name__}: {exc}"
            if getattr(self, "_judgements_failure", None):
                detail["judgements_failure"] = self._judgements_failure
            self._judgements = None
        stop = getattr(self, "_stop", None)
        if stop is not None:
            stop.close()
            self._stop = None
        tap = getattr(self, "_tap", None)
        if tap is not None:
            tap.close()
            self._tap = None
        # The idle status file (card 085) is written from this run's own log, BEFORE run_ended, so a
        # write that failed is an event in the log and in the stream. It never changes how the run ended.
        writer = getattr(self, "status_writer", None)
        if writer is not None:
            try:
                writer(self, how)
            except Exception as exc:                    # noqa: BLE001 - said, never raised
                self.record(event="idle_status_write_failed", error=f"{type(exc).__name__}: {exc}")
        with self._log_lock:
            if getattr(self, "_stream", None) is not None:
                self._stream_line({"event": "run_ended", "how": how,
                                   "t_mono": self.clock.offset(), **detail})
                self._stream.close()
                self._stream = None

    def stop_channel_address(self) -> dict | None:
        stop = getattr(self, "_stop", None)
        return None if stop is None else stop.address()

    def frame_tap_address(self) -> dict | None:
        tap = getattr(self, "_tap", None)
        return None if tap is None else tap.address()

    def mm_label(self, name: str) -> dict | None:
        """A registry name's Micro-Manager label with its entry's reference, grade and digest, or None.

        THE ONE LOOKUP. It reads what the registry file carried and nothing else, and it decides
        nothing: which device a name is, never whether it may move or whether this system may use
        the label. The check asks that.
        """
        return self.mm_labels.get(name)

    def mm_binding(self, name: str, quantity: str) -> dict | None:
        """The binding a registry name carries for a quantity, with its entry's facts, or None (card 095).

        Like mm_label it reads what the registry file carried and decides nothing: whether the
        binding may be used is `binding_refusal`'s.
        """
        return next((b for b in self.mm_bindings.get(name, []) if b["quantity"] == quantity), None)

    def mm_state(self, name: str, word: str) -> dict | None:
        """The state label a registry name's `mm_states` gives a plan's word, with its entry's facts, or None."""
        return next((s for s in self.mm_states.get(name, []) if s["word"] == word), None)

    def _entry_refusal(self, what: str, head: str, ref: str, grade, digest) -> str | None:
        """Why an entry cannot be acted on in this run, or None: E1, and read under the configuration loaded.

        The one test a label, a binding and a state each pass (plan.md 15.1 item 9). `what` names the
        kind in the words of the refusal.
        """
        if grade != "E1":
            shown = grade or f"unknown (the registry file carries no entry {ref!r})"
            return (f"{head}, graded {shown}: only a {what} this system read here (E1) commands a "
                    "device")
        loaded = self.loaded_config_sha256
        if digest is None:
            return (f"{head}, which names its configuration only in prose: it carries no "
                    f"{ENTRY_DIGEST_IDENTIFIER}, so the {what} cannot be tied to the configuration "
                    "this run loaded")
        if loaded is None:
            return (f"{head}, read under configuration sha256 {digest}; no approved configuration "
                    "is loaded in this run to compare it with")
        if digest != loaded:
            return (f"{head}, read under configuration sha256 {digest}; this run loaded the "
                    f"approved original with sha256 {loaded}. A {what} read under another "
                    "configuration commands nothing")
        return None

    @staticmethod
    def _identifier_refusal(head: str, facts: dict, expected: dict) -> str | None:
        """An entry that names another label, property, quantity or unit than its row copied is not used."""
        for key, want in expected.items():
            got = facts.get(key)
            if got != want:
                return f"{head}: its entry carries {key} {got!r} and the row says {want!r}"
        return None

    @staticmethod
    def _binding_head(binding: dict) -> str:
        return (f"the binding of {binding['quantity']!r} on {binding['name']!r} "
                f"({binding['property']!r} through entry {binding['entry_ref']!r})")

    def binding_step(self, binding: dict) -> tuple[Fraction | None, str | None]:
        """(the binding's step as an exact fraction, why not): its own step, in its own unit (card 098).

        Silence about the step does not mean any value, so a binding with none, with a step in
        another unit or with one that is not a positive number cannot be written through.
        """
        head = self._binding_head(binding)
        step = binding.get("step")
        if not isinstance(step, dict):
            return None, f"{head} carries no step, and a value is written only to a multiple of one"
        if step.get("unit") != binding["unit"]:
            return None, (f"{head} carries a step in {step.get('unit')!r}, not in the binding's unit "
                          f"{binding['unit']!r}")
        exact = _exact_number(step.get("value"))
        if exact is None or exact <= 0:
            return None, f"{head} carries a step of {step.get('value')!r}: a step is a positive number"
        return exact, None

    def binding_refusal(self, binding: dict) -> str | None:
        """Why a binding may not be written through, or None. One grade for every binding: E1 under this run's digest."""
        label = (self.mm_label(binding["name"]) or {}).get("label")
        head = self._binding_head(binding)
        why = self._entry_refusal("binding", head, binding["entry_ref"], binding["grade"],
                                  binding["config_sha256"])
        return why or self._identifier_refusal(head, binding["identifiers"], {
            "mm_label": label, "mm_property": binding["property"],
            "quantity": binding["quantity"], "unit": binding["unit"]})

    def state_refusal(self, state: dict) -> str | None:
        """Why a state resolution may not be used, or None. The same grade and digest as a label."""
        label = (self.mm_label(state["name"]) or {}).get("label")
        head = (f"the state {state['word']!r} of {state['name']!r} "
                f"({state['state_label']!r} through entry {state['entry_ref']!r})")
        why = self._entry_refusal("state", head, state["entry_ref"], state["grade"],
                                  state["config_sha256"])
        return why or self._identifier_refusal(head, state["identifiers"], {
            "mm_label": label, "path_word": state["word"], "mm_state_label": state["state_label"]})

    def calibration_for(self, label: str, prop: str, quantity: str) -> dict | None:
        """The snapshot's calibration entry for a label, property and quantity, found by its identifiers.

        A calibration is its own entry and is never on the row. Several are not resolved by choosing
        one: the snapshot carrying two for the same triple is refused where it is asked.
        """
        found = []
        for ref, held in self.entries.items():
            try:
                entry = json.loads(held["text"]) if isinstance(held.get("text"), str) else held
            except (ValueError, AttributeError):
                continue
            ids = entry.get("identifiers") or {}
            if (entry.get("kind") == "calibration" and ids.get("mm_label") == label
                    and ids.get("mm_property") == prop and ids.get("quantity") == quantity):
                found.append({"entry_ref": ref, "grade": entry.get("grade"),
                              "valid_until": entry.get("valid_until"),
                              "validity": entry.get("validity"),
                              "conversion": entry.get("conversion")})
        if len(found) > 1:
            raise GapError(f"the snapshot holds {len(found)} calibrations for {quantity!r} of "
                           f"{label!r}.{prop}: {[f['entry_ref'] for f in found]}")
        return found[0] if found else None

    def convert_for_binding(self, value, unit: str, binding: dict) -> tuple[object, str | None, str | None]:
        """(written value, calibration entry used, why not): `convert_detail` without the detail."""
        detail, ref, why = self.convert_detail(value, unit, binding)
        return (detail["written"] if detail else None), ref, why

    def convert_detail(self, value, unit: str, binding: dict) -> tuple[dict | None, str | None, str | None]:
        """(detail, calibration entry used, why not): a plan's number in the binding's unit, on its step.

        Three routes and no formula here. Unchanged when the unit matches; an exact factor read from
        contracts/units.json when both units are there with one dimension; otherwise an unexpired E2
        calibration from the snapshot whose range covers the value and whose points convert it. Every
        route ends the same way, in exact fractions: rounded to the nearest multiple of the binding's
        step, ties to even (card 098). The detail carries what was written and what it was before
        rounding, the step, and on the calibration route the value in the form's physical unit.
        """
        step, why = self.binding_step(binding)
        if why:
            return None, None, why
        target = binding["unit"]
        number = _exact_number(value)

        def detail(unrounded: Fraction, physical=None, physical_unit=None) -> dict:
            return {"written": _number_out(round(unrounded / step) * step),
                    "unrounded": _number_out(unrounded), "step": dict(binding["step"]),
                    "physical_value": None if physical is None else _number_out(physical),
                    "physical_unit": physical_unit}

        if unit == target:
            if number is None:
                return None, None, f"{value!r} {unit!r} is not a number"
            return detail(number), None, None
        factor = _exact_factor(unit, target)
        if factor is not None:
            if number is None:
                return None, None, f"{value!r} {unit!r} is not a number"
            return detail(number * factor), None, None
        label = (self.mm_label(binding["name"]) or {}).get("label")
        need = (f"a calibration of {binding['quantity']!r} for {label}.{binding['property']} "
                f"covering {value} {unit} (the plan's unit is not the property's {target!r} and "
                "contracts/units.json holds no exact factor between them)")
        found = self.calibration_for(label, binding["property"], binding["quantity"])
        if found is None:
            return None, None, f"needs {need}; the snapshot holds none"
        ref = found["entry_ref"]
        if found["grade"] != "E2":
            return None, ref, f"needs {need}; calibration {ref!r} is graded {found['grade']}, not E2"
        until = found["valid_until"]
        date = until.get("date") if isinstance(until, dict) else None
        try:
            expired = date is None or datetime.fromisoformat(str(date)).date() < datetime.now(timezone.utc).date()
        except ValueError:
            expired = True
        if expired:
            return None, ref, f"needs {need}; calibration {ref!r} is expired or carries no date ({date!r})"
        if not (isinstance(until, dict) and until.get("no_event")):
            return None, ref, (f"needs {need}; calibration {ref!r} is valid only until an event the "
                               "runtime cannot check, and ambiguity stops")
        span = (found["validity"] or {}).get(binding["quantity"]) if isinstance(found["validity"], dict) else None
        lo = _exact_number(span.get("min")) if isinstance(span, dict) else None
        hi = _exact_number(span.get("max")) if isinstance(span, dict) else None
        span_unit = span.get("unit") if isinstance(span, dict) else None
        in_span = None
        if number is not None and lo is not None and hi is not None:
            span_factor = _exact_factor(unit, span_unit)
            if span_factor is None:
                return None, ref, (f"needs {need}; calibration {ref!r} is valid in {span_unit!r} and "
                                   f"contracts/units.json holds no exact factor between {unit!r} and "
                                   f"{span_unit!r}")
            in_span = number * span_factor
        if in_span is None or not lo <= in_span <= hi:
            return None, ref, (f"needs {need}; calibration {ref!r} covers {span!r}, which does not "
                               "cover it")
        return self._by_points(found, need, number, unit, binding, detail)

    @staticmethod
    def _by_points(found: dict, need: str, number: Fraction, unit: str, binding: dict, detail):
        """Apply a calibration's `piecewise_linear_within_points` form to a number, in exact fractions.

        Only that form and only that direction. The points are read, never fitted, and a value outside
        the first and last of them is refused rather than extended. The range the calibration is good
        over is `validity`'s and was checked before this.
        """
        ref = found["entry_ref"]
        form = found.get("conversion")

        def refuse(field: str, what: str):
            return None, ref, f"needs {need}; calibration {ref!r}: {field} {what}"

        if not isinstance(form, dict):
            return None, ref, (f"needs {need}; calibration {ref!r} covers it but carries no conversion "
                               "form the runtime can apply, and it holds no formula of its own")
        if form.get("direction") != "physical_to_control":
            return refuse("conversion.direction", f"is {form.get('direction')!r}; the runtime applies "
                          "only 'physical_to_control'")
        if form.get("rule") != "piecewise_linear_within_points":
            return refuse("conversion.rule", f"is {form.get('rule')!r}; the runtime applies only "
                          "'piecewise_linear_within_points'")
        physical, control = form.get("physical"), form.get("control")
        got = physical.get("quantity") if isinstance(physical, dict) else physical
        if got != binding["quantity"]:
            return refuse("conversion.physical.quantity", f"is {got!r}, not {binding['quantity']!r}")
        got = control.get("unit") if isinstance(control, dict) else control
        if got != binding["unit"]:
            return refuse("conversion.control.unit", f"is {got!r}, not the binding's {binding['unit']!r}")
        p_unit, c_unit = physical.get("unit"), control["unit"]
        points = form.get("points")
        if not isinstance(points, list) or len(points) < 2:
            return refuse("conversion.points", "is not a list of at least two points")
        xs, ys = [], []
        for i, pt in enumerate(points):
            at = f"conversion.points[{i}]"
            for side, unit_want, store in (("physical", p_unit, xs), ("control", c_unit, ys)):
                part = pt.get(side) if isinstance(pt, dict) else None
                if not isinstance(part, dict) or part.get("unit") != unit_want:
                    return refuse(f"{at}.{side}.unit", f"is not the form's {unit_want!r}")
                exact = _exact_number(part.get("value"))
                if exact is None:
                    return refuse(f"{at}.{side}.value", f"is {part.get('value')!r}, not a number")
                store.append(exact)
            if i and xs[i] <= xs[i - 1]:
                return refuse(f"{at}.physical", "does not increase over the point before it")
            if i and (ys[i] == ys[i - 1] or (i > 1 and (ys[i] > ys[i - 1]) != (ys[1] > ys[0]))):
                return refuse(f"{at}.control", "does not keep to one direction over the points before it")
        factor = _exact_factor(unit, p_unit)
        if factor is None:
            return None, ref, (f"needs {need}; calibration {ref!r} converts from {p_unit!r} and "
                               f"contracts/units.json holds no exact factor between {unit!r} and "
                               f"{p_unit!r}")
        x = number * factor
        if not xs[0] <= x <= xs[-1]:
            return None, ref, (f"needs {need}; calibration {ref!r}: {_number_out(x)} {p_unit} is "
                               f"outside its points, which span {_number_out(xs[0])} to "
                               f"{_number_out(xs[-1])} {p_unit}")
        i = next(k for k in range(len(xs) - 1) if x <= xs[k + 1])
        control_value = ys[i] + (x - xs[i]) * (ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i])
        return detail(control_value, x, p_unit), ref, None

    def camera_label(self, channel_id: str) -> str | None:
        """The device name the tap keys a camera channel's frames by: its label, or None and why.

        The call's own channel is what is looked up, never a name read from a frame's metadata. A
        channel with no label taps nothing, and the run's log and the tap's reply name the missing
        label.
        """
        found = self.mm_label(channel_id)
        if found is not None:
            return found["label"]
        if channel_id not in self.tap_unlabelled:
            why = (f"{channel_id!r} has no Micro-Manager label in the registry "
                   f"({self.registry_source}), so its frames are not tapped")
            self.tap_unlabelled[channel_id] = why
            self.record(event="frame_tap_unlabelled", channel=channel_id, reason=why)
        return None

    def set_config_digest_by_hand(self, sha256: str | None) -> None:
        """Mock only: stand for the approved original configuration this run would have loaded.

        On mock no file is loaded, so a test names the digest the mock stands for, the way it gives a
        selector its position. It is not a command, it is not reachable from a plan or the console,
        and on the instrument the only digest is the one the operator read from the approved file.
        """
        if self.backend != "mock":
            raise InterlockError(
                "refusing to set the loaded configuration's digest by hand: this is not the mock "
                "backend, and nothing here may stand for a configuration that was not loaded")
        self.loaded_config_sha256 = sha256
        self.record(event="config_digest_set_by_hand", loaded_config_sha256=sha256,
                    note="set by a test for the mock; no configuration file was loaded")

    def _tap_frame(self, image, metadata, camera: str | None = None) -> None:
        tap = getattr(self, "_tap", None)
        if tap is not None:
            tap.put(image, metadata, self.clock.offset(), camera)
        ring = getattr(self, "_pre_stop", None)
        if ring is not None:
            try:
                ring.put(image, metadata, self.clock.offset())
            except Exception:                           # noqa: BLE001 - the run never pays for the buffer
                pass
        watcher = getattr(self, "_watcher", None)
        if watcher is not None:
            try:
                watcher.put_frame(image, metadata, self.clock.offset())
            except Exception:                           # noqa: BLE001 - the run never pays for the watcher
                pass
        judgements = getattr(self, "_judgements", None)
        if judgements is not None:
            try:
                judgements.put_frame(image, metadata, self.clock.offset())
            except Exception:                           # noqa: BLE001 - nor for a judgement
                pass

    def reach_point(self, point: str) -> None:
        """The run is at `point` (card 081): the judgements the plan names there are asked. They record only.

        Nothing here returns a value the run reads, and a failure inside is kept for run_ended's detail and
        never raised: no answer reaches a move, a skip, a retry, the stop channel or the person.
        """
        judgements = getattr(self, "_judgements", None)
        if judgements is None:
            return
        try:
            judgements.reach(point, self.clock.offset())
            self._drain_judgements()
        except Exception as exc:                        # noqa: BLE001 - the run never pays for a judgement
            self._judgements_failure = f"{type(exc).__name__}: {exc}"

    def _drain_judgements(self) -> None:
        judgements = getattr(self, "_judgements", None)
        if judgements is not None:
            for event in judgements.drain():
                self.record(**event)

    def _judge_stop(self, reason: str) -> None:
        """DM-4, after the abort and the save, once per run. It reads the saved window and acts on nothing."""
        judgements = getattr(self, "_judgements", None)
        if judgements is None or getattr(self, "_judge_stopped", False):
            return
        self._judge_stopped = True
        try:
            ring = getattr(self, "_pre_stop", None)
            window = [] if ring is None else ring.window()
            saved = None
            for event in reversed(list(self.log)):
                if event.get("event") == "pre_stop_buffer_saved":
                    saved = dict(event["buffer"])
                    break
                if event.get("event") == "pre_stop_buffer_not_saved":
                    saved = {"why": event.get("why")}
                    break
            recent = [e.get("event") for e in list(self.log)[-20:]]
            judgements.stopped(reason, window, saved, recent, self.clock.offset())
            self._drain_judgements()
        except Exception as exc:                        # noqa: BLE001 - the run never pays for a judgement
            self._judgements_failure = f"{type(exc).__name__}: {exc}"

    def acquire_sequence(self, channel_id: str, n: int, sink, timeout_s: float | None = None):
        """The channel's own sequence(), with the run's sink teed into the frame tap.

        The run's sink is called FIRST, with the frame exactly as it came; the
        tap's copy is taken after it returns, so nothing the tap does can reach
        the run's data. The tap adds no camera call: this is the run's
        acquisition, and the tee is the only thing added to it.
        """
        camera = self.camera_label(channel_id)          # the call's own camera, never the metadata's

        def tee(i, image, metadata):
            sink(i, image, metadata)
            self._tap_frame(image, metadata, camera)
        module = self.module_for(channel_id)
        sequence_for = getattr(module, "sequence_for", None)
        if sequence_for is not None:
            return sequence_for(channel_id, n, tee, timeout_s=timeout_s)
        return module.sequence(n, tee, timeout_s=timeout_s)

    def acquire_snap(self, channel_id: str):
        """The channel's own snap(); its frame is copied into the tap and returned unchanged."""
        module = self.module_for(channel_id)
        snap_for = getattr(module, "snap_for", None)
        image, metadata = snap_for(channel_id) if snap_for is not None else module.snap()
        self._tap_frame(image, metadata, self.camera_label(channel_id))
        return image, metadata

    #: Frames the mock takes for an acquisition that is a series. Synthetic: no plan's frame count.
    MOCK_SERIES_FRAMES = 3

    def _mock_acquire(self, channel_id: str, command) -> None:
        """What a plan's acquiring command does on the mock: it takes frames, through the run's own tee.

        `apply` alone moves no frame, so a mock run of a plan that acquires on a camera showed the
        console nothing (card 086 item 1). The frames go through acquire_snap / acquire_sequence,
        the one acquisition path the tap is fed from, and the run discards them: no plan field
        says where a mock frame would be written. On hardware an acquisition is not driven from
        here, so nothing else calls this.
        """
        if command.action in ("snap", "acquire"):
            self.acquire_snap(channel_id)
            return
        wanted = command.frame_count or self.MOCK_SERIES_FRAMES
        got = self.acquire_sequence(channel_id, wanted, lambda i, image, metadata: None)
        if command.frame_count is not None:
            self._check_frame_count(command, got)

    def _check_frame_count(self, command, returned) -> None:
        """The frames a plan's `frame_count` asked for against the frames the sequence returned (card 095).

        Counted by image number, so a frame delivered twice counts once and a gap is a missing
        frame. Fewer frames is a logged disagreement and not a refusal: the frames are taken and
        the run says it did not get all it asked for. It is its own event with `plan_field` and no
        `from`, so check 66 does not read it as a second dispatch of the command.
        """
        numbers = returned.get("image_numbers") if isinstance(returned, dict) else None
        counted = len(set(numbers)) if numbers is not None else None
        if counted is not None and counted >= command.frame_count:
            self.record(event="frame_count_verified", plan_field=command.from_field,
                        wanted=command.frame_count, counted=counted)
            return
        self.record(event="frame_count_disagreed", plan_field=command.from_field,
                    wanted=command.frame_count, counted=counted,
                    note=("fewer frames came back than the plan asked for, counted by image number"
                          if counted is not None else
                          "the sequence returned no image numbers, so no frames could be counted"))

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
        resolved: dict[str, dict] = {}
        for command in commands:
            settings = command.settings or (command.params or {}).get("settings") or {}
            why = mm.refusal(None, None, command.action)
            if why:
                refused.append(f"{command.from_field}: {why}")
            for name in self._names_reached(command):
                why = self._motion_refusal(name, None, None, mm, resolved, command.from_field)
                if why:
                    refused.append(f"{command.from_field}: {why}")
            for device, props in settings.items():
                for prop, value in (props or {}).items():
                    why = self._motion_refusal(str(device), str(prop), value, mm, resolved,
                                               command.from_field)
                    if why:
                        refused.append(f"{command.from_field}: settings {device}.{prop}: {why}")
        facts = {"resolved": list(resolved.values()),
                 "loaded_config_sha256": self.loaded_config_sha256}
        if refused:
            self.record(event="software_motion_refused", commands=len(commands),
                        refusals=refused, **facts)
            raise InterlockError(
                f"refusing the whole plan before any command goes out: {len(refused)} "
                "refusal(s). " + " | ".join(refused))
        self.record(event="software_motion_checked", commands=len(commands),
                    allowed=sorted(mm.SOFTWARE_MAY_COMMAND), **facts)

    def _names_reached(self, command: Command) -> list[str]:
        """The names one command reaches: its element when one is named, else its channel.

        A registry channel with an element named is the container of that element and the element is
        the device, so the element is the name that is resolved; a channel the registry does not hold
        is a name written as it is and is asked as written beside the element.
        """
        element = command.element
        if element and element != command.channel:
            return ([] if command.channel in self.names else [command.channel]) + [element]
        return [command.channel]

    def _motion_refusal(self, name: str, prop: str | None, value, mm, resolved: dict,
                        from_field: str) -> str | None:
        """Why this name may not be commanded, or None. The policy is micromanager.refusal's and this
        decides only whether the name is a label this system may use.

        A name that is not a registry name, or is already a label the allow-list holds, is asked as
        written, exactly as before: a plan that writes `ZDrive` fails as a plan commanding the focus
        drive. A registry name is a name and never a label, so it is asked through the label the
        registry gives it, and a label is used only when its entry is E1 and names the configuration
        this run loaded (plan.md 15.1 item 9).
        """
        if name in mm.SOFTWARE_MAY_COMMAND or name not in self.names:
            return mm.refusal(name, prop, "setProperty", value)
        found = self.mm_label(name)
        if found is None:
            return f"{name!r} has no Micro-Manager label in the registry ({self.registry_source})"
        label, ref = found["label"], found["entry_ref"]
        resolved.setdefault(name, {**found, "loaded_config_sha256": self.loaded_config_sha256,
                                   "from": from_field})
        why = mm.refusal(label, prop, "setProperty", value)
        if why:
            return f"{name!r} is the label {label!r}: {why}"
        head = f"{name!r} reaches the label {label!r} through entry {ref!r}"
        return self._entry_refusal("label", head, ref, found["grade"], found["config_sha256"])

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

    def check_required_states(self, required: list[dict]) -> None:
        """Read each required state and compare it with the plan's value; refuse the whole plan on any miss.

        A selector on a device software may not command is a state the plan needs and nothing here
        writes: after preflight and before the first action each element is READ, and the state label
        the plan's word resolved to must be what came back (card 095). A mismatch, an element that was
        not read, or a read that failed refuses, naming the element. Nothing is sent: this is a read.
        """
        rows, refused = [], []
        for item in required:
            element = item["element"]
            got, note = None, None
            try:
                cid, inner = self.resolve(element)
                if inner is None:
                    note = f"{element!r} is a channel, not an element whose state is read"
                else:
                    got = (self._read_channel(cid, wait=True).get("elements") or {}).get(inner)
            except Exception as exc:                        # noqa: BLE001 - recorded, and it refuses
                note = f"the read raised {type(exc).__name__}: {exc}"
            matched = got is not None and str(got) == item["state"]
            rows.append({"element": element, "from": item["from"], "word": item["word"],
                         "state": item["state"], "read": got, "matched": matched})
            if not matched:
                refused.append(f"{item['from']}: {element!r} must read {item['state']!r} "
                               f"(the plan's {item['word']!r}) and "
                               + (f"was not read ({note})" if got is None and note else
                                  "was not read" if got is None else f"reads {got!r}"))
        if refused:
            self.record(event="required_states_refused", states=rows, refusals=refused)
            raise InterlockError("refusing the whole plan before any action: a state it needs is not "
                                 "the one read. " + " | ".join(refused))
        if rows:
            self.record(event="required_states_checked", states=rows)

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

    def _authorise(self, plan: dict):
        """The approval every exemption gate asks for. operator.authorise against this
        tree's approvals/, unless the run set `plan_authoriser` -- which operator.run does
        for a scratch root (card 063), on mock only -- so a gate reads the same approvals
        as the run that called it."""
        authoriser = getattr(self, "plan_authoriser", None)
        decision = authoriser(plan) if authoriser is not None else _operator().authorise(plan)
        # Every ask is logged with the file the reader judged: its path and the sha256 of the bytes
        # it read, taken from the decision and never from a second read of the folder, so a file
        # rewritten between this ask and the run's first one cannot make the log name another.
        fields = {"plan_id": plan.get("id"), "plan_revision": plan.get("revision"),
                  "permitted": decision.permitted,
                  "approval_id": getattr(decision, "approval_id", None),
                  "kind": getattr(decision, "kind", None),
                  "file": getattr(decision, "approval_file", None)}
        if not decision.permitted:
            fields["reasons"] = list(getattr(decision, "reasons", ()))
        self.record(event="authorisation", **fields)
        return decision

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
        decision = self._authorise(plan)
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

    def _read_z(self) -> tuple[float | None, str | None]:
        """The Z encoder through read_z, a read every backend allows: (value, why it failed)."""
        try:
            value = self.module_for(FOCUS_EXEMPT_CHANNEL).read_z()
            return (None if value is None else float(value)), None
        except Exception as exc:                                # noqa: BLE001 - recorded, never fatal
            return None, f"{type(exc).__name__}: {exc}"

    def run_focus_search(self, plan: dict, decide=None, load_safety=None,
                         method_ready=None) -> dict:
        """Walk Z from the retract, one decided branch at a time, refusing at every gate.

        THE GATE'S ORDER IS SAFETY FIRST, METHOD SECOND (card 066), and it stops
        at the first that refuses: (1) the plan revision's approval, (2) the
        hand-over lens, (3) the limits and the range, (4) focus hold, (5) only
        then `method_ready()`, which builds the decider -- the camera ceiling,
        the thresholds -- and (6) the first Z command. A gap ceiling stays a gap
        until the bench count is in the store, and checked first it made every
        refusal read as the ceiling's. A gap depth of field does not refuse:
        the run records that its success criterion cannot be judged.

        The encoder is read through read_z before the gate and again at a
        refusal, and both go in the refusal event; a failed read is recorded
        and the refusal still happens.

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
        z_before, before_failed = self._read_z()
        self.record(event="focus_search_z_before", z_um=z_before, z_read_failed=before_failed,
                    **{"from": "read_z, before the gate"})
        try:
            return self._focus_search(plan, decide, load_safety, method_ready)
        except InterlockError as exc:
            z_at, at_failed = self._read_z()
            self.record(event="focus_search_refused", reason=str(exc),
                        z_before_um=z_before, z_at_refusal_um=z_at,
                        z_read_failed="; ".join(f for f in (before_failed, at_failed) if f) or None)
            raise
        finally:
            self._focus_expected = None

    def _focus_search(self, plan: dict, decide, load_safety, method_ready=None) -> dict:
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

        # -- before the first Z command, in the card 066 order -------------- #
        # (1) the plan revision's approval. The Z exemption asks it again at
        # every move; asking here first makes "not approved" a refusal of its
        # own, with the encoder read around it, rather than whatever came next.
        decision = self._authorise(plan)
        if not decision.permitted:
            raise InterlockError("the focus-search plan is not approved for this revision: "
                                 + "; ".join(decision.reasons))
        # (2) the hand-over lens
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
        pfs = pfs_not_engaged(load_safety())
        device, prop, offs = pfs["device"], pfs["property"], pfs["values"]
        try:
            reading = module.read_property(device, prop)
        except Exception as exc:                                # noqa: BLE001 - unreadable refuses
            reading, unreadable = None, f"{type(exc).__name__}: {exc}"
        else:
            unreadable = None
        self.record(event="focus_search_pfs_read", device=device, property=prop,
                    read=reading, not_engaged_values=offs, unreadable=unreadable,
                    **{"from": "envelope pfs_not_engaged"})
        if reading is None or str(reading) not in offs:
            raise InterlockError(f"PFS reads {device}.{prop} = {reading!r}"
                                 + (f" ({unreadable})" if unreadable else "")
                                 + f", not one of {offs}: it may be engaged, and a held focus "
                                 "fights a sweep. The person switches PFS off")

        # (5) only now the method's own readiness: the camera ceiling, the
        # verdict's thresholds, the decider. Every safety check has passed.
        if method_ready is not None:
            decide = method_ready()
        if decide is None:
            raise InterlockError("no decider: the plan's method is not ready")
        dof = ((fs.get("success") or {}).get("depth_of_field") or {})
        if "gap" in dof:
            # A gap depth of field does not refuse the run (card 066, check 88):
            # its success criterion cannot be judged, and the run says so.
            self.record(event="focus_success_not_judgeable", gap=dof["gap"],
                        note="the depth of field is a gap, so the success tolerance, a fraction "
                             "of it, cannot be judged; the search itself runs")

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
        decision = self._authorise(plan)
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
        decision = self._authorise(plan)
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
                            apply_for = getattr(module, "apply_for", None)
                            # What the derivation wrote for the device goes to the device beside the
                            # plan's numbers; the log keeps the two apart (card 095).
                            sent = ({**command.params, "settings": command.settings}
                                    if command.settings else command.params)
                            value = apply_for(cid, sent) if apply_for else module.apply(sent)
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
                            if command.settings:
                                detail["settings_sent"] = command.settings
                                detail["written"] = command.written
                            self.record(event="apply", channel=cid, element=command.element,
                                        action=command.action, params=command.params,
                                        verification=verification, verification_note=why,
                                        **detail, **{"from": command.from_field})
                            if (command.acquires and self.backend == "mock"
                                    and cid in getattr(self.module_for(cid), "CAMERAS", ())):
                                self._mock_acquire(cid, command)
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
        ring = getattr(self, "_pre_stop", None)
        if ring is not None:
            ring.stop_at(self.clock.offset())           # the window ends where the stop began (card 082)
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
                    "commanded": None, "read_back": None, "closed": None, "backend": None,
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
        # THE SAVE COMES LAST (plan.md 4.6.1, card 082): lamps off and shutters closed and read back are
        # already in the log above, and nothing here sends a command to anything.
        self._save_pre_stop()
        # DM-4 comes after the save and nothing waits on it (plan.md 13.5): it is asked on a thread and
        # recorded, and it starts no recovery.
        self._judge_stop(reason)
        return report

    #: The saved window, one file in the run folder: one JSON line (this format, the plan's length, the
    #: instant the stop began, and one entry per frame -- index, t_mono, byte count, shape, dtype and the
    #: acquisition's metadata), then each frame's bytes in that order.
    PRE_STOP_FILE = "pre_stop_buffer.frames"
    PRE_STOP_FORMAT = "pre-stop-buffer-1"

    def _save_pre_stop(self) -> None:
        """Save the ring whole after an abort, or say why not. Once per run, never retried, never raises.

        A save sends no command and asks for no frame: it writes copies the run already made. A failure is
        a record (`pre_stop_buffer_not_saved`, why `save_failed`) and not a second attempt, and nothing
        here can reach a light.
        """
        length = self.pre_stop_length_s
        if length is None or self._pre_stop_handled:
            return
        self._pre_stop_handled = True
        said = {"from": "pre_stop_buffer", "length_s": length, "frames": 0}
        try:
            ring = getattr(self, "_pre_stop", None)
            if ring is None:
                self.record(event="pre_stop_buffer_not_saved", why="no_run_folder", **said)
                return
            if length == 0:
                self.record(event="pre_stop_buffer_not_saved", why="length_zero", **said)
                return
            window = ring.window()
            if not window:
                self.record(event="pre_stop_buffer_not_saved", why="no_frames", **said)
                return
            entries, bodies = [], []
            for index, t_mono, frame, metadata in window:
                if hasattr(frame, "tobytes"):
                    body, shape, dtype = frame.tobytes(), list(getattr(frame, "shape", [])), str(frame.dtype)
                else:
                    body, shape, dtype = bytes(frame), [len(frame)], "bytes"
                entries.append({"index": index, "t_mono": t_mono, "bytes": len(body), "shape": shape,
                                "dtype": dtype, "metadata": metadata})
                bodies.append(body)
            stopped = ring._stop_t
            header = json.dumps({"format": self.PRE_STOP_FORMAT, "length_s": length,
                                 "stopped_at_t_mono": stopped, "frames": entries}, default=str)
            data = header.encode("utf-8") + b"\n" + b"".join(bodies)
            (Path(self._folder) / self.PRE_STOP_FILE).write_bytes(data)
            first, last = window[0], window[-1]
            span = last[1] - first[1]
            rate = (len(window) - 1) / span if len(window) >= 2 and span > 0 else None
            self.record(event="pre_stop_buffer_saved", **{"from": "pre_stop_buffer"}, buffer={
                "length_s": length, "frames": len(window), "recorded_rate_hz": rate,
                "first_frame_index": first[0], "last_frame_index": last[0], "path": self.PRE_STOP_FILE,
                "sha256": "sha256:" + hashlib.sha256(data).hexdigest()})
        except Exception as exc:                            # noqa: BLE001 - recorded, never retried
            try:
                self.record(event="pre_stop_buffer_not_saved", why="save_failed",
                            detail=f"{type(exc).__name__}: {exc}", **said)
            except Exception:                               # noqa: BLE001
                pass

    def _close_shutter(self, cid: str, element: str, entry: dict | None) -> dict:
        """One recognised shutter's row: what was sent, what came back, what that shows.

        `closed` is True or False only from the backend's own read-back of
        the declared pair, the way `_power_down()` judges `matched`. A call
        that returned with nothing read back gives `closed: None`, never
        True -- the defect this replaces wrote True on the call returning,
        including through micromanager, where the call wrote nothing.
        A failure is recorded and the abort goes on.
        """
        # `backend` is the module that answered, read from what it returned and
        # never assumed (card 065): a `closed: true` from mock is mock repeating
        # what it was told, and a reader takes true as a confirmation only when
        # backend is not mock. None means nothing answered.
        row = {"channel": cid, "element": element, "identified": True,
               "commanded": None, "read_back": None, "closed": None, "backend": None}
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
        row["backend"] = returned.get("backend")
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
                   "commanded": None, "read_back": None, "matched": None, "backend": None}
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
            row["backend"] = returned.get("backend")       # who answered (card 065)
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

    def watcher_snapshot(self, t_mono: float | None = None) -> dict:
        """The watcher's snapshot (card 076 part C): `read(wait=False)` and nothing else.

        Only channels this run's preflight reached are read: their interfaces were opened after the
        ownership check passed, and a channel this run did not open is recorded as not open, never
        opened to be read. A read never waits: a channel whose device is busy is recorded as not read,
        with why, and is never carried forward as its last value. Once an abort has begun it reads nothing.
        The snapshot is one `snapshot` event labelled `watcher`, so the reads are in the log for every reader.
        """
        began = self.clock.offset() if t_mono is None else t_mono
        states: dict[str, dict] = {}
        for cid in self.channels:
            if self._aborted.is_set():
                states[cid] = {"not_read": True, "why": "an abort began, so no more reads were taken"}
            elif cid not in self._preflight_state:
                states[cid] = {"not_open": True, "why": ("this run's preflight did not reach this channel, so its "
                                                         "interface was not opened and is not opened to be read")}
            else:
                try:
                    states[cid] = self._read_channel(cid, wait=False)
                except Exception as exc:                # noqa: BLE001 - an unread channel is a fact
                    states[cid] = {"not_read": True,
                                   "why": str(exc) if getattr(exc, "would_wait", False)
                                   else f"{type(exc).__name__}: {exc}"}
        self.record(event="snapshot", label="watcher", t_mono=began, states=states)
        return states

    def _read_channel(self, cid: str, wait: bool) -> dict:
        """One channel's read. A module that reads per channel is asked with the channel's element ids."""
        module = self.module_for(cid)
        read_for = getattr(module, "read_for", None)
        if read_for is None:
            return module.read(wait=wait)
        return read_for(cid, wait=wait, elements=self.channels[cid].element_ids())

    def open_channel(self, cid: str) -> None:
        """Open one channel's interface to read it (card 085). Sends nothing: there is no apply here.

        A module with no `open_for` has nothing to open, and the event says so rather than implying
        an open happened. A failure is raised for the caller to record.
        """
        module = self.module_for(cid)
        open_for = getattr(module, "open_for", None)
        if open_for is not None:
            open_for(cid)
        self.record(event="check_now_open", channel=cid, implicit=open_for is None)

    def close_channel(self, cid: str) -> None:
        module = self.module_for(cid)
        close_for = getattr(module, "close_for", None)
        if close_for is not None:
            close_for(cid)
        self.record(event="check_now_close", channel=cid, implicit=close_for is None)

    def set_element_by_hand(self, channel_id: str, element_id: str, value: object) -> None:
        """Mock only: stand for the person turning one registry element at the instrument.

        This is not a command. It goes through no check, no lock and no `apply`, because on the
        instrument nothing in this program turns these elements; it exists so a screen on mock can
        show an element that something other than the mock set. The event says so, and the id has to
        be one the registry gives this channel -- a name the registry does not hold is not made up.
        """
        if self.backend != "mock":
            raise InterlockError(
                f"refusing to set {element_id!r} on {channel_id!r} by hand: this is not the mock "
                "backend, and nothing here may stand for a hand on the instrument")
        channel = self.channels.get(channel_id)
        if channel is None or element_id not in channel.elements:
            raise GapError(
                f"{element_id!r} is not an element of channel {channel_id!r} in the registry "
                f"(it has {channel.element_ids() if channel else 'no such channel'}); the mock does "
                "not invent one")
        self.module_for(channel_id).set_by_hand(channel_id, element_id, value)
        self.record(event="element_set_by_hand", channel=channel_id, element=element_id, value=value,
                    note="set by a hand on the mock, not by a command; nothing was dispatched")

    def set_mock_connection(self, channel_id: str, state: str) -> None:
        """Mock only, for a test: make one registry channel answer, be absent, or be busy (card 086).

        Not a command and not reachable from the console: the host answers a fixed set of messages
        and none of them names this. It goes through no check and no `apply`, and the event says so,
        so a run log shows the states a test set and a run is never read as a real one. The id has
        to be one the registry holds -- a channel it does not hold is not made up.
        """
        if self.backend != "mock":
            raise InterlockError(
                f"refusing to set a connection state on {channel_id!r}: this is not the mock "
                "backend, and nothing here may make an instrument appear absent or busy")
        if channel_id not in self.channels:
            raise GapError(f"{channel_id!r} is not a channel in the registry; the mock does not invent one")
        self.module_for(channel_id).set_connection(channel_id, state)
        self.record(event="mock_connection_set", channel=channel_id, state=state,
                    note="set by a test on the mock, not by a command; nothing was dispatched")

    def snapshot(self, label: str) -> dict:
        """read() from every channel, gathered into the log around each step."""
        states = {}
        for cid in self.channels:
            try:
                states[cid] = self._read_channel(cid, wait=True)
            except Exception as exc:                            # noqa: BLE001 - an unreadable channel is a fact
                states[cid] = {"error": str(exc)}
        self.record(event="snapshot", label=label, states=states)
        return states
