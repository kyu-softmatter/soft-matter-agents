"""The result card for `bd_overdamped_trapped` (sim-20260923-102).

`result_trap`'s shape with the observable a width. The card's CLAIM is the
model's prediction, sqrt(k_B*T/k_t), computed from the plan's own numbers; what
the run read enters only as comparison terms, each named by a field. A run's
observable is not a graded number on this side yet (5.3 has no source kind
for it), which is the ruling `result_trap` and this module both follow.

Criteria evaluated, with the plan's own comparators:

    step_displacement_diverged   -> max_step_displacement
    width_within_decade          -> width_deviation_in_decades, |log10(measured/predicted)|
    width_within_three_scatters  -> relative_deviation_of_width_from_equipartition

`width_within_decade` is the goal's decade target read as what a decade means
for a width: the log of the ratio, at most one. The observable itself is a
length and a decade target is a count, so comparing the two directly would
compare metres with a number of decades.
"""

from __future__ import annotations

import math
import sys

from . import cards, operator, result_card
from .config_bd_overdamped_trapped import _one
from .result_card import (Unwritable, assumptions_for, carried, deviation, kb_refs_for,
                          outcome_of, plan_of, read_run, reading, targets_from, threshold_si,
                          time_base, unevaluated)

CONFIG = "bd_overdamped_trapped"
OBSERVED = {
    "step_displacement_diverged": "max_step_displacement",
    "width_within_decade": "width_deviation_in_decades",
    "width_within_three_scatters": "relative_deviation_of_width_from_equipartition",
}


def evaluate(plan, by_name, meta, targets):
    out = []
    for kind, key in (("stop", "stop_criteria"), ("success", "success_criteria")):
        for cr in plan.get(key) or []:
            cid = cr["id"]
            if cid not in OBSERVED:
                raise Unwritable(f"the plan declares criterion {cid!r} and this module has no reading for it")
            name = OBSERVED[cid]
            if name not in by_name:
                out.append(unevaluated(cid, kind, None, f"the run record carries no value for {cr.get('metric')!r}"))
                continue
            if cid == "width_within_decade":
                threshold = 1.0   # one decade: the goal's decade_resolution target, value 1
            else:
                threshold = threshold_si(cr, plan, by_name, targets)
            if threshold is None:
                out.append(unevaluated(cid, kind, name, f"no threshold for {cr.get('target') or cr.get('number')!r}"))
                continue
            observed = operator.si(by_name[name])
            met = operator.COMPARATORS[cr["comparator"]](observed, threshold)
            if kind == "stop" and meta.get("stopped_by") == cid and not met:
                raise Unwritable(f"{cid!r} stopped the run and does not evaluate as met")
            out.append({"id": cid, "kind": kind, "met": met, "observed_number": name})
    return out


