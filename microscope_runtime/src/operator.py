"""S6: carry out an approved plan without changing it (4.6).

The operator is the only component that holds Tier 1-2 (6). Everything above it
-- the system designer, S3 to S5 -- holds Tier 0 and runs nothing, so the line
between designer and operator is the approval gate itself.

On the normal path there is no model here. Commands are derived mechanically
from fields of plan.json and each parameter carries the field it came from
(check 14). Monitors are compiled from stop_criteria and the decision to stop
is a comparison, not a judgement (4.6.1). A model is wanted in exactly one
place: writing up, afterwards, what the plan failed to anticipate -- and by
then Python has already stopped the run.

This file depends on the orchestrator and on contracts, and on nothing else.
It never touches a device module (7.2 rule 3).

Both dependencies are resolved by path. `operator` is also the name of a
standard-library module and plan.md 7 fixes this filename, so putting src/ on
sys.path would shadow the standard module for every other import in the
process. Loading by path keeps that from happening and keeps this file from
being reachable as `import operator` by accident. Renaming it to
system_operator.py -- the term 4.6 already uses -- would remove the collision
outright, but the name is written in plan.md 7 and that file belongs to the
design seat.
"""

from __future__ import annotations

import os
import sys

# The docstring above says this collision from the other side: loading our
# dependencies by path keeps THIS file from shadowing the standard `operator`
# for them. Running this file as a script is the remaining direction, and it
# needs the other half -- python3 src/operator.py puts src/ at the head of
# sys.path, `enum` does `from operator import or_` during interpreter
# start-up, and it lands here instead, mid-way through our own `import json`.
# EVERY SCRIPT IN THIS DIRECTORY CARRIES THE SAME FOUR LINES, and this
# comment used to name two of them and say "three modules", which is where a
# later seat got a wrong count from -- it read this sentence and reported it.
# A comment that counts goes stale silently and is quoted as evidence, so
# count it instead:
#
#   grep -l 'sys\.path\[:\] = \[p for p in sys\.path' src/*.py
#
# The rule that run gives: every module here with a `__main__` carries it,
# and orchestrator.py is the only one without, because it is never executed
# as a script. The workaround is the condition of being runnable in this
# directory, not a few special cases -- which is the argument for the rename,
# and plan.md 7's filename is the design seat's.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import hashlib                                                   # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
import math                                                      # noqa: E402
import re                                                        # noqa: E402
from fractions import Fraction                                   # noqa: E402
from dataclasses import dataclass, field                         # noqa: E402
from datetime import datetime, timezone                          # noqa: E402
from pathlib import Path                                         # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent
CONTRACTS = REPO / "contracts"

#: The knowledge snapshot stays with the design and is read by both folders, so a plan and
#: the run that executes it stand on the same store version (plan.md 15). AGENT is
#: microscope_runtime/ now: policy, approvals and runs resolve from it, the snapshot only here.
SNAPSHOT_PATH = REPO / "microscope_agent" / "envelope" / "snapshot.json"


def _load(name: str, path: Path):
    """Import a module by path, registered under a name that collides with nothing."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                            # type: ignore[union-attr]
    return module


orch = _load("_mic_orchestrator", Path(__file__).resolve().parent / "orchestrator.py")
run_lock = _load("_mic_run_lock", Path(__file__).resolve().parent / "run_lock.py")
#: The configuration gate (card 069): what a hardware run may load.
mm_gate = _load("_mic_mm_config_gate", Path(__file__).resolve().parent / "mm_config_gate.py")
#: The run-time watcher (card 076): it records and never acts, and holds nothing of this module.
watcher_mod = _load("_mic_watcher", Path(__file__).resolve().parent / "watcher.py")
judgements_mod = _load("_mic_judgements", Path(__file__).resolve().parent / "judgements.py")

#: Where the one-run-at-a-time lock lives (card 062). None means
#: run_lock.default_path(), outside this tree. Tests point it elsewhere.
RUN_LOCK_PATH: Path | None = None


def _take_run_lock(holder: dict):
    """The run lock, held, or a Refusal naming who holds it. Never waits."""
    lock = run_lock.RunLock(RUN_LOCK_PATH)
    try:
        lock.acquire(holder)
    except run_lock.RunLockHeld as exc:
        raise Refusal(f"{exc}. One run at a time: two runs would be two Micro-Manager cores "
                      "on one instrument (plan.md 11-25)") from None
    return lock


def _contracts_validate():
    """Borrow the validator's own plan hash rather than reimplementing it.

    An approval is bound to the hash of the plan with `status` removed (5.5).
    Two implementations of that would agree until the day they did not, and the
    day they did not, an approval would be honoured for a plan nobody approved.
    """
    return _load("_contracts_validate", CONTRACTS / "validate.py")


class Refusal(RuntimeError):
    """The run does not start, and the reason is a fact, not an opinion."""


@dataclass
class Authorisation:
    permitted: bool
    reasons: list[str] = field(default_factory=list)
    approval_id: str | None = None
    kind: str | None = None          # plan_approval | scope_approval
    max_tier: int = 0
    #: The file that authorised, as the reader read it: {path, sha256[, signed_through]} -- what
    #: the run log's approval.file carries (card 087). None for a run no approval authorised.
    approval_file: dict | None = None


# --------------------------------------------------------------------------- #
# O0 -- the gate (6, 6.1, 2.1)
# --------------------------------------------------------------------------- #


def agent_root(root: Path | None) -> Path:
    """The runtime's folder, or the scratch copy of it under `root` (card 063).

    `root` mirrors the repository: `<root>/microscope_runtime/{envelope,approvals,runs}`,
    with the snapshot under `<root>/microscope_agent/envelope/` (plan.md 15).
    A scratch root is for mock only, and operator.run refuses it with any other
    backend before reading anything, so a TEST envelope can never reach the
    instrument.
    """
    return AGENT if root is None else Path(root) / "microscope_runtime"


def snapshot_path(agent: Path | None = None) -> Path:
    """Where the knowledge snapshot is read: the design's one copy, never beside the policy.

    `agent` is the runtime's folder or a scratch copy of it, so a scratch root's snapshot
    sits in that root's own microscope_agent/. Nothing falls back from one folder to the
    other (plan.md 15).
    """
    if agent is None:
        return SNAPSHOT_PATH
    return Path(agent).parent / "microscope_agent" / "envelope" / "snapshot.json"


def load_safety(agent: Path | None = None) -> dict:
    """Policy. A person writes it after confirming the limits physically.

    Absent is not permissive. With no safety policy on disk there is nothing to
    compare a condition against, and 2.1 rule 2 makes the default stop rather
    than proceed. This is also why the file was deliberately not extracted from
    the prior project (10.3 rule 4): a limit that migrated is not a limit
    anybody checked here.
    """
    path = (agent or AGENT) / "envelope" / "safety.json"
    if not path.exists():
        raise Refusal(
            "envelope/safety.json does not exist. Nothing executes without a safety policy: "
            "there is no limit to compare a condition against, and an unknown limit is not a "
            "satisfied limit (2.1 rule 2, rule 7). A person writes this file after confirming "
            "the values on the instrument (10.3 rule 4)"
        )
    # utf-8-sig for the same reason as approvals below: the person writes this file.
    return json.loads(path.read_text(encoding="utf-8-sig"))


def approvals_on_disk(agent: Path | None = None, folder: Path | None = None) -> list[dict]:
    """approvals/ is the one folder a person writes and the agent does not (7.1 rule 5).

    Each file is read ONCE, as bytes, and the sha256 kept beside `__path` is of exactly those bytes
    (card 087): the hash a run log names is of what was judged, never of a second read. `folder`
    is a test folder a mock run was pointed at (`--approvals`); without it the runtime's own.
    Nothing here ever falls back to the planning agent's old approvals folder (plan.md 15).
    """
    out = []
    folder = Path(folder) if folder is not None else (agent or AGENT) / "approvals"
    if not folder.exists():
        return out
    for path in sorted(folder.glob("*.json")):
        raw = path.read_bytes()
        try:
            # utf-8-sig, card 041 item 3: PowerShell 5.1's `Set-Content -Encoding
            # utf8` writes a byte-order mark, and the person writes approvals from
            # there. The mark is accepted and nothing else changes; a file that is
            # malformed for any other reason is still refused below.
            card = json.loads(raw.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise Refusal(f"{path.name} is not readable JSON: {exc}. An unreadable approval is not an approval")
        try:
            card["__path"] = str(path.relative_to(REPO))
        except ValueError:                                      # a scratch root, outside the tree
            card["__path"] = str(path)
        card["__sha256"] = hashlib.sha256(raw).hexdigest()
        # The person's own login lives beside the policy of the folder this approval was read from.
        card["__login_path"] = str(folder.parent / "envelope" / "console_login.json")
        out.append(card)
    return out


#: A console login, as plan_approval's signed_through and console_login.json both spell it.
_LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def console_login_problem(doc) -> str | None:
    """Why `doc` is not a valid console_login.json (console_login.schema.json), or None.

    Written out by hand because the operator depends on nothing else; a test holds it to the
    schema, case by case.
    """
    if not isinstance(doc, dict):
        return "it is not a JSON object"
    wanted = {"artifact", "schema_version", "login", "written_by", "written_at"}
    if set(doc) != wanted:
        return f"its keys are {sorted(doc)}, and the schema admits exactly {sorted(wanted)}"
    if doc["artifact"] != "console_login":
        return "`artifact` is not 'console_login'"
    if doc["schema_version"] != "0.1":
        return "`schema_version` is not '0.1'"
    if not isinstance(doc["login"], str) or not _LOGIN.fullmatch(doc["login"]):
        return "`login` is not a plain id (letters, digits, '.', '_', '-', at most 64, never an email)"
    if not isinstance(doc["written_by"], str) or not doc["written_by"]:
        return "`written_by` is not a non-empty string"
    at = doc["written_at"]
    if not isinstance(at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", at):
        return "`written_at` is not a date (YYYY-MM-DD)"
    try:
        datetime.strptime(at, "%Y-%m-%d")
    except ValueError:
        return "`written_at` is not a real date"
    return None


def _console_mark_problem(mark) -> str | None:
    """Why an approval's `signed_through` is not the console mark {via: console, login}, or None."""
    if not isinstance(mark, dict) or set(mark) != {"via", "login"}:
        return "it is not an object with exactly `via` and `login`"
    if mark["via"] != "console":
        return "`via` is not 'console'"
    if not isinstance(mark["login"], str) or not _LOGIN.fullmatch(mark["login"]):
        return "`login` is not a plain id"
    return None


