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
import sys

from . import cards
from .physics import K_B

# 7.2's diagram says planning-stage code "imports contracts only", so the
# rounding rule is CALLED rather than copied. It cannot be a bare import: the
# agent runs as `python3 -m src.fanout` from simulation_agent/, where the
# repository root is not on the path, so the root is put there the way
# cards.py and physics.py already locate it.
#
# `cards.py`'s docstring says this module "reads contracts/ as data and
# imports nothing from it (7.2 rule 2)". Rule 2 says planning code knows no
# DEVICE; it says nothing about contracts, and the diagram above it permits
# this import outright. That mis-citation is why SOURCE_GRADE is a second
# copy, and cards.py records what the copy cost: two days where
# grade_for("prior_run:...") raised against 26 store entries, found by
# counting the two tables and not by a failure.
#
# The objection to importing it -- that the shared working copy's validator
# moves under you -- is real and does not apply here. The cards are judged by
# that same volatile file, so a shared rule keeps generation and judgement in
# agreement while a copy drifts silently out of it.
_ROOT = str(cards.REPO)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from contracts.validate import round_to_sig  # noqa: E402

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


def _interval(parameter, unit, basis, varies_with=None, **bound):
    """An allowed range, and whether it is a function of the sweep.

    `varies_with` names the sweep axes the bound moves with, so S4 evaluates
    it per point instead of intersecting it across the whole sweep. ABSENCE IS
    A CLAIM that the bound is constant over the sweep, so every interval below
    either carries the field or means that -- there is no third state, and an
    omission here is now a wrong assertion rather than a missing one.

    The field exists because of this configuration. Intersecting the timestep
    from the stiff corner with the record length from the soft one combines
    two claims about different points, which is a category error and not a
    narrow answer, and it catches nothing because it still produces a number.
    Here both bounds go as the same local gamma/k_t, so the cost is flat
    across three decades of stiffness at 1e5 steps a point, while one interval
    per parameter gives 1e8 -- a factor equal to the stiffness range exactly.
    """
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


def _one(x: float) -> float:
    """One significant figure, by the validator's own rule.

    `f"{x:.0e}"` is NOT this: Python formats half-to-even, so 25 becomes 2e+01
    while check 17 recomputes 30 and fails a number that is right. Found by
    running it, on a7's soft-corner speed. This was a copy of the validator's
    eight lines for one commit; it calls them now, because two implementations
    of one rounding rule is the 11-11 shape and the copy is the half that rots.
    """
    return float(f"{round_to_sig(x, 1):g}")


