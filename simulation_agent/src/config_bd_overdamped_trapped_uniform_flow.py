"""A1-A7 for `bd_overdamped_trapped_uniform_flow` (plan.md 4.5.2, 4.5.3).

One sphere, overdamped, no pair interaction, an external harmonic potential of
stiffness `k_t`, and a uniform background fluid velocity. Registered at
`8a0d036` for sim-20260923-201.

**Why the six shared modules cannot be reused.** They were written for
`bd_overdamped`, where the only characteristic time is the diffusive one,
`tau_d = d**2/D`. Under a trap the relaxation time `tau_t = gamma/k_t` sits
two to five decades below it across this sweep, so A1 bounded by `tau_d`
would return a timestep five decades too loose and the card would validate.
And the flow adds a deterministic drift the free configuration has no term
for, which turns out to be what actually binds A1 here.

**The exact identity this whole module leans on.** For an Ornstein-Uhlenbeck
coordinate, the stationary width, the diffusivity and the relaxation time are
not three independent facts:

    sigma**2 = k_B*T/k_t ,  D = k_B*T/gamma ,  tau_t = gamma/k_t
    =>  sigma**2 = D * tau_t                               (exactly)

That is used three times below, and each time it collapses something that
looks like two constraints into one. It is stated once here so the three
sites can point at it instead of re-deriving it.
"""

from __future__ import annotations

import json
import math

from . import cards
from .physics import K_B

ENVELOPE = cards.AGENT / "envelope" / "budget.json"

ANCHORS = ["bead_diameter", "temperature", "viscosity", "diffusivity",
           "diffusive_time", "sigma_over_diameter_soft_corner",
           "trap_stiffness_min", "trap_stiffness_max",
           "trap_relaxation_time_min", "trap_relaxation_time_max",
           "offset_over_sigma_min", "offset_over_sigma_max"]

# What each axis CARRIES, which is not the whole anchor set. cards.carry's own
# docstring gives the reason -- "A1 would end up holding a temperature it has
# no use for" -- and there is a second, sharper one found by running it: carry
# narrows the goal's assumptions to those whose numbers came along, so an axis
# that carries an anchor it does not use inherits an assumption it does not
# use, and check 39 then demands the gap behind that assumption in a card with
# no business citing it. Six axes each asking the store for two names they do
# not need is what a too-wide carry list costs.
USES = {
    "a1": ["trap_relaxation_time_min", "offset_over_sigma_max"],
    "a2": ["trap_relaxation_time_min", "trap_relaxation_time_max",
           "offset_over_sigma_min"],
    "a3": ["bead_diameter", "sigma_over_diameter_soft_corner",
           "offset_over_sigma_max"],
    "a4": ["trap_relaxation_time_min"],
    "a5": [],
    "a7": ["bead_diameter", "temperature", "viscosity", "diffusivity",
           "sigma_over_diameter_soft_corner", "trap_stiffness_max",
           "trap_relaxation_time_min", "trap_relaxation_time_max",
           "offset_over_sigma_max"],
}

# One kb_query per name, per axis. A gap that comes back is the gap_ref of the
# assumption standing where the entry would have been.
QUERIES = {
    "a1": ["integration_timestep_resolution_factor", "flow_speed"],
    "a2": ["statistical_target_confirm", "flow_speed"],
    "a3": ["trapped_particle_drag_offset", "trap_stiffness", "flow_speed"],
    "a4": ["save_interval_fraction_of_relaxation_time"],
    "a5": ["cost_per_particle_step_overdamped", "flow_speed"],
    "a7": ["flow_speed", "trap_escape_force", "temperature", "trap_stiffness"],
}


