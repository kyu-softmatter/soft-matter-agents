"""`bd_overdamped` for one observable only: `bleach_recovery_diffusivity`.

The configuration produces two observables (contracts/capabilities/simulation.json):
`tracer_diffusivity`, whose axis bodies, operating point, plan and result
are the shared files' and predate this module, and `bleach_recovery_diffusivity`,
whose are here. **Every hook in this file hands a tracer_diffusivity goal
back untouched**: `build` and `build_plan` return None, `plan_queries`
returns [], and `render_plan` calls `plan_card.render`. `operating_point` and
`applicable` are deliberately not defined. `configs.operating_point` passes
no goal, so a definition here could not tell the two observables apart and
would replace the tracer table for every bd_overdamped question. S4 for a
bleach goal is `python -m src.config_bd_overdamped synthesis` instead.

    cd simulation_agent
    python -m src.fanout <qid> <created_at>                        # S3, six axis cards
    python -m src.config_bd_overdamped synthesis <qid> <created_at>  # S4
    python -m src.plan_card <qid> <created_at>                     # S5, DRAFT -> VALIDATED
    python -m src.operator <qid> <run_id> <point> smoke|full <seed>  # S6
    python -m src.config_bd_overdamped result <run_id> [<run_id> ...] # the result card

**What the axes own here, and why it differs from the tracer path.**
- A1: the free Gaussian step is exact at any dt, so there is no stability
  bound. What the step must resolve is the bleach, a time-dependent sink
  applied once per step.
- A2: curves times beads, not displacements at a lag.
- A3: the box against the disc (the registered estimator's 10 w), not
  against a tracer's periodic image.
- A4: the frame interval, bleach length and record length, from the
  registered estimator's three refusal bounds on tau.
- A5: the same ceilings over particle-steps. Every step is read out, so the
  rate counts both terms (integration and readout) together.
- A7: abstains, because nothing is driven.

All of them hold `degraded: ["librarian_agent"]`. The axes made no calls,
because what they need is either on the goal (whose calls are logged under
`<qid>:v<N>:s2`) or in the registered estimator. A card that asked nothing
must not claim the service answered it.
"""

from __future__ import annotations

import itertools
import json
import math
import sys

from . import cards, synthesis

OBSERVABLE = "bleach_recovery_diffusivity"
CONFIG = "bd_overdamped"
SPEC = "spec:contracts/observables.json:bleach_recovery_diffusivity"
BEAD_LEVELS = (10, 30, 100, 300, 1000)
BASE_LEVEL = 300

MODEL = (
    "non-interacting spheres in overdamped Brownian motion in a periodic box, three-dimensional, "
    "no pair potential, no wall. A uniform disc is bleached as a column through the whole depth by "
    "labelling beads, not by any force: the label changes nothing about how a bead moves. The "
    "depth-projected count of unbleached beads inside the disc is read as a camera would read it"
)


def _goal_is_ours(goal: dict) -> bool:
    return (goal.get("observable") or {}).get("name") == OBSERVABLE


# --------------------------------------------------------------------------- #
# S3 -- the axis cards
# --------------------------------------------------------------------------- #


def plan_queries(qid: str, revision: int, config: str, issue) -> list:
    goal = cards.load_goal(qid, revision)
    if not _goal_is_ours(goal):
        return []
    raise SystemExit(
        f"{qid}'s axes make no store calls: what they need is on the goal, whose calls are logged "
        f"under {qid}:v{revision}:s2, or in the registered estimator. Each axis card says "
        "degraded: [\"librarian_agent\"] rather than claim an answer nobody gave. Run the fan-out "
        "without --queries."
    )


def _interval(parameter, unit, *, lo=None, hi=None, basis):
    iv = {"parameter": parameter, "unit": unit, "basis": basis, "precision": "order_of_magnitude"}
    if lo is not None:
        iv["min"] = lo
    if hi is not None:
        iv["max"] = hi
    return iv


def build(axis: str, qid: str, config: str, created_at: str, caller_id: str, kb_version: str,
          kb_result, revision: int):
    goal = cards.load_goal(qid, revision)
    if not _goal_is_ours(goal):
        return None
    head = cards.head(
        "axis", f"axis-{qid}-{config}-{axis}" + ("" if revision == 1 else f"-r{revision}"), qid,
        created_at, revision=revision, caller_id=caller_id, config=config, axis=axis,
        kb_version=kb_version,
    )
    body = {"a1": _a1, "a2": _a2, "a3": _a3, "a4": _a4, "a5": _a5, "a7": _a7}[axis](goal)
    head.update({k: v for k, v in body.items() if k not in ("numbers", "assumptions", "note")})
    head.update(cards.tail(body["numbers"], assumptions=body["assumptions"], kb_refs=[], kb_gaps=[],
                           degraded=["librarian_agent"]))
    head["note"] = body["note"]
    return head


def _carry(goal, *names):
    return cards.carry(goal, list(names))


def _grades(numbers):
    return {n["name"]: n["grade"] for n in numbers}


def _a1(goal):
    numbers, assumptions = _carry(goal, "recovery_time")
    numbers.append(cards.num(
        "steps_per_recovery_min", 100, "1", "assumed:a_bleach_resolution", precision="order_of_magnitude",
        note="engine steps per recovery time. The shortest bleach worth planning is a few hundredths "
             "of tau, and a few steps across it needs of order a hundred steps per tau"))
    g = _grades(numbers)
    numbers.append(cards.num(
        "integration_timestep_max", 0.006, "s", "computed:recovery_time_over_steps",
        formula="recovery_time/steps_per_recovery_min",
        inputs=[("recovery_time", g["recovery_time"]), ("steps_per_recovery_min", g["steps_per_recovery_min"])],
        precision="order_of_magnitude",
        note="the longest engine step. Not a stability bound: free Brownian increments are exact at any dt"))
    assumptions.append({
        "rationale_id": "a_bleach_resolution", "gap_ref": "bleach_step_resolution_absent",
        "statement": "The bleach is applied once per engine step, so a bleach a few steps long is a few "
                     "kicks rather than a continuous exposure. Four steps across the shortest bleach "
                     "worth running keeps the kick sequence close to continuous; the dt-halving point "
                     "of the plan measures whether it is.",
        "numbers": ["steps_per_recovery_min"],
        "falsifier": "a fitted D that moves by more than three standard errors when the step is halved"})
    iv = _interval("integration_timestep", "s", hi=0.006, basis=["integration_timestep_max"])
    return {
        "method": "llm_estimate", "verdict": "feasible", "constraints": [iv],
        "inequalities": [{
            "inequality": "dt <= recovery_time / steps_per_recovery_min: the step resolves the bleach, the "
                          "only time-dependent term; free diffusion itself sets no stability limit",
            "parameter": "integration_timestep", "state": "returned", "interval": iv}],
        "numbers": numbers, "assumptions": assumptions,
        "note": "bd_overdamped's tracer A1 bounds dt by curvature and the diffusive time. Neither enters "
                "here: there is no potential, and the bead size never appears in a column bleach",
    }


