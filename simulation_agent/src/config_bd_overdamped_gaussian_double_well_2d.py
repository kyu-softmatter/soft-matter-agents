"""A1-A7, S4 and S5 for `bd_overdamped_gaussian_double_well_2d` (plan.md 4.5.2-4.5.4).

One overdamped bead, two dimensions, two additive Gaussian wells, fluid at
rest. Declared at 4ab86d9; first used by sim-20260923-101 revision 2 (task 024).

What is particular to this configuration, and why the axes read as they do:

- **Every time scale is gamma/k.** In the engine's reduced units the in-well
  relaxation time is 1/eps in w^2/D, and w^2/(D eps) = kT/(D k) = gamma/k. So a
  timestep rule written in reduced units, dt <= 0.025/eps, is dt <= 0.025 gamma/k
  in SI -- the width drops out. Task 024 measured that rule: at eps 247 kT the
  rate moved within its scatter between 0.05 and 0.02 of gamma/k.
- **The separation is not a plan number.** Near merging the barrier moves by
  about half a kT per 10 nm at 1 pN/um, so the plan carries the barrier target
  and the engine solves the separation (double_well.separation_for_barrier) and
  reports it. An explore-mode separation, written to one figure, would be a
  different experiment.
- **A1-A5 bound what a single record resolves; they do not predict the rate.**
  The rate over a few-kT saddle in this 2-D landscape has no safe closed form
  (the capability entry), so A2's hop count is a precondition the run checks,
  not an interval computed from a guess.
- **A7 abstains**: nothing is driven.
"""

from __future__ import annotations

import json

from . import cards, synthesis
from contracts.validate import round_to_sig

ENVELOPE = cards.AGENT / "envelope" / "budget.json"
CONFIG = "bd_overdamped_gaussian_double_well_2d"

ANCHORS = ["bead_diameter", "temperature", "viscosity", "trap_stiffness_1", "trap_stiffness_2",
           "trap_width_1", "trap_width_2", "barrier_target", "record_length", "save_interval",
           "milestone_core_fraction", "walkers"]

USES = {
    "a1": ["bead_diameter", "viscosity", "trap_stiffness_1", "trap_stiffness_2"],
    "a2": ["bead_diameter", "viscosity", "trap_stiffness_1", "record_length", "walkers"],
    "a3": ["trap_width_1"],
    "a4": ["bead_diameter", "viscosity", "trap_stiffness_1", "save_interval"],
    "a5": ["walkers"],
    "a7": [],
}

QUERIES = {
    "a1": ["integration_timestep_resolution_factor"],
    "a2": ["interwell_transition_rate"],
    "a3": ["trap_potential_width"],
    "a4": ["camera_exposure_time"],
    "a5": ["particle_step_rate"],
    "a7": ["flow_speed"],
}


# The goal S4 is choosing for. `configs.operating_point` passes no question, and
# `synthesis.build` asks `applicable(goal)` of this module first, so the goal is kept
# here for the spec to compute from -- the point's costs depend on its walkers.
_GOAL: dict | None = None


def applicable(goal: dict) -> tuple[bool, str]:
    global _GOAL
    _GOAL = goal
    named = {n["name"] for n in goal.get("numbers", []) or []}
    missing = [n for n in ANCHORS if n not in named]
    if missing:
        return False, ("this goal carries no " + ", ".join(missing) + " in numbers[]; every axis here is "
                       "written in the traps' stiffness, width and barrier, and none is defaulted here")
    return True, ""


def axis_queries(goal: dict, axis: str) -> list[str]:
    """The axis's own names, plus the gap names of every goal assumption it carries.

    A carried assumption keeps its gap_ref, and check 39 wants that gap in the
    card that holds the assumption. So the axis asks for it again under its own
    caller_id rather than copying the goal's answer -- a gap is what THIS caller
    was told, and a copied one would be a claim nobody asked for.
    """
    names = list(QUERIES[axis])
    carried = set(USES[axis])
    for a in goal.get("assumptions") or []:
        if carried & set(a.get("numbers") or []) and a.get("gap_ref", "").endswith("_absent"):
            name = a["gap_ref"][: -len("_absent")]
            if name not in names:
                names.append(name)
    return names


def plan_queries(qid: str, revision: int, config: str, issue) -> list[dict]:
    goal = cards.load_goal(qid, revision)
    versions = {r["kb_version"] for r in goal.get("kb_refs") or []}
    kb_version = versions.pop() if len(versions) == 1 else None
    return [{"tool": "kb_query", "caller_id": issue(qid, revision, config, axis),
             "args": {"kb_version": kb_version, "observable": name, "purpose": goal["purpose"]},
             "why": f"{axis}: an entry replaces the assumption standing where {name} would"}
            for axis in QUERIES for name in axis_queries(goal, axis)]


# --------------------------------------------------------------------------- #

def _value(numbers, name):
    return next(n for n in numbers if n["name"] == name)["value"]


