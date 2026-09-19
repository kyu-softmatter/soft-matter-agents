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
them (4.6), so the ceilings come off `envelope/safety.json` at run time rather
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
from . import mock_backend

APPROVALS = cards.AGENT / "approvals"
RUNS = cards.AGENT / "runs"
ENVELOPE = cards.AGENT / "envelope" / "safety.json"

# Which budget a run is measured against. A smoke run that may spend the full
# allowance tells you nothing before the run it is supposed to precede, so the
# two are separate ceilings rather than one.
SMOKE, FULL = "smoke", "full"

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

    The file says what it is, and that is checked before it is believed.
    Reading a policy file without confirming it is one would let any JSON that
    happens to have a `targets` key act as a ceiling, and a safety decision
    reads fail-closed or it is not one (P0).
    """
    if not ENVELOPE.exists():
        return None
    envelope = json.loads(ENVELOPE.read_text())
    if envelope.get("artifact") != "envelope_safety":
        raise Refused(
            f"{ENVELOPE.relative_to(cards.REPO)} does not declare artifact envelope_safety "
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
                f"{ENVELOPE.relative_to(cards.REPO)} does not exist. A person writes it "
                "(2.1 rule 7, 10.3 rule 4); a ceiling this agent derived from what the job "
                "needs would not be a ceiling."
            ),
        }
    targets = {row["target"]: row for row in envelope.get("targets", [])}
    if target not in targets:
        return {
            "status": "unavailable",
            "target": target,
            "reason": f"the envelope declares {sorted(targets)} and not {target!r}",
        }
    ceilings = targets[target]
    limits = ceilings["smoke_budget"] if budget == SMOKE else ceilings
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
    known = {(round(float(n["value"]), 12), n["unit"]) for n in plan["numbers"]}
    import re

    units = sorted((u for u in json.loads((cards.CONTRACTS / "units.json").read_text())["units"] if u != "1"), key=len, reverse=True)
    pattern = re.compile(
        r"(?<![A-Za-z0-9_.-])([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)[ \t]*("
        + "|".join(re.escape(u) for u in units)
        + r")(?![A-Za-z0-9_])"
    )
    for m in pattern.finditer(md.read_text()):
        value, unit = float(m.group(1)), m.group(2)
        if not any(u == unit and abs(v - value) <= abs(v) * 1e-9 for v, u in known):
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


def run(qid: str, run_id: str, backend=None, seed: int = 1,
        budget: str = SMOKE, target: str = "local") -> Path:
    """O1 preflight, O2 dispatch, O3 monitor, O4 record.

    Raises Refused before creating anything if the gate is shut.
    """
    plan_path = cards.question_dir(qid) / f"plan_simulation_{qid}.json"
    plan = json.loads(plan_path.read_text())

    if plan["status"] not in ("VALIDATED", "APPROVED"):
        raise Refused(
            f"plan status is {plan['status']}; the validator has not passed it, so there is "
            "nothing to gate yet (5.5)."
        )

    approval, envelope = gate(plan, budget, target)

    # The status flip is bookkeeping and belongs to the agent; the decision it
    # records belongs elsewhere. For tier 2 that decision is a person's approval
    # card in approvals/ -- the one folder they write and no seat may (7.1 rule
    # 5). For tier 0-1 it is the gate above having passed deterministically.
    if plan["status"] == "VALIDATED":
        plan["status"] = "APPROVED"
        cards.write(plan_path, plan)
    check_md_agrees(plan_path, plan)

    backend = backend or mock_backend.MockBackend(seed=seed)
    params, provenance = derive_commands(plan)
    monitors = compile_monitors(plan)

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
    record("gate", tier=max_tier(plan), approval=approval, envelope=envelope)
    pre = backend.preflight(params)
    record("preflight", report=pre)
    if pre.get("missing_parameters"):
        raise Refused(f"preflight is short of {pre['missing_parameters']}; stopping before dispatch")
    if not pre.get("save_interval_divides_step"):
        raise Refused(
            "the save interval is not a whole number of integration steps; a frame would land "
            "between steps and the lag axis would be wrong"
        )

    # O2 -- dispatch, in chunks of one saved frame.
    steps_per_frame = int(pre["steps_per_frame"])
    frames = int(pre["frames_expected"])
    record(
        "dispatch",
        action="integrate",
        **{"from": "actions[integrate]"},
        params={
            entry["parameter"]: {
                "value": entry["value_si"],
                "unit": entry["unit_in_plan"],
                "grade": entry["grade"],
                "from": entry["from"],
            }
            for entry in provenance
        },
    )
    record("monitors_compiled", monitors=[m["id"] for m in monitors],
           **{"from": "stop_criteria"})

    stopped_by, stopped_early = None, False
    for frame in range(frames):
        backend.apply({**params, "steps": steps_per_frame})
        state = backend.read()
        fired = evaluate(monitors, state)
        if fired:
            # O3 -- the stop is taken here, deterministically, before anything
            # interprets it. Writing up what happened is a later, human-facing
            # job and does not gate the stop (4.6.1).
            #
            # A fault is preferred over a completion when both fire in the same
            # chunk: a run that broke on its last step did not finish.
            stopped_by = next((f for f in fired if f["outcome"] == "fault"), fired[0])
            stopped_early = stopped_by["outcome"] == "fault"
            if stopped_early:
                record("abort", monitor=stopped_by, state=state,
                       reason=backend.abort(f"stop criterion {stopped_by['id']} fired")["reason"])
            else:
                record("complete", monitor=stopped_by, state=state,
                       note="the criterion that fired declares on_met complete")
            break
        if frame % 20 == 0 or frame == frames - 1:
            record("progress", frame=frame, state=state)
    else:
        record("complete", monitor=None, state=backend.read(),
               note="every planned chunk ran and no stop criterion fired")

    # O4 -- record. The run directory is only created once a run happened.
    out = RUNS / run_id
    out.mkdir(parents=True, exist_ok=True)
    cards.write(out / "config.json", {
        "run_id": run_id,
        "qid": qid,
        "plan_id": plan["id"],
        "plan_revision": plan["revision"],
        "plan_hash": plan_hash(plan),
        "approval": approval,
        "envelope_check": envelope,
        "backend": getattr(backend, "NAME", mock_backend.NAME),
        "seed": getattr(backend, "seed", seed),
        "parameters_si": params,
        "provenance": provenance,
    })
    window = params["max_lag_time"]
    fit = backend.fit_diffusivity(window)
    cards.write(out / "trajectory_meta.json", {
        "run_id": run_id,
        "frames_saved": backend.read().get("frames_saved"),
        "simulated_time": backend.read().get("simulated_time"),
        "steps_taken": backend.read().get("steps_taken"),
        "stopped_by": stopped_by["id"] if stopped_by else None,
        # Read off the criterion's own on_met rather than inferred from when it
        # fired. A result card's outcome rests on this, so it has to be a fact
        # the plan stated and not one the operator worked out (5492e93).
        "stop_outcome": stopped_by["outcome"] if stopped_by else "complete",
        "stopped_early": stopped_early,
        "completed_planned_duration": not stopped_early,
    })
    cards.write(out / "observables.json", {
        "run_id": run_id,
        "observable": plan["observable"]["name"],
        "window_parameter": "max_lag_time",
        "window_si": window,
        "fit": fit,
        "msd_curve": backend.mean_squared_displacement(window),
    })
    cards.write(out / "log.json", {
        "artifact": "run_log",
        "schema_version": "0.1",
        "run_id": run_id,
        "plan_id": plan["id"],
        "revision": plan["revision"],
        "approval": approval,
        "safety_policy_version": (read_envelope() or {}).get("policy_version"),
        "stop_criteria": [m["id"] for m in monitors],
        "t0_wall": t0_wall,
        "t0_mono": t0_mono,
        "time_base_note": (
            "Every offset is software: this side has no trigger counter and no device clock. "
            "Simulated time is a coordinate of the model, not a clock reading, so it is recorded "
            "in trajectory_meta.json rather than as this log's time base (4.6.9)."
        ),
        "backend": getattr(backend, "NAME", mock_backend.NAME),
        "events": events,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    })
    return out


if __name__ == "__main__":
    qid = sys.argv[1] if len(sys.argv) > 1 else "sim-20260917-001"
    run_id = sys.argv[2] if len(sys.argv) > 2 else "run-20260917-001"
    try:
        print(run(qid, run_id).relative_to(cards.REPO))
    except Refused as exc:
        print(f"REFUSED: {exc}")
        raise SystemExit(3)
