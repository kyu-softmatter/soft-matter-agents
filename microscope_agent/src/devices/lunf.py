"""The confocal laser combiner, `laser_combiner`: four lines, blanking only.

Card 036, phase A. **Nothing here has touched the hardware.** The only
transport that exists is `MockTransport`; the NI-DAQmx one is not written,
and with no transport bound every function reports not-ready or refuses.

It implements preflight / apply / read / abort, knows only itself and imports
nothing from the agent (7.2 rule 5). Unlike micromanager.py it DOES hold
refusals, because 2.1 rule 9 puts a guard where the command leaves, and for a
laser line that is here: every enable passes through `apply`, and `apply` has
no path to the write that skips the gates. Rule 9 also asks that a way around
be written down where it cannot be closed, so:

**The same lines are reachable through Micro-Manager**, as `LUNF-Blanking` on
the `NIDAQHub`, in the prior project's configurations. micromanager.py refuses
both names today (`NAMED_REFUSALS`). The day either is lifted there, that path
enables a laser line with none of the checks below. Lifting it is a card's
decision, and this is the sentence that card has to answer. A configuration
whose startup preset sets a blanking line is the same door (2.1 rule 10).

## What `laser_combiner` is, and is not, reachable as

- **Blanking and line select**, on digital lines. That is all this file
  writes.
- **Per-line power, never.** The word format the power interface expects is
  undocumented and the store records that it is deliberately not guessed
  (`lunf_per_line_power_is_not_transmittable`, E3). Any power parameter is
  refused, not ignored.
- **Read-back, none.** The registry marks the channel `read_back: false`, and
  a digital-output read-back would be this program's own echo, not the
  shutter's state. So every dispatch records `verification: none`, always:
  `apply` returns no `verified` key and `read` returns what was commanded,
  labelled as commanded, never as state.

## An enable needs five things, and each is its own gate

An enable -- any `apply` that opens a line -- is refused, with nothing
written, unless ALL of these hold. Every failing gate is collected and
reported at once, so a person sees everything that is wrong rather than the
first thing. **No gate permits**: each can only refuse, and the write is
reached only when the list of refusals is empty (2.1 rule 8). A clean
light-path read-back with any other gate failing still refuses.

1. **The person's limit for these lines.** `optical_power_max` in
   `envelope/safety.json` is the trapping laser's dial range at the sample
   plane and says nothing about these lines. Which limit covers them, and at
   what value, is the person's to decide; `COVERING_LIMIT` is `None` until
   the person has said. A named limit absent from the file refuses; one
   present but not confirmed physically refuses too, because an unconfirmed
   limit does not parameterise an exposure a person's eye can take.

   **This gate cannot compare anything against the limit.** Power is not
   transmitted, so this file never knows the level: it is whatever was last
   set by hand. The gate checks that the person's decision exists. That the
   level honours it is the person's to set before the bench.

2. **The approved command list names this enable.** `bind_approval` takes
   the list a person approved and who approved it; the enable must appear in
   it as `device: laser_combiner`, `settings.laser_combiner.enable` equal to
   the lines being opened. This file cannot tell a real approval from a
   fabricated one -- that is `operator.authorise()` and check 85 -- so what it
   guarantees is narrower: no enable leaves here without someone having
   bound a list that names it.

3. **The bench was handed to this seat by the person.** `bind_bench` takes
   who holds it and the person's words. Unbound, every enable refuses. The
   same narrowing as (2) applies: a hand-over happens in a seat's window and
   no code can see it; this gate makes its absence a refusal.

4. **Somewhere to log the read-back.** Rule 11 asks for the light-path
   read-back as its own event immediately before the enable, and a check
   reading run logs for exactly that is to follow. With no log bound
   (`bind_log`, which takes the orchestrator's `record`), an enable would
   leave no trace of its read-back, so it refuses.

5. **A light path, read back NOW, at a state recorded as not reaching the
   eyepieces** (2.1 rule 11). The reader bound by `bind_light_path` is called
   at every enable, never cached, and its answer is logged as
   `light_path_readback` before anything is written. The state must be an
   integer -- never a label -- and must be in the recorded mapping, each
   entry citing the store entry that records it. **In phase A no mapping is
   recorded, so every state counts as reaching the eyepieces** and every
   enable refuses on this ground. Establishing the mapping, with the person,
   is phase B's first job. An unreadable path, a reading that is not a
   read-back, or a reader that raises, all refuse.

Plus the ground under all of it: a transport, a line map and a polarity in
the channel row, and lines no other program holds. The row fields read are
`elements[line_select].lines` (line id -> digital line) and `.open_level` /
`.closed_level`; the registry carries none of them yet, and the prior
project's values are ruled downgrade to the store, not code.

**Closing lines is never refused on (1)-(5)**: taking light away needs no
permission. It does need the ground -- with no polarity known, nothing here
knows which level closes a line, and it says so rather than guessing.

## abort

Blanks **every mapped line**, not only the ones this file opened, and reports
one row per line. Recorded as written, not read back: `verification: none`.
It cannot close the fiber shutter at the source, which nothing here reaches
and which stays open when its controlling program dies (a prior measurement,
E3 at best). A release that says "stated state" has to say that too.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

BACKEND = "lunf"
CHANNEL = "laser_combiner"

#: The person's answer to "which limit covers the confocal lines". None until
#: given. Naming a limit here is not a value and grants nothing by itself: the
#: named limit must then be present in envelope/safety.json and confirmed
#: physically, and it is read from the file at every enable.
COVERING_LIMIT: str | None = None

#: Read at every enable, never cached. Tests point it elsewhere.
ENVELOPE_PATH = Path(__file__).resolve().parents[2] / "envelope" / "safety.json"
BENCH_TARGET = "bench"

_LOCK = threading.Lock()
_ABORTED = False
_ROW: dict | None = None
_TRANSPORT = None
_PATH_READER = None
_EYEPIECE_FREE: dict[int, str] = {}
_APPROVED: list[dict] | None = None
_APPROVED_BY: str | None = None
_BENCH: dict | None = None
_LOG = None
_COMMANDED: dict[str, str] | None = None


class LaserRefused(RuntimeError):
    """An enable refused before anything was written. `.reasons` lists every ground."""

    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)


# --------------------------------------------------------------------------- #
# binding: what this file is told, never what it assumes
# --------------------------------------------------------------------------- #

def use_transport(transport) -> None:
    """Bind the thing that writes digital lines. Phase A binds only MockTransport."""
    global _TRANSPORT
    _TRANSPORT = transport


def bind_light_path(reader, eyepiece_free: dict[int, str]) -> None:
    """Bind the stand's light-path read-back and the recorded eyepiece-free states.

    `reader()` is called at every enable and must return the path selector's
    state as read back from the stand: `{"state": <int>, "read_back": True}`.
    `eyepiece_free` maps each state integer established at the bench as not
    reaching the eyepieces to the store entry that records it. A state with no
    entry behind it is not recorded, so a blank citation is dropped rather
    than trusted, and a key that is not an integer is dropped with it.
    """
    global _PATH_READER, _EYEPIECE_FREE
    _PATH_READER = reader
    _EYEPIECE_FREE = {k: v for k, v in (eyepiece_free or {}).items()
                      if isinstance(k, int) and not isinstance(k, bool)
                      and isinstance(v, str) and v.strip()}


def bind_approval(commands: list[dict] | None, approved_by: str | None) -> None:
    """Bind the command list a person approved, and who approved it in words."""
    global _APPROVED, _APPROVED_BY
    _APPROVED = list(commands) if commands is not None else None
    _APPROVED_BY = approved_by


def bind_bench(holder: str | None, said: str | None) -> None:
    """Bind the bench hand-over: which seat holds it, and the person's words."""
    global _BENCH
    _BENCH = {"holder": holder, "said": said} if holder or said else None


