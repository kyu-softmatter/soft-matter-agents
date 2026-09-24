"""A1-A7 for `bd_overdamped_trapped` (plan.md 4.5.2, 4.5.3).

One sphere, overdamped, no pair interaction, a harmonic external potential of
stiffness `k_t`, fluid at rest. Declared at `2899a0c` on the person's decision
that the double well starts from one trap; first used by sim-20260923-102.

This is `bd_overdamped_trapped_uniform_flow` with the flow removed, and the
axes are that module's with three things changed rather than a fresh design:

- **No drift.** The flow's bound on the timestep was the one that bound there;
  here it does not exist, and the relaxation bound decides.
- **A7 abstains.** Nothing is driven, so the axis has nothing to bound, and an
  abstaining card is the record that it was asked (P1).
- **The observable is a WIDTH, not a mean.** That changes A2 and A4, and it is
  the whole reason the two modules are not one. A mean's error falls as
  sqrt(2*tau_t/T) and a record's start-up is its only bias. A width is
  understated by a short record, because the record's own mean is subtracted:
  E[s**2] = sigma**2 * (1 - 2*tau_t/T) to first order, so the relative bias on
  sigma is about -tau_t/T. And the width's own scatter is
  sqrt(tau_t/(2*T)) relative. So a record of a hundred relaxation times is
  one per cent low and seven per cent noisy, and those are two numbers.

The identity sigma**2 = D*tau_t (exact for an Ornstein-Uhlenbeck coordinate)
is used here as it is in the flow module; see that module's header.

A CAMERA FRAME IS NOT AN INSTANT, and that is a condition of the comparison
this configuration exists for. A frame averages the position over its
exposure t_e, which narrows the measured variance by
S(a) = 2/a**2 * (a - 1 + exp(-a)), a = t_e/tau_t. The simulation writes
instantaneous positions. So A4 carries the exposure as a precondition the plan
must state, rather than letting a bench width be compared with an instantaneous
one under one name.
"""

from __future__ import annotations

import json
import math

from . import cards
from contracts.validate import round_to_sig

ENVELOPE = cards.AGENT / "envelope" / "budget.json"

ANCHORS = ["bead_diameter", "temperature", "viscosity", "diffusivity",
           "trap_stiffness_min", "trap_stiffness_max", "trap_stiffness_operating",
           "trap_relaxation_time_max", "trap_relaxation_time_min",
           "thermal_width_max", "thermal_width_min"]

# What each axis carries. Kept narrow on purpose: carry brings the goal's
# assumptions with it, and an axis inheriting one it does not use is then asked
# by check 39 for a gap it has no business citing.
USES = {
    "a1": ["trap_relaxation_time_min"],
    "a2": ["trap_relaxation_time_max", "trap_relaxation_time_min"],
    "a3": ["thermal_width_max"],
    "a4": ["trap_relaxation_time_min"],
    "a5": [],
    "a7": [],
}

# One kb_query per name, per axis. A gap that comes back is the gap_ref of the
# assumption standing where the entry would have been.
QUERIES = {
    "a1": ["integration_timestep_resolution_factor"],
    "a2": ["width_record_length_factor"],
    "a3": ["trap_potential_width"],
    "a4": ["save_interval_fraction_of_relaxation_time", "camera_exposure_time"],
    "a5": ["particle_step_rate"],
    "a7": ["flow_speed"],
}


def applicable(goal: dict) -> tuple[bool, str]:
    """This configuration answers a goal that states the trap sweep."""
    named = {n["name"] for n in goal.get("numbers", []) or []}
    missing = [n for n in ANCHORS if n not in named]
    if missing:
        return False, (
            "this goal carries no " + ", ".join(missing) + " in numbers[]. Every axis here "
            "is written in the trap's relaxation time and thermal width, and neither can "
            "be defaulted here: a default range is a decision, and an axis is not where "
            "decisions are made."
        )
    return True, ""


