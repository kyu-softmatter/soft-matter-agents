"""S3.0: keep only the configurations that can actually produce the observable.

Deterministic Python, no model (4.5). The screen reads contracts/ and nothing
else: no device table, no run history, and deliberately **no lessons** -- a
lesson may reorder candidates but may never remove one, and the surest way to
break that is to let screening see them (P16, 8.2).

Three things leave here: the surviving candidates, the kb_version pinned for
the whole fan-out, and one caller_id per (candidate, axis). The ids are issued
here because a sub-agent that chose its own could impersonate a sibling's, and
text found in a document could make it do so (4.3.1 rule 3).

This file knows no devices and imports none (7.2 rule 2). It has to run with no
instrument attached, or planning would need hardware to happen.

Reading contracts/ and nothing else is a statement about inputs. The entry
point at the bottom writes one thing, the stage's own record under
questions/<qid>/ (7.1), because a stage that leaves no trace cannot be audited
and the record is what a person reads when the screen stops.
"""

from __future__ import annotations

import os
import sys

# Running this file as a script puts its own directory at the head of
# sys.path, and this directory holds operator.py. `operator` is a
# standard-library module that `enum` imports during interpreter start-up, so
# the shadow does not wait to be asked for: `import argparse` below is enough
# to pull our operator.py into the middle of the standard library's own
# import and fail there. operator.py says the same thing from the other side
# and resolves it by loading its dependencies by path.
#
# Dropping this directory from sys.path costs nothing here -- this module
# imports no sibling -- and it has to happen before the first import that
# scans the path. sys and os are already loaded by the time any module body
# runs, so importing them does not scan it.
#
# The collision is in a fixed filename, not in this file: plan.md 7 names
# operator.py, and 4.6 already uses the term "system operator". Renaming it to
# system_operator.py would remove the collision for every caller instead of
# each caller working around it, and that rename belongs to the design seat.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import json                                                      # noqa: E402
import re                                                        # noqa: E402
from dataclasses import dataclass, field                         # noqa: E402
from datetime import datetime, timezone                          # noqa: E402
from pathlib import Path                                         # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent
CONTRACTS = REPO / "contracts"

AXES = ["a1", "a2", "a3", "a4", "a5", "a6", "a7"]


class ScreeningError(RuntimeError):
    """Raised when the inputs cannot be read. Not the same as a refusal:
    a refusal is an answer, this is the absence of one."""


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #


def load_capabilities(agent: str = "microscope") -> dict:
    return json.loads((CONTRACTS / "capabilities" / f"{agent}.json").read_text())


def load_vocabulary() -> dict[str, dict]:
    doc = json.loads((CONTRACTS / "observables.json").read_text())
    return {entry["id"]: entry for entry in doc.get("observables", [])}


def load_limits() -> dict:
    return json.loads((CONTRACTS / "validation_limits.json").read_text())


def pin_kb_version() -> str | None:
    """Fix the knowledge version for the whole fan-out (4.3.1).

    Siblings reading different KBs are not independent -- the difference is
    itself a channel between them -- and the question stops being reproducible.
    Returns None when no store is reachable; the caller then runs degraded.
    """
    path = REPO / "librarian_agent" / "kb" / "index.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text()).get("kb_version")
    except json.JSONDecodeError:
        return None


def produced_ids(configuration: dict) -> dict[str, list[str]]:
    """Normalise `produces` to {observable_id: [compositions required]}.

    An entry is either a bare id or an object naming what it has to be composed
    with. Optical trapping puts no light on a detector, so an observable that
    needs a trap is produced by the imaging configuration the trap rides on,
    and never by the trap alone.
    """
    out: dict[str, list[str]] = {}
    for entry in configuration.get("produces", []) or []:
        if isinstance(entry, str):
            out[entry] = []
        elif isinstance(entry, dict) and "id" in entry:
            out[entry["id"]] = list(entry.get("requires_composition", []))
        else:
            raise ScreeningError(f"produces entry is neither an id nor an object: {entry!r}")
    return out


# --------------------------------------------------------------------------- #
# candidates
# --------------------------------------------------------------------------- #