def applicable(goal: dict) -> tuple[bool, str]:
    """This configuration answers a goal that names a trap and a flow.

    It is the only one producing `trapped_particle_drag_offset` today, so this
    cannot yet discriminate between siblings. It is here because the check is
    cheap and because a goal reaching this module without the sweep corners
    would otherwise fail deep inside an axis with a KeyError -- the shape
    fanout.plan_queries was just repaired for.
    """
    named = {n["name"] for n in goal.get("numbers", []) or []}
    missing = [n for n in ANCHORS if n not in named]
    if missing:
        return False, (
            "this goal carries no " + ", ".join(missing) + " in numbers[]. The trap "
            "relaxation time and the dimensionless offset are what every axis here is "
            "written in, and neither can be derived from a goal that does not state the "
            "sweep. Cut a revision carrying them (4.5.1) rather than defaulting them here: "
            "a default range is a decision, and an axis is not where decisions are made."
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
# helpers, the same shape the other configuration modules use
# --------------------------------------------------------------------------- #

def _value(numbers: list[dict], name: str) -> float:
    return next(n for n in numbers if n["name"] == name)["value"]


def _head(axis, qid, config, created_at, caller_id, kb_version, revision, **kw):
    return cards.head(
        "axis",
        f"axis-{qid}-{config}-{axis}" + ("" if revision == 1 else f"-r{revision}"),
        qid, created_at, revision=revision, caller_id=caller_id, config=config,
        axis=axis, kb_version=kb_version, **kw,
    )


def _interval(parameter, unit, basis, **bound):
    return {"parameter": parameter, "unit": unit, **bound,
            "basis": [basis], "precision": "order_of_magnitude"}


def _ineq(text, parameter, interval=None, precondition=None):
    out = {"inequality": text, "parameter": parameter, "state": "returned"}
    if interval is not None:
        out["interval"] = interval
    if precondition is not None:
        out["precondition"] = precondition
    return out


def _one(x: float) -> float:
    """One significant figure, ties away from zero.

    `f"{x:.0e}"` is NOT this: Python formats half-to-even, so 25 becomes 2e+01
    while contracts/validate.py's `round_to_sig` gives 30 and check 17 fails
    on a number that is right. Copied from the validator's rule rather than
    approximated, because the two have to agree exactly or every borderline
    value is a false failure. Found by running it (a7's soft-corner speed).
    """
    if x == 0:
        return 0.0
    exp = math.floor(math.log10(abs(x)))
    scale = 10 ** (0 - exp)
    scaled = abs(x) * scale
    rounded = math.floor(scaled) + (1 if scaled - math.floor(scaled) >= 0.5 else 0)
    return math.copysign(rounded / scale, x)


def _anchors(goal, numbers, assumptions, axis):
    carried, carried_assumptions = cards.carry(goal, USES[axis])
    numbers += carried
    assumptions += carried_assumptions
    return {n["name"]: n["grade"] for n in numbers}


# --------------------------------------------------------------------------- #
# axes
# --------------------------------------------------------------------------- #

def a1(goal, numbers, assumptions):
    """Three bounds on the timestep, and two of them are the same inequality."""
    g = _anchors(goal, numbers, assumptions, "a1")
    tau_stiff = _value(numbers, "trap_relaxation_time_min")
    ratio_max = _value(numbers, "offset_over_sigma_max")

    numbers.append(cards.num(
        "dt_resolution_factor", 0.01, "1", "assumed:a_dt_factor",
        precision="order_of_magnitude",
        note="how far below the shortest resolved time the step sits. Two decades is the "
             "usual margin for an overdamped integrator, a convention and not a derivation"))
    dt_relax = _one(0.01 * tau_stiff)
    numbers.append(cards.num(
        "dt_max_relaxation", dt_relax, "s", "computed:factor_times_relaxation_time",
        formula="dt_resolution_factor*trap_relaxation_time_min",
        inputs=[("dt_resolution_factor", "E5"), ("trap_relaxation_time_min", g["trap_relaxation_time_min"])],
        precision="order_of_magnitude",
        note="dt << gamma/k_t at the STIFF corner, which is the shortest characteristic "
             "time in the problem. bd_overdamped's A1 would have bounded the step by the "
             "diffusive time instead, five decades looser"))

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
             "so this reduces to dt << tau_t and differs from the line above only by the "
             "factor chosen. Recorded because it looks independent and is not -- under a "
             "trap the thermal width IS the diffusive displacement over one relaxation "
             "time, which is why a seat reading bd_pairwise's A1, where the screening "
             "length and the curvature time are genuinely different scales, would expect "
             "two bounds here and find one"))

    numbers.append(cards.num(
        "drift_step_fraction", 0.1, "1", "assumed:a_drift_step",
        precision="order_of_magnitude",
        note="the flow's deterministic displacement per step as a fraction of the "
             "thermal width"))
    dt_drift = _one(0.1 * tau_stiff / ratio_max)
    numbers.append(cards.num(
        "dt_max_drift", dt_drift, "s", "computed:drift_step_inside_thermal_width",
        formula="drift_step_fraction*trap_relaxation_time_min/offset_over_sigma_max",
        inputs=[("drift_step_fraction", "E5"), ("trap_relaxation_time_min", g["trap_relaxation_time_min"]),
                ("offset_over_sigma_max", g["offset_over_sigma_max"])],
        precision="order_of_magnitude",
        note="v*dt << sigma. THE ONE THAT BINDS, and the one bd_overdamped has no term "
             "for at all, because it has no drift. Writing v as (offset/sigma)*sigma/tau_t "
             "makes it dt << tau_t/(offset/sigma), so it is tighter than the relaxation "
             "bound by the whole dimensionless offset -- two decades at the fast corner"))

    assumptions += [
        {"rationale_id": "a_dt_factor",
         "statement": "Two decades below the shortest resolved time is the usual margin for "
                      "an overdamped integrator. A convention, not a derivation, and no "
                      "timestep scan has been run on this configuration.",
         "numbers": ["dt_resolution_factor"],
         "falsifier": "a timestep scan showing the recovered stiffness flat over a wider "
                      "range of steps replaces the factor with a measured one",
         "gap_ref": "integration_timestep_resolution_factor_absent"},
        {"rationale_id": "a_noise_step",
         "statement": "A tenth of the thermal width per step. Kept although it is not "
                      "independent of the relaxation bound, because the identity that makes "
                      "it dependent is exact only for the harmonic potential declared here: "
                      "add anharmonicity and the two separate again.",
         "numbers": ["noise_step_fraction"],
         "falsifier": "a configuration with a non-quadratic trap makes this a distinct bound "
                      "and this note wrong",
         "gap_ref": "integration_timestep_resolution_factor_absent"},
        {"rationale_id": "a_drift_step",
         "statement": "A tenth of the thermal width of deterministic travel per step keeps "
                      "the restoring force felt during a step close to the force at its "
                      "start. This is the bound that decides dt, and it is set by the fast "
                      "end of the speed sweep rather than by the trap alone.",
         "numbers": ["drift_step_fraction"],
         "falsifier": "a person's narrower speed range raises it in proportion; a scan "
                      "showing the recovered offset flat at larger drift fractions retires it",
         "gap_ref": "flow_speed_absent"},
    ]
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[
            _interval("integration_timestep", "s", "dt_max_drift", max=dt_drift),
            _interval("integration_timestep", "s", "dt_max_noise", max=dt_noise),
            _interval("integration_timestep", "s", "dt_max_relaxation", max=dt_relax),
        ],
        inequalities=[
            _ineq("v*dt << sigma at the fastest point of the sweep", "integration_timestep",
                  interval=_interval("integration_timestep", "s", "dt_max_drift", max=dt_drift)),
            _ineq("sqrt(2*D*dt) << sigma at the stiffest point", "integration_timestep",
                  interval=_interval("integration_timestep", "s", "dt_max_noise", max=dt_noise)),
            _ineq("dt << gamma/k_t at the stiffest point", "integration_timestep",
                  interval=_interval("integration_timestep", "s", "dt_max_relaxation", max=dt_relax)),
        ],
        note="S4 takes the tightest, which is the drift bound. All three are recorded "
             "because which one binds moves with the sweep: at the slow end the drift bound "
             "relaxes by two decades and the relaxation bound takes over. The middle one is "
             "kept knowing it is not independent -- sigma**2 = D*tau_t makes it the first "
             "one again -- because a reader who does not know that identity would otherwise "
             "add it back.",
    )


