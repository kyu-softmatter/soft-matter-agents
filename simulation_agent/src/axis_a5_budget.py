"""A5 -- resource budget (plan.md 4.5.3).

**This axis abstains, and the reason is structural rather than local.** Every
inequality A5 owns has the same shape -- estimated cost against an allowance --
and the two halves have different owners: **the cost model belongs to this
agent and the ceiling belongs to a person.** The ceilings live in
`envelope/safety.json` (2.1 rule 7, 6.1), which does not exist yet. Its shape
is no longer open -- this agent's standing orders specify a list of execution
targets, each carrying a wall-clock ceiling, a storage ceiling and a separate
smoke budget -- but a specified shape is not a written file, and an unwritten
ceiling is not a satisfied one.

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

AXIS = "a5"

ENVELOPE = cards.AGENT / "envelope" / "safety.json"


def build(qid: str, config: str, created_at: str) -> dict:
    goal = cards.load_goal(qid)
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
            "statement": "Cost is estimated at a reference step of ten milliseconds over a window of a few seconds, with one interaction-free force evaluation per particle per step. Nothing has been benchmarked on this machine, so both figures are order-of-magnitude estimates of an unrun job.",
            "numbers": ["reference_timestep", "storage_estimate", "wall_clock_estimate"],
            "falsifier": "a smoke run's own log replaces both estimates with measured values",
        }
    )

    card = cards.head(
        "axis",
        f"axis-{qid}-{config}-{AXIS}",
        qid,
        created_at,
        caller_id=f"{qid}:{config}:{AXIS}",
        config=config,
        axis=AXIS,
        kb_version="kbv-9bc3910f1886",
        method="llm_estimate",
        verdict="abstain",
        abstain_reason=(
            "No resource allowance exists to compare the estimated cost against. "
            f"{ENVELOPE.relative_to(cards.REPO)} is absent, so the limit side of every budget "
            "inequality is missing. Its shape is specified -- one row per execution target, "
            "with a wall-clock ceiling, a storage ceiling and a separate smoke budget -- but "
            "only a person writes the file (2.1 rule 7). Supplying a ceiling here would make "
            "the cost model its own limit. The cost side is recorded in numbers[] so that the "
            "abstention does not discard the estimate too."
        ),
    )
    card.update(cards.tail(numbers, assumptions=assumptions, degraded=["librarian_agent"]))
    card["note"] = (
        "The estimates say this job is trivially small, which is exactly why abstaining rather "
        "than passing matters: a cheap run is not the same fact as a run inside a known budget, "
        "and only the second one is what the envelope check is asking about."
    )
    return card


if __name__ == "__main__":
    qid = sys.argv[1] if len(sys.argv) > 1 else "sim-20260917-001"
    config = sys.argv[2] if len(sys.argv) > 2 else "bd_overdamped"
    created_at = sys.argv[3] if len(sys.argv) > 3 else "2026-09-17T12:10:00Z"
    print(cards.write(cards.question_dir(qid) / f"axis_{config}_{AXIS}.json",
                      build(qid, config, created_at)).relative_to(cards.REPO))
