"""The result card for one run of `bd_overdamped_gaussian_double_well_2d` (plan.md 5.1, 4.6 O4).

    cd simulation_agent && python -m src.result_double_well <run_id> [--ask <run_id> ...]

The configuration declares `output_independent_of_input: true` -- the escape
rate over a few-kT saddle in this 2-D landscape has no safe closed form -- so
`values[]` carries what the run READ: the ensemble mean of each observable
over records and, as its uncertainty, the spread ONE record shows (the
standard deviation over records), because the bench has one bead and one
record and that spread is what its single value is compared against. The
capability entry's caveat is kept in the notes: the occupancy and the barrier
are fixed by the potential in the long-record limit, so for those two the run
establishes what a finite record returns, not the potential.

**`--ask` makes this card the payload of the round to the experiment** (task
024 stage 5). It adds, from the other points of the same revision, the same
readings under their own run ids, and the bench request as numbers whose notes
say, in words, that they are TARGETS and not predictions -- the bridge's
interim convention while no structured range slot exists (bridge gap G9). The
request's three parts with no schema field -- return the calibrated values,
the tolerances, tune in situ by the histogram -- are prose in `estimation.note`
and in those numbers' notes; nothing is invented as a field.
"""

from __future__ import annotations

import argparse
import math

from . import cards, operator, result_card
from .config_bd_overdamped_gaussian_double_well_2d import _one
from .result_card import (Unwritable, assumptions_for, carried, deviation, kb_refs_for, outcome_of, plan_of,
                          read_run, reading, targets_from, time_base, unevaluated)

CONFIG = "bd_overdamped_gaussian_double_well_2d"


def _read_point(run_id: str, tag: str, numbers: list, inputs: list, values: list, primary: bool) -> dict:
    """The four observables of one run as readings, named by values[] entries."""
    run = read_run(run_id)
    o = run["observables"]
    sfx = "" if primary else f"_{tag}"

    def rd(name, v, unit, note):
        n = reading(name + sfx, v, unit, run_id, inputs, note)
        numbers.append(n)
        return n

    occ, r12 = o["well_occupancy"], o["interwell_transition_rate"]["well_1_to_2"]
    r21 = o["interwell_transition_rate"]["well_2_to_1"]
    hop = o["interwell_transition_rate"]["hop_frequency_both_directions"]
    res = o["well_residence_time"]
    bar = o["interwell_barrier_height"]
    records = occ["n_records"]
    got = {}
    got["occ"] = rd("well_occupancy_mean", occ["mean"], "1",
                    f"well 1's occupancy, the mean over {records} independent records of {run_id}")
    got["occ_sd"] = rd("well_occupancy_one_record_spread", occ["sd_over_records"], "1",
                       f"the standard deviation over records: what ONE record's occupancy scatters by. 5th-95th "
                       f"percentile over records {occ['p05']:.2f}-{occ['p95']:.2f}")
    got["r12"] = rd("transition_rate_1_to_2_mean", r12["mean"], "1/s",
                    "the registered rate out of well 1: transitions out over the time assigned to well 1, mean over "
                    f"records; one record's 5th-95th percentile {r12['p05']:.3g}-{r12['p95']:.3g} /s")
    got["r12_sd"] = rd("transition_rate_1_to_2_one_record_spread", r12["sd_over_records"], "1/s",
                       "the standard deviation of that rate over records")
    got["r21"] = rd("transition_rate_2_to_1_mean", r21["mean"], "1/s",
                    f"the same out of well 2; one record's 5th-95th percentile {r21['p05']:.3g}-{r21['p95']:.3g} /s")
    got["r21_sd"] = rd("transition_rate_2_to_1_one_record_spread", r21["sd_over_records"], "1/s",
                       "the standard deviation of that rate over records")
    got["hop_h"] = rd("hops_per_hour_mean", hop["mean"] * 3600, "1",
                      "all transitions, both directions, over the record, per hour: for planning a record, not the "
                      "registered observable")
    got["res1"] = rd("residence_time_well_1_mean", res["well_1"]["mean"], "s",
                     "the registered residence in well 1: time assigned to well 1 over the exits from it (the renewal "
                     "form), per record and averaged over records. One "
                     f"record's 5th-95th percentile {res['well_1']['p05']:.3g}-{res['well_1']['p95']:.3g} s")
    got["res1_sd"] = rd("residence_time_well_1_one_record_spread", res["well_1"]["sd_over_records"], "s",
                        "the standard deviation of that per-record mean over records")
    got["bar"] = rd("barrier_projected_pooled", bar["projected_free_energy_kT"], "kT",
                    "k_B*T at the card's temperature: -ln of the projected histogram pooled over all records, saddle minus the "
                    f"deeper peak. The potential's own barrier, computed, is {bar['potential_computed_kT']:.2f}")
    for metric, n, u in (("well_occupancy", got["occ"], got["occ_sd"]),
                         ("interwell_transition_rate", got["r12"], got["r12_sd"]),
                         ("interwell_transition_rate", got["r21"], got["r21_sd"]),
                         ("well_residence_time", got["res1"], got["res1_sd"]),
                         ("interwell_barrier_height", got["bar"], None)):
        values.append({"metric": metric, "number": n["name"], "uncertainty": u["name"] if u else None})
    values.append({"metric": "interwell_transition_rate", "number": got["hop_h"]["name"], "uncertainty": None})
    got["run"], got["obs"] = run, o
    return got