def plan_queries(qid: str, revision: int, config: str, issue) -> list[dict]:
    goal = cards.load_goal(qid, revision)
    versions = {r["kb_version"] for r in goal.get("kb_refs") or []}
    kb_version = versions.pop() if len(versions) == 1 else None
    out = []
    for axis, names in QUERIES.items():
        for name in names:
            out.append({
                "tool": "kb_query",
                "caller_id": issue(qid, revision, config, axis),
                "args": {"kb_version": kb_version, "observable": name,
                         "purpose": goal["purpose"]},
                "why": f"{axis}: an entry replaces the assumption standing where {name} would; "
                       f"a gap is what that assumption then cites",
            })
    return out


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _value(numbers, name):
    return next(n for n in numbers if n["name"] == name)["value"]


def _head(axis, qid, config, created_at, caller_id, kb_version, revision, **kw):
    return cards.head(
        "axis",
        f"axis-{qid}-{config}-{axis}" + ("" if revision == 1 else f"-r{revision}"),
        qid, created_at, revision=revision, caller_id=caller_id, config=config,
        axis=axis, kb_version=kb_version, **kw,
    )


def _interval(parameter, unit, basis, varies_with=None, **bound):
    out = {"parameter": parameter, "unit": unit, **bound,
           "basis": [basis], "precision": "order_of_magnitude"}
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


def _one(x):
    """One significant figure by the validator's own rule, called not copied."""
    return float(f"{round_to_sig(x, 1):g}")


def _anchors(goal, numbers, assumptions, axis):
    carried, carried_assumptions = cards.carry(goal, USES[axis])
    numbers += carried
    assumptions += carried_assumptions
    return {n["name"]: n["grade"] for n in numbers}


# --------------------------------------------------------------------------- #
# axes
# --------------------------------------------------------------------------- #

def a1(goal, numbers, assumptions):
    """The timestep. With no drift, the relaxation bound is the one that binds."""
    g = _anchors(goal, numbers, assumptions, "a1")
    tau_stiff = _value(numbers, "trap_relaxation_time_min")

    numbers.append(cards.num(
        "dt_resolution_factor", 0.01, "1", "assumed:a_dt_factor",
        precision="order_of_magnitude",
        note="how far below the shortest resolved time the step sits: two decades, the "
             "usual margin for an overdamped integrator, a convention and not a derivation"))
    dt_relax = _one(0.01 * tau_stiff)
    numbers.append(cards.num(
        "dt_max_relaxation", dt_relax, "s", "computed:factor_times_relaxation_time",
        formula="dt_resolution_factor*trap_relaxation_time_min",
        inputs=[("dt_resolution_factor", "E5"), ("trap_relaxation_time_min", g["trap_relaxation_time_min"])],
        precision="order_of_magnitude",
        note="dt << gamma/k_t at the stiff end, the shortest time in the problem. Per point "
             "it is a hundredth of the LOCAL relaxation time, which is why it varies with "
             "the stiffness"))
    numbers.append(cards.num(
        "noise_step_fraction", 0.1, "1", "assumed:a_noise_step",
        precision="order_of_magnitude",
        note="the rms noise displacement per step as a fraction of the thermal width"))
    dt_noise = _one(0.5 * 0.1 ** 2 * tau_stiff)
    numbers.append(cards.num(
        "dt_max_noise", dt_noise, "s", "computed:noise_step_inside_thermal_width",
        formula="0.5*noise_step_fraction**2*trap_relaxation_time_min",
        inputs=[("noise_step_fraction", "E5"), ("trap_relaxation_time_min", g["trap_relaxation_time_min"])],
        precision="order_of_magnitude",
        note="sqrt(2*D*dt) << sigma. NOT AN INDEPENDENT BOUND: sigma**2 = D*tau_t exactly, "
             "so this is dt << tau_t again with a different factor. Kept so a reader who "
             "expects two bounds finds why there is one"))
    assumptions += [
        {"rationale_id": "a_dt_factor",
         "statement": "Two decades below the shortest resolved time is the usual margin for an "
                      "overdamped integrator. A convention; no timestep scan has been run on "
                      "this configuration.",
         "numbers": ["dt_resolution_factor"],
         "falsifier": "a timestep scan showing the width flat over a wider range of steps "
                      "replaces the factor with a measured one",
         "gap_ref": "integration_timestep_resolution_factor_absent"},
        {"rationale_id": "a_noise_step",
         "statement": "A tenth of the thermal width per step. Dependent on the relaxation bound "
                      "only because the declared potential is exactly harmonic; a trap that "
                      "flattens away from its centre would separate them again.",
         "numbers": ["noise_step_fraction"],
         "falsifier": "a non-quadratic trap makes this a distinct bound",
         "gap_ref": "integration_timestep_resolution_factor_absent"},
    ]
    iv_n = _interval("integration_timestep", "s", "dt_max_noise", ["trap_stiffness"], max=dt_noise)
    iv_r = _interval("integration_timestep", "s", "dt_max_relaxation", ["trap_stiffness"], max=dt_relax)
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[iv_n, iv_r],
        inequalities=[
            _ineq("sqrt(2*D*dt) << sigma at the stiffest point", "integration_timestep", interval=iv_n),
            _ineq("dt << gamma/k_t at the stiffest point", "integration_timestep", interval=iv_r),
        ],
        note="S4 takes the tighter, which is the noise bound by its factor. With no flow the "
             "drift bound that decided the driven configuration is absent, so the step here "
             "is a decade looser than there at the same stiffness.",
    )