def a2(goal, numbers, assumptions):
    """Record length. Two different constraints bind at the two corners."""
    g = _anchors(goal, numbers, assumptions, "a2")
    tau_soft = _value(numbers, "trap_relaxation_time_max")
    tau_stiff = _value(numbers, "trap_relaxation_time_min")
    ratio_min = _value(numbers, "offset_over_sigma_min")

    numbers.append(cards.num(
        "relaxation_times_per_record", 100, "1", "assumed:a_record_floor",
        precision="order_of_magnitude",
        note="the FLOOR on a record in units of gamma/k_t. Below this the mean is not a "
             "stationary average and the standard error expression does not apply, "
             "whatever the target accuracy is"))
    t_floor_soft = _one(100 * tau_soft)
    numbers.append(cards.num(
        "record_length_floor_soft_corner", t_floor_soft, "s",
        source="computed:relaxation_times_times_tau",
        formula="relaxation_times_per_record*trap_relaxation_time_max",
        inputs=[("relaxation_times_per_record", "E5"), ("trap_relaxation_time_max", g["trap_relaxation_time_max"])],
        precision="order_of_magnitude",
        note="the soft corner's floor, which is where the floor is worst"))
    t_floor_stiff = _one(100 * tau_stiff)
    numbers.append(cards.num(
        "record_length_floor_stiff_corner", t_floor_stiff, "s",
        source="computed:relaxation_times_times_tau",
        formula="relaxation_times_per_record*trap_relaxation_time_min",
        inputs=[("relaxation_times_per_record", "E5"), ("trap_relaxation_time_min", g["trap_relaxation_time_min"])],
        precision="order_of_magnitude",
        note="the stiff corner's floor. AT THIS CORNER THE FLOOR IS WHAT BINDS, not the "
             "statistics: the offset is already many thermal widths, so the error target "
             "is met long before a hundred relaxation times have passed"))

    # The error model, written in the dimensionless variable so the cancellation is visible.
    numbers.append(cards.num(
        "relative_error_at_floor_soft_slow", _one(math.sqrt(2.0 / 100) / ratio_min), "1",
        source="computed:ou_standard_error_of_the_mean",
        formula="(2/relaxation_times_per_record)**0.5/offset_over_sigma_min",
        inputs=[("relaxation_times_per_record", "E5"), ("offset_over_sigma_min", g["offset_over_sigma_min"])],
        precision="order_of_magnitude",
        note="SE/signal = sqrt(2*tau_t/T)/(offset/sigma). THE STIFFNESS IS ABSENT FROM "
             "THIS EXPRESSION AND THAT IS THE RESULT THE QUESTION EXISTS TO TEST: signal "
             "and noise-on-the-mean both scale as 1/k_t and cancel. At the worst corner -- "
             "soft trap, offset one thermal width -- a hundred relaxation times give about "
             "this fractional error, and only a longer record improves it"))

    assumptions += [
        {"rationale_id": "a_record_floor",
         "statement": "A hundred relaxation times is the floor for treating the trapped "
                      "coordinate as a stationary Ornstein-Uhlenbeck average. It is a "
                      "convention and it is not the accuracy requirement -- the accuracy "
                      "requirement is a target the person has not given, which is why this "
                      "axis returns a floor and a relation rather than a record length.",
         "numbers": ["relaxation_times_per_record"],
         "falsifier": "a measured autocorrelation on a first run replaces the factor with "
                      "the record length at which the mean stops drifting",
         "gap_ref": "statistical_target_confirm_absent"},
    ]
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[
            _interval("record_length", "s", "record_length_floor_soft_corner", min=t_floor_soft),
        ],
        inequalities=[
            _ineq("record_length >> gamma/k_t, at the softest point of the sweep",
                  "record_length",
                  interval=_interval("record_length", "s", "record_length_floor_soft_corner",
                                     min=t_floor_soft)),
            _ineq("record_length >= 2*(gamma/k_t)/((offset/sigma)*target_relative_error)**2",
                  "record_length",
                  precondition={
                      "parameter": "record_length",
                      "requires": "the plan must carry a target relative error on the "
                                  "recovered stiffness. The goal's targets[] is empty, so "
                                  "this inequality is a RELATION AND NOT AN INTERVAL: it is "
                                  "the binding one at the soft, slow corner, where a one per "
                                  "cent target asks about four decades more record than the "
                                  "floor and will not fit inside the local wall clock. The "
                                  "target accuracy and the speed range are therefore not "
                                  "independent choices, which is the trade this axis hands up",
                      "basis": ["offset_over_sigma_min", "relaxation_times_per_record"]}),
        ],
        note="Two constraints bind at two different corners, which is what makes this sweep "
             "expensive in a way neither corner shows alone. At the stiff, fast corner the "
             "floor binds and the statistics are free. At the soft, slow corner the "
             "statistics bind and the floor is free. A plan that sizes the record at one "
             "corner and reuses it at the other is wrong in one direction or the other.",
    )


