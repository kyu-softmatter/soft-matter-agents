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


def emit(qid: str, created_at: str) -> tuple[Path, str]:
    directory = cards.question_dir(qid)
    revision = cards.question_revision(qid)
    card = build(qid, created_at, revision)
    json_path = directory / cards.artifact_name(f"plan_simulation_{qid}.json", revision)
    md_path = json_path.with_suffix(".md")
    cards.refuse_overwrite(json_path, revision, card)
    cards.write(json_path, card)
    md_path.write_text(render(card))
    verdict = subprocess.run([sys.executable, str(cards.CONTRACTS / "validate.py"), "--quiet"], capture_output=True, text=True)
    if verdict.returncode == 0:
        card["status"] = "VALIDATED"
        cards.write(json_path, card)
        md_path.write_text(render(card))
        return json_path, "VALIDATED"
    tail = verdict.stdout.strip().splitlines()[-1] if verdict.stdout.strip() else "see validate.py"
    return json_path, f"DRAFT (validator exit {verdict.returncode}; {tail})"


if __name__ == "__main__":
    path, status = emit(sys.argv[1], sys.argv[2])
    print(path.name, status)