def a2(goal, numbers, assumptions):
    """The record length, for a width: a bias and a scatter, and they are two numbers."""
    g = _anchors(goal, numbers, assumptions, "a2")
    tau_soft = _value(numbers, "trap_relaxation_time_max")
    tau_stiff = _value(numbers, "trap_relaxation_time_min")

    numbers.append(cards.num(
        "relaxation_times_per_record", 100, "1", "assumed:a_record_floor",
        precision="order_of_magnitude",
        note="the record in units of gamma/k_t. It fixes both the bias and the scatter below"))
    numbers.append(cards.num(
        "width_bias_at_floor", _one(1.0 / 100), "1", source="computed:record_mean_subtraction_bias",
        formula="1/relaxation_times_per_record",
        inputs=[("relaxation_times_per_record", "E5")],
        precision="order_of_magnitude",
        note="THE WIDTH IS UNDERSTATED BY A SHORT RECORD, and this is how much. Subtracting "
             "the record's own mean removes the slow part of the fluctuation: "
             "E[s**2] = sigma**2*(1 - 2*tau_t/T), so sigma comes out low by about tau_t/T. "
             "One per cent at a hundred relaxation times, and it has a sign, which scatter "
             "does not"))
    numbers.append(cards.num(
        "width_scatter_at_floor", _one(math.sqrt(1.0 / (2 * 100))), "1",
        source="computed:ou_variance_standard_error",
        formula="(1/(2*relaxation_times_per_record))**0.5",
        inputs=[("relaxation_times_per_record", "E5")],
        precision="order_of_magnitude",
        note="the relative standard error of the width from one record. The variance of an "
             "Ornstein-Uhlenbeck coordinate's squares decorrelates over tau_t/2, so the "
             "sample variance has relative error sqrt(2*tau_t/T) and the width half that. "
             "Seven per cent at the floor: inside one decade by far, and the reason a "
             "per-cent stiffness needs a longer record, not a longer list of runs"))
    t_floor_soft = _one(100 * tau_soft)
    numbers.append(cards.num(
        "record_length_floor_soft_corner", t_floor_soft, "s",
        source="computed:relaxation_times_times_tau",
        formula="relaxation_times_per_record*trap_relaxation_time_max",
        inputs=[("relaxation_times_per_record", "E5"), ("trap_relaxation_time_max", g["trap_relaxation_time_max"])],
        precision="order_of_magnitude",
        note="a minute and a half at the soft end. THIS IS ALSO THE BENCH'S RECORD LENGTH: a "
             "camera recording of the same trap needs the same hundred relaxation times, and "
             "that is the number the bridge carries to the microscope"))
    t_floor_stiff = _one(100 * tau_stiff)
    numbers.append(cards.num(
        "record_length_floor_stiff_corner", t_floor_stiff, "s",
        source="computed:relaxation_times_times_tau",
        formula="relaxation_times_per_record*trap_relaxation_time_min",
        inputs=[("relaxation_times_per_record", "E5"), ("trap_relaxation_time_min", g["trap_relaxation_time_min"])],
        precision="order_of_magnitude",
        note="a tenth of a second at the stiff end"))
    assumptions += [
        {"rationale_id": "a_record_floor",
         "statement": "A hundred relaxation times: long enough that the width's bias is a per "
                      "cent and its scatter under a tenth, both far inside the one decade the "
                      "goal asks for. A convention, and the record a per-cent stiffness would "
                      "need is the relation in the note, not this number.",
         "numbers": ["relaxation_times_per_record"],
         "falsifier": "a first run whose measured width is still rising between half the record "
                      "and the whole of it falsifies the bias estimate and lengthens the record",
         "gap_ref": "width_record_length_factor_absent"},
    ]
    iv = _interval("record_length", "s", "record_length_floor_soft_corner", ["trap_stiffness"], min=t_floor_soft)
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[iv],
        inequalities=[
            _ineq("record_length >= 100*gamma/k_t at each stiffness", "record_length", interval=iv),
        ],
        note="Two numbers where a mean has one. The relative bias is -tau_t/T and has a sign; "
             "the relative scatter is sqrt(tau_t/(2T)) and does not. At the floor they are one "
             "and seven per cent. For a stiffness to a per cent the scatter must reach half a "
             "per cent, which is T = 2e4*tau_t, and that is the next revision's record, not "
             "this one's.",
    )