def a3(goal, numbers, assumptions):
    """Finite size, and the honest answer is that it costs nothing here."""
    g = _anchors(goal, numbers, assumptions, "a3")
    d = _value(numbers, "bead_diameter")
    ratio_max = _value(numbers, "offset_over_sigma_max")
    sigma_frac = 0.1   # the soft corner's thermal width, as a fraction of the diameter
    excursion = _one(ratio_max * sigma_frac * d)

    numbers.append(cards.num(
        "max_offset_soft_corner", excursion, "um",
        source="computed:offset_ratio_times_thermal_width",
        formula="offset_over_sigma_max*sigma_over_diameter_soft_corner*bead_diameter",
        inputs=[("offset_over_sigma_max", g["offset_over_sigma_max"]),
                ("sigma_over_diameter_soft_corner", g["sigma_over_diameter_soft_corner"]),
                ("bead_diameter", g["bead_diameter"])],
        precision="order_of_magnitude",
        note="the largest steady-state displacement anywhere in the sweep, at the soft "
             "corner and the fast end. Ten bead diameters"))
    box = _one(10 * excursion)
    numbers.append(cards.num(
        "box_edge_min", box, "um", source="computed:margin_times_max_offset",
        formula="10*max_offset_soft_corner", inputs=[("max_offset_soft_corner", "E5")],
        precision="order_of_magnitude",
        note="a decade of margin on the excursion, so the recorded trajectory never "
             "approaches a boundary"))

    return dict(
        method="deterministic", verdict="feasible",
        constraints=[_interval("box_edge", "um", "box_edge_min", min=box)],
        inequalities=[
            _ineq("box_edge >> the steady-state offset at the softest, fastest corner",
                  "box_edge",
                  interval=_interval("box_edge", "um", "box_edge_min", min=box)),
        ],
        note="THIS AXIS IS NEARLY VACUOUS HERE AND SAYS SO RATHER THAN ABSTAINING. There is "
             "one particle, no pair potential and no wall, so there is no periodic image to "
             "meet and nothing in the physics depends on the box at all -- the bound above "
             "is a recording convention, not a physical constraint. It also costs nothing: "
             "with no interaction there is no neighbour list, so enlarging the box is free, "
             "which is the opposite of every other configuration where A3 and A5 trade "
             "against each other. The bound is still written down because the trajectory is "
             "stored in unwrapped coordinates (013) and a reader needs to know the offset "
             "never wrapped.",
    )