def _a2(goal):
    numbers = [
        cards.num("single_curve_spread", 0.5, "1", "assumed:a_single_curve_spread", precision="order_of_magnitude",
                  note="relative standard deviation of D over single curves at a few hundred beads: a guess, "
                       "and the quantity the scatter points of the plan measure"),
        cards.num("target_relative_error", 0.07, "1", "assumed:a_target_error", precision="order_of_magnitude",
                  note="the relative standard error wanted on one point's MEAN D, so that a point can be set "
                       "against the deterministic prediction. Not the person's target, which is a decade"),
    ]
    g = _grades(numbers)
    numbers.append(cards.num(
        "n_curves_min", 50, "1", "computed:spread_over_target_squared",
        formula="(single_curve_spread/target_relative_error)**2",
        inputs=[("single_curve_spread", g["single_curve_spread"]),
                ("target_relative_error", g["target_relative_error"])],
        precision="order_of_magnitude",
        note="independent curves per point; each curve starts from a fresh uniform draw, an exact "
             "equilibrium sample for non-interacting beads, so curves are independent by construction"))
    iv = _interval("n_curves", "1", lo=50, basis=["n_curves_min"])
    return {
        "method": "llm_estimate", "verdict": "feasible", "constraints": [iv],
        "inequalities": [{
            "inequality": "n_curves >= (single_curve_spread / target_relative_error)^2",
            "parameter": "n_curves", "state": "returned", "interval": iv}],
        "numbers": numbers,
        "assumptions": [
            {"rationale_id": "a_single_curve_spread", "gap_ref": "single_curve_spread_absent",
             "statement": "One curve's D scatters by about half its value at a few hundred beads, from "
                          "counting noise of order one over the square root of the bead count, correlated "
                          "over a recovery time.",
             "numbers": ["single_curve_spread"],
             "falsifier": "the measured spread over curves at the base point replaces it"},
            {"rationale_id": "a_target_error", "gap_ref": "target_relative_error_absent",
             "statement": "A few per cent on a point's mean separates a bias of ten per cent from noise, "
                          "which is the size the finite bleach and frame are expected to cause.",
             "numbers": ["target_relative_error"],
             "falsifier": "a bias comparison that cannot be resolved at this error raises the curve count"},
        ],
        "note": "The spread of single curves is the result the scatter question asks for, so it is "
                "assumed here only to size the record and is then measured, not inherited",
    }


def _a3(goal):
    numbers, assumptions = _carry(goal, "bleach_radius")
    numbers.append(cards.num(
        "box_to_radius_min", 10, "1", SPEC, precision="significant_figures",
        note="the registered estimator: the engine's box is periodic and at least 10 w across"))
    g = _grades(numbers)
    numbers.append(cards.num(
        "box_length_min", 30, "um", "computed:ten_disc_radii", formula="box_to_radius_min*bleach_radius",
        inputs=[("box_to_radius_min", g["box_to_radius_min"]), ("bleach_radius", g["bleach_radius"])],
        precision="significant_figures",
        note="the lateral box edge. The finite reservoir sets the plateau at one minus the bleached "
             "amount over the box area, which the free Finf of the fit absorbs and the result states"))
    iv = _interval("box_length", "um", lo=30, basis=["box_length_min"])
    return {
        "method": "deterministic", "verdict": "feasible", "constraints": [iv],
        "inequalities": [{
            "inequality": "box_length >= 10 * bleach_radius (the registered estimator), so the reservoir "
                          "outside the disc is much larger than the disc",
            "parameter": "box_length", "state": "returned", "interval": iv}],
        "numbers": numbers, "assumptions": assumptions,
        "note": "No image bound: the signal is a count of labels inside a disc, not a displacement, so "
                "a bead crossing the periodic edge carries nothing wrong into it. The chamber depth is "
                "the experiment's and only sets how many beads one curve counts",
    }


def _a4(goal):
    numbers, assumptions = _carry(goal, "recovery_time")
    for name, value, note in (
        ("frame_fraction_max", 0.2, "the registered estimator: frame interval <= tau/5"),
        ("bleach_fraction_max", 0.1, "the registered estimator: bleach duration <= tau/10"),
        ("window_multiple_min", 10, "the registered estimator: max_recovery_time >= 10 tau"),
    ):
        numbers.append(cards.num(name, value, "1", SPEC, precision="significant_figures", note=note))
    numbers.append(cards.num(
        "pre_bleach_frames_min", 10, "1", "assumed:a_pre_frames", precision="order_of_magnitude",
        note="frames before the bleach, whose mean normalises the curve"))
    g = _grades(numbers)
    rt = ("recovery_time", g["recovery_time"])
    numbers.append(cards.num("frame_interval_max", 0.1, "s", "computed:recovery_time_times_fraction",
                             formula="recovery_time*frame_fraction_max",
                             inputs=[rt, ("frame_fraction_max", g["frame_fraction_max"])],
                             precision="significant_figures"))
    numbers.append(cards.num("bleach_duration_max", 0.06, "s", "computed:recovery_time_times_fraction",
                             formula="recovery_time*bleach_fraction_max",
                             inputs=[rt, ("bleach_fraction_max", g["bleach_fraction_max"])],
                             precision="significant_figures"))
    numbers.append(cards.num("max_recovery_time_min", 6, "s", "computed:recovery_time_times_multiple",
                             formula="recovery_time*window_multiple_min",
                             inputs=[rt, ("window_multiple_min", g["window_multiple_min"])],
                             precision="significant_figures"))
    ivs = [
        _interval("frame_interval", "s", hi=0.1, basis=["frame_interval_max"]),
        _interval("bleach_duration", "s", hi=0.06, basis=["bleach_duration_max"]),
        _interval("max_recovery_time", "s", lo=6, basis=["max_recovery_time_min"]),
        _interval("pre_bleach_frames", "1", lo=10, basis=["pre_bleach_frames_min"]),
    ]
    assumptions.append({
        "rationale_id": "a_pre_frames", "gap_ref": "pre_bleach_frames_absent",
        "statement": "Ten frames before the bleach put the counting error of the normalising mean at "
                     "about a third of one frame's, so normalisation adds little to a curve's scatter.",
        "numbers": ["pre_bleach_frames_min"],
        "falsifier": "a scatter that falls when the pre-bleach frames are doubled raises the count"})
    text = {
        "frame_interval": "frame_interval <= tau/5; a coarser frame resolves no recovery and the curve is a bound",
        "bleach_duration": "bleach_duration <= tau/10; a longer bleach refills while it bleaches",
        "max_recovery_time": "max_recovery_time >= 10 tau; the Soumpasis tail is slow (0.91 at 10 tau) and Finf is free",
        "pre_bleach_frames": "pre_bleach_frames >= 10, so the normalising mean is not the noisiest number in the curve",
    }
    return {
        "method": "llm_estimate", "verdict": "feasible", "constraints": ivs,
        "inequalities": [{"inequality": text[iv["parameter"]], "parameter": iv["parameter"],
                          "state": "returned", "interval": iv} for iv in ivs],
        "numbers": numbers, "assumptions": assumptions,
        "note": "The three bounds are the registered estimator's own refusals, applied here to the "
                "planned tau. The estimator applies them again to each curve's fitted tau, which a "
                "noisy curve can push outside them -- the refused fraction is a result",
    }


