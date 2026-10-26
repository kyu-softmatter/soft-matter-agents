"""The rules the Experiments screens stand on (console card 014). Pure: no file is read and nothing is sent.

Each rule is held to the file that says it: which approval covers a plan is what the runtime's `authorise`
decides (microscope_runtime/src/operator.py), the run request and its three replies are
`contracts/schemas/run_interface.schema.json`, and the hand-step sheet is the format
`devices/manual.py` writes. Where the console cannot know what the runtime knows, the words say so.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .instruments import tweezers_sent
from .sma_files import plan_hash
from .sma_run import RUN_ENDED_HOW

# -- which approval covers a plan -------------------------------------------------------------------

#: a login as the runtime accepts it in an approval's `signed_through` mark
LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


@dataclass(frozen=True)
class ApprovalJudgement:
    """`relevant`: the file names this plan (by id and revision). `covers`: and the runtime would take it.
    `why_void`: in words, when it is about this plan and would not be taken."""

    relevant: bool
    covers: bool = False
    why_void: str | None = None
    signed_through: dict[str, str] | None = None


def judge_approval(plan: dict[str, Any], approval: dict[str, Any]) -> ApprovalJudgement:
    """Mirrors `authorise`: a card of another kind, or one naming another plan or another revision, is not
    about this plan. One that names the plan and no `plan_revision` is void. A `signed_through` that is
    present must be exactly the console's mark, and the plan must be what was hashed. The approval's own
    `status`, and the plan's, are never read: a REVOKED label is not a revocation."""
    if approval.get("card") != "plan_approval" or approval.get("plan_id") != plan.get("id"):
        return ApprovalJudgement(False)
    if "plan_revision" not in approval:
        return ApprovalJudgement(True, why_void="it names the plan but carries no plan_revision, "
                                 "so the runtime does not know which revision it approved")
    if approval["plan_revision"] != plan.get("revision"):
        return ApprovalJudgement(False)
    mark = None
    if "signed_through" in approval:
        raw = approval["signed_through"]
        if not (isinstance(raw, dict) and set(raw) == {"via", "login"} and raw["via"] == "console"
                and isinstance(raw["login"], str) and LOGIN.fullmatch(raw["login"])):
            return ApprovalJudgement(True, why_void="its signed_through is not the console's mark "
                                     "(via console, and a login of letters, digits, . _ -)")
        mark = {"via": "console", "login": raw["login"]}
    if approval.get("plan_hash") != plan_hash(plan):
        return ApprovalJudgement(True, why_void="the plan changed after it was signed "
                                 "(the plan's hash is no longer the one approved)", signed_through=mark)
    return ApprovalJudgement(True, covers=True, signed_through=mark)


def signed_words(mark: dict[str, str] | None) -> str:
    if mark is None:
        return "signed by hand"
    return (f"signed through the console under the login {mark['login']} "
            "(the runtime checks that login when it starts)")


# -- the run request and its three replies ----------------------------------------------------------

SHA256 = re.compile(r"[0-9a-f]{64}")
RUN_ID = re.compile(r"run-[0-9]{8}-[0-9]{3}")


def run_request(sha256: str) -> dict[str, str]:
    """The one message that starts a run: the sha256 of the approval file's raw bytes, and nothing else."""
    if not isinstance(sha256, str) or not SHA256.fullmatch(sha256):
        raise ValueError("a run request names an approval file by its sha256 in lower-case hex")
    return {"run": sha256}


@dataclass(frozen=True)
class ReplyWords:
    kind: str  # started | waiting_for_bench | refused | unreadable
    text: str
    offers: list[str] = field(default_factory=list)  # what the console offers next: never anything


def reply_words(reply: Any) -> ReplyWords:
    """One of the schema's three replies, in words. Anything the schema does not admit is not believed."""
    if isinstance(reply, dict) and isinstance(reply.get("run"), str):
        kind = reply["run"]
        keys = set(reply)
        run_id = reply.get("run_id")
        if kind in ("started", "waiting_for_bench") and keys == {"run", "run_id"} \
                and isinstance(run_id, str) and RUN_ID.fullmatch(run_id):
            if kind == "started":
                return ReplyWords("started", f"The run started: {run_id}.")
            return ReplyWords("waiting_for_bench",
                              f"The run {run_id} waits for the person at the microscope.")
        reason = reply.get("reason")
        if kind == "refused" and keys == {"run", "reason"} and isinstance(reason, str) and reason:
            return ReplyWords("refused", f"The run was refused: {reason}")
    return ReplyWords("unreadable", "The answer was not understood, so nothing is shown as done.")


