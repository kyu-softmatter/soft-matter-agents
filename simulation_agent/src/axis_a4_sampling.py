"""A4 -- sampling (plan.md 4.5.3).

Two inequalities, both about where the estimator's window sits relative to the
physics, and neither about how the run is integrated:

1. **Resolution of the window.** A slope fit needs the mean squared
   displacement sampled across the window, not at its ends, so the save
   interval has to sit well below the longest lag. Two decades of lag coverage
   is the target.

2. **Staying in the free regime.** `tracer_diffusivity` is defined over lags
   *below* the diffusive time (contracts/observables.json), so the window has
   an upper bound of its own: past the time to diffuse one particle radius the
   slope is no longer the free-space slope.

The second bound rests on the same timescale A1 uses, and derives it again
from the goal rather than reading A1's card. That is not duplication by
accident -- 4.5.3 rule (b) forbids an axis from taking a sibling's output as
input, and a shared *input* is the allowed way for two axes to agree.

A4 says nothing about the integration step. The step and the save interval are
related only through S4's intersection.
"""

from __future__ import annotations

import sys

from . import cards
from . import axes_abp

AXIS = "a4"


def build(qid: str, config: str, created_at: str, caller_id: str, kb_version: str,
          kb_result: dict | None = None, revision: int = 1) -> dict:
    if axes_abp.is_active(config):
        # The active configurations are a different physics; every number below is
        # bd_overdamped's. Dispatched rather than branched so this file regenerates
        # its own cards byte for byte (axes_abp).
        return axes_abp.build(AXIS, qid, config, created_at, caller_id, kb_version, kb_result, revision)
    FALLBACK_REFS = [
        {
                    "entry_id": "tau_d",
                    "grade": "E4",
                    "kb_version": kb_version,
                    "claim": "The diffusive time is the time a sphere needs to diffuse its own diameter, and it sets the shortest record length from which a mean squared displacement can be read.",
                }
    ]
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
    numbers, assumptions = cards.carry(
        goal, ["max_lag_time", "bead_diameter", "diffusivity"]
    )
    grades = {n["name"]: n["grade"] for n in numbers}

    numbers.append(
        cards.num(
            "lag_coverage_factor",
            0.01,
            "1",
            "assumed:a_lag_coverage",
            precision="order_of_magnitude",
            note="save interval as a fraction of the longest lag: two decades of coverage",
        )
    )
    numbers.append(
        cards.num(
            "save_interval_max",
            0.3,
            "s",
            "computed:two_decades_below_the_window",
            formula="lag_coverage_factor * max_lag_time",
            inputs=[("lag_coverage_factor", "E5"), ("max_lag_time", grades["max_lag_time"])],
            precision="order_of_magnitude",
            note="upper bound. Saving more often costs storage, which is A5's, not A4's",
        )
    )
    numbers.append(
        cards.num(
            "tau_d",
            300,
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
            note="kb:tau_d, applied to this card's own inputs rather than read from A1 (4.5.3 rule b). The entry says this time sets the shortest record an MSD can be read from, which is exactly what this axis needs it for",
        )
    )
    numbers.append(
        cards.num(
            "intercept_sigma_max",
            3,
            "1",
            "assumed:a_intercept_guard",
            precision="order_of_magnitude",
            note=(
                "how far the MSD fit's intercept may sit from zero, in standard errors of the "
                "BLOCK-RESAMPLED uncertainty and not the fit's own. The fit treats correlated MSD "
                "points as independent and quotes an error about 36x too small (measured over 32 "
                "seeds), so the same criterion against the fit's error would refuse a sound run: "
                "run-20260920-002 reads 6.5 sigma there and 2.0 sigma here"
            ),
        )
    )
    assumptions.append(
        {
            "rationale_id": "a_intercept_guard",
            "gap_ref": "msd_intercept_tolerance_absent",
            "statement": (
                "Three standard errors is a guard against a gross short-lag failure, not a test of "
                "bias, and it is set from the asymmetry rather than from any observation: a false "
                "refusal costs one re-run of a job sitting far under budget, while a false "
                "acceptance puts a biased number into a graded card. IT CANNOT DETECT AN ARTIFACT, "
                "and saying so is the point -- a systematic short-lag error shows in the MEAN over "
                "runs while a fluctuation shows in a single one, and no threshold on a single "
                "run's intercept separates them. Tight refuses good runs at the fluctuation rate; "
                "loose misses a small artifact. The test that catches an artifact is that the mean "
                "intercept over an ensemble of runs is consistent with zero, which needs a "
                "campaign and is not a criterion one plan can carry."
            ),
            "numbers": ["intercept_sigma_max"],
            "falsifier": (
                "a campaign whose mean intercept is inconsistent with zero, which would show this "
                "guard passing runs it cannot judge"
            ),
        }
    )
    assumptions.append(
        {
            "rationale_id": "a_lag_coverage",
            "gap_ref": "lag_coverage_factor_absent",
            "statement": "Two decades of lag below the window is enough to see whether the mean squared displacement is linear in lag at all, which is what a free-diffusion claim rests on. Fewer decades would fit a slope through a line nobody checked was straight.",
            "numbers": ["lag_coverage_factor"],
            "falsifier": "a fit whose residuals are flat over one decade retires the second decade",
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
        method="deterministic",
        verdict="feasible",
        constraints=[
            {
                "parameter": "save_interval",
                "unit": "s",
                "max": 0.02,
                "basis": ["save_interval_max"],
                "precision": "order_of_magnitude",
            },
            {
                "parameter": "max_lag_time",
                "unit": "s",
                "max": 20,
                "basis": ["tau_d"],
                "precision": "order_of_magnitude",
            },
        ],
    )
    card.update(cards.tail(
            numbers,
            assumptions=assumptions,
                        **cards.evidence(kb_result, FALLBACK_REFS + cards.carried_kb_refs(goal, numbers)),
    ))
    card["note"] = (
        "The window the goal chose sits an order of magnitude inside the diffusive time. "
        "That is a pass on this axis, not a coincidence worth keeping quiet about: had the goal "
        "asked for a longer window the observable's own definition would have refused it."
    )
    return card


if __name__ == "__main__":
    # Runnable alone, but only with an id handed in: whoever runs it is acting
    # as the fan-out executor and says so by supplying one (4.3.1 rule 3).
    # `python3 -m src.fanout` is the normal path and issues all six.
    if len(sys.argv) < 6:
        raise SystemExit(
            "usage: python3 -m src.axis_a4_sampling <qid> <config> <created_at> "
            "<caller_id> <kb_version>"
            "\n"
            "The caller_id is issued by the fan-out executor and cannot be chosen "
            "here (4.3.1 rule 3). Use `python3 -m src.fanout` unless you are "
            "standing in for it."
        )
    qid, config, created_at, caller_id, kb_version = sys.argv[1:6]
    print(cards.write(cards.question_dir(qid) / f"axis_{config}_{AXIS}.json",
                      build(qid, config, created_at, caller_id, kb_version, None)).relative_to(cards.REPO))