def a4(goal, numbers, assumptions):
    """Sampling, and the interval has a LOWER bound for a reason A4 usually lacks."""
    g = _anchors(goal, numbers, assumptions, "a4")
    tau_stiff = _value(numbers, "trap_relaxation_time_min")

    numbers.append(cards.num(
        "save_interval_fraction", 0.1, "1", "assumed:a_save_fraction",
        precision="order_of_magnitude",
        note="the save interval as a fraction of gamma/k_t at the stiff corner"))
    dt_save_max = _one(0.1 * tau_stiff)
    numbers.append(cards.num(
        "save_interval_max", dt_save_max, "s",
        source="computed:fraction_times_relaxation_time",
        formula="save_interval_fraction*trap_relaxation_time_min",
        inputs=[("save_interval_fraction", "E5"), ("trap_relaxation_time_min", g["trap_relaxation_time_min"])],
        precision="order_of_magnitude",
        note="fine enough to resolve the approach to steady state and to measure the "
             "autocorrelation the error model rests on"))
    dt_save_min = _one(0.01 * tau_stiff)
    numbers.append(cards.num(
        "save_interval_min", dt_save_min, "s",
        source="computed:hundredth_of_relaxation_time",
        formula="0.01*trap_relaxation_time_min",
        inputs=[("trap_relaxation_time_min", g["trap_relaxation_time_min"])],
        precision="order_of_magnitude",
        note="A LOWER BOUND, WHICH THIS AXIS DOES NOT USUALLY CARRY. For a MEAN, samples "
             "closer together than the correlation time are not independent and add no "
             "information -- only storage. That is the reverse of the diffusivity case, "
             "where the MSD fit needs lags far below tau_d and oversampling is what buys "
             "the short-lag points. Saving faster than this is pure cost"))

    assumptions += [
        {"rationale_id": "a_save_fraction",
         "statement": "A tenth of the relaxation time resolves the autocorrelation whose "
                      "shape the A2 error model assumes, which is the one thing the run can "
                      "genuinely check about its own statistics.",
         "numbers": ["save_interval_fraction"],
         "falsifier": "a first run whose measured autocorrelation is flat between a tenth "
                      "and a half of tau_t loosens it",
         "gap_ref": "save_interval_fraction_of_relaxation_time_absent"},
    ]
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[_interval("save_interval", "s", "save_interval_max",
                               min=dt_save_min, max=dt_save_max)],
        inequalities=[
            _ineq("save_interval << gamma/k_t, so the relaxation is resolved", "save_interval",
                  interval=_interval("save_interval", "s", "save_interval_max", max=dt_save_max)),
            _ineq("save_interval >= 0.01*gamma/k_t, because a mean gains nothing from "
                  "correlated samples", "save_interval",
                  interval=_interval("save_interval", "s", "save_interval_min", min=dt_save_min)),
        ],
        note="A two-sided interval, and the lower half is the unusual one. The save interval "
             "should scale with the LOCAL relaxation time at each stiffness rather than being "
             "fixed at the stiff corner's value: three decades of stiffness is three decades "
             "of tau_t, and a single interval sized for the stiff corner would store a "
             "thousand times more frames than the soft corner can use.",
    )


