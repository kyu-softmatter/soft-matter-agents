"""The optical tweezers (Aresis Tweez 300), through its GUI's TCP text interface.

The registry row `optical_tweezers` names driver `python_tcp`, and the router
resolves that to this file. Card 037.

The GUI must already be running and connected to its System Manager. This
module sends it the same text lines its own TCP/IP server pane logs; it starts
nothing, and it cannot start the System Manager or touch an interlock.

WHAT A REPLY MEANS HERE, which is the whole reason this file is shaped the way
it is (`tweez300_reports_nothing_back`, E3):

- **A zero is acceptance, never verification.** The interface has no query
  command of any kind -- no position, no force, no trap list, no calibration --
  and six distinct ways a command can be ignored all return zero. So every
  dispatch this module records carries `verification: "none"`, whatever came
  back, and nothing here converts a reply into a state.
- **Silence is never retried.** A missing reply leaves the command's fate
  unknown, and several commands are relative (`TRAP_POSITION_REL`), so
  re-sending one that did land moves the trap twice. After a silence the link
  stops: nothing more is sent until a person has looked at the GUI and said
  what they saw (`acknowledge_unknown`). Only the safe direction -- trap off,
  laser off -- still goes out, because abort must always be able to.
- **An explicit busy answer may be retried.** The GUI answered, and its answer
  was *I did not run this*, so re-sending is safe. How many times and how long
  to wait are the caller's to pass, not constants here.

The two are told apart by what came back, not by a timeout.

NOT WRAPPED: `LASER_ON`. The interface can switch emission on even though the
power is a hand dial with no software path (`trap_laser_power_has_no_software_path`).
Turning a class-4 source on is not a step this module takes; a person does it
at the instrument. `LASER_OFF` is wrapped, because it is the safe direction.
Anything else not in `WRAPPED` is refused before a byte is sent -- a command
nothing here has exercised is not one to run first on the instrument.

NUMBERS THIS MODULE DOES NOT HOLD. The command gap, the busy retry count and
backoff, and the reply timeout all have measured values in the prior project,
measured on its bench. They are that project's measurements (E3 at best here)
and go to the librarian, not into this file: `Link` requires every one of them
from the caller, with no default, so each use says where its number came from.

CALIBRATION. The GUI holds two calibrations -- pixel-to-micrometre and the
AOD's trapping-field response -- and neither is readable over TCP
(`objective_change_invalidates_trap_calibration`, E3). An objective change
invalidates both silently. This module tracks only what a person has told it:
both start `unknown`, `confirm_calibration` records a person's statement, and
`objective_changed` returns both to `unknown`. Every dispatch carries the
calibration state as it stood, so a position in micrometres sent while it was
unknown says so in its own record.

Device modules import nothing from the agent (7.2 rule 5), and this one holds
no policy about values: whether a position or strength is allowed is the
envelope's question.
"""

from __future__ import annotations

import datetime as _dt
import json
import socket
import time
from pathlib import Path

#: The busy answer: "another command active". Vendor manual, Command Reference.
BUSY = -14

#: Commands this module sends, and the ones whose effect adds to the last.
#: `TRAP_DELETE` of a name that does not exist is also the readiness probe:
#: the protocol has no query, so the only liveness test is a harmless command.
WRAPPED = frozenset({
    "TRAP_DELETE", "SIMPLE_TRAP_CREATE", "TRAP_POSITION", "TRAP_POSITION_REL",
    "TRAP_STRENGTH", "TRAP_ON", "TRAP_OFF", "LASER_OFF",
    "LOAD_PATTERN", "DELETE_PATTERN", "TRAP_ASSIGN_PATTERN", "TRAP_REMOVE_PATTERN",
})
RELATIVE = frozenset({"TRAP_POSITION_REL"})
#: Allowed even while a silence is unresolved: the directions that remove light.
SAFE_DIRECTION = frozenset({"TRAP_OFF", "LASER_OFF"})

NOT_WRAPPED_REASON = {
    "LASER_ON": ("switching the trapping laser's emission on is done by a person at the "
                 "instrument; its power is a hand dial nothing here can read, so software "
                 "turning it on would put an unrecorded level of a class-4 source on the sample"),
}

