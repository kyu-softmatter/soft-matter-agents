"""A5 -- resource budget (plan.md 4.5.3).

**This axis abstains, and the reason is structural rather than local.** Every
inequality A5 owns has the same shape -- estimated cost against an allowance --
and the two halves have different owners: **the cost model belongs to this
agent and the ceiling belongs to a person.** The ceilings live in
`envelope/budget.json`, renamed from `safety.json` on 2026-09-20 because the
grade of harm differs -- get the laser ceiling wrong and you lose an eye, get
the wall clock wrong and you lose a night.

**Why it abstains is read off the file rather than asserted.** This docstring
said "which does not exist yet" and the `abstain_reason` below said the same,
unconditionally, for a day after the person wrote the file. A sentence about a
file that does not consult the file cannot notice when it stops being true,
and no check compares prose to disk. So the reason is derived, and the two
cases it distinguishes are different facts: with no file there is no allowance
to compare against, and with a file there is one this axis does not yet turn
into an interval. Only the second is this agent's to close.

P5 says a judgement without a basis abstains rather than guessing. An axis
that supplied its own allowance would be writing policy, and "does not submit
an over-budget job on its own" (4.2) would become unenforceable: a ceiling
derived from what the job needs is not a ceiling.

The cost side is still recorded. An abstention that carried no numbers would
lose the estimate as well as the verdict, and S4 needs the estimate to rank
configurations even when no limit is known.

The estimates rest on a reference step A5 chose for itself, not on A1's
bound: 4.5.3 rule (b) keeps an axis from reading a sibling's output. S4
rescales them once the step is picked.
"""

from __future__ import annotations

import sys

from . import cards
from . import axes_abp

AXIS = "a5"

ENVELOPE = cards.AGENT / "envelope" / "budget.json"


def abstain_reason() -> str:
    """Why this axis abstains, stated from the file rather than about it.

    Both branches abstain and they abstain for different reasons, so the two
    sentences are not interchangeable. Emitting an interval once a ceiling
    exists is a behaviour change with a card of its own; what this function
    fixes is only that the card stops claiming something false about disk.
    """
    where = ENVELOPE.relative_to(cards.REPO)
    if not ENVELOPE.exists():
        return (
            "No resource allowance exists to compare the estimated cost against. "
            f"{where} is absent, so the limit side of every budget inequality is missing. "
            "Its shape is specified -- one row per execution target, with a wall-clock "
            "ceiling, a storage ceiling and a separate smoke budget -- but a specified "
            "shape is not a written file. Supplying a ceiling here would make the cost "
            "model its own limit. The cost side is recorded in numbers[] so that the "
            "abstention does not discard the estimate too."
        )
    return (
        f"An allowance exists -- {where} declares one -- and this axis does not yet turn "
        "it into an allowed interval over the settable parameters. So the abstention is "
        "this agent's unfinished work and not a missing ceiling, which are different "
        "facts and were reported as the same one until 2026-09-20. The operator compares "
        "the cost against these ceilings at run time either way (4.6 O1), so nothing runs "
        "over budget on the strength of this abstention; what is missing is the constraint "
        "at plan time. The cost side is recorded in numbers[] as before."
    )