def a3(goal, numbers, assumptions):
    """Finite size. Vacuous for one particle, and what it does carry is the trap's range."""
    g = _anchors(goal, numbers, assumptions, "a3")
    sigma_soft = _value(numbers, "thermal_width_max")
    excursion = _one(5 * sigma_soft)
    numbers.append(cards.num(
        "max_excursion_soft_corner", excursion, "um",
        source="computed:five_thermal_widths",
        formula="5*thermal_width_max",
        inputs=[("thermal_width_max", g["thermal_width_max"])],
        precision="order_of_magnitude",
        note="five thermal widths at the softest trap: a Gaussian coordinate goes there about "
             "once in two million samples, so it bounds every frame of any record here"))
    box = _one(10 * excursion)
    numbers.append(cards.num(
        "box_edge_min", box, "um", source="computed:margin_times_max_excursion",
        formula="10*max_excursion_soft_corner", inputs=[("max_excursion_soft_corner", "E5")],
        precision="order_of_magnitude",
        note="a decade of margin, so the unwrapped trajectory never approaches a boundary"))
    iv = _interval("box_edge", "um", "box_edge_min", min=box)
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[iv],
        inequalities=[
            _ineq("box_edge >> the largest excursion at the softest trap", "box_edge", interval=iv),
            _ineq("the particle stays where the bench trap is still harmonic", "trap_stiffness",
                  precondition={
                      "parameter": "trap_stiffness",
                      "requires": "the plan must record that this is NOT CHECKABLE IN THIS MODEL. "
                                  "The declared potential is harmonic everywhere, while a real "
                                  "trap goes to zero far from its focus. The store holds no trap "
                                  "width, so where the bench trap stops being harmonic is unknown. "
                                  "What decides it is the measured histogram's tails against a "
                                  "Gaussian, which is a bench result and the second thing this "
                                  "comparison is for",
                      "basis": ["max_excursion_soft_corner"]}),
        ],
        note="NO `varies_with` ON THE BOX, AND THAT IS AN ASSERTION: one box sized for the "
             "softest trap fits every stiffness, and with one particle and no interaction a "
             "larger box costs nothing. The axis is nearly vacuous and says so rather than "
             "abstaining, because the unwrapped trajectory needs the statement that it never "
             "wrapped.",
    )


