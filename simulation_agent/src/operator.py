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
from . import mock_backend

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
    deadline = time.monotonic() + POLL_BUDGET_S
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
                       f"no terminal state within {POLL_BUDGET_S} s of polling"
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
    uncertainty = backend.block_uncertainty(window)
    final = backend.read()
    cards.write(out / "trajectory_meta.json", {
        "run_id": run_id,
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
    cards.write(out / "observables.json", {
        "run_id": run_id,
        "observable": plan["observable"]["name"],
        "window_parameter": "max_lag_time",
        "window_si": window,
        "fit": fit,
        "uncertainty": uncertainty,
        "msd_curve": backend.mean_squared_displacement(window),
    })
    cards.write(out / "log.json", {
        "artifact": "run_log",
        "schema_version": "0.1",
        "run_id": run_id,
        "plan_id": plan["id"],
        "revision": plan["revision"],
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
