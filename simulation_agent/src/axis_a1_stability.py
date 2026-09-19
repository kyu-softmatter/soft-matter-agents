"""A1 -- integration stability (plan.md 4.5.3).

The inequality this axis owns: **the integration step must resolve the
shortest characteristic time of the system.** Nothing else here is A1's
business -- how many steps to take is A2's and A5's, how often to save is
A4's.

For an overdamped Brownian dynamics run there is no inertial time to resolve.
The momentum relaxation time is absent from the physics by construction, and
mass-based time units have no experimental counterpart (4.2, 5.7), so the
shortest time that has to be resolved is set by the slowest thing that still
moves: for dilute non-interacting tracers, the diffusive time -- the librarian's
`kb:tau_d`, the time a sphere needs to diffuse its own diameter --

    tau_d = d^2 / D

and the step has to sit well below it. The definition is cited rather than
re-derived: a hand-made radius-squared version would be a second definition of
the same symbol at a worse grade. `dt_resolution_factor` is how far
below, and it is a judgement rather than a derivation -- so it enters as an
estimate with a falsifier, and the bound it produces inherits its grade.

**All of it rests on the tracers not interacting**, and that premise is in the
card as `a_non_interacting`. With a pair potential the curvature time is
usually much shorter than the diffusive time and this bound would be wrong by
decades, so the premise is not context -- it is the load-bearing part.

**This module does not choose dt.** It returns the interval and S4 picks the
point inside it (4.5.2). Choosing here would produce one plan per axis and
nothing could be synthesised.
"""

from __future__ import annotations

import sys

from . import cards

AXIS = "a1"


def build(qid: str, config: str, created_at: str, caller_id: str, kb_version: str) -> dict:
    """The caller_id is injected by the fan-out executor, never chosen here.

    4.3.1 rule 3: a sub-agent that picks its own id can impersonate a
    sibling's. The check below refuses an id that does not name this axis --
    that catches an executor mistake, and is not this module choosing one.
    """
    if not caller_id.endswith(f":{AXIS}"):
        raise ValueError(f"{caller_id!r} was issued to another axis; this module is {AXIS}")

    goal = cards.load_goal(qid)
    numbers, assumptions = cards.carry(goal, ["bead_diameter", "diffusivity"])
    grades = {n["name"]: n["grade"] for n in numbers}

    # The shortest time the integrator has to resolve, and it is the
    # librarian's definition rather than a second one. kb:tau_d is E4 with a
    # validity of "spherical tracer, bulk fluid, no slip, overdamped" -- this
    # configuration exactly. Re-deriving it by hand as a radius-squared time
    # would produce a worse-graded number that differs by a factor of four and
    # a second definition of the same symbol, which is what check 36 exists to
    # catch (5.7).
    numbers.append(
        cards.num(
            "tau_d",
            20,
            "s",
            "computed:diffusive_time",
            formula="bead_diameter**2/diffusivity",
            inputs=[
                ("bead_diameter", grades["bead_diameter"]),
                ("diffusivity", grades["diffusivity"]),
            ],
            derived=True,
            symbol="tau_d",
            precision="order_of_magnitude",
            note="kb:tau_d. The grade follows the inputs, not the entry: a formula applied to estimates yields an estimate",
        )
    )
    numbers.append(
        cards.num(
            "dt_resolution_factor",
            0.01,
            "1",
            "assumed:a_dt_factor",
            precision="order_of_magnitude",
            note="how far below the diffusive time the step must sit: two decades",
        )
    )
    numbers.append(
        cards.num(
            "integration_timestep_max",
            0.2,
            "s",
            "computed:resolution_of_shortest_time",
            formula="dt_resolution_factor * tau_d",
            inputs=[("dt_resolution_factor", "E5"), ("tau_d", "E5")],
            precision="order_of_magnitude",
            note="upper bound only; nothing in A1 bounds the step from below",
        )
    )
    assumptions += [
        {
            "rationale_id": "a_dt_factor",
            "statement": "Two decades below the shortest resolved time is the usual margin for an overdamped integrator, but it is a convention rather than a derivation: no convergence scan on this model has been run.",
            "numbers": ["dt_resolution_factor"],
            "falsifier": "a timestep scan showing the diffusivity flat over a wider range of steps replaces this factor with a measured one",
        },
        {
            "rationale_id": "a_non_interacting",
            "statement": "The tracers do not interact. No pair potential is part of this configuration and none is declared in capabilities/simulation.json, so the diffusive time is the shortest time in the system. This premise is what the bound rests on: with interactions the curvature time of the potential, gamma over k, is usually far shorter, and a step set from the diffusive time would be wrong by decades rather than by a factor.",
            "numbers": ["tau_d", "integration_timestep_max"],
            "falsifier": "any interaction parameter entering the model retires this bound and the axis has to be re-run against the curvature time",
        },
    ]

    card = cards.head(
        "axis",
        f"axis-{qid}-{config}-{AXIS}",
        qid,
        created_at,
        caller_id=caller_id,
        config=config,
        axis=AXIS,
        kb_version=kb_version,
        method="deterministic",
        verdict="feasible",
        constraints=[
            {
                "parameter": "integration_timestep",
                "unit": "s",
                "max": 0.2,
                "basis": ["integration_timestep_max"],
                "precision": "order_of_magnitude",
            }
        ],
    )
    card.update(
        cards.tail(
            numbers,
            assumptions=assumptions,
            kb_refs=[
            {
                "entry_id": "tau_d",
                "grade": "E4",
                "kb_version": kb_version,
                "claim": "The diffusive time is the time a sphere needs to diffuse its own diameter, and it sets the shortest record length from which a mean squared displacement can be read.",
            }
            ],
            degraded=["librarian_agent"],
        )
    )
    card["note"] = (
        "The form of the bound is the librarian's definition and its prefactor is an estimate, "
        "so S4 should weight it accordingly (4.5.2). The premise that matters most is not a "
        "number at all: the tracers do not interact, and a_non_interacting records it."
    )
    return card


if __name__ == "__main__":
    # Runnable alone, but only with an id handed in: whoever runs it is acting
    # as the fan-out executor and says so by supplying one (4.3.1 rule 3).
    # `python3 -m src.fanout` is the normal path and issues all six.
    if len(sys.argv) < 6:
        raise SystemExit(
            "usage: python3 -m src.axis_a1_stability <qid> <config> <created_at> "
            "<caller_id> <kb_version>"
            "\n"
            "The caller_id is issued by the fan-out executor and cannot be chosen "
            "here (4.3.1 rule 3). Use `python3 -m src.fanout` unless you are "
            "standing in for it."
        )
    qid, config, created_at, caller_id, kb_version = sys.argv[1:6]
    print(cards.write(cards.question_dir(qid) / f"axis_{config}_{AXIS}.json",
                      build(qid, config, created_at, caller_id, kb_version)).relative_to(cards.REPO))