def a4(goal, numbers, assumptions):
    """Sampling, and the exposure a camera adds that a simulation does not have."""
    g = _anchors(goal, numbers, assumptions, "a4")
    tau_stiff = _value(numbers, "trap_relaxation_time_min")
    numbers.append(cards.num(
        "save_interval_fraction", 0.1, "1", "assumed:a_save_fraction",
        precision="order_of_magnitude",
        note="the save interval as a fraction of the local gamma/k_t"))
    dt_save_max = _one(0.1 * tau_stiff)
    numbers.append(cards.num(
        "save_interval_max", dt_save_max, "s",
        source="computed:fraction_times_relaxation_time",
        formula="save_interval_fraction*trap_relaxation_time_min",
        inputs=[("save_interval_fraction", "E5"), ("trap_relaxation_time_min", g["trap_relaxation_time_min"])],
        precision="order_of_magnitude",
        note="fine enough to resolve the autocorrelation the A2 scatter rests on, and to draw "
             "the histogram from frames that are a tenth of a relaxation time apart"))
    dt_save_min = _one(0.01 * tau_stiff)
    numbers.append(cards.num(
        "save_interval_min", dt_save_min, "s",
        source="computed:hundredth_of_relaxation_time",
        formula="0.01*trap_relaxation_time_min",
        inputs=[("trap_relaxation_time_min", g["trap_relaxation_time_min"])],
        precision="order_of_magnitude",
        note="a floor: frames closer than this are correlated and add storage, not information"))
    assumptions += [
        {"rationale_id": "a_save_fraction",
         "statement": "A tenth of the relaxation time resolves the autocorrelation whose shape "
                      "the A2 scatter assumes, which is the one thing a run can check about its "
                      "own statistics.",
         "numbers": ["save_interval_fraction"],
         "falsifier": "a first run whose measured autocorrelation is flat between a tenth and "
                      "a half of tau_t loosens it",
         "gap_ref": "save_interval_fraction_of_relaxation_time_absent"},
    ]
    iv = _interval("save_interval", "s", "save_interval_max", ["trap_stiffness"], min=dt_save_min, max=dt_save_max)
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[iv],
        inequalities=[
            _ineq("save_interval << gamma/k_t, and no finer than a hundredth of it", "save_interval", interval=iv),
            _ineq("the width a camera measures is the width the simulation reports", "camera_exposure_time",
                  precondition={
                      "parameter": "camera_exposure_time",
                      "requires": "the plan must state the exposure as a condition of the "
                                  "comparison. A frame averages the position over its exposure "
                                  "t_e and narrows the variance by S(a) = 2/a**2*(a - 1 + exp(-a)) "
                                  "with a = t_e/(gamma/k_t): 0.97 at a tenth of a relaxation time, "
                                  "0.74 at one, 0.18 at ten. The simulation's positions are "
                                  "instantaneous. Either the bench exposure stays well below "
                                  "gamma/k_t -- under a tenth of it, 0.9 s at the soft trap and "
                                  "0.09 ms at the stiff one -- or the comparison applies S to "
                                  "the simulated width. Never neither",
                      "basis": ["save_interval_max"]}),
        ],
        note="Two-sided, and the lower half is the unusual one: for a width, as for a mean, "
             "samples closer than the correlation time add nothing. The exposure is the "
             "half that does not exist on this side at all and decides whether the two "
             "sides measure the same quantity.",
    )


def _allowance():
    try:
        data = json.loads(ENVELOPE.read_text())
    except FileNotFoundError:
        return None, "No envelope/budget.json is present."
    targets = data.get("targets") or []
    if len(targets) != 1:
        return None, f"envelope/budget.json declares {len(targets)} execution targets."
    lim = targets[0].get("limits") or {}
    return {"target": targets[0].get("target"), **lim}, "An allowance exists."