def bind_log(record) -> None:
    """Bind the event recorder; the orchestrator's `record(**fields)` fits."""
    global _LOG
    _LOG = record


def _elements(row: dict | None) -> dict[str, dict]:
    elements = (row or {}).get("elements") or {}
    if isinstance(elements, list):
        return {e.get("id"): e for e in elements if isinstance(e, dict)}
    return dict(elements)


def _wiring(row: dict | None) -> tuple[dict[str, str], object, object, list[str]]:
    """(line map, open level, closed level, what is missing) from the channel row."""
    select = _elements(row).get("line_select") or {}
    lines = select.get("lines") or {}
    missing = []
    if not lines:
        missing.append("elements[line_select].lines, the line id -> digital line map")
    if "open_level" not in select or "closed_level" not in select:
        missing.append("elements[line_select].open_level / closed_level, the blanking polarity")
    return dict(lines), select.get("open_level"), select.get("closed_level"), missing


# --------------------------------------------------------------------------- #
# the gates, one function each so each can be watched failing
# --------------------------------------------------------------------------- #

def _limit_refusal(enable: list[str]) -> str | None:
    """Refuse while the person's limit for these lines is absent or unconfirmed."""
    if COVERING_LIMIT is None:
        return ("the person has not said which limit in envelope/safety.json covers the "
                "confocal lines. optical_power_max is the trapping laser's dial range and does "
                "not cover them, and illumination_power_max is unwritten")
    try:
        envelope = json.loads(Path(ENVELOPE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"envelope/safety.json could not be read ({exc}), so no limit can be found"
    limits = next((t.get("limits") or {} for t in envelope.get("targets") or []
                   if t.get("target") == BENCH_TARGET), {})
    limit = limits.get(COVERING_LIMIT)
    if not isinstance(limit, dict):
        return (f"{COVERING_LIMIT!r} is named as covering the confocal lines and is not in "
                f"envelope/safety.json under target {BENCH_TARGET!r}")
    kind = (limit.get("confirmation") or {}).get("kind")
    if kind != "physical":
        return (f"{COVERING_LIMIT!r} is present with confirmation {kind!r}, not 'physical'. "
                "An unconfirmed limit does not parameterise a laser exposure")
    return None


def _approval_refusal(enable: list[str]) -> str | None:
    """Refuse unless a bound, person-approved command list names exactly this enable."""
    if _APPROVED is None or not (isinstance(_APPROVED_BY, str) and _APPROVED_BY.strip()):
        return "no person-approved command list is bound, so no enable is approved"
    wanted = sorted(enable)
    for c in _APPROVED:
        settings = ((c or {}).get("settings") or {}).get(CHANNEL) or {}
        if (c or {}).get("device") == CHANNEL and sorted(settings.get("enable") or []) == wanted:
            return None
    return f"the approved command list does not name an enable of {wanted} on {CHANNEL}"


def _bench_refusal(enable: list[str]) -> str | None:
    """Refuse unless the person's hand-over of the bench is bound."""
    if not _BENCH or not all(isinstance(_BENCH.get(k), str) and _BENCH[k].strip()
                             for k in ("holder", "said")):
        return ("the bench has not been handed to this seat by the person, and a relayed "
                "hand-over is none")
    return None


def _log_refusal(enable: list[str]) -> str | None:
    """Refuse an enable that could leave no record of its read-back."""
    if _LOG is None:
        return "no log is bound, so the light-path read-back could not be recorded before the enable"
    return None


def _path_refusal(enable: list[str]) -> str | None:
    """Read the light path NOW, log it, and refuse unless its state is recorded eyepiece-free.

    A pass is not permission (2.1 rule 8): it is one empty entry in a list of
    refusals, and the write needs every other gate empty as well.
    """
    if _PATH_READER is None:
        return ("no light-path read-back is bound, so the path cannot be read and an "
                "unreadable path refuses")
    try:
        reading = _PATH_READER()
    except Exception as exc:                                    # noqa: BLE001
        reading, error = None, repr(exc)
    else:
        error = None
    if _LOG is not None:
        _LOG(event="light_path_readback", channel=CHANNEL, for_enable=sorted(enable),
             reading=reading, error=error, recorded_eyepiece_free=sorted(_EYEPIECE_FREE))
    if error is not None:
        return f"the light path could not be read back ({error}), and an unreadable path refuses"
    if not isinstance(reading, dict) or reading.get("read_back") is not True:
        return ("the light path's reading is not a read-back from the stand, so the path "
                "counts as unread")
    state = reading.get("state")
    if isinstance(state, bool) or not isinstance(state, int):
        return (f"the light path read back {state!r}, not an integer state. States are keyed "
                "by integer, never by label")
    if not _EYEPIECE_FREE:
        return (f"the light path reads state {state}, and no state is recorded as not reaching "
                "the eyepieces, so every state counts as reaching them")
    if state not in _EYEPIECE_FREE:
        return (f"the light path reads state {state}, which the recorded mapping does not name "
                f"as eyepiece-free ({sorted(_EYEPIECE_FREE)}), so it counts as reaching them")
    return None


#: Order matters for one reason only: the path is read LAST, so the read-back
#: logged is the one nearest the write.
ENABLE_GATES = (_limit_refusal, _approval_refusal, _bench_refusal, _log_refusal, _path_refusal)


def _ground_refusal(lines: dict, missing: list[str]) -> str | None:
    """Refuse anything that would write while there is nothing sound to write with."""
    if _TRANSPORT is None:
        return "no transport is bound; phase A has only the mock, and nothing is written"
    if missing:
        return "the channel row does not carry " + " and ".join(missing)
    free, why = _TRANSPORT.lines_free(sorted(lines.values()))
    if not free:
        return f"the digital lines are not free ({why}); held lines are reported, not retried"
    return None


# --------------------------------------------------------------------------- #
# the four functions
# --------------------------------------------------------------------------- #

def preflight(channel: dict | None = None) -> dict:
    """Whether this channel can be addressed. Writes nothing, and reports read_back false."""
    global _ROW
    channel = channel or {}
    with _LOCK:
        _ROW = channel
    lines, _, _, missing = _wiring(channel)
    report = {"channel": channel.get("id", CHANNEL), "backend": BACKEND,
              "read_back": False, "automatable": channel.get("automatable"),
              "aborted": _ABORTED, "lines": sorted(lines)}
    why = _ground_refusal(lines, missing)
    report.update(ready=why is None)
    if why:
        report["reason"] = why
    return report


def apply(params: dict) -> dict:
    """Set which lines are open: `{"enable": [<line id>, ...]}`, every other line closed.

    `{"enable": []}` closes all. Closes are written before opens, so light
    goes down before it goes up. Nothing is read back, and the return says so.
    """
    if _ABORTED:
        raise RuntimeError("aborted: this backend refuses commands until it is reset")
    params = dict(params or {})
    unknown = sorted(k for k in params if k != "enable")
    if unknown:
        raise LaserRefused([
            f"{k!r} is refused: per-line power is not transmitted "
            "(lunf_per_line_power_is_not_transmittable), and a parameter this file does not "
            "write is refused rather than ignored" for k in unknown])
    if not isinstance(params.get("enable"), (list, tuple)):
        raise LaserRefused(["'enable' must list the lines to open; [] closes all"])
    enable = sorted(set(params["enable"]))
    lines, open_level, closed_level, missing = _wiring(_ROW)
    reasons = []
    unmapped = sorted(set(enable) - set(lines))
    if unmapped and not missing:
        reasons.append(f"line(s) {unmapped} are not in the channel row's line map {sorted(lines)}")
    why = _ground_refusal(lines, missing)
    if why:
        reasons.append(why)
    if enable:
        reasons += [why for gate in ENABLE_GATES if (why := gate(enable))]
    if reasons:
        if enable and _LOG is not None:
            _LOG(event="laser_enable_refused", channel=CHANNEL, lines=enable, reasons=reasons)
        raise LaserRefused(reasons)

    global _COMMANDED
    written = []
    with _LOCK:
        order = sorted(lid for lid in lines if lid not in enable) + enable
        for lid in order:
            level = open_level if lid in enable else closed_level
            _TRANSPORT.write_level(lines[lid], level)
            written.append({"line": lid, "digital_line": lines[lid], "level": level,
                            "open": lid in enable})
        _COMMANDED = {w["line"]: ("open" if w["open"] else "closed") for w in written}
    if enable:
        _LOG(event="laser_enable", channel=CHANNEL, lines=enable, verification="none")
    return {"applied": written, "verification": "none", "backend": BACKEND,
            "why_none": ("laser_combiner cannot be read back: these levels were written and "
                         "nothing queried the lines after")}


def read() -> dict:
    """What was last commanded, labelled as commanded. There is no state to read."""
    with _LOCK:
        commanded = dict(_COMMANDED) if _COMMANDED is not None else None
    return {"state": None, "commanded": commanded, "verification": "none",
            "aborted": _ABORTED, "backend": BACKEND,
            "note": ("a digital-output read-back would be this program's own echo, not the "
                     "shutter's state, so nothing here is reported as state")}


def abort() -> dict:
    """Stop, then blank every mapped line, one row per line. Written, not read back."""
    global _ABORTED, _COMMANDED
    _ABORTED = True
    lines, _, closed_level, missing = _wiring(_ROW)
    report = {"aborted": True, "backend": BACKEND, "verification": "none", "blanked": [],
              "not_reachable": ("the fiber shutter at the source: nothing here reaches it, "
                                "and it stays open when its controlling program dies")}
    if _TRANSPORT is None or missing:
        report["could_not_blank"] = ("no transport is bound" if _TRANSPORT is None else
                                     "the channel row does not carry " + " and ".join(missing))
        return report
    with _LOCK:
        for lid in sorted(lines):
            row = {"line": lid, "digital_line": lines[lid], "level": closed_level}
            try:
                _TRANSPORT.write_level(lines[lid], closed_level)
                row["written"] = True
            except Exception as exc:                            # noqa: BLE001
                row.update(written=False, error=repr(exc))
            report["blanked"].append(row)
        _COMMANDED = {r["line"]: "closed" for r in report["blanked"] if r["written"]}
    report["note"] = (f"{sum(r['written'] for r in report['blanked'])} of {len(lines)} lines "
                      "written closed; none read back")
    return report


def reset() -> None:
    """Not part of the interface. Test scaffolding, and only that."""
    global _ABORTED, _ROW, _TRANSPORT, _PATH_READER, _EYEPIECE_FREE, _COMMANDED
    global _APPROVED, _APPROVED_BY, _BENCH, _LOG
    with _LOCK:
        _ABORTED, _ROW, _TRANSPORT, _PATH_READER = False, None, None, None
        _EYEPIECE_FREE, _COMMANDED = {}, None
        _APPROVED, _APPROVED_BY, _BENCH, _LOG = None, None, None, None


class MockTransport:
    """Records every write. `held_by` stands in for another program holding the lines."""

    def __init__(self, held_by: str | None = None, fail_on: set[str] | None = None):
        self.writes: list[tuple[str, object]] = []
        self.held_by = held_by
        self.fail_on = set(fail_on or ())

    def lines_free(self, digital_lines: list[str]) -> tuple[bool, str]:
        if self.held_by:
            return False, f"held by {self.held_by}"
        return True, ""

    def write_level(self, digital_line: str, level) -> None:
        if digital_line in self.fail_on:
            raise OSError(f"mock write failure on {digital_line}")
        self.writes.append((digital_line, level))
