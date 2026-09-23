"""S4 for the active questions (plan.md 4.5.4): intersect, choose, refuse in numbers.

`synthesis.py` owns the deterministic half -- `intersect`, `carry_from`,
`assumptions_for`, `kb_refs_for` -- and a judgement table keyed by
configuration that is `bd_overdamped`'s. This module reuses the first half
and supplies the judgement for `sim-20260923-041` and `-042`, whose axis
cards come from `axes_abp`.

Three things S4 decides here that the table could not:

* **Which configuration.** Both `abp_free` and `abp_wca_2d` survive S3.0 and
  neither intersection is empty. The person ruled WCA on 2026-09-23, so
  `abp_free` is rejected on that ruling and the rejection is recorded with
  the number that exists only because of it, `wca_epsilon`.

* **The point, from the intervals.** The step a decade under A1's ceiling;
  the window at A4's floor; the record at whatever A2's ratio makes the
  window require, which is above A2's own floor -- an intersection the
  per-parameter code cannot see because the two bounds sit on different
  parameters. The middle box arm is the geometric mean of the two the goal
  named, since a compare in decades has its arms a decade apart.

* **The products against A5.** A5 constrains particle-steps and stored
  coordinates, which no other axis bounds, so `intersect` finds no conflict
  there. This module evaluates both products per arm at the chosen point and
  drops an arm that exceeds either, naming the two numbers that collide.
  That is the refusal 4.2 expects to be the common one on this side, and it
  is written as a refusal card beside the synthesis, not as prose.

No new facts and no lookups (4.5.4 rule 4): every number is carried with an
`origin` or computed from ones that are.
"""

from __future__ import annotations

import json
import math
import sys

from . import cards, synthesis

WCA = "abp_wca_2d"
FREE = "abp_free"


def _n(name, value, unit, source, formula, inputs, grades, note):
    return cards.num(name, value, unit, source, formula=formula,
                     inputs=[(i, grades[i]) for i in inputs], precision="order_of_magnitude", note=note)


def _val(numbers, name):
    return next(float(n["value"]) for n in numbers if n["name"] == name)