def a5(goal, numbers, assumptions):
    """Cost, as a constraint on the settable parameters and not a prediction."""
    g = _anchors(goal, numbers, assumptions, "a5")

    allowance, allowance_note = _allowance()
    numbers.append(cards.num(
        "stiffness_points", 4, "1", "assumed:a_sweep_grid", precision="order_of_magnitude",
        note="one point per decade across the three-decade stiffness sweep, plus its end"))
    numbers.append(cards.num(
        "speed_points", 3, "1", "assumed:a_sweep_grid", precision="order_of_magnitude",
        note="one per decade of the dimensionless offset, plus its end. A drag calibration "
             "needs at least three speeds for the slope to have a residual"))

    assumptions += [
        {"rationale_id": "a_sweep_grid",
         "statement": "A point per decade is the coarsest grid on which a slope has a "
                      "residual and a trend is visible. The grid is a decision and not a "
                      "measurement, and it is here rather than in the goal because it is "
                      "what turns two ranges into a run count.",
         "numbers": ["stiffness_points", "speed_points"],
         "falsifier": "a first sweep in which the recovered error is flat across stiffness, "
                      "which is the prediction, allows the stiffness axis to be thinned to "
                      "its two ends; a curved slope residual demands more speeds",
         "gap_ref": "flow_speed_absent"},
    ]
    return dict(
        method="deterministic", verdict="abstain",
        abstain_reason=(
            "This axis constrains the settable parameters against the envelope and does not "
            "yet turn them into an interval. " + allowance_note + " What stops it being "
            "computable is not the ceiling: it is that the record length A2 needs is a "
            "function of a target relative error the person has not set, so the step count "
            "has a free parameter in it. The cost is therefore stated as a relation for S4 "
            "and not as a number. THE RELATION THAT MATTERS IS NOT THE ONE THIS CARD FIRST "
            "STATED. It said the timestep is fixed by the stiff corner and the record by the "
            "soft one, so the cost goes as the RATIO of the stiffness range -- three decades "
            "of stiffness, three decades of steps. That is true of a plan carrying ONE "
            "timestep and ONE record length, and it is not a property of the sweep. Both "
            "bounds scale with the same local gamma/k_t, so at parameters chosen PER CORNER "
            "the step count is the same at every corner and the sweep is flat in cost. The "
            "blow-up is what intersecting one interval per parameter does to a swept "
            "question, and the factor it costs is exactly the stiffness range. Raised to "
            "manager-simulation rather than worked around here: an axis returning one "
            "interval is 4.5.3's contract and a sweep is not one operating point. A5 does "
            "not take A1's or A2's output as input (rule b) -- the scaling above is read off "
            "the SHAPE of the two bounds, both of which are proportional to the local "
            "relaxation time, and no number crosses."),
        constraints=[],
        inequalities=[
            _ineq("predicted wall clock <= the local target's wall_clock_max",
                  "wall_clock",
                  precondition={
                      "parameter": "wall_clock",
                      "requires": "the plan must carry a target relative error before a "
                                  "wall clock can be predicted: the record length is a "
                                  "function of it, so the step count has a free parameter. "
                                  + allowance_note,
                      "basis": ["stiffness_points", "speed_points"]}),
            _ineq("predicted storage <= the local target's storage_max", "storage",
                  precondition={
                      "parameter": "storage",
                      "requires": "frames are record_length/save_interval and the record "
                                  "length is unset for the same reason. The trajectory is "
                                  "written to disk now (013), so this is a real ceiling "
                                  "rather than a notional one",
                      "basis": ["stiffness_points", "speed_points"]}),
        ],
        note="The abstention is THIS AGENT'S UNFINISHED WORK and not a missing ceiling -- "
             "the distinction bd_overdamped's a5 card had to make once the envelope existed. "
             "The blocking input is the person's target accuracy, which is also what A2 is "
             "waiting on, so one answer releases both.",
    )


def _allowance() -> tuple[dict | None, str]:
    """The envelope's ceilings, read rather than asserted."""
    try:
        data = json.loads(ENVELOPE.read_text())
    except FileNotFoundError:
        return None, "No envelope/budget.json is present, so there is no allowance to compare against."
    targets = data.get("targets") or []
    if len(targets) != 1:
        return None, (f"envelope/budget.json declares {len(targets)} execution targets and a "
                      "plan carries no target field, so which ceiling applies cannot be "
                      "decided here.")
    t = targets[0]
    return t, (f"An allowance exists: target {t.get('target')!r}, wall clock "
               f"{t.get('wall_clock_max', {}).get('value')} "
               f"{t.get('wall_clock_max', {}).get('unit')}, storage "
               f"{t.get('storage_max', {}).get('value')} "
               f"{t.get('storage_max', {}).get('unit')}.")


