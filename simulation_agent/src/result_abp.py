"""The result card for one arm of an active compare (plan.md 5.1, 4.6 O4).

`result_card.py` is bd_overdamped's, and its central ruling does not carry
over: there the fitted diffusivity may only appear as a comparison term,
because the configuration's output is fixed by its inputs. `abp_wca_2d`
declares `output_independent_of_input: true`, so a run of it IS evidence
about the model, and the effective translational diffusivity this run read
goes into `values[]` as a `simulated:` number, graded max(E4, worst input) --
E5, because the Peclet number, the packing fraction and the WCA depth were
assumed into it. That is the true grade and not a defect to tidy.

Everything else is the other module's discipline, reused where it is not
configuration-specific: the run is read back from its four files, the plan
is resolved by the revision the run carried and checked by hash, every
criterion the plan declares is evaluated with the plan's own comparator in
SI or reported as not evaluable with the reason, deviations are exact
reproduction or nothing, and the time base is the model step index.

**One criterion needs the other arm.** `arms_agree_within_decade` compares
the effective diffusivity of the arm at ten persistence lengths with the arm
at one. A single run cannot answer it; when the other arm's run is on disk
under the same plan the ratio is computed and the criterion evaluated, and
when it is not the criterion is `met: null` with that reason. The second
arm's card therefore answers the compare, and the first arm's says it could
not yet.

**The estimator's window is checked at both ends** against what the plan
declared: the shortest lag fitted must be the declared lower bound and the
longest the declared window. A run that stopped early fits a shorter range,
`estimation.followed` goes false, and every criterion standing on the fit
comes out null rather than compared against a number the vocabulary's
estimator did not produce.
"""

from __future__ import annotations

import json
import math
import sys

from . import cards, operator, result_card
from .result_card import Unwritable, carried, reading, read_run, plan_of, time_base, deviation, \
    outcome_of, targets_from, assumptions_for, kb_refs_for, unevaluated, threshold_si, RUNS

OBSERVED = {
    "planned_duration_reached": ("total_simulated_time_actual", False),
    "step_displacement_diverged": ("max_step_displacement", False),
    "statistics_met": ("relative_standard_error", True),
    "arms_agree_within_decade": ("arm_disagreement_decades", True),
    "window_insensitive": ("window_half_disagreement", True),
}

RENAMED = {
    "total_simulated_time_point": "total_simulated_time_planned",
    "integration_timestep_point": "integration_timestep_planned",
    "save_interval_point": "save_interval_planned",
    "max_lag_time_point": "max_lag_time_planned",
    "fit_lag_range_lower_bound_point": "fit_lag_range_lower_bound_planned",
}


def other_arm_fit(plan: dict, this_run: str, this_arm: str) -> tuple[str, dict] | None:
    """The other arm's fitted effective diffusivity, if a run of it exists
    under the same plan (same id, revision and hash)."""
    for d in sorted(RUNS.iterdir()):
        if d.name == this_run or not (d / "config.json").exists() or not (d / "observables.json").exists():
            continue
        cfg = json.loads((d / "config.json").read_text())
        if cfg.get("plan_id") != plan["id"] or cfg.get("plan_hash") != operator.plan_hash(plan):
            continue
        if cfg.get("compare_arm") in (None, this_arm):
            continue
        fit = json.loads((d / "observables.json").read_text()).get("fit") or {}
        if fit.get("diffusivity"):
            return d.name, fit
    return None


def estimation_of(run: dict, lower_planned: dict, window_planned: dict) -> dict:
    fit = run["observables"]["fit"]
    deviations = []
    if fit.get("shortest_lag") != operator.si(lower_planned):
        deviations.append(f"the shortest lag fitted was {fit.get('shortest_lag')} s against a declared lower bound of {operator.si(lower_planned)} s")
    if fit.get("longest_lag") != operator.si(window_planned):
        deviations.append(f"the longest lag fitted was {fit.get('longest_lag')} s against a declared max_lag_time of {operator.si(window_planned)} s, so the record ended before the window")
    out = {"vocabulary_version": result_card.vocabulary_version(), "followed": not deviations,
           "note": ("effective_translational_diffusivity as contracts/observables.json declares it: weighted least squares of the "
                    "MSD on lag over lags at or above the declared lower bound, slope over 2*d with d = 2, run by abp_backend "
                    "through estimator_abp. What is compared here is the fit range at both ends")}
    if deviations:
        out["deviations"] = deviations
    return out