def build(run_id: str, ask: list[str] | None = None) -> dict:
    run = read_run(run_id)
    plan, plan_path = plan_of(run)
    if (plan.get("system_configuration") or {}).get("config") != CONFIG:
        raise Unwritable(f"{run_id} ran {plan.get('system_configuration')!r}; this module writes cards for {CONFIG}")
    if run["config"].get("plan_hash") != operator.plan_hash(plan):
        raise Unwritable(f"{plan_path.name} has changed since {run_id} read it; a result cites the plan that ran")
    qid = run["config"]["qid"]
    meta, log = run["meta"], run["log"]
    cond = {c["parameter"]: c["number"] for c in plan["conditions"]}
    cell = run["config"].get("compare_arm")
    if plan.get("sweep"):
        if cell is None:
            raise Unwritable(f"{run_id} ran a sweep plan without naming its point")
        point = next(p for p in plan["sweep"]["points"] if p["point"] == cell)
        cond.update({c["parameter"]: c["number"] for c in point["conditions"]})
    numbers: list[dict] = []

    def carry(src):
        if any(n["name"] == src for n in numbers):
            return next(n for n in numbers if n["name"] == src)
        n = carried(plan, plan_path, src)
        numbers.append(n)
        return n

    model = [carry(cond[p]) for p in ("temperature", "viscosity", "bead_diameter", "trap_stiffness_1",
                                      "trap_stiffness_2", "trap_width_1", "trap_width_2", "barrier_target",
                                      "integration_timestep", "save_interval", "startup_discard", "record_length",
                                      "walkers", "milestone_core_fraction")]
    if "depth_difference" in cond:
        model.append(carry(cond["depth_difference"]))
    for cr in (plan.get("success_criteria") or []) + (plan.get("stop_criteria") or []):
        if cr.get("number"):
            carry(cr["number"])
    by = {n["name"]: n for n in numbers}
    dt_p, save_p, rec_p, start_p = (by[cond[k]] for k in ("integration_timestep", "save_interval",
                                                         "record_length", "startup_discard"))

    values: list[dict] = []
    main = _read_point(run_id, cell or "", numbers, model, values, primary=True)
    o = main["obs"]
    step = reading("max_step_displacement", meta.get("max_single_step_displacement"), "m", run_id, model,
                   "the largest single-step displacement, which the divergence criterion watches against the box")
    hops_med = reading("hops_per_record_median", o["interwell_transition_rate"]["transitions_per_record"]["p50"],
                       "1", run_id, model, "the median over records of the transitions in one record")
    steps, sim_time, frames = meta.get("steps_taken"), meta.get("simulated_time"), meta.get("frames_saved")
    dt_a = reading("integration_timestep_actual", sim_time / steps, dt_p["unit"], run_id, [dt_p],
                   "simulated time over the integer step count")
    save_a = reading("save_interval_actual", sim_time / (frames - 1), save_p["unit"], run_id, [save_p],
                     "simulated time over the intervals between saved frames")
    rec_a = reading("record_length_actual", sim_time - operator.si(start_p), rec_p["unit"], run_id, [rec_p, start_p],
                    "simulated time after the startup discard")
    numbers += [step, hops_med, dt_a, save_a, rec_a]
    pre = next(e["report"] for e in log["events"] if e["event"] == "preflight")
    sep_m = pre["engine_parameters"]["separation_m_solved_from_barrier"]

    criteria = []
    for kind, key in (("stop", "stop_criteria"), ("success", "success_criteria")):
        for cr in plan.get(key) or []:
            cid = cr["id"]
            if cid == "step_displacement_diverged":
                met = operator.COMPARATORS[cr["comparator"]](operator.si(step), operator.si(by[cr["number"]]))
                criteria.append({"id": cid, "kind": kind, "met": met, "observed_number": step["name"]})
            elif cid == "hops_counted":
                met = operator.COMPARATORS[cr["comparator"]](operator.si(hops_med), operator.si(by[cr["number"]]))
                criteria.append({"id": cid, "kind": kind, "met": met, "observed_number": hops_med["name"]})
            elif cid == "occupancy_symmetric":
                criteria.append(unevaluated(cid, kind, main["occ"]["name"],
                    "the criterion names a decade-resolution target as its threshold, which is not an occupancy; "
                    "it was written ill-posed and is not evaluated after the run. The mean occupancy and its spread "
                    "are the card's values"))
            else:
                raise Unwritable(f"the plan declares criterion {cid!r} and this module has no reading for it")
    deviations = [d for d in (deviation("integration_timestep", dt_p, dt_a), deviation("save_interval", save_p, save_a),
                              deviation("record_length", rec_p, rec_a)) if d is not None]

    note = ("the registered estimators, applied to each record's trajectory projected on the line joining the traps: "
            "cores around the two histogram peaks of the pooled record, radius the plan's fraction of their spacing, "
            "sticky milestoning at the frame interval; occupancy as time assigned to well 1; each ordered rate as "
            "transitions out of a well over the time assigned to it; residence as time assigned to a well over the "
            "exits from it. The barrier is in kT at the temperature on this card; the plan's barrier_target stays a "
            "plain number in units of k_B*T because the operator converts every plan value to SI and kT has no "
            "fixed SI factor without a temperature. "
            f"Trap 1 is at negative x and +x points from trap 1 to trap 2; the separation the engine solved from the "
            f"barrier is {sep_m * 1e6:.3f} um.")
    assumptions = assumptions_for(plan, numbers)
    if ask:
        others = [(rid, read_run(rid)["config"].get("compare_arm")) for rid in ask]
        for rid, tag in others:
            _read_point(rid, tag, numbers, model, values, primary=False)
        _bench_request(numbers, by, assumptions)
        note = ("THIS CARD IS THE ASK TO THE EXPERIMENT. What the simulation found, in plain words, from a thousand "
                "independent ten-minute records a point: (1) one ten-minute record fixes the barrier to a few "
                "hundredths of k_B*T, but the occupancy only to about plus or minus 0.2 and the rate only to about a "
                "factor of two; a record of about half an hour halves that spread. (2) Making well 2 one k_B*T "
                "shallower moves the mean occupancy from 0.50 to 0.64, but a single ten-minute record cannot tell "
                "that from equal wells -- the two ranges overlap from 0.47 to 0.70 -- so an asymmetric run needs "
                "about an hour of record in total, as one long record or several short ones. (3) The frame interval "
                "does not matter between 10 and 50 ms: the bench is free to choose. (4) The two stiffnesses must "
                "match to within a few per cent at 1 pN/um and about forty per cent at 0.1 pN/um, and a ratio of "
                "0.5 or below gives no hops at all at any separation -- so soft, equal traps are the operating "
                "point. " + note)
        note += (" The tolerances and the separation sensitivity quoted here come from the map computed from the "
                 "potential, which is not on disk in this tree; it regenerates exactly with `cd simulation_agent && "
                 "python -m src.double_well_map <out.json>` from the commit that adds this card.")
        note += (" Its bench_* numbers are TARGETS for the bench, not "
                 "predictions, in the bridge's interim convention for ranges. What is asked, in words: (1) set both "
                 "traps to the same stiffness, in 0.1-1 pN/um, matched to within bench_stiffness_mismatch_max -- a "
                 "calibration cannot resolve a few per cent, so match them by watching the two histogram peaks "
                 "until the occupancy is one half; (2) bring the traps together until the projected histogram "
                 "shows two peaks with a barrier of bench_barrier_low to bench_barrier_high k_B*T between them -- "
                 "tune the separation by the histogram, not by a number, because the barrier moves by about half a "
                 "kT per ten nanometres at 1 pN/um; about 2.1 trap widths is where to start; (3) for the "
                 "asymmetric round, trim trap 2 until its well holds about a third of the time (one kT of depth); "
                 "(4) record bench_record_length at bench_frame_interval or finer, and state the exposure; (5) "
                 "RETURN, trap by trap, the calibrated stiffness and width, the separation as set, the diffusivity "
                 "measured in situ from the same record, and the temperature at the sample if it is read. The "
                 "simulation re-predicts at those values before the bridge compares, and that re-prediction is a "
                 "different card which opens a new thread pointing back to this one; the numbers on this card are "
                 "not the comparison. The round is gated on well_occupancy, which the bench reads straight off its "
                 "histogram; the other three observables ride on the card as numbers. One ten-minute record resolves the barrier; it resolves the occupancy and "
                 "the rate only to about a factor of two, which is the spread given beside each value.")

    outcome = outcome_of(meta)
    card = cards.head("result", f"result-{qid}-{run_id}", qid, log["finished_at"],
                      thread=plan.get("thread", f"solo-{qid}"), round=plan.get("round", 0), revision=1,
                      status="FAILED" if outcome == "FAILED" else "DONE")
    card.update({
        "plan_id": plan["id"], "plan_revision": plan["revision"], "plan_hash": run["config"]["plan_hash"],
        "approval_id": (run["config"].get("approval") or {}).get("id"), "run_id": run_id,
        "observable": cards.observable(plan["observable"]["name"]), "outcome": outcome,
        "values": values, "criteria_evaluation": criteria, "deviations": deviations,
        "time_base": time_base(log), "targets": targets_from(plan, qid),
        "estimation": {"vocabulary_version": result_card.vocabulary_version(), "followed": True, "note": note},
    })
    card.update(cards.tail(numbers, assumptions=assumptions, kb_refs=kb_refs_for(plan, numbers),
                           kb_gaps=list(plan.get("kb_gaps") or []), degraded=list(plan.get("degraded") or [])))
    return card