#: The vendor manual's meanings for the codes. Meanings only: which of them mean
#: "up" on THIS bench is measured here, and `READINESS` below says whose each is.
CODES = {
    0: "success", -10: "invalid command line", -11: "unknown command",
    -12: "general command failure", -13: "command timeout", -14: "another command active",
    -15: "system manager not connected", -16: "device not ready", -17: "GUI not ready",
    -18: "GUI locked", -19: "calibration active", -20: "requested resource not supported",
    -21: "requested resource not available due to some other active process",
    -22: "no resource selected", -23: "resource not valid for this operation",
    -24: "element already exists", -25: "no such element", -26: "element locked",
    -27: "invalid parameters",
}

#: The prior project's readiness shape: up, up-but-wait, up-but-fix-by-hand.
#: Taken as a shape. Every code in it is THEIRS until measured on this bench;
#: `source` says so, and `classify` carries it into every answer.
READINESS = {
    0:   {"means": "up", "source": "agentic-microscope, vendor manual"},
    -25: {"means": "up", "source": "agentic-microscope, vendor manual"},
    -22: {"means": "up", "source": "agentic-microscope, measured on its bench 2026-08-27"},
    -16: {"means": "wait", "source": "agentic-microscope, vendor manual"},
    -17: {"means": "wait", "source": "agentic-microscope, vendor manual"},
    -19: {"means": "wait", "source": "agentic-microscope, vendor manual"},
    -15: {"means": "fix_by_hand", "source": "agentic-microscope, vendor manual"},
    -18: {"means": "fix_by_hand", "source": "agentic-microscope, vendor manual"},
}
#: Codes whose readiness meaning has been observed on this bench. Empty until it has.
MEASURED_HERE: dict[int, str] = {}

PROBE_TRAP = "__readiness_probe__"


class Refused(RuntimeError):
    """Raised before anything is sent. Nothing reached the GUI."""


class NoReply(RuntimeError):
    """The command was sent and nothing came back. Its fate is unknown."""


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _quote(name: str) -> str:
    return f'"{name}"' if " " in name else name


def write_pattern(path: str | Path, points) -> Path:
    """Write a pattern file: (x, y, strength) per point, x and y relative to the trap.

    The vendor's format: a tab-separated header naming the columns, one point
    per line, ASCII with CRLF. The GUI reads it by absolute path, so the
    absolute path is returned. Points outside the calibrated trapping range are
    clipped by the GUI to its edge and nothing reports it, and with the
    calibration unknown the range is unknown too -- so the size of a pattern
    means nothing in micrometres until a person has stated the calibration.
    """
    rows = ["colX\tcolY\tcolStr"]
    for x, y, s in points:
        if not 0.0 <= float(s) <= 1.0:
            raise Refused(f"relative strength {s} is outside 0-1, which the format defines")
        rows.append("\t".join(f"{float(v):.4f}".replace("-0.0000", "0.0000") for v in (x, y, s)))
    if len(rows) < 2:
        raise Refused("a pattern needs at least one point")
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(rows) + "\n", encoding="ascii", newline="\r\n")
    return out


def classify(status) -> dict:
    """Which readiness class a probe's status falls in, and on whose evidence."""
    if status is None:
        return {"status": None, "means": "no_reply", "measured_here": False,
                "source": "no reply is not a code"}
    row = READINESS.get(status, {"means": "unknown", "source": "not in any table"})
    return {"status": status, "code_meaning": CODES.get(status), **row,
            "measured_here": status in MEASURED_HERE}