def _g(numbers, name):
    """A number's grade as the card already holds it -- read, never restated."""
    return next(n for n in numbers if n["name"] == name)["grade"]


def _one(x):
    return float(f"{round_to_sig(x, 1):g}")


def _anchors(goal, numbers, assumptions, axis):
    carried, carried_assumptions = cards.carry(goal, USES[axis])
    numbers += carried
    assumptions += carried_assumptions
    return {n["name"]: n["grade"] for n in numbers}


def _interval(parameter, unit, basis, varies_with=None, **bound):
    out = {"parameter": parameter, "unit": unit, **bound, "basis": [basis], "precision": "order_of_magnitude"}
    if varies_with:
        out["varies_with"] = list(varies_with)
    return out


def _ineq(text, parameter, interval=None, precondition=None):
    out = {"inequality": text, "parameter": parameter, "state": "returned"}
    if interval is not None:
        out["interval"] = interval
    if precondition is not None:
        out["precondition"] = precondition
    return out


def _drag_and_tau(numbers, g):
    """gamma = 3 pi eta d and the stiff trap's relaxation time gamma/k, both computed."""
    d, eta = _value(numbers, "bead_diameter") * 1e-6, _value(numbers, "viscosity")
    gamma = _one(3 * 3.141592653589793 * eta * d)
    numbers.append(cards.num(
        "drag_coefficient", gamma, "N*s/m", "computed:stokes_drag",
        formula="3*pi*viscosity*bead_diameter",
        inputs=[("viscosity", g["viscosity"]), ("bead_diameter", g["bead_diameter"])],
        precision="order_of_magnitude",
        note="bulk Stokes drag. Near the coverslip the drag is larger; the bench's in-situ diffusivity "
             "replaces this in the re-prediction"))
    k = _value(numbers, "trap_stiffness_1")
    tau = _one(gamma / k)
    numbers.append(cards.num(
        "trap_relaxation_time", tau, "s", "computed:drag_over_stiffness",
        formula="drag_coefficient/trap_stiffness_1",
        inputs=[("drag_coefficient", "E4"), ("trap_stiffness_1", g["trap_stiffness_1"])],
        precision="order_of_magnitude",
        note="gamma/k at the bottom of one well alone: the shortest time in the problem. Near merging the "
             "curvature at the minima is smaller, so the true in-well time is longer and this bound is safe"))
    return tau


def a1(goal, numbers, assumptions):
    g = _anchors(goal, numbers, assumptions, "a1")
    tau = _drag_and_tau(numbers, g)
    numbers.append(cards.num(
        "dt_relaxation_factor", 0.02, "1", "assumed:a_dt_factor", precision="order_of_magnitude",
        note="dt as a fraction of gamma/k; equivalently dt <= 0.02/eps in the engine's w^2/D"))
    dt_max = _one(0.02 * tau)
    numbers.append(cards.num(
        "integration_timestep_max", dt_max, "s", "computed:factor_times_relaxation_time",
        formula="dt_relaxation_factor*trap_relaxation_time",
        inputs=[("dt_relaxation_factor", "E5"), ("trap_relaxation_time", _g(numbers, "trap_relaxation_time"))],
        precision="order_of_magnitude",
        note="the stiff trap sets it; equal stiffnesses here, so either"))
    assumptions.append({
        "rationale_id": "a_dt_factor",
        "statement": "A fiftieth of gamma/k, one figure on the safe side of the fortieth that was measured. Task 024 ran this configuration at eps 247 kT with the step at "
                     "0.05, 0.025 and 0.0125 of gamma/k, on the engine and on the NumPy reference, and the "
                     "occupancy, the rate and the projected barrier did not move beyond their scatter across "
                     "the three. That study is not a run record, so the factor stands here as a convention "
                     "it supports rather than as a citation.",
        "numbers": ["dt_relaxation_factor"],
        "falsifier": "this plan's own run at half the step returning a rate outside the first run's scatter",
        "gap_ref": "integration_timestep_resolution_factor_absent"})
    iv = _interval("integration_timestep", "s", "integration_timestep_max", ["trap_stiffness"], max=dt_max)
    return dict(method="deterministic", verdict="feasible", constraints=[iv],
                inequalities=[_ineq("dt <= 0.02*gamma/k at the stiffer trap", "integration_timestep", interval=iv)],
                note="The width drops out: w^2/(D*eps) = gamma/k. So one rule holds at every width of the map.")