def a5(goal, numbers, assumptions):
    """Cost as a step budget per sweep point, on a MEASURED single-particle cost."""
    _anchors(goal, numbers, assumptions, "a5")
    allowance, allowance_note = _allowance()
    corners = {x["name"]: float(x["value"]) for x in goal.get("numbers", [])}
    n_stiff = int(round(math.log10(corners["trap_stiffness_max"] / corners["trap_stiffness_min"]))) + 1
    numbers.append(cards.num(
        "stiffness_points", n_stiff, "1", "assumed:a_sweep_grid", precision="significant_figures",
        note="one point per decade of the goal's stiffness range, plus its end, read off the goal"))
    numbers.append(cards.num(
        "cost_per_step", 5e-06, "s", "prior_run:run-20260923-201-smoke-hoomd-s1",
        precision="order_of_magnitude",
        note="62000 steps in 0.31 s of wall clock, one particle, on trap_hoomd_backend -- the "
             "same builder this configuration runs on with the flow removed. MEASURED at N=1, "
             "which the driven configuration's budget had to bracket across three decades "
             "before this run existed"))
    budget = None
    if allowance:
        wc = allowance.get("wall_clock_max") or {}
        if wc.get("unit") == "h" and wc.get("value"):
            budget = _one(float(wc["value"]) * 3600.0 / 5e-06 / n_stiff)
            numbers.append(cards.num(
                "steps_max_per_point", budget, "1", "assumed:a_step_budget",
                precision="order_of_magnitude",
                note="the share of the local wall clock one sweep point may spend, as steps. No "
                     "formula: the ceiling is the person's decision and 5.3 has no source kind "
                     "for one; the arithmetic is in the rationale"))
    assumptions += [
        {"rationale_id": "a_step_budget",
         "statement": f"Two hours from envelope/budget.json over the measured 5 us a step over "
                      f"{n_stiff} stiffness points: 7200 / 5e-6 / {n_stiff}, about "
                      f"{7200/5e-6/n_stiff:.0f} steps a point, to one figure. A point needs "
                      "about 1e4 steps, so the budget is not the constraint anywhere here.",
         "numbers": ["steps_max_per_point"],
         "falsifier": "this question's own first run replaces the prior run's cost",
         "gap_ref": "particle_step_rate_absent"},
        {"rationale_id": "a_sweep_grid",
         "statement": "A point per decade is the coarsest grid on which a trend is visible.",
         "numbers": ["stiffness_points"],
         "falsifier": "a first sweep with the width exactly on sqrt(kT/k) at every point, which "
                      "is the prediction, lets the grid thin to its ends",
         "gap_ref": "particle_step_rate_absent"},
    ]
    constraints, ineqs = [], []
    if budget is not None:
        iv = _interval("integration_steps", "1", "steps_max_per_point", max=budget)
        constraints.append(iv)
        ineqs.append(_ineq("record_length/integration_timestep <= wall_clock_max/(cost_per_step*stiffness_points)",
                           "integration_steps", interval=iv))
    ineqs.append(_ineq("predicted storage <= the local target's storage_max", "storage",
        precondition={"parameter": "storage",
                      "requires": "the plan must state the frame count, record_length/save_interval, "
                                  "which is A2's and A4's to fix; a thousand frames of three "
                                  "coordinates is tens of kilobytes",
                      "basis": ["stiffness_points"]}))
    return dict(
        method="deterministic", verdict="feasible" if budget is not None else "abstain",
        **({} if budget is not None else {"abstain_reason": "no single-target allowance. " + allowance_note}),
        constraints=constraints, inequalities=ineqs,
        note="THE COST IS MEASURED, NOT BRACKETED: one particle on the builder this "
             "configuration uses. The budget is five orders above what a point needs.",
    )


def a7(goal, numbers, assumptions):
    """Nothing is driven. The card records that the axis was asked."""
    return dict(
        method="deterministic", verdict="abstain",
        abstain_reason=("No driving. bd_overdamped_trapped is declared undriven: the fluid is at "
                        "rest and nothing moves the trap, so there is no driving amount for this "
                        "axis to bound. Abstaining is not being absent: this card is the record "
                        "that the axis was asked and had nothing to constrain (P1)."),
        note="numbers[] is empty because an abstention has nothing to measure. The driven "
             "sibling, bd_overdamped_trapped_uniform_flow, is where this axis owns the speed.",
    )


AXES = {"a1": a1, "a2": a2, "a3": a3, "a4": a4, "a5": a5, "a7": a7}


def build(axis, qid, config, created_at, caller_id, kb_version, kb_result, revision):
    if not caller_id.endswith(f":{axis}"):
        raise ValueError(f"{caller_id!r} was issued to another axis; this is {axis}")
    goal = cards.load_goal(qid, revision)
    numbers: list[dict] = []
    assumptions: list[dict] = []
    body = AXES[axis](goal, numbers, assumptions)
    note = body.pop("note", None)
    card = _head(axis, qid, config, created_at, caller_id, kb_version, revision, **body)
    card.update(cards.tail(numbers, assumptions=assumptions,
                           **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
    if note:
        card["note"] = note
    return card
