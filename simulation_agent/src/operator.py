"""S6 -- the system operator (plan.md 4.6).

It takes an approved plan, derives commands from it, watches the run against
the criteria the plan already declared, and records what happened. **It does
not change the plan.** If the plan and reality disagree, the disagreement is
recorded as a deviation; the plan is not edited to match.

Four things this file is careful about, each because the design says so:

**The gate is here, and what it demands depends on the tier.** The designer
stages hold Tier 0 and execute nothing; this module is the only one with
Tier 1-2.

* **Tier 0-1 is autonomous** -- a smoke run needs no approval card. It is
  gated on three things instead: the validator passed, the cost is inside the
  envelope, and it is inside the smoke budget. An autonomous run records
  `approval: {id: null, kind: null}`, which says it needed none; that is a
  different fact from failing to record one.
* **Tier 2 needs a person** -- an over-budget job or a change of physical
  model. It takes a `plan_approval` naming this exact `(plan_id, revision)`
  with a matching hash, or a live `scope_approval`. Nothing in this agent can
  write either.

**The limits are re-read here, not trusted from the plan.** O1 re-confirms
them (4.6), so the ceilings come off `envelope/budget.json` at run time rather
than out of the plan's `envelope_check` field. A plan that said `inside`
against an envelope that has since changed is exactly what re-confirming is
for. If the file is absent the run is refused: an unavailable ceiling is not a
satisfied one, and a cost model that supplied its own ceiling would make
"does not submit an over-budget job on its own" unenforceable.

**Commands are derived, never composed.** Every parameter handed to the
backend comes out of `plan.json` by name, and the log records which field it
came from (4.6.1, check 14). No model output reaches the backend.

**Stopping is deterministic.** The stop criteria are compiled into comparisons
and evaluated after every chunk. There is no model in the abort path (4.6.1).

**It imports the backend, never a device.** 7.2 rule 3: on this side the
operator sees backend modules and nothing below them.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import cards
from . import abp_backend
from . import hoomd_backend
from . import mock_backend
from . import trajectory

APPROVALS = cards.AGENT / "approvals"
RUNS = cards.AGENT / "runs"
ENVELOPE = cards.AGENT / "envelope" / "budget.json"

# Which budget a run is measured against. A smoke run that may spend the full
# allowance tells you nothing before the run it is supposed to precede, so the
# two are separate ceilings rather than one.
SMOKE, FULL = "smoke", "full"

# How the operator watches a submitted job. The budget is a guard against a
# backend that never reaches a terminal state, not a limit on the run: a run
# too long for it is over budget, which is the envelope's judgement and not
# this loop's.
#
# Polling buys observability at the price of latency: between two polls the
# job keeps going, so a stop criterion fires a poll-interval late. On a
# multi-hour engine run that is nothing; on the mock, which outruns any sane
# interval, a divergence monitor caught a run at frame 164 where the old
# synchronous loop caught it at frame 2. The trade is the right way round --
# an unobservable run cannot be stopped at all -- and the cost is put in the
# record rather than hidden: trajectory_meta reports how far the run actually
# got before it was stopped. Shrinking the interval further would spend CPU
# spinning, and the backend cannot close the gap itself because a backend that
# judged its own conditions would hold policy (4.6.5).
POLL_INTERVAL_S = 0.02
POLL_BUDGET_S = 600.0
PROGRESS_EVERY = 200

COMPARATORS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


class Refused(Exception):
    """The run does not start. Raised before anything is created."""


def plan_hash(plan: dict) -> str:
    """sha256 of the plan card with `status` removed, canonically (5.5).

    Status moves along the state machine on the same file, so hashing it would
    void an approval at the instant it was granted. The canonical form -- keys
    sorted, no spaces -- has to match the validator's byte for byte, or an
    approval that check 7 accepts would be one the operator rejects.
    """
    body = {k: v for k, v in plan.items() if k != "status"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()


def find_approval(plan: dict) -> dict:
    """The person's approval for this exact plan and revision (6.1).

    A plan_approval is looked for first, then a live scope_approval. Absence
    is the normal state until a person writes one, and it is a refusal rather
    than a warning: the gate is the reason the designer and the operator are
    separate things at all (4.6).
    """
    if not APPROVALS.exists():
        raise Refused(
            f"{APPROVALS.relative_to(cards.REPO)} does not exist. Only a person writes an "
            "approval card (6.1); no seat may create one, including this one."
        )
    for path in sorted(APPROVALS.glob("*.json")):
        card = json.loads(path.read_text())
        if card.get("card") == "plan_approval":
            if card.get("plan_id") != plan["id"] or card.get("plan_revision") != plan["revision"]:
                continue
            expected = plan_hash(plan)
            if card.get("plan_hash") != expected:
                raise Refused(
                    f"{path.name} approves {plan['id']} revision {plan['revision']} but carries a "
                    "different plan hash, so the plan changed after it was approved. An approval is "
                    f"valid for one exact card (5.5). The current hash is {expected}."
                )
            return card
        elif card.get("card") == "scope_approval":
            if card.get("voided"):
                continue
            if plan["qid"] in (card.get("qids") or []) or card.get("applies_to_all_qids"):
                return card
    raise Refused(
        f"no approval card names {plan['id']} revision {plan['revision']}. An approval is "
        "valid for one (plan_id, revision) only, so a changed plan needs a new one (5.5)."
    )


def max_tier(plan: dict) -> int:
    """The highest tier any action of this plan asks for (6)."""
    return max((int(a["tier"]) for a in plan.get("actions", [])), default=0)


def read_envelope() -> dict | None:
    """The person's ceilings, or None if they were never written (2.1 rule 7).

    Renamed from `envelope/safety.json` on 2026-09-20. The grade of harm is
    what differs: get the laser ceiling wrong and you lose an eye, get the
    wall clock wrong and you lose a night, and the same lock on the same door
    was never decided. There is no `safety.json` in this tree (7). What the
    rename drops is the physical-confirmation requirement and Tier 3, both
    meaningless about a disk quota; what it does not drop is the gate, because
    a run that cannot tell whether it is inside budget still stops.

    There is deliberately no fallback to the old name. A reader that takes
    whichever of two files happens to exist makes behaviour depend on the
    state of a migration, and picks one silently when they disagree -- which
    is the ambiguity P0 says to stop on rather than resolve.

    The file says what it is, and that is checked before it is believed.
    Reading a policy file without confirming it is one would let any JSON that
    happens to have a `targets` key act as a ceiling, and a safety decision
    reads fail-closed or it is not one (P0).
    """
    if not ENVELOPE.exists():
        return None
    envelope = json.loads(ENVELOPE.read_text())
    if envelope.get("artifact") != "envelope_budget":
        raise Refused(
            f"{ENVELOPE.relative_to(cards.REPO)} does not declare artifact envelope_budget "
            f"(it says {envelope.get('artifact')!r}); this is not the ceilings file"
        )
    if envelope.get("schema_version") != "0.1":
        raise Refused(
            f"{ENVELOPE.relative_to(cards.REPO)} is schema_version "
            f"{envelope.get('schema_version')!r}, which this operator does not read"
        )
    if not envelope.get("policy_version"):
        raise Refused(
            f"{ENVELOPE.relative_to(cards.REPO)} has no policy_version. Every run log records "
            "which policy it ran under, and a run that cannot name one cannot be read back (2.1)"
        )
    return envelope


def check_budget(plan: dict, budget: str, target: str) -> dict:
    """Re-confirm the cost against the ceilings in force, at run time (4.6 O1).

    The cost model belongs to this agent and the ceiling belongs to a person.
    Both halves have to be present for the comparison to mean anything, so an
    absent envelope is reported as `unavailable` rather than waved through.
    """
    nums = {n["name"]: n for n in plan["numbers"]}
    envelope = read_envelope()
    if envelope is None:
        return {
            "status": "unavailable",
            "target": target,
            "reason": (
                f"{ENVELOPE.relative_to(cards.REPO)} does not exist; a ceiling this agent "
                "derived from what the job needs would not be a ceiling. P0 rule 7 binds "
                "`safety.*` and not this file, so what a budget needs is that somebody who "
                "knows the machine chose the number -- `chosen_by` -- and not that anyone "
                "measured it."
            ),
        }
    targets = {row["target"]: row for row in envelope.get("targets", [])}
    if target not in targets:
        return {
            "status": "unavailable",
            "target": target,
            "reason": f"the envelope declares {sorted(targets)} and not {target!r}",
        }
    row = targets[target]
    # 5e05d58 moved every ceiling one level down into a per-agent `limits`
    # block and this read stayed flat, so it compared nothing while reporting
    # that it had compared. Descend once -- and refuse rather than crash on a
    # shape error, because read_envelope() checks the file's three
    # self-declarations and does not validate it against
    # envelope_budget.schema.json, so a malformed row arrives here intact.
    if "limits" not in row:
        return {
            "status": "unavailable",
            "target": target,
            "reason": (
                f"the {target!r} row carries no `limits` block, which "
                "envelope_budget.schema.json requires of every target"
            ),
        }
    ceilings = row["limits"]
    # The membership test below runs before anything looks at the type, so a
    # `limits` that is not an object used to be reported as a missing
    # `smoke_budget` -- the right refusal pointing at the wrong field, and a
    # reader believes a message. It was worse than a wrong sentence: only
    # `list` under `smoke` reached that message at all, and every other
    # non-object shape raised TypeError out of the membership test or the
    # subscript. One type check ahead of the membership test says what is
    # actually wrong and closes all of them.
    if not isinstance(ceilings, dict):
        return {
            "status": "unavailable",
            "target": target,
            "reason": (
                f"the {target!r} row's `limits` is {type(ceilings).__name__} and not an object, "
                "which envelope_budget.schema.json requires; nothing can be read under it"
            ),
        }
    if budget == SMOKE and "smoke_budget" not in ceilings:
        return {
            "status": "unavailable",
            "target": target,
            "reason": (
                f"the {target!r} limits carry no `smoke_budget`, which the schema requires of "
                "this agent. A smoke run that may spend the full budget tells you nothing "
                "before the run it precedes"
            ),
        }
    limits = ceilings["smoke_budget"] if budget == SMOKE else ceilings
    # The same defect one level down, and beyond what 005 named. `smoke_budget`
    # nests ceilings of its own, each a limit in its own right, so a non-object
    # there fails in exactly the way the block above was written against.
    if not isinstance(limits, dict):
        return {
            "status": "unavailable",
            "target": target,
            "reason": (
                f"the {target!r} limits carry a `smoke_budget` that is "
                f"{type(limits).__name__} and not an object, so it nests no ceilings"
            ),
        }
    compared, exceeded = [], []
    for cost_name, limit_name in (
        ("wall_clock_estimate", "wall_clock_max"),
        ("storage_estimate", "storage_max"),
    ):
        if cost_name not in nums or limit_name not in limits:
            continue
        cost = si(nums[cost_name])
        limit = si({**limits[limit_name], "name": limit_name})
        compared.append({"cost": cost_name, "limit": limit_name, "cost_si": cost, "limit_si": limit})
        if cost > limit:
            exceeded.append(f"{cost_name} exceeds {limit_name}")
    if not compared:
        return {
            "status": "unavailable",
            "target": target,
            "reason": "no cost number of this plan lines up with a ceiling in the envelope",
        }
    return {
        "status": "outside" if exceeded else "inside",
        "target": target,
        "budget": budget,
        "compared": compared,
        "exceeded": exceeded,
    }


def gate(plan: dict, budget: str, target: str) -> tuple[dict, dict]:
    """What this plan needs before it may run, by tier (6, standing orders).

    Returns (approval_record, envelope_record). The approval record is what the
    run log carries: a null id and kind is the honest state of an autonomous
    run, not a missing field.
    """
    tier = max_tier(plan)
    envelope = check_budget(plan, budget, target)

    if tier >= 2:
        approval = find_approval(plan)
        return {"id": approval["id"], "kind": approval.get("card", "plan_approval")}, envelope

    if envelope["status"] != "inside":
        raise Refused(
            f"tier {tier} runs autonomously, so no approval card is wanted -- but it is gated on "
            f"being inside the envelope, and that check reports {envelope['status']}: "
            f"{(envelope.get('reason') or '; '.join(envelope.get('exceeded', []))).rstrip('.')}. "
            "An unavailable ceiling is not a satisfied one."
        )
    return {"id": None, "kind": None}, envelope


def check_md_agrees(plan_path: Path, plan: dict) -> None:
    """The write-time check run again at execution time (4.6.2, P3).

    Check 9 compares the pair when the card is written. The operator compares
    them again before executing, because the file could have been edited since
    and the Markdown is what a person read before approving.
    """
    md = plan_path.with_suffix(".md")
    if not md.exists():
        return
    # Not rounded. `round(x, 12)` turned a WCA well depth of 4e-21 J into 0.0
    # and then refused the Markdown for stating the value the card holds; a
    # relative comparison needs no rounding and check 9 passes the same pair.
    known = {(float(n["value"]), n["unit"]) for n in plan["numbers"]}
    import re

    units = sorted((u for u in json.loads((cards.CONTRACTS / "units.json").read_text())["units"] if u != "1"), key=len, reverse=True)
    pattern = re.compile(
        r"(?<![A-Za-z0-9_.-])([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)[ \t]*("
        + "|".join(re.escape(u) for u in units)
        + r")(?![A-Za-z0-9_])"
    )
    for m in pattern.finditer(md.read_text()):
        value, unit = float(m.group(1)), m.group(2)
        if not any(u == unit and abs(v - value) <= max(abs(v), abs(value)) * 1e-9 for v, u in known):
            raise Refused(
                f"{md.name} states {m.group(0)!r}, which the plan's numbers do not hold. "
                "The Markdown never wins over the JSON; a disagreement stops the run (4.6.2)."
            )


def si(number: dict) -> float:
    """A plan value in SI, using the authoritative registry (D7)."""
    units = json.loads((cards.CONTRACTS / "units.json").read_text())["units"]
    factor = units[number["unit"]]["si_factor"]
    if factor is None:
        raise Refused(f"{number['name']} uses {number['unit']}, which has no fixed SI factor")
    return float(number["value"]) * float(factor)


def derive_commands(plan: dict) -> tuple[dict, list[dict]]:
    """plan.json -> backend parameters, mechanically (4.6.1).

    Returns the parameter map and its provenance: one entry per parameter
    saying which field of the plan it came from, which is what check 14 reads.
    """
    nums = {n["name"]: n for n in plan["numbers"]}
    params, provenance = {}, []
    for index, cond in enumerate(plan["conditions"]):
        number = nums[cond["number"]]
        params[cond["parameter"]] = si(number)
        provenance.append(
            {
                "parameter": cond["parameter"],
                "value_si": params[cond["parameter"]],
                "unit_in_plan": number["unit"],
                "from": f"conditions[{index}].number -> numbers[{cond['number']}]",
                "grade": number["grade"],
            }
        )
    return params, provenance


def compile_monitors(plan: dict) -> list[dict]:
    """Stop criteria as comparisons, in SI. No model in this path (4.6.1)."""
    nums = {n["name"]: n for n in plan["numbers"]}
    monitors = []
    for cr in plan["stop_criteria"]:
        monitors.append(
            {
                "id": cr["id"],
                "metric": cr["metric"],
                "comparator": cr["comparator"],
                "threshold_si": si(nums[cr["number"]]),
                # Absent means the old reading: met is the stop. Declared, it
                # says what being met *means*, which is the difference between
                # a run that finished and one that broke.
                "on_met": cr.get("on_met", "fault"),
                "from": f"stop_criteria[{cr['id']}].number -> numbers[{cr['number']}]",
            }
        )
    return monitors


def evaluate(monitors: list[dict], state: dict) -> list[dict]:
    """Which monitors say the run stops here, and why.

    `on_met` inverts the comparison for one of its three values, and that is
    the whole reason the field exists:

    * `continue` -- met means the guard held, so the **stop** is the comparison
      failing. A drift tolerance reads this way.
    * `complete` -- met means the run reached its planned end.
    * `fault` -- met means something broke.

    Reading the comparison the same way for all three is what produced the
    inference this replaces. A metric the backend does not report is not a
    pass: it is simply not evaluated, and that is recorded rather than assumed.
    """
    fired = []
    for m in monitors:
        if m["metric"] not in state:
            continue
        met = COMPARATORS[m["comparator"]](state[m["metric"]], m["threshold_si"])
        stops = (not met) if m["on_met"] == "continue" else met
        if stops:
            fired.append({
                **m,
                "met": met,
                "outcome": "complete" if m["on_met"] == "complete" else "fault",
            })
    return fired


def _capability_row(config: str) -> dict | None:
    """The configuration's row in the capability table, or None.

    Read rather than cached: the table is `contracts/` and four seats change
    it, so a copy taken at import would be a copy of whatever the tree held
    when this session started.
    """
    import json as _json                              # noqa: PLC0415

    path = cards.CONTRACTS / "capabilities" / "simulation.json"
    try:
        table = _json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    for row in table.get("configurations", []):
        if row.get("config") == config:
            return row
    return None


def backend_name(backend) -> str:
    """What answered, refused rather than defaulted.

    Both call sites used to read the backend's `NAME` with a getattr default
    falling back to the mock module's own, and **a default that names a
    specific backend is the one shape this field must not have.** The literal
    is described rather than quoted here on purpose: card 014's open/closed
    condition greps the source for it, and a comment reproducing the string
    would report the line as still present. A backend without `NAME` produced
    neither an error nor a blank but the string "mock_backend", so the run
    record asserted that an engine answered which had not.

    It happened. `run-20260922-hoomd-s1` carries `mock_backend` in its log and
    its config while holding HOOMD's trajectory bit for bit -- same seed, same
    `parameters_si`, same `plan_hash`, same budget as `run-20260922-mock-s1`,
    and a different curve from it. That run executed at 01:31:54 and both
    backend files have mtime 01:34:00, so it ran on code three minutes older
    than the fix that gave `HoomdBackend` its name.

    **A run is the evidence itself**, which is what makes this worse than the
    same fault one turn back in `009`, where the log did not say which PLAN it
    opened. 4.6.5 defines reproducibility as *the same plan.json running
    unchanged on the mock and on the real instrument*, and a mock-against-
    engine comparison means nothing unless which one ran is true. So there is
    no default here: a backend that cannot say what it is stops the run.
    """
    name = getattr(backend, "NAME", None)
    if not isinstance(name, str) or not name:
        raise Refused(
            f"the backend {type(backend).__name__} carries no NAME, so this run cannot record "
            "which engine produced it. There is deliberately no default: the previous default "
            "named mock_backend, and a run record that misattributes its engine makes every "
            "mock-against-engine comparison resting on it unverifiable (4.6.5)"
        )
    return name


def backend_seed(backend, requested: int) -> int:
    """Which seed the backend actually used, refused rather than defaulted.

    `014` removed two `getattr(..., default)` reads one line above this one and
    did not see this third. Both backends carry `.seed` today so it reads
    correctly -- which is the exact state `NAME` was in until 2026-09-22, when
    the first HOOMD run recorded itself as a mock run.

    **Wrong, this costs more than the label did.** `config.json` would record
    the seed that was REQUESTED rather than the one that ran, and
    `config.json` is the basis for reproducing a run. A false backend label
    shows up the moment anyone compares two trajectories; a false seed
    reproduces nothing and announces nothing, because the field you would
    check it against is this field.
    """
    used = getattr(backend, "seed", None)
    if not isinstance(used, int):
        raise Refused(
            f"the backend {type(backend).__name__} does not report which seed it used, so this "
            f"run cannot be reproduced from its own config. The requested seed was {requested!r} "
            "and there is deliberately no fallback to it: recording a requested seed as though "
            "it were the one that ran is the one way this field can be worse than absent"
        )
    return used


def arm_view(plan: dict, arm: str | None) -> tuple[dict, dict | None]:
    """The plan as ONE ARM of a compare sees it, and the arm's own cost.

    A compare plan holds the conditions every arm shares in `conditions` and
    the one that differs in `compare_arms[].conditions` (check 34). The
    operator runs one arm at a time, so the arm's condition is appended to
    the shared list for `derive_commands` -- in a copy; the plan on disk and
    its hash are untouched, and config.json records which arm ran.

    The envelope is compared against the ARM's cost when the plan carries
    it. The plan's wall_clock_estimate and storage_estimate are the sum over
    kept arms (that is what the plan-time check compares), and a smoke run
    of the smallest arm would otherwise be refused for the cost of the
    largest. The arm's numbers are the plan's own -- particle_steps_arm_<arm>
    and coordinates_stored_arm_<arm> against particle_step_rate and
    bytes_per_coordinate -- so nothing is estimated here; when the plan does
    not carry them the plan-level numbers stand and the record says so.
    """
    if arm is None:
        return plan, None
    # One name serves both shapes a plan can take: an arm of a compare or a
    # point of a sweep (plan.schema.json: a card carries one or the other,
    # never both). Either is a condition set appended to the shared ones,
    # and either may carry its own cost under the plan's per-arm or per-cell
    # numbers. A skipped sweep point is refused: S4 dropped it with numbers,
    # and running it anyway would be the operator overruling the plan.
    arms = {a.get("arm"): a for a in plan.get("compare_arms") or []}
    points = {p.get("point"): p for p in (plan.get("sweep") or {}).get("points") or []}
    if arm in arms:
        chosen = arms[arm]
    elif arm in points:
        chosen = points[arm]
        if chosen.get("skipped"):
            raise Refused(f"sweep point {arm!r} was skipped by S4: {chosen['skipped']}. The operator does not run a cell the plan dropped (4.6)")
    else:
        raise Refused(f"the plan has no compare arm or sweep point named {arm!r}; it has arms {sorted(arms)} and points {sorted(points)}")
    view = dict(plan)
    view["conditions"] = list(plan["conditions"]) + list(chosen["conditions"])
    nums = {n["name"]: n for n in plan["numbers"]}
    steps = nums.get(f"particle_steps_arm_{arm}") or nums.get(f"particle_steps_{arm}")
    coords = nums.get(f"coordinates_stored_arm_{arm}") or nums.get(f"coordinates_stored_{arm}")
    rate, bytes_per = nums.get("particle_step_rate"), nums.get("bytes_per_coordinate")
    cost = None
    frames_n = nums.get(f"particle_frames_saved_arm_{arm}") or nums.get(f"particle_frames_saved_{arm}")
    frame_cost = nums.get("particle_frame_cost")
    if steps and coords and rate and bytes_per:
        wall_s = si(steps) / si(rate)
        # The second term (task 023): every saved frame is a round trip out of
        # the engine, and that scales with frames, not steps. sim-20260923-003
        # v4 was estimated at 40 s on the first term alone and ran over an
        # hour. Absent either number the first term stands alone and `from`
        # says so, rather than a zero standing in for a cost nobody measured.
        if frames_n and frame_cost:
            wall_s += si(frames_n) * si(frame_cost)
        # GB is the registry's base for storage (si_factor 1), so si() of a
        # bytes-per-coordinate written in GB is already gigabytes and the
        # product needs no further division. The first smoke run recorded
        # 4.8e-12 GB for a 4.8 MB record because this line divided by 1e9 twice.
        store_gb = si(coords) * si(bytes_per)
        replaced = [n for n in plan["numbers"] if n["name"] not in ("wall_clock_estimate", "storage_estimate")]
        replaced += [
            {"name": "wall_clock_estimate", "value": wall_s, "unit": "s", "source": "computed:arm_cost", "grade": steps["grade"]},
            {"name": "storage_estimate", "value": store_gb, "unit": "GB", "source": "computed:arm_cost", "grade": coords["grade"]},
        ]
        view["numbers"] = replaced
        cost = {"arm": arm, "wall_clock_s": wall_s, "storage_gb": store_gb,
                "from": [steps["name"], rate["name"], coords["name"], bytes_per["name"]]
                        + ([frames_n["name"], frame_cost["name"]] if frames_n and frame_cost else []),
                "frame_term": "included" if frames_n and frame_cost else "not in the plan: first term only",
                "note": "the arm's cost from the plan's own per-arm numbers; the plan-level estimates are the sum over kept arms"}
    return view, cost


# The parameters a smoke fraction may shorten: the record, under the two names
# plans here give it. The save interval is never touched, so steps and saved
# frames shrink together and the two cost terms keep their ratio (task 023).
DURATION_PARAMS = ("record_length", "total_simulated_time")


def smoke_view(plan: dict) -> tuple[dict, dict]:
    """The plan as a smoke run sees it: the record shortened by the fraction the plan declared.

    The operator never chooses the size -- that would be widening or narrowing
    what the plan fixed -- so a plan without `smoke.record_fraction` is refused
    here, naming the missing number. The plan on disk and its hash are
    untouched; the shortened value goes to derive_commands in a copy and its
    provenance names both numbers it came from.
    """
    ref = (plan.get("smoke") or {}).get("record_fraction")
    nums = {n["name"]: n for n in plan["numbers"]}
    if not ref:
        raise Refused(
            "a smoke run needs its size declared by the plan, and this plan declares none: add "
            "`smoke: {\"record_fraction\": \"smoke_record_fraction\"}` and the number "
            "`smoke_record_fraction` (unit 1, 0 < value <= 1). The operator does not choose it; a "
            "smoke run at full size measures the same job against a tighter ceiling and calibrates nothing")
    if ref not in nums:
        raise Refused(f"smoke.record_fraction names {ref!r}, which is not in the plan's numbers[]")
    frac = si(nums[ref])
    if not 0 < frac <= 1:
        raise Refused(f"{ref} is {frac}; a smoke fraction lies in (0, 1]")
    conds = [c for c in plan["conditions"] if c["parameter"] in DURATION_PARAMS]
    if len(conds) != 1:
        raise Refused(f"a smoke fraction shortens exactly one record parameter, one of {DURATION_PARAMS}; "
                      f"the plan's conditions carry {[c['parameter'] for c in conds]}")
    target = conds[0]["number"]
    view = dict(plan)
    scaled = []
    for n in plan["numbers"]:
        if n["name"] == target or n["name"] in ("wall_clock_estimate", "storage_estimate"):
            n = {**n, "value": n["value"] * frac,
                 "smoke": f"{n['name']} x numbers[{ref}] = {n['value']} x {frac}"}
        scaled.append(n)
    view["numbers"] = scaled
    return view, {"record_fraction": frac, "from": f"smoke.record_fraction -> numbers[{ref}]",
                  "parameter": conds[0]["parameter"], "number": target}


def run(qid: str, run_id: str, backend=None, seed: int = 1,
        budget: str = SMOKE, target: str = "local",
        revision: int | None = None, arm: str | None = None) -> Path:
    """O1 preflight, O2 dispatch, O3 monitor, O4 record.

    Raises Refused before creating anything if the gate is shut.

    **A revision is a different experiment, not a newer copy of one**, which
    is why a runner has to know about revisions at all. This resolved
    `plan_simulation_<qid>.json` unconditionally until 2026-09-20 -- revision
    1's filename -- so once the question moved to revision 2 the operator ran
    the discarded plan: 2 um beads where the measurement said 5 um, with the
    window and the record length that went with them. **It did not fail.** It
    wrote `rev 1` and finished green, and check 15 then compared that log
    against revision 1's card and found them agreeing.

    That is the same hardcoded-filename fault `load_goal` had, and it is worse
    here for a reason worth keeping: a goal is CITED, so reading a stale one
    produces a value mismatch that check 12 shows you 46 times. A plan is
    EXECUTED, so reading a stale one produces a perfectly consistent run of the
    wrong experiment, and nothing anywhere disagrees.

    The default is the question's current revision; pass one explicitly to
    repeat an older run on purpose. Both are legitimate and the log has to tell
    them apart -- see below.
    """
    revision = cards.question_revision(qid) if revision is None else revision
    plan_path = cards.question_dir(qid) / cards.artifact_name(
        f"plan_simulation_{qid}.json", revision)
    if not plan_path.exists():
        raise Refused(
            f"revision {revision} of {qid} has no plan at "
            f"{plan_path.relative_to(cards.REPO)}. A revision is a different experiment, so "
            "there is nothing to fall back to: running the previous revision's plan under this "
            "one's number is the fault this resolution exists to stop."
        )
    plan = json.loads(plan_path.read_text())
    # The filename says which revision was resolved and the card says which
    # revision it is. They are two independent claims and this is the only
    # place both are in hand, so it is the only place they can be compared --
    # a card whose name and content disagree would otherwise run happily and
    # log whichever of the two was asked for.
    if int(plan.get("revision", -1)) != revision:
        raise Refused(
            f"{plan_path.name} is revision {revision} by its name and {plan.get('revision')!r} "
            "by its own field; one of the two is wrong and this run cannot say which plan it "
            "carried out until that is settled (5.5)"
        )

    if plan["status"] not in ("VALIDATED", "APPROVED"):
        raise Refused(
            f"plan status is {plan['status']}; the validator has not passed it, so there is "
            "nothing to gate yet (5.5)."
        )

    # A run id names one run and never two. On 2026-09-22 a second seat ran
    # the engine under an id this tree already held: cards.write replaced the
    # four files of the earlier run, and `git commit -- <paths>` carried the
    # replacement into HEAD as an ordinary edit. The gate judged a valid tree
    # and check 73 saw an id that existed, so nothing refused -- because
    # nothing here asked. An existing directory is a record (P1), and the
    # repair for wanting another run is another id, not a steadier hand. This
    # is opt-in like every operator guard: a directory made by hand walks past
    # it (2.1 rule 9), and the history-reading counterpart -- one id, one
    # content, ever -- belongs in contracts/ and was raised there.
    if (RUNS / run_id).exists():
        raise Refused(
            f"runs/{run_id} already exists and holds a run; a run id names one run and never "
            "two (P1). Choose an id this tree does not hold -- `ls runs/` first, and remember "
            "that four seats read the same listing, so a number that looks free to one looks "
            "free to all of them at once."
        )

    view, arm_cost = arm_view(plan, arm)
    smoke = None
    if budget == SMOKE:
        # after arm_view, so the estimates it scales are the arm's own
        view, smoke = smoke_view(view)
    approval, envelope = gate(view, budget, target)

    # The status flip is bookkeeping and belongs to the agent; the decision it
    # records belongs to a person. APPROVED has exactly two routes in (6.1): a
    # plan_approval for this (plan_id, revision), or a live scope_approval
    # covering it. There is no third -- the state machine's arrow into APPROVED
    # is labelled `person` -- and check 7 refuses the status with neither card
    # present.
    #
    # So a tier 0-1 run leaves the plan VALIDATED. This used to flip regardless
    # and the first run in this repository's history turned the tree red: the
    # gate runs the whole validator, so every other session's commit was
    # refused until the line was reverted. The reasoning it rested on was that
    # a deterministic gate passing is the equivalent decision, and it is not;
    # the tier split exists precisely because those two are different things.
    # The run's autonomy is already on the record where it belongs, in the run
    # log's `approval: {id: null, kind: null}`, which says it needed none -- a
    # different fact from a plan card claiming an approval nobody gave.
    if approval["id"] is not None and plan["status"] == "VALIDATED":
        plan["status"] = "APPROVED"
        cards.write(plan_path, plan)
    check_md_agrees(plan_path, plan)

    # THE ENGINE IS THE DEFAULT (018, the person's instruction 2026-09-22).
    # A run that names no backend gets HOOMD; the mock is still a first-class
    # backend and is still what runs when one is passed explicitly.
    #
    # What was dropped with it is 010's requirement to run the mock alongside
    # and compare. The analytic half stands -- the engine is checked against
    # D = k_B*T/(3*pi*eta*d) -- and the mock arm goes, because the sweep
    # showed the comparison had stopped paying: at ten seeds each, mock sits
    # at 0.99973 +- 0.241 % of the analytic and HOOMD at 0.99964 +- 0.210 %.
    # They agree to 0.01 per cent and neither is distinguishable from the
    # closed form. At three seeds the mock looked three times wider, and ten
    # seeds showed that was sampling noise -- a comparison that cannot
    # separate its arms is measuring how many seeds were run.
    #
    # `hoomd_backend` is imported at module scope and that is safe without
    # HOOMD installed: it imports `hoomd` inside the function that needs it,
    # so this module still loads on a machine that has no engine. 4.6.5 wants
    # the whole pipeline to run with no HOOMD, and it still does -- by being
    # handed a MockBackend, which is what the sweeps and the tests do.
    # THE ENGINE'S PRESENCE DECIDES (4.6.5 as amended by the person, 2026-09-22;
    # de438d0). 018 replaced one default with another, and on a machine without
    # HOOMD that default died at the import. The amendment's third option is
    # the one here: where the engine is present it runs; where it is not, the
    # mock runs AND the run says so, with an instruction naming the platform it
    # is on. The text changes no verdict -- a mock run is a valid run -- and it
    # is recorded as an event, not only printed, so a session reset cannot
    # lose the fact that the reduced path was taken (6.2 rule 2). The same
    # shape as `degraded` carrying the librarian's name.
    engine_missing: str | None = None
    if backend is None:
        # The configuration names the backend module (capabilities executed_by):
        # an active configuration runs on abp_backend, the rest on hoomd_backend.
        config_name = str((plan.get("system_configuration") or {}).get("config") or "")
        # A configuration with a harmonic trap and a flow has no term for
        # either in HoomdBackend, which integrates FREE diffusion. Falling
        # through to it would not fail: it would run the wrong physics under
        # this plan's id and finish green, because nothing in a free run
        # contradicts a trap plan's monitors. So the trap configuration is
        # dispatched by name like the active one: HOOMD where it is present,
        # its own NumPy mock where it is not.
        #
        # THE FALLBACK IS PER CONFIGURATION, and until now it was not. Every
        # EngineMissing fell back to mock_backend.MockBackend, which is free
        # diffusion -- so on a machine without HOOMD a trap plan would have
        # been integrated as free diffusion under the trap plan's id, the same
        # wrong-physics-finishing-green the dispatch above exists to prevent,
        # arriving by the other door. The active configuration still falls
        # back to MockBackend here: abp_backend has no mock of its own, and
        # choosing one for it is simulation-10's.
        #
        # simulation-10's choice: an ACTIVE configuration has NO fallback and
        # refuses. The free-diffusion mock would integrate a self-propelled,
        # repelling system as passive tracers and finish green under the
        # active plan's id. A mock for the free active particle could be
        # written (its answer is closed-form), but none can be written for the
        # interacting one, and a fallback that exists for one of two active
        # configurations invites the other to take it.
        fallback_class = None if config_name.startswith("abp") else mock_backend.MockBackend
        if config_name == "bd_overdamped_trapped_uniform_flow":
            from . import trap_backend, trap_hoomd_backend  # noqa: PLC0415
            engine_class = trap_hoomd_backend.TrapHoomdBackend
            fallback_class = trap_backend.TrapBackend
        elif config_name == "bd_overdamped_trapped":
            # The same trap builders with the fluid at rest. Without this branch
            # the undriven trap fell through to the free-diffusion engine and
            # would have run a trap plan with no trap under the plan's id --
            # the wrong-physics-finishing-green this dispatch exists to stop.
            from . import trap_rest_backend  # noqa: PLC0415
            engine_class = trap_rest_backend.TrapRestHoomdBackend
            fallback_class = trap_rest_backend.TrapRestBackend
        elif config_name == "bd_overdamped_gaussian_double_well_2d":
            # The double well has NO fallback. The NumPy integrator in
            # `double_well` is the reference the engine was validated against
            # (task 024), not a backend: running it under the plan's id would
            # record the reference as the engine. And a missing module refuses
            # rather than falling through to free diffusion, which would finish
            # green with no wells at all.
            try:
                from . import double_well_hoomd_backend  # noqa: PLC0415
            except ImportError as exc:
                raise Refused(f"{config_name} declares executed_by double_well_hoomd_backend and it "
                              f"cannot be imported here ({exc}); there is no substitute") from exc
            engine_class = double_well_hoomd_backend.DoubleWellHoomdBackend
            fallback_class = None
        else:
            # READ THE DECLARATION, which is what the comment above always
            # claimed and the code did not do. It dispatched on the name
            # starting with `abp`, and that is a proxy for `executed_by` which
            # was wrong for one configuration: both active ones declared
            # `hoomd_backend` while the prefix sent both to `abp_backend`.
            # Right for `abp_wca_2d`, whose interacting integrator is there,
            # and wrong for `abp_free`, whose integrator was written into
            # `hoomd_backend` because its declaration says so -- the run
            # refused for want of `wca_epsilon`, which its model has no term
            # for. The table was corrected the same day and now names
            # `abp_backend` for the interacting configuration and
            # `hoomd_backend` for the free one, so the declaration can be read
            # directly and the proxy retired.
            #
            # A module the table names and this file has no class for falls
            # through to the old rule rather than refusing: a configuration
            # declared by another seat must not be stopped by a table this
            # dispatch has not caught up with.
            declared = str(((_capability_row(config_name) or {}).get("executed_by") or {}).get("module") or "")
            engine_class = {
                "hoomd_backend": hoomd_backend.HoomdBackend,
                "abp_backend": abp_backend.AbpBackend,
            }.get(declared) or (
                abp_backend.AbpBackend if config_name.startswith("abp") else hoomd_backend.HoomdBackend
            )
        try:
            backend = engine_class(seed=seed)
        except hoomd_backend.EngineMissing:
            from . import engine_check                 # noqa: PLC0415
            if fallback_class is None:
                raise Refused(
                    f"{config_name} needs the engine and HOOMD is not importable here. There is no "
                    "substitute: the free-diffusion mock would run a different physical model and "
                    "record it as this plan's run. " + engine_check.instruction(ran="nothing")
                )
            backend = fallback_class(seed=seed)
            engine_missing = engine_check.instruction(ran=backend_name(backend))
            print(engine_missing, file=sys.stderr)
    params, provenance = derive_commands(view)
    if smoke:
        for entry in provenance:
            if entry["parameter"] == smoke["parameter"]:
                entry["from"] += f" x {smoke['from']}"
    monitors = compile_monitors(view)

    # One origin for the whole run, and every event an offset against it
    # (4.6.9, check 37). t0_wall places the run in history; it does not order
    # events, because wall clocks step. time_base says where an offset came
    # from, and on this side it is `software`: the engine has no trigger
    # counter, and a simulated time is not a clock reading.
    t0_wall = datetime.now(timezone.utc).isoformat()
    t0_mono = time.monotonic()
    events: list[dict] = []

    def record(event: str, **fields) -> None:
        events.append({
            "t_mono": round(time.monotonic() - t0_mono, 6),
            "time_base": "software",
            "event": event,
            **fields,
        })

    # O1 -- preflight. Nothing has been commanded yet.
    record("gate", tier=max_tier(plan), approval=approval, envelope=envelope,
           **({"compare_arm": arm, "arm_cost": arm_cost} if arm is not None else {}),
           **({"smoke": smoke} if smoke else {}))
    if engine_missing is not None:
        # The name of the backend that actually took over, not a constant:
        # with the fallback per configuration, `mock_backend.NAME` would record
        # the free-diffusion mock for a run the trap mock made.
        record("engine_missing", fell_back_to=backend_name(backend), instruction=engine_missing)
    pre = backend.preflight(params)
    record("preflight", report=pre)
    if pre.get("missing_parameters"):
        raise Refused(f"preflight is short of {pre['missing_parameters']}; stopping before dispatch")
    if not pre.get("save_interval_divides_step"):
        raise Refused(
            "the save interval is not a whole number of integration steps; a frame would land "
            "between steps and the lag axis would be wrong"
        )

    # O2 -- dispatch. One submission, and it returns before the run finishes.
    submission = backend.apply(params)
    record(
        "dispatch",
        action="integrate",
        **{"from": "actions[integrate]"},
        handle=submission.get("handle"),
        state=submission.get("state"),
        # `value_si` and `unit_in_plan`, the two names `provenance` uses, and
        # not `value`/`unit`. Pairing a converted value with the plan's unit
        # made every dispatched parameter read as a number in a unit it is not
        # in: the box went into the log as `9.999999999999999e-05 um` for a
        # 100 um box, and the bead as `2e-06 um` for a 2 um bead. Both are the
        # right value and the wrong label, which is the one shape P2 exists to
        # refuse -- and this is a run log rather than a card, so no check looks
        # at it. The plan's own unit is kept because what the parameter was
        # written as is part of what was dispatched.
        params={
            entry["parameter"]: {
                "value_si": entry["value_si"],
                "unit_in_plan": entry["unit_in_plan"],
                "grade": entry["grade"],
                "from": entry["from"],
            }
            for entry in provenance
        },
    )
    record("monitors_compiled", monitors=[m["id"] for m in monitors],
           **{"from": "stop_criteria"})

    # O3 -- watch. The monitors are evaluated against a running job rather
    # than between synchronous chunks, which is the whole reason apply() does
    # not block: a stop criterion that can only be checked after the run has
    # returned is not a stop criterion.
    stopped_by, stopped_early = None, False
    polls, last_progress = 0, -1
    # The polling guard is against a backend that never reaches a terminal
    # state, not a limit on the run: the run's limit is the envelope's wall
    # clock, re-read here. At 600 s flat it would have aborted a 40-minute arm
    # the envelope allows two hours for, and reported the abort as the
    # backend's -- the guard judging what the ceiling owns.
    ceiling_s = POLL_BUDGET_S
    try:
        limits = next(t for t in (read_envelope() or {}).get("targets", []) if t["target"] == target)["limits"]
        wall = (limits["smoke_budget"] if budget == SMOKE else limits)["wall_clock_max"]
        ceiling_s = max(POLL_BUDGET_S, si({**wall, "name": "wall_clock_max"}))
    except (StopIteration, KeyError, TypeError, Refused):
        pass
    deadline = time.monotonic() + ceiling_s
    while True:
        state = backend.read()
        fired = evaluate(monitors, state)
        if fired:
            # A fault beats a completion when both fire on the same poll: a run
            # that broke on its last step did not finish.
            stopped_by = next((f for f in fired if f["outcome"] == "fault"), fired[0])
            stopped_early = stopped_by["outcome"] == "fault"
            if stopped_early:
                record("abort", monitor=stopped_by, state=state,
                       reason=backend.abort(f"stop criterion {stopped_by['id']} fired")["reason"])
            else:
                record("complete", monitor=stopped_by, state=state,
                       note="the criterion that fired declares on_met complete")
                backend.abort("planned end reached")
            break
        if state.get("state") in mock_backend.TERMINAL:
            record(
                "failed" if state.get("state") == mock_backend.FAILED else "complete",
                monitor=None, state=state,
                note=f"the backend reports {state.get('state')} and no stop criterion fired",
            )
            break
        if time.monotonic() > deadline:
            record("abort", monitor=None, state=state,
                   reason=backend.abort(
                       f"no terminal state within {ceiling_s:g} s of polling, the envelope's wall clock for this budget"
                   )["reason"])
            stopped_early = True
            break
        frames = state.get("frames_saved", 0)
        if frames - last_progress >= PROGRESS_EVERY:
            record("progress", state=state)
            last_progress = frames
        polls += 1
        time.sleep(POLL_INTERVAL_S)

    # O4 -- record. The run directory is only created once a run happened.
    out = RUNS / run_id
    out.mkdir(parents=True, exist_ok=True)
    cards.write(out / "config.json", {
        "run_id": run_id,
        "qid": qid,
        "plan_id": plan["id"],
        # The RESOLVED revision, not the card's own field. They are equal --
        # run() refuses the pair when they are not -- and which one is written
        # is still the difference between recording what was opened and
        # recording what the thing opened says about itself.
        "plan_revision": revision,
        "plan_hash": plan_hash(plan),
        "approval": approval,
        "envelope_check": envelope,
        "backend": backend_name(backend),
        "seed": backend_seed(backend, seed),
        "parameters_si": params,
        "provenance": provenance,
        **({"compare_arm": arm} if arm is not None else {}),
    })
    # A backend whose observable is not a diffusivity says what it read
    # through `observables(params)`, and the diffusivity block below is
    # skipped rather than run against a window the plan does not carry. The
    # other route was a backend growing `fit_diffusivity` for a quantity that
    # is not one, which would put a false label on the run record. Absent,
    # everything below is exactly what it was.
    own_observables = getattr(backend, "observables", None)
    window = None if own_observables else params["max_lag_time"]
    fit = None if own_observables else backend.fit_diffusivity(window)
    # An honest error bar beside the fit's own, and not instead of it (006,
    # d7b47e3). The weighted fit treats a hundred MSD points as independent
    # observations when every lag comes from the same trajectories, and
    # measured over 32 seeds of this configuration its quoted error is about
    # 36 times too small. The backend estimates the same quantity from blocks
    # of tracers, which are independent by construction here.
    #
    # It is recorded because a criterion is evaluated against it. `statistics_met`
    # compares a relative standard error against a target, and a result card
    # carries that comparison permanently -- so the run record has to hold the
    # number the card should use, or the card reaches for the only one on disk.
    # Both are kept: the fit's own stays inside `fit` with its own note, and
    # nothing is silently rescaled.
    uncertainty = None if own_observables else backend.block_uncertainty(window)
    # Whether the fit agrees with itself across the window. Revision 2's
    # `window_insensitive` compares it against the decade target, and nothing
    # recorded it -- so the criterion was declared and unevaluable. It is
    # separate from the error bars on purpose: both of those describe scatter
    # at one window, and this one asks whether the window itself was right.
    halves = None if own_observables else backend.window_halves(window)
    final = backend.read()
    # The positions, written beside the summary (013). Steps per frame are
    # derived from each frame's simulated time and the plan's dt -- an
    # integer count read back from a product, not a running sum (see the
    # completion-criterion incident in this agent's CLAUDE.md).
    dt = float(params["integration_timestep"])
    steps = [int(round(t / dt)) for t in getattr(backend, "frame_times", [])]
    # ONE TEXT FILE (021, the person's request of 2026-09-23): analysis reads
    # it instead of re-running, and the person deletes it by hand. It replaces
    # the GSD rather than sitting beside it.
    build = (pre.get("engine_build") or {})
    # The backend's declared dimensionality where it has one; otherwise the
    # width of the frames it actually holds -- what was simulated, not a
    # default. A 2D backend that padded z would otherwise write a column of
    # zeros as though it were a coordinate.
    frames_held = list(getattr(backend, "frames", []))
    dims = int(getattr(backend, "DIMENSIONS", None) or (frames_held[0].shape[1] if frames_held else 3))
    write_started = time.perf_counter()
    written = trajectory.write_text(
        out, list(getattr(backend, "frames", [])), steps, float(params["box_length"]),
        dimensions=dims, run_id=run_id, plan_hash=plan_hash(plan),
        engine=str(build.get("engine") or backend_name(backend)), engine_version=str(build.get("version") or "unrecorded"),
        seed=backend_seed(backend, seed), save_interval_steps=int(pre.get("steps_per_frame") or 1),
        orientations=list(getattr(backend, "orientations", []) or []) or None,
        reduced_units=pre.get("reduced_units"))
    write_after_s = time.perf_counter() - write_started
    # Timing that separates the two cost terms (task 023), read from the
    # backend where it reports it and None where it does not -- None is "not
    # reported", never zero. The trajectory write after the loop is timed
    # here, since it happens here; a streaming backend reports its in-loop
    # write itself. Peak resident memory is recorded and not limited: whether
    # memory gets a ceiling is the person's decision, and this is what lets
    # them make it.
    import resource
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = rss if sys.platform == "darwin" else rss * 1024
    n_part = int(params.get("n_particles") or getattr(backend, "N_PARTICLES", 0) or 1)
    fs = final.get("frames_saved")
    integ, readout = final.get("integration_wall_s"), final.get("frame_readout_wall_s")
    record("cost_measured",
           steps_taken=final.get("steps_taken"), frames_saved=fs, n_particles=n_part,
           integration_wall_s=integ, frame_readout_wall_s=readout,
           frame_write_wall_s=final.get("frame_write_wall_s"),
           trajectory_write_after_run_s=write_after_s,
           particle_step_rate=(final["steps_taken"] * n_part / integ) if integ and final.get("steps_taken") else None,
           particle_frame_cost=(readout / (fs * n_part)) if readout and fs else None,
           peak_rss_bytes=rss_bytes,
           note="peak_rss is the operator process's high-water mark, which includes the backend running in it. "
                "particle_frame_cost covers readout only; a streaming backend's in-loop write is frame_write_wall_s")
    cards.write(out / "trajectory_meta.json", {
        "artifact": "trajectory_meta",
        "schema_version": 1,
        "run_id": run_id,
        # What is on disk beside this file and what a frame in it is, or why
        # nothing is. This summary is the part that outlives the data: a
        # deletion later (run_log `deletion` event, check 77) removes the
        # file and leaves this block saying what it was.
        "trajectory": written,
        # Storing the trajectory moves the cost: 10001 frames x 1000 x 3 x 4
        # bytes is ~0.12 GB per revision-3 run against a plan storage_estimate
        # of 0.02 GB. Recorded here and not corrected here -- that estimate is
        # a_cost_reference's, and replacing it is revision 4's work (013, 020).
        "frames_saved": final.get("frames_saved"),
        "simulated_time": final.get("simulated_time"),
        "steps_taken": final.get("steps_taken"),
        # The metric the divergence criterion compares against, at the end of
        # the run. Without it the summary cannot answer a stop criterion the
        # plan declares, and a reader has to reconstruct it out of the last
        # event in the log -- which exists, and is the event stream rather than
        # the summary of what the run reached.
        "max_single_step_displacement": final.get("max_single_step_displacement"),
        "stopped_by": stopped_by["id"] if stopped_by else None,
        # Read off the criterion's own on_met rather than inferred from when it
        # fired. A result card's outcome rests on this, so it has to be a fact
        # the plan stated and not one the operator worked out (5492e93).
        "stop_outcome": stopped_by["outcome"] if stopped_by else "complete",
        "stopped_early": stopped_early,
        "completed_planned_duration": not stopped_early,
    })
    if own_observables:
        cards.write(out / "observables.json", {
            "run_id": run_id,
            "observable": plan["observable"]["name"],
            **own_observables(params),
        })
    else:
        _write_diffusivity_observables(out, run_id, plan, window, fit, uncertainty, halves, backend)
    cards.write(out / "log.json", {
        "artifact": "run_log",
        "schema_version": "0.1",
        "run_id": run_id,
        "plan_id": plan["id"],
        # What was OPENED, beside what the card CLAIMS. 009 made the
        # resolution correct and 4d01f29 added this field to record it; until
        # now nothing wrote it, so 33 run logs said which revision the card
        # believed itself to be and none said which file that came from. The
        # two agree exactly while the resolution is right, which is why the
        # day they stop agreeing is the day nobody would notice.
        "plan_path": str(plan_path.relative_to(cards.REPO)),
        # Likewise, and here it is the point of the card: a later reader has to
        # be able to tell "ran revision 1 on purpose" from "ran revision 1
        # because the code could not see revision 2". Taken from the plan's own
        # field, the log says the same thing in both cases -- every plan agrees
        # with itself about which revision it is, whichever file was opened.
        # Taken from the resolution, it says which file this run actually read.
        #
        # THE LOG CANNOT NAME THE FILE OUTRIGHT. run_log.schema.json is
        # additionalProperties: false and has no field for a path, so
        # (plan_id, revision) is the whole vocabulary available for it. That is
        # why run() cross-checks the filename against the card's field instead:
        # the pair is only as good as the guarantee that the name and the
        # content agree, and nothing else was making that guarantee. A field
        # naming the resolved path would say it directly and is the manager's.
        "revision": revision,
        "approval": approval,
        # The field is named in run_log.schema.json and the value now comes out of
        # envelope/budget.json, so the name says `safety` about a file that is
        # deliberately not one. Renaming it is the manager's and would strand the
        # two run logs already on disk that carry it; raised rather than changed.
        "safety_policy_version": (read_envelope() or {}).get("policy_version"),
        "stop_criteria": [m["id"] for m in monitors],
        "t0_wall": t0_wall,
        "t0_mono": t0_mono,
        "time_base_note": (
            "Every offset is software: this side has no trigger counter and no device clock. "
            "Simulated time is a coordinate of the model, not a clock reading, so it is recorded "
            "in trajectory_meta.json rather than as this log's time base (4.6.9)."
        ),
        "backend": backend_name(backend),
        "events": events,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    })
    return out



def _write_diffusivity_observables(out, run_id, plan, window, fit, uncertainty, halves, backend):
    """The `tracer_diffusivity`-shaped record, moved out of run() unchanged."""
    cards.write(out / "observables.json", {
        "run_id": run_id,
        "observable": plan["observable"]["name"],
        "window_parameter": "max_lag_time",
        "window_si": window,
        "fit": fit,
        "uncertainty": uncertainty,
        "window_sensitivity": halves,
        "msd_curve": backend.mean_squared_displacement(window),
        **(backend.active_observables(window) if hasattr(backend, "active_observables") else {}),
    })

if __name__ == "__main__":
    qid = sys.argv[1] if len(sys.argv) > 1 else "sim-20260917-001"
    run_id = sys.argv[2] if len(sys.argv) > 2 else "run-20260917-001"
    arm = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    budget = sys.argv[4] if len(sys.argv) > 4 else SMOKE
    seed = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    try:
        print(run(qid, run_id, budget=budget, seed=seed, arm=arm).relative_to(cards.REPO))
    except Refused as exc:
        print(f"REFUSED: {exc}")
        raise SystemExit(3)