def a2(goal, numbers, assumptions):
    g = _anchors(goal, numbers, assumptions, "a2")
    tau = _drag_and_tau(numbers, g)
    numbers.append(cards.num(
        "startup_relaxation_times", 200, "1", "assumed:a_startup", precision="order_of_magnitude",
        note="the discard in units of gamma/k"))
    startup = _one(200 * tau)
    numbers.append(cards.num(
        "startup_discard_min", startup, "s", "computed:relaxation_times_times_tau",
        formula="startup_relaxation_times*trap_relaxation_time",
        inputs=[("startup_relaxation_times", "E5"), ("trap_relaxation_time", _g(numbers, "trap_relaxation_time"))],
        precision="order_of_magnitude",
        note="the walkers start at the trap centres, half in each; two hundred in-well times relaxes each "
             "into its well. It does not relax the occupancy between wells, and for equal wells it need not"))
    numbers.append(cards.num(
        "records_min", 100, "1", "assumed:a_records", precision="significant_figures",
        note="independent single-bead records, so the spread one record shows can be read, not guessed"))
    numbers.append(cards.num(
        "hops_per_record_min", 10, "count", "assumed:a_hops", precision="significant_figures",
        note="below this a record bounds the rate rather than measuring it (the observable's own note)"))
    assumptions += [
        {"rationale_id": "a_startup", "statement": "Two hundred in-well relaxation times of discard.",
         "numbers": ["startup_relaxation_times"],
         "falsifier": "an occupancy that still drifts between the first and second halves of the record",
         "gap_ref": "interwell_transition_rate_absent"},
        {"rationale_id": "a_records", "statement": "A hundred records is the least that shows a spread.",
         "numbers": ["records_min"], "falsifier": "the thousand-record spread study replaces it",
         "gap_ref": "interwell_transition_rate_absent"},
        {"rationale_id": "a_hops", "statement": "Ten hops a record separates a measured rate from a bound.",
         "numbers": ["hops_per_record_min"],
         "falsifier": "a record with fewer is reported as a bound and the plan's barrier is lowered",
         "gap_ref": "interwell_transition_rate_absent"},
    ]
    iv_s = _interval("startup_discard", "s", "startup_discard_min", ["trap_stiffness"], min=startup)
    iv_w = _interval("walkers", "1", "records_min", min=100)
    return dict(method="deterministic", verdict="feasible", constraints=[iv_s, iv_w],
                inequalities=[
                    _ineq("startup_discard >= 200*gamma/k", "startup_discard", interval=iv_s),
                    _ineq("walkers >= 100 independent records", "walkers", interval=iv_w),
                    _ineq("each record holds at least ten hops", "record_length", precondition={
                        "parameter": "record_length",
                        "requires": "the run must report the hops per record it measured. The rate over a "
                                    "few-kT saddle in this landscape has no safe closed form, so A2 does not "
                                    "predict it: the record length is the bench's, and whether it holds ten "
                                    "hops is the run's first result",
                        "basis": ["hops_per_record_min"]}),
                ],
                note="The hop count is a precondition and not an interval, on purpose: an interval would need a "
                     "predicted rate, and the configuration is declared because that rate is not predictable.")


def a3(goal, numbers, assumptions):
    g = _anchors(goal, numbers, assumptions, "a3")
    w = _value(numbers, "trap_width_1")
    box = _one(100 * w)
    numbers.append(cards.num(
        "box_edge_min", box, "m", "computed:hundred_widths",
        formula="100*trap_width_1", inputs=[("trap_width_1", g["trap_width_1"])],
        precision="order_of_magnitude",
        note="the wells are zero beyond a few widths, so a box of a hundred keeps the far field flat and "
             "never wrapped. The walkers carry no pair force, so they need no spacing from each other"))
    iv = _interval("box_length", "m", "box_edge_min", min=box)
    return dict(method="deterministic", verdict="feasible", constraints=[iv],
                inequalities=[_ineq("box_edge >> separation + a few widths", "box_length", interval=iv)],
                note="Nearly vacuous: one bead per record and no interaction. The axis says so rather than "
                     "abstaining, because the unwrapped trajectory needs the statement that it never wrapped.")


def a4(goal, numbers, assumptions):
    g = _anchors(goal, numbers, assumptions, "a4")
    tau = _drag_and_tau(numbers, g)
    save_max = _one(0.5 * tau)
    numbers.append(cards.num(
        "save_interval_max", save_max, "s", "computed:half_relaxation_time",
        formula="0.5*trap_relaxation_time", inputs=[("trap_relaxation_time", _g(numbers, "trap_relaxation_time"))],
        precision="order_of_magnitude",
        note="frames closer than the in-well relaxation, so a short excursion into a core is not missed and "
             "milestoning does not undercount returns"))
    iv = _interval("save_interval", "s", "save_interval_max", ["trap_stiffness"], max=save_max)
    return dict(method="deterministic", verdict="feasible", constraints=[iv],
                inequalities=[
                    _ineq("save_interval <= gamma/(2k)", "save_interval", interval=iv),
                    _ineq("a camera frame is an instant", "camera_exposure_time", precondition={
                        "parameter": "camera_exposure_time",
                        "requires": "the plan must state the exposure as a condition of the comparison: a frame "
                                    "averages the position over its exposure, which narrows each peak and can "
                                    "hide a short visit, while the simulation's positions are instantaneous",
                        "basis": ["save_interval_max"]}),
                ],
                note="The frame interval is the bench's, and the same estimator is applied to both records at "
                     "it; this axis says how coarse it may be before milestoning misses returns.")