# -- how a run ended ------------------------------------------------------------------------------------

ENDED_WORDS: dict[str, str] = {
    "completed": "finished all its steps",
    "aborted_by_monitor": "stopped by the safety monitor",
    "stopped_from_outside": "stopped from outside the run (a stop was sent)",
    "failed": "failed before it finished",
    "refused": "refused by the runtime before any command went out",
}
assert set(ENDED_WORDS) == set(RUN_ENDED_HOW)


def ended_words(how: str | None) -> str | None:
    if how is None:
        return None
    return ENDED_WORDS.get(how, f"ended as the run wrote it: {how}")


# -- the hand-step sheet ----------------------------------------------------------------------------------

WAITING_LINE = "Waiting for a step at the microscope. Confirm it there."

_HEADER = re.compile(r"^## (?P<id>\S+) - (?P<channel>[^/\n]+?)(?: / (?P<element>.+))?\s*$")
_CONFIRMED = re.compile(r"^- confirmed: (?P<at>\S+) by (?P<who>.+?)\s*$")


@dataclass
class ManualStep:
    sheet_id: str
    channel: str
    element: str | None
    instruction: str
    opened_at: str | None = None
    confirmed: bool = False
    confirmed_at: str | None = None
    confirmed_by: str | None = None
    observed: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_manual_steps(text: str) -> list[ManualStep]:
    """`manual_steps.md` as `devices/manual.py` renders it. A sheet with no confirmed line is open: one the
    parser cannot place never reads as a step that was done."""
    sheets: list[ManualStep] = []
    body: list[str] = []
    for line in text.splitlines():
        m = _HEADER.match(line)
        if m:
            sheets.append(ManualStep(m["id"], m["channel"].strip(), m["element"], ""))
            body = []
            continue
        if not sheets:
            continue
        sheet = sheets[-1]
        c = _CONFIRMED.match(line)
        if line.startswith("- opened: "):
            sheet.opened_at = line[len("- opened: "):].strip()
        elif c:
            sheet.confirmed, sheet.confirmed_at, sheet.confirmed_by = True, c["at"], c["who"]
        elif line.startswith("- observed: "):
            seen = line[len("- observed: "):].strip()
            sheet.observed = None if seen == "(nothing recorded)" else seen
        elif not line.startswith("- "):
            body.append(line)
            sheet.instruction = "\n".join(body).strip()
    return sheets


# -- what a stop leaves on ------------------------------------------------------------------------------

TWEEZERS_NOTE = "tweezers laser: software cannot switch it; assumed on until you confirm"
_STOPS = ("stopped_from_outside", "aborted_by_monitor")


def tweezers_note(how: str | None, events: list[dict[str, Any]]) -> str | None:
    """After a stop on a run that had traps, the laser is assumed on: software has no switch for it."""
    if how in _STOPS and tweezers_sent(events)["traps"]:
        return TWEEZERS_NOTE
    return None


# -- plan state -----------------------------------------------------------------------------------------

STATE_WORDS = {
    "draft": "draft: not validated yet",
    "waiting_for_signature": "waiting for a signature",
    "approved": "approved: signed and on disk",
    "running": "running now",
    "ended": "ended: a run of it is finished",
}

# -- the sample map ------------------------------------------------------------------------------------------

SAMPLE_MAP_PARTS: list[dict[str, str]] = [
    {"part": "frames_with_stage_readback", "state": "not_built",
     "why": "no run yet saves frames together with the stage's read-back position, so a frame cannot be "
            "placed on the sample"},
    {"part": "hole_fitter", "state": "not_built",
     "why": "the runtime has no hole fitter, so no grid of holes is found from frames"},
    {"part": "candidate_finder", "state": "not_built",
     "why": "the runtime has no candidate finder; a model's guesses are never drawn as candidates"},
    {"part": "flags_and_confirmations", "state": "not_built",
     "why": "flags and candidate confirmations cannot be recorded yet: there is nowhere to write them"},
]