def build_042(qid: str, configs: list[str], created_at: str, revision: int) -> tuple[dict, dict | None]:
    """The synthesis card and, when an arm is dropped, the S4 refusal card."""
    per_config = []
    for config in configs:
        group = synthesis.axis_cards(qid, config, revision)
        intersection, conflict = synthesis.intersect(group)
        entry = {"config": config, "empty": conflict is not None, "axis_files": [f for f, _ in group]}
        if conflict is not None:
            entry["conflict"] = conflict
        else:
            entry["intersection"] = intersection
        per_config.append(entry)
    if any(e["empty"] for e in per_config if e["config"] == WCA):
        raise SystemExit("abp_wca_2d came out empty; S4 ends in a refusal card, not a plan (P5)")

    goal = cards.load_goal(qid, revision)
    G = cards.artifact_name("goal.json", revision)
    A = lambda ax: cards.artifact_name(f"axis_{WCA}_{ax}.json", revision)
    wanted = [
        (G, "bead_diameter"), (G, "temperature"), (G, "viscosity"), (G, "translational_diffusivity"),
        (G, "rotational_diffusivity"), (G, "persistence_time_expected"), (G, "wca_epsilon"),
        (G, "peclet"), (G, "packing_fraction"), (G, "persistence_length_expected"),
        (G, "box_over_persistence_length_min"), (G, "box_over_persistence_length_max"),
        (A("a1"), "integration_timestep_max"),
        (A("a2"), "total_simulated_time_min"), (A("a2"), "lag_to_record_ratio_max"), (A("a2"), "target_relative_error"),
        (A("a3"), "box_length_smallest_arm"), (A("a3"), "box_length_largest_arm"), (A("a3"), "n_particles_largest_arm"),
        (A("a4"), "save_interval_max"), (A("a4"), "fit_lag_range_lower_bound_min"), (A("a4"), "max_lag_time_min"),
        (A("a5"), "particle_steps_max"), (A("a5"), "coordinates_stored_max"), (A("a5"), "particle_step_rate"),
        (A("a5"), "wall_clock_max"), (A("a5"), "storage_max"),
    ]
    numbers = synthesis.carry_from(qid, WCA, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)
    g = {n["name"]: n["grade"] for n in numbers}
    V = lambda name: _val(numbers, name)

    def add(name, value, unit, source, formula, inputs, note):
        n = _n(name, value, unit, source, formula, inputs, g, note)
        numbers.append(n); g[name] = n["grade"]
        return n

    from .axes_abp import oom
    dt = 0.1 * V("integration_timestep_max")
    add("integration_timestep_point", oom(dt, "s"), "s", "computed:decade_under_a1_ceiling",
        "integration_timestep_max/10", ["integration_timestep_max"],
        "S4's choice inside A1's interval: a decade under the ceiling, because the ceiling rests on a contact time estimated at the potential minimum and activity drives overlaps deeper. target_accuracy outranks cost in the goal's priority, and this is where that order is spent")
    lag_lo = V("fit_lag_range_lower_bound_min")
    add("fit_lag_range_lower_bound_point", oom(lag_lo, "s"), "s", "computed:a4_floor",
        "fit_lag_range_lower_bound_min", ["fit_lag_range_lower_bound_min"],
        "the window parameter of effective_translational_diffusivity, at A4's floor")
    lag_hi = V("max_lag_time_min")
    add("max_lag_time_point", oom(lag_hi, "s"), "s", "computed:a4_floor",
        "max_lag_time_min", ["max_lag_time_min"],
        "the window parameter of mean_squared_displacement, at A4's floor")
    T = lag_hi / V("lag_to_record_ratio_max")
    add("total_simulated_time_point", oom(T, "s"), "s", "computed:window_over_record_ratio",
        "max_lag_time_point/lag_to_record_ratio_max", ["max_lag_time_point", "lag_to_record_ratio_max"],
        "the record A2's ratio requires for A4's window: three times A2's own floor, which A2 set from its reference lag and not from the window. Two axes constrain the record and this is their intersection")
    add("lag_to_record_ratio", oom(lag_hi / T, "1"), "1", "computed:window_over_record",
        "max_lag_time_point/total_simulated_time_point", ["max_lag_time_point", "total_simulated_time_point"],
        "the window as a share of the record, at A2's ceiling by construction")
    save = V("save_interval_max")
    add("save_interval_point", oom(save, "s"), "s", "computed:a4_ceiling",
        "save_interval_max", ["save_interval_max"],
        "at A4's ceiling: saving more often costs storage and buys nothing the windows need")
    mid = math.sqrt(V("box_over_persistence_length_min") * V("box_over_persistence_length_max"))
    add("box_over_persistence_length_mid", oom(mid, "1"), "1", "computed:geometric_mean_of_arms",
        "(box_over_persistence_length_min*box_over_persistence_length_max)**0.5",
        ["box_over_persistence_length_min", "box_over_persistence_length_max"],
        "the middle arm: a compare in decades has its arms a decade apart, and the goal named the ends")
    lp = V("persistence_length_expected")
    add("box_length_arm_mid", oom(mid * lp * 1e-6, "um"), "um", "computed:arm_times_persistence_length",
        "box_over_persistence_length_mid*persistence_length_expected",
        ["box_over_persistence_length_mid", "persistence_length_expected"], "the middle arm's box")
    d = V("bead_diameter"); phi = V("packing_fraction")
    arms = {"small": V("box_length_smallest_arm"), "mid": mid * lp, "large": V("box_length_largest_arm")}
    box_name = {"small": "box_length_smallest_arm", "mid": "box_length_arm_mid", "large": "box_length_largest_arm"}
    n_name = {}
    for arm, L in arms.items():
        if arm == "large":
            n_name[arm] = "n_particles_largest_arm"
            continue
        N = 4 * phi * L * L / (math.pi * d * d)
        n_name[arm] = f"n_particles_arm_{arm}"
        add(n_name[arm], oom(N, "1"), "1", "computed:area_fraction_times_box",
            f"4*packing_fraction*{box_name[arm]}**2/(pi*bead_diameter**2)", ["packing_fraction", box_name[arm], "bead_diameter"],
            f"particles in the {arm} arm at the held packing fraction" + (". Of order ten: the smallest arm is a handful of particles, which is what one persistence length of box at this density holds, and A2's record floor is what carries its statistics" if arm == "small" else ""))
    dropped = []
    steps_cap = V("particle_steps_max"); coords_cap = V("coordinates_stored_max")
    for arm in arms:
        N = V(n_name[arm])
        steps = N * V("total_simulated_time_point") / V("integration_timestep_point")
        coords = 2 * N * V("total_simulated_time_point") / V("save_interval_point")
        add(f"particle_steps_arm_{arm}", oom(steps, "1"), "1", "computed:particles_times_steps",
            f"{n_name[arm]}*total_simulated_time_point/integration_timestep_point",
            [n_name[arm], "total_simulated_time_point", "integration_timestep_point"],
            f"the {arm} arm's cost in particle-steps, against A5's ceiling particle_steps_max")
        add(f"coordinates_stored_arm_{arm}", oom(coords, "1"), "1", "computed:two_coordinates_per_frame",
            f"2*{n_name[arm]}*total_simulated_time_point/save_interval_point",
            [n_name[arm], "total_simulated_time_point", "save_interval_point"],
            f"the {arm} arm's stored coordinates, against A5's ceiling coordinates_stored_max")
        over = []
        if oom(steps, "1") > steps_cap:
            over.append(("particle_steps", f"particle_steps_arm_{arm}", "particle_steps_max"))
        if oom(coords, "1") > coords_cap:
            over.append(("coordinates_stored", f"coordinates_stored_arm_{arm}", "coordinates_stored_max"))
        if over:
            dropped.append((arm, over))

    rejected = [{
        "what": f"configuration {FREE}",
        "kind": "configuration",
        "reason": "the person ruled on 2026-09-23 that the repulsion is WCA, so the system is interacting; the free configuration is the closed-form reference and belongs in the store, not in this run. Its intersection is not empty and its cards stand as the record of what a free arm would need",
        "grounds": ["wca_epsilon"],
    }]
    for arm, over in dropped:
        rejected.append({
            "what": f"box arm '{arm}' at {box_name[arm]}",
            "kind": "operating_point",
            "reason": "exceeds A5's ceiling on " + " and ".join(p for p, _, _ in over) + " at the chosen point; dropped with a counterexample in the S4 refusal card, and the compare keeps the arms that fit",
            "grounds": [x for _, a, b in over for x in (a, b)],
        })
    kept = [arm for arm in arms if arm not in {a for a, _ in dropped}]
    if len(kept) < 2:
        raise SystemExit("fewer than two arms fit the budget; the compare cannot be run (P5)")

    point = [
        ("integration_timestep", "integration_timestep_point"),
        ("total_simulated_time", "total_simulated_time_point"),
        ("save_interval", "save_interval_point"),
        ("max_lag_time", "max_lag_time_point"),
        ("fit_lag_range_lower_bound", "fit_lag_range_lower_bound_point"),
        ("peclet_number_steric", "peclet"),
        ("packing_fraction", "packing_fraction"),
    ]
    card = cards.head(
        "synthesis", f"synthesis-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, configs_screened=configs, per_config=per_config, chosen_config=WCA,
        operating_point=[{"parameter": p, "number": n} for p, n in point],
        priority_used=goal["priority"], priority_source="goal_card", rejected=rejected,
        tie_break="no same-decade tie: abp_free is rejected on the person's ruling, the large arm on A5's ceilings, and the arms kept are " + ", ".join(kept) + " -- the box is the compare variable and every other condition is held across them (check 34). S4 made no lookup, so the librarian is degraded here by construction and the gaps are the goal's",
    )
    card.update(cards.tail(numbers, assumptions=assumptions,
                           kb_refs=synthesis.kb_refs_for(qid, numbers), kb_gaps=synthesis.kb_gaps_for(qid),
                           degraded=["librarian_agent"]))

    refusal = None
    if dropped:
        counter = []
        for arm, over in dropped:
            for param, need, cap in over:
                counter.append({"parameter": param, "required_number": need, "limit_number": cap,
                                "statement": f"the {arm} arm needs {need} = {_val(numbers, need):g} against {cap} = {_val(numbers, cap):g}, at the step, record and save interval the intersection allows; the save interval is already at A4's ceiling and the step a decade under A1's, so no settable parameter inside the intervals brings this arm under the ceiling"})
        refusal = cards.head("refusal", f"refusal-{qid}-s4" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
                             revision=revision, status="REFUSED", stage="S4",
                             refused_what=f"box arm(s) {', '.join(a for a, _ in dropped)} of the compare over box_size: the box at {V('box_over_persistence_length_max'):g} persistence lengths at the held packing fraction",
                             reason_code="budget_exceeded", counterexample=counter,
                             alternatives=[{
                                 "what": "raise the local ceilings, or add an execution target with a larger disk and wall clock, by the factors the counterexample states; the arm then runs unchanged",
                                 "requires": "a person's edit to simulation_agent/envelope/budget.json -- a ceiling is a decision and this agent does not raise its own",
                             }, {
                                 "what": "store a subsample of the particles' coordinates rather than all of them, which lowers coordinates_stored without touching the physics; the wall-clock excess needs the first alternative regardless",
                                 "requires": "a revision that declares the subsample as a condition, because the MSD estimator's particle average then reads a declared subset",
                             }])
        keep = {x for _, over in dropped for _, a, b in over for x in (a, b)}
        syn_name = cards.artifact_name("synthesis.json", revision)
        carried = []
        for n in numbers:
            if n["name"] not in keep:
                continue
            c = {k: n[k] for k in ("name", "value", "unit", "source", "grade") }
            c["origin"] = n.get("origin") or f"{syn_name}#{n['name']}"
            for k in ("precision", "note"):
                if k in n:
                    c[k] = n[k]
            carried.append(c)
        refusal.update(cards.tail(carried))
    return card, refusal


if __name__ == "__main__":
    qid, created_at = sys.argv[1], sys.argv[2]
    revision = cards.question_revision(qid)
    configs = [FREE, WCA]
    card, refusal = build_042(qid, configs, created_at, revision)
    d = cards.question_dir(qid)
    p = d / cards.artifact_name("synthesis.json", revision)
    cards.refuse_overwrite(p, revision, card); cards.write(p, card); print(p.name)
    if refusal is not None:
        r = d / cards.artifact_name(f"refusal_s4_{qid}.json", revision)
        cards.refuse_overwrite(r, revision, refusal); cards.write(r, refusal); print(r.name)
