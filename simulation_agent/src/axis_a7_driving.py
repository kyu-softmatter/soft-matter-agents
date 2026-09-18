"""A7 -- driving protocol (plan.md 4.5.3).

**A7 abstains here, and it is still a card.** `bd_overdamped` drives nothing:
the configuration is declared undriven in `contracts/capabilities/simulation.json`
and the goal asks for no driving parameter. An equilibrium run leaves an a7
card saying so rather than leaving the axis out, because a pruned axis leaves
nothing behind to record that the constraint was dropped (P1, 4.5.3).

**The number is A7 on both sides on purpose.** There is no A6 in this agent --
spatial resolution is an imaging axis -- and the hole in the numbering is what
lets the bridge put a microscope a7 card and an engine a7 card side by side
(M4). Renumbering the driving axis to fill the gap would make a6 mean
resolution on one side and driving on the other.

When a question does drive the system, this axis owns the inequalities that
the driving amount appears in: quasi-staticity (ramp duration against the
relaxation time), the strain needed to reach steady state, and whether the
driving keeps the overdamped assumption valid. A1 takes a shear rate as an
*input* and bounds the step from it; it does not bound the rate itself.
"""

from __future__ import annotations

import json
import sys

from . import cards

AXIS = "a7"

# The parameter names that would make this a driven question. Checked against
# the goal deterministically, so the abstention is read off the card rather
# than asserted by whoever ran the axis.
DRIVING_PARAMETERS = (
    "shear_rate",
    "strain_amplitude",
    "strain_rate",
    "external_force",
    "force_ramp_rate",
    "ramp_duration",
    "driving_frequency",
    "flow_velocity",
)


def driving_requested(goal: dict) -> list[str]:
    named = {n["name"] for n in goal.get("numbers", [])}
    return sorted(named.intersection(DRIVING_PARAMETERS))


def build(qid: str, config: str, created_at: str) -> dict:
    goal = cards.load_goal(qid)
    requested = driving_requested(goal)
    capabilities = json.loads(
        (cards.CONTRACTS / "capabilities" / "simulation.json").read_text()
    )
    declared = next(
        (c for c in capabilities["configurations"] if c["config"] == config), None
    )
    if declared is None:
        raise KeyError(f"{config} is not a declared configuration; A7 has nothing to read")

    if requested:
        raise NotImplementedError(
            f"the goal requests driving parameters {requested}; the driven branch of A7 "
            "is not built yet and must not be silently abstained through"
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
        method="deterministic",
        verdict="abstain",
        abstain_reason=(
            "No driving was requested. The goal names no driving parameter, and "
            f"{config} is declared undriven, so there is no driving amount for this axis to "
            "bound. Abstaining is not the same as being absent: this card is the record that "
            "the axis was asked and had nothing to constrain (P1)."
        ),
    )
    card.update(cards.tail([], degraded=["librarian_agent"]))
    card["note"] = (
        "numbers[] is empty because an abstention on this axis has nothing to measure -- "
        "unlike A5, which abstains for want of a limit while still knowing the cost."
    )
    return card


if __name__ == "__main__":
    qid = sys.argv[1] if len(sys.argv) > 1 else "sim-20260917-001"
    config = sys.argv[2] if len(sys.argv) > 2 else "bd_overdamped"
    created_at = sys.argv[3] if len(sys.argv) > 3 else "2026-09-17T12:10:00Z"
    print(cards.write(cards.question_dir(qid) / f"axis_{config}_{AXIS}.json",
                      build(qid, config, created_at)).relative_to(cards.REPO))
