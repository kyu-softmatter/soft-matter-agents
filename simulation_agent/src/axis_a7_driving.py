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


def build(qid: str, config: str, created_at: str, caller_id: str, kb_version: str,
          kb_result: dict | None = None, revision: int = 1) -> dict:
    """The caller_id is injected by the fan-out executor, never chosen here.

    4.3.1 rule 3: a sub-agent that picks its own id can impersonate a
    sibling's. The check below refuses an id that does not name this axis --
    that catches an executor mistake, and is not this module choosing one.
    """
    if not caller_id.endswith(f":{AXIS}"):
        raise ValueError(f"{caller_id!r} was issued to another axis; this module is {AXIS}")

    goal = cards.load_goal(qid, revision)
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
        f"axis-{qid}-{config}-{AXIS}" + ("" if revision == 1 else f"-r{revision}"),
        qid,
        created_at,
        revision=revision,
        caller_id=caller_id,
        config=config,
        axis=AXIS,
        kb_version=kb_version,
        method="deterministic",
        verdict="abstain",
        abstain_reason=(
            "No driving was requested. The goal names no driving parameter, and "
            f"{config} is declared undriven, so there is no driving amount for this axis to "
            "bound. Abstaining is not the same as being absent: this card is the record that "
            "the axis was asked and had nothing to constrain (P1)."
        ),
    )
    card.update(cards.tail([], **cards.evidence(kb_result, [])))
    card["note"] = (
        "numbers[] is empty because an abstention on this axis has nothing to measure -- "
        "unlike A5, which abstains for want of a limit while still knowing the cost."
    )
    return card


if __name__ == "__main__":
    # Runnable alone, but only with an id handed in: whoever runs it is acting
    # as the fan-out executor and says so by supplying one (4.3.1 rule 3).
    # `python3 -m src.fanout` is the normal path and issues all six.
    if len(sys.argv) < 6:
        raise SystemExit(
            "usage: python3 -m src.axis_a7_driving <qid> <config> <created_at> "
            "<caller_id> <kb_version>"
            "\n"
            "The caller_id is issued by the fan-out executor and cannot be chosen "
            "here (4.3.1 rule 3). Use `python3 -m src.fanout` unless you are "
            "standing in for it."
        )
    qid, config, created_at, caller_id, kb_version = sys.argv[1:6]
    print(cards.write(cards.question_dir(qid) / f"axis_{config}_{AXIS}.json",
                      build(qid, config, created_at, caller_id, kb_version, None)).relative_to(cards.REPO))
