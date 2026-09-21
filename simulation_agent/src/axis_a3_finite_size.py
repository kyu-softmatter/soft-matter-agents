"""A3 -- finite size (plan.md 4.5.3).

Two inequalities bound the box from below, for unrelated reasons, and both
are recorded rather than collapsed into whichever happens to bind:

1. **Periodic images.** Under periodic boundaries a tracer that diffuses far
   enough during the fit window meets its own image, and the displacement it
   reports is no longer a free-space displacement. The root mean square
   displacement per axis over the window is `sqrt(2 D t)`, and the box has to
   be a good multiple of it.

2. **Dilution.** The tracers do not interact in this model, so nothing stops
   them overlapping -- which is exactly why the box size has to carry the
   dilution instead. The observable is defined for *dilute* tracers
   (contracts/observables.json), so the mean spacing has to stay well above
   the particle size, or the number produced answers a different question than
   the one the vocabulary names.

Emitting both as separate intervals on the same parameter is deliberate. S4
intersects them and the tighter one wins, but the record still says there were
two reasons -- collapsing them here would leave nothing behind to say that the
image bound existed (P1).
"""

from __future__ import annotations

import sys

from . import cards

AXIS = "a3"


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
    numbers, assumptions = cards.carry(
        goal,
        ["diffusivity", "max_lag_time", "bead_diameter", "particles_per_edge"],
    )
    grades = {n["name"]: n["grade"] for n in numbers}

    numbers.append(
        cards.num(
            "box_margin_factor",
            10,
            "1",
            "assumed:a_box_margin",
            precision="order_of_magnitude",
            note="how many rms displacements of clearance the box needs before an image matters",
        )
    )
    numbers.append(
        cards.num(
            "box_length_min_images",
            20,
            "um",
            "computed:margin_over_rms_displacement",
            formula="box_margin_factor * (2 * diffusivity * max_lag_time) ** 0.5",
            inputs=[
                ("box_margin_factor", "E5"),
                ("diffusivity", grades["diffusivity"]),
                ("max_lag_time", grades["max_lag_time"]),
            ],
            precision="order_of_magnitude",
            note="a tracer must not reach its own periodic image within the fit window",
        )
    )
    numbers.append(
        cards.num(
            "spacing_factor",
            5,
            "1",
            "assumed:a_dilution",
            precision="order_of_magnitude",
            note="mean centre-to-centre spacing in particle diameters",
        )
    )
    numbers.append(
        cards.num(
            "box_length_min_dilution",
            300,
            "um",
            "computed:spacing_times_particles_per_edge",
            formula="spacing_factor * bead_diameter * particles_per_edge",
            inputs=[
                ("spacing_factor", "E5"),
                ("bead_diameter", grades["bead_diameter"]),
                ("particles_per_edge", grades["particles_per_edge"]),
            ],
            precision="order_of_magnitude",
            note="the binding bound here: dilution costs a hundred microns, images only nine",
        )
    )
    assumptions += [
        {
            "rationale_id": "a_box_margin",
            "gap_ref": "box_margin_factor_absent",
            "statement": "Ten root-mean-square displacements of clearance keeps the image contribution to the mean squared displacement far below the ten per cent statistical error. It is a margin rather than a measured threshold.",
            "numbers": ["box_margin_factor"],
            "falsifier": "a run at a smaller box that reproduces the same diffusivity retires the margin",
        },
        {
            "rationale_id": "a_dilution",
            "gap_ref": "tracer_spacing_factor_absent",
            "statement": "Dilute means the mean spacing is large compared with the particle, and five diameters is the conventional reading of that. The tracers do not interact in this model, so this bound protects the meaning of the observable rather than the physics of the run.",
            "numbers": ["spacing_factor"],
            "falsifier": "a vocabulary entry that states a volume fraction for dilute replaces this with that number",
        },
    ]

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
        verdict="feasible",
        constraints=[
            {
                "parameter": "box_length",
                "unit": "um",
                "min": 9,
                "basis": ["box_length_min_images"],
                "precision": "order_of_magnitude",
            },
            {
                "parameter": "box_length",
                "unit": "um",
                "min": 100,
                "basis": ["box_length_min_dilution"],
                "precision": "order_of_magnitude",
            },
        ],
    )
    card.update(cards.tail(numbers, assumptions=assumptions, **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
    card["note"] = (
        "Boundary conditions are periodic in all three directions; that is what makes the "
        "image bound apply at all. A wall would replace it with a different inequality."
    )
    return card


if __name__ == "__main__":
    # Runnable alone, but only with an id handed in: whoever runs it is acting
    # as the fan-out executor and says so by supplying one (4.3.1 rule 3).
    # `python3 -m src.fanout` is the normal path and issues all six.
    if len(sys.argv) < 6:
        raise SystemExit(
            "usage: python3 -m src.axis_a3_finite_size <qid> <config> <created_at> "
            "<caller_id> <kb_version>"
            "\n"
            "The caller_id is issued by the fan-out executor and cannot be chosen "
            "here (4.3.1 rule 3). Use `python3 -m src.fanout` unless you are "
            "standing in for it."
        )
    qid, config, created_at, caller_id, kb_version = sys.argv[1:6]
    print(cards.write(cards.question_dir(qid) / f"axis_{config}_{AXIS}.json",
                      build(qid, config, created_at, caller_id, kb_version, None)).relative_to(cards.REPO))
