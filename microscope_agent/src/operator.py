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
# screening.py and synthesis.py carry the same four lines. Three modules
# working around one filename is the argument for the rename, which is
# plan.md 7's and the design seat's.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
from dataclasses import dataclass, field                         # noqa: E402
from datetime import datetime, timezone                          # noqa: E402
from pathlib import Path                                         # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent
CONTRACTS = REPO / "contracts"


def _load(name: str, path: Path):
    """Import a module by path, registered under a name that collides with nothing."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                            # type: ignore[union-attr]
    return module


orch = _load("_mic_orchestrator", Path(__file__).resolve().parent / "orchestrator.py")


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


# --------------------------------------------------------------------------- #
# O0 -- the gate (6, 6.1, 2.1)
# --------------------------------------------------------------------------- #


def load_safety() -> dict:
    """Policy. A person writes it after confirming the limits physically.

    Absent is not permissive. With no safety policy on disk there is nothing to
    compare a condition against, and 2.1 rule 2 makes the default stop rather
    than proceed. This is also why the file was deliberately not extracted from
    the prior project (10.3 rule 4): a limit that migrated is not a limit
    anybody checked here.
    """
    path = AGENT / "envelope" / "safety.json"
    if not path.exists():
        raise Refusal(
            "envelope/safety.json does not exist. Nothing executes without a safety policy: "
            "there is no limit to compare a condition against, and an unknown limit is not a "
            "satisfied limit (2.1 rule 2, rule 7). A person writes this file after confirming "
            "the values on the instrument (10.3 rule 4)"
        )
    return json.loads(path.read_text())


def approvals_on_disk() -> list[dict]:
    """approvals/ is the one folder a person writes and the agent does not (7.1 rule 5)."""
    out = []
    folder = AGENT / "approvals"
    if not folder.exists():
        return out
    for path in sorted(folder.glob("*.json")):
        try:
            card = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise Refusal(f"{path.name} is not readable JSON: {exc}. An unreadable approval is not an approval")
        card["__path"] = str(path.relative_to(REPO))
        out.append(card)
    return out


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
        got = card.get("plan_hash")
        if got != wanted:
            reasons.append(
                f"{card['__path']} names this revision but its plan_hash does not match the plan on "
                f"disk. The plan changed after it was approved, so the approval is void (5.5)"
            )
            continue
        return Authorisation(True, ["individual approval matches this revision and hash"],
                             card.get("id"), "plan_approval", max_tier=2)

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


def load_snapshot() -> dict:
    """The KB as this agent copied it, and the only store this file reads.

    The librarian owns knowledge and cannot write here (P14, D11), so the copy
    into envelope/ is deliberate: which KB version entered this envelope, and
    when, is then a fact of this agent's own commit history. Reading
    librarian_agent/kb/ at run time would resolve a limit against whatever the
    store holds at that moment, and afterwards the run could not say what it
    resolved against.
    """
    path = AGENT / "envelope" / "snapshot.json"
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


def resolve_limits(plan: dict, safety: dict) -> list[dict]:
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
                snap = load_snapshot()
            answer = resolver(plan, snap)
            resolved.append({
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


# --------------------------------------------------------------------------- #
# O2 -- commands derived from fields, never composed (4.6.1)
# --------------------------------------------------------------------------- #

POWER_UP = {"set_power", "ramp_up", "open_shutter", "enable"}
POWER_DOWN = {"ramp_down", "close_shutter", "disable", "blank"}
ACQUIRE = {"acquire", "acquire_series", "snap", "stream"}


def derive_commands(plan: dict) -> list[orch.Command]:
    """plan.json -> commands, mechanically.

    Every parameter carries the field path it came from. A command whose
    parameter cannot name its origin does not go out; orchestrator.Command
    refuses to be built without one.
    """
    numbers = {n["name"]: n for n in plan.get("numbers", [])}
    commands: list[orch.Command] = []

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
    for criterion in plan.get("stop_criteria", []) or []:
        name = criterion.get("number")
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


def run(plan_path: Path, run_id: str, backend: str = "mock", observe=None) -> dict:
    """O1 preflight -> O2 dispatch -> O3 watch -> O4 record.

    Returns the run record. Writes nothing until the gate has been passed,
    because a run directory that exists without an approval is itself the thing
    check 15 looks for.
    """
    plan = json.loads(Path(plan_path).read_text())
    if plan.get("card") != "plan":
        raise Refusal(f"{plan_path} is a {plan.get('card')!r} card, not a plan")

    safety = load_safety()                       # refuses when absent
    decision = authorise(plan)
    tier = highest_tier(plan)
    if tier >= 2 and not decision.permitted:
        raise Refusal(
            f"plan {plan.get('id')} reaches Tier {tier} and is not approved: "
            + "; ".join(decision.reasons)
        )

    monitors = compile_monitors(plan)
    commands = derive_commands(plan)

    o = orch.Orchestrator(backend=backend)
    record: dict = {
        # The collector picks up a json file only when it carries `card` or
        # `artifact`, so a run log without this pair is not rejected -- it is
        # ignored, and a log nothing reads is a log that proves nothing (P4).
        "artifact": "run_log",
        "schema_version": "0.1",
        "run_id": run_id,
        "plan_id": plan.get("id"),
        "revision": plan.get("revision"),
        "approval": {"id": decision.approval_id, "kind": decision.kind},
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
    for resolution in resolve_limits(plan, safety):
        o.record(event="limit_resolved", **resolution)

    o.preflight(sorted({c.channel for c in commands}))
    o.snapshot("before")
    o.dispatch(commands)

    if observe is not None:
        for monitor in monitors:
            value = observe(monitor.metric)
            if value is None:
                o.record(event="monitor_blind", criterion=monitor.id, metric=monitor.metric)
                o.abort(reason=f"{monitor.metric} cannot be observed, so {monitor.id} cannot be evaluated")
                break
            if monitor.violated(value):
                o.record(event="stop_criterion_violated", criterion=monitor.id,
                         observed=value, limit=monitor.limit, unit=monitor.unit)
                o.abort(reason=f"{monitor.id}: {monitor.metric} = {value} {monitor.unit} breaks {monitor.comparator} {monitor.limit}")
                break

    o.snapshot("after")
    record["events"] = o.log
    record["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return record


def write_run(record: dict, deviations: list[dict] | None = None) -> Path:
    """runs/<run_id>/ is append-only; a second write makes a new run (P9)."""
    folder = AGENT / "runs" / record["run_id"]
    if folder.exists():
        raise Refusal(f"{folder} already exists. Runs are never overwritten; raise the run id (P9)")
    folder.mkdir(parents=True)
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
    args = parser.parse_args(argv)

    try:
        record = run(args.plan, run_id=args.run_id, backend=args.backend)
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except orch.InterlockError as exc:
        print(f"INTERLOCK: {exc}", file=sys.stderr)
        return 2

    print(f"run {record['run_id']}: plan {record['plan_id']} revision {record['revision']}, "
          f"backend {record['backend']}, policy {record['safety_policy_version']}")
    print(f"  registry {record['registry_source']}")
    for event in record["events"]:
        line = f"  {event['t_mono']:>9.3f}s {event['event']}"
        if event.get("channel"):
            line += f" {event['channel']}"
        if event.get("element"):
            line += f"/{event['element']}"
        if event.get("verification"):
            line += f"  verification={event['verification']}"
        if event["event"] == "limit_resolved":
            line += (f" {event['limit']}={event['value']} {event['unit']} "
                     f"({event['key']['objective']}, {event['kb_version']})")
        print(line)
    if args.write:
        folder = write_run(record)
        print(f"  wrote {folder.relative_to(REPO)}")
    else:
        print("  not written: pass --write to create runs/<run_id>/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