def evaluate(plan, by_name, meta, estimation, targets) -> list[dict]:
    out = []
    for kind, key in (("stop", "stop_criteria"), ("success", "success_criteria")):
        for cr in plan.get(key) or []:
            cid = cr["id"]
            if cid not in OBSERVED:
                raise Unwritable(f"the plan declares criterion {cid!r} and this module has no number for it")
            name, from_estimator = OBSERVED[cid]
            if name not in by_name:
                why = ("the other arm of the compare has not run under this plan, so the ratio of the two effective "
                       "diffusivities cannot be formed; the second arm's card answers this criterion"
                       if cid == "arms_agree_within_decade" else
                       f"the run record carries no value for {cr.get('metric')!r}, so there is nothing to compare")
                out.append(unevaluated(cid, kind, None, why))
                continue
            if from_estimator and not estimation.get("followed", True):
                out.append(unevaluated(cid, kind, name, "the estimator did not run over the declared range -- "
                                       + "; ".join(estimation.get("deviations") or [])))
                continue
            threshold = threshold_si({**cr, "number": RENAMED.get(cr.get("number"), cr.get("number"))} if cr.get("number") else cr,
                                     plan, by_name, targets)
            if threshold is None:
                out.append(unevaluated(cid, kind, name, f"no target for {cr.get('target')!r} is stated on this card"))
                continue
            observed = operator.si(by_name[name])
            met = operator.COMPARATORS[cr["comparator"]](observed, threshold)
            if kind == "stop" and meta.get("stopped_by") == cid and not met:
                raise Unwritable(f"{cid!r} stopped the run and does not evaluate as met against the final record")
            out.append({"id": cid, "kind": kind, "met": met, "observed_number": name})
    return out