@dataclass
class Candidate:
    config: str
    devices: list[str]
    optical_path: str | None
    composed_with: list[str] = field(default_factory=list)
    grounds: str = ""

    def as_dict(self) -> dict:
        return {
            "config": self.config,
            "optical_path": self.optical_path,
            "devices": self.devices,
            "composed_with": self.composed_with,
            "grounds": self.grounds,
        }


@dataclass
class Rejection:
    config: str
    reason: str


@dataclass
class Screening:
    observable: str
    candidates: list[Candidate]
    rejected: list[Rejection]
    kb_version: str | None
    cap: int
    cap_unresolved: bool = False
    undiscriminating: list[str] = field(default_factory=list)
    degraded: list[str] = field(default_factory=list)

    @property
    def refused(self) -> bool:
        return not self.candidates


def screen(goal: dict, capabilities: dict | None = None) -> Screening:
    """Which configurations can produce this observable, and at most the cap.

    Screening asks one question -- can this configuration put this quantity on
    a detector -- and refuses to answer any other. Everything about how well it
    would do so belongs to S3, which has not run yet.
    """
    capabilities = capabilities or load_capabilities()
    vocabulary = load_vocabulary()
    limits = load_limits()
    cap = int(limits.get("max_configs_after_screening", 3))

    observable = (goal.get("observable") or {}).get("name", "")
    if not observable:
        raise ScreeningError("the goal card names no observable; S2 did not finish (4.5.1)")

    by_id = {c["config"]: c for c in capabilities.get("configurations", [])}
    candidates: list[Candidate] = []
    rejected: list[Rejection] = []

    if observable not in vocabulary:
        # Populated means absence is a real answer; provisional means the name
        # is simply undecided. Either way the question goes back to S2 rather
        # than being rewritten here -- the designer may not change the question
        # it was given (4.5).
        status = capabilities.get("status")
        reason = ("the vocabulary is fixed and does not define it"
                  if status == "populated" else
                  "the vocabulary is provisional and has not named it yet, which is undecided rather than impossible")
        return Screening(observable, [], [Rejection("(vocabulary)", reason)], pin_kb_version(), cap)

    for config_id in sorted(by_id):
        configuration = by_id[config_id]
        role = configuration.get("role", "imaging")
        produces = produced_ids(configuration)

        if role == "perturbation":
            rejected.append(Rejection(config_id, "perturbation: it drives the sample and produces no observable of its own"))
            continue
        if observable not in produces:
            rejected.append(Rejection(config_id, f"does not produce {observable!r}"))
            continue

        required = produces[observable]
        missing = []
        for partner_id in required:
            partner = by_id.get(partner_id)
            if partner is None:
                missing.append(f"{partner_id} is not a configuration")
            elif partner.get("role") != "perturbation":
                missing.append(f"{partner_id} is not a perturbation and cannot be composed in")
            elif config_id not in (partner.get("composes_with") or []):
                missing.append(f"{partner_id} does not compose with {config_id}")
        if missing:
            rejected.append(Rejection(config_id, "; ".join(missing)))
            continue

        grounds = f"declares {observable!r}"
        if required:
            grounds += f", composed with {', '.join(required)}"
        candidates.append(Candidate(
            config=config_id,
            devices=list(configuration.get("devices", [])),
            optical_path=configuration.get("optical_path"),
            composed_with=list(required),
            grounds=grounds,
        ))

    result = Screening(observable, candidates, rejected, pin_kb_version(), cap)
    if result.kb_version is None:
        result.degraded.append("librarian_agent")
    if len(candidates) > cap:
        apply_cap(result, goal, by_id)
    return result


def apply_cap(result: Screening, goal: dict, by_id: dict[str, dict]) -> None:
    """Cut to the cap using the goal's priorities -- or stop and say it cannot.

    4.5.3 caps the fan-out at three configurations and says to cut by the
    goal's priority. The priorities are physical_feasibility, target_accuracy,
    evidence_grade and cost, and **not one of them can be evaluated here**: all
    four need numbers that S3 produces, and S3 is what the cut is deciding
    whether to run. Cutting anyway would mean dropping a candidate on no
    grounds, which is the failure P16 names -- a configuration that is never
    tried never accumulates the record that would have justified trying it.

    So the cap goes unresolved and a person picks, once (4.5.1 branch c). The
    discriminator that would settle this case is not missing knowledge but a
    missing field: which contrast mechanism a configuration needs is written in
    prose in `label`, where deterministic code cannot read it.
    """
    usable: list[str] = []
    for term in goal.get("priority", []) or []:
        if term == "contrast" and all("contrast" in by_id[c.config] for c in result.candidates):
            usable.append(term)          # honoured once capabilities declares it
        else:
            result.undiscriminating.append(term)
    if not usable:
        result.cap_unresolved = True