def _a5(goal):
    numbers = [
        cards.num("wall_clock_max", 2, "h", "spec:simulation_agent/envelope/budget.json:local",
                  precision="significant_figures", note="the ceiling a person chose (kyuhwan, 2026-09-19)"),
        cards.num("storage_max", 10, "GB", "spec:simulation_agent/envelope/budget.json:local",
                  precision="significant_figures", note="the disk ceiling of the same target"),
        cards.num("particle_step_rate", 10000000.0, "1/s", "assumed:a_cost_reference",
                  precision="order_of_magnitude",
                  note="particle-steps per second including the per-step readout, on one CPU core of this "
                       "MacBook. A scratch timing on 2026-09-30 read 8.7 million; no plan cites that "
                       "timing, so it stands here as an assumption the smoke run replaces"),
        cards.num("bytes_per_value", 8e-09, "GB", "spec:ieee754_double", precision="significant_figures",
                  note="one double, in the unit the ceiling is written in"),
    ]
    g = _grades(numbers)
    numbers.append(cards.num("particle_steps_max", 70000000000.0, "1", "computed:ceiling_times_rate",
                             formula="wall_clock_max*particle_step_rate",
                             inputs=[("wall_clock_max", g["wall_clock_max"]), ("particle_step_rate", g["particle_step_rate"])],
                             precision="order_of_magnitude",
                             note="n_particles * steps over every curve of every point may not exceed this"))
    numbers.append(cards.num("values_stored_max", 1000000000.0, "1", "computed:ceiling_over_bytes",
                             formula="storage_max/bytes_per_value",
                             inputs=[("storage_max", g["storage_max"]), ("bytes_per_value", g["bytes_per_value"])],
                             precision="order_of_magnitude",
                             note="no trajectory is kept: what is stored is one count per frame per curve"))
    ivs = [_interval("particle_steps", "1", hi=70000000000.0, basis=["particle_steps_max"]),
           _interval("values_stored", "1", hi=1000000000.0, basis=["values_stored_max"])]
    return {
        "method": "llm_estimate", "verdict": "feasible", "constraints": ivs,
        "inequalities": [
            {"inequality": "sum over points of n_particles * n_curves * steps_per_curve <= wall_clock_max * particle_step_rate",
             "parameter": "particle_steps", "state": "returned", "interval": ivs[0]},
            {"inequality": "frames stored <= storage_max / bytes_per_value", "parameter": "values_stored",
             "state": "returned", "interval": ivs[1]}],
        "numbers": numbers,
        "assumptions": [{"rationale_id": "a_cost_reference", "gap_ref": "particle_step_rate_absent",
                         "statement": "Of order ten million particle-steps a second with a readout every "
                                      "step: HOOMD's Brownian step without a neighbour list, and a NumPy "
                                      "pass over the positions to label and count.",
                         "numbers": ["particle_step_rate"],
                         "falsifier": "the smoke run's cost_measured event replaces it"}],
        "note": "A5 constrains products of the settable parameters and takes nothing from A1 or A2 "
                "(4.5.3 rule b). The two-term cost of task 023 collapses to one here because every step "
                "is read: the readout is inside the rate",
    }


def _a7(goal):
    return {
        "method": "deterministic", "verdict": "abstain",
        "abstain_reason": "Nothing is driven. bd_overdamped is undriven and the bleach is a label applied "
                          "to beads, not a force on them, so there is no driving amount for this axis to "
                          "bound. This card is the record that the axis was asked (P1).",
        "numbers": [], "assumptions": [],
        "note": "numbers[] is empty because an abstention on this axis has nothing to measure",
    }


# --------------------------------------------------------------------------- #
# S4 -- the synthesis
# --------------------------------------------------------------------------- #

LEVEL_POINT = {"dt": "integration_timestep_point", "dt2": "integration_timestep_half",
               "f30": "frame_interval_fast", "f12": "frame_interval_point", "f6": "frame_interval_slow",
               "b30": "bleach_duration_point", "b12": "bleach_duration_long"}

# The one-factor-at-a-time design: the base point, then each factor moved
# alone, then the corner where the two allowed extremes meet.
PERFORMED = [
    (10, "dt", "f12", "b30"), (30, "dt", "f12", "b30"), (100, "dt", "f12", "b30"),
    (300, "dt", "f12", "b30"), (1000, "dt", "f12", "b30"),
    (300, "dt2", "f12", "b30"),
    (300, "dt", "f30", "b30"), (300, "dt", "f6", "b30"),
    (300, "dt", "f12", "b12"),
    (300, "dt", "f6", "b12"),
]


def point_name(level, dt, f, b) -> str:
    return f"n{level}_{dt}_{f}_{b}"


def _steps_formula(dt, f, b):
    return (f"(pre_bleach_frames_min*{LEVEL_POINT[f]} + {LEVEL_POINT[b]} + max_recovery_time_point)"
            f"/{LEVEL_POINT[dt]}")


