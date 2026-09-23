"""S5 for sim-20260923-042: the compare over box size, as a plan and its Markdown twin.

`plan_card.py` is bd_overdamped's -- its criteria compare a fitted diffusivity
against Stokes-Einstein and its prose is about the free regime. This module
assembles the plan for the active compare from `v2_synthesis.json` the same
way: every number carried with an `origin`, criteria declared before the run,
the envelope check run rather than written, the Markdown generated from the
JSON (P3). What differs is the shape a compare needs and this observable's
windows:

* **`compare_arms`** hold the one condition that differs, `box_length`.
  The particle count differs too, but as a consequence of the held packing
  fraction and not as a choice, so it is carried in numbers[] for the record
  and the backend derives it -- check 34 would otherwise read it as a second
  compared variable, which it is not.

* **Three windows are conditions**, one per registered observable the run
  reads: `max_lag_time` for the MSD curve (check 40), the lower bound of the
  fit range for the effective diffusivity, and the save interval that
  resolves the crossover. `dynamical_crossover_time` needs a slope threshold
  no card carries, so it is not read by this plan and the open risks say so.

* **The success criteria are the compare's**: the two arms agree within the
  goal's decade, or they do not, and either is a result about the box.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import cards, synthesis, plan_card
from .axes_abp import oom

WCA = "abp_wca_2d"
MODEL = ("interacting active Brownian dynamics in two dimensions: one orientation per particle "
         "diffusing at D_R, self-propulsion v0 along it, translational noise D_T, WCA pair "
         "repulsion, periodic box, undriven")


def build(qid: str, created_at: str, revision: int) -> dict:
    goal = cards.load_goal(qid, revision)
    syn_name = cards.artifact_name("synthesis.json", revision)
    syn = __import__("json").loads((cards.question_dir(qid) / syn_name).read_text())
    A5 = cards.artifact_name(f"axis_{WCA}_a5.json", revision)

    shared = ["temperature", "viscosity", "bead_diameter", "translational_diffusivity",
              "rotational_diffusivity", "wca_epsilon", "peclet", "packing_fraction",
              "integration_timestep_point", "total_simulated_time_point", "save_interval_point",
              "max_lag_time_point", "fit_lag_range_lower_bound_point"]
    arms = {"small": ("box_length_smallest_arm", "n_particles_arm_small"),
            "mid": ("box_length_arm_mid", "n_particles_arm_mid")}
    wanted = [(syn_name, n) for n in shared]
    wanted += [(syn_name, n) for pair in arms.values() for n in pair]
    wanted += [(syn_name, n) for n in ("persistence_time_expected", "persistence_length_expected",
                                       "target_relative_error", "lag_to_record_ratio",
                                       "particle_step_rate", "particle_steps_max", "coordinates_stored_max",
                                       "box_length_largest_arm", "n_particles_largest_arm",
                                       "particle_steps_arm_large", "coordinates_stored_arm_large",
                                       "particle_steps_arm_small", "particle_steps_arm_mid",
                                       "coordinates_stored_arm_small", "coordinates_stored_arm_mid",
                                       "integration_timestep_max", "wall_clock_max", "storage_max")]
    wanted += [(A5, "bytes_per_coordinate")]
    numbers = synthesis.carry_from(qid, WCA, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)
    g = {n["name"]: n["grade"] for n in numbers}
    V = lambda name: next(float(n["value"]) for n in numbers if n["name"] == name)

    wall_s = (V("particle_steps_arm_small") + V("particle_steps_arm_mid")) / V("particle_step_rate")
    # In minutes and not hours: check 17 rounds in SI to one figure (600 s) and
    # check 28 wants one figure in the card's unit, and 600 s is 10 min but
    # 0.1667 h. The envelope check converts through si() either way.
    numbers.append(cards.num("wall_clock_estimate", oom(wall_s, "min"), "min", "computed:particle_steps_over_rate",
        formula="(particle_steps_arm_small+particle_steps_arm_mid)/particle_step_rate",
        inputs=[(n, g[n]) for n in ("particle_steps_arm_small", "particle_steps_arm_mid", "particle_step_rate")],
        precision="order_of_magnitude",
        note="both kept arms, one seed each, at the assumed rate; the number the envelope check compares against wall_clock_max. A5's rate is a guess until the smoke run measures it"))
    store_gb = (V("coordinates_stored_arm_small") + V("coordinates_stored_arm_mid")) * V("bytes_per_coordinate")
    numbers.append(cards.num("storage_estimate", oom(store_gb * 1e9, "GB"), "GB", "computed:coordinates_times_bytes",
        formula="(coordinates_stored_arm_small+coordinates_stored_arm_mid)*bytes_per_coordinate",
        inputs=[(n, g[n]) for n in ("coordinates_stored_arm_small", "coordinates_stored_arm_mid", "bytes_per_coordinate")],
        precision="order_of_magnitude",
        note="both kept arms' trajectories in double precision; compared against storage_max"))

    cond = lambda p, n: {"parameter": p, "number": n}
    conditions = [
        cond("temperature", "temperature"), cond("viscosity", "viscosity"), cond("bead_diameter", "bead_diameter"),
        cond("translational_diffusivity", "translational_diffusivity"), cond("rotational_diffusivity", "rotational_diffusivity"),
        cond("wca_epsilon", "wca_epsilon"), cond("peclet_number_steric", "peclet"), cond("packing_fraction", "packing_fraction"),
        cond("integration_timestep", "integration_timestep_point"), cond("total_simulated_time", "total_simulated_time_point"),
        cond("save_interval", "save_interval_point"), cond("max_lag_time", "max_lag_time_point"),
        cond("fit_lag_range_lower_bound", "fit_lag_range_lower_bound_point"),
    ]
    compare_arms = [{"arm": arm, "conditions": [cond("box_length", box)]} for arm, (box, _) in arms.items()]

    card = cards.head(
        "plan", f"plan-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, goal_id=goal["id"], synthesis_id=syn["id"],
        purpose=goal["purpose"], intent=goal["intent"],
        observable=cards.observable(goal["observable"]["name"]),
        system_configuration={"config": WCA, "optical_path": None, "devices": ["hoomd_backend"], "model": MODEL},
        targets=[dict(t) for t in goal.get("targets", [])],
        compare_variable="box_length",
        compare_arms=compare_arms,
        conditions=conditions,
        actions=[
            {"id": "integrate", "device": "hoomd_backend",
             "action": "integrate the declared configuration in each arm for the planned duration, saving unwrapped positions and orientations at the planned interval; the particle count of an arm is the held packing fraction times its box",
             "reversible": True, "parameters": [c["parameter"] for c in conditions] + ["box_length"], "tier": 1},
            {"id": "estimate", "device": "hoomd_backend",
             "action": "per arm: the mean squared displacement on the declared lag grid up to max_lag_time; the effective translational diffusivity from the slope above fit_lag_range_lower_bound divided by 2*d; the persistence time from the orientational autocorrelation; the persistence length from the crossover; the log-log slope on a rolling window. Uncertainties block-resampled over independent time origins, never from the fit",
             "reversible": True, "parameters": ["max_lag_time", "fit_lag_range_lower_bound", "save_interval"], "tier": 0},
        ],
        envelope_check=plan_card.envelope_check(numbers),
        cost={"wall_clock": "minutes: the mid arm is six billion particle-steps and the small arm a hundredth of it",
              "numbers": ["wall_clock_estimate", "storage_estimate"],
              "note": "estimates of an unrun job at an assumed rate, from A5 through S4. The smoke run's own log replaces the rate with a measured one"},
        stop_criteria=[
            {"id": "planned_duration_reached", "metric": "simulated_time", "comparator": ">=", "number": "total_simulated_time_point",
             "on_met": "complete", "statement": "stop when the run reaches the planned duration; running longer would be a different plan"},
            {"id": "step_displacement_diverged", "metric": "max_single_step_displacement", "comparator": ">", "number": "bead_diameter",
             "on_met": "fault", "statement": "a particle moving more than its own diameter in one step has passed through a neighbour's core; the WCA force there is enormous and the integration has diverged. Stop and keep the run, because divergence is a result"},
        ],
        success_criteria=[
            {"id": "statistics_met", "metric": "relative_block_error_of_effective_translational_diffusivity", "comparator": "<=",
             "number": "target_relative_error", "window": "lags from fit_lag_range_lower_bound to max_lag_time",
             "statement": "in each arm the block-resampled error on the long-time slope is small enough that the decade is decided by the physics and not by the sampling"},
            {"id": "arms_agree_within_decade", "metric": "log10_ratio_of_effective_translational_diffusivity_mid_to_small", "comparator": "<=",
             "target": "effective_translational_diffusivity", "window": "lags from fit_lag_range_lower_bound to max_lag_time",
             "statement": "the compare's question: the arm at ten persistence lengths and the arm at one agree within the goal's decade. Meeting it says the box does not matter at decade resolution between these two sizes; failing it says a persistence length of box is too small, and either is the result the question asked for"},
            {"id": "window_insensitive", "metric": "log10_ratio_of_first_half_to_second_half_effective_translational_diffusivity", "comparator": "<=",
             "target": "effective_translational_diffusivity", "window": "lags from fit_lag_range_lower_bound to max_lag_time, split at the midpoint",
             "statement": "the long-time slope agrees with itself across the fit range: if it does not, the lower bound sits inside the crossover and the number is not the plateau under this name"},
        ],
        alternatives_rejected=[{"what": r["what"], "reason": r["reason"], "grounds": r["grounds"]} for r in syn.get("rejected", [])],
        open_risks=[
            "The compare has two arms and not three: the arm at a hundred persistence lengths exceeds both A5 ceilings at the intersection's operating point and is refused in v2_refusal_s4 with the numbers. So this plan can say whether one persistence length of box already suffices against ten; it cannot say where independence sets in above ten.",
            "The small arm holds of order ten particles. At that count the packing fraction is realised coarsely and the MSD's particle average is thin; A2's record floor carries its statistics, and the block error is what says whether that was enough.",
            "At decade resolution a finite-size effect of a few tens of per cent is a tie (P15). The person has not asked for confirm, so a pass on arms_agree_within_decade means the box does not change the decade, not that it changes nothing.",
            "dynamical_crossover_time is registered but not read by this plan: its window parameter is a slope threshold between 2 and 1 that no card carries, and S4 introduces no numbers. Declaring it is a revision.",
            "In this system D_R is tied to D_T through the sphere's rotational drag as a stated assumption; the store holds no rotational diffusivity entry. If the person rules D_R an independent axis the persistence time, and with it every window here, moves.",
            "The temperature is realised exactly by the noise amplitude and is not a measurement; kb:lab_ambient_temperature records why the value was chosen. The experiment's side of any later comparison carries the whole temperature uncertainty.",
            "Nothing runs until a person writes a plan_approval for this revision, and no backend for the active configuration exists yet: hoomd_backend integrates bd_overdamped. The backend that realises this plan is the next thing this agent writes, and it has to convert nothing -- the plan is already in SI (D7).",
        ],
    )
    card["status"] = "DRAFT"
    card.update(cards.tail(numbers, assumptions=assumptions,
                           kb_refs=synthesis.kb_refs_for(qid, numbers), kb_gaps=synthesis.kb_gaps_for(qid),
                           degraded=["librarian_agent"]))
    return card


def render(card: dict) -> str:
    nums = {n["name"]: n for n in card["numbers"]}
    def fmt(v: float) -> str:
        # No exponent notation: check 9 reads "6e+09" as the number 6 with the
        # unit e (the electron charge). Large counts are written out in full.
        return f"{v:,.0f}" if abs(v) >= 1e6 else plan_card.fmt(v)
    q = lambda name: f"{fmt(nums[name]['value'])} {nums[name]['unit']}"
    L = []
    add = L.append
    add(f"# Plan {card['id']}"); add("")
    add(f"*Generated from `v{card['revision']}_plan_simulation_{card['qid']}.json`. The JSON is authoritative; editing this file changes nothing (P3).*"); add("")
    add(f"- **question** `{card['qid']}`, revision {card['revision']}, status `{card['status']}`")
    add(f"- **purpose** {card['purpose']} · **intent** {card['intent']} · **compares** `{card['compare_variable']}`")
    add(f"- **from** goal `{card['goal_id']}` via synthesis `{card['synthesis_id']}`")
    add(f"- **degraded** {', '.join(card['degraded'])} — S4 and S5 make no lookup; the axis cards did"); add("")
    add("## What is computed"); add("")
    entry = cards.definition_entry(card["observable"]["name"])
    add(f"**{card['observable']['name']}** — {entry['definition']}"); add("")
    add(f"*Estimator (from `contracts/observables.json`):* {entry['estimator']}"); add("")
    sc = card["system_configuration"]
    add(f"Configuration `{sc['config']}` on `{', '.join(sc['devices'])}`. Model: {sc['model']}."); add("")
    add("## The arms"); add("")
    add("| arm | box_length | particles (derived from the held packing fraction) |"); add("|---|---|---|")
    for arm in card["compare_arms"]:
        box = arm["conditions"][0]["number"]
        n = {"small": "n_particles_arm_small", "mid": "n_particles_arm_mid"}[arm["arm"]]
        add(f"| {arm['arm']} | {q(box)} | {q(n)} |")
    add("")
    add(f"A third arm at {q('box_length_largest_arm')} ({q('n_particles_largest_arm')} particles) was refused: "
        f"{q('particle_steps_arm_large')} particle-steps against a ceiling of {q('particle_steps_max')}, and "
        f"{q('coordinates_stored_arm_large')} stored coordinates against {q('coordinates_stored_max')}. See the S4 refusal card."); add("")
    add("## Conditions held across the arms"); add("")
    add("| parameter | value | source | grade |"); add("|---|---|---|---|")
    for c in card["conditions"]:
        n = nums[c["number"]]
        add(f"| `{c['parameter']}` | {q(c['number'])} | `{n['source']}` | {n['grade']} |")
    add("")
    add("## The windows"); add("")
    add(f"- the MSD curve runs to `max_lag_time` {q('max_lag_time_point')}, thirty persistence times ({q('persistence_time_expected')} each)")
    add(f"- the effective diffusivity is read above `fit_lag_range_lower_bound` {q('fit_lag_range_lower_bound_point')}; read earlier it is D_T under that name")
    add(f"- frames every {q('save_interval_point')}, two decades below the persistence time, so the crossover is resolved")
    add(f"- the record is {q('total_simulated_time_point')}, so the longest lag is a share {q('lag_to_record_ratio')} of it"); add("")
    add("## Declared before the run"); add("")
    for kind, title in (("stop_criteria", "Stop"), ("success_criteria", "Success")):
        add(f"**{title}**"); add("")
        for cr in card[kind]:
            if "number" in cr:
                against = q(cr["number"])
            else:
                t = next((t for t in card.get("targets", []) if t["metric"] == cr.get("target")), None)
                against = plan_card.target_phrase(cr.get("target"), t)
            add(f"- `{cr['metric']}` {cr['comparator']} {against} — {cr.get('statement', '')}")
        add("")
    env = card["envelope_check"]
    add("## Envelope"); add("")
    add(f"Status **{env['status']}**, checked against {', '.join(f'`{p}`' for p in env['checked_against'])}. {env.get('note', '')}"); add("")
    add(f"Cost: {q('wall_clock_estimate')} of wall clock and {q('storage_estimate')} of disk for both arms, at an assumed rate of ten million particle-steps per second (`particle_step_rate`)."); add("")
    add("## Rejected"); add("")
    for r in card["alternatives_rejected"]:
        add(f"- **{r['what']}** — {r['reason']} (grounds: {', '.join(f'`{x}`' for x in r['grounds'])})")
    add(""); add("## Open risks"); add("")
    for r in card["open_risks"]:
        add(f"- {r}")
    add("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# 041 -- the sweep
# --------------------------------------------------------------------------- #

PE_LEVELS = ("peclet_min", "peclet_mid", "peclet_max")
PHI_LEVELS = ("packing_fraction_min", "packing_fraction_mid", "packing_fraction_max")


def build_041(qid: str, created_at: str, revision: int) -> dict:
    """The plan for the (Peclet, packing fraction) grid, carried as `sweep`.

    `sweep.axes` names the two quantities that move and their levels;
    `sweep.points` lists the nine cells with their conditions, and the cells
    S4 skipped carry `skipped` with the reason, so an empty corner is visible
    and not silent. Two per-point conditions are not axes: the step and the
    box are FUNCTIONS of the Peclet level (A1 and A3 marked them varies_with),
    so they differ between points along that axis and are constant along the
    other. The schema's invariant -- every point shares every condition except
    the ones the axes name -- is read here as: except the axes and what the
    axes determine. Stated so it can be refused if that reading is wrong.
    """
    import json as _json
    goal = cards.load_goal(qid, revision)
    syn_name = cards.artifact_name("synthesis.json", revision)
    syn = _json.loads((cards.question_dir(qid) / syn_name).read_text())
    A5 = cards.artifact_name(f"axis_{WCA}_a5.json", revision)

    shared = ["temperature", "viscosity", "bead_diameter", "translational_diffusivity", "rotational_diffusivity",
              "wca_epsilon", "persistence_time_expected", "total_simulated_time_point", "save_interval_point",
              "max_lag_time_point", "fit_lag_range_lower_bound_point", "lag_to_record_ratio", "target_relative_error",
              "particle_step_rate", "particle_steps_max", "coordinates_stored_max", "wall_clock_max", "storage_max"]
    levels = list(PE_LEVELS + PHI_LEVELS)
    per_pe = [f"{k}_pe_{l.split('_')[-1]}" for l in PE_LEVELS for k in ("integration_timestep_point", "box_length", "integration_timestep_max")]
    cells = [f"{a.split('_')[-1]}_{b.split('_')[-1]}" for a in PE_LEVELS for b in PHI_LEVELS]
    per_cell = [f"{k}_{c}" for c in cells for k in ("n_particles", "particle_steps", "coordinates_stored")]
    wanted = [(syn_name, n) for n in shared + levels + per_pe + per_cell] + [(A5, "bytes_per_coordinate")]
    numbers = synthesis.carry_from(qid, WCA, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)
    g = {n["name"]: n["grade"] for n in numbers}
    V = lambda name: next(float(n["value"]) for n in numbers if n["name"] == name)

    skipped = {r["what"].split()[-1]: r for r in syn.get("rejected", []) if r.get("kind") == "operating_point"}
    kept = [c for c in cells if c not in skipped]

    # the free-particle expectation per Peclet level, the reference the compare with the free model is read against
    for l in PE_LEVELS:
        tag = l.split("_")[-1]
        pe = V(l); dt_ = V("translational_diffusivity"); dr = V("rotational_diffusivity"); d = V("bead_diameter")
        v0 = pe * d * dr                                    # um/s with d in um and D_R in 1/s
        d_free = dt_ + v0 * v0 / (2 * dr)                   # um^2/s
        numbers.append(cards.num(f"effective_diffusivity_free_pe_{tag}", oom(d_free * 1e-12, "um^2/s"), "um^2/s", "computed:free_active_brownian_long_time",
            formula=f"translational_diffusivity+({l}*bead_diameter*rotational_diffusivity)**2/(2*rotational_diffusivity)",
            inputs=[(n, g[n]) for n in ("translational_diffusivity", l, "bead_diameter", "rotational_diffusivity")],
            precision="order_of_magnitude",
            note=f"the closed-form long-time diffusivity of a FREE active Brownian particle in 2D at Pe = {pe:g}, D_T + v0^2/(2 D_R): what an interacting cell's value is read against. A literature relation applied to this plan's inputs, not a store entry -- the store holds none (kb_gaps), and entering it is the librarian's"))
        g[f"effective_diffusivity_free_pe_{tag}"] = numbers[-1]["grade"]

    wall_s = sum(V(f"particle_steps_{c}") for c in kept) / V("particle_step_rate")
    numbers.append(cards.num("wall_clock_estimate", oom(wall_s, "s"), "s", "computed:particle_steps_over_rate",
        formula="(" + "+".join(f"particle_steps_{c}" for c in kept) + ")/particle_step_rate",
        inputs=[(n, g[n]) for n in [f"particle_steps_{c}" for c in kept] + ["particle_step_rate"]],
        precision="order_of_magnitude",
        note=f"all {len(kept)} kept cells, one seed each, at A5's assumed rate; in seconds because one figure in SI is one figure here. See the open risks for the measured rate"))
    store = sum(V(f"coordinates_stored_{c}") for c in kept) * V("bytes_per_coordinate")
    numbers.append(cards.num("storage_estimate", oom(store * 1e9, "GB"), "GB", "computed:coordinates_times_bytes",
        formula="(" + "+".join(f"coordinates_stored_{c}" for c in kept) + ")*bytes_per_coordinate",
        inputs=[(n, g[n]) for n in [f"coordinates_stored_{c}" for c in kept] + ["bytes_per_coordinate"]],
        precision="order_of_magnitude", note="all kept cells' trajectories in double precision"))

    cond = lambda p, n: {"parameter": p, "number": n}
    conditions = [cond("temperature", "temperature"), cond("viscosity", "viscosity"), cond("bead_diameter", "bead_diameter"),
                  cond("translational_diffusivity", "translational_diffusivity"), cond("rotational_diffusivity", "rotational_diffusivity"),
                  cond("wca_epsilon", "wca_epsilon"), cond("total_simulated_time", "total_simulated_time_point"),
                  cond("save_interval", "save_interval_point"), cond("max_lag_time", "max_lag_time_point"),
                  cond("fit_lag_range_lower_bound", "fit_lag_range_lower_bound_point")]
    points = []
    for a in PE_LEVELS:
        for b in PHI_LEVELS:
            tag = f"{a.split('_')[-1]}_{b.split('_')[-1]}"
            pt = {"point": tag, "conditions": [cond("peclet_number_steric", a), cond("packing_fraction", b),
                                                cond("integration_timestep", f"integration_timestep_point_pe_{a.split('_')[-1]}"),
                                                cond("box_length", f"box_length_pe_{a.split('_')[-1]}")]}
            if tag in skipped:
                pt["skipped"] = skipped[tag]["reason"] + " (grounds: " + ", ".join(skipped[tag]["grounds"]) + ")"
            points.append(pt)
    sweep = {"axes": [{"parameter": "peclet_number_steric", "levels": list(PE_LEVELS)},
                      {"parameter": "packing_fraction", "levels": list(PHI_LEVELS)}],
             "points": points}

    card = cards.head(
        "plan", f"plan-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, goal_id=goal["id"], synthesis_id=syn["id"], purpose=goal["purpose"], intent=goal["intent"],
        observable=cards.observable(goal["observable"]["name"]),
        system_configuration={"config": WCA, "optical_path": None, "devices": ["hoomd_backend"], "model": MODEL},
        targets=[dict(t) for t in goal.get("targets", [])],
        sweep=sweep, conditions=conditions,
        actions=[
            {"id": "integrate", "device": "hoomd_backend",
             "action": "per kept cell: integrate the declared configuration for the planned duration at the cell's step and box, saving unwrapped positions and orientations at the planned interval; the particle count is the cell's packing fraction times its box",
             "reversible": True, "parameters": [c["parameter"] for c in conditions] + ["peclet_number_steric", "packing_fraction", "integration_timestep", "box_length"], "tier": 1},
            {"id": "estimate", "device": "hoomd_backend",
             "action": "per cell: the MSD on the declared lag grid up to max_lag_time; the effective translational diffusivity from the slope above fit_lag_range_lower_bound over 2*d; the persistence time from the orientational autocorrelation; the persistence length from the crossover; the log-log slope on a rolling window. Uncertainties block-resampled over particles",
             "reversible": True, "parameters": ["max_lag_time", "fit_lag_range_lower_bound", "save_interval"], "tier": 0},
        ],
        envelope_check=plan_card.envelope_check(numbers),
        cost={"wall_clock": f"about an hour and a half for the {len(kept)} kept cells at the assumed rate, most of it in the densest kept cell",
              "numbers": ["wall_clock_estimate", "storage_estimate"],
              "note": "estimates at A5's assumed rate; the measured rate on this CPU is lower, see the open risks"},
        stop_criteria=[
            {"id": "planned_duration_reached", "metric": "simulated_time", "comparator": ">=", "number": "total_simulated_time_point",
             "on_met": "complete", "statement": "stop when the run reaches the planned duration; running longer would be a different plan"},
            {"id": "step_displacement_diverged", "metric": "max_single_step_displacement", "comparator": ">", "number": "bead_diameter",
             "on_met": "fault", "statement": "a particle moving more than its own diameter in one step has passed through a neighbour's core; stop and keep the run, because divergence is a result"},
        ],
        success_criteria=[
            {"id": "statistics_met", "metric": "relative_block_error_of_effective_translational_diffusivity", "comparator": "<=",
             "number": "target_relative_error", "window": "lags from fit_lag_range_lower_bound to max_lag_time",
             "statement": "in each cell the block-resampled error on the long-time slope is small enough that the decade is decided by the physics"},
            {"id": "within_decade_of_free_expectation", "metric": "log10_ratio_of_effective_translational_diffusivity_to_free_expectation_at_this_peclet", "comparator": "<=",
             "target": "effective_translational_diffusivity", "window": "lags from fit_lag_range_lower_bound to max_lag_time",
             "statement": "the question's own criterion: the interacting cell agrees with the free active particle's closed-form long-time diffusivity at its Peclet number within the goal's decade. Meeting it says interactions do not change the decade there; failing it is the qualitatively different regime the question asked whether density produces, and either is the result"},
            {"id": "window_insensitive", "metric": "log10_ratio_of_first_half_to_second_half_effective_translational_diffusivity", "comparator": "<=",
             "target": "effective_translational_diffusivity", "window": "lags from fit_lag_range_lower_bound to max_lag_time, split at the midpoint",
             "statement": "the long-time slope agrees with itself across the fit range; if not, the lower bound sits inside the crossover and the number is not the plateau"},
        ],
        alternatives_rejected=[{"what": r["what"], "reason": r["reason"], "grounds": r["grounds"]} for r in syn.get("rejected", [])],
        open_risks=[
            f"Three of the nine cells are skipped -- the whole Pe 100 row -- because at that level the step is a decade under a millisecond-scale ceiling and the box is five millimetres, so even the dilute cell costs 3e11 particle-steps against a ceiling of 7e10. The S4 refusal card says which single cell would fit at A1's ceiling rather than a decade under it, and why the margin is not owed where the self-propulsion step binds. So this plan characterises Pe 1 and 10 and says nothing about Pe 100 until the person raises a ceiling or accepts the ceiling step.",
            "The step and the box differ between points along the Peclet axis because A1 and A3 marked those bounds varies_with peclet_number_steric. They are not sweep axes; they are functions of one. The schema's invariant is read here as 'shared except the axes and what the axes determine', and if that reading is refused the plan is wrong and not the invariant.",
            "The wall-clock estimate rests on A5's assumed rate of ten million particle-steps per second. The small arm of the box compare (question 042 of this seat) measured 8e5 per second at 13 particles and a trial at a thousand particles measured 3.5e6, so the estimates here are three to ten times low and the densest kept cell (Pe 10, phi 0.5, 6000 particles, 4e10 particle-steps) may run three hours against a two-hour ceiling. The operator's gate reads the plan's rate and will not catch it; a_cost_reference's falsifier needs a trajectory-writing run, and gsd is not in the sim environment, so it has not fired. The person should know before the densest cell is started.",
            "The sparsest cell, Pe 1 and phi 0.01, holds one particle in a box of one persistence length. Its MSD is one particle's, its packing fraction is realised as one particle, and its block error cannot be formed (fewer than two blocks). It is kept because the grid is the question and an empty cell would have to say why; its result card will say what a single particle can and cannot support.",
            "The free-particle expectation each cell is compared against is D_T + v0^2/(2 D_R), a literature relation applied to this plan's inputs and not a store entry; the librarian holds nothing on active matter yet (kb_gaps). Entering it is the librarian's, and until then the comparison rests on a relation this plan wrote down.",
            "In the free arm the ballistic slope is not resolvable below Pe_thermal of about 20 (window 3's measurement), which is Pe_steric about 12 in this SED-tied system; the Pe 1 row therefore shows no ballistic regime in the reference and the crossover observables there are about the interacting system alone.",
            "D_R is tied to D_T through the sphere's rotational drag as a stated assumption; the store holds no rotational diffusivity entry. The persistence time and every window here move with it.",
            "No plan_approval exists and none is needed at tier 1; each cell runs autonomously once inside the envelope. No trajectory is written while gsd is absent from the sim environment, and each run's meta says so.",
        ],
    )
    card["status"] = "DRAFT"
    card.update(cards.tail(numbers, assumptions=assumptions, kb_refs=synthesis.kb_refs_for(qid, numbers),
                           kb_gaps=synthesis.kb_gaps_for(qid), degraded=["librarian_agent"]))
    return card


def render_041(card: dict) -> str:
    nums = {n["name"]: n for n in card["numbers"]}
    def fmt(v):
        return f"{v:,.0f}" if abs(v) >= 1e6 else plan_card.fmt(v)
    q = lambda name: f"{fmt(nums[name]['value'])} {nums[name]['unit']}"
    L = []; add = L.append
    add(f"# Plan {card['id']}"); add("")
    add(f"*Generated from `v{card['revision']}_plan_simulation_{card['qid']}.json`. The JSON is authoritative; editing this file changes nothing (P3).*"); add("")
    add(f"- **question** `{card['qid']}`, revision {card['revision']}, status `{card['status']}`")
    add(f"- **purpose** {card['purpose']} · **intent** {card['intent']} · **sweep** over `peclet_number_steric` and `packing_fraction`")
    add(f"- **from** goal `{card['goal_id']}` via synthesis `{card['synthesis_id']}`")
    add(f"- **degraded** {', '.join(card['degraded'])} — S4 and S5 make no lookup; the axis cards did"); add("")
    add("## What is computed"); add("")
    entry = cards.definition_entry(card["observable"]["name"])
    add(f"**{card['observable']['name']}** — {entry['definition']}"); add("")
    add(f"*Estimator (from `contracts/observables.json`):* {entry['estimator']}"); add("")
    sc = card["system_configuration"]; add(f"Configuration `{sc['config']}` on `{', '.join(sc['devices'])}`. Model: {sc['model']}."); add("")
    add("## The grid"); add("")
    add("| cell | Pe | packing fraction | step | box | particles | particle-steps | run? |"); add("|---|---|---|---|---|---|---|---|")
    for pt in card["sweep"]["points"]:
        c = {x["parameter"]: x["number"] for x in pt["conditions"]}
        tag = pt["point"]
        add(f"| {tag} | {q(c['peclet_number_steric'])} | {q(c['packing_fraction'])} | {q(c['integration_timestep'])} | {q(c['box_length'])} | {q('n_particles_' + tag)} | {q('particle_steps_' + tag)} | {'skipped' if 'skipped' in pt else 'yes'} |")
    add("")
    add("Skipped cells exceed A5's ceilings at their own step and box; the S4 refusal card carries the counterexample and the alternatives."); add("")
    add("## Conditions held across the grid"); add("")
    add("| parameter | value | source | grade |"); add("|---|---|---|---|")
    for c in card["conditions"]:
        n = nums[c["number"]]; add(f"| `{c['parameter']}` | {q(c['number'])} | `{n['source']}` | {n['grade']} |")
    add("")
    add("## The free expectation each cell is read against"); add("")
    for l in PE_LEVELS:
        tag = l.split("_")[-1]
        add(f"- Pe {q(l)}: D_T + v0²/(2 D_R) = {q('effective_diffusivity_free_pe_' + tag)}")
    add("")
    add("## Declared before the run"); add("")
    for kind, title in (("stop_criteria", "Stop"), ("success_criteria", "Success")):
        add(f"**{title}**"); add("")
        for cr in card[kind]:
            if "number" in cr:
                against = q(cr["number"])
            else:
                t = next((t for t in card.get("targets", []) if t["metric"] == cr.get("target")), None)
                against = plan_card.target_phrase(cr.get("target"), t)
            add(f"- `{cr['metric']}` {cr['comparator']} {against} — {cr.get('statement', '')}")
        add("")
    env = card["envelope_check"]
    add("## Envelope"); add("")
    add(f"Status **{env['status']}**, checked against {', '.join(f'`{p}`' for p in env['checked_against'])}. {env.get('note', '')}"); add("")
    add(f"Cost: {q('wall_clock_estimate')} of wall clock and {q('storage_estimate')} of disk for the kept cells, at an assumed rate of ten million particle-steps per second (`particle_step_rate`)."); add("")
    add("## Rejected"); add("")
    for r in card["alternatives_rejected"]:
        add(f"- **{r['what']}** — {r['reason']} (grounds: {', '.join(f'`{x}`' for x in r['grounds'])})")
    add(""); add("## Open risks"); add("")
    for r in card["open_risks"]:
        add(f"- {r}")
    add("")
    return "\n".join(L)


def emit(qid: str, created_at: str) -> tuple[Path, str]:
    directory = cards.question_dir(qid)
    revision = cards.question_revision(qid)
    sweep = qid.endswith("-041")
    card = (build_041 if sweep else build)(qid, created_at, revision)
    draw = render_041 if sweep else render
    json_path = directory / cards.artifact_name(f"plan_simulation_{qid}.json", revision)
    md_path = json_path.with_suffix(".md")
    cards.refuse_overwrite(json_path, revision, card)
    cards.write(json_path, card)
    md_path.write_text(draw(card))
    verdict = subprocess.run([sys.executable, str(cards.CONTRACTS / "validate.py"), "--quiet"], capture_output=True, text=True)
    if verdict.returncode == 0:
        card["status"] = "VALIDATED"
        cards.write(json_path, card)
        md_path.write_text(draw(card))
        return json_path, "VALIDATED"
    tail = verdict.stdout.strip().splitlines()[-1] if verdict.stdout.strip() else "see validate.py"
    return json_path, f"DRAFT (validator exit {verdict.returncode}; {tail})"


if __name__ == "__main__":
    path, status = emit(sys.argv[1], sys.argv[2])
    print(path.name, status)