def _allowance():
    try:
        data = json.loads(ENVELOPE.read_text())
    except FileNotFoundError:
        return None
    targets = data.get("targets") or []
    return {"target": targets[0].get("target"), **(targets[0].get("limits") or {})} if len(targets) == 1 else None


def a5(goal, numbers, assumptions):
    _anchors(goal, numbers, assumptions, "a5")
    allowance = _allowance()
    numbers.append(cards.num(
        "particle_step_rate", 1e6, "1/s", "assumed:a_step_rate", precision="order_of_magnitude",
        note="walker-steps a second on one core, HOOMD CPU with the wells as a Python force"))
    if int(goal["revision"]) >= 3:
        # Revision 3 costs storage as the text trajectory the operator writes, which is what
        # fills the disk, and adds the per-frame term (task 023). Both were read off revision
        # 2's own runs: 78.8 MB for 2.8e6 coordinates in run-20260924-101-v2-smoke2, and 74 s
        # of readout and writing for 1.22e7 walker-frames in run-20260924-101-v2-full.
        numbers.append(cards.num(
            "bytes_per_coordinate", 3e-8, "GB", "assumed:a_step_rate", precision="order_of_magnitude",
            note="about 28 bytes a coordinate in the text trajectory, read off run-20260924-101-v2-smoke2"))
        numbers.append(cards.num(
            "particle_frame_cost", 6e-6, "s", "assumed:a_step_rate", precision="order_of_magnitude",
            note="readout and text write per walker-frame, read off run-20260924-101-v2-full"))
    else:
        numbers.append(cards.num(
            "bytes_per_coordinate", 8e-9, "GB", "assumed:a_step_rate", precision="significant_figures",
            note="eight bytes, double precision in memory; the text trajectory is larger per coordinate"))
    assumptions += [
        {"rationale_id": "a_step_rate",
         "statement": "About a million walker-steps a second: task 024 timed 1.1e6 at 200 walkers and 3.6e6 at "
                      "2000 on this machine, in a study rather than a run, so it stands here as an assumption.",
         "numbers": ["particle_step_rate", "bytes_per_coordinate"]
                    + (["particle_frame_cost"] if int(goal["revision"]) >= 3 else []),
         "falsifier": "this plan's smoke run log replaces the rate, and its peak memory the bytes",
         "gap_ref": "particle_step_rate_absent"},
    ]
    constraints, ineqs = [], []
    wc = (allowance or {}).get("wall_clock_max") or {}
    if wc.get("unit") == "h" and wc.get("value"):
        steps_max = _one(float(wc["value"]) * 3600 * 1e6)
        numbers.append(cards.num(
            "particle_steps_max", steps_max, "1", "assumed:a_step_budget", precision="order_of_magnitude",
            note="the local wall clock at the assumed rate, as walker-steps"))
        assumptions.append({
            "rationale_id": "a_step_budget",
            "statement": f"{wc['value']} h from envelope/budget.json at a million walker-steps a second.",
            "numbers": ["particle_steps_max"], "falsifier": "the smoke run's measured rate",
            "gap_ref": "particle_step_rate_absent"})
        iv = _interval("particle_steps", "1", "particle_steps_max", max=steps_max)
        constraints.append(iv)
        ineqs.append(_ineq("walkers*(startup+record)/dt <= wall_clock_max*particle_step_rate",
                           "particle_steps", interval=iv))
    return dict(method="deterministic", verdict="feasible" if constraints else "abstain",
                **({} if constraints else {"abstain_reason": "no single-target allowance in envelope/budget.json"}),
                constraints=constraints, inequalities=ineqs,
                note="A5 constrains the product of the settable parameters and does not see A1's step.")


def a7(goal, numbers, assumptions):
    return dict(method="deterministic", verdict="abstain",
                abstain_reason=("No driving. The configuration is declared undriven: the fluid is at rest and "
                                "the traps do not move during a record. This card is the record that the axis "
                                "was asked and had nothing to constrain (P1)."),
                note="numbers[] is empty because an abstention has nothing to measure.")


AXES = {"a1": a1, "a2": a2, "a3": a3, "a4": a4, "a5": a5, "a7": a7}