def build_synthesis(qid: str, created_at: str, revision: int) -> dict:
    goal = cards.load_goal(qid, revision)
    if not _goal_is_ours(goal):
        raise SystemExit(f"{qid} does not ask for {OBSERVABLE}; use python -m src.synthesis")
    group = synthesis.axis_cards(qid, CONFIG, revision)
    intersection, conflict = synthesis.intersect(group)
    per_config = [{"config": CONFIG, "empty": conflict is not None,
                   "axis_files": [f for f, _ in group]}]
    if conflict is not None:
        per_config[0]["conflict"] = conflict
        raise SystemExit(f"the axes of {CONFIG} do not intersect: {conflict['statement']}")
    per_config[0]["intersection"] = intersection

    A = lambda f: cards.artifact_name(f, revision)
    carry = [(A("goal.json"), n) for n in (
        "temperature", "viscosity", "bead_diameter", "diffusivity", "bleach_radius", "recovery_time",
        "chamber_depth", "bleach_rate", *[f"beads_in_disc_{k}" for k in BEAD_LEVELS])]
    carry += [(A(f"axis_{CONFIG}_a1.json"), "integration_timestep_max"),
              (A(f"axis_{CONFIG}_a2.json"), "n_curves_min"),
              (A(f"axis_{CONFIG}_a3.json"), "box_length_min"),
              (A(f"axis_{CONFIG}_a4.json"), "frame_interval_max"),
              (A(f"axis_{CONFIG}_a4.json"), "bleach_duration_max"),
              (A(f"axis_{CONFIG}_a4.json"), "max_recovery_time_min"),
              (A(f"axis_{CONFIG}_a4.json"), "pre_bleach_frames_min"),
              (A(f"axis_{CONFIG}_a5.json"), "particle_steps_max")]
    numbers = synthesis.carry_from(qid, CONFIG, carry)
    grades = _grades(numbers)

    def comp(name, value, unit, formula, inputs, note, precision="significant_figures"):
        n = cards.num(name, value, unit, f"computed:operating_point_of_{CONFIG}_bleach", formula=formula,
                      inputs=[(i, grades[i]) for i in inputs], precision=precision, note=note)
        numbers.append(n)
        grades[name] = n["grade"]
        return n

    comp("integration_timestep_point", 0.005, "s", "recovery_time/120", ["recovery_time"],
         "A1's ceiling exactly: a hundred and twenty steps per planned tau")
    comp("integration_timestep_half", 0.002, "s", "recovery_time/300", ["recovery_time"],
         "a step two and a half times finer, for the integrator check; it divides the base frame and bleach")
    comp("frame_interval_point", 0.05, "s", "recovery_time/12", ["recovery_time"],
         "a twelfth of tau, comfortably inside A4's fifth, so a curve whose fitted tau comes out "
         "short is still read")
    comp("frame_interval_fast", 0.02, "s", "recovery_time/30", ["recovery_time"],
         "a faster camera, for the finite-frame bias")
    comp("frame_interval_slow", 0.1, "s", "recovery_time/6", ["recovery_time"],
         "near A4's ceiling of a fifth of tau, for the finite-frame bias at the edge it allows")
    comp("bleach_duration_point", 0.02, "s", "recovery_time/30", ["recovery_time"],
         "a thirtieth of tau, four steps")
    comp("bleach_duration_long", 0.05, "s", "recovery_time/12", ["recovery_time"],
         "near A4's ceiling of a tenth of tau, for the finite-bleach bias at the edge it allows")
    comp("max_recovery_time_point", 9, "s", "15*recovery_time", ["recovery_time"],
         "fifteen planned taus, 1.5 times A4's floor, so a curve whose fitted tau comes out half again "
         "as long is still inside the estimator's window bound")
    comp("box_length_point", 30, "um", "box_length_min", ["box_length_min"], "A3's floor exactly")
    comp("n_curves_point", 50, "1", "n_curves_min", ["n_curves_min"],
         "A2's floor exactly")
    comp("curve_period", 20, "s", "2*max_recovery_time_point", ["max_recovery_time_point"],
         "a bookkeeping period per curve, longer than any point's curve (at most ten seconds of pre-bleach "
         "frames, bleach and record); only the steps a curve needs are integrated, so the period costs "
         "nothing. A smoke run shortens the record by curves, not by time per curve")
    comp("record_length_point", 1000, "s", "n_curves_point*curve_period", ["n_curves_point", "curve_period"],
         "curves times the curve period: a count of curves in the unit of the record")

    for k in BEAD_LEVELS:
        val = int(float(f"{k * 30.0**2 / (math.pi * 3.0**2):.1g}"))
        comp(f"n_particles_{k}", val, "1",
             f"beads_in_disc_{k}*box_length_point**2/(pi*bleach_radius**2)",
             [f"beads_in_disc_{k}", "box_length_point", "bleach_radius"],
             f"about {k} beads in the disc ({val * math.pi * 9 / 900:.3g} exactly at this count), at the "
             "uniform density this many particles have in the box")

    total = 0.0
    for level, dt, f, b in PERFORMED:
        nm = point_name(level, dt, f, b)
        steps = ((10 * float(_val(numbers, LEVEL_POINT[f])) + float(_val(numbers, LEVEL_POINT[b]))
                  + 9.0) / float(_val(numbers, LEVEL_POINT[dt])))
        ps = float(_val(numbers, f"n_particles_{level}")) * 50 * steps
        total += ps
        comp(f"particle_steps_{nm}", float(f"{ps:.1g}"), "1",
             f"n_particles_{level}*n_curves_point*{_steps_formula(dt, f, b)}",
             [f"n_particles_{level}", "n_curves_point", "pre_bleach_frames_min", LEVEL_POINT[f], LEVEL_POINT[b],
              "max_recovery_time_point", LEVEL_POINT[dt]],
             "particle-steps this point costs", precision="order_of_magnitude")
    comp("particle_steps_total", float(f"{total:.1g}"), "1",
         " + ".join(f"particle_steps_{point_name(*p).replace('-', '_')}" for p in PERFORMED),
         [f"particle_steps_{point_name(*p).replace('-', '_')}" for p in PERFORMED],
         "the sum over points, against A5's ceiling of 7e10", precision="order_of_magnitude")

    rejected = [
        {"what": "a full product grid of bead count x timestep x frame x bleach", "kind": "operating_point",
         "reason": "sixty cells for questions that each move one factor; the base point and one move per "
                   "factor answer them, and the corner tests the two allowed extremes together",
         "grounds": ["particle_steps_total", "particle_steps_max"]},
        {"what": "frame and bleach lengths beyond A4's ceilings", "kind": "operating_point",
         "reason": "the estimator refuses such curves as one-sided bounds; a point there measures the "
                   "refusal and not the bias, and A4's interval excludes it",
         "grounds": ["frame_interval_max", "bleach_duration_max"]},
        {"what": "a disc larger than 3 um", "kind": "operating_point",
         "reason": "in units of tau and w the problem is scale-free: at a fixed bleach/tau, frame/tau, "
                   "k*tau and beads per disc the curve and its bias are the same at any w, so a larger "
                   "disc needs no run of its own; the first stage's closed form gives tau at any w",
         "grounds": ["bleach_radius", "recovery_time"]},
    ]
    card = cards.head(
        "synthesis", f"synthesis-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, configs_screened=[CONFIG], per_config=per_config, chosen_config=CONFIG,
        operating_point=[
            {"parameter": "box_length", "number": "box_length_point"},
            {"parameter": "max_recovery_time", "number": "max_recovery_time_point"},
            {"parameter": "record_length", "number": "record_length_point"},
            {"parameter": "integration_timestep", "number": "integration_timestep_point"},
            {"parameter": "frame_interval", "number": "frame_interval_point"},
            {"parameter": "bleach_duration", "number": "bleach_duration_point"},
            {"parameter": "n_particles", "number": f"n_particles_{BASE_LEVEL}"},
        ],
        priority_used=goal.get("priority"), priority_source="goal_card", rejected=rejected,
    )
    gaps = {}
    for _, c in group:
        for gp in c.get("kb_gaps") or []:
            gaps.setdefault(gp["gap_id"], gp)
    card.update(cards.tail(numbers, assumptions=synthesis.assumptions_for(qid, numbers),
                           kb_refs=synthesis.kb_refs_for(qid, numbers),
                           kb_gaps=synthesis.kb_gaps_for(qid),
                           degraded=["librarian_agent"]))
    return card