def build(run_id: str) -> dict:
    run = read_run(run_id)
    plan, plan_path = plan_of(run)
    if (plan.get("system_configuration") or {}).get("config") != CONFIG:
        raise Unwritable(f"{run_id} ran {plan.get('system_configuration')!r}; this module writes cards for {CONFIG}")
    if run["config"].get("plan_hash") != operator.plan_hash(plan):
        raise Unwritable(f"{plan_path.name} has changed since {run_id} read it; a result cites the plan that ran")
    qid = run["config"]["qid"]
    obs, meta, log = run["observables"], run["meta"], run["log"]
    w = obs.get("trapped_position_distribution")
    if not w:
        raise Unwritable(f"{run_id} carries no width block; nothing to report")

    cond = {c["parameter"]: c["number"] for c in plan["conditions"]}
    numbers: list[dict] = []

    def carry(src):
        n = carried(plan, plan_path, src)
        numbers.append(n)
        return n

    temperature = carry(cond["temperature"]); viscosity = carry(cond["viscosity"])
    bead = carry(cond["bead_diameter"]); k_t = carry(cond["trap_stiffness"])
    dt_p = carry(cond["integration_timestep"]); save_p = carry(cond["save_interval"])
    startup_p = carry(cond["startup_discard"]); record_p = carry(cond["record_length"])
    for cr in plan.get("success_criteria") or []:
        if cr.get("number") and all(n["name"] != cr["number"] for n in numbers):
            carry(cr["number"])
    model_inputs = [temperature, viscosity, bead, k_t, dt_p, save_p, startup_p, record_p]
    g = {n["name"]: n["grade"] for n in numbers}

    # -- what the MODEL predicts, from the plan's own numbers: the card's claim --
    kT = 1.380649e-23 * operator.si(temperature)
    gamma = 3 * math.pi * operator.si(viscosity) * operator.si(bead)
    k_si, rec_si = operator.si(k_t), operator.si(record_p)
    p_w = cards.num(
        "thermal_width_predicted", _one(math.sqrt(kT / k_si) * 1e6), "um", "computed:equipartition_width",
        formula=f"(k_B*temperature/{k_t['name']})**0.5",
        inputs=[(n, g[n]) for n in ("temperature", k_t["name"])], precision="order_of_magnitude",
        note="sqrt(k_B*T/k_t) from the plan's inputs: the per-axis width the model predicts, and the number the "
             "bench width is compared against. One figure because the inputs are declared that way; the "
             "comparison that carries precision is the ratio in criteria_evaluation, set by the run")
    p_s = cards.num(
        "thermal_width_scatter_predicted", _one(math.sqrt(kT / k_si) * math.sqrt((gamma / k_si) / (2 * rec_si)) * 1e6),
        "um", "computed:ou_variance_standard_error",
        formula=f"(k_B*temperature/{k_t['name']})**0.5*(3*pi*viscosity*bead_diameter/({k_t['name']}*2*{record_p['name']}))**0.5",
        inputs=[(n, g[n]) for n in ("temperature", k_t["name"], "viscosity", "bead_diameter", record_p["name"])],
        precision="order_of_magnitude",
        note="the width's standard error from one record of the declared length, sigma*sqrt(tau/(2T))")
    numbers += [p_w, p_s]

    def read(name, value_si, unit, inputs, note):
        n = reading(name, value_si, unit, run_id, inputs, note)
        numbers.append(n)
        return n

    read("max_step_displacement", meta.get("max_single_step_displacement"), "um", model_inputs,
         "the largest single-step displacement, which the divergence criterion watches against the bead diameter")
    ax = w["axes"]
    ratio_log = max(abs(math.log10(a["ratio_to_equipartition"])) for a in ax.values())
    read("width_deviation_in_decades", ratio_log, "count", model_inputs,
         "|log10(measured width / predicted width)|, the larger of x and y: how many decades apart")
    read("relative_deviation_of_width_from_equipartition", w["relative_deviation_of_width_from_equipartition"], "1",
         model_inputs,
         "the larger of |x| and |y| width over sqrt(k_B*T/k_t), corrected for the record's expected low bias, "
         f"minus one. x read {ax['x']['ratio_bias_corrected']:.4f} and y {ax['y']['ratio_bias_corrected']:.4f} of "
         f"the prediction, {ax['x']['deviation_in_scatters']:+.2f} and {ax['y']['deviation_in_scatters']:+.2f} of "
         "the record's own scatter. NOT EVIDENCE ABOUT ANY TRAP: k_t went in")
    steps, sim_time, frames = meta.get("steps_taken"), meta.get("simulated_time"), meta.get("frames_saved")
    dt_a = read("integration_timestep_actual", sim_time / steps, dt_p["unit"], [dt_p],
                "simulated time over the integer step count")
    save_a = read("save_interval_actual", sim_time / (frames - 1), save_p["unit"], [save_p],
                  "simulated time over the number of intervals between saved frames")
    record_a = read("record_length_actual", w["record_length_si"], record_p["unit"], [record_p, startup_p],
                    "the span of frames the estimator read, after startup_discard")

    targets = targets_from(plan, qid)
    by_name = {n["name"]: n for n in numbers}
    criteria = evaluate(plan, by_name, meta, targets)
    deviations = [d for d in (deviation("integration_timestep", dt_p, dt_a),
                              deviation("save_interval", save_p, save_a),
                              deviation("record_length", record_p, record_a)) if d is not None]

    backend = run["config"].get("backend")
    if backend not in ("trap_hoomd_backend", "trap_backend"):
        raise Unwritable(f"{run_id} ran on {backend!r}, which this module cannot describe a cost for")
    cost = obs.get("cost") or {}
    new_facts = []
    if cost.get("wall_s_per_step"):
        numbers.append(cards.num(
            "cost_per_step_measured", float(f"{result_card.round_to_sig(cost['wall_s_per_step'], 2):g}")
            if hasattr(result_card, "round_to_sig") else round(cost["wall_s_per_step"], 8),
            "s", f"measured:{run_id}", precision="significant_figures",
            note=f"{cost['integration_wall_s']:.3f} s over {cost['steps']} steps of the integration loop alone, "
                 f"on {backend}, one bead, fluid at rest"))
        new_facts.append({
            "claim": (f"On this workstation {backend} costs about {cost['wall_s_per_step']*1e6:.1g} microseconds of "
                      "wall clock per integration step for one overdamped sphere in a harmonic trap with the fluid "
                      "at rest."),
            "numbers": ["cost_per_step_measured"],
            "validity_conditions": (f"{backend} as committed at the time of {run_id}, one particle, a save every "
                                    f"twenty steps, one run of {cost['steps']} steps on 2026-09-24 while other "
                                    "sessions shared the machine. Not a per-particle cost for N above one."),
            "proposed_grade": "E1",
        })

    outcome = outcome_of(meta)
    card = cards.head("result", f"result-{qid}-{run_id}", qid, log["finished_at"],
                      thread=plan.get("thread", f"solo-{qid}"), round=plan.get("round", 0), revision=1,
                      status="FAILED" if outcome == "FAILED" else "DONE")
    card.update({
        "plan_id": plan["id"], "plan_revision": plan["revision"], "plan_hash": run["config"]["plan_hash"],
        "approval_id": (run["config"].get("approval") or {}).get("id"), "run_id": run_id,
        "observable": cards.observable(plan["observable"]["name"]), "outcome": outcome,
        "values": [{"metric": plan["observable"]["name"], "number": p_w["name"], "uncertainty": p_s["name"]}],
        "criteria_evaluation": criteria, "deviations": deviations,
        "time_base": time_base(log), "targets": targets,
        "estimation": {
            "vocabulary_version": result_card.vocabulary_version(), "followed": True,
            "note": ("the registered estimator: the per-axis standard deviation of x and y about the record's own "
                     "mean over the declared record_length after startup_discard. The bias correction, the "
                     "histogram and the kurtosis ride on the same trace and are not the estimator"),
        },
        **({"new_facts": new_facts} if new_facts else {}),
    })
    card.update(cards.tail(numbers, assumptions=assumptions_for(plan, numbers),
                           kb_refs=kb_refs_for(plan, numbers), kb_gaps=[],
                           degraded=list(plan.get("degraded") or [])))
    return card


def emit(run_id: str):
    card = build(run_id)
    path = result_card.path_for(card["qid"], run_id)
    cards.refuse_overwrite(path, card["revision"], card)
    return cards.write(path, card)


if __name__ == "__main__":
    print(emit(sys.argv[1]).relative_to(cards.REPO))