def a7(goal, numbers, assumptions):
    """Driving. Live for the first time on this side, and it owns the speed."""
    g = _anchors(goal, numbers, assumptions, "a7")
    d = _value(numbers, "bead_diameter")
    D = _value(numbers, "diffusivity")
    tau_soft = _value(numbers, "trap_relaxation_time_max")
    tau_stiff = _value(numbers, "trap_relaxation_time_min")
    ratio_max = _value(numbers, "offset_over_sigma_max")
    sigma_soft = _value(numbers, "sigma_over_diameter_soft_corner") * d   # um
    # In micrometres, from the same expression the formula string declares.
    # Computed rather than scaled off the soft corner by sqrt(1000): that
    # shortcut rounds the width first and the speed second, and check 17
    # recomputes from the formula in one step -- 1000 um/s against 700.
    k_stiff_si = _value(numbers, "trap_stiffness_max") * 1e-6      # pN/um -> N/m
    sigma_stiff = math.sqrt(K_B * _value(numbers, "temperature") / k_stiff_si) * 1e6

    v_soft_max = _one(ratio_max * sigma_soft / tau_soft)
    numbers.append(cards.num(
        "flow_speed_max_soft_corner", v_soft_max, "um/s",
        source="computed:offset_ratio_times_width_over_tau",
        formula="offset_over_sigma_max*sigma_over_diameter_soft_corner*bead_diameter"
                "/trap_relaxation_time_max",
        inputs=[("offset_over_sigma_max", g["offset_over_sigma_max"]),
                ("sigma_over_diameter_soft_corner", g["sigma_over_diameter_soft_corner"]),
                ("bead_diameter", g["bead_diameter"]),
                ("trap_relaxation_time_max", g["trap_relaxation_time_max"])],
        precision="order_of_magnitude",
        note="v = (offset/sigma)*sigma/tau_t. THE SPEED IS NOT ONE NUMBER FOR THE SWEEP: "
             "the same speed is a large offset in a soft trap and invisible in a stiff one, "
             "so A7 returns a speed per stiffness and the goal carries the dimensionless "
             "corner instead"))
    v_stiff_max = _one(ratio_max * sigma_stiff / tau_stiff)
    numbers.append(cards.num(
        "flow_speed_max_stiff_corner", v_stiff_max, "um/s",
        source="computed:offset_ratio_times_width_over_tau",
        formula="offset_over_sigma_max*(k_B*temperature/trap_stiffness_max)**0.5/trap_relaxation_time_min",
        inputs=[("offset_over_sigma_max", g["offset_over_sigma_max"]),
                ("temperature", g["temperature"]),
                ("trap_stiffness_max", g["trap_stiffness_max"]),
                ("trap_relaxation_time_min", g["trap_relaxation_time_min"])],
        precision="order_of_magnitude",
        note="the same dimensionless offset at the stiff corner needs a speed larger by "
             "sqrt(1000), because sigma falls as 1/sqrt(k_t) while tau_t falls as 1/k_t"))

    peclet = _one((v_soft_max * d) / D)
    numbers.append(cards.num(
        "peclet_number_max", peclet, "1", source="computed:v_d_over_diffusivity",
        formula="flow_speed_max_soft_corner*bead_diameter/diffusivity",
        inputs=[("flow_speed_max_soft_corner", "E5"), ("bead_diameter", g["bead_diameter"]),
                ("diffusivity", g["diffusivity"])],
        precision="order_of_magnitude",
        note="advection against diffusion over a bead diameter. Large at the fast end, "
             "which is the point: that is where the offset is visible in a single frame"))

    numbers.append(cards.num(
        "startup_relaxation_times", 10, "1", "assumed:a_startup",
        precision="order_of_magnitude",
        note="how many gamma/k_t to discard after the flow is switched on, before the "
             "record begins"))
    startup_soft = _one(10 * tau_soft)
    numbers.append(cards.num(
        "startup_discard_soft_corner", startup_soft, "s",
        source="computed:startup_times_tau",
        formula="startup_relaxation_times*trap_relaxation_time_max",
        inputs=[("startup_relaxation_times", "E5"), ("trap_relaxation_time_max", g["trap_relaxation_time_max"])],
        precision="order_of_magnitude",
        note="the approach to the displaced steady state is exponential with time constant "
             "gamma/k_t, so ten of them leaves a residual offset error below a per-mille. "
             "DECLARED IN ADVANCE and evaluated by the operator, never chosen after seeing "
             "the data"))

    assumptions += [
        {"rationale_id": "a_startup",
         "statement": "Ten relaxation times of discard. The displaced mean approaches its "
                      "steady value as exp(-t*k_t/gamma) with no other slow mode in this "
                      "model, so the residual is set purely by the multiple chosen.",
         "numbers": ["startup_relaxation_times"],
         "falsifier": "a first run whose running mean is still drifting after ten relaxation "
                      "times falsifies the single-exponential premise and therefore the model, "
                      "not just the multiple",
         "gap_ref": "flow_speed_absent"},
    ]
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[
            _interval("flow_speed", "um/s", "flow_speed_max_soft_corner", max=v_soft_max),
            _interval("startup_discard", "s", "startup_discard_soft_corner", min=startup_soft),
        ],
        inequalities=[
            _ineq("the imposed speed realises the declared dimensionless offset at each "
                  "stiffness", "flow_speed",
                  interval=_interval("flow_speed", "um/s", "flow_speed_max_soft_corner",
                                     max=v_soft_max)),
            _ineq("startup_discard >> gamma/k_t, so the record begins at steady state",
                  "startup_discard",
                  interval=_interval("startup_discard", "s", "startup_discard_soft_corner",
                                     min=startup_soft)),
            _ineq("Reynolds number << 1, so the overdamped model holds", "flow_speed",
                  precondition={
                      "parameter": "flow_speed",
                      "requires": "the plan must state the fluid density this premise rests "
                                  "on. THE NUMBER WAS WRITTEN HERE AND REMOVED: rho*v*d/eta "
                                  "needs a density, the store carries water's VISCOSITY and "
                                  "not its density, and a literal 1000 in the formula made "
                                  "check 17 report a dimension of L**3/M -- the check "
                                  "catching a constant smuggled in without its units, which "
                                  "is what P2 is for. The Peclet number beside it needs no "
                                  "density and is computed. By hand the Reynolds number is "
                                  "of order 1e-7 across the sweep, so the premise is not in "
                                  "doubt; what is missing is a graded number to stand it on",
                      "basis": ["flow_speed_max_soft_corner"]}),
            _ineq("the steady-state offset stays inside the trap's quadratic range",
                  "flow_speed",
                  precondition={
                      "parameter": "flow_speed",
                      "requires": "the plan must record that this is NOT CHECKABLE IN THIS "
                                  "MODEL, which is this axis's main finding. The potential is "
                                  "harmonic by declaration, so it has no linear range to "
                                  "leave and no maximum restoring force to exceed: the "
                                  "particle never escapes at any speed. On the bench both end "
                                  "a drag calibration, and the fast end of this sweep is "
                                  "where they would -- at the soft corner the largest offset "
                                  "is ten bead diameters, which no real optical trap "
                                  "survives. So the model reports the method working over a "
                                  "range the instrument does not have, and no run of it can "
                                  "detect that. kb:trap_escape_force is absent, so there is "
                                  "not even a number to compare against. Declaring a maximum "
                                  "trap force is the person's call and makes a different "
                                  "configuration rather than setting a parameter",
                      "basis": ["flow_speed_max_soft_corner"]}),
        ],
        note="A7 STOPS ABSTAINING HERE, which is the structural difference from every other "
             "configuration this agent has run. It also owns the speed outright: because the "
             "statistics depend on the offset in thermal widths and not on the speed, the "
             "goal carries the dimensionless corners and this axis turns them into a speed at "
             "each stiffness. The one inequality it cannot close is the one that matters most "
             "for the bench, and it is a limit of the declared model rather than of the "
             "protocol.",
    )


AXES = {"a1": a1, "a2": a2, "a3": a3, "a4": a4, "a5": a5, "a7": a7}


def build(axis, qid, config, created_at, caller_id, kb_version, kb_result, revision):
    if not caller_id.endswith(f":{axis}"):
        raise ValueError(f"{caller_id!r} was issued to another axis; this is {axis}")
    goal = cards.load_goal(qid, revision)
    numbers: list[dict] = []
    assumptions: list[dict] = []
    body = AXES[axis](goal, numbers, assumptions)
    card = _head(axis, qid, config, created_at, caller_id, kb_version, revision, **body)
    card.update(cards.tail(numbers, assumptions=assumptions,
                           **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
    if "note" in body:
        card["note"] = body["note"]
    return card