def _val(numbers, name):
    return next(n["value"] for n in numbers if n["name"] == name)


# --------------------------------------------------------------------------- #
# S5 -- the plan
# --------------------------------------------------------------------------- #


def build_plan(qid: str, created_at: str, revision: int = 1):
    goal = cards.load_goal(qid, revision)
    if not _goal_is_ours(goal):
        return None
    from . import plan_card                                # noqa: PLC0415

    syn_name = cards.artifact_name("synthesis.json", revision)
    syn = json.loads((cards.question_dir(qid) / syn_name).read_text())
    # The bead-count levels stay on the synthesis: the plan runs particle
    # counts, and each carried n_particles_<k> points back at where it was made.
    wanted = [n["name"] for n in syn["numbers"] if not n["name"].startswith("beads_in_disc_")]
    numbers = synthesis.carry_from(qid, CONFIG, [(syn_name, n) for n in wanted])
    a5 = cards.artifact_name(f"axis_{CONFIG}_a5.json", revision)
    numbers += synthesis.carry_from(qid, CONFIG, [(a5, "particle_step_rate"), (a5, "bytes_per_value")])
    grades = _grades(numbers)

    numbers.append(cards.num(
        "wall_clock_estimate", float(f"{float(_val(numbers, 'particle_steps_total')) / 1e7:.1g}"), "s",
        "computed:particle_steps_over_rate", formula="particle_steps_total/particle_step_rate",
        inputs=[("particle_steps_total", grades["particle_steps_total"]),
                ("particle_step_rate", grades["particle_step_rate"])],
        precision="order_of_magnitude",
        note="the whole sweep on one core; the rate is A5's assumption and the smoke run measures it"))
    numbers.append(cards.num(
        "values_stored_point", 100000, "1", "computed:frames_times_curves_times_points",
        formula="10*n_curves_point*(pre_bleach_frames_min + max_recovery_time_point/frame_interval_point)",
        inputs=[(n, grades[n]) for n in ("n_curves_point", "pre_bleach_frames_min", "max_recovery_time_point",
                                         "frame_interval_point")],
        precision="order_of_magnitude",
        note="one bright count per frame per curve over the ten points, kept in observables.json; no "
             "position is stored"))
    grades["values_stored_point"] = numbers[-1]["grade"]
    numbers.append(cards.num(
        "storage_estimate", 0.0008, "GB", "computed:values_times_bytes",
        formula="values_stored_point*bytes_per_value",
        inputs=[("values_stored_point", grades["values_stored_point"]), ("bytes_per_value", grades["bytes_per_value"])],
        precision="order_of_magnitude", note="no trajectory is written"))
    numbers.append(cards.num("smoke_record_fraction", 0.1, "1", "assumed:a_run_design", precision="significant_figures",
                             note="a smoke run of one point runs a tenth of its curves"))
    numbers.append(cards.num("agreement_z_max", 3, "1", "assumed:a_run_design", precision="significant_figures",
                             note="a point agrees with the deterministic prediction when its mean D lies "
                                  "within three standard errors of it"))
    assumptions = synthesis.assumptions_for(qid, [n for n in numbers if "origin" in n]) + [
        {"rationale_id": "a_run_design", "gap_ref": "run_design_choices_absent",
         "statement": "Two choices of how the runs are checked, which nothing measured: a smoke run of a "
                      "tenth of a point's curves sees the run work end to end inside the five-minute "
                      "smoke ceiling, and three standard errors separates a real difference from the "
                      "scatter of fifty curves at about the one-in-four-hundred level.",
         "numbers": ["smoke_record_fraction", "agreement_z_max"],
         "falsifier": "a smoke run over its ceiling, or a point that disagrees and agrees when re-run"},
    ]

    axes = [
        {"parameter": "n_particles", "levels": [f"n_particles_{k}" for k in BEAD_LEVELS]},
        {"parameter": "integration_timestep", "levels": ["integration_timestep_point", "integration_timestep_half"]},
        {"parameter": "frame_interval", "levels": ["frame_interval_fast", "frame_interval_point", "frame_interval_slow"]},
        {"parameter": "bleach_duration", "levels": ["bleach_duration_point", "bleach_duration_long"]},
    ]
    performed = set(PERFORMED)
    points = []
    for level, dt, f, b in itertools.product(BEAD_LEVELS, ("dt", "dt2"), ("f30", "f12", "f6"), ("b30", "b12")):
        pt = {"point": point_name(level, dt, f, b), "conditions": [
            {"parameter": "n_particles", "number": f"n_particles_{level}"},
            {"parameter": "integration_timestep", "number": LEVEL_POINT[dt]},
            {"parameter": "frame_interval", "number": LEVEL_POINT[f]},
            {"parameter": "bleach_duration", "number": LEVEL_POINT[b]},
        ]}
        if (level, dt, f, b) not in performed:
            pt["skipped"] = ("one factor at a time: this cell moves more than one factor away from the "
                             "base point n300_dt_f12_b30 and is not the declared corner")
        points.append(pt)

    conditions = [
        {"parameter": "temperature", "number": "temperature"},
        {"parameter": "viscosity", "number": "viscosity"},
        {"parameter": "bead_diameter", "number": "bead_diameter"},
        {"parameter": "bleach_radius", "number": "bleach_radius"},
        {"parameter": "box_length", "number": "box_length_point"},
        {"parameter": "chamber_depth", "number": "chamber_depth"},
        {"parameter": "bleach_rate", "number": "bleach_rate"},
        {"parameter": "max_recovery_time", "number": "max_recovery_time_point"},
        {"parameter": "pre_bleach_frames", "number": "pre_bleach_frames_min"},
        {"parameter": "record_length", "number": "record_length_point"},
        {"parameter": "curve_period", "number": "curve_period"},
    ]
    params = [c["parameter"] for c in conditions] + [a["parameter"] for a in axes]
    card = cards.head(
        "plan", f"plan-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, goal_id=goal["id"], synthesis_id=syn["id"], purpose=goal["purpose"],
        intent=goal["intent"], observable=cards.observable(OBSERVABLE),
        system_configuration={"config": CONFIG, "optical_path": None, "devices": ["hoomd_backend"],
                              "model": MODEL},
        targets=[dict(t) for t in goal.get("targets", [])],
        sweep={"axes": axes, "points": points},
        conditions=conditions,
        actions=[
            {"id": "integrate", "device": "hoomd_backend", "reversible": True, "tier": 1,
             "action": "integrate independent curves of free overdamped motion, each from a fresh uniform "
                       "draw, reading the beads' xy positions at every step",
             "parameters": params},
            {"id": "estimate_recovery", "device": "hoomd_backend", "reversible": True, "tier": 0,
             "action": "label beads dark inside the disc during the bleach, sample the depth-projected "
                       "bright count as an integrating camera, and apply the registered estimator to "
                       "each curve: half-contrast w, Soumpasis fit, D = w^2/(4 tau), refusals on tau",
             "parameters": ["bleach_radius", "bleach_rate", "bleach_duration", "frame_interval",
                            "max_recovery_time", "pre_bleach_frames"]},
        ],
        envelope_check=plan_card.envelope_check(numbers),
        cost={"wall_clock": "about 6e9 particle-steps over ten points on one core, of order ten minutes "
                            "at the assumed rate; points run in parallel on at most four cores",
              "numbers": ["wall_clock_estimate", "storage_estimate"],
              "note": "the rate is A5's assumption; each run's cost_measured event replaces it"},
        stop_criteria=[
            {"id": "planned_record_reached", "metric": "record_time_completed", "comparator": ">=",
             "number": "record_length_point", "on_met": "complete",
             "statement": "stop when the planned number of curves has run; the record is curves times "
                          "the curve period"},
            {"id": "step_displacement_diverged", "metric": "max_single_step_displacement", "comparator": ">",
             "number": "bleach_radius", "on_met": "fault",
             "statement": "a bead moving more than the disc radius in one step is a broken integration; "
                          "stop and keep the run, because divergence is a result"},
        ],
        smoke={"record_fraction": "smoke_record_fraction"},
        success_criteria=[
            {"id": "agrees_with_solver", "metric": "deviation_from_solver_in_standard_errors",
             "comparator": "<=", "number": "agreement_z_max", "window": "over the curves of one point",
             "statement": "the point's mean fitted D lies within three standard errors of what the "
                          "diffusion equation predicts for the same bleach, camera and fit; this is the "
                          "integrator check, and it is against the solver and not against Stokes-Einstein"},
            {"id": "dt_halving_unchanged", "metric": "dt_halving_deviation_in_standard_errors",
             "comparator": "<=", "number": "agreement_z_max", "window": "base point against its half-step twin",
             "statement": "halving the engine step moves the mean fitted D by no more than three combined "
                          "standard errors"},
        ],
        alternatives_rejected=[{"what": r["what"], "reason": r["reason"], "grounds": r["grounds"]}
                               for r in syn.get("rejected", [])],
        open_risks=[
            "The run's D is fixed by its inputs (the configuration says so): it checks the integrator, "
            "the bleach and the estimator, and says nothing independent about the beads.",
            "The bleach rate is a guess. It sets how deep the dip is, which sets how noisy one curve is; "
            "a slower real bleach makes every point here an optimistic case.",
            "No imaging bleach, no background, no drift and no walls are modelled. The reference ratio and "
            "background the estimator applies are identities here. At large discs, where the record runs "
            "for minutes, these are what bind first, and none of them is in this model.",
            "The camera is ideal: it counts beads, with no point-spread function, no shot noise from "
            "photons and no pixel grid. Counting noise is the only noise.",
        ],
    )
    card["status"] = "DRAFT"
    card.update(cards.tail(numbers, assumptions=assumptions,
                           kb_refs=synthesis.kb_refs_for(qid, [n for n in numbers if "origin" in n]),
                           kb_gaps=synthesis.kb_gaps_for(qid), degraded=["librarian_agent"]))
    return card