def _target(goal) -> float | None:
    """The person's relative uncertainty on the recovered stiffness, or None.

    Returned rather than defaulted. A target is a decision and carries no
    grade (5.3.1), so a default one is indistinguishable from a chosen one --
    which is why revision 2 left targets[] empty and A2 returned a relation.
    """
    for t in goal.get("targets", []) or []:
        if t.get("metric") == "trap_stiffness" and t.get("kind") == "uncertainty":
            return float(t["value"])
    return None


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
            _interval("integration_timestep", "s", "dt_max_drift", ["trap_stiffness", "flow_speed"], max=dt_drift),
            _interval("integration_timestep", "s", "dt_max_noise", ["trap_stiffness"], max=dt_noise),
            _interval("integration_timestep", "s", "dt_max_relaxation", ["trap_stiffness"], max=dt_relax),
        ],
        inequalities=[
            _ineq("v*dt << sigma at the fastest point of the sweep", "integration_timestep",
                  interval=_interval("integration_timestep", "s", "dt_max_drift", ["trap_stiffness", "flow_speed"], max=dt_drift)),
            _ineq("sqrt(2*D*dt) << sigma at the stiffest point", "integration_timestep",
                  interval=_interval("integration_timestep", "s", "dt_max_noise", ["trap_stiffness"], max=dt_noise)),
            _ineq("dt << gamma/k_t at the stiffest point", "integration_timestep",
                  interval=_interval("integration_timestep", "s", "dt_max_relaxation", ["trap_stiffness"], max=dt_relax)),
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

    target = _target(goal)
    if target is not None:
        numbers.append(cards.num(
            "target_relative_error", target, "1", "assumed:a_target_is_the_persons",
            precision="significant_figures",
            note="the person's, settled 2026-09-23, and it is a DECISION carrying no grade "
                 "of its own (5.3.1). It sits in numbers[] only so the record lengths below "
                 "can name it as an input; the authority is the goal's targets[]"))
        t_stat_soft = _one(2 * tau_soft / (ratio_min * target) ** 2)
        numbers.append(cards.num(
            "record_length_statistical_soft_slow", t_stat_soft, "s",
            source="computed:ou_record_for_target_error",
            formula="2*trap_relaxation_time_max/(offset_over_sigma_min*target_relative_error)**2",
            inputs=[("trap_relaxation_time_max", g["trap_relaxation_time_max"]),
                    ("offset_over_sigma_min", g["offset_over_sigma_min"]),
                    ("target_relative_error", "E5")],
            precision="order_of_magnitude",
            note="inverting SE/signal = sqrt(2*tau_t/T)/(offset/sigma) for the target. THE "
                 "WORST CORNER BY FAR: soft trap and an offset of one thermal width, where "
                 "the statistics ask two decades more record than the hundred-relaxation-time "
                 "floor. At the fast end the floor takes over again, which is why both are "
                 "returned and both carry varies_with"))

    assumptions += [
        {"rationale_id": "a_target_is_the_persons",
         "statement": "The relative error target on the recovered stiffness is the person's "
                      "and was given on 2026-09-23. It is not an estimate this axis made, and "
                      "the `assumed:` prefix is the nearest source kind for a decision -- "
                      "5.3 has no kind for `a person chose this`, which is the same gap the "
                      "run observable waits on from the other direction.",
         "numbers": ["target_relative_error"],
         "falsifier": "the person changes the target, which is a revision and not a "
                      "correction; and an A5 collision at this target is a reason to raise "
                      "it rather than evidence that it was wrong",
         "gap_ref": "statistical_target_confirm_absent"},
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
    constraints = [
        _interval("record_length", "s", "record_length_floor_soft_corner",
                  ["trap_stiffness"], min=t_floor_soft),
    ]
    inequalities_extra = []
    if target is not None:
        iv = _interval("record_length", "s", "record_length_statistical_soft_slow",
                       ["trap_stiffness", "flow_speed"], min=t_stat_soft)
        constraints.append(iv)
        inequalities_extra.append(_ineq(
            "record_length >= 2*(gamma/k_t)/((offset/sigma)*target_relative_error)**2",
            "record_length", interval=iv))
    return dict(
        method="deterministic", verdict="feasible",
        constraints=constraints,
        inequalities=[
            _ineq("record_length >> gamma/k_t, at the softest point of the sweep",
                  "record_length",
                  interval=_interval("record_length", "s", "record_length_floor_soft_corner",
                                     ["trap_stiffness"], min=t_floor_soft)),
        ] + inequalities_extra,
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
        note="THE BOX BOUND CARRIES NO `varies_with`, AND THAT IS NOW AN ASSERTION. It is "
             "the one bound here that really is constant over the sweep: a box sized for "
             "the largest excursion anywhere fits every corner, and with no neighbour list "
             "it costs nothing to carry that size at the tight corners. Every other "
             "interval this configuration emits goes as the local gamma/k_t and says so. "
             "THIS AXIS IS NEARLY VACUOUS HERE AND SAYS SO RATHER THAN ABSTAINING. There is "
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
                               ["trap_stiffness"], min=dt_save_min, max=dt_save_max)],
        inequalities=[
            _ineq("save_interval << gamma/k_t, so the relaxation is resolved", "save_interval",
                  interval=_interval("save_interval", "s", "save_interval_max", ["trap_stiffness"], max=dt_save_max)),
            _ineq("save_interval >= 0.01*gamma/k_t, because a mean gains nothing from "
                  "correlated samples", "save_interval",
                  interval=_interval("save_interval", "s", "save_interval_min", ["trap_stiffness"], min=dt_save_min)),
        ],
        note="A two-sided interval, and the lower half is the unusual one. The save interval "
             "should scale with the LOCAL relaxation time at each stiffness rather than being "
             "fixed at the stiff corner's value: three decades of stiffness is three decades "
             "of tau_t, and a single interval sized for the stiff corner would store a "
             "thousand times more frames than the soft corner can use.",
    )