def _bench_request(numbers: list, by: dict, assumptions: list) -> None:
    g = {n["name"]: n["grade"] for n in numbers}
    t = lambda name, v, unit, note: numbers.append(cards.num(  # noqa: E731
        name, v, unit, "assumed:a_bench_request", precision="order_of_magnitude", note="TARGET, not a prediction: " + note))
    t("bench_stiffness_low", 1e-7, "N/m", "the soft end of the stiffness to hold each trap at, 0.1 pN/um")
    t("bench_stiffness_high", 1e-6, "N/m", "the stiff end, 1 pN/um; softer widens every tolerance")
    t("bench_barrier_low", 1, "1", "the least barrier worth calling two wells, in k_B*T")
    t("bench_barrier_high", 4, "1", "the most that still gives tens of hops an hour at 1 um width, in k_B*T")
    t("bench_record_length", 600, "s", "ten minutes at least; longer narrows the occupancy and the rate")
    t("bench_frame_interval", 0.01, "s", "10 ms or finer between frames")
    k1, w1, temp = (by[n] for n in ("trap_stiffness_1", "trap_width_1", "temperature"))
    numbers.append(cards.num(
        "bench_stiffness_mismatch_max", _one(10 / (operator.si(k1) * operator.si(w1) ** 2 / (1.380649e-23 * operator.si(temp)))),
        "1", "computed:depth_difference_bound",
        formula=f"10/({k1['name']}*{w1['name']}**2/(k_B*temperature))",
        inputs=[(k1["name"], g[k1["name"]]), (w1["name"], g[w1["name"]]), ("temperature", g["temperature"])],
        precision="order_of_magnitude",
        note="TARGET, not a prediction: the largest fractional difference between the two stiffnesses that still "
             "leaves a barrier under 10 kT from the deeper well -- the depth difference (1 - k2/k1)*eps is a lower "
             "bound on it. At 1 pN/um and 1 um width it is a few per cent (solved exactly from the potential: 5 per "
             "cent); at 0.1 pN/um about forty. A width mismatch costs the same at half the fraction"))
    assumptions.append({
        "rationale_id": "a_bench_request",
        "statement": "What the bench is asked to set, chosen from the map computed from the potential and the "
                     "ensembles run on it: soft, equal traps, a barrier of 1-4 kT, ten-minute records at 10 ms.",
        "numbers": ["bench_stiffness_low", "bench_stiffness_high", "bench_barrier_low", "bench_barrier_high",
                    "bench_record_length", "bench_frame_interval"],
        "falsifier": "the bench's calibrated values, returned, replace every one of them",
        "gap_ref": "trap_stiffness_absent"})


def emit(run_id: str, ask: list[str] | None = None):
    card = build(run_id, ask)
    path = result_card.path_for(card["qid"], run_id)
    cards.refuse_overwrite(path, card["revision"], card)
    return cards.write(path, card)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--ask", nargs="*")
    a = ap.parse_args()
    print(emit(a.run_id, a.ask).relative_to(cards.REPO))