def render_plan(card: dict) -> str:
    if (card.get("observable") or {}).get("name") != OBSERVABLE:
        from . import plan_card                            # noqa: PLC0415
        return plan_card.render(card)
    nums = {n["name"]: n for n in card["numbers"]}
    q = lambda name: f"{nums[name]['value']:g} {nums[name]['unit']}"
    L = [f"# {card['id']} — bleach recovery of 100 nm beads, on the model",
         "", "*Generated from the JSON card beside this file. If the two disagree the JSON wins.*", "",
         f"**Status** {card['status']}  ·  **Configuration** {card['system_configuration']['config']}", "",
         "## The model", "", card["system_configuration"]["model"], "",
         "## What every point shares", "", "| parameter | value |", "|---|---|"]
    for c in card["conditions"]:
        L.append(f"| `{c['parameter']}` | {q(c['number'])} |")
    L += ["", "## The points that run", "", "| point | beads in disc | step | frame | bleach |", "|---|---|---|---|---|"]
    for pt in card["sweep"]["points"]:
        if pt.get("skipped"):
            continue
        c = {x["parameter"]: x["number"] for x in pt["conditions"]}
        lvl = c["n_particles"].split("_")[-1]
        L.append(f"| {pt['point']} | {lvl} | {q(c['integration_timestep'])} | {q(c['frame_interval'])} | "
                 f"{q(c['bleach_duration'])} |")
    skipped = sum(1 for pt in card["sweep"]["points"] if pt.get("skipped"))
    L += ["", f"{skipped} further cells of the grid are listed as skipped, each with its reason.", "",
          "## What would make this a failure", ""]
    for c in card["success_criteria"]:
        L.append(f"- **{c['id']}** — {c['statement']}")
    L += ["", "## What was considered and dropped", ""]
    for r in card["alternatives_rejected"]:
        L.append(f"- **{r['what']}** — {r['reason']}")
    L += ["", "## What this run cannot settle", ""]
    L += [f"- {r}" for r in card["open_risks"]]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- #