def _signed_through_reasons(card: dict) -> list[str]:
    """The three checks a console-signed approval adds to the plan hash (plan.md 15.1 item 4).

    [] when the approval carries no `signed_through` (judged as ever) or when its login is the
    one the person placed by hand. A test login is just another login: nothing here treats one
    specially, and it binds only if the person put it in the file themselves.
    """
    if "signed_through" not in card:
        return []
    where = card["__path"]
    mark = card["signed_through"]
    bad = _console_mark_problem(mark)
    if bad:
        return [f"{where}: `signed_through` is not the console's mark ({bad}), so it says nothing "
                "about who signed and the approval covers nothing"]
    login_path = Path(card.get("__login_path") or AGENT / "envelope" / "console_login.json")
    if not login_path.exists():
        return [f"{where} is signed through the console under login {mark['login']!r}, and "
                f"{login_path.name} is absent: the person's own login is placed by hand beside the "
                "safety policy, and without it nothing says whose login that is. It covers nothing"]
    try:
        doc = json.loads(login_path.read_bytes().decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [f"{where} is signed through the console, and {login_path.name} is not valid: {exc}. "
                "It covers nothing"]
    bad = console_login_problem(doc)
    if bad:
        return [f"{where} is signed through the console, and {login_path.name} is not valid: {bad}. "
                "It covers nothing"]
    if doc["login"] != mark["login"]:
        return [f"{where} is signed through the console under login {mark['login']!r}, and the login "
                f"the person placed in {login_path.name} is {doc['login']!r}. They are compared byte "
                "for byte and these differ, so it covers nothing"]
    return []


def _approval_file(card: dict) -> dict | None:
    """What a run log's approval.file names: the file as it was read, never a second read of it."""
    if "__sha256" not in card:
        return None
    out = {"path": Path(card["__path"]).as_posix(), "sha256": card["__sha256"]}
    if "signed_through" in card:
        out["signed_through"] = dict(card["signed_through"])
    return out


def approval_block(decision: "Authorisation") -> dict:
    """The run log's `approval`: id, kind, and the file that authorised (card 087)."""
    block = {"id": decision.approval_id, "kind": decision.kind}
    if decision.approval_file is not None and decision.approval_id is not None:
        block["file"] = decision.approval_file
    return block


def approvals_source(folder: Path | None, backend: str) -> Path | None:
    """`--approvals <folder>`: a test folder, honoured only with the mock backend (card 087 item 5).

    Refused before anything is read or opened for any other backend, unless the folder named is
    the runtime's own, which is no change at all. A hardware run reads approvals/ and nothing else.
    """
    if folder is None:
        return None
    folder = Path(folder)
    if backend != "mock" and folder.resolve() != (AGENT / "approvals").resolve():
        raise Refusal(f"--approvals {folder} is for the mock backend only, and this run asks for "
                      f"{backend!r}. A hardware run reads microscope_runtime/approvals/ and nothing "
                      "else: a test folder's approvals never authorise the instrument")
    return folder


def authorise(plan: dict, approvals: list[dict] | None = None) -> Authorisation:
    """Does a valid approval cover this exact plan revision?

    Two routes reach APPROVED (5.5): a plan_approval naming this
    (plan_id, revision), or a live scope_approval whose range contains the
    plan. Neither is inferred from the plan's own `status` field -- a card
    that approves itself is not a gate (P4).
    """
    approvals = approvals_on_disk() if approvals is None else approvals
    validate = _contracts_validate()
    wanted = validate.plan_hash(plan)
    plan_id, revision = plan.get("id"), plan.get("revision")
    reasons: list[str] = []

    for card in approvals:
        if card.get("card") != "plan_approval":
            continue
        if card.get("plan_id") != plan_id:
            continue
        # `plan_revision` is the field plan_approval.schema.json declares for
        # this, and what was read here until 2026-09-20 was `revision` -- the
        # APPROVAL CARD'S OWN revision, which common_head gives every card.
        # The two agree in the one approval on disk and agree for no reason:
        # bump a plan to r2 and issue a fresh approval, and the new card is at
        # its own revision 1 against a plan at 2, so a valid approval is
        # refused. Revise the approval instead and it matches a plan revision
        # it was never about. Absent is refused rather than fallen back on --
        # a fallback here would re-create the coincidence it replaces.
        if "plan_revision" not in card:
            reasons.append(
                f"{card['__path']} names this plan and carries no `plan_revision`, which is the "
                "field that says which revision was approved (plan_approval.schema.json). An "
                "approval that cannot name a revision does not cover one (5.5)"
            )
            continue
        if card.get("plan_revision") != revision:
            continue
        # A console-signed approval adds three checks before the hash (card 087). An approval that
        # fails any covers nothing, and the reason says which.
        signed = _signed_through_reasons(card)
        if signed:
            reasons.extend(signed)
            continue
        got = card.get("plan_hash")
        if got != wanted:
            reasons.append(
                f"{card['__path']} names this revision but its plan_hash does not match the plan on "
                f"disk. The plan changed after it was approved, so the approval is void (5.5)"
            )
            continue
        return Authorisation(True, ["individual approval matches this revision and hash"],
                             card.get("id"), "plan_approval", max_tier=2,
                             approval_file=_approval_file(card))

    if is_console(plan.get("qid")):
        # Another login's question (plan.md 15.1 item 5): no scope_approval is even looked at.
        reasons.append(
            f"{plan.get('qid')} is another login's question (the `c` in its id). It waits for the "
            "person's own OK at every tier: only a plan_approval naming this plan's id, revision and "
            "hash covers it, and a scope_approval never does"
        )
        reasons.append(f"no plan_approval on disk names ({plan_id}, revision {revision})")
        return Authorisation(False, reasons)

    irreversible = [a for a in plan.get("actions", []) if a.get("reversible") is False]
    if irreversible:
        reasons.append(
            f"{len(irreversible)} irreversible action(s) present; a scope_approval cannot cover "
            "them and an individual plan_approval is required (2.1 rule 3, 6.1)"
        )
        return Authorisation(False, reasons)

    for card in approvals:
        if card.get("card") != "scope_approval":
            continue
        reasons.append(
            f"{card['__path']} is a scope_approval; its range still has to be checked against this "
            "plan and against envelope/safety.json, and neither comparison is implemented -- so "
            "this route authorises nothing yet. It said until 2026-09-20 that the envelope does "
            "not exist, which stopped being true at c1404bf and has been revised twice since; a "
            "refusal reason describing a world two days gone sends its reader to fix the wrong "
            "thing"
        )

    reasons.append(f"no plan_approval on disk names ({plan_id}, revision {revision})")
    return Authorisation(False, reasons)


#: A question id the console minted (plan.md 7.1.1 rule 9): `<agent>-<YYYYMMDD>-c<NNN>`. The runtime
#: keys on this mark alone -- never on what the plan says about who asked, never on the console's
#: settings -- and in the first build every console question is another login's (plan.md 15.1 item 5).
CONSOLE_QID = re.compile(r"-c[0-9]{3}$")
CONSOLE_ITEM_NAME = re.compile(r"^ci-[0-9]{8}-[0-9]{6}-[a-z0-9]{4}[.]json$")


def is_console(qid) -> bool:
    """Whether a question id carries the console's mark. An absent id is the window form, as before."""
    return qid is not None and bool(CONSOLE_QID.search(str(qid)))


def console_inbox(agent: Path | None = None) -> Path:
    """Where the console's items are read: beside the design's folder, in the root of whichever tree."""
    return (Path(agent) if agent is not None else AGENT).parent / "microscope_agent" / "console_inbox"


def _where(path: Path) -> str:
    """A path as the run log names it: repo-relative where it can be."""
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:                                          # a scratch root, outside the tree
        return path.as_posix()


def read_console_item(qid: str, inbox: Path) -> dict:
    """The inbox item that asked this question, read to confirm it (card 089).

    Every way of not finding exactly one readable item refuses: no folder (the inbox is not open),
    no item with this question_id, more than one, an item that cannot be read or parsed -- since
    then nobody can say it was not this question's -- and an attachment that cannot be read or
    whose bytes do not have the sha256 the item names. Ambiguity stops (P0). The item's own
    `asker_mark` is not read: whose question it is was decided by the `c` in the id.

    Returns what the run log's `console_item` carries: the item's path and the sha256 of the bytes
    that were parsed, so an item changed after the run leaves a trace.
    """
    inbox = Path(inbox)
    if not inbox.is_dir():
        raise Refusal(
            f"{qid} is a console question and {_where(inbox)} does not exist, so the item that asked "
            "it cannot be read. The inbox is not open; a console plan does not run until it is, even "
            "under an approval")
    found, unreadable = [], []
    for path in sorted(inbox.iterdir()):
        if not CONSOLE_ITEM_NAME.match(path.name):
            continue                                            # attachments carry `--<name>`; read below
        try:
            raw = path.read_bytes()
            item = json.loads(raw)
        except (OSError, ValueError) as exc:
            unreadable.append(f"{path.name} ({type(exc).__name__})")
            continue
        if isinstance(item, dict) and item.get("question_id") == qid:
            found.append((path, raw, item))
    if unreadable:
        raise Refusal(
            f"{qid} is a console question and the console inbox holds items that cannot be read: "
            f"{', '.join(unreadable)}. Any of them could be the one that asked it, so the run does "
            "not start until they read")
    if len(found) != 1:
        raise Refusal(
            f"{qid} is a console question and the console inbox holds {len(found)} items with that "
            f"question_id{': ' + ', '.join(p.name for p, _, _ in found) if found else ''}. Exactly one "
            "item asks a question; with none there is nothing to confirm and with more nobody can "
            "say which one this plan answers")
    path, raw, item = found[0]
    if path.name != f"{item.get('item_id')}.json":
        raise Refusal(f"{path.name} carries item_id {item.get('item_id')!r}; an item's file is named by its id")
    attachments = []
    for att in item.get("attachments") or []:
        name = str((att or {}).get("file") or "")
        if not name or Path(name).name != name:
            raise Refusal(f"{path.name} names an attachment {name!r}, which is not a plain file name beside it")
        try:
            got = hashlib.sha256((inbox / name).read_bytes()).hexdigest()
        except OSError as exc:
            raise Refusal(f"{path.name} names the attachment {name}, which cannot be read "
                          f"({type(exc).__name__})") from exc
        if got != att.get("sha256"):
            raise Refusal(f"{path.name} names the attachment {name} with sha256 {att.get('sha256')} and its "
                          f"bytes hash to {got}. The file is not the one that was asked with")
        attachments.append({"file": name, "sha256": got})
    return {"path": _where(path), "sha256": hashlib.sha256(raw).hexdigest(),
            "item_id": item.get("item_id"), "question_id": qid, "attachments": attachments}


def plan_path_of(plan_path: Path) -> str:
    """The plan file a run opened, as its log names it: repo-relative with forward slashes (card 089).

    Check 91 finds a run's question through this path, so a backslash here names no card. A plan
    outside the repository (a scratch root, in a test) is named by its absolute path in forward
    slashes, which joined to the repository root is still that file.
    """
    return _where(Path(plan_path).resolve())


def console_gate(plan: dict, decision: Authorisation, agent: Path | None = None) -> dict | None:
    """Another login's question runs only under an exact plan_approval and a readable item (card 089).

    None for a window question, which stays under the tier table unchanged. Refuses before anything
    is built, so no command is sent and no run folder exists.
    """
    qid = plan.get("qid")
    if not is_console(qid):
        return None
    if not (decision.permitted and decision.kind == "plan_approval"):
        raise Refusal(
            f"plan {plan.get('id')} answers {qid}, another login's question (the `c` in its id), and "
            "another login's question waits for the person's own OK at every tier, Tier 0 included: "
            "only a plan_approval naming this plan's id, revision and hash covers it, and a "
            "scope_approval never does. " + "; ".join(decision.reasons))
    try:
        return read_console_item(qid, console_inbox(agent))
    except Refusal as exc:
        # Whichever way the confirming read failed, the reason names the question and the rule.
        raise Refusal(f"plan {plan.get('id')} answers {qid}, another login's question, and the item that "
                      f"asked it cannot be confirmed (it is read before the run, never after): {exc}") from None


def highest_tier(plan: dict) -> int:
    return max([int(a.get("tier", 0)) for a in plan.get("actions", [])] or [0])


# --------------------------------------------------------------------------- #
# O1 -- a limit that is a lookup becomes a number, before anything moves
# --------------------------------------------------------------------------- #

# Which lookup answers which quantity. `resolved_from.keyed_by` in the envelope
# is prose -- the person saying what selects the value -- so it is not a field
# a program dispatches on, and the resolution itself is written here and is
# answerable to that sentence. A quantity with no resolver REFUSES: a lookup
# this file does not know how to perform is not one it may skip.
KEYED_BY_NOSEPIECE = "nosepiece_position"


def load_snapshot(agent: Path | None = None) -> dict:
    """The KB as this agent copied it, and the only store this file reads.

    The librarian owns knowledge and cannot write here (P14, D11), so the copy
    into envelope/ is deliberate: which KB version entered this envelope, and
    when, is then a fact of this agent's own commit history. Reading
    librarian_agent/kb/ at run time would resolve a limit against whatever the
    store holds at that moment, and afterwards the run could not say what it
    resolved against.
    """
    path = snapshot_path(agent)
    if not path.exists():
        raise Refusal(
            "envelope/snapshot.json does not exist, so a limit that resolves from the store has "
            "nothing to resolve against. Absent is not permissive (2.1 rule 2)"
        )
    return json.loads(path.read_text())


def _snapshot_entry(snap: dict, entry_id: str) -> dict:
    held = (snap.get("entries") or {}).get(entry_id)
    if held is None:
        raise Refusal(
            f"the snapshot at {snap.get('kb_version')} holds no entry {entry_id!r}. The limit "
            "names where to look and nothing is there; a floor that disappears when its lookup "
            "misses fails toward allowing everything"
        )
    return json.loads(held["text"])


def _nosepiece(snap: dict) -> dict:
    """The turret row of the device table, carried inside the snapshot.

    Read from the snapshot rather than from the staged table for the same
    reason the entries are: one store per run, named in the log.
    """
    text = ((snap.get("tables") or {}).get("devices") or {}).get("text")
    if text is None:
        raise Refusal("the snapshot carries no device table, so the turret cannot be read from it")
    for channel in json.loads(text).get("channels", []) or []:
        for element in channel.get("elements", []) or []:
            # EQUALITY AGAINST A BARE LITERAL, which is the shape the probe
            # that found card 030's other sites did not look for -- it
            # searched substring, startswith, endswith and membership. This
            # file was reported as one hit and not read. The turret is named
            # here, in orchestrator's `!= "nosepiece"` and
            # `state.get("nosepiece")`, and in plan_card's number-to-element
            # map: four sites, one element, no declared field. The `role` row
            # retires all four.
            if element.get("id") == "nosepiece":
                return element
    raise Refusal("the snapshot's device table has no nosepiece element")


def objective_in_path(plan: dict, snap: dict) -> dict:
    """Which of the six lenses this plan puts in front of the sample.

    `objective_clearance_min` is keyed by it, and the six run from 20 mm to
    0.13 mm -- a factor of 150, so the key is the whole of the answer.

    The plan says it by driving the turret, and the only machine-readable way
    it can is a number: numbers[] is where a card keeps its values, and an
    objective's id is a string that is exact by designation (5.3), so what a
    plan can carry is the POSITION. Matched against the table's own
    `objectives[].position` rather than against a range written here -- this
    turret is indexed from 0 and the table says so in an `index_note`, and
    1-6 would be off by one on every lens.

    THE FIELD NAME IS A DECISION MADE HERE. No plan has ever named an
    objective, because S5 does not exist yet, so there is no contract to read
    this off -- what a plan must carry is fixed by this function and reported
    up rather than discovered. The alternative considered and rejected was
    reading the turret back at preflight: a read-back is what the instrument
    currently holds, and the floor has to bound what the plan drives to.
    """
    objectives = _nosepiece(snap).get("objectives") or []
    key = {n.get("name"): n for n in plan.get("numbers", []) or []}.get(KEYED_BY_NOSEPIECE)
    if key is None:
        raise Refusal(
            f"the plan carries no number named {KEYED_BY_NOSEPIECE!r}, so which objective is in "
            "front of the sample is not stated. objective_clearance_min resolves from that "
            "objective's working distance and the six on this stand run from 20 mm to 0.13 mm; "
            "an unstated objective is not a forgiving one (2.1 rule 2)"
        )
    for row in objectives:
        if row.get("position") == key.get("value"):
            return row
    raise Refusal(
        f"{KEYED_BY_NOSEPIECE} is {key.get('value')!r} and this turret has positions "
        f"{sorted(r.get('position') for r in objectives)}. It is indexed from 0, not from 1"
    )


def _working_distance(plan: dict, snap: dict) -> dict:
    """The working distance of the objective the plan drives to.

    TWO SHAPES COME BACK AND THE SECOND IS THE ONE THAT MATTERS. Five lenses
    carry `working_distance`, a point. The 40x WI carries
    `working_distance_min` and `working_distance_max` instead, because the
    catalogue quotes a range for a correction-collar lens and the librarian
    does not interpolate inside a quotation. Asking for the point name alone
    answers for five of six and comes back EMPTY for the sixth -- not a range
    to think about, nothing at all, which is the worse of the two: a range is
    visible and an absence looks like a lookup that has not run.

    FOR A FLOOR THE NEAR END BINDS. A floor answers *how close may it come*,
    and the true working distance is at least the minimum at any collar
    setting -- so 0.16 mm is not crossed before focus while 0.20 mm can be.
    Taking the maximum would permit 40 um of approach the vendor never
    promised.

    The part number is checked against the table's, because the table's
    `entry_ref` and the entry's `identifiers.part_number` are two statements
    about the same lens written in two places, and a floor resolved off a
    mis-wired reference would be the right shape and the wrong lens.
    """
    row = objective_in_path(plan, snap)
    key = {"field": KEYED_BY_NOSEPIECE,
           "value": {n.get("name"): n.get("value")
                     for n in plan.get("numbers", []) or []}.get(KEYED_BY_NOSEPIECE),
           "objective": row.get("id"),
           "part_number": row.get("part_number")}
    entry_id = row.get("entry_ref")
    if not entry_id:
        raise Refusal(
            f"the turret row for objective {row.get('id')!r} names no entry_ref, so its working "
            "distance has nowhere to be read from"
        )
    entry = _snapshot_entry(snap, entry_id)
    part = (entry.get("identifiers") or {}).get("part_number")
    if part and row.get("part_number") and part != row.get("part_number"):
        raise Refusal(
            f"the turret says position {row.get('position')} is {row.get('part_number')} and "
            f"entry {entry_id!r} is about {part}. Two statements about one lens disagree and "
            "neither is preferred here"
        )
    numbers = {n.get("name"): n for n in entry.get("numbers", []) or []}
    exact = numbers.get("working_distance")
    if exact is not None:
        return {"value": exact.get("value"), "unit": exact.get("unit"), "entry": entry_id,
                "number": "working_distance", "grade": exact.get("grade"), "key": key,
                "note": "a point value, as five of the six lenses carry it"}
    low, high = numbers.get("working_distance_min"), numbers.get("working_distance_max")
    if low is None:
        raise Refusal(
            f"entry {entry_id!r} carries neither working_distance nor working_distance_min, so "
            f"the floor for objective {row.get('id')!r} does not resolve. Not a default and not "
            "a warning: the run stops (2.1 rule 2)"
        )
    return {"value": low.get("value"), "unit": low.get("unit"), "entry": entry_id,
            "number": "working_distance_min", "grade": low.get("grade"), "key": key,
            "note": (f"quoted as a range {low.get('value')} to "
                     f"{(high or {}).get('value')} {low.get('unit')} across the correction "
                     "collar. A floor takes the near end: the true working distance is at "
                     "least the minimum at any collar setting, so this end is not crossed "
                     "before focus and the far end can be")}


RESOLVERS = {"working_distance": _working_distance}


def resolve_limits(plan: dict, safety: dict, agent: Path | None = None) -> list[dict]:
    """Every limit that is a lookup becomes a number here, or the run does not start.

    A limit is EITHER a constant or a `resolved_from` lookup, never both and
    never neither (envelope_safety.schema.json). A constant is already a bound
    and is not touched. A lookup has no `value` and no `unit`, so anything
    reading lim["value"] on one raises rather than mis-comparing -- that is
    true today and stays true: the resolved number is returned beside the
    limit and never written back into it.

    REFUSING IS THE POINT. A floor that quietly disappears when its lookup
    misses is the most dangerous failure this file has, because it fails
    toward allowing everything -- a floor is where zero is dangerous, while a
    ceiling is where zero is safe. So there is no default, no skip and no
    warning the run proceeds past. There is also NO TOLERANCE: the limit came
    from the person, and an operator that widened it at run time would be
    changing an approved number.
    """
    snap: dict | None = None
    resolved: list[dict] = []
    for target in safety.get("targets", []) or []:
        for name, limit in (target.get("limits") or {}).items():
            spec = limit.get("resolved_from") if isinstance(limit, dict) else None
            if not spec:
                # A CONSTANT IS A LIMIT AND IT USED TO FALL OUT HERE. `continue`
                # walked past every limit that was already a number, so
                # objective_clearance_absolute_min -- the backstop -- never
                # entered this list and nothing downstream could see it. The
                # envelope says in as many words what that costs: "An operator
                # that reads one and not the other, or takes the last it
                # parsed, has one guard and a decoration."
                #
                # It is returned rather than skipped precisely BECAUSE it needs
                # no resolving: the comparison takes the larger of the two
                # floors, and a floor it cannot see is a floor it cannot take
                # the larger of.
                if isinstance(limit, dict) and limit.get("value") is not None:
                    resolved.append({
                        "kind": "constant",
                        "limit": name,
                        "target": target.get("target"),
                        "value": limit["value"],
                        "unit": limit.get("unit"),
                        "confirmation": (limit.get("confirmation") or {}).get("kind"),
                        "note": limit.get("note"),
                    })
                continue
            quantity = spec.get("quantity")
            resolver = RESOLVERS.get(quantity)
            if resolver is None:
                raise Refusal(
                    f"limit {name!r} resolves from {quantity!r} and this operator has no way to "
                    f"perform that lookup. A lookup nothing knows how to do is not one to skip: "
                    f"the bound would be absent and absent is not permissive (2.1 rule 2)"
                )
            if snap is None:
                snap = load_snapshot() if agent is None else load_snapshot(agent)
            answer = resolver(plan, snap)
            resolved.append({
                "kind": "lookup",
                "limit": name,
                "target": target.get("target"),
                "quantity": quantity,
                "keyed_by": spec.get("keyed_by"),
                "key": answer["key"],
                "value": answer["value"],
                "unit": answer["unit"],
                "grade": answer["grade"],
                "entry": answer["entry"],
                "number": answer["number"],
                "kb_version": snap.get("kb_version"),
                "built_from_commit": snap.get("built_from_commit"),
                "confirmation": (limit.get("confirmation") or {}).get("kind"),
                "note": answer["note"],
            })
    return resolved


_UNITS: dict | None = None


def si(value: float, unit: str) -> Fraction:
    """A magnitude in SI, converted through contracts/units.json and nowhere else.

    Two floors on one quantity arrive as 0.13 mm and 130 um, and comparing
    them means converting. Doing that with a factor written here would put
    the unit table in two places (P3), and the second copy is the one that
    goes stale.

    EXACT RATIONALS, NOT FLOATS, AND A RUN CAUGHT WHY. In binary,
    130 * 1e-6 is 0.00013 and 0.13 * 1e-3 is 0.00013000000000000002. Those
    are the same clearance written two ways, and the comparison refused one
    and permitted the other -- a plan asking for exactly the person's floor
    was rejected or accepted depending on which unit somebody typed it in.
    The two limits in this envelope coincide EXACTLY, so this boundary is
    not a corner case here, it is the only case.

    It is the rule already written for a record length arriving one ULP
    short of its planned end: a comparison at a boundary is a decision, not
    a measurement, and the size of the error has nothing to do with the size
    of the consequence. AND NO EPSILON -- widening a floor by a tolerance is
    changing the person's number at run time, which is the one thing an
    operator may never do. Fraction over the decimal text is exact, so the
    two spellings compare equal because they are equal.

    AN UNKNOWN UNIT REFUSES. A floor is where zero is dangerous, so a
    conversion this cannot do has to stop the run rather than fall back to
    the raw magnitude -- treating 130 as metres would pass everything and
    treating 0.13 as metres would fail everything, and only one of those is
    noticeable.
    """
    global _UNITS
    if _UNITS is None:
        _UNITS = json.loads((CONTRACTS / "units.json").read_text())["units"]
    row = _UNITS.get(unit)
    if row is None:
        raise Refusal(
            f"unit {unit!r} is not in contracts/units.json, so this magnitude cannot be "
            "compared against anything. A limit that cannot be converted is not one to "
            "compare loosely (2.1 rule 2)"
        )
    return Fraction(str(value)) * Fraction(str(row["si_factor"]))


# A floor is named `<quantity>_min` and a ceiling `<quantity>_max`
# (envelope_safety.schema.json), so the quantity a limit bounds comes off its
# own name -- except for one, and the schema says why in prose a reader can
# check and code cannot:
#
#   "the person ... asked for the names to be split. Only one landed -- and
#    not by oversight: `limits` enumerates its names and there was no second
#    clearance name to land in."
#
# So `objective_clearance_absolute_min` reads as a floor on
# `objective_clearance_absolute`, a quantity nothing measures, and the
# sentence that says otherwise -- "BOTH ARE MINIMA ON CLEARANCE" -- is in a
# $comment. This map is that sentence, and it is the whole of the
# hand-written part. A `bounds` field on the limit would retire it; raised.
BOUNDS = {"objective_clearance_absolute": "objective_clearance"}


def binding_limits(resolved: list[dict]) -> dict[str, dict]:
    """Per quantity, the one limit that actually binds.

    Minima: the LARGER binds. Maxima: the smaller. Stated by the envelope for
    the clearance pair and true of any two bounds in the same direction --
    obeying both is obeying the tighter one, and there is no case where
    reading only one is right.
    """
    binding: dict[str, dict] = {}
    for row in resolved:
        name = str(row.get("limit", ""))
        if name.endswith("_min"):
            quantity, tighter = name[:-len("_min")], max
        elif name.endswith("_max"):
            quantity, tighter = name[:-len("_max")], min
        else:
            raise Refusal(
                f"limit {name!r} names no direction. A floor is `<quantity>_min` and a "
                "ceiling `<quantity>_max` (envelope_safety.schema.json); a limit whose "
                "direction has to be guessed is one that could be applied backwards"
            )
        quantity = BOUNDS.get(quantity, quantity)
        # `si` is a Fraction and stays one all the way to the comparison. The
        # log needs JSON, so the float goes in beside it under a name that
        # says it is the lossy one -- and nothing compares that field.
        exact = si(row["value"], row["unit"])
        row = {**row, "quantity_bounded": quantity,
               "direction": "min" if tighter is max else "max",
               "si": exact, "si_float": float(exact)}
        held = binding.get(quantity)
        if held is None or tighter(row["si"], held["si"]) == row["si"] != held["si"]:
            binding[quantity] = row
    return binding


def check_envelope(plan: dict, resolved: list[dict]) -> list[dict]:
    """Compare the plan's numbers against the limits, and REFUSE on a breach.

    Until this existed `resolve_limits` ran, wrote its answer to the log and
    nothing read it -- a floor that was recorded and not enforced, which
    reads in a log exactly like one that held.

    Every comparison is returned, including the ones with nothing on the
    plan's side, because `compared: null` and a comparison that passed are
    different facts and a log that shows only breaches cannot tell them
    apart.
    """
    numbers = {n["name"]: n for n in plan.get("numbers") or []}
    out: list[dict] = []
    for quantity, limit in sorted(binding_limits(resolved).items()):
        number = numbers.get(quantity)
        row = {"quantity": quantity, "limit": limit["limit"], "direction": limit["direction"],
               "limit_value": limit["value"], "limit_unit": limit["unit"],
               "limit_si_float": limit["si_float"],
               "binds_over": sorted(r["limit"] for r in resolved
                                    if BOUNDS.get(str(r["limit"]).rsplit("_", 1)[0],
                                                  str(r["limit"]).rsplit("_", 1)[0]) == quantity)}
        if number is None:
            # NOT A PASS. The plan states no value for this quantity, so this
            # limit had nothing to act on -- which is a true statement about
            # this plan and not a verdict about the instrument. A quantity a
            # plan never names can still be moved by an action: a turret
            # rotation changes the clearance without any number saying so,
            # and the interlock in orchestrator.py is what covers that.
            row["compared"] = None
            out.append(row)
            continue
        got = si(number["value"], number["unit"])
        row["compared"] = {"value": number["value"], "unit": number["unit"],
                           "si_float": float(got)}
        breached = got < limit["si"] if limit["direction"] == "min" else got > limit["si"]
        row["within"] = not breached
        if breached:
            raise Refusal(
                f"{quantity} is {number['value']} {number['unit']} and "
                f"{limit['limit']} is {limit['value']} {limit['unit']}, which it "
                f"{'falls below' if limit['direction'] == 'min' else 'exceeds'}. No plan, "
                "no scope approval and no human approval may exceed a limit in "
                "envelope/safety.json (2.1 rule 7). Nothing is widened to fit: the number "
                "is the person's"
            )
        out.append(row)
    return out


# --------------------------------------------------------------------------- #
# O2 -- commands derived from fields, never composed (4.6.1)
# --------------------------------------------------------------------------- #

POWER_UP = {"set_power", "ramp_up", "open_shutter", "enable"}
POWER_DOWN = {"ramp_down", "close_shutter", "disable", "blank"}
ACQUIRE = {"acquire", "acquire_series", "snap", "stream"}


# --------------------------------------------------------------------------- #
# operation plans (plan.md 11-21, card 040): a move that verifies
# --------------------------------------------------------------------------- #

#: The interval between the writes of a RAMPED step. The schema gives a ramp a
#: rate and no interval, so one is chosen here; it is written into every
#: command it shapes, so the log says what paced the ramp. Not a limit.
RAMP_DT_S = 0.005


def _sine_point(move: dict, i: int) -> float:
    """Point i of a sine, from the integer index -- never from an accumulated phase."""
    c, a = float(move["centre_um"]), float(move["amplitude_um"])
    phase = 2 * math.pi * i / int(move["points_per_period"])
    start = move["start"]
    if start == "minimum":
        return c - a * math.cos(phase)
    if start == "maximum":
        return c + a * math.cos(phase)
    return c + a * math.sin(phase)                               # centre, rising


def _start_point(move: dict) -> float:
    return _sine_point(move, 0)


def readback_tolerance(plan: dict) -> dict:
    """The plan's own tolerance for a read-back, from targets[position_readback_error]."""
    for t in plan.get("targets", []) or []:
        if t.get("metric") == "position_readback_error" and t.get("unit") == "um":
            return {"value": t.get("value"), "unit": "um",
                    "from": "targets[position_readback_error]"}
    raise Refusal("an operation plan states no position_readback_error target in um, so no "
                  "read-back could be judged; condition 4 needs one")


def derive_operation(plan: dict) -> list[orch.Command]:
    """operation.moves -> one command per move, each carrying every point it will send.

    A step is one absolute write, or a ramp of writes paced from the integer
    index when it names `ramp_um_per_s` -- starting from the previous move's
    target on that axis, because a ramp needs a known start and a position read
    at run time would make the points depend on something not in the plan. A
    sine is `cycles * points_per_period` writes, point i at t0 + i * dt. The
    move before a sine on its axis must be a step to exactly the sine's start.
    Every point is checked against the envelope before anything is sent, by
    check_operation_points below.
    """
    op = plan["operation"]
    device = op.get("device", "")
    actions = {a.get("id"): a for a in plan.get("actions", []) or []}
    tolerance = readback_tolerance(plan)
    last_target: dict[str, float] = {}
    commands: list[orch.Command] = []
    for move in op.get("moves", []) or []:
        mid, axis, kind = move.get("id"), move.get("axis"), move.get("kind")
        action = actions.get(mid)
        if action is None or action.get("device") != device:
            raise Refusal(f"operation.moves[{mid}] has no action of the same id on {device!r}; "
                          "the move and the action that approves it must name each other")
        if action.get("reversible") is not True:
            raise Refusal(f"operation.moves[{mid}] is not marked reversible; an operation plan "
                          "carries reversible moves only (condition 6)")
        if kind == "step":
            target = float(move["target_um"])
            rate = move.get("ramp_um_per_s")
            if rate:
                if axis not in last_target:
                    raise Refusal(f"operation.moves[{mid}] ramps from an unknown start: a ramp "
                                  "has to follow a move on the same axis")
                start = last_target[axis]
                n = max(1, math.ceil(abs(target - start) / (float(rate) * RAMP_DT_S)))
                points = [[i, start + (target - start) * i / n] for i in range(1, n + 1)]
                dt = RAMP_DT_S
            else:
                points, dt = [[0, target]], RAMP_DT_S
            last_target[axis] = target
        elif kind == "sine":
            if last_target.get(axis) != _start_point(move):
                raise Refusal(f"operation.moves[{mid}] starts at its {move['start']} "
                              f"({_start_point(move)} um) and the move before it on {axis} does "
                              f"not end there ({last_target.get(axis)!r})")
            ppp, n = int(move["points_per_period"]), int(move["cycles"]) * int(move["points_per_period"])
            dt = float(move["period_s"]) / ppp
            points = [[i, _sine_point(move, i)] for i in range(1, n + 1)]
            last_target[axis] = points[-1][1]
        else:
            raise Refusal(f"operation.moves[{mid}] has kind {kind!r}, which is neither step nor sine")
        commands.append(orch.Command(
            channel=device, action="move_trajectory",
            params={"trajectory": {"move_id": mid, "axis": axis, "dt_s": dt, "points": points,
                                   "from": f"operation.moves[{mid}]"},
                    "tolerance_um": tolerance},
            from_field=f"operation.moves[{mid}]",
            tier=int(action.get("tier", 1)),
        ))
    return commands


def check_operation_points(plan: dict, commands: list[orch.Command], safety: dict) -> list[dict]:
    """Every derived point against the envelope, before the first is sent (condition 2).

    Check 86 checks the plan statically; this checks what was actually derived.
    A missing limit refuses. A point outside refuses, and if the plan claimed
    `inside` that is a disagreement between the plan and its derivation, said
    as one.
    """
    limits: dict[str, dict] = {}
    for target in safety.get("targets") or []:
        limits.update({k: v for k, v in (target.get("limits") or {}).items()
                       if k.startswith("piezo_")})
    claimed = (plan.get("envelope_check") or {}).get("status")
    out, bad = [], []
    for command in commands:
        traj = command.params["trajectory"]
        axis = traj["axis"]
        lo = limits.get(f"piezo_{axis}_position_min", {})
        hi = limits.get(f"piezo_{axis}_position_max", {})
        if lo.get("unit") != "um" or hi.get("unit") != "um" or lo.get("value") is None \
                or hi.get("value") is None:
            raise Refusal(f"{command.from_field}: envelope/safety.json has no piezo_{axis}_position "
                          "min and max in um; a missing limit refuses (condition 2)")
        xs = [x for _, x in traj["points"]]
        outside = [x for x in xs if not (lo["value"] <= x <= hi["value"])]
        out.append({"plan_field": command.from_field, "axis": axis, "points": len(xs),
                    "min_um": min(xs), "max_um": max(xs),
                    "limit_um": [lo["value"], hi["value"]], "inside": not outside})
        if outside:
            bad.append(f"{command.from_field}: {len(outside)} point(s) outside "
                       f"{lo['value']} to {hi['value']} um")
    if bad:
        raise Refusal(("the plan says its points are inside the envelope and its derivation "
                       "disagrees: " if claimed == "inside" else "") + "; ".join(bad))
    return out


# --------------------------------------------------------------------------- #
# trap steps (card 049 item 3): the tweezers, blind, from a plan's own fields
# --------------------------------------------------------------------------- #

#: One Tweez300 text command per step kind. Positions are ABSOLUTE only --
#: TRAP_POSITION, never TRAP_POSITION_REL -- because a relative command re-sent
#: after a lost reply moves the trap twice, and an absolute target can be
#: checked against the envelope before anything is sent.
TRAP_STEP_VERBS = {"create": "SIMPLE_TRAP_CREATE", "position": "TRAP_POSITION",
                   "strength": "TRAP_STRENGTH", "on": "TRAP_ON", "off": "TRAP_OFF",
                   "delete": "TRAP_DELETE"}


def derive_trap_steps(plan: dict) -> list[orch.Command]:
    """trap_steps.steps -> one command per step, each carrying the text lines it sends.

    `create` is three lines: create, position, strength -- a new trap starts at
    strength 0 (tweez300_new_trap_starts_at_strength_zero), so its position and
    strength are set before anything turns it on. `hold_for_person` derives no
    command: the tweezers are blind, so what the hold waits for can only be the
    person's statement, and the operator stops there rather than sending on.
    """
    ts = plan["trap_steps"]
    device = ts.get("device", "")
    actions = {a.get("id"): a for a in plan.get("actions", []) or []}
    commands: list[orch.Command] = []
    for step in ts.get("steps", []) or []:
        sid, kind = step.get("id"), step.get("kind")
        if kind == "hold_for_person":
            continue
        action = actions.get(sid)
        if action is None or action.get("device") != device:
            raise Refusal(f"trap_steps.steps[{sid}] has no action of the same id on {device!r}; "
                          "the step and the action that approves it must name each other")
        if action.get("reversible") is not True:
            raise Refusal(f"trap_steps.steps[{sid}] is not marked reversible")
        trap = step.get("trap")
        if not trap:
            raise Refusal(f"trap_steps.steps[{sid}] names no trap")
        if kind == "create":
            lines = [["SIMPLE_TRAP_CREATE", trap],
                     ["TRAP_POSITION", trap, float(step["x_um"]), float(step["y_um"])],
                     ["TRAP_STRENGTH", trap, float(step["strength"])]]
        elif kind == "position":
            lines = [["TRAP_POSITION", trap, float(step["x_um"]), float(step["y_um"])]]
        elif kind == "strength":
            lines = [["TRAP_STRENGTH", trap, float(step["strength"])]]
        elif kind in ("on", "off", "delete"):
            lines = [[TRAP_STEP_VERBS[kind], trap]]
        else:
            raise Refusal(f"trap_steps.steps[{sid}] has kind {kind!r}, which is not a trap step")
        commands.append(orch.Command(
            channel=device, action=f"trap_{kind}",
            params={"commands": lines, "step": {"id": sid, "kind": kind, "trap": trap,
                                                "from": f"trap_steps.steps[{sid}]"}},
            from_field=f"trap_steps.steps[{sid}]",
            # A trap switched on puts light on the sample, and one switched off
            # takes it away: the power rule orders them.
            raises_power=kind == "on", lowers_power=kind in ("off", "delete"),
            tier=int(action.get("tier", 1)),
        ))
    return commands


def check_trap_steps(plan: dict, commands: list[orch.Command], safety: dict,
                     objective_in_place: str | None) -> list[dict]:
    """Every derived position, strength and step against the envelope, before the first is sent.

    The person's names (envelope policy 8): `tweezers_trap_position_<objective>_{min,max}`,
    one range for x and y alike and for every trap, with the objective in the
    NAME -- the GUI's pixel-to-um calibration belongs to one objective and
    nothing reads it (objective_change_invalidates_trap_calibration), so a
    range is looked up only for the objective in place and a missing one
    refuses; `tweezers_trap_strength_{min,max}`; `tweezers_trap_step_max`.
    The objective in place is the person's hand-over statement. A position
    step is measured from the same trap's previous ABSOLUTE position in the
    plan; a trap whose first position has no known start is refused, never
    assumed to start at the centre.
    """
    limits: dict[str, dict] = {}
    for target in safety.get("targets") or []:
        limits.update({k: v for k, v in (target.get("limits") or {}).items()
                       if k.startswith("tweezers_trap_")})
    planned = (plan.get("trap_steps") or {}).get("objective")
    if not objective_in_place:
        raise Refusal("no objective stated at hand-over; a trap position means nothing in um "
                      "until the person has said which objective is in place")
    if planned != objective_in_place:
        raise Refusal(f"the plan is written for {planned!r} and the person states "
                      f"{objective_in_place!r} is in place")

    def need(name: str, unit: str) -> float:
        lim = limits.get(name)
        if not lim or lim.get("value") is None or lim.get("unit") != unit:
            raise Refusal(f"envelope/safety.json has no {name} in {unit}; a missing limit refuses")
        return float(lim["value"])

    out, bad = [], []
    last: dict[str, tuple[float, float]] = {}
    for command in commands:
        step = command.params["step"]
        for line in command.params["commands"]:
            verb = line[0]
            if verb == "TRAP_POSITION":
                trap, x, y = line[1], float(line[2]), float(line[3])
                lo = need(f"tweezers_trap_position_{objective_in_place}_min", "um")
                hi = need(f"tweezers_trap_position_{objective_in_place}_max", "um")
                for axis, v in (("x", x), ("y", y)):
                    if not lo <= v <= hi:
                        bad.append(f"{command.from_field}: {trap} {axis} = {v} um outside "
                                   f"{lo} to {hi} um at {objective_in_place}")
                if step["kind"] == "position":
                    if trap not in last:
                        raise Refusal(f"{command.from_field}: {trap} is moved before the plan "
                                      "has placed it, so the step's size is unknown")
                    step_max = need("tweezers_trap_step_max", "um")
                    px, py = last[trap]
                    d = math.hypot(x - px, y - py)
                    if d > step_max:
                        bad.append(f"{command.from_field}: {trap} moves {d:.3f} um in one step, "
                                   f"more than {step_max} um")
                last[trap] = (x, y)
                out.append({"plan_field": command.from_field, "trap": trap, "x_um": x, "y_um": y,
                            "objective": objective_in_place, "range_um": [lo, hi]})
            elif verb == "TRAP_STRENGTH":
                s = float(line[2])
                lo = need("tweezers_trap_strength_min", "1")
                hi = need("tweezers_trap_strength_max", "1")
                if not lo <= s <= hi:
                    bad.append(f"{command.from_field}: {line[1]} strength {s} outside {lo} to {hi}")
                out.append({"plan_field": command.from_field, "trap": line[1], "strength": s})
    if bad:
        raise Refusal("trap steps outside the envelope: " + "; ".join(bad))
    return out


def derive_commands(plan: dict) -> list[orch.Command]:
    """plan.json -> commands, mechanically.

    Every parameter carries the field path it came from. A command whose
    parameter cannot name its origin does not go out; orchestrator.Command
    refuses to be built without one.
    """
    if "operation" in plan:
        return derive_operation(plan)
    if "trap_steps" in plan:
        return derive_trap_steps(plan)
    numbers = {n["name"]: n for n in plan.get("numbers", [])}
    commands: list[orch.Command] = []

    # SELECTORS FIRST, AND THEY ARE COMMANDS. `$defs/selector` calls one "a
    # discrete setting the plan COMMANDS", and until the slot existed this
    # function had nothing to read them from -- so the first mock run set the
    # nosepiece and the magnification and acquired on camera_red WITHOUT
    # setting the port that puts the light on that arm. The commands were all
    # correct and the run was meaningless.
    #
    # They go before the actions because the order is physical: the path is
    # made, then the acquisition happens down it. Nothing sorts them among
    # themselves -- the plan's order is the plan's, and an operator that
    # reordered a path would be deciding something.
    #
    # A selector's params carry no unit and no grade, and the keys are ABSENT
    # rather than null. run_log.schema.json requires only `from` and types the
    # other two, so a null fails on its type while an omission is lawful --
    # and the omission is the true statement: a selector is a decision, a
    # decision makes no claim about the world, and there is nothing for a
    # grade to measure. Writing null said "this has a grade and it is
    # missing", which is a different and false thing. `from` still points at
    # the exact field, which is what check 14 reads.
    for selector in plan.get("system_configuration", {}).get("selectors", []) or []:
        element = selector.get("element", "")
        if not element:
            raise Refusal(
                "a selector with no `element` names nothing to command; "
                "common.schema.json requires it"
            )
        commands.append(orch.Command(
            channel=element,
            action=f"select_{element}",
            params={element: {
                "value": selector.get("value"),
                "from": f"system_configuration.selectors[{element}]",
            }},
            from_field=f"system_configuration.selectors[{element}]",
            tier=1,
        ))

    for index, action in enumerate(plan.get("actions", [])):
        # The field path names the action's ID and not its index. Check 66
        # matches `actions[<id>]` against the plan's own actions[].id to find
        # which dispatch carried something irreversible; an index matches no
        # id, so a log written with one reads as a run that dispatched nothing
        # irreversible at all -- a check passing because it found nothing to
        # look at. An id also survives a revision that reorders the list.
        aid = action.get("id")
        if not aid:
            raise Refusal(
                f"actions[{index}] has no id. Every command names the action it came from and "
                "an unnamed action cannot be named (4.6.1); plan.schema.json requires it"
            )
        params: dict[str, dict] = {}
        for name in action.get("parameters", []) or []:
            if name not in numbers:
                raise Refusal(
                    f"actions[{aid}] wants parameter {name!r}, which is not "
                    "in numbers[]. The card holds its numbers in one place and nowhere else (5.2)"
                )
            number = numbers[name]
            params[name] = {
                "value": number.get("value"),
                "unit": number.get("unit"),
                "grade": number.get("grade"),
                "from": f"numbers[{name}]",
            }
        verb = action.get("action", "")
        commands.append(orch.Command(
            channel=action.get("device", ""),
            action=verb,
            params=params,
            from_field=f"actions[{aid}]",
            raises_power=verb in POWER_UP,
            lowers_power=verb in POWER_DOWN,
            acquires=verb in ACQUIRE,
            tier=int(action.get("tier", 0)),
        ))
    return commands


# --------------------------------------------------------------------------- #
# O3 -- monitors compiled from the plan, decided by comparison (4.6.1)
# --------------------------------------------------------------------------- #

COMPARATORS = {
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "==": lambda a, b: a == b,
}


@dataclass
class Monitor:
    id: str
    metric: str
    comparator: str
    limit: float
    unit: str
    statement: str

    def violated(self, observed: float) -> bool:
        return not COMPARATORS[self.comparator](observed, self.limit)


def compile_monitors(plan: dict) -> list[Monitor]:
    """stop_criteria become comparisons before the run, not after it.

    Declaring the stopping rule in advance is the single most important line in
    this design (5.4). A criterion chosen after the data is not a result, it is
    a description of the data.
    """
    numbers = {n["name"]: n for n in plan.get("numbers", [])}
    monitors = []
    targets = {t.get("metric"): t for t in plan.get("targets", []) or []}
    for criterion in plan.get("stop_criteria", []) or []:
        name = criterion.get("number")
        if name is None and criterion.get("target") in targets:
            # An operation plan's criteria point at its own targets -- the
            # read-back tolerance is a decision the person approved, not a
            # number with a grade -- and plan.schema.json lets them.
            target = targets[criterion["target"]]
            comparator = criterion.get("comparator")
            if comparator not in COMPARATORS:
                raise Refusal(f"stop criterion {criterion.get('id')!r} uses comparator {comparator!r}, which is not machine readable")
            monitors.append(Monitor(
                id=criterion.get("id", criterion["target"]), metric=criterion.get("metric", ""),
                comparator=comparator, limit=target.get("value"), unit=target.get("unit", ""),
                statement=criterion.get("statement", "")))
            continue
        if name not in numbers:
            raise Refusal(f"stop criterion {criterion.get('id')!r} points at {name!r}, which is not in numbers[]")
        comparator = criterion.get("comparator")
        if comparator not in COMPARATORS:
            raise Refusal(f"stop criterion {criterion.get('id')!r} uses comparator {comparator!r}, which is not machine readable")
        monitors.append(Monitor(
            id=criterion.get("id", name),
            metric=criterion.get("metric", ""),
            comparator=comparator,
            limit=numbers[name]["value"],
            unit=numbers[name].get("unit", ""),
            statement=criterion.get("statement", ""),
        ))
    if not monitors:
        raise Refusal("the plan declares no stop criteria; a run with no stopping rule does not start (5.4)")
    return monitors


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #


def pre_stop_buffer_length(plan: dict) -> float | None:
    """The plan's `pre_stop_buffer.length_s`, or a refusal (plan.md 4.6.1, card 082).

    A plan authored by microscope_agent reaches a device, and a stop keeps and saves the last seconds
    before it, so how long is the plan's to say: there is no default and zero counts only if it is
    written (2.1 rule 2: unstated is a stop). A block that is there is judged by what the schema says of
    it -- an object whose only key is `length_s`, a finite number of at least 0 -- for any author. A plan
    authored by anyone else and carrying no block returns None: it is exempt, and the run records no
    buffer.
    """
    block = plan.get("pre_stop_buffer")
    if block is None:
        if plan.get("author") == "microscope_agent":
            raise Refusal(f"plan {plan.get('id')} was authored by microscope_agent and has no top-level "
                          "pre_stop_buffer block. A stop keeps and saves the last seconds before it, how "
                          "long is the plan's to say and there is no default; zero counts only if it is "
                          "written (plan.md 4.6.1: unstated is a stop). Nothing was sent")
        return None
    length = block.get("length_s") if isinstance(block, dict) else None
    if (not isinstance(block, dict) or set(block) != {"length_s"} or isinstance(length, bool)
            or not isinstance(length, (int, float)) or not math.isfinite(length) or length < 0):
        raise Refusal(f"plan {plan.get('id')}'s pre_stop_buffer block must be an object with exactly "
                      f"length_s, a number of seconds of at least 0, and has {block!r} (plan.md 4.6.1: "
                      "no rate field, no default). Nothing was sent")
    return length


def run(plan_path: Path, run_id: str, backend: str = "mock", observe=None,
        handover: dict | None = None, ask_person=None,
        tweezers_link: dict | None = None, runs_root: Path | None = None,
        root: Path | None = None, mm_config: Path | None = None,
        config_loader=None, watcher_backend=None, judgement_backend=None,
        approvals_dir: Path | None = None) -> dict:
    """O1 preflight -> O2 dispatch -> O3 watch -> O4 record.

    Returns the run record. Writes nothing until the gate has been passed,
    because a run directory that exists without an approval is itself the thing
    check 15 looks for.

    With `runs_root` (card 057), the run is followed as it happens:
    `<runs_root>/<run_id>/events.jsonl` is opened once the gate has passed,
    every event is appended as it is recorded, and a loopback stop channel
    is open for the length of the run. The folder must not exist yet -- a
    run id is never reused -- and `run_ended` closes the file however the
    run ends. Without it, nothing is written, as before.
    """
    # A TEST APPROVALS FOLDER IS MOCK ONLY (card 087), refused before anything is read or opened.
    approvals_dir = approvals_source(approvals_dir, backend)
    # A SCRATCH ROOT IS MOCK ONLY (card 063), refused before anything is read:
    # a TEST envelope, approval or list must never reach the instrument.
    if root is not None and backend != "mock":
        raise Refusal(f"a scratch root ({root}) is for the mock backend only, and this run asks "
                      f"for {backend!r}. TEST values never reach the instrument")
    # A CONFIGURATION IS LOADED ONLY BY A HARDWARE RUN (card 069). The mock loads none, so the
    # option is refused with it, not ignored: a command line that names a file and gets a run
    # that never touched it would say something false about what ran.
    if mm_config is not None and backend == "mock":
        raise Refusal(f"--mm-config {mm_config} is refused with the mock backend, not ignored: "
                      "the mock loads no Micro-Manager configuration, so a run that names one "
                      "would say it ran against a file it never touched")
    # THE WATCHER'S BACKEND IS THIS RUN'S ARGUMENT, never the plan's (plan.md 13.4 item 5), and it is
    # chosen before anything is read: the test double is refused on every backend but mock, so no
    # instrument run ever carries its answer. Named nowhere, it is `none`: states recorded, nobody asked.
    try:
        if callable(getattr(watcher_backend, "ask", None)):         # a backend object, as tests hand in
            if watcher_backend.kind == "test_double" and backend != "mock":
                raise watcher_mod.BackendRefused("the test double is refused on every backend but mock, so "
                                                 f"no instrument run ever carries its answer; this run's backend is {backend!r}")
            watcher_obj = watcher_backend
        else:
            watcher_obj = watcher_mod.make_backend(watcher_backend or "none", backend)
    except watcher_mod.BackendRefused as exc:
        raise Refusal(str(exc)) from None
    # THE JUDGEMENTS' BACKEND IS A RUN ARGUMENT TOO (plan.md 13.5, card 081), chosen the same way and refused
    # the same way: the test double on mock only, named nowhere it is `none` and asks nobody.
    try:
        if callable(getattr(judgement_backend, "judge", None)):
            if judgement_backend.kind == "test_double" and backend != "mock":
                raise watcher_mod.BackendRefused("the test double is refused on every backend but mock, so "
                                                 f"no instrument run ever carries its answer; this run's backend is {backend!r}")
            judge_obj = judgement_backend
        else:
            judge_obj = judgements_mod.make_backend(judgement_backend or "none", backend)
    except (watcher_mod.BackendRefused, judgements_mod.W.BackendRefused) as exc:
        raise Refusal(str(exc)) from None
    agent = agent_root(root)
    if root is not None and runs_root is None:
        runs_root = agent / "runs"
    plan = json.loads(Path(plan_path).read_text())
    if plan.get("card") != "plan":
        raise Refusal(f"{plan_path} is a {plan.get('card')!r} card, not a plan")
    pre_stop_length = pre_stop_buffer_length(plan)      # refuses before any lock, folder or command

    safety = load_safety() if root is None else load_safety(agent)     # refuses when absent
    # The approvals are read ONCE here: the file the log names is the file this decision judged.
    decision = (authorise(plan) if root is None and approvals_dir is None
                else authorise(plan, approvals_on_disk(agent, approvals_dir)))
    # ANOTHER LOGIN'S QUESTION is judged first and before anything else is looked at (card 089).
    console_item = console_gate(plan, decision, agent)
    plan_file = plan_path_of(plan_path)
    tier = highest_tier(plan)
    if "trap_steps" in plan and not decision.permitted:
        # Trap motion is motion, whatever tier its actions carry (check 85).
        raise Refusal(f"trap-step plan {plan.get('id')} is not approved: "
                      + "; ".join(decision.reasons))
    # A focus-search plan's approval is the FIRST check of its gate, inside
    # the run (card 066), so that "not approved" is refused with the encoder
    # read around it and leaves a refused log, like every other focus refusal.
    # Nothing is sent before that check, and the Z exemption asks it again.
    if "operation" in plan and not decision.permitted:
        # Condition 3 of an operation plan: each move approved by the person,
        # whatever tier its actions carry. A Tier 1 move of a stage is still a
        # move of a stage.
        raise Refusal(f"operation plan {plan.get('id')} is not approved: "
                      + "; ".join(decision.reasons))
    if tier >= 2 and not decision.permitted:
        raise Refusal(
            f"plan {plan.get('id')} reaches Tier {tier} and is not approved: "
            + "; ".join(decision.reasons)
        )

    monitors = compile_monitors(plan)
    commands = derive_commands(plan)
    if "focus_search" in plan:
        # The search derives its own moves through the gate; its action is not
        # dispatched as a plain command, which the allow-list would refuse.
        focus_from = f"actions[{plan['focus_search'].get('action')}]"
        commands = [c for c in commands if c.from_field != focus_from]

    # THE CONFIGURATION IS JUDGED BEFORE ANYTHING IS HELD OR LOADED (card 069): approved by
    # hash, its focus direction checked. With no run folder there is nowhere to keep the
    # derived copy, so the load does not happen.
    mm_checked = None
    if mm_config is not None:
        if runs_root is None:
            raise Refusal("a hardware load of a configuration needs --write: the derived copy of "
                          "the file is evidence and no run record would keep it anywhere else. "
                          "Nothing is loaded")
        mm_checked = _check_mm_config(mm_config)

    # ONE RUN AT A TIME (card 062): taken after the gate, so a refused plan
    # holds nothing, and before the orchestrator exists, so no run starts
    # beside another. Released however the run ends.
    lock = _take_run_lock({"kind": "plan", "plan_id": plan.get("id"), "run_id": run_id})
    try:
        o = orch.Orchestrator(backend=backend)
        o.pre_stop_length_s = pre_stop_length
        folder = None
        if runs_root is not None:
            folder = Path(runs_root) / run_id
            if folder.exists():
                raise Refusal(f"{folder} already exists. A run id is never reused; raise it (P9)")
            folder.mkdir(parents=True, exist_ok=True)
            watcher, watcher_event = watcher_mod.build(plan, watcher_obj, folder, o.clock.offset,
                                                       orch.is_light_command)
            judgements, judgements_event = judgements_mod.build(plan, judge_obj, folder, o.clock.offset)
            o.begin_run(folder, run_id=run_id, plan_id=plan.get("id"),
                        revision=plan.get("revision"), watcher=watcher, watcher_event=watcher_event,
                        judgements=judgements, judgements_event=judgements_event)
        elif plan.get("watcher") is not None:
            o.record(event="watcher_off", watcher={"why": "did_not_start", "detail": (
                "no run folder (no --write): the watcher keeps each state whole in the run folder, so "
                "it is not started")})
        else:
            o.record(event="watcher_off", watcher={"why": "plan_declares_no_watcher"})
        if folder is None and plan.get("judgements") is not None:
            o.record(event="judgements_off", **{"from": "judgements"}, judgements={"why": "did_not_start", "detail": (
                "no run folder (no --write): each request's context is kept whole in the run folder, so "
                "the judgements are not started")})
        mm_load = None
        if mm_checked is not None:
            mm_load = lambda: _load_mm_config(o, mm_checked, folder, config_loader)    # noqa: E731
        how = "failed"
        refusal = None
        try:
            if root is not None or approvals_dir is not None:
                o.plan_authoriser = lambda p: authorise(p, approvals_on_disk(agent, approvals_dir))
            record = _run_body(o, plan, run_id, backend, observe, handover, ask_person,
                               tweezers_link, safety, decision, monitors, commands,
                               agent=None if root is None else agent, mm_load=mm_load,
                               console_item=console_item, plan_file=plan_file)
            monitor_abort, failed = record.pop("_monitor_abort"), record.pop("_failed")
            how = ("stopped_from_outside" if getattr(o, "stopped_from_outside", False)
                   else "aborted_by_monitor" if monitor_abort
                   else "failed" if failed
                   else "completed")
            record["ended"] = how
            return record
        except (Refusal, orch.InterlockError) as exc:
            # A REFUSAL IS AN OUTCOME AND LEAVES A RECORD (card 065). It is
            # `refused` only if nothing went out: no dispatch and no Z move of
            # a focus search. A refusal raised after something was sent -- a
            # focus step refused above the limit after earlier steps moved Z
            # -- is a run that did something and stopped, so it stays
            # `failed`, and check 15 would fail it as a refusal.
            sent = [e for e in o.log if e.get("event") in _SENT_EVENTS]
            if not sent:
                how, refusal = "refused", str(exc)
            raise
        finally:
            if folder is not None:
                o.end_run(how)
                if refusal is not None:
                    write_run(_refused_record(o, plan, run_id, decision, safety, refusal, console_item, plan_file),
                              runs_root=folder.parent)
    finally:
        lock.release()


#: Events that mean something went out to a device: the dispatch events check
#: 15 counts, and a focus search's Z read back after a move.
_SENT_EVENTS = frozenset({"apply", "apply_failed", "dispatch", "focus_search_readback"})


def _refused_record(o, plan: dict, run_id: str, decision, safety: dict, refusal: str,
                    console_item: dict | None = None, plan_file: str | None = None) -> dict:
    """The log of a run refused inside operator.run, before anything went out (card 065)."""
    return {
        "artifact": "run_log", "schema_version": "0.1", "run_id": run_id,
        "plan_id": plan.get("id"), "revision": plan.get("revision"),
        "approval": approval_block(decision),
        **({"plan_path": plan_file} if plan_file else {}),
        **({"console_item": console_item} if console_item else {}),
        "safety_policy_version": safety.get("policy_version"),
        "stop_criteria": [c.get("id") for c in plan.get("stop_criteria") or []],
        **o.log_header(), "events": o.log,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ended": "refused", "refusal": refusal,
    }


def _check_mm_config(mm_config: Path, approvals_dir: Path | None = None) -> dict:
    """The configuration judged against the person's approvals in the runtime's folder."""
    try:
        return mm_gate.check(Path(mm_config), AGENT / "approvals" if approvals_dir is None
                             else Path(approvals_dir))
    except mm_gate.ConfigRefused as exc:
        raise Refusal(str(exc)) from None


def _load_mm_config(o, checked: dict, folder: Path, config_loader=None) -> dict:
    """Load the checked configuration through the micromanager module THIS run holds.

    The module is the orchestrator's own, so the core the loader opens is the core every later
    read goes to. `config_loader(mm, path)` is for tests: they hand in a fake core and no real
    Micro-Manager is needed. The event is recorded whether or not AutoShutter verified.
    """
    mm = o._device_module("micromanager", needed_by="the approved configuration's load")
    if config_loader is None:
        loader = mm.load_configuration
    else:
        def loader(path):
            return config_loader(mm, path)
    try:
        event = mm_gate.load(checked, folder, loader)
    except mm_gate.AutoShutterNotVerified as exc:
        o.record(**exc.event)
        raise Refusal(str(exc)) from None
    except mm_gate.ConfigRefused as exc:
        raise Refusal(str(exc)) from None
    o.record(**event)
    return event


def _run_body(o, plan: dict, run_id: str, backend: str, observe, handover, ask_person,
              tweezers_link, safety: dict, decision, monitors, commands,
              agent: Path | None = None, mm_load=None, console_item: dict | None = None,
              plan_file: str | None = None) -> dict:
    """run()'s body from the hand-over on, so run() can close the stream however it ends."""
    # The approved configuration is loaded first, and its event is the first thing the run
    # records: before the hand-over, before any preflight or focus read, so nothing is asked of
    # a core that has no configuration (card 069). AutoShutter not read back as 0 stops here.
    if mm_load is not None:
        mm_load()
    o.handover = dict(handover or {})
    if o.handover:
        o.record(event="handover", **o.handover)
    if "trap_steps" in plan and backend != "mock":
        # The link's timing numbers come from the caller, each with its source
        # (python_tcp.Link has no defaults), so the run log says where they came from.
        if not tweezers_link:
            raise Refusal("a trap-step plan on the instrument needs tweezers_link: host, port and "
                          "every timing number with numbers_from; python_tcp holds none of them")
        link = o.module_for(orch.TRAP_EXEMPT_DEVICE).connect(**tweezers_link)
        cal = o.handover.get("tweezers_calibration") or {}
        if cal:
            # Recorded in the tweezers' own exchange log too, beside every dispatch.
            link.confirm_calibration(by=cal.get("stated_by"), objective=cal.get("objective"),
                                     pixel_to_um=cal.get("pixel_to_um"),
                                     aod_field=cal.get("aod_field", "not stated"))
    record: dict = {
        # The collector picks up a json file only when it carries `card` or
        # `artifact`, so a run log without this pair is not rejected -- it is
        # ignored, and a log nothing reads is a log that proves nothing (P4).
        "artifact": "run_log",
        "schema_version": "0.1",
        "run_id": run_id,
        "plan_id": plan.get("id"),
        "revision": plan.get("revision"),
        "approval": approval_block(decision),
        # The inbox item that asked another login's question, read before the run (card 089):
        # present for such a plan only, since the record's schema has no null for it.
        **({"plan_path": plan_file} if plan_file else {}),
        **({"console_item": console_item} if console_item else {}),
        # envelope_safety.schema.json calls it `policy_version`, and this read
        # `version` -- a key no envelope has ever carried -- so every run would
        # have recorded null for the one field that says which ceilings it ran
        # under. The person raised the policy to 3 the same morning the focus
        # ceiling changed shape, which is exactly the change a run has to be
        # able to name afterwards.
        "safety_policy_version": safety.get("policy_version"),
        "stop_criteria": [m.id for m in monitors],
        **o.log_header(),
    }

    # O1. A limit that is a lookup becomes a number here, before preflight
    # touches anything -- and refuses if it does not resolve. The resolution
    # goes into the log rather than into the record's own fields: which
    # objective keyed it, which quantity, which value and out of which
    # kb_version. A resolved limit nobody can read back later is a limit
    # nobody can audit.
    resolutions = resolve_limits(plan, safety, agent)
    for resolution in resolutions:
        o.record(event="limit_resolved", **resolution)

    # AND THEN COMPARED, which is the half that was missing. A resolution
    # written to the log and never read is indistinguishable from a floor
    # that held.
    for comparison in check_envelope(plan, resolutions):
        o.record(event="limit_compared", **comparison)

    # Card 033: the whole plan is refused here if any command reaches outside
    # what software may command, before preflight touches anything.
    # Card 040 item 4: the allow-list over everything it binds, and for an
    # approved operation plan's piezo X/Y moves the derived-point envelope
    # check instead -- both inside check_software_motion_for, one call, so no
    # caller can lift the one without running the other.
    o.check_software_motion_for(plan, commands)
    o.preflight(sorted({c.channel for c in commands}))
    o.snapshot("before")
    if "trap_steps" in plan:
        dispatched = _run_trap_steps(o, plan, commands, ask_person)
    else:
        dispatched = o.dispatch(commands, plan=plan)
    if "focus_search" in plan:
        _run_focus_search(o, plan, agent)

    # A COMMAND THAT DID NOT HAPPEN STOPS THE PLAN. dispatch's return value
    # was read by nobody, so a refusal inside it left no mark on the run's
    # outcome -- the log said apply_failed and the operator carried on to the
    # acquire. A plan is the set of its steps; one of them refusing is not a
    # partial success to be reported afterwards.
    failed = [r for batch in dispatched for rows in batch["results"].values()
              for r in rows if r.get("ok") is False]
    monitor_abort = False
    if failed:
        o.abort(reason=("a command was refused or failed, so the plan did not happen as "
                        "approved: " + "; ".join(f"{r['command']}: {r['error']}"
                                                 for r in failed)[:400]))

    if observe is not None:
        # THE POINTS THE RUN REACHES (plan.md 13.5, card 081), which a plan's judgements name: `run_start`
        # after the commands went out and before the first measurement, then around each measurement
        # `before_measure:<stop criterion id>` and `after_measure:<id>`. Reaching one asks what the plan
        # names there and records; nothing is read back from it.
        o.reach_point("run_start")
        for monitor in monitors:
            if getattr(o, "stopped_from_outside", False):
                # Stopped from outside: the abort has run, and no monitor is
                # evaluated after it, so nothing more is decided on this run.
                break
            o.reach_point(f"before_measure:{monitor.id}")
            value = observe(monitor.metric)
            if getattr(o, "stopped_from_outside", False):
                break
            o.reach_point(f"after_measure:{monitor.id}")
            if value is None:
                o.record(event="monitor_blind", criterion=monitor.id, metric=monitor.metric)
                o.abort(reason=f"{monitor.metric} cannot be observed, so {monitor.id} cannot be evaluated")
                break
            if monitor.violated(value):
                monitor_abort = True
                o.record(event="stop_criterion_violated", criterion=monitor.id,
                         observed=value, limit=monitor.limit, unit=monitor.unit)
                o.abort(reason=f"{monitor.id}: {monitor.metric} = {value} {monitor.unit} breaks {monitor.comparator} {monitor.limit}")
                break

    o.snapshot("after")
    record["events"] = o.log
    record["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record["_monitor_abort"], record["_failed"] = monitor_abort, bool(failed)
    return record


def _run_focus_search(o, plan: dict, agent: Path | None) -> dict:
    """The plan's focus search: the copied core decides each branch, the gate derives each move.

    The decider is built BEFORE the first Z command, so a ceiling that is a
    gap, thresholds the plan does not carry, or a decider that is not built
    refuse with nothing moved. Its frames are the run's own: one snap of the
    camera at each Z, which also feeds the frame tap.
    """
    decider_mod = _load("_mic_focus_decider", Path(__file__).resolve().parent / "focus_decider.py")
    built = {}

    def method_ready():
        """Step 5 of the gate, after every safety check (card 066): build the decider."""
        try:
            decide = decider_mod.MetricMaximumDecider(
                plan, grab=lambda: o.acquire_snap(LIVE_VIEW_ROUTES["Kinetix_red"]))
        except decider_mod.DeciderRefused as exc:
            raise orch.InterlockError(f"focus search not started: {exc}") from None
        o.record(event="focus_decider_built", ceiling_adu=decide.ceiling,
                 thresholds=decide.thresholds, metric=decide.metric, bin_px=decide.bin_px,
                 blocks_per_side=decide.blocks_per_side,
                 **{"from": "focus_search.camera_ceiling, focus_search.verdict_thresholds"})
        built["decide"] = decide
        return decide
    loader = load_safety if agent is None else (lambda: load_safety(agent))
    try:
        result = o.run_focus_search(plan, load_safety=loader, method_ready=method_ready)
    finally:
        if "decide" in built:
            o.record(event="focus_decider_records", records=built["decide"].records)
    return result


def _run_trap_steps(o, plan: dict, commands: list, ask_person) -> list[dict]:
    """Trap steps one at a time, in the PLAN's order, stopping at every hold.

    Not one dispatch of the whole list: dispatch orders a batch by the power
    rule, which would move a trap's `off` ahead of the positions before it.
    A plan's step order is the plan's. Each step is its own dispatch, so the
    gate re-checks the approval and every derived value before each one.

    A step the GUI did not accept -- a rejection, a silence, or any line of a
    create that did not go -- stops the plan: the tweezers are blind, and what
    happens after a step that did not happen is unknown. A hold waits for the
    person's answer; no answer, or an answer that is not a plain yes, stops.
    """
    by_field = {c.from_field: c for c in commands}
    outcomes: list[dict] = []
    for step in plan["trap_steps"].get("steps", []) or []:
        field_ = f"trap_steps.steps[{step.get('id')}]"
        if step.get("kind") == "hold_for_person":
            statement = step.get("statement", "")
            answer = ask_person(statement) if ask_person else None
            o.record(event="hold_for_person", plan_field=field_, statement=statement,
                     answer=answer)
            said = str(answer or "").strip().lower()
            if said in ("abort", "stop"):
                # The person's call that something is wrong: this route stays,
                # and it is a failure, so run() aborts and the log says whose call.
                o.record(event="hold_aborted_by_person", plan_field=field_, answer=answer)
                outcomes.append({"rank": None, "results": {"hold": [{
                    "command": field_, "ok": False,
                    "error": f"the person answered {answer!r} at {field_}: abort"}]}})
                break
            if said not in ("yes", "y"):
                # A PLANNED STOP, NOT A FAILURE. A hold's other answer is how
                # the person ends the plan where they want it -- "stop here
                # with both traps on". It was marked ok False until
                # run-20260925-008, and run() then aborted, and the abort's
                # fan-out sent LASER_OFF: the plan said the traps stay on and
                # the laser went off. Nothing failed, so nothing aborts; the
                # plan ends with the instrument as the last accepted step left it.
                o.record(event="hold_declined", plan_field=field_, answer=answer,
                         note="the plan ends here as the person chose; no abort, no further command")
                outcomes.append({"rank": None, "results": {"hold": [{
                    "command": field_, "ok": True, "declined": True, "answer": answer}]}})
                break
            continue
        batch = o.dispatch([by_field[field_]], plan=plan)
        outcomes.extend(batch)
        rows = [r for b in batch for rs in b["results"].values() for r in rs]
        not_done = [r for r in rows if r.get("ok") is False or (
            isinstance(r.get("returned"), dict) and r["returned"].get("complete") is False)]
        if not_done:
            for r in not_done:
                r["ok"] = False
                r.setdefault("error", f"{field_} was not accepted in full by the tweezers GUI")
            break
    return outcomes


# --------------------------------------------------------------------------- #
# live view (card 062): a preparatory run the console switches on and off
# --------------------------------------------------------------------------- #

#: Which channel each device a live-view list may name is driven through.
#: Declared, not inferred from the label (check 80). The list's schema allows
#: exactly these two devices; a list naming another is refused before this
#: table is read.
LIVE_VIEW_ROUTES = {"DiaLamp": "stand_ti2e", "Kinetix_red": "camera_red"}

LIVE_VIEW_NO_PLAN = (
    "live view: the person switched the camera on from the console to find the sample "
    "(card 062, plan.md 11-25). It runs only the live-view list the person approved in "
    "approvals/, named by its sha256, and nothing else; it measures nothing, and its frames "
    "feed the frame tap and are not written to disk")
LIVE_VIEW_NOT_DISPATCHED = (
    "This run did not come through the plan dispatcher. A live view has no plan, so "
    "operator.run_live_view sets the transmitted lamp and runs the one camera sequence "
    "from the approved list's own fields. Each lamp write is asked of the allow-list "
    "(micromanager.refusal) before it is sent, and read back")


def check_live_view_list(doc: dict) -> dict:
    """The approved list's fields this run uses, or Refusal. Closed: anything unnamed refuses.

    The schema at contracts/schemas/live_view_list.schema.json holds the same
    shape at commit time. This is the run-time copy, because the file the
    host runs is the one on disk now, not the one a commit judged.
    EXCITATION IS REFUSED in this build: the schema lets a list add the Aura
    with a separate approval's reference, and checking that reference is not
    built here, so a list carrying it refuses rather than runs half-checked.
    """
    def need(cond, why):
        if not cond:
            raise Refusal(f"not a runnable live-view list: {why}")
    need(isinstance(doc, dict), "not a JSON object")
    need(doc.get("artifact") == "live_view_list", "artifact is not live_view_list")
    need(doc.get("schema_version") == "0.1", "schema_version is not 0.1")
    allowed = {"artifact", "schema_version", "written_by", "written_at", "label",
               "transmitted_lamp", "camera", "excitation"}
    need(not set(doc) - allowed, f"unknown fields {sorted(set(doc) - allowed)}")
    need("excitation" not in doc, "it adds excitation, which bleaches and needs its own "
         "approval; this host does not run excitation lists yet")
    need(isinstance(doc.get("written_by"), str) and doc["written_by"], "no written_by")
    need(isinstance(doc.get("written_at"), str) and doc["written_at"], "no written_at")
    lamp, cam = doc.get("transmitted_lamp"), doc.get("camera")
    need(isinstance(lamp, dict) and set(lamp) == {"device", "intensity"}
         and lamp.get("device") == "DiaLamp", "transmitted_lamp is not exactly DiaLamp and intensity")
    inten = lamp["intensity"]
    need(isinstance(inten, dict) and set(inten) <= {"value", "note"}
         and isinstance(inten.get("value"), (int, float)) and not isinstance(inten["value"], bool)
         and inten["value"] >= 0, "intensity.value is not a number >= 0")
    need(isinstance(cam, dict) and set(cam) == {"device", "exposure_ms", "frame_ceiling"}
         and cam.get("device") == "Kinetix_red", "camera is not exactly Kinetix_red, exposure_ms "
         "and frame_ceiling")
    need(isinstance(cam["exposure_ms"], (int, float)) and not isinstance(cam["exposure_ms"], bool)
         and cam["exposure_ms"] > 0, "exposure_ms is not a number > 0")
    need(isinstance(cam["frame_ceiling"], int) and not isinstance(cam["frame_ceiling"], bool)
         and cam["frame_ceiling"] >= 1, "frame_ceiling is not a whole number >= 1")
    return {"intensity": inten["value"], "exposure_ms": cam["exposure_ms"],
            "frame_ceiling": cam["frame_ceiling"], "lamp": "DiaLamp", "camera": "Kinetix_red"}


def run_live_view(list_path: Path, run_id: str, runs_root: Path | None = None,
                  backend: str = "mock", lock=None, started=None, on_orchestrator=None,
                  mm_config: Path | None = None, mm_approvals: Path | None = None,
                  mm_state: dict | None = None, config_loader=None) -> dict:
    """One live view: lamp on at the person's intensity, one sequence to the ceiling, lamp off.

    A preparatory run (plan.md 11-21): plan_id null, `no_plan_because`, and
    `approved_commands` naming the list by path and sha256 of its raw bytes.
    Frames go to the run's frame tap and nowhere else. "Off" is the run's own
    stop channel, which runs the usual abort(): lamp off, shutters closed,
    the sequence ended within a frame. Reaching the ceiling ends it as
    completed and switches the lamp off, read back.

    `lock` is a held run lock handed over by the live-view host, which took
    it before starting this run; without one this takes its own. It is
    released when the run ends, however it ends. `started` is a
    threading.Event set once `run_started` is written; `on_orchestrator` is a
    hook tests use to configure the mock.

    `mm_config` (card 069) is a configuration the person approved by sha256 under
    `mm_approvals`, loaded on hardware at the start of the host's first live view, into
    that run's own folder. `mm_state` is the host's memory of it: the core keeps the
    configuration for as long as the host runs, so a later live view records that it is
    already loaded and loads nothing again. The file is judged afresh at every live view.
    """
    import hashlib
    list_path = Path(list_path)
    data = list_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    lock = lock or _take_run_lock({"kind": "live_view", "run_id": run_id})
    try:
        values = check_live_view_list(json.loads(data.decode("utf-8-sig")))
        mm_checked = None
        if mm_config is not None:
            if backend == "mock":
                raise Refusal(f"a configuration ({mm_config}) is refused with the mock backend, "
                              "not ignored: the mock loads none")
            mm_checked = _check_mm_config(mm_config, mm_approvals)
            held = (mm_state or {}).get("loaded")
            if held is not None and held["sha256"] != mm_checked["sha256"]:
                # The core holds the file this host loaded. What is on disk now is another approved
                # file, and loading it over a running host is a decision for a restart, not a live view.
                raise Refusal(f"the approved configuration on disk (sha256 {mm_checked['sha256']}) is "
                              f"not the one this host loaded in {held['run_id']} ({held['sha256']}). "
                              "Restart the host to load it")
        root = AGENT / "runs" if runs_root is None else Path(runs_root)
        folder = root / run_id
        if folder.exists():
            raise Refusal(f"{folder} already exists. A run id is never reused; raise it (P9)")
        o = orch.Orchestrator(backend=backend)
        if on_orchestrator is not None:
            on_orchestrator(o)
        o.begin_run(folder, run_id=run_id, plan_id=None, revision=None)
        if started is not None:
            started.set()
        how = "failed"
        try:
            if mm_checked is not None:
                _live_view_mm_config(o, mm_checked, folder, config_loader, mm_state, run_id)
            _live_view_body(o, values)
            how = ("stopped_from_outside" if getattr(o, "stopped_from_outside", False)
                   else "failed" if o._aborted.is_set() else "completed")
        except Exception as exc:                                # noqa: BLE001 - recorded, then the lamp goes off
            o.record(event="live_view_failed", error=f"{type(exc).__name__}: {exc}")
            if not o._aborted.is_set():
                o.abort(reason=f"live view failed: {exc}")
        finally:
            o.end_run(how)
        try:
            approved_path = str(list_path.resolve().relative_to(REPO)).replace("\\", "/")
        except ValueError:
            approved_path = str(list_path.resolve())
        record = {
            "artifact": "run_log", "schema_version": "0.1", "run_id": run_id,
            "plan_id": None, "revision": None,
            "no_plan_because": LIVE_VIEW_NO_PLAN, "not_dispatched": LIVE_VIEW_NOT_DISPATCHED,
            "approved_commands": {"path": approved_path, "sha256": sha},
            "approval": {"id": None, "kind": None}, "stop_criteria": [],
            **o.log_header(), "events": o.log,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ended": how,
        }
        write_run(record, runs_root=root)
        return record
    finally:
        lock.release()


def _live_view_mm_config(o, checked: dict, folder: Path, config_loader, state: dict | None,
                         run_id: str) -> None:
    """Load the approved configuration once for this host, or record that it is already loaded.

    A file on disk that is not the one this host loaded was refused before the run began.
    """
    state = {} if state is None else state
    held = state.get("loaded")
    if held is None:
        event = _load_mm_config(o, checked, folder, config_loader)
        state["loaded"] = {"sha256": checked["sha256"], "loaded_sha256": event.get("loaded_sha256"),
                           "run_id": run_id}
    else:
        o.record(event="mm_config_already_loaded",
                 original={"path": checked["path"], "sha256": checked["sha256"]},
                 loaded_sha256=held["loaded_sha256"], loaded_in_run=held["run_id"])


def _live_view_lamp(o, prop: str, value, from_field: str) -> None:
    """One DiaLamp write: asked of the allow-list, sent as settings, read back, recorded."""
    mm = o._device_module("micromanager", needed_by="the live view's allow-list check")
    why = mm.refusal("DiaLamp", prop, "setProperty", value)
    if why is not None:
        raise Refusal(f"{from_field}: {why}")
    channel = LIVE_VIEW_ROUTES["DiaLamp"]
    params = {"settings": {"DiaLamp": {prop: value}}}
    returned = o.module_for(channel).apply(params)
    verification, note = o.verification_of(channel, returned)
    # Recorded in the run log's named-parameter form, each carrying its `from`
    # (run_log.schema.json, check 14); the exact settings sent sit beside it.
    o.record(event="apply", channel=channel, element="dia_lamp", action="set_dia_lamp",
             params={f"DiaLamp.{prop}": {"value": value, "from": from_field}},
             settings_sent=params, verification=verification, verification_note=note,
             **{"from": from_field})
    if verification != "readback":
        raise Refusal(f"{from_field}: DiaLamp.{prop} = {value!r} was not confirmed: {note}")


def _live_view_body(o, values: dict) -> None:
    """Lamp on (intensity, then State 1: power up last), exposure, the sequence, lamp off."""
    _live_view_lamp(o, "Intensity", str(values["intensity"]),
                    "approved_commands.transmitted_lamp.intensity")
    if o._aborted.is_set():
        return
    _live_view_lamp(o, "State", "1", "approved_commands.transmitted_lamp")
    camera = o.module_for(LIVE_VIEW_ROUTES["Kinetix_red"])
    if hasattr(camera, "set_exposure"):
        got = camera.set_exposure(values["exposure_ms"])
        o.record(event="apply", channel=LIVE_VIEW_ROUTES["Kinetix_red"], action="set_exposure",
                 params={"exposure_ms": {"value": values["exposure_ms"], "unit": "ms",
                                         "from": "approved_commands.camera.exposure_ms"}},
                 verification="readback" if got.get("verified") else "none",
                 verification_note=f"read back {got.get('read_ms')!r} ms",
                 **{"from": "approved_commands.camera.exposure_ms"})
    else:
        o.record(event="exposure_not_set", wanted_ms=values["exposure_ms"],
                 note="this backend has no exposure call; the mock's frames have no exposure")
    counted = [0]

    def discard(i, image, metadata):
        counted[0] += 1                         # not written: the tap is the only consumer
    out = o.acquire_sequence(LIVE_VIEW_ROUTES["Kinetix_red"], values["frame_ceiling"], discard)
    o.record(event="live_view_frames", wanted=values["frame_ceiling"],
             received=out.get("received"), aborted=bool(out.get("aborted")),
             written_to_disk=False, gaps=out.get("gaps"),
             note="frames fed the frame tap and nothing else", **{"from": "approved_commands.camera"})
    if not o._aborted.is_set():
        _live_view_lamp(o, "State", "0", "live_view.end: the lamp off at the frame ceiling")


def write_run(record: dict, deviations: list[dict] | None = None,
              runs_root: Path | None = None) -> Path:
    """runs/<run_id>/ is append-only; a second write makes a new run (P9).

    THE GUARD IS ON log.json, NOT ON THE FOLDER, since card 057. A followed
    run creates its folder at the start, to hold events.jsonl, so "the folder
    exists" no longer means "this run was written". The rule is unchanged: a
    second write still refuses, because log.json is what a write creates.
    run() refuses a run id whose folder already exists before it starts, so
    an id is still never reused.
    """
    folder = (AGENT / "runs" if runs_root is None else Path(runs_root)) / record["run_id"]
    if (folder / "log.json").exists():
        raise Refusal(f"{folder / 'log.json'} already exists. Runs are never overwritten; "
                      "raise the run id (P9)")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "log.json").write_text(json.dumps(record, indent=2) + "\n")
    (folder / "deviations.json").write_text(json.dumps(deviations or [], indent=2) + "\n")
    return folder


# --------------------------------------------------------------------------- #
# the way in
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    """S6 from a command line, which it had no way in from until 2026-09-20.

    Two halves were missing and only together are they a run. There was no
    entry point at all -- no `__main__` here or in orchestrator.py, so the
    only caller S6 ever had was a Python session someone typed by hand. And
    `run()` returns the record without writing it, so even that left nothing
    on disk: `write_run` existed, was correct, and nobody called it. A run
    that leaves no record is not a run (P1, P9), and 4.6's [O4] is the stage
    that makes it one.

    `--write` is opt-in rather than the default because `run()` reaches the
    instrument on a real backend and the directory is append-only -- a
    mistyped run id cannot be taken back, and P9 says to raise the id rather
    than overwrite. On mock nothing is at stake and the flag still costs one
    word, which is the right price for the one that leaves a trace.

    A refusal exits 2 and prints why. That is the normal outcome of a plan
    that is not approved, of an envelope that is absent and of a limit whose
    lookup does not resolve, and none of the three is an error in this file.
    """
    parser = argparse.ArgumentParser(description="S6: carry out an approved plan (4.6)")
    parser.add_argument("--plan", required=True, type=Path, help="path to plan_<agent>_<qid>.json")
    parser.add_argument("--run-id", required=True,
                        help="runs/<run_id>/ is created and never overwritten (P9)")
    parser.add_argument("--backend", default="mock",
                        help="mock is a first-class backend, not a test double (4.6.5)")
    parser.add_argument("--write", action="store_true",
                        help="write runs/<run_id>/; without it the record is printed and dropped")
    parser.add_argument("--mm-config", type=Path, default=None,
                        help="hardware only, with --write: a Micro-Manager configuration file the "
                             "person approved by sha256 under approvals/ (card 069)")
    parser.add_argument("--approvals", type=Path, default=None,
                        help="mock only: a test folder of approvals to read instead of "
                             "microscope_runtime/approvals/ (card 087). Refused with any other backend")
    parser.add_argument("--watcher-backend", default=None, choices=["none", "test_double"],
                        help="which backend answers the run-time watcher (card 076): none records states and "
                             "asks nobody; test_double is refused on every backend but mock. Never a plan field")
    parser.add_argument("--judgement-backend", default=None, choices=["none", "test_double"],
                        help="which backend answers DM-1, DM-2 and DM-4 (card 081): none asks nobody; test_double "
                             "is refused on every backend but mock. Never a plan field")
    parser.add_argument("--handover-objective", default=None,
                        help="the lens the person states is in place, passed exactly and never "
                             "inferred or defaulted (card 069)")
    args = parser.parse_args(argv)
    # What the person states on the command line is logged as theirs, in the hand-over event.
    handover = None if args.handover_objective is None else {
        "objective": args.handover_objective,
        "stated_by": "the person, on the command line (--handover-objective)"}

    try:
        # With --write the run is followed as it happens (card 057): its folder
        # and events.jsonl exist from the start, beside the stop channel.
        record = run(args.plan, run_id=args.run_id, backend=args.backend,
                     runs_root=AGENT / "runs" if args.write else None,
                     handover=handover, mm_config=args.mm_config, watcher_backend=args.watcher_backend,
                     judgement_backend=args.judgement_backend, approvals_dir=args.approvals)
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except orch.InterlockError as exc:
        print(f"INTERLOCK: {exc}", file=sys.stderr)
        return 2

    print(f"run {record['run_id']}: plan {record['plan_id']} revision {record['revision']}, "
          f"backend {record['backend']}, policy {record['safety_policy_version']}")
    print(f"  registry {record['registry_source']}")
    if record["approval"].get("file"):
        file = record["approval"]["file"]
        print(f"  approval {record['approval']['id']}: {file['path']} sha256 {file['sha256']}"
              + (f", signed through the console under login {file['signed_through']['login']}"
                 if file.get("signed_through") else ""))
    if record.get("console_item"):
        item = record["console_item"]
        print(f"  console item {item['item_id']} for {item['question_id']}: {item['path']} sha256 {item['sha256']}")
    refused = [e for e in record["events"] if e["event"] == "apply_failed"]
    for event in record["events"]:
        line = f"  {event['t_mono']:>9.3f}s {event['event']}"
        if event.get("channel"):
            line += f" {event['channel']}"
        if event.get("element"):
            line += f"/{event['element']}"
        if event.get("verification"):
            line += f"  verification={event['verification']}"
        if event["event"] == "limit_resolved":
            # A constant carries no key and no kb_version -- that is what
            # makes it a backstop rather than a second copy of the lookup --
            # so this reads them only when they are there. It said
            # event['key']['objective'] unconditionally and crashed the
            # moment constants started being resolved alongside lookups.
            line += f" {event['limit']}={event['value']} {event['unit']} ({event['kind']}"
            if event.get("key"):
                line += f": {event['key'].get('objective')}, {event.get('kb_version')}"
            line += ")"
        if event["event"] == "limit_compared":
            got = event.get("compared")
            line += (f" {event['quantity']} {'>=' if event['direction'] == 'min' else '<='} "
                     f"{event['limit_value']} {event['limit_unit']} [{event['limit']}"
                     + (f", the larger of {len(event['binds_over'])}"
                        if len(event.get("binds_over") or []) > 1 else "") + "] "
                     + (f"plan says {got['value']} {got['unit']}: "
                        + ("within" if event.get("within") else "BREACH")
                        if got else "the plan states no such number, so nothing was compared"))
        print(line)
    if args.write:
        folder = write_run(record)
        print(f"  wrote {folder.relative_to(REPO)}")
    else:
        print("  not written: pass --write to create runs/<run_id>/")
    if refused:
        # Non-zero, because a run whose commands were refused is not a run
        # that happened. The log is still written -- what was refused and why
        # is the record (P1) -- and the exit code is what a caller reads.
        print(f"  REFUSED: {len(refused)} command(s) did not happen, and the plan stopped there")
        for event in refused:
            print(f"    {event.get('element') or event['channel']}: {event['error']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