# --------------------------------------------------------------------------- #
# outputs
# --------------------------------------------------------------------------- #


def caller_id(qid: str, config: str, axis: str) -> str:
    return f"{qid}:{config}:{axis}"


def fan_out(result: Screening, qid: str, limits: dict | None = None) -> list[dict]:
    """One sub-agent per (candidate, axis), with its id issued here."""
    limits = limits or load_limits()
    ceiling = int(limits.get("max_subagents_per_question", 21))
    jobs = [
        {"caller_id": caller_id(qid, c.config, axis), "config": c.config, "axis": axis,
         "kb_version": result.kb_version}
        for c in result.candidates for axis in AXES
    ]
    if len(jobs) > ceiling:
        raise ScreeningError(f"{len(jobs)} sub-agents exceeds the ceiling of {ceiling} (4.5.3)")
    return jobs


def to_configs(result: Screening, goal: dict, qid: str) -> dict:
    """questions/<qid>/configs.json -- the audit record of what survived.

    It carries no `card` or `artifact` discriminator on purpose: the validator
    fails an artifact kind it does not know, and no schema for this one exists
    yet. That makes this file unchecked, which is a gap and not a design -- a
    contract nobody checks is decoration (P4).
    """
    return {
        "schema_version": "0.1",
        "unvalidated": "no schema is registered for this artifact yet; contracts/ is the design seat's",
        "qid": qid,
        "stage": "S3.0",
        "observable": result.observable,
        "kb_version": result.kb_version,
        "cap": result.cap,
        "candidates": [c.as_dict() for c in result.candidates],
        "rejected": [{"config": r.config, "reason": r.reason} for r in result.rejected],
        "cap_unresolved": result.cap_unresolved,
        "priority_terms_not_evaluable_here": result.undiscriminating,
        "fan_out": fan_out(result, qid) if not result.cap_unresolved and result.candidates else [],
        "degraded": result.degraded,
        "screened_against": "contracts/capabilities/microscope.json and contracts/observables.json only; no lessons (P16)",
    }


def to_refusal(result: Screening, goal: dict, qid: str, created_at: str) -> dict:
    """A refusal is a first-class output, and it carries numbers (P5)."""
    reason_code = ("observable_not_producible"
                   if any(r.config == "(vocabulary)" for r in result.rejected)
                   else "no_capable_configuration")
    return {
        "card": "refusal",
        "schema_version": "0.1",
        "id": f"refusal-{qid}-s30",
        "qid": qid,
        "thread": goal.get("thread", f"solo-{qid}"),
        "round": goal.get("round", 0),
        "revision": goal.get("revision", 1),
        "author": "microscope_agent",
        "created_at": created_at,
        "status": "REFUSED",
        "stage": "S3.0",
        "refused_what": f"producing {result.observable!r} on this instrument",
        "reason_code": reason_code,
        "counterexample": [{
            "parameter": "capable_configurations",
            "required_number": "configurations_required",
            "limit_number": "configurations_available",
            "statement": "screening needs at least one configuration that declares this observable, and the capability table declares none",
        }],
        "numbers": [
            {"name": "configurations_required", "value": 1, "unit": "count",
             "source": "computed:screening_minimum", "grade": "E4"},
            {"name": "configurations_available", "value": len(result.candidates), "unit": "count",
             "source": "computed:screening", "grade": "E4"},
        ],
        "assumptions": [],
        "kb_refs": [],
        "degraded": result.degraded,
    }


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


QID_SHAPE = re.compile(r"^[a-z0-9-]+$")