# the result
# --------------------------------------------------------------------------- #


def build_result(run_ids: list[str], kb_answer: dict | None = None) -> dict:
    """The result card: the first run id is the card's run, and the readings of
    every other run of the same plan revision ride along under their own run
    ids, so the one card the bridge carries holds the whole sweep.

    The numbers are `report_bleach.collect`'s, so the card and the person's
    report cannot disagree. Two comparisons sit side by side, and only the
    first was declared before the runs:

    - DECLARED: the mean of single-curve fits against the solver
      (`agrees_with_solver`, evaluated as written). At a few hundred beads
      the fit's refusals remove the slow curves, so this mean is selected
      and reads high. That is a property of averaging single-curve reads,
      and the card says so rather than redefining the criterion.
    - ADDED AFTER THE DATA, labelled in every note: the mean curve against
      the equation frame by frame, and one fit to the mean curve with a
      jackknife error over curves where the run saved its curves.
    """
    from contracts.validate import vocabulary_version      # noqa: PLC0415

    from . import report_bleach, result_card              # noqa: PLC0415

    runs = {r: result_card.read_run(r) for r in run_ids}
    first = runs[run_ids[0]]
    plan, plan_path = result_card.plan_of(first)
    for rid, r in runs.items():
        if r["config"]["plan_hash"] != first["config"]["plan_hash"]:
            raise SystemExit(f"{rid} ran a different plan")
    qid = first["config"]["qid"]
    points = report_bleach.collect(run_ids)
    threshold_beads = report_bleach.threshold(points)["beads_where_spread_is_a_tie"]
    by_run = {p["run_id"]: p for p in points.values()}
    numbers: list[dict] = []
    for name in ("temperature", "viscosity", "bead_diameter", "diffusivity", "bleach_radius",
                 "recovery_time", "bleach_rate", "agreement_z_max", "record_length_point"):
        numbers.append(result_card.carried(plan, plan_path, name))
    inputs = [n for n in numbers if n["name"] in ("temperature", "viscosity", "bead_diameter", "bleach_rate")]

    def reading(name, value, unit, rid, note, graded=True):
        n = result_card.reading(name, value, unit, rid, inputs if graded else [], note)
        numbers.append(n)
        return name

    criteria, deviations = [], []
    z_max = float(_val(numbers, "agreement_z_max"))
    declared_z = []
    for rid in run_ids:
        p = by_run[rid]
        tag = rid.replace("run-20260930-401-", "").replace("-", "_")
        if p.get("ratio_mean") is None:
            continue
        spread = (f"; one curve's middle 90 per cent over every fitted curve {p['all_p05']:.2g} to "
                  f"{p['all_p95']:.2g} of the value put in (x{p['all_spread_factor_90']:.2g})"
                  if p.get("all_spread_factor_90") else "")
        curve = (f"; ADDED AFTER THE DATA: the mean curve lies within {p['curve_z_max']:.2g} standard errors of "
                 f"the equation at every frame, and one fit to it reads {p['mean_curve_ratio']:.3f}"
                 + (f" +/- {p['mean_curve_ratio_se']:.3f} (jackknife over curves)" if p.get("mean_curve_ratio_se") else "")
                 if p.get("curve_z_max") is not None and p.get("mean_curve_ratio") else "")
        pr = reading(f"predicted_ratio_{tag}", float(f"{p['predicted_ratio']:.3g}"), "1", rid,
                     "what the fit reads on the diffusion equation solved at this run's own bleach, camera, box "
                     "and fit (bleach_solver) -- deterministic, not from the particle engine", graded=False)
        rr = reading(f"read_ratio_{tag}", float(f"{p['ratio_mean']:.3g}"), "1", rid,
                     f"mean D of the {p['n_reported']} curves the fit read, of {p['n_curves']}, over the value put "
                     f"in; standard error {p['ratio_sem']:.3f}; {p['beads_in_disc']:.0f} beads in the disc"
                     + spread + curve, graded=False)
        z = p.get("z_vs_solver")
        if z is not None:
            declared_z.append((z, tag))
        deviations.append({"parameter": f"read_against_solver_{tag}", "planned_number": pr, "actual_number": rr,
                           "within_tolerance": bool(z is not None and z <= z_max),
                           "note": f"{rid}: the declared comparison, {z:.3g} standard errors apart against a "
                                   "tolerance of three. Where the fit refuses many curves the kept ones are a "
                                   "selected set and their mean is pulled away from the prediction; the note on "
                                   "the reading gives the curve-level comparison, which no selection biases"})
    if declared_z:
        worst_z, worst_tag = max(declared_z)
        reading("deviation_from_solver_in_standard_errors", float(f"{worst_z:.3g}"), "1",
                f"run-20260930-401-{worst_tag.replace('_', '-')}",
                f"the largest declared deviation over the {len(declared_z)} runs, at {worst_tag}; "
                f"{sum(1 for z, _ in declared_z if z > z_max)} of them exceed three", graded=False)
    meta_ok = all(r["meta"].get("completed_planned_duration") for r in runs.values())
    period = float(first["config"]["parameters_si"]["curve_period"])
    curves_run = min(by_run[r]["n_curves"] for r in run_ids)
    reading("record_time_completed", curves_run * period, "s", run_ids[0],
            f"the fewest curves any run completed ({curves_run}) times the {period:g} s curve period; "
            "every run completed its planned record", graded=False)
    criteria.append({"id": "planned_record_reached", "kind": "stop", "met": meta_ok,
                     "observed_number": "record_time_completed"})
    max_step = max(float(r["meta"].get("max_single_step_displacement") or 0) for r in runs.values())
    numbers.append(cards.num("max_single_step_displacement", float(f"{max_step * 1e6:.1g}"), "um",
                             f"simulated:{run_ids[0]}", precision="order_of_magnitude",
                             note="the largest one-step move over every run, against a 3 um disc; not met is the good outcome"))
    criteria.append({"id": "step_displacement_diverged", "kind": "stop", "met": bool(max_step > 3e-6),
                     "observed_number": "max_single_step_displacement"})
    if declared_z:
        criteria.append({"id": "agrees_with_solver", "kind": "success",
                         "met": bool(all(z <= z_max for z, _ in declared_z)),
                         "observed_number": "deviation_from_solver_in_standard_errors"})
    else:
        criteria.append({"id": "agrees_with_solver", "kind": "success", "met": None,
                         "why_unevaluated": "no point produced a mean over read curves"})
    base, finer = points.get("n300_dt_f12_b30"), points.get("n300_dt2_f12_b30")
    if base and finer and base.get("ratio_sem") and finer.get("ratio_sem"):
        zz = abs(base["ratio_mean"] - finer["ratio_mean"]) / math.hypot(base["ratio_sem"], finer["ratio_sem"])
        reading("dt_halving_deviation_in_standard_errors", float(f"{zz:.2g}"), "1", base["run_id"],
                "base point against its finer-step twin, means of the read curves", graded=False)
        criteria.append({"id": "dt_halving_unchanged", "kind": "success", "met": bool(zz <= z_max),
                         "observed_number": "dt_halving_deviation_in_standard_errors"})
    else:
        criteria.append({"id": "dt_halving_unchanged", "kind": "success", "met": None,
                         "why_unevaluated": "the base point or its finer-step twin is not among the runs given"})

    card = cards.head(
        "result", f"result-{qid}-{run_ids[0]}", qid, first["log"]["finished_at"],
        revision=int(first["config"]["plan_revision"]),
        plan_id=plan["id"], plan_revision=int(first["config"]["plan_revision"]),
        plan_hash=first["config"]["plan_hash"], approval_id=None, run_id=run_ids[0],
        observable=cards.observable(OBSERVABLE),
        outcome=result_card.outcome_of(first["meta"]),
        values=[{"metric": OBSERVABLE, "number": "diffusivity", "uncertainty": None}],
        criteria_evaluation=criteria, deviations=deviations,
        time_base=result_card.time_base(first["log"]),
        estimation={"vocabulary_version": vocabulary_version(), "followed": True,
                    "note": "estimator_bleach.estimate, the registered steps; background 0 and reference "
                            "ratio 1 are identities in the engine and were applied. WHAT THE RUNS FOUND, in "
                            "full in stage2_runs.json and stage2_runs.md beside this card: one bleach needs "
                            f"about {int(float(f'{threshold_beads:.1g}'))} beads in the disc before its D is "
                            "inside a factor of ten (90 per cent of single curves); below that most curves are "
                            "refused. Averaging single-curve D is biased by those refusals; average the curves, "
                            "then fit once" if threshold_beads else
                            "estimator_bleach.estimate, the registered steps"},
    )
    card["status"] = "DONE" if card["outcome"] == "DONE" else "FAILED"
    for n in numbers:
        if n["name"] == "bead_diameter":
            n["note"] = (n.get("note", "") + ". THE VALUE DID NOT CHANGE, ITS SOURCE DID: 100 nm nominal, now "
                         "the cited f8801_nominal_diameter applied to the bench through "
                         "particle_suspension_b_identity, so E5 either way; the run used the same 100 nm")
    refs, gaps, degraded = result_card.kb_refs_for(plan, numbers), list(plan.get("kb_gaps") or []), ["librarian_agent"]
    if kb_answer is not None:
        # The bead identity, published after the question was pinned, asked for
        # under the operator id at the version that holds it (fanout.issue_operator).
        refs = refs + [{"entry_id": e["entry_id"], "grade": e["grade"], "kb_version": kb_answer["kb_version"],
                        "claim": e["claim"]} for e in kb_answer["entries"]]
        newer = {g["gap_id"]: g for g in kb_answer.get("gaps", [])}
        gaps = [newer.pop(g["gap_id"], g) for g in gaps] + list(newer.values())
        # `degraded` keeps the librarian's name: the plan's axes made no calls,
        # and a result inherits what its plan stood on (check 10). The calls
        # this card made are in the log under its caller_id regardless.
        card["caller_id"] = kb_answer["caller_id"]
    card.update(cards.tail(numbers, assumptions=result_card.assumptions_for(plan, numbers),
                           kb_refs=refs, kb_gaps=gaps, degraded=degraded))
    return card


def _dedupe(criteria):
    seen, out = set(), []
    for c in criteria:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        out.append(c)
    return out


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "synthesis":
        qid, created_at = sys.argv[2], sys.argv[3]
        revision = cards.question_revision(qid)
        target = cards.question_dir(qid) / cards.artifact_name("synthesis.json", revision)
        card = build_synthesis(qid, created_at, revision)
        cards.refuse_overwrite(target, revision, card)
        print(cards.write(target, card).relative_to(cards.REPO))
    elif what == "result":
        from . import result_card                          # noqa: PLC0415
        args = sys.argv[2:]
        kb_answer = None
        if args and args[0] == "--kb":
            # {"caller_id", "kb_version", "entries": [...], "gaps": [...]}: what the
            # session's librarian calls under fanout.issue_operator returned
            kb_answer = json.loads(open(args[1]).read())
            args = args[2:]
        run_ids = args
        card = build_result(run_ids, kb_answer)
        path = result_card.path_for(card["qid"], run_ids[0])
        print(cards.write(path, card).relative_to(cards.REPO))
    else:
        raise SystemExit(f"unknown step {what!r}: synthesis or result")