def a5(goal, numbers, assumptions):
    """Cost, as a STEP BUDGET and not as a predicted wall clock.

    4.5.3 rule b forbids taking A1's or A2's output: A5 does not compute "your
    job costs X hours given your dt". So it divides the ceiling by a measured
    cost per step and returns the quotient as a bound on the settable product
    `integration_steps`. A1 bounds the timestep, A2 bounds the record, and S4
    is where `record_length/integration_timestep` meets this number. That the
    two collide is S4's finding to make, not this axis's to assert.
    """
    g = _anchors(goal, numbers, assumptions, "a5")
    allowance, allowance_note = _allowance()

    numbers.append(cards.num(
        "stiffness_points", 4, "1", "assumed:a_sweep_grid", precision="significant_figures",
        note="one point per decade across the three-decade stiffness sweep, plus its end"))
    numbers.append(cards.num(
        "speed_points", 3, "1", "assumed:a_sweep_grid", precision="significant_figures",
        note="one per decade of the dimensionless offset, plus its end. A drag calibration "
             "needs at least three speeds for the slope to have a residual"))
    # NO `sweep_points` NUMBER. 4*3 = 12 claims two significant figures from two
    # one-figure inputs, and check 17 and check 28 both refuse it -- correctly in
    # general, whatever is true of exact counts, because nothing in a number
    # distinguishes a count from a measurement. Relabelling it
    # `significant_figures` did not help and should not have: the inputs are
    # still single digits. The product goes inside the budget's formula instead,
    # where it is an arithmetic step rather than a claimed quantity.

    # MEASURED, off this agent's own runs, so the cost model does not start as a guess.
    numbers.append(cards.num(
        "cost_per_step_upper", 0.004, "s", "prior_run:run-20260922-hoomd-s3",
        precision="order_of_magnitude",
        note="44.9 s of wall clock over 10000 steps on hoomd_backend, and mock_backend gave "
             "43.1 s for the same run. AN UPPER BOUND FOR THIS QUESTION AND NOT THE VALUE: "
             "that run carried 1000 particles and this configuration carries ONE, so the "
             "real per-step cost is somewhere below it"))
    numbers.append(cards.num(
        "cost_per_particle_step_lower", 4e-06, "s", "prior_run:run-20260922-hoomd-s3",
        precision="order_of_magnitude",
        note="the same 44.9 s divided by 10000 steps AND by 1000 particles. A LOWER BOUND, "
             "and it is the optimistic end because it assumes the per-step overhead "
             "vanishes at one particle, which it does not. The true single-particle cost "
             "lies between these two, three decades apart, and only a run at N=1 says "
             "where -- which is what the smoke run is for"))

    budget = None
    if allowance:
        wc = (allowance.get("wall_clock_max") or {})
        if wc.get("unit") == "h" and wc.get("value"):
            seconds = float(wc["value"]) * 3600.0
            budget = _one(seconds / 0.004 / 12)
            numbers.append(cards.num(
                "steps_max_per_point", budget, "1", "assumed:a_step_budget",
                precision="order_of_magnitude",
                note="the share of the local wall clock one sweep point may spend, as a "
                     "step count. NO `formula`, following axis_a5_budget: the ceiling is a "
                     "decision the person owns and 5.3 has no source kind for one, so "
                     "carrying it as a graded input would dress a decision as an estimate. "
                     "The arithmetic is in the rationale, where a reader can check it and "
                     "no check re-evaluates it. Against the LOWER cost bound this number is "
                     "three decades larger, which is the whole uncertainty."))

    assumptions += [
        {"rationale_id": "a_step_budget",
         "statement": "Two hours from envelope/budget.json, chosen by the person on "
                      "2026-09-19, over the measured upper cost of 4 ms a step, over the "
                      "twelve sweep points: 7200 / 0.004 / 12, about 150 thousand steps a "
                      "point, written to one significant figure. THE UPPER COST IS THE "
                      "CONSERVATIVE END OF A THREE-DECADE BRACKET -- measured at 1000 "
                      "particles while this configuration runs one -- so against the lower "
                      "end the budget is a thousand times larger and the sweep is free. The "
                      "store holds no cost-per-step entry at all, which is the gap this "
                      "stands on. AND 5.3 HAS NO SOURCE KIND FOR A DECISION, so the ceiling "
                      "and the person's target both arrive wearing `assumed:`, which means "
                      "an estimate; second instance in this one question, raised rather "
                      "than worked around.",
         "numbers": ["steps_max_per_point"],
         "falsifier": "a smoke run at N=1 replaces the cost bracket with a measured value "
                      "and this number moves by up to three decades; a store entry for the "
                      "per-step cost does the same with no run; and 5.3 gaining a source "
                      "kind for a decision retires the prefix complaint",
         "gap_ref": "cost_per_particle_step_overdamped_absent"},
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

    constraints, ineqs = [], []
    if budget is not None:
        iv = _interval("integration_steps", "1", "steps_max_per_point", max=budget)
        constraints.append(iv)
        ineqs.append(_ineq(
            "record_length/integration_timestep <= wall_clock_max/(cost_per_step*sweep_points), "
            "at every sweep point", "integration_steps", interval=iv))
    ineqs.append(_ineq("predicted storage <= the local target's storage_max", "storage",
        precondition={
            "parameter": "storage",
            "requires": "the plan must state the frame count, which is "
                        "record_length/save_interval and so A2's and A4's to fix. The "
                        "trajectory is written to disk now (013), so this is a real ceiling "
                        "rather than a notional one, and it is not computed here for the "
                        "same rule-b reason the wall clock is not",
            "basis": ["stiffness_points", "speed_points"]}))

    return dict(
        method="deterministic", verdict="feasible" if budget is not None else "abstain",
        **({} if budget is not None else {"abstain_reason":
            "no single-target allowance could be read, so there is no ceiling to divide. "
            + allowance_note}),
        constraints=constraints,
        inequalities=ineqs,
        note="THE STEP BUDGET CARRIES NO `varies_with`, AND THAT IS DELIBERATE: a wall clock "
             "shared across the sweep is one pot, and the bound on each point's share really "
             "is the same number at every point. Every other interval in this question moves "
             "with the stiffness; this one does not, and the difference is that the others "
             "come from the physics at a point while this comes from a budget over all of "
             "them. THE COST MODEL IS BRACKETED AND THE BRACKET STRADDLES THE CEILING. The "
             "upper end is measured at 1000 particles and the lower divides it by 1000, and "
             "the true single-particle cost is between them -- three decades. A smoke run at "
             "N=1 collapses that to a number, and it cannot be run yet because this "
             "configuration has no backend: mock_backend and hoomd_backend both integrate "
             "free diffusion with no trap term and no flow term. Writing that integrator is "
             "what unblocks the measurement, and until then the budget above stands on the "
             "conservative end on purpose.",
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
    # The ceilings live under `limits`, not on the target. Read wrong at first,
    # and the symptom was an abstention with `wall clock None None` in its own
    # reason -- the axis said it had no ceiling while the file had one. The
    # sentence named the cause and nobody was reading it, which is why this
    # note is here and not in a commit message.
    lim = t.get("limits") or {}
    return {"target": t.get("target"), **lim}, (
        f"An allowance exists: target {t.get('target')!r}, wall clock "
        f"{(lim.get('wall_clock_max') or {}).get('value')} "
        f"{(lim.get('wall_clock_max') or {}).get('unit')}, storage "
        f"{(lim.get('storage_max') or {}).get('value')} "
        f"{(lim.get('storage_max') or {}).get('unit')}.")


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
            _interval("flow_speed", "um/s", "flow_speed_max_soft_corner", ["trap_stiffness"], max=v_soft_max),
            _interval("startup_discard", "s", "startup_discard_soft_corner", ["trap_stiffness"], min=startup_soft),
        ],
        inequalities=[
            _ineq("the imposed speed realises the declared dimensionless offset at each "
                  "stiffness", "flow_speed",
                  interval=_interval("flow_speed", "um/s", "flow_speed_max_soft_corner",
                                     ["trap_stiffness"], max=v_soft_max)),
            _ineq("startup_discard >> gamma/k_t, so the record begins at steady state",
                  "startup_discard",
                  interval=_interval("startup_discard", "s", "startup_discard_soft_corner",
                                     ["trap_stiffness"], min=startup_soft)),
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
