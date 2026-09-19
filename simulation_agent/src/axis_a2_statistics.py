"""A2 -- statistics (plan.md 4.5.3).

The inequality this axis owns: **enough independent samples to meet the
target uncertainty.** For a diffusivity read off the slope of a mean squared
displacement, the samples that count are displacements separated by more than
the longest lag in the fit -- displacements closer than that share most of
their path and are not independent. So

    independent_samples ~ n_particles * total_simulated_time / max_lag_time

and the requirement is a floor on that product. A2 owns the ensemble size and
the trajectory length together because they appear in one inequality
(4.5.3 rule a); it does not own the save interval, which is A4's.

`independent_samples_min` is an estimate rather than a derivation. The
1/sqrt(N) scaling is not in doubt, but the prefactor for an MSD slope estimator
depends on the fit range and on how the lags are weighted, and none of that has
been measured on this model.
"""

from __future__ import annotations

import sys

from . import cards

AXIS = "a2"


def build(qid: str, config: str, created_at: str, caller_id: str, kb_version: str,
          kb_result: dict | None = None) -> dict:
    """The caller_id is injected by the fan-out executor, never chosen here.

    4.3.1 rule 3: a sub-agent that picks its own id can impersonate a
    sibling's. The check below refuses an id that does not name this axis --
    that catches an executor mistake, and is not this module choosing one.
    """
    if not caller_id.endswith(f":{AXIS}"):
        raise ValueError(f"{caller_id!r} was issued to another axis; this module is {AXIS}")

    goal = cards.load_goal(qid)
    numbers, assumptions = cards.carry(goal, ["max_lag_time", "n_particles"])
    grades = {n["name"]: n["grade"] for n in numbers}

    numbers.append(
        cards.num(
            "target_relative_error",
            0.1,
            "1",
            "assumed:a_statistics",
            precision="order_of_magnitude",
            note="ten per cent, which is well inside the one decade the goal asks for",
        )
    )
    numbers.append(
        cards.num(
            "independent_samples_min",
            100,
            "count",
            "assumed:a_statistics",
            precision="order_of_magnitude",
            note="one over the square of the target error; entered as an estimate because the prefactor of an MSD slope estimator is not derived here",
        )
    )
    numbers.append(
        cards.num(
            "total_simulated_time_min",
            0.2,
            "s",
            "computed:independent_samples_over_ensemble",
            formula="independent_samples_min * max_lag_time / n_particles",
            inputs=[
                ("independent_samples_min", "E5"),
                ("max_lag_time", grades["max_lag_time"]),
                ("n_particles", grades["n_particles"]),
            ],
            precision="order_of_magnitude",
            note="floor only. A2 does not bound the run from above; that is A5's",
        )
    )
    numbers.append(
        cards.num(
            "lag_to_record_ratio_max",
            0.1,
            "1",
            "assumed:a_window_statistics",
            precision="order_of_magnitude",
            note="the largest share of the record one lag may span. At a ratio of one the longest lag has a single displacement per tracer",
        )
    )
    assumptions.append(
        {
            "rationale_id": "a_window_statistics",
            "statement": "A lag may span at most about a tenth of the record, so that every lag in the fit is determined by many displacements rather than by one. The vocabulary requires the window to satisfy this statistical bound as well as the physical one but deliberately fixes no fraction -- a number chosen in the contract would be a threshold nobody measured -- so the value is declared here and carried into the plan.",
            "numbers": ["lag_to_record_ratio_max"],
            "falsifier": "a weighted fit whose slope is unchanged when the longest lag is shortened retires this fraction",
        }
    )
    assumptions.append(
        {
            "rationale_id": "a_statistics",
            "statement": "A ten per cent statistical error needs of order one hundred independent samples, from the square-root scaling of an ensemble mean. The target is set at ten per cent rather than at the goal's full decade so that the statistical error is not what decides the decade.",
            "numbers": ["target_relative_error", "independent_samples_min"],
            "falsifier": "a seed-to-seed spread wider than ten per cent at this sample count retires the prefactor and raises the floor",
        }
    )

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
                "parameter": "total_simulated_time",
                "unit": "s",
                "min": 0.2,
                "basis": ["total_simulated_time_min"],
                "precision": "order_of_magnitude",
            },
            {
                "parameter": "lag_to_record_ratio",
                "unit": "1",
                "max": 0.1,
                "basis": ["lag_to_record_ratio_max"],
                "precision": "order_of_magnitude",
            },
        ],
    )
    card.update(cards.tail(numbers, assumptions=assumptions, **cards.evidence(kb_result, [])))
    card["note"] = (
        "The ensemble is taken from the goal rather than bounded here: the tracers do not "
        "interact, so trading particles against time is free along this axis. A3 is where "
        "the ensemble costs something, because the box has to hold it."
    )
    return card


if __name__ == "__main__":
    # Runnable alone, but only with an id handed in: whoever runs it is acting
    # as the fan-out executor and says so by supplying one (4.3.1 rule 3).
    # `python3 -m src.fanout` is the normal path and issues all six.
    if len(sys.argv) < 6:
        raise SystemExit(
            "usage: python3 -m src.axis_a2_statistics <qid> <config> <created_at> "
            "<caller_id> <kb_version>"
            "\n"
            "The caller_id is issued by the fan-out executor and cannot be chosen "
            "here (4.3.1 rule 3). Use `python3 -m src.fanout` unless you are "
            "standing in for it."
        )
    qid, config, created_at, caller_id, kb_version = sys.argv[1:6]
    print(cards.write(cards.question_dir(qid) / f"axis_{config}_{AXIS}.json",
                      build(qid, config, created_at, caller_id, kb_version, None)).relative_to(cards.REPO))