def qid_of(goal: dict) -> str:
    """The qid names a folder, so it has to be usable as one.

    The validator's path rule expects questions/<qid>/ with the qid in
    [a-z0-9-]+ (8, the repository layout rule). Checking it here means a
    malformed id is refused before a directory is created under it, rather
    than leaving a folder nothing will ever look in.
    """
    qid = goal.get("qid", "")
    if not isinstance(qid, str) or not QID_SHAPE.match(qid):
        raise ScreeningError(
            f"the goal card's qid {qid!r} cannot name a folder: "
            "questions/<qid>/ requires [a-z0-9-]+ (7.1)"
        )
    return qid


def record_path(qid: str, refused: bool) -> Path:
    """Where the stage's record goes.

    A refusal is a card that leaves this agent, so it carries the identifier in
    its filename the way plan_microscope_<qid>.json does (7.1 rule 4).
    configs.json is an internal audit record and the path already says whose
    question it belongs to, so it stays short.
    """
    folder = AGENT / "questions" / qid
    name = f"refusal_microscope_{qid}_s30.json" if refused else "configs.json"
    return folder / name


def main(argv: list[str] | None = None) -> int:
    """Run S3.0 on a goal card and leave its record on disk.

    Nothing ran this stage before this block existed. screen(), to_configs()
    and to_refusal() were reachable only from a Python prompt, so the artifact
    7.1 asks for -- questions/<qid>/configs.json -- was written by nothing, and
    the stage could be exercised only by a throwaway script whose output went
    nowhere. A stage nobody can run from the repository is a stage whose
    behaviour is a claim.

    Exit codes, because a caller has to tell three outcomes apart without
    parsing prose:

      0  a record was written. What happened is in the record: candidates and a
         fan-out, or candidates with cap_unresolved and no fan-out, or a
         refusal card. A screen that stops at the cap exits 0 -- the stop is an
         outcome that got recorded, not a failure to produce one (4.5.1 c).
      2  the inputs could not be read, or the goal card is malformed. This is
         the absence of an answer rather than an answer, which is the line
         ScreeningError draws.
      3  a record for this qid already exists. Records are facts in this
         agent's commit history, so overwriting one silently would rewrite a
         fact; --force says to do it deliberately.
    """
    parser = argparse.ArgumentParser(
        description="S3.0: screen configurations for a goal card and record the result."
    )
    parser.add_argument("goal", type=Path, help="path to the goal card (4.5.1)")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing record for this qid")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the record and write nothing")
    args = parser.parse_args(argv)

    try:
        goal = json.loads(args.goal.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read the goal card: {exc}", file=sys.stderr)
        return 2
    if goal.get("card") != "goal":
        print(f"{args.goal} is not a goal card (card={goal.get('card')!r})", file=sys.stderr)
        return 2

    try:
        qid = qid_of(goal)
        result = screen(goal)
    except ScreeningError as exc:
        print(f"S3.0 could not run: {exc}", file=sys.stderr)
        return 2

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if result.refused:
        record = to_refusal(result, goal, qid, created_at)
    else:
        record = to_configs(result, goal, qid)
    blob = json.dumps(record, ensure_ascii=False, indent=2) + "\n"

    print(f"S3.0 {result.observable}: {len(result.candidates)} candidates, "
          f"{len(result.rejected)} rejected, cap {result.cap}")
    for c in result.candidates:
        print(f"  candidate {c.config}: {c.grounds}")
    for r in result.rejected:
        print(f"  rejected  {r.config}: {r.reason}")
    if result.cap_unresolved:
        print(f"  cap unresolved: {len(result.candidates)} candidates over a cap of "
              f"{result.cap}, and none of {', '.join(result.undiscriminating)} can be "
              "evaluated at S3.0. No fan-out; a person picks once (4.5.1 c).")
    if result.degraded:
        print(f"  degraded: {', '.join(result.degraded)} -- we do not know what we missed")

    path = record_path(qid, result.refused)
    if args.dry_run:
        print(f"--dry-run: would write {path.relative_to(REPO)}")
        print(blob, end="")
        return 0
    if path.exists() and not args.force:
        print(f"{path.relative_to(REPO)} already exists; --force overwrites it", file=sys.stderr)
        return 3
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(blob)
    print(f"wrote {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