def build(qid: str, config: str, created_at: str, caller_id: str, kb_version: str,
          kb_result: dict | None = None, revision: int = 1) -> dict:
    if axes_abp.is_active(config):
        # The active configurations are a different physics; every number below is
        # bd_overdamped's. Dispatched rather than branched so this file regenerates
        # its own cards byte for byte (axes_abp).
        return axes_abp.build(AXIS, qid, config, created_at, caller_id, kb_version, kb_result, revision)
    """The caller_id is injected by the fan-out executor, never chosen here.

    4.3.1 rule 3: a sub-agent that picks its own id can impersonate a
    sibling's. The check below refuses an id that does not name this axis --
    that catches an executor mistake, and is not this module choosing one.
    """
    if not caller_id.endswith(f":{AXIS}"):
        raise ValueError(f"{caller_id!r} was issued to another axis; this module is {AXIS}")
    # A configuration with its own module answers for itself (src/configs.py).
    # bd_overdamped has none and falls through to the body below, unchanged.
    from . import configs as _configs
    _card = _configs.dispatch(AXIS, qid, config, created_at, caller_id, kb_version, kb_result, revision)
    if _card is not None:
        return _card

    goal = cards.load_goal(qid, revision)
    numbers, assumptions = cards.carry(goal, ["n_particles", "max_lag_time"])

    numbers.append(
        cards.num(
            "reference_timestep",
            0.01,
            "s",
            "assumed:a_cost_reference",
            precision="order_of_magnitude",
            note="A5's own reference step for costing, chosen rather than read from A1 (4.5.3 rule b)",
        )
    )
    numbers.append(
        cards.num(
            "storage_estimate",
            0.02,
            "GB",
            "assumed:a_cost_reference",
            precision="order_of_magnitude",
            note="of order a thousand frames of a thousand tracers at three double coordinates each, a few tens of megabytes",
        )
    )
    numbers.append(
        cards.num(
            "wall_clock_estimate",
            0.0001,
            "core_h",
            "assumed:a_cost_reference",
            precision="order_of_magnitude",
            note="of order ten million particle-steps with no pair interactions; the run is still far too small for this axis to bind",
        )
    )
    assumptions.append(
        {
            "rationale_id": "a_cost_reference",
            "statement": "Cost is estimated at a reference step of ten milliseconds over a window of a few seconds, with one interaction-free force evaluation per particle per step. Two mock runs have happened on this machine and neither benchmarks this job: 93 per cent of their wall clock fell outside the monitored window, in process start and a poll interval the mock outruns, and the mock writes no trajectory at all, so the size of its run directory measures four cards. Both figures stay order-of-magnitude estimates of an unrun job.",
            "numbers": ["reference_timestep", "storage_estimate", "wall_clock_estimate"],
            "falsifier": "a run that WRITES THE TRAJECTORY THIS PLAN DECLARES, on the backend this configuration declares (hoomd_backend), replaces both estimates with values measured off that run's own artefacts. The condition names a STATE checkable against the run directory -- a trajectory file of the declared frames and tracers is present -- and not a backend or an event, because each earlier form was satisfied in letter by a run that measured something else: 'a smoke run\'s own log' was met by two mock runs that measured the harness, and 'a run on hoomd_backend' was met on 2026-09-22 by engine runs that wrote no trajectory at all (every run directory holds config, log, trajectory_meta and observables and no frames), whose 36 KB against a 0.02 GB estimate is a run measuring a different thing and not an estimate being wrong. The backend is necessary and not sufficient. It does not fire today because no run writes a trajectory (013 is open); when one does, storage_estimate and wall_clock_estimate become measured and leave E5 (020).",
        }
    )

    card = cards.head(
        "axis",
        f"axis-{qid}-{config}-{AXIS}" + ("" if revision == 1 else f"-r{revision}"),
        qid,
        created_at,
        revision=revision,
        caller_id=caller_id,
        config=config,
        axis=AXIS,
        kb_version=kb_version,
        method="llm_estimate",
        verdict="abstain",
        abstain_reason=abstain_reason(),
    )
    card.update(cards.tail(numbers, assumptions=assumptions, **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
    card["note"] = (
        "The estimates say this job is trivially small, which is exactly why abstaining rather "
        "than passing matters: a cheap run is not the same fact as a run inside a known budget, "
        "and only the second one is what the envelope check is asking about."
    )
    return card


if __name__ == "__main__":
    # Runnable alone, but only with an id handed in: whoever runs it is acting
    # as the fan-out executor and says so by supplying one (4.3.1 rule 3).
    # `python3 -m src.fanout` is the normal path and issues all six.
    if len(sys.argv) < 6:
        raise SystemExit(
            "usage: python3 -m src.axis_a5_budget <qid> <config> <created_at> "
            "<caller_id> <kb_version>"
            "\n"
            "The caller_id is issued by the fan-out executor and cannot be chosen "
            "here (4.3.1 rule 3). Use `python3 -m src.fanout` unless you are "
            "standing in for it."
        )
    qid, config, created_at, caller_id, kb_version = sys.argv[1:6]
    print(cards.write(cards.question_dir(qid) / f"axis_{config}_{AXIS}.json",
                      build(qid, config, created_at, caller_id, kb_version, None)).relative_to(cards.REPO))
