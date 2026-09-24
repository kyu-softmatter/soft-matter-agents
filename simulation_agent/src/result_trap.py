"""The result card for one run of `bd_overdamped_trapped_uniform_flow` (plan.md 5.1, 4.6 O4).

The configuration declares `output_independent_of_input: false`, and that one
field decides the shape of this card. It is the ruling `result_card.py` carries
for `bd_overdamped` and not the one `result_abp.py` carries for the active
questions, whose configuration IS its own source:

**The card asserts the model's prediction and reports the run's reading.** 5.3,
as check 21 enforces it: `values[]` is the card claiming something about the
system, and a `simulated:` number may stand there only for a configuration
whose output its inputs do not fix. Here the estimator inverts the equation the
integrator solved -- gamma and k_t both go in, and the offset gamma*v/k_t comes
back out -- so `values[]` carries the offset and its sampling error AS THE MODEL
PREDICTS THEM from the plan's own numbers, and what the run read appears only as
comparison terms: each criterion's `observed_number` and each deviation's
`actual_number`. A verification run shows the two meeting and claims nothing
beyond that.

**Every reading is named by a field, or it is not on this card.** Check 21
refuses a `simulated:` number that no field names, because nothing would then
say it is the run's reading rather than a claim. So the run's diagnostics --
the stiffness through equipartition, the fitted relaxation time, the transverse
means -- stay in `runs/<id>/observables.json`, the run's own record, and do not
come here as free numbers. The plan declared no criterion over them, and a
criterion written after the run would be narration (5.4).

**The one fact this run returns to the store is its cost.** A5 asked for
`cost_per_particle_step_overdamped` and the librarian answered absent; the run
timed its own integration loop. That is a measurement of this workstation
running this code, not an output of the model, so it is `measured:` and leaves
through `new_facts` for the librarian to enter (4.3.2, P14) -- the loop the gap
opened, closed. It is the first `new_facts` entry any result card here carries.

The machinery -- reading the four files, resolving the plan by the revision the
run carried and checking its hash, `met` computed with the operator's own
comparators in SI, deviations as exact reproduction -- is `result_card`'s,
imported rather than copied.
"""

from __future__ import annotations

import json
import math
import sys

from . import cards, operator, result_card
from .config_bd_overdamped_trapped_uniform_flow import _one, round_to_sig
from .result_card import (RUNS, Unwritable, assumptions_for, carried, deviation, kb_refs_for,
                          outcome_of, plan_of, read_run, reading, targets_from, threshold_si,
                          time_base, unevaluated)

CONFIG = "bd_overdamped_trapped_uniform_flow"

# criterion id -> the reading it is evaluated on
OBSERVED = {
    "step_displacement_diverged": "max_step_displacement",
    "statistics_met": "relative_block_standard_error_of_drag_offset",
    "recovered_stiffness_within_target": "relative_deviation_of_stiffness_recovered_through_drag",
}