class Link:
    """One socket to one GUI instance, and the record of every exchange on it.

    The port is also the choice of GUI instance, and so of camera and
    calibration: the vendor increments it per running GUI.
    """

    def __init__(self, host: str, port: int, *, connect_timeout_s: float,
                 reply_timeout_s: float, min_gap_s: float, busy_retries: int,
                 busy_backoff_s: float, log_path: str | Path, numbers_from: str,
                 sock: socket.socket | None = None):
        self.host, self.port = host, port
        self.reply_timeout_s = reply_timeout_s
        self.min_gap_s = min_gap_s
        self.busy_retries = busy_retries
        self.busy_backoff_s = busy_backoff_s
        self.numbers_from = numbers_from
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._buf = b""
        self._last_send: float | None = None
        self._seq = 0
        self.fate_unknown: dict | None = None
        #: After any command the trapping beam is ASSUMED ON (card 037, plan.md at
        #: 66e3d83). Nothing on this channel reads it, so only a person's
        #: statement moves it, and the next command moves it back.
        self.beam = {"state": "assumed on", "shown_blocked_by": None}
        self.calibration = {"pixel_to_um": "unknown", "aod_field": "unknown",
                            "objective": None, "stated_by": None}
        self._record({"event": "connect", "host": host, "port": port,
                      "timing": {"connect_timeout_s": connect_timeout_s,
                                 "reply_timeout_s": reply_timeout_s, "min_gap_s": min_gap_s,
                                 "busy_retries": busy_retries, "busy_backoff_s": busy_backoff_s,
                                 "numbers_from": numbers_from}})
        self._sock = sock or socket.create_connection((host, port), timeout=connect_timeout_s)

    # -- record -------------------------------------------------------------- #

    def _record(self, entry: dict) -> dict:
        self._seq += 1
        entry = {"seq": self._seq, "t": _now(), **entry}
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        return entry

    # -- wire ---------------------------------------------------------------- #

    def _readline(self) -> bytes | None:
        self._sock.settimeout(self.reply_timeout_s)
        try:
            while b"\n" not in self._buf:
                chunk = self._sock.recv(1024)
                if not chunk:
                    break
                self._buf += chunk
        except socket.timeout:
            return None
        line, sep, self._buf = self._buf.partition(b"\n")
        return line.rstrip(b"\r") if sep else None

    def _send_once(self, line: str) -> bytes | None:
        if self._last_send is not None and self.min_gap_s:
            wait = self.min_gap_s - (time.monotonic() - self._last_send)
            if wait > 0:
                time.sleep(wait)
        self._sock.sendall(line.encode("utf-8") + b"\r\n")
        self._last_send = time.monotonic()
        return self._readline()

    # -- the one way a command goes out --------------------------------------- #

    def send(self, verb: str, *args) -> dict:
        """Send one wrapped command and return its dispatch record.

        Raises `Refused` before sending, and `NoReply` after a silence. A
        non-zero, non-busy status is returned, not raised: it is an answer, and
        the caller decides what an answer means.
        """
        verb = verb.upper()
        line = " ".join([verb, *(_quote(str(a)) for a in args)])
        if verb not in WRAPPED:
            reason = NOT_WRAPPED_REASON.get(verb, "not wrapped: nothing here has exercised it")
            self._record({"event": "refused", "command": line, "reason": reason})
            raise Refused(f"{verb}: {reason}")
        if self.fate_unknown and verb not in SAFE_DIRECTION:
            reason = (f"an earlier command's fate is unknown ({self.fate_unknown['command']!r} "
                      "got no reply); a person must look at the GUI and acknowledge_unknown()")
            self._record({"event": "refused", "command": line, "reason": reason})
            raise Refused(reason)

        attempts = []
        self.beam = {"state": "assumed on", "shown_blocked_by": None}
        while True:
            raw = self._send_once(line)
            if raw is None:
                attempts.append({"reply": None})
                outcome = "silence"
                break
            text = raw.decode("utf-8", errors="replace").strip()
            try:
                status = int(text)
            except ValueError:
                attempts.append({"reply": text, "status": None})
                outcome = "unparsed"
                break
            attempts.append({"reply": text, "status": status})
            if status == BUSY and len(attempts) <= self.busy_retries:
                time.sleep(self.busy_backoff_s)
                continue
            outcome = "accepted" if status == 0 else "rejected"
            break

        entry = self._record({
            "event": "dispatch", "command": line, "verb": verb,
            "relative": verb in RELATIVE, "attempts": attempts, "outcome": outcome,
            "status": attempts[-1].get("status"),
            "meaning": CODES.get(attempts[-1].get("status")),
            "verification": "none",
            "beam": dict(self.beam),
            "calibration": dict(self.calibration),
        })
        if outcome in ("silence", "unparsed"):
            # An unparsed line is a reply that does not say whether the command ran,
            # so it leaves the same unknown a silence does.
            self.fate_unknown = {"command": line, "seq": entry["seq"], "outcome": outcome}
            raise NoReply(f"{line!r}: {outcome}; its fate is unknown and it is not re-sent")
        return entry

    def probe(self) -> dict:
        """The readiness probe: delete a trap no one would name. Changes nothing."""
        entry = self.send("TRAP_DELETE", PROBE_TRAP)
        return {**classify(entry["status"]), "seq": entry["seq"]}

    # -- what only a person can say ----------------------------------------- #

    def acknowledge_unknown(self, by: str, observed: str) -> dict:
        """A person looked at the GUI after a silence and says what they saw."""
        if not self.fate_unknown:
            raise Refused("nothing is unknown to acknowledge")
        entry = self._record({"event": "unknown_acknowledged", "by": by, "observed": observed,
                              "was": self.fate_unknown})
        self.fate_unknown = None
        return entry

    def person_shows_beam_blocked(self, by: str, observed: str) -> dict:
        """A person says the beam is blocked. Holds until the next command is sent."""
        self.beam = {"state": "blocked, stated by a person", "shown_blocked_by": by,
                     "observed": observed}
        return self._record({"event": "beam_stated", **self.beam})

    def confirm_calibration(self, by: str, objective: str, pixel_to_um: str,
                            aod_field: str) -> dict:
        """Record a person's statement of the GUI's calibrations. Nothing reads them."""
        self.calibration = {"pixel_to_um": pixel_to_um, "aod_field": aod_field,
                            "objective": objective, "stated_by": by}
        return self._record({"event": "calibration_stated", **self.calibration})

    def objective_changed(self, to: str | None = None) -> dict:
        """Both calibrations become unknown. Neither is readable to check."""
        self.calibration = {"pixel_to_um": "unknown", "aod_field": "unknown",
                            "objective": to, "stated_by": None}
        return self._record({"event": "objective_changed", "to": to,
                             "calibration": dict(self.calibration)})

    def close(self) -> None:
        self._record({"event": "close"})
        self._sock.close()


