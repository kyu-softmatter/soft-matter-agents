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

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

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
        if card.get("plan_id") != plan_id or card.get("revision") != revision:
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
            "plan and against envelope/safety.json, which does not exist yet"
        )

    reasons.append(f"no plan_approval on disk names ({plan_id}, revision {revision})")
    return Authorisation(False, reasons)


def highest_tier(plan: dict) -> int:
    return max([int(a.get("tier", 0)) for a in plan.get("actions", [])] or [0])


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
        params: dict[str, dict] = {}
        for name in action.get("parameters", []) or []:
            if name not in numbers:
                raise Refusal(
                    f"actions[{index}] ({action.get('id')}) wants parameter {name!r}, which is not "
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
            from_field=f"actions[{index}]",
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
        "run_id": run_id,
        "plan_id": plan.get("id"),
        "revision": plan.get("revision"),
        "approval": {"id": decision.approval_id, "kind": decision.kind},
        "safety_policy_version": safety.get("version"),
        "stop_criteria": [m.id for m in monitors],
        **o.log_header(),
    }

    channels = sorted({c.channel for c in commands})
    o.preflight(channels)
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