def build(run_id: str) -> dict:
    run = read_run(run_id)
    plan, plan_path = plan_of(run)
    qid = run["config"]["qid"]
    arm = run["config"].get("compare_arm")
    if arm is None:
        raise Unwritable(f"{run_id} names no compare arm; this module writes cards for arms of a compare")
    fit = run["observables"]["fit"]; unc = run["observables"].get("uncertainty") or {}; meta = run["meta"]
    if fit.get("diffusivity") is None:
        raise Unwritable(f"{run_id} produced no fitted effective diffusivity -- {fit.get('reason')!r}")
    if unc.get("standard_error") is None:
        raise Unwritable(f"{run_id} carries no block standard error ({unc.get('reason')})")

    numbers: list[dict] = []

    def carry(src, as_name=None):
        n = carried(plan, plan_path, src, as_name); numbers.append(n); return n

    temperature = carry("temperature"); viscosity = carry("viscosity"); bead = carry("bead_diameter")
    d_r = carry("rotational_diffusivity"); carry("translational_diffusivity"); eps = carry("wca_epsilon")
    pe = carry("peclet"); phi = carry("packing_fraction"); carry("persistence_time_expected")
    carry("target_relative_error")
    dt_p = carry("integration_timestep_point", RENAMED["integration_timestep_point"])
    dur_p = carry("total_simulated_time_point", RENAMED["total_simulated_time_point"])
    save_p = carry("save_interval_point", RENAMED["save_interval_point"])
    win_p = carry("max_lag_time_point", RENAMED["max_lag_time_point"])
    low_p = carry("fit_lag_range_lower_bound_point", RENAMED["fit_lag_range_lower_bound_point"])
    arm_conditions = {a["arm"]: a["conditions"] for a in plan.get("compare_arms") or []}
    box_src = next(c["number"] for c in arm_conditions[arm] if c["parameter"] == "box_length")
    box = carry(box_src, "box_length")
    n_src = f"n_particles_arm_{arm}" if f"n_particles_arm_{arm}" in {n["name"] for n in plan["numbers"]} else "n_particles_largest_arm"
    n_p = carry(n_src, "n_particles")

    model_inputs = [temperature, viscosity, bead, d_r, eps, pe, phi, box, n_p, dt_p, save_p, win_p, low_p]

    def read(name, value_si, unit, inputs, note=None):
        if value_si is None:
            return None
        n = reading(name, value_si, unit, run_id, inputs, note); numbers.append(n); return n

    d_eff = read("effective_translational_diffusivity", fit["diffusivity"], "um^2/s", model_inputs,
                 note=("the long-time slope of the MSD over 2*d for lags at or above the declared lower bound, read off this run. "
                       "For abp_wca_2d the output is not fixed by the inputs (capabilities: independent true), so this is the card's "
                       "claim about the model and not a comparison term; its grade is the worst of what went in"))
    se = read("effective_translational_diffusivity_standard_error", unc["standard_error"], "um^2/s", model_inputs,
              note=f"block-resampled over {unc.get('blocks')} particle blocks; the fit's own error is not used (task 006)")
    read("relative_standard_error", unc["standard_error"] / fit["diffusivity"], "1", model_inputs,
         note="the block standard error over the estimate, compared by statistics_met")
    read("window_half_disagreement", (run["observables"].get("window_sensitivity") or {}).get("log10_ratio"), "count", model_inputs,
         note="log10 of the slope over the first half of the fit range against the second, in absolute value; zero when the plateau is reached")
    pt = (run["observables"].get("persistence_time") or {}).get("persistence_time")
    read("persistence_time", pt, "s", model_inputs,
         note="decay time of the orientational autocorrelation fitted on a log scale over lags where it stays above 0.05; the input-side expectation is persistence_time_expected")
    other = other_arm_fit(plan, run_id, arm)
    if other is not None:
        other_run, other_fit = other
        read("arm_disagreement_decades", abs(math.log10(fit["diffusivity"] / other_fit["diffusivity"])), "count", model_inputs,
             note=f"log10 of this arm's effective diffusivity over the other arm's ({other_run}), in absolute value: the compare's own question")
    sim_time, steps, frames = meta.get("simulated_time"), meta.get("steps_taken"), meta.get("frames_saved")
    dur_a = read("total_simulated_time_actual", sim_time, dur_p["unit"], [dt_p, dur_p], note="steps_taken * dt, read off the integer step count")
    read("max_step_displacement", meta.get("max_single_step_displacement"), "um", [dt_p, pe, d_r, bead],
         note="the largest single-step displacement any particle took, which the divergence criterion watches against the bead diameter")
    dt_a = read("integration_timestep_actual", (sim_time / steps) if sim_time and steps else None, dt_p["unit"], [dt_p, dur_p])
    save_a = read("save_interval_actual", (sim_time / (frames - 1)) if sim_time and frames and frames > 1 else None, save_p["unit"], [save_p, dur_p])
    win_a = read("max_lag_time_actual", fit.get("longest_lag"), win_p["unit"], [win_p, save_p])
    low_a = read("fit_lag_range_lower_bound_actual", fit.get("shortest_lag"), low_p["unit"], [low_p, save_p])

    estimation = estimation_of(run, low_p, win_p)
    targets = targets_from(plan, qid)
    by_name = {n["name"]: n for n in numbers}
    criteria = evaluate(plan, by_name, meta, estimation, targets)
    deviations = [d for d in (deviation("integration_timestep", dt_p, dt_a), deviation("total_simulated_time", dur_p, dur_a),
                              deviation("save_interval", save_p, save_a), deviation("max_lag_time", win_p, win_a),
                              deviation("fit_lag_range_lower_bound", low_p, low_a)) if d is not None]
    outcome = outcome_of(meta)
    card = cards.head("result", f"result-{qid}-{run_id}", qid, run["log"]["finished_at"],
                      thread=plan.get("thread", f"solo-{qid}"), round=plan.get("round", 0), revision=1,
                      status="FAILED" if outcome == "FAILED" else "DONE")
    values = [{"metric": "effective_translational_diffusivity", "number": d_eff["name"], "uncertainty": se["name"]}]
    if pt is not None:
        values.append({"metric": "persistence_time", "number": "persistence_time", "uncertainty": None})
    card.update({
        "plan_id": plan["id"], "plan_revision": plan["revision"], "plan_hash": run["config"]["plan_hash"],
        "approval_id": (run["config"].get("approval") or {}).get("id"), "run_id": run_id,
        "observable": cards.observable(plan["observable"]["name"]), "outcome": outcome,
        "values": values, "criteria_evaluation": criteria, "deviations": deviations,
        "time_base": time_base(run["log"]), "targets": targets, "estimation": estimation,
    })
    card.update(cards.tail(numbers, assumptions=assumptions_for(plan, numbers), kb_refs=kb_refs_for(plan, numbers),
                           kb_gaps=[], degraded=list(plan.get("degraded") or [])))
    return card


def emit(run_id: str):
    card = build(run_id)
    path = result_card.path_for(card["qid"], run_id)
    cards.refuse_overwrite(path, card["revision"], card)
    return cards.write(path, card)


if __name__ == "__main__":
    print(emit(sys.argv[1]).relative_to(cards.REPO))