# -- the four functions the orchestrator checks for ------------------------- #

_LINK: Link | None = None


def connect(**kwargs) -> Link:
    """Open the module's link. The caller supplies every number (see Link)."""
    global _LINK
    _LINK = Link(**kwargs)
    return _LINK


def preflight(channel: dict | None = None) -> dict:
    """Report readiness, and say what it cannot establish."""
    channel = channel or {}
    report = {"channel": channel.get("id", "optical_tweezers"), "backend": "python_tcp",
              "read_back": False, "verification": "none"}
    if _LINK is None:
        return {**report, "ready": False, "reason": "no link: connect() has not been called"}
    probe = _LINK.probe()
    return {**report, "ready": probe["means"] == "up", "probe": probe,
            "calibration": dict(_LINK.calibration)}


def apply(params: dict) -> dict:
    """Send `params["commands"]`, a list of [verb, *args], one at a time, in order.

    Stops at the first refusal, silence or rejection and reports how far it got.
    """
    if _LINK is None:
        raise Refused("no link: connect() has not been called")
    sent = []
    for cmd in params.get("commands", []):
        entry = _LINK.send(*cmd)
        sent.append(entry)
        if entry["outcome"] != "accepted":
            break
    return {"dispatched": sent, "verification": "none",
            "complete": len(sent) == len(params.get("commands", []))
            and all(e["outcome"] == "accepted" for e in sent)}


def read() -> dict:
    """There is nothing to read. Says so, and gives the last thing commanded."""
    return {"read_back": False, "verification": "none",
            "note": "the Tweez 300 interface has no query of any kind; this is not a state",
            "beam": dict(_LINK.beam) if _LINK else {"state": "assumed on", "shown_blocked_by": None},
            "fate_unknown": _LINK.fate_unknown if _LINK else None,
            "calibration": dict(_LINK.calibration) if _LINK else None}


def abort(traps: list[str] | tuple[str, ...] = ()) -> dict:
    """Send the safe direction: each named trap off, then laser off. Never retried on silence.

    A zero here is acceptance, not a dark sample, so the beam is reported
    ASSUMED ON afterwards, never off: nothing on this channel reads blocked, and
    only a person at the instrument can say it is.
    """
    if _LINK is None:
        return {"aborted": False, "reason": "no link; nothing was sent",
                "beam": {"state": "assumed on", "shown_blocked_by": None},
                "reads_blocked": "nothing on this channel; only the person"}
    out = []
    for verb, *args in [*(("TRAP_OFF", t) for t in traps), ("LASER_OFF",)]:
        try:
            out.append(_LINK.send(verb, *args))
        except NoReply as exc:
            out.append({"command": verb, "outcome": "silence", "error": str(exc)})
    return {"aborted": True, "dispatched": out, "verification": "none",
            "beam": dict(_LINK.beam),
            "reads_blocked": "nothing on this channel; only the person"}