def evaluate(plan: dict, by_name: dict, meta: dict, targets: list[dict]) -> list[dict]:
    """Every stop and success criterion the plan declares, with the plan's own comparator."""
    out = []
    for kind, key in (("stop", "stop_criteria"), ("success", "success_criteria")):
        for cr in plan.get(key) or []:
            cid = cr["id"]
            if cid not in OBSERVED:
                raise Unwritable(f"the plan declares criterion {cid!r} and this module has no reading for it; "
                                 "a criterion silently missing reads as one that was met")
            name = OBSERVED[cid]
            if name not in by_name:
                out.append(unevaluated(cid, kind, None, f"the run record carries no value for {cr.get('metric')!r}"))
                continue
            threshold = threshold_si(cr, plan, by_name, targets)
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
    if (plan.get("system_configuration") or {}).get("config") != CONFIG:
        raise Unwritable(f"{run_id} ran {plan.get('system_configuration')!r}; this module writes cards for {CONFIG}")
    if run["config"].get("plan_hash") != operator.plan_hash(plan):
        raise Unwritable(f"{plan_path.name} has changed since {run_id} read it; a result cites the plan that ran")
    qid = run["config"]["qid"]
    obs, meta, log = run["observables"], run["meta"], run["log"]
    drag, stiff = obs.get("drag_offset"), obs.get("recovered_stiffness")
    if not drag or drag.get("standard_error_block_si") is None or math.isnan(drag["standard_error_block_si"]):
        raise Unwritable(f"{run_id} carries no block standard error for the offset; this module does not "
                         "fall back to an error bar that was not read off the trace (result_card, task 006)")

    cond = {c["parameter"]: c["number"] for c in plan["conditions"]}
    # A grid plan holds the conditions every cell shares at the top and the
    # rest in the cell's own point; the run records which cell it was.
    cell = run["config"].get("compare_arm")
    if plan.get("sweep"):
        if cell is None:
            raise Unwritable(f"{run_id} ran a grid plan without naming its cell")
        point = next(p for p in plan["sweep"]["points"] if p["point"] == cell)
        cond.update({c["parameter"]: c["number"] for c in point["conditions"]})
    numbers: list[dict] = []

    def carry(src):
        n = carried(plan, plan_path, src)
        numbers.append(n)
        return n

    temperature = carry(cond["temperature"]); viscosity = carry(cond["viscosity"])
    bead = carry(cond["bead_diameter"]); k_t = carry(cond["trap_stiffness"])
    v = carry(cond["flow_speed"]); dt_p = carry(cond["integration_timestep"])
    save_p = carry(cond["save_interval"]); startup_p = carry(cond["startup_discard"])
    record_p = carry(cond["record_length"]); offset_p = carry(cond["offset_over_sigma"])
    carry("target_relative_error")
    model_inputs = [temperature, viscosity, bead, k_t, v, dt_p, save_p, startup_p, record_p]
    g = {n["name"]: n["grade"] for n in numbers}

    # -- what the MODEL predicts, from the plan's own numbers: the card's claim --
    kT = 1.380649e-23 * operator.si(temperature)
    gamma = 3 * math.pi * operator.si(viscosity) * operator.si(bead)
    k_si, v_si, rec_si = operator.si(k_t), operator.si(v), operator.si(record_p)
    offset_pred = gamma * v_si / k_si
    se_pred = math.sqrt(kT / k_si) * math.sqrt(2 * (gamma / k_si) / rec_si)
    p_off = cards.num(
        "drag_offset_predicted", _one(offset_pred * 1e6), "um", "computed:stokes_drag_over_stiffness",
        formula=f"3*pi*viscosity*bead_diameter*{v['name']}/{k_t['name']}",
        inputs=[(n, g[n]) for n in ("viscosity", "bead_diameter", v["name"], k_t["name"])],
        precision="order_of_magnitude",
        note="gamma*v/k_t from the plan's inputs: the steady offset the model predicts. ONE FIGURE because "
             "the sweep corners it stands on are declared order_of_magnitude, although the model realises "
             "them exactly. The comparison that carries precision is not this number but the recovered-over-"
             "declared ratio in criteria_evaluation, which is a ratio and so is set by the run")
    p_se = cards.num(
        "drag_offset_standard_error_predicted", _one(se_pred * 1e6), "um", "computed:ou_standard_error_of_the_mean",
        formula=f"(k_B*temperature/{k_t['name']})**0.5*(2*3*pi*viscosity*bead_diameter/({k_t['name']}*{record_p['name']}))**0.5",
        inputs=[(n, g[n]) for n in ("temperature", k_t["name"], "viscosity", "bead_diameter", record_p["name"])],
        precision="order_of_magnitude",
        note="sigma*sqrt(2*tau/T) at the declared record: the sampling error the OU model predicts for the "
             "mean. This is the claim the question is about, because the stiffness cancels out of it")
    numbers += [p_off, p_se]

    # -- what the RUN read: comparison terms only, each named by a field -------
    def read(name, value_si, unit, inputs, note):
        n = reading(name, value_si, unit, run_id, inputs, note)
        numbers.append(n)
        return n

    read("max_step_displacement", meta.get("max_single_step_displacement"), "um", model_inputs,
         "the largest single-step displacement, which the divergence criterion watches against the bead diameter")
    read("relative_block_standard_error_of_drag_offset",
         drag["standard_error_block_si"] / drag["value_si"], "1", model_inputs,
         f"the block standard error of the mean offset over the offset, from {drag['block_count']} blocks of "
         "ten declared relaxation times. statistics_met compares it against the person's target")
    read("relative_deviation_of_stiffness_recovered_through_drag", abs(stiff["from_drag_ratio"] - 1.0), "1",
         model_inputs,
         "|gamma*v/<x> over the declared stiffness, minus one|. NOT EVIDENCE ABOUT ANY TRAP: gamma and k_t "
         "both went in. It tests the integrator and the estimator, and the run read it at "
         f"{stiff['from_drag_ratio']:.4f} of the declared value")
    steps, sim_time, frames = meta.get("steps_taken"), meta.get("simulated_time"), meta.get("frames_saved")
    dt_a = read("integration_timestep_actual", sim_time / steps, dt_p["unit"], [dt_p],
                "simulated time over the integer step count")
    save_a = read("save_interval_actual", sim_time / (frames - 1), save_p["unit"], [save_p],
                  "simulated time over the number of intervals between saved frames")
    record_a = read("record_length_actual", drag["record_length_s"], record_p["unit"], [record_p, startup_p],
                    "the span of frames the estimator averaged, after startup_discard")
    pre = next(e["report"] for e in log["events"] if e["event"] == "preflight")
    offset_a = read("offset_over_sigma_realised", pre["realised_offset_over_sigma"], "1", [k_t, v, temperature],
                    "the steady offset in thermal widths that the dispatched speed actually produces. The plan's "
                    "axis LABELS the cell ten; the speed was derived from that label at one significant figure, "
                    "and one figure of 19.09 um/s is 20")

    targets = targets_from(plan, qid)
    by_name = {n["name"]: n for n in numbers}
    criteria = evaluate(plan, by_name, meta, targets)
    deviations = [d for d in (deviation("integration_timestep", dt_p, dt_a),
                              deviation("save_interval", save_p, save_a),
                              deviation("record_length", record_p, record_a)) if d is not None]
    deviations.append({
        "parameter": "offset_over_sigma", "planned_number": offset_p["name"], "actual_number": offset_a["name"],
        "within_tolerance": operator.si(offset_p) == operator.si(offset_a),
        "note": ("the one parameter the run did not reproduce exactly, and it is not an error: the offset level "
                 "names the cell and the speed that realises it was rounded to one figure. Reported as a "
                 "deviation because no tolerance is declared, so anything other than exact is a person's to "
                 "read (result_card)"),
    })

    # -- the fact this run returns: its own cost ------------------------------
    # Phrased from the backend the RUN recorded, not from the one the plan
    # names. The plan was written against trap_backend and runs unchanged on
    # trap_hoomd_backend (4.6.5's definition of reproducibility), so the plan
    # cannot say which engine a given run's cost belongs to and the run can.
    backend = run["config"].get("backend")
    ENGINES = {
        "trap_backend": ("the trap_backend integrator -- NumPy, Euler-Maruyama, a Python loop over steps",
                         "NOT HOOMD"),
        "trap_hoomd_backend": ("the trap_hoomd_backend integrator -- HOOMD-blue 7.2.0 on the CPU, its Brownian "
                               "method, the trap as a harmonic bond to a tether outside the integration filter",
                               "NOT the NumPy mock, whose figure is measured separately"),
    }
    if backend not in ENGINES:
        raise Unwritable(f"{run_id} ran on {backend!r}, which this module cannot describe a cost for")
    engine_text, not_text = ENGINES[backend]
    cost = obs.get("cost") or {}
    new_facts, cost_n = [], None
    if cost.get("wall_s_per_step"):
        cost_n = cards.num(
            "cost_per_step_measured", float(f"{round_to_sig(cost['wall_s_per_step'], 2):g}"), "s", f"measured:{run_id}",
            precision="significant_figures",
            note=f"{cost['integration_wall_s']:.3f} s over {cost['steps']} steps of the integration loop alone, "
                 f"on {backend}, excluding process start and polling. A measurement of this workstation running "
                 "this code, which is why it is `measured:` while the offset is not")
        numbers.append(cost_n)
        per_step_us = cost["wall_s_per_step"] * 1e6
        new_facts.append({
            "claim": f"On this workstation {engine_text} costs about {per_step_us:.1g} microseconds of wall clock "
                     "per integration step, for one overdamped sphere in a harmonic trap under uniform flow.",
            "numbers": ["cost_per_step_measured"],
            "validity_conditions": (
                f"{backend} as committed at the time of {run_id}, one particle, three coordinates, a save every "
                f"twenty steps, measured on 2026-09-23 over one run of {cost['steps']} steps while other sessions "
                f"shared the machine. {not_text}, and not a cost per particle-step for N above one: the "
                "1000-particle hoomd_backend run run-20260922-hoomd-s3 cost 4 ms a step and 4 us a particle-step, "
                "and the figures do not interpolate. It answers the gap A5 found as "
                "cost_per_particle_step_overdamped_absent for this backend only."),
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
        "values": [{"metric": plan["observable"]["name"], "number": p_off["name"], "uncertainty": p_se["name"]}],
        "criteria_evaluation": criteria, "deviations": deviations,
        "time_base": time_base(log), "targets": targets,
        "estimation": {
            "vocabulary_version": result_card.vocabulary_version(), "followed": True,
            "note": ("the registered estimator: the mean along-flow displacement from the DECLARED trap centre, "
                     "over the declared record_length after startup_discard. The block standard error and the "
                     "second route to the stiffness ride on the same trace and are not the estimator"),
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