def build(axis, qid, config, created_at, caller_id, kb_version, kb_result, revision):
    if not caller_id.endswith(f":{axis}"):
        raise ValueError(f"{caller_id!r} was issued to another axis; this is {axis}")
    goal = cards.load_goal(qid, revision)
    numbers: list[dict] = []
    assumptions: list[dict] = []
    body = AXES[axis](goal, numbers, assumptions)
    note = body.pop("note", None)
    card = cards.head("axis", f"axis-{qid}-{config}-{axis}" + ("" if revision == 1 else f"-r{revision}"),
                      qid, created_at, revision=revision, caller_id=caller_id, config=config, axis=axis,
                      kb_version=kb_version, **body)
    card.update(cards.tail(numbers, assumptions=assumptions,
                           **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
    if note:
        card["note"] = note
    return card


# --- S4: the operating point ------------------------------------------- #
#
# Checked against the axis intervals before writing: dt 1e-3 s at A1's 1e-3 s
# ceiling and dividing the 10 ms frame into ten steps; the 10 s discard at A2's
# floor; 200 walkers over A2's 100; the 10 ms frame under A4's 20 ms; a 100 um
# box at A3's floor; 1e8 walker-steps under A5's 7e9.

_A = f"axis_{CONFIG}_"


def _gv(name: str) -> float:
    return float(next(n["value"] for n in (_GOAL or {})["numbers"] if n["name"] == name))


def operating_point() -> dict:
    goal_names = ["bead_diameter", "temperature", "viscosity", "trap_stiffness_1", "trap_stiffness_2",
                  "trap_width_1", "trap_width_2", "barrier_target", "record_length", "save_interval",
                  "milestone_core_fraction", "walkers", "smoke_record_fraction"]
    return {
        "carry": [("goal.json", n) for n in goal_names] + [
            (_A + "a1.json", "drag_coefficient"),
            (_A + "a1.json", "trap_relaxation_time"),
            (_A + "a1.json", "integration_timestep_max"),
            (_A + "a2.json", "startup_discard_min"),
            (_A + "a2.json", "hops_per_record_min"),
            (_A + "a3.json", "box_edge_min"),
            (_A + "a4.json", "save_interval_max"),
            (_A + "a5.json", "particle_step_rate"),
            (_A + "a5.json", "bytes_per_coordinate"),
        ] + ([(_A + "a5.json", "particle_frame_cost")] if int((_GOAL or {}).get("revision", 2)) >= 3 else []),
        "computed": [
            {"name": "integration_timestep_point", "value": 0.001, "unit": "s",
             "source": "computed:a1_ceiling", "formula": "1*integration_timestep_max",
             "inputs": ["integration_timestep_max"],
             "note": "at A1's ceiling, and a tenth of the frame so a frame never falls between steps"},
            {"name": "startup_discard_point", "value": 10, "unit": "s",
             "source": "computed:a2_floor", "formula": "1*startup_discard_min",
             "inputs": ["startup_discard_min"], "note": "at A2's floor"},
            {"name": "box_length_point", "value": 0.0001, "unit": "m",
             "source": "computed:a3_floor", "formula": "1*box_edge_min", "inputs": ["box_edge_min"],
             "note": "at A3's floor: a hundred widths, the far field flat and never wrapped"},
            {"name": "particle_steps_point", "value": _one(_gv("walkers") * (_gv("record_length") + 10) / 0.001), "unit": "1",
             "source": "computed:walkers_times_steps",
             "formula": "walkers*(record_length+startup_discard_point)/integration_timestep_point",
             "inputs": ["walkers", "record_length", "startup_discard_point", "integration_timestep_point"],
             "note": "the records of the base point at a millisecond step, to one figure"},
            {"name": "coordinates_stored_point", "value": _one(2 * _gv("walkers") * (_gv("record_length") + 10) / _gv("save_interval")), "unit": "1",
             "source": "computed:walkers_times_frames_times_two",
             "formula": "walkers*(record_length+startup_discard_point)/save_interval*2",
             "inputs": ["walkers", "record_length", "startup_discard_point", "save_interval"],
             "note": "two coordinates a frame: the configuration is two-dimensional"},
        ],
        "point": [
            ("integration_timestep", "integration_timestep_point"),
            ("save_interval", "save_interval"),
            ("record_length", "record_length"),
            ("startup_discard", "startup_discard_point"),
            ("box_length", "box_length_point"),
            ("walkers", "walkers"),
            ("trap_stiffness_1", "trap_stiffness_1"),
            ("trap_stiffness_2", "trap_stiffness_2"),
            ("trap_width_1", "trap_width_1"),
            ("trap_width_2", "trap_width_2"),
            ("barrier_target", "barrier_target"),
            ("milestone_core_fraction", "milestone_core_fraction"),
        ],
        "rejected": [
            {"what": "a stiffness ratio anywhere in the person's 1 to 100",
             "kind": "operating_point",
             "reason": "computed from the potential: with wells hundreds of kT deep, any k2/k1 of 0.5 or below "
                       "makes the shallow well vanish while the barrier from the deeper one is still tens to "
                       "thousands of kT, so no separation gives a barrier in 1-10 kT. Equal stiffnesses are "
                       "the operating point; asymmetry is a depth difference of a few kT, a trim of a few per cent",
             "grounds": ["trap_stiffness_1", "trap_stiffness_2", "barrier_target"]},
            {"what": "the separation as a plan number",
             "kind": "operating_point",
             "reason": "the barrier moves by about half a kT per ten nanometres at this stiffness, so a separation to "
                       "one figure is a different experiment. The plan carries the barrier and the engine "
                       "solves the separation from it",
             "grounds": ["barrier_target", "trap_width_1"]},
        ],
    }


# --- S5: the plan ------------------------------------------------------- #

MODEL = ("one overdamped bead in two dimensions, in fluid at rest, in two optical traps modelled as two "
         "Gaussian wells that add: U = -eps_1 exp(-|r-r_1|^2/2w_1^2) - eps_2 exp(-|r-r_2|^2/2w_2^2), each "
         "0.5*k_i*dr^2 at its centre with k_i = eps_i/w_i^2. Many independent single-bead records in one "
         "engine run; no pair interaction")


def build_plan(qid: str, created_at: str, revision: int = 1) -> dict:
    from . import plan_card

    goal = cards.load_goal(qid, revision)
    syn = json.loads((cards.question_dir(qid) / cards.artifact_name("synthesis.json", revision)).read_text())
    point = {p["parameter"]: p["number"] for p in syn["operating_point"]}
    extra = ["temperature", "viscosity", "bead_diameter", "drag_coefficient", "trap_relaxation_time",
             "integration_timestep_max", "startup_discard_min", "hops_per_record_min",
             "box_edge_min", "save_interval_max", "particle_step_rate", "bytes_per_coordinate",
             "particle_steps_point", "coordinates_stored_point", "smoke_record_fraction"] + (
                 ["particle_frame_cost"] if int(revision) >= 3 else [])
    wanted = [(cards.artifact_name("synthesis.json", revision), n)
              for n in dict.fromkeys(list(point.values()) + extra)]
    numbers = synthesis.carry_from(qid, CONFIG, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)
    grades = {n["name"]: n["grade"] for n in numbers}
    value = lambda name: next(float(n["value"]) for n in numbers if n["name"] == name)  # noqa: E731

    wall = value("particle_steps_point") / value("particle_step_rate")
    numbers.append(cards.num(
        "wall_clock_estimate", float(f"{wall:.1g}"), "s", "computed:particle_steps_over_rate",
        formula="particle_steps_point / particle_step_rate",
        inputs=[(n, grades[n]) for n in ("particle_steps_point", "particle_step_rate")],
        precision="order_of_magnitude",
        note="stepping only, and so a LOWER BOUND: 61000 frames are read out of the engine and written as text "
             "after the run, a term this estimate does not carry (task 023)"))
    store = value("coordinates_stored_point") * value("bytes_per_coordinate")
    numbers.append(cards.num(
        "storage_estimate", float(f"{store:.1g}"), "GB", "computed:coordinates_times_bytes",
        formula="coordinates_stored_point * bytes_per_coordinate",
        inputs=[(n, grades[n]) for n in ("coordinates_stored_point", "bytes_per_coordinate")],
        precision="order_of_magnitude",
        note="in memory; the text trajectory on disk is several times larger per coordinate"))

    conditions = [{"parameter": p, "number": n} for p, n in point.items()]
    conditions += [{"parameter": "temperature", "number": "temperature"},
                   {"parameter": "viscosity", "number": "viscosity"},
                   {"parameter": "bead_diameter", "number": "bead_diameter"}]
    card = cards.head(
        "plan", f"plan-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, goal_id=goal["id"], synthesis_id=syn["id"], purpose=goal["purpose"],
        intent=goal["intent"], observable=cards.observable(goal["observable"]["name"]),
        system_configuration={"config": CONFIG, "optical_path": None, "devices": ["hoomd_backend"], "model": MODEL},
        targets=[dict(t) for t in goal.get("targets", [])],
        conditions=conditions,
        actions=[
            {"id": "integrate", "device": "hoomd_backend",
             "action": "integrate the declared configuration for the startup discard and the record, saving "
                       "frames at the planned interval, with the separation solved from the barrier target",
             "reversible": True, "parameters": [c["parameter"] for c in conditions], "tier": 1},
            {"id": "estimate_wells", "device": "hoomd_backend",
             "action": "project each record on the line joining the traps, place cores around the two histogram "
                       "peaks at the declared fraction of their spacing, and report per record and over records "
                       "the occupancy, both residence times, both ordered transition rates and the projected "
                       "barrier -- the estimator the experiment applies to its own record",
             "reversible": True, "parameters": ["milestone_core_fraction", "save_interval", "record_length"],
             "tier": 0},
        ],
        envelope_check=plan_card.envelope_check(numbers),
        cost={"wall_clock": "about two minutes of stepping at the assumed rate, plus reading out and writing "
                            "61000 frames of 200 records, which the estimate does not carry",
              "numbers": ["wall_clock_estimate", "storage_estimate"],
              "note": "the rate is assumed; the smoke run's log replaces it"},
        smoke={"record_fraction": "smoke_record_fraction"},
        # filled below, once numbers[] exists to point into; the run ends when the backend
        # reports COMPLETE, which the operator records without a criterion firing
        stop_criteria=[],
        success_criteria=[
            {"id": "hops_counted", "metric": "median_transitions_per_record", "comparator": ">=",
             "number": "hops_per_record_min", "window": "the record after the startup discard",
             "statement": "the median record holds at least ten hops; below that a record bounds the rate and "
                          "the barrier target is lowered in the next revision"},
            {"id": "occupancy_symmetric", "metric": "well_occupancy", "comparator": "==",
             "target": "well_occupancy", "window": "the record after the startup discard",
             "statement": "for equal wells the mean occupancy over records is one half within its standard error; "
                          "a departure is the estimator or the engine, since the potential fixes it"},
        ],
        alternatives_rejected=[{"what": r["what"], "reason": r["reason"], "grounds": r["grounds"]}
                               for r in syn.get("rejected", [])],
        open_risks=[
            "Only the rates and residence times are results about the model. The occupancy and the barrier are "
            "fixed by the potential in the long-record limit, so for those two this run establishes only what a "
            "finite record returns -- its spread and its bias -- and must not be read as discovering them.",
            "The separation is solved from the barrier and is not a number the bench can set: near merging the "
            "barrier moves by about half a kT per ten nanometres, so the bench reaches this point by watching its "
            "histogram, and the comparison runs at the calibrated values it returns.",
            "Bulk Stokes drag. Near the coverslip the bead's drag is larger and every time here stretches with "
            "it; the bench's in-situ diffusivity replaces the drag in the re-prediction.",
            "Simulated positions are instantaneous and a camera frame averages over its exposure, which narrows "
            "each peak and can hide a short visit. The exposure is a condition of any comparison.",
            "The axis along the beam is not modelled. A real trap is weaker there; the in-plane observables are "
            "unaffected only while nothing reads that axis.",
        ],
    )
    card["status"] = "DRAFT"
    if int(revision) >= 3:
        _add_sweep(qid, revision, card, numbers, grades)
        # the synthesis's rationales, joined by id with the goal's for the numbers the sweep
        # carried straight from the goal, each narrowed to the numbers this card holds
        held = {n["name"] for n in numbers}
        merged = {}
        for a in synthesis.assumptions_for(qid, numbers) + list(cards.load_goal(qid, revision).get("assumptions") or []):
            nums = [x for x in a.get("numbers", []) if x in held]
            if not nums:
                continue
            m = merged.setdefault(a["rationale_id"], {**a, "numbers": []})
            m["numbers"] = list(dict.fromkeys(m["numbers"] + nums))
        assumptions = list(merged.values())
    card.update(cards.tail(numbers, assumptions=assumptions, kb_refs=synthesis.kb_refs_for(qid, numbers),
                           kb_gaps=syn.get("kb_gaps") or [], degraded=list(syn.get("degraded") or [])))
    card["stop_criteria"] = _stop_criteria(card)
    return card


# Revision 3's five points: what one record shows (task 024 stage 4). Each names the
# numbers its conditions point at; the parameters they set leave the shared list.
SWEEP_POINTS = {
    "soft":        ("trap_stiffness_soft", "trap_stiffness_soft", "barrier_soft", "depth_difference_none",
                    "record_length", "save_interval", "walkers"),
    "hold":        ("trap_stiffness_1", "trap_stiffness_2", "barrier_target", "depth_difference_none",
                    "record_length", "save_interval", "walkers"),
    "hold_asym":   ("trap_stiffness_1", "trap_stiffness_2", "barrier_target", "depth_difference_mild",
                    "record_length", "save_interval", "walkers"),
    "hold_long":   ("trap_stiffness_1", "trap_stiffness_2", "barrier_target", "depth_difference_none",
                    "record_length_long", "save_interval", "walkers_long"),
    "hold_coarse": ("trap_stiffness_1", "trap_stiffness_2", "barrier_target", "depth_difference_none",
                    "record_length", "save_interval_coarse", "walkers"),
}
SWEEP_PARAMS = ("trap_stiffness_1", "trap_stiffness_2", "barrier_target", "depth_difference",
                "record_length", "save_interval", "walkers")


def _add_sweep(qid, revision, card, numbers, grades):
    have = {n["name"] for n in numbers}
    wanted = [n for n in dict.fromkeys(x for pt in SWEEP_POINTS.values() for x in pt) if n not in have]
    # From the goal with their rationales: `carry` narrows each rationale to the numbers
    # that came along, and `build_plan` then re-derives the plan's assumptions over all of them.
    carried, _ = cards.carry(cards.load_goal(qid, revision), wanted)
    numbers += carried
    grades.update({n["name"]: n["grade"] for n in numbers})
    value = lambda name: next(float(n["value"]) for n in numbers if n["name"] == name)  # noqa: E731
    points, steps_names, frames_names, coord_names = [], [], [], []
    for pt, names in SWEEP_POINTS.items():
        rec, save, walk = names[4], names[5], names[6]
        span = value(walk) * (value(rec) + value("startup_discard_point"))
        for kind, val, unit, formula, ins, dest in (
            ("particle_steps", span / value("integration_timestep_point"), "1",
             f"{walk}*({rec}+startup_discard_point)/integration_timestep_point",
             [walk, rec, "startup_discard_point", "integration_timestep_point"], steps_names),
            ("particle_frames_saved", span / value(save), "1",
             f"{walk}*({rec}+startup_discard_point)/{save}", [walk, rec, "startup_discard_point", save], frames_names),
            ("coordinates_stored", 2 * span / value(save), "1",
             f"2*{walk}*({rec}+startup_discard_point)/{save}", [walk, rec, "startup_discard_point", save], coord_names),
        ):
            name = f"{kind}_{pt}"
            numbers.append(cards.num(name, _one(val), unit, "computed:sweep_point_cost", formula=formula,
                                     inputs=[(i, grades[i]) for i in ins], precision="order_of_magnitude"))
            grades[name] = numbers[-1]["grade"]
            dest.append(name)
        points.append({"point": pt, "conditions": [{"parameter": p, "number": n}
                                                    for p, n in zip(SWEEP_PARAMS, names)]})
    # the plan-level estimates are the sums over points, both cost terms (task 023)
    wall = sum(value(s) for s in steps_names) / value("particle_step_rate") \
        + sum(value(f) for f in frames_names) * value("particle_frame_cost")
    store = sum(value(c) for c in coord_names) * value("bytes_per_coordinate")
    numbers[:] = [n for n in numbers if n["name"] not in ("wall_clock_estimate", "storage_estimate")]
    numbers.append(cards.num(
        "wall_clock_estimate", _one(wall), "s", "computed:sweep_steps_over_rate_plus_frames",
        formula=f"({' + '.join(steps_names)}) / particle_step_rate + ({' + '.join(frames_names)}) * particle_frame_cost",
        inputs=[(n, grades[n]) for n in steps_names + frames_names + ["particle_step_rate", "particle_frame_cost"]],
        precision="order_of_magnitude",
        note="all five points run one after another on one core; they are independent and may run side by side"))
    numbers.append(cards.num(
        "storage_estimate", _one(store), "GB", "computed:sweep_coordinates_times_bytes",
        formula=f"({' + '.join(coord_names)}) * bytes_per_coordinate",
        inputs=[(n, grades[n]) for n in coord_names + ["bytes_per_coordinate"]], precision="order_of_magnitude",
        note="the text trajectories on disk, summed over the five points"))
    card["conditions"] = [c for c in card["conditions"] if c["parameter"] not in SWEEP_PARAMS]
    card["actions"][0]["parameters"] = [c["parameter"] for c in card["conditions"]] + list(SWEEP_PARAMS)
    card["sweep"] = {"axes": [{"parameter": p, "levels": list(dict.fromkeys(n[i] for n in SWEEP_POINTS.values()))}
                              for i, p in enumerate(SWEEP_PARAMS)],
                     "points": points}
    card["envelope_check"] = __import__(f"{__package__}.plan_card", fromlist=["x"]).envelope_check(numbers)
    card["cost"] = {"wall_clock": "about an hour and a quarter for the five points in sequence, stepping and "
                                  "frames together; they run side by side",
                    "numbers": ["wall_clock_estimate", "storage_estimate"],
                    "note": "the rate, the per-frame cost and the bytes were read off revision 2's runs"}


def _stop_criteria(card: dict) -> list[dict]:
    names = {n["name"] for n in card["numbers"]}
    out = []
    if "box_length_point" in names:
        out.append({"id": "step_displacement_diverged", "metric": "max_single_step_displacement",
                    "comparator": ">", "number": "box_length_point", "on_met": "fault",
                    "statement": "a bead moving more than the box in one step is a diverged integration; stop and "
                                 "keep the run, because divergence is a result"})
    return out


def render_plan(card: dict) -> str:
    nums = {n["name"]: n for n in card["numbers"]}
    q = lambda name: f"{nums[name]['value']} {nums[name]['unit']}"  # noqa: E731
    lines = [f"# {card['id']} -- the double well, one bead and two traps", "",
             "*Generated from the JSON card beside this file. If the two disagree the JSON wins.*", "",
             f"**Status** {card['status']}  ·  **Configuration** {card['system_configuration']['config']}", "",
             "## The model", "", card["system_configuration"]["model"], "",
             "## The operating point", "", "| parameter | value |", "|---|---|"]
    for c in card["conditions"]:
        if c["number"] in nums:
            lines.append(f"| `{c['parameter']}` | {q(c['number'])} |")
    lines += ["", "## What would make this run a failure", ""]
    lines += [f"- **{c['id']}** -- {c['statement']}" for c in card["success_criteria"]]
    lines += ["", "## What was considered and dropped", ""]
    lines += [f"- **{r['what']}** -- {r['reason']}" for r in card["alternatives_rejected"]]
    lines += ["", "## What this run cannot settle", ""]
    lines += [f"- {r}" for r in card["open_risks"]]
    return "\n".join(lines) + "\n"
