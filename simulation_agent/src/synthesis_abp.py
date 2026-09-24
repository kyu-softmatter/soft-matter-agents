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


# --------------------------------------------------------------------------- #
# 041 -- the sweep, evaluated per point
# --------------------------------------------------------------------------- #

PE_LEVELS = ("peclet_min", "peclet_mid", "peclet_max")
PHI_LEVELS = ("packing_fraction_min", "packing_fraction_mid", "packing_fraction_max")

# The person's rulings on a revision's S4 refusal, keyed by (qid, revision).
# A ruling is a decision and carries no grade; the goal of that revision
# records who ruled, when and why in constraint_notes, and this table is the
# one place the code reads it. 2026-09-23, on revision 3's refusal of the
# Pe 100 row: the dilute cell runs with the step AT A1's ceiling and a box
# of ONE persistence length -- the second resting on sim-20260923-042's
# measurement at Pe 10, applied at Pe 100 as an assumption the person chose.
RULINGS = {
    ("sim-20260923-041", 4): {"max_min": {"step_at_ceiling": True, "box_over_persistence_length": 1}},
}


def build_041(qid: str, configs: list[str], created_at: str, revision: int) -> tuple[dict, dict | None]:
    """S4 for a characterize over the (Peclet, packing fraction) grid.

    The axis cards state their bounds at the top corner of the sweep and mark
    which are functions of the Peclet number (`varies_with`). Intersecting
    those across the grid would combine claims about different points, so
    this evaluates them per point: the step bound is rescaled to each Peclet
    level by the ratio of that level's shortest time to the top corner's, the
    box by the ratio of persistence lengths, and the particle count follows
    from the box and the level's packing fraction. A5's two products are then
    formed per cell and a cell that exceeds either ceiling is SKIPPED, with
    the numbers, in the plan's `sweep.points[].skipped` and in the S4 refusal
    card. Nothing is new here: every number is carried or computed from
    carried ones, and the rescalings are arithmetic on the cards' own values.
    """
    per_config = []
    for config in configs:
        group = synthesis.axis_cards(qid, config, revision)
        intersection, conflict = synthesis.intersect(group)
        entry = {"config": config, "empty": conflict is not None, "axis_files": [f for f, _ in group]}
        entry["conflict" if conflict is not None else "intersection"] = conflict if conflict is not None else intersection
        per_config.append(entry)
    if any(e["empty"] for e in per_config if e["config"] == WCA):
        raise SystemExit("abp_wca_2d came out empty at the top corner; S4 ends in a refusal card, not a plan (P5)")

    goal = cards.load_goal(qid, revision)
    G = cards.artifact_name("goal.json", revision)
    A = lambda ax: cards.artifact_name(f"axis_{WCA}_{ax}.json", revision)
    wanted = [(G, n) for n in ("bead_diameter", "temperature", "viscosity", "translational_diffusivity",
                               "rotational_diffusivity", "persistence_time_expected", "wca_epsilon")]
    wanted += [(G, n) for n in PE_LEVELS + PHI_LEVELS]
    wanted += [(A("a1"), n) for n in ("integration_timestep_max", "shortest_resolved_time", "contact_relaxation_time", "active_step_time")]
    wanted += [(A("a2"), n) for n in ("total_simulated_time_min", "lag_to_record_ratio_max", "target_relative_error")]
    wanted += [(A("a3"), n) for n in ("box_length_min", "persistence_length_max")]
    wanted += [(A("a4"), n) for n in ("save_interval_max", "fit_lag_range_lower_bound_min", "max_lag_time_min")]
    wanted += [(A("a5"), n) for n in ("particle_steps_max", "coordinates_stored_max", "particle_step_rate", "wall_clock_max", "storage_max", "bytes_per_coordinate")]
    numbers = synthesis.carry_from(qid, WCA, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)
    g = {n["name"]: n["grade"] for n in numbers}
    V = lambda name: _val(numbers, name)
    from .axes_abp import oom

    def add(name, value, unit, source, formula, inputs, note):
        n = _n(name, value, unit, source, formula, inputs, g, note); numbers.append(n); g[name] = n["grade"]; return n

    # shared across the grid
    lag_hi = V("max_lag_time_min"); T = lag_hi / V("lag_to_record_ratio_max")
    add("fit_lag_range_lower_bound_point", oom(V("fit_lag_range_lower_bound_min"), "s"), "s", "computed:a4_floor", "fit_lag_range_lower_bound_min", ["fit_lag_range_lower_bound_min"], "constant over the grid: the persistence time does not move with Pe or phi")
    add("max_lag_time_point", oom(lag_hi, "s"), "s", "computed:a4_floor", "max_lag_time_min", ["max_lag_time_min"], "constant over the grid")
    add("total_simulated_time_point", oom(T, "s"), "s", "computed:window_over_record_ratio", "max_lag_time_point/lag_to_record_ratio_max", ["max_lag_time_point", "lag_to_record_ratio_max"], "the record A2's ratio requires for A4's window; constant over the grid")
    add("lag_to_record_ratio", oom(lag_hi / T, "1"), "1", "computed:window_over_record", "max_lag_time_point/total_simulated_time_point", ["max_lag_time_point", "total_simulated_time_point"], "at A2's ceiling by construction")
    add("save_interval_point", oom(V("save_interval_max"), "s"), "s", "computed:a4_ceiling", "save_interval_max", ["save_interval_max"], "constant over the grid")

    # per Peclet level: the step and the box are functions of Pe (varies_with)
    d_r = V("rotational_diffusivity"); short_top = V("shortest_resolved_time"); contact = V("contact_relaxation_time")
    dt_name, box_name = {}, {}
    for lvl in PE_LEVELS:
        pe = V(lvl); tag = lvl.split("_")[-1]
        t_active = 1.0 / (pe * d_r)
        add(f"active_step_time_pe_{tag}", oom(t_active, "s"), "s", "computed:diameter_over_speed",
            f"1/({lvl}*rotational_diffusivity)", [lvl, "rotational_diffusivity"],
            f"the time to self-propel one diameter at Pe = {pe:g}: d/(Pe*d*D_R)")
        shortest_lvl = min(t_active, contact); short_name = f"active_step_time_pe_{tag}" if t_active < contact else "contact_relaxation_time"
        dt_max = V("integration_timestep_max") * shortest_lvl / short_top
        add(f"integration_timestep_max_pe_{tag}", oom(dt_max, "s"), "s", "computed:a1_bound_rescaled_to_level",
            f"integration_timestep_max*{short_name}/shortest_resolved_time", ["integration_timestep_max", short_name, "shortest_resolved_time"],
            f"A1's ceiling evaluated at this Peclet level: the same resolution factor applied to the shortest time HERE ({short_name}), not to the top corner's. This is what varies_with buys")
        dt_name[lvl] = f"integration_timestep_point_pe_{tag}"
        add(dt_name[lvl], oom(dt_max / 10, "s"), "s", "computed:decade_under_a1_ceiling",
            f"integration_timestep_max_pe_{tag}/10", [f"integration_timestep_max_pe_{tag}"], "a decade under the level's ceiling, as for 042")
        box = V("box_length_min") * pe / V("peclet_max")
        box_name[lvl] = f"box_length_pe_{tag}"
        add(box_name[lvl], oom(box * 1e-6, "um"), "um", "computed:a3_bound_rescaled_to_level",
            f"box_length_min*{lvl}/peclet_max", ["box_length_min", lvl, "peclet_max"],
            f"A3's minimum box at this level: ten persistence lengths, and the persistence length is Pe*d")

    # per cell: particles, then A5's two products
    d = V("bead_diameter"); skipped = {}
    cells = []
    rulings = RULINGS.get((qid, revision), {})
    cell_dt, cell_box = {}, {}
    for tag, r in rulings.items():
        lvl = next(l for l in PE_LEVELS if tag.startswith(l.split("_")[-1] + "_"))
        lt = lvl.split("_")[-1]
        if r.get("step_at_ceiling"):
            cell_dt[tag] = f"integration_timestep_point_{tag}"
            add(cell_dt[tag], oom(V(f"integration_timestep_max_pe_{lt}"), "s"), "s", "computed:a1_ceiling_by_ruling",
                f"integration_timestep_max_pe_{lt}", [f"integration_timestep_max_pe_{lt}"],
                "the step AT A1's ceiling for this level, by the person's ruling of 2026-09-23: where the self-propulsion step binds, the bound is kinematic and carries no estimate, so the decade of margin the other cells take is not owed. The divergence monitor carries the risk the margin carried")
        if r.get("box_over_persistence_length"):
            k = r["box_over_persistence_length"]
            cell_box[tag] = f"box_length_{tag}"
            add(cell_box[tag], oom(V("box_length_min") * V(lvl) / V("peclet_max") / 10 * k * 1e-6, "um"), "um", "computed:persistence_lengths_by_ruling",
                f"box_length_min*{lvl}/peclet_max/10*{k}", ["box_length_min", lvl, "peclet_max"],
                f"{k} persistence length(s) of box at this level rather than A3's ten, by the person's ruling of 2026-09-23. Grounded in sim-20260923-042, where one and ten persistence lengths agreed to 3 per cent at Pe 10 and phi 0.1; at this Pe that agreement is ASSUMED, not measured, and this cell's result is the first test of it")
    for lvl in PE_LEVELS:
        for plv in PHI_LEVELS:
            tag = f"{lvl.split('_')[-1]}_{plv.split('_')[-1]}"
            L = V(cell_box.get(tag, box_name[lvl])); phi = V(plv)
            N = 4 * phi * L * L / (math.pi * d * d)
            bx = cell_box.get(tag, box_name[lvl]); dtn = cell_dt.get(tag, dt_name[lvl])
            add(f"n_particles_{tag}", oom(N, "1"), "1", "computed:area_fraction_times_box",
                f"4*{plv}*{bx}**2/(pi*bead_diameter**2)", [plv, bx, "bead_diameter"],
                f"particles in the cell Pe {V(lvl):g}, phi {phi:g}")
            steps = V(f"n_particles_{tag}") * V("total_simulated_time_point") / V(dtn)
            coords = 2 * V(f"n_particles_{tag}") * V("total_simulated_time_point") / V("save_interval_point")
            add(f"particle_steps_{tag}", oom(steps, "1"), "1", "computed:particles_times_steps",
                f"n_particles_{tag}*total_simulated_time_point/{dtn}", [f"n_particles_{tag}", "total_simulated_time_point", dtn],
                "the cell's cost in particle-steps against particle_steps_max")
            add(f"coordinates_stored_{tag}", oom(coords, "1"), "1", "computed:two_coordinates_per_frame",
                f"2*n_particles_{tag}*total_simulated_time_point/save_interval_point", [f"n_particles_{tag}", "total_simulated_time_point", "save_interval_point"],
                "the cell's stored coordinates against coordinates_stored_max")
            over = []
            if V(f"particle_steps_{tag}") > V("particle_steps_max"):
                over.append(("particle_steps", f"particle_steps_{tag}", "particle_steps_max"))
            if V(f"coordinates_stored_{tag}") > V("coordinates_stored_max"):
                over.append(("coordinates_stored", f"coordinates_stored_{tag}", "coordinates_stored_max"))
            cells.append((tag, lvl, plv, over))
            if over:
                skipped[tag] = over

    # The sparsest skipped cell at A1's CEILING rather than a decade under it:
    # where the self-propulsion step binds, the bound is kinematic and carries
    # no estimate, so the decade bought against the contact-time estimate is
    # not owed there. Recorded as a number so the refusal can offer it.
    at_ceiling = {}
    for tag, over in skipped.items():
        lvl = next(l for l in PE_LEVELS if tag.startswith(l.split("_")[-1] + "_"))
        steps = V(f"n_particles_{tag}") * V("total_simulated_time_point") / V(f"integration_timestep_max_pe_{lvl.split('_')[-1]}")
        name = f"particle_steps_{tag}_at_a1_ceiling"
        add(name, oom(steps, "1"), "1", "computed:particles_times_steps",
            f"n_particles_{tag}*total_simulated_time_point/integration_timestep_max_pe_{lvl.split('_')[-1]}",
            [f"n_particles_{tag}", "total_simulated_time_point", f"integration_timestep_max_pe_{lvl.split('_')[-1]}"],
            "the same cell with the step at A1's ceiling instead of a decade under it")
        if V(name) <= V("particle_steps_max") and all(p != "coordinates_stored" for p, _, _ in over):
            at_ceiling[tag] = name

    rejected = [{
        "what": f"configuration {FREE}", "kind": "configuration",
        "reason": "the person ruled on 2026-09-23 that the repulsion is WCA; the free configuration is the closed-form reference the interacting results are read against and belongs in the store, not in this run. Its cards stand as the record of what a free arm would need",
        "grounds": ["wca_epsilon"],
    }]
    for tag, over in skipped.items():
        rejected.append({"what": f"grid cell {tag}", "kind": "operating_point",
                         "reason": "exceeds A5's ceiling on " + " and ".join(p for p, _, _ in over) + " at the cell's own step and box; skipped, and the plan's sweep records the empty cell with this reason",
                         "grounds": [x for _, a, b in over for x in (a, b)]})
    if len(cells) - len(skipped) < 1:
        raise SystemExit("every cell exceeds the ceilings; the sweep cannot be run (P5)")

    card = cards.head("synthesis", f"synthesis-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
                      revision=revision, configs_screened=configs, per_config=per_config, chosen_config=WCA,
                      operating_point=[{"parameter": p, "number": n} for p, n in (
                          ("total_simulated_time", "total_simulated_time_point"), ("save_interval", "save_interval_point"),
                          ("max_lag_time", "max_lag_time_point"), ("fit_lag_range_lower_bound", "fit_lag_range_lower_bound_point"))],
                      priority_used=goal["priority"], priority_source="goal_card", rejected=rejected,
                      tie_break=(f"no same-decade tie. The grid is {len(cells)} cells; {len(cells) - len(skipped)} fit A5's ceilings at their own "
                                 f"step and box and {len(skipped)} do not ({', '.join(sorted(skipped)) or 'none'}). The step and the box are "
                                 "evaluated per Peclet level because A1 and A3 marked them varies_with peclet_number_steric; the record, "
                                 "the windows and the save interval are constant because A2 and A4 did not. S4 made no lookup, so the "
                                 "librarian is degraded here by construction and the gaps are the goal's"))
    card.update(cards.tail(numbers, assumptions=assumptions, kb_refs=synthesis.kb_refs_for(qid, numbers),
                           kb_gaps=synthesis.kb_gaps_for(qid), degraded=["librarian_agent"]))
    if rulings:
        card["tie_break"] += (". BY THE PERSON'S RULING (goal constraint_notes): " + "; ".join(
            f"cell {t} takes step {cell_dt.get(t, '(level default)')} and box {cell_box.get(t, '(level default)')}" for t in sorted(rulings)))

    refusal = None
    if skipped:
        counter = [{"parameter": p, "required_number": need, "limit_number": cap,
                    "statement": f"cell {tag} needs {need} = {_val(numbers, need):g} against {cap} = {_val(numbers, cap):g} at its own step and box; the save interval is at A4's ceiling and the step a decade under A1's for that level, so no settable parameter inside the intervals brings the cell under the ceiling"}
                   for tag, over in skipped.items() for p, need, cap in over]
        refusal = cards.head("refusal", f"refusal-{qid}-s4" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
                             revision=revision, status="REFUSED", stage="S4",
                             refused_what=f"grid cells {', '.join(sorted(skipped))} of the (Peclet, packing fraction) sweep: the dense, fast corner of the grid",
                             reason_code="budget_exceeded", counterexample=counter,
                             alternatives=[
                                 {"what": "raise the local ceilings, or add an execution target with more wall clock and disk, by the factors the counterexample states",
                                  "requires": "a person's edit to simulation_agent/envelope/budget.json"},
                             ] + ([{
                                 "what": "run " + ", ".join(sorted(at_ceiling)) + " with the step at A1's ceiling for that Peclet level rather than a decade under it: "
                                         + "; ".join(f"{tag} then costs {_val(numbers, n):g} particle-steps against {V('particle_steps_max'):g}" for tag, n in sorted(at_ceiling.items()))
                                         + ". Where the self-propulsion step binds the bound is kinematic and carries no estimate, so the margin bought against the contact-time estimate is not owed",
                                 "requires": "S4 choosing the ceiling for those cells, which is a decision inside the interval and needs no new number; the divergence monitor then carries the risk the margin carried",
                             }] if at_ceiling else []) + [
                                 {"what": "shrink the box at those cells below ten persistence lengths and accept that the image bound is then a measured question, which sim-20260923-042 is the instrument for",
                                  "requires": "042's result: if one persistence length of box already reproduces ten, A3's margin drops and these cells come under the ceiling by a hundred"},
                             ])
        keep = {x for over in skipped.values() for _, a, b in over for x in (a, b)}
        syn_name = cards.artifact_name("synthesis.json", revision)
        carried = []
        for n in numbers:
            if n["name"] in keep:
                c = {k: n[k] for k in ("name", "value", "unit", "source", "grade")}
                c["origin"] = n.get("origin") or f"{syn_name}#{n['name']}"
                for k in ("precision", "note"):
                    if k in n: c[k] = n[k]
                carried.append(c)
        refusal.update(cards.tail(carried))
    card["_cells"] = None  # placeholder removed below; kept out of the schema
    del card["_cells"]
    return card, refusal


if __name__ == "__main__":
    qid, created_at = sys.argv[1], sys.argv[2]
    revision = cards.question_revision(qid)
    configs = [FREE, WCA]
    builder = build_041 if qid.endswith("-041") else build_042
    card, refusal = builder(qid, configs, created_at, revision)
    d = cards.question_dir(qid)
    p = d / cards.artifact_name("synthesis.json", revision)
    cards.refuse_overwrite(p, revision, card); cards.write(p, card); print(p.name)
    if refusal is not None:
        r = d / cards.artifact_name(f"refusal_s4_{qid}.json", revision)
        cards.refuse_overwrite(r, revision, refusal); cards.write(r, refusal); print(r.name)
