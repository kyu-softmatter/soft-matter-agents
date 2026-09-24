"""S4 and S5 for sim-20260923-102: one trap at rest, one operating point.

The synthesis and the plan for `bd_overdamped_trapped`, in one module because
there is one cell and nothing to choose between: one configuration survived
screening, and the operating point is the goal's `trap_stiffness_operating`,
the double well's soft trap. `synthesis_trap` / `plan_trap` are the driven
configuration's and grid-shaped; this is their one-cell case with the flow
removed and the observable a width.

Every bound the axes returned is a multiple of the local gamma/k_t, so each
value here is written as that multiple of `relaxation_time_op` and read off the
axis cards' own numbers. S4 introduces no number (4.5.4): the three factors
below sit inside formulas on carried numbers.

    DT_MARGIN 0.8  -- the step sits under A1's binding bound with room for the
                      one-figure rounding of tau, and build() checks the bound
                      at the UNROUNDED tau rather than trusting the factor
    RECORD 2       -- the record is twice A2's floor, because one figure of
                      1.5 * 100 * 0.09 = 13.5 is 10 and loses the margin
    STARTUP 10     -- relaxation times discarded from the start, the same
                      multiple the driven configuration's A7 declares

    python -m simulation_agent.src.plan_trap_width sim-20260923-102 <created_at> synthesis|plan
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

from . import cards, plan_card, synthesis
from .config_bd_overdamped_trapped import _one

CONFIG = "bd_overdamped_trapped"
DT_MARGIN = 0.8
RECORD = 2
STARTUP = 10
MODEL = ("one overdamped sphere in a harmonic external potential of stiffness k_t centred at the "
         "origin, fluid at rest; three dimensions, the estimator reads the two in-plane axes; "
         "no pair interaction, no wall")


def _n(numbers, g, name, value, unit, source, formula, inputs, note, precision="order_of_magnitude"):
    n = cards.num(name, value, unit, source, formula=formula,
                  inputs=[(i, g[i]) for i in inputs], precision=precision, note=note)
    numbers.append(n)
    g[name] = n["grade"]
    return n


def synthesis_card(qid: str, created_at: str, revision: int) -> dict:
    group = synthesis.axis_cards(qid, CONFIG, revision)
    intersection, conflict = synthesis.intersect(group)
    if conflict is not None:
        raise SystemExit(f"{CONFIG} came out empty; S4 ends in a refusal card, not a plan (P5)")
    goal = cards.load_goal(qid, revision)
    G = cards.artifact_name("goal.json", revision)
    A = lambda ax: cards.artifact_name(f"axis_{CONFIG}_{ax}.json", revision)
    wanted = [(G, n) for n in ("bead_diameter", "temperature", "viscosity", "trap_stiffness_operating")]
    wanted += [(A("a1"), "noise_step_fraction"), (A("a2"), "relaxation_times_per_record"),
               (A("a4"), "save_interval_fraction"),
               (A("a5"), "cost_per_step"), (A("a5"), "steps_max_per_point")]
    numbers = synthesis.carry_from(qid, CONFIG, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)
    g = {n["name"]: n["grade"] for n in numbers}
    V = lambda name: next(float(n["value"]) for n in numbers if n["name"] == name)
    add = lambda *a, **k: _n(numbers, g, *a, **k)

    gamma = 3 * math.pi * V("viscosity") * V("bead_diameter") * 1e-6        # kg/s
    k_si = V("trap_stiffness_operating") * 1e-6                              # N/m
    add("relaxation_time_op", _one(gamma / k_si), "s", "computed:stokes_drag_over_stiffness",
        "3*pi*viscosity*bead_diameter/trap_stiffness_operating",
        ["viscosity", "bead_diameter", "trap_stiffness_operating"],
        "gamma/k_t at the operating stiffness. Every bound below is a multiple of it, which is what the "
        "axis cards' varies_with said")
    add("thermal_width_op", _one(math.sqrt(1.380649e-23 * V("temperature") / k_si) * 1e6), "um",
        "computed:equipartition_width", "(k_B*temperature/trap_stiffness_operating)**0.5",
        ["temperature", "trap_stiffness_operating"],
        "THE PREDICTION: the per-axis width equipartition gives at this stiffness. Both the run and the "
        "bench are compared against it, and the bench's deviation from it is what yields the stiffness")
    add("integration_timestep_op", _one(DT_MARGIN * 0.5 * V("noise_step_fraction") ** 2 * V("relaxation_time_op")),
        "s", "computed:a1_noise_bound_with_margin",
        f"{DT_MARGIN}*0.5*noise_step_fraction**2*relaxation_time_op", ["noise_step_fraction", "relaxation_time_op"],
        "A1's noise bound binds, with S4's margin for the rounding of tau")
    # A FRAME MUST FALL ON A STEP. Revision 1 wrote the save interval as A4's
    # ceiling, one figure of 0.1*tau = 0.009 s, and 0.009/0.0004 = 22.5 steps:
    # the operator refused it before a step was taken, correctly. So the save
    # interval is the LARGEST whole number of steps that is also a clean one-figure
    # value (so check 17's rounding cannot move it off the grid) and stays
    # under A4's ceiling; the start-up is the SMALLEST whole number of frames
    # at or above STARTUP relaxation times that is clean in the same sense.
    dt = V("integration_timestep_op")
    ceiling = _one(V("save_interval_fraction") * V("relaxation_time_op"))
    n_save = max(n for n in range(1, int(ceiling / dt) + 1) if abs(_one(n * dt) - n * dt) < 1e-12)
    add("save_interval_op", _one(n_save * dt), "s", "computed:whole_steps_under_a4_ceiling",
        f"{n_save}*integration_timestep_op", ["integration_timestep_op"],
        f"{n_save} steps a frame: the largest whole number of steps under A4's ceiling of a tenth of "
        "gamma/k_t that is a clean one-figure value, so every frame falls on a step")
    save = V("save_interval_op")
    n_start = next(n for n in range(int(STARTUP * V("relaxation_time_op") / save), 100000)
                   if n * save >= STARTUP * V("relaxation_time_op") and abs(_one(n * save) - n * save) < 1e-12)
    add("startup_discard_op", _one(n_start * save), "s", "computed:whole_frames_over_startup_floor",
        f"{n_start}*save_interval_op", ["save_interval_op"],
        f"{n_start} frames: the first whole number of frames at or above ten relaxation times. The particle "
        "starts at the trap centre and its distribution relaxes over gamma/k_t, so ten of them leave a "
        "residual far below a per mille. Declared in advance, never chosen after seeing the data")
    add("record_length_op", _one(RECORD * V("relaxation_times_per_record") * V("relaxation_time_op")), "s",
        "computed:margin_times_record_floor", f"{RECORD}*relaxation_times_per_record*relaxation_time_op",
        ["relaxation_times_per_record", "relaxation_time_op"],
        "the averaging window after the start-up: twice A2's floor. The observable's registered window, "
        "and the bench's record length too")
    add("width_bias_op", _one(V("relaxation_time_op") / V("record_length_op")), "1",
        "computed:record_mean_subtraction_bias", "relaxation_time_op/record_length_op",
        ["relaxation_time_op", "record_length_op"],
        "how far below the true width this record's width is expected to sit, from subtracting its own mean")
    add("width_scatter_op", _one((V("relaxation_time_op") / (2 * V("record_length_op"))) ** 0.5), "1",
        "computed:ou_variance_standard_error", "(relaxation_time_op/(2*record_length_op))**0.5",
        ["relaxation_time_op", "record_length_op"],
        "the width's relative standard error from one record of this length")
    add("width_acceptance_op", _one(3 * V("width_scatter_op")), "1", "computed:three_scatters",
        "3*width_scatter_op", ["width_scatter_op"],
        "the success band, three of the record's own standard errors, fixed before the run")
    add("camera_exposure_max_op", _one(0.1 * V("relaxation_time_op")), "s", "computed:tenth_of_tau",
        "0.1*relaxation_time_op", ["relaxation_time_op"],
        "the longest bench exposure that keeps exposure averaging under three per cent of the variance "
        "(A4's precondition); a longer one needs the correction applied to the simulated width")
    add("particle_step_rate", _one(1.0 / V("cost_per_step")), "1/s", "computed:inverse_cost",
        "1/cost_per_step", ["cost_per_step"], "the measured single-particle rate on the trap builder")
    add("particle_steps_op", _one((V("startup_discard_op") + V("record_length_op")) / V("integration_timestep_op")),
        "1", "computed:duration_over_step", "(startup_discard_op+record_length_op)/integration_timestep_op",
        ["startup_discard_op", "record_length_op", "integration_timestep_op"],
        "one particle, so particle-steps are steps; against steps_max_per_point")
    add("coordinates_stored_op", _one(3 * (V("startup_discard_op") + V("record_length_op")) / V("save_interval_op")),
        "1", "computed:three_coordinates_per_frame", "3*(startup_discard_op+record_length_op)/save_interval_op",
        ["startup_discard_op", "record_length_op", "save_interval_op"], "one particle, three coordinates a frame")

    tau_true = gamma / k_si
    for name in ("save_interval_op", "startup_discard_op", "record_length_op"):
        steps = V(name) / V("integration_timestep_op")
        if abs(steps - round(steps)) > 1e-9:
            raise SystemExit(f"{name} is {steps} steps, not a whole number; a frame would land between steps")
    if not (_one(0.01 * V("relaxation_time_op")) <= V("save_interval_op") <= ceiling):
        raise SystemExit("the save interval left A4's interval")
    if V("integration_timestep_op") > 0.5 * V("noise_step_fraction") ** 2 * tau_true * (1 + 1e-9):
        raise SystemExit("the step exceeds A1's bound at the unrounded relaxation time; the margin is too thin")
    if V("particle_steps_op") > V("steps_max_per_point"):
        raise SystemExit("the operating point exceeds A5's step budget (P5)")

    card = cards.head(
        "synthesis", f"synthesis-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, configs_screened=[CONFIG],
        per_config=[{"config": CONFIG, "empty": False, "axis_files": [f for f, _ in group],
                     "intersection": intersection}],
        chosen_config=CONFIG,
        operating_point=[{"parameter": p, "number": n} for p, n in (
            ("temperature", "temperature"), ("viscosity", "viscosity"), ("bead_diameter", "bead_diameter"),
            ("trap_stiffness", "trap_stiffness_operating"), ("integration_timestep", "integration_timestep_op"),
            ("save_interval", "save_interval_op"), ("startup_discard", "startup_discard_op"),
            ("record_length", "record_length_op"))],
        priority_used=goal["priority"], priority_source="goal_card", rejected=[],
        tie_break=("one configuration survived screening and the goal names one operating stiffness, so there "
                   "was nothing to break. The step, save interval, start-up and record are multiples of this "
                   "stiffness's gamma/k_t because the axis cards marked them varies_with trap_stiffness. S4 made "
                   "no lookup, so the librarian is degraded here by construction and the gaps are the axes'"),
    )
    card.update(cards.tail(numbers, assumptions=assumptions, kb_refs=synthesis.kb_refs_for(qid, numbers),
                           kb_gaps=synthesis.kb_gaps_for(qid), degraded=["librarian_agent"]))
    return card


def plan(qid: str, created_at: str, revision: int) -> dict:
    goal = cards.load_goal(qid, revision)
    S = cards.artifact_name("synthesis.json", revision)
    syn = json.loads((cards.question_dir(qid) / S).read_text())
    A3 = cards.artifact_name(f"axis_{CONFIG}_a3.json", revision)
    wanted = [(S, n) for n in (
        "temperature", "viscosity", "bead_diameter", "trap_stiffness_operating", "relaxation_time_op",
        "thermal_width_op", "integration_timestep_op", "save_interval_op", "startup_discard_op",
        "record_length_op", "width_bias_op", "width_scatter_op", "width_acceptance_op",
        "camera_exposure_max_op", "particle_step_rate", "steps_max_per_point", "particle_steps_op",
        "coordinates_stored_op")] + [(A3, "box_edge_min")]
    numbers = synthesis.carry_from(qid, CONFIG, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)
    g = {n["name"]: n["grade"] for n in numbers}
    V = lambda name: next(float(n["value"]) for n in numbers if n["name"] == name)
    numbers.append(cards.num("bytes_per_coordinate", 4e-09, "GB", "spec:ieee754_single",
                             precision="significant_figures", note="float32, the trajectory writer's dtype"))
    g["bytes_per_coordinate"] = "E3"
    numbers.append(cards.num(
        "wall_clock_estimate", _one(V("particle_steps_op") / V("particle_step_rate")), "s",
        "computed:particle_steps_over_rate", formula="particle_steps_op/particle_step_rate",
        inputs=[("particle_steps_op", g["particle_steps_op"]), ("particle_step_rate", g["particle_step_rate"])],
        precision="order_of_magnitude", note="one seed at the rate measured at one particle"))
    numbers.append(cards.num(
        "storage_estimate", _one(V("coordinates_stored_op") * V("bytes_per_coordinate")), "GB",
        "computed:coordinates_times_bytes", formula="coordinates_stored_op*bytes_per_coordinate",
        inputs=[("coordinates_stored_op", g["coordinates_stored_op"]), ("bytes_per_coordinate", "E3")],
        precision="order_of_magnitude", note="the trajectory in single precision"))

    cond = lambda p, n: {"parameter": p, "number": n}
    conditions = [
        cond("temperature", "temperature"), cond("viscosity", "viscosity"),
        cond("bead_diameter", "bead_diameter"), cond("box_length", "box_edge_min"),
        cond("trap_stiffness", "trap_stiffness_operating"), cond("integration_timestep", "integration_timestep_op"),
        cond("save_interval", "save_interval_op"), cond("startup_discard", "startup_discard_op"),
        cond("record_length", "record_length_op"),
    ]
    card = cards.head(
        "plan", f"plan-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, goal_id=goal["id"], synthesis_id=syn["id"],
        purpose=goal["purpose"], intent=goal["intent"],
        observable=cards.observable(goal["observable"]["name"]),
        system_configuration={"config": CONFIG, "optical_path": None, "devices": ["trap_hoomd_backend"],
                              "model": MODEL},
        targets=[dict(t) for t in goal.get("targets", [])],
        conditions=conditions,
        actions=[
            {"id": "integrate", "device": "trap_hoomd_backend",
             "action": "integrate one sphere from the trap centre with the fluid at rest, for startup_discard plus "
                       "record_length, saving its unwrapped position at save_interval",
             "reversible": True, "parameters": [x["parameter"] for x in conditions], "tier": 1},
            {"id": "estimate", "device": "trap_hoomd_backend",
             "action": "after startup_discard: the per-axis standard deviation of x and y about their record mean, "
                       "the position histogram against a Gaussian of the predicted width, and the cost per step",
             "reversible": True, "parameters": ["startup_discard", "record_length", "save_interval"], "tier": 0},
        ],
        envelope_check=plan_card.envelope_check(numbers),
        cost={"wall_clock": "a fraction of a second at the measured single-particle rate",
              "numbers": ["wall_clock_estimate", "storage_estimate"],
              "note": "measured, not bracketed: one particle on the builder this configuration uses"},
        stop_criteria=[
            {"id": "step_displacement_diverged", "metric": "max_single_step_displacement", "comparator": ">",
             "number": "bead_diameter", "on_met": "fault",
             "statement": "a sphere moving more than its own diameter in one step means the integration has run "
                          "away. Stop and keep the run: divergence is a result"},
        ],
        success_criteria=[
            {"id": "width_within_decade", "metric": "trapped_position_distribution",
             "comparator": "<=", "target": "trapped_position_distribution",
             "window": "record_length, after startup_discard",
             "statement": "the goal's target: both in-plane widths within one decade of the prediction"},
            {"id": "width_within_three_scatters", "metric": "relative_deviation_of_width_from_equipartition",
             "comparator": "<=", "number": "width_acceptance_op", "window": "record_length, after startup_discard",
             "statement": "each in-plane width within three of this record's own standard errors of "
                          "sqrt(k_B*T/k_t), after allowing for the expected low bias of one relaxation time over "
                          "the record. Stricter than the target and declared anyway, because it is what tests the "
                          "estimator rather than only the integrator"},
        ],
        alternatives_rejected=[{
            "what": "the other three stiffnesses of the goal's range, in this revision",
            "reason": "the double well's soft trap is the first input it needs; the range is swept once the "
                      "bench has said which dial settings it can use",
            "grounds": ["trap_stiffness_operating"]}],
        open_risks=[
            "THE WIDTH IS NOT EVIDENCE ABOUT ANY TRAP: k_t goes in and sqrt(k_B*T/k_t) comes out by construction "
            "(output_independent_of_input false). A pass tests the integrator and the estimator. What the run "
            "carries to the bench is the record length and the expected bias and scatter at that length.",
            "A CAMERA FRAME IS NOT AN INSTANT. The run's positions are instantaneous; a frame averages over its "
            "exposure and narrows the variance. The bench exposure must stay under camera_exposure_max_op, or the "
            "comparison must apply the exposure correction to the simulated width.",
            "The trap is harmonic by declaration and a real trap goes to zero far from its focus. Where the bench "
            "trap stops being harmonic is unknown -- the store holds no trap width -- and only the measured "
            "histogram's tails can say.",
            "The width's low bias from a finite record has a sign and scatter does not. The three-scatter criterion "
            "allows for it; a comparison that ignores it reads a one-relaxation-time-over-the-record shortfall as "
            "a stiffer trap.",
            "The sample temperature is neither actuated nor read, and the width goes as its square root. On the "
            "bench a kelvin of drift moves the width by a sixth of a per cent, far inside the target; in a confirm "
            "revision it will not be.",
        ],
    )
    card["status"] = "DRAFT"
    card.update(cards.tail(numbers, assumptions=assumptions,
                           kb_refs=synthesis.kb_refs_for(qid, numbers), kb_gaps=synthesis.kb_gaps_for(qid),
                           degraded=["librarian_agent"]))
    return card


def render(card: dict) -> str:
    """The Markdown twin. Every number it states is one the card holds (P3)."""
    N = {n["name"]: n for n in card["numbers"]}
    q = lambda name: f"{N[name]['value']:g} {N[name]['unit']}"
    L = [f"# {card['id']}: one trap at rest, the width a camera should see", "",
         f"*Generated from the JSON beside this file, which is authoritative (P3). Status: {card['status']}.*", "",
         f"One sphere of {q('bead_diameter')} in a harmonic trap of {q('trap_stiffness_operating')}, fluid at rest. "
         f"Timestep {q('integration_timestep_op')}, start-up {q('startup_discard_op')} discarded, then a record of "
         f"{q('record_length_op')} saved every {q('save_interval_op')}.", "",
         f"Predicted in-plane width: {q('thermal_width_op')}. Longest bench exposure without correction: "
         f"{q('camera_exposure_max_op')}.", "", "## Success criteria", ""]
    L += [f"- **{c['id']}**: {c['statement']}" for c in card["success_criteria"]]
    L += ["", "## Open risks", ""] + [f"- {r}" for r in card["open_risks"]] + [""]
    return "\n".join(L)


def emit(qid: str, created_at: str, stage: str):
    directory = cards.question_dir(qid)
    revision = cards.question_revision(qid)
    if stage == "synthesis":
        path = directory / cards.artifact_name("synthesis.json", revision)
        cards.write(path, synthesis_card(qid, created_at, revision))
        return path, "written"
    card = plan(qid, created_at, revision)
    json_path = directory / cards.artifact_name(f"plan_simulation_{qid}.json", revision)
    md_path = json_path.with_suffix(".md")
    cards.refuse_overwrite(json_path, revision, card)
    cards.write(json_path, card)
    md_path.write_text(render(card))
    verdict = subprocess.run([sys.executable, str(cards.CONTRACTS / "validate.py"), "--quiet"],
                             capture_output=True, text=True)
    if verdict.returncode == 0:
        card["status"] = "VALIDATED"
        cards.write(json_path, card)
        md_path.write_text(render(card))
        return json_path, "VALIDATED"
    tail = verdict.stdout.strip().splitlines()[-1] if verdict.stdout.strip() else "see validate.py"
    return json_path, f"DRAFT (validator exit {verdict.returncode}; {tail})"


if __name__ == "__main__":
    path, status = emit(sys.argv[1], sys.argv[2], sys.argv[3])
    print(Path(path).relative_to(cards.REPO), status)
