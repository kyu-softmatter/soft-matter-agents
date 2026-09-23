"""bd_pairwise -- 2D overdamped Brownian dynamics, periodic, purely repulsive
Yukawa pair potential, undriven. Produces `structural_relaxation_time`
(contracts/capabilities/simulation.json, contracts/observables.json).

Physics the axes share, stated once. Particles of diameter d in a bath at
temperature T and viscosity eta have free diffusivity D0 (Stokes-Einstein,
carried from the goal). At area density rho the mean spacing is a = rho**-1/2
and the natural time unit of structural relaxation is the Brownian time
tau_B = a**2 / D0: the time a particle needs to diffuse one spacing. The pair
potential is written u(r) = U0 * (a / r) * exp(-kappa * (r - a)), so that U0
is the energy at the mean spacing, and the sweep is over the two
dimensionless groups the person asked about -- Gamma = U0 / k_B T (strength)
and kappa * a (range) -- plus the density through a.

What is DIFFERENT from bd_overdamped, axis by axis, and why a card from the
old modules would be wrong here:

  A1  the shortest time is no longer tau_B. The curvature of u at the mean
      spacing gives a relaxation time gamma / u''(a) = tau_B / (Gamma * ((kappa
      a)**2 + 2 kappa a + 2)), five decades below tau_B at the stiff corner
      of the sweep; and the noise step sqrt(2 D0 dt) must stay well inside a
      screening length or a particle jumps across the potential.
  A2  one run yields ONE relaxation time (psi6(t) averaged over particles),
      so the independent samples are seeds -- random initial configurations
      -- and not displacements.
  A3  the correlation length of psi6 GROWS toward the box as the structure
      orders, so finite size is always present; the box must hold many
      spacings, and it must be commensurate with a triangular lattice or the
      plateau is capped by frustration and the relaxation time measures the
      box.
  A4  the quantity to resolve is the rise of psi6(t) on the tau_B scale, and
      the plateau criterion and fit window are the observable's window.
  A5  the cost has a neighbour list in it and the sweep multiplies runs.
  A7  abstains: undriven. `bd_pairwise_driven_tracer` is where it speaks.

Every factor that is a convention and not a derivation is an `assumed:`
number with a rationale and a falsifier, and names the gap the librarian
returned for it (check 39). The sweep's corners are assumptions too: the
person said the ranges are S3's to bound, so S3 writes them down as its own
and says what would move them.
"""

from __future__ import annotations

import json

from . import cards

ENVELOPE = cards.AGENT / "envelope" / "budget.json"

# The names each axis asks the store for, one kb_query per name. A gap that
# comes back is the gap_ref of the assumption standing where the entry would.
QUERIES = {
    "a1": ["mean_spacing_over_diameter", "yukawa_coupling_sweep_range",
           "integration_timestep_resolution_factor", "noise_step_fraction_of_screening_length"],
    "a2": ["relaxation_time_seed_variability", "statistical_target_explore"],
    "a3": ["mean_spacing_over_diameter", "psi6_finite_size_margin"],
    "a4": ["mean_spacing_over_diameter", "save_interval_fraction_of_brownian_time",
           "psi6_plateau_fraction", "relaxation_fit_window_frames"],
    "a5": ["cost_per_particle_step_yukawa_2d", "structural_relaxation_time"],
    "a7": [],
}


def goal_drives(goal: dict) -> bool:
    """Whether the goal imposes a drive: a selector named `drive` on the goal."""
    return any(sel.get("parameter") == "drive" for sel in (goal.get("selectors") or []))


def applicable(goal: dict) -> tuple[bool, str]:
    if goal_drives(goal):
        return False, ("bd_pairwise drives nothing, and this goal imposes a drive (selector `drive`); "
                       "bd_pairwise_driven_tracer is the configuration that does")
    return True, ""


def plan_queries(qid: str, revision: int, config: str, issue) -> list[dict]:
    goal = cards.load_goal(qid, revision)
    kb_version = {r["kb_version"] for r in goal.get("kb_refs") or []}
    kb_version = kb_version.pop() if len(kb_version) == 1 else None
    out = []
    for axis, names in QUERIES.items():
        for name in names:
            out.append({
                "tool": "kb_query",
                "caller_id": issue(qid, revision, config, axis),
                "args": {"kb_version": kb_version, "observable": name, "purpose": goal["purpose"]},
                "why": f"{axis}: an entry replaces the assumption standing where {name} would; a gap is what the assumption then cites",
            })
    return out


# --------------------------------------------------------------------------- #
# shared derivations
# --------------------------------------------------------------------------- #

def _spacing(goal: dict, numbers: list[dict], assumptions: list[dict]) -> dict[str, str]:
    """mean_spacing and brownian_time from the goal's anchor, via one assumption."""
    carried, carried_assumptions = cards.carry(goal, ["bead_diameter", "diffusivity"])
    numbers += carried
    assumptions += carried_assumptions
    g = {n["name"]: n["grade"] for n in numbers}
    d = next(n for n in numbers if n["name"] == "bead_diameter")["value"]
    D0 = next(n for n in numbers if n["name"] == "diffusivity")["value"]
    numbers.append(cards.num("spacing_over_diameter", 2, "1", "assumed:a_spacing",
                             precision="order_of_magnitude",
                             note="mean centre-to-centre spacing in diameters; sets the area fraction, about 0.2 for a triangular arrangement at 2"))
    a = 2 * d
    numbers.append(cards.num("mean_spacing", a, "um", "computed:spacing_times_diameter",
                             formula="spacing_over_diameter*bead_diameter",
                             inputs=[("spacing_over_diameter", "E5"), ("bead_diameter", g["bead_diameter"])],
                             precision="order_of_magnitude",
                             note="a = rho**-1/2 at the reference density; the density sweep moves it by less than a decade"))
    tau_b = a * a / D0
    numbers.append(cards.num("brownian_time", _oom(tau_b), "s", "computed:brownian_time",
                             formula="mean_spacing**2/diffusivity",
                             inputs=[("mean_spacing", "E5"), ("diffusivity", g["diffusivity"])],
                             precision="order_of_magnitude",
                             note="the time to diffuse one spacing: the natural unit of structural relaxation here, and NOT tau_d, which is the time to diffuse one diameter and belongs to the free-tracer question"))
    assumptions.append({
        "rationale_id": "a_spacing",
        "gap_ref": "mean_spacing_over_diameter_absent",
        "statement": "Two diameters of spacing is a reference density where a 2D Yukawa suspension is neither dilute nor jammed, so the sweep in strength and range has room on both sides. Nothing physical picks it; the density is one of the swept parameters and this is the point about which it is swept.",
        "numbers": ["spacing_over_diameter"],
        "falsifier": "a person naming the area fraction of interest, or a first run showing the plateau unreachable at this density inside budget, moves the reference",
    })
    return {**g, "spacing_over_diameter": "E5", "mean_spacing": "E5", "brownian_time": "E5"}



def _oom(x: float) -> float:
    """One significant figure: explore mode answers in decades and a computed
    value inherits the worst precision of its inputs (P15, check 28)."""
    if x == 0:
        return 0.0
    from math import floor, log10
    e = floor(log10(abs(x)))
    return round(x / 10 ** e) * 10 ** e if e < 0 else float(round(x, -e))


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
    return {"parameter": parameter, "unit": unit, **bound, "basis": [basis], "precision": "order_of_magnitude"}


def _ineq(text, parameter, interval=None, precondition=None):
    out = {"inequality": text, "parameter": parameter, "state": "returned"}
    if interval is not None:
        out["interval"] = interval
    if precondition is not None:
        out["precondition"] = precondition
    return out


# --------------------------------------------------------------------------- #
# axes
# --------------------------------------------------------------------------- #

def a1(goal, numbers, assumptions):
    g = _spacing(goal, numbers, assumptions)
    numbers.append(cards.num("gamma_max", 1000, "1", "assumed:a_sweep_corner", precision="order_of_magnitude",
                             note="the largest U0/kT in the sweep; the stiff corner A1 must survive"))
    numbers.append(cards.num("kappa_a_max", 10, "1", "assumed:a_sweep_corner", precision="order_of_magnitude",
                             note="the shortest range in the sweep, as kappa times the mean spacing"))
    numbers.append(cards.num("curvature_factor", _oom(1000 * (100 + 20 + 2)), "1", "computed:yukawa_curvature_at_spacing",
                             formula="gamma_max*(kappa_a_max**2 + 2*kappa_a_max + 2)",
                             inputs=[("gamma_max", "E5"), ("kappa_a_max", "E5")], precision="order_of_magnitude",
                             note="a**2 u''(a) / kT for u = U0 (a/r) exp(-kappa (r-a)); the ratio of the Brownian time to the curvature relaxation time"))
    # Every derived value below is computed from the ROUNDED values already in
    # numbers[], because that is what the validator recomputes from (check 17):
    # a chain computed exactly and rounded at the end disagrees with a chain
    # rounded at each step by up to a factor of two at one significant figure.
    tau_b = _value(numbers, "brownian_time")
    cf = _value(numbers, "curvature_factor")
    numbers.append(cards.num("curvature_time", _oom(tau_b / cf), "s", "computed:curvature_relaxation_time",
                             formula="brownian_time/curvature_factor",
                             inputs=[("brownian_time", "E5"), ("curvature_factor", "E5")], precision="order_of_magnitude",
                             note="gamma / u''(a): the shortest characteristic time in the system at the stiff corner, five decades below tau_B"))
    numbers.append(cards.num("dt_resolution_factor", 0.01, "1", "assumed:a_dt_factor", precision="order_of_magnitude",
                             note="how far below the shortest resolved time the step sits"))
    ct = _value(numbers, "curvature_time")
    numbers.append(cards.num("dt_max_curvature", _oom(0.01 * ct), "s", "computed:factor_times_curvature_time",
                             formula="dt_resolution_factor*curvature_time",
                             inputs=[("dt_resolution_factor", "E5"), ("curvature_time", "E5")], precision="order_of_magnitude"))
    numbers.append(cards.num("dt_max_brownian", _oom(0.01 * tau_b), "s", "computed:factor_times_brownian_time",
                             formula="dt_resolution_factor*brownian_time",
                             inputs=[("dt_resolution_factor", "E5"), ("brownian_time", "E5")], precision="order_of_magnitude",
                             note="the bound the free-tracer configuration would have stopped at; here it is the loosest of three"))
    numbers.append(cards.num("noise_step_fraction", 0.1, "1", "assumed:a_noise_step", precision="order_of_magnitude",
                             note="the rms noise displacement per step as a fraction of the screening length"))
    a = _value(numbers, "mean_spacing"); D0 = _value(numbers, "diffusivity")
    numbers.append(cards.num("screening_length_min", _oom(a / 10), "um", "computed:spacing_over_kappa_a",
                             formula="mean_spacing/kappa_a_max", inputs=[("mean_spacing", "E5"), ("kappa_a_max", "E5")],
                             precision="order_of_magnitude"))
    dt_noise = (0.1 * _value(numbers, "screening_length_min")) ** 2 / (2 * D0)
    numbers.append(cards.num("dt_max_noise", _oom(dt_noise), "s", "computed:noise_step_inside_screening_length",
                             formula="(noise_step_fraction*screening_length_min)**2/(2*diffusivity)",
                             inputs=[("noise_step_fraction", "E5"), ("screening_length_min", "E5"), ("diffusivity", g["diffusivity"])],
                             precision="order_of_magnitude",
                             note="sqrt(2 D0 dt) must stay inside the potential's range or a step carries a particle across it in one move"))
    assumptions += [
        {"rationale_id": "a_sweep_corner", "gap_ref": "yukawa_coupling_sweep_range_absent",
         "statement": "The person left the ranges to S3. Gamma from 10 to 1000 spans the 2D Yukawa fluid, its ordering, and a stiff crystal; kappa a from 1 to 10 spans long-ranged to nearly hard. The stiff corner, Gamma 1000 at kappa a 10, is what the timestep has to survive, and the bound scales as 1/(Gamma (kappa a)**2) away from it.",
         "numbers": ["gamma_max", "kappa_a_max"],
         "falsifier": "a first run showing psi6 already at its plateau at the lowest Gamma, or unreachable inside budget at the highest, moves the corresponding end by a decade"},
        {"rationale_id": "a_dt_factor", "gap_ref": "integration_timestep_resolution_factor_absent",
         "statement": "Two decades below the shortest resolved time is the usual margin for an overdamped integrator with a stiff repulsion; a convention, not a derivation, and no timestep scan on this model has been run.",
         "numbers": ["dt_resolution_factor"],
         "falsifier": "a timestep scan showing the relaxation time flat over a wider range of steps replaces the factor with a measured one"},
        {"rationale_id": "a_noise_step", "gap_ref": "noise_step_fraction_of_screening_length_absent",
         "statement": "A tenth of a screening length per step keeps the force felt during a step close to the force at its start. Looser than the curvature bound at this corner, and recorded because at small Gamma it is the one that binds.",
         "numbers": ["noise_step_fraction"],
         "falsifier": "energy drift or overlap counts flat against step size at larger fractions retires it"},
    ]
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[
            _interval("integration_timestep", "s", "dt_max_curvature", max=_oom(0.01 * ct)),
            _interval("integration_timestep", "s", "dt_max_noise", max=_oom(dt_noise)),
            _interval("integration_timestep", "s", "dt_max_brownian", max=_oom(0.01 * tau_b)),
        ],
        inequalities=[
            _ineq("dt << gamma / u''(a) at the stiffest point of the sweep", "integration_timestep",
                  interval=_interval("integration_timestep", "s", "dt_max_curvature", max=_oom(0.01 * ct))),
            _ineq("sqrt(2 D0 dt) << 1/kappa", "integration_timestep",
                  interval=_interval("integration_timestep", "s", "dt_max_noise", max=_oom(dt_noise))),
            _ineq("dt << a**2 / D0", "integration_timestep",
                  interval=_interval("integration_timestep", "s", "dt_max_brownian", max=_oom(0.01 * tau_b))),
        ],
        note="Three bounds on one parameter, and S4 takes the tightest; all three are recorded because which one binds moves across the sweep. At the stiff corner the curvature bound is five decades below the Brownian one -- the whole reason bd_overdamped's A1 could not be reused here.",
    )


def a2(goal, numbers, assumptions):
    numbers.append(cards.num("seed_cv_assumed", 0.3, "1", "assumed:a_seed_cv", precision="order_of_magnitude",
                             note="run-to-run coefficient of variation of the relaxation time across random initial configurations"))
    numbers.append(cards.num("target_rel_error", 0.1, "1", "assumed:a_target", precision="order_of_magnitude",
                             note="statistical error on the relaxation time at one sweep point; inside a decade with room to spare"))
    numbers.append(cards.num("n_seeds_min", 9, "1", "computed:seeds_for_target",
                             formula="(seed_cv_assumed/target_rel_error)**2",
                             inputs=[("seed_cv_assumed", "E5"), ("target_rel_error", "E5")], precision="order_of_magnitude",
                             note="independent samples are SEEDS: one run gives one relaxation time, because psi6(t) is already averaged over every particle"))
    assumptions += [
        {"rationale_id": "a_seed_cv", "gap_ref": "relaxation_time_seed_variability_absent",
         "statement": "Ordering from a random start is nucleation-like and its time varies from seed to seed by tens of per cent; a third is a guess at that spread until seeds have been run.",
         "numbers": ["seed_cv_assumed"],
         "falsifier": "the measured spread across the first seeds replaces this, and the seed count follows"},
        {"rationale_id": "a_target", "gap_ref": "statistical_target_explore_absent",
         "statement": "Ten per cent is a tenth of the decade explore mode answers in, so the statistical error never decides a comparison between sweep points.",
         "numbers": ["target_rel_error"],
         "falsifier": "a person stating a target accuracy replaces it"},
    ]
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[_interval("n_seeds", "1", "n_seeds_min", min=9)],
        inequalities=[
            _ineq("n_seeds >= (cv / target)**2", "n_seeds", interval=_interval("n_seeds", "1", "n_seeds_min", min=9)),
            _ineq("the run lasts until the plateau criterion fires, or reports not converged", "stop_criterion",
                  precondition={"parameter": "stop_criterion",
                                "requires": "Carry a stop criterion on psi6(t) reaching the declared plateau fraction with on_met complete, and a run_time_max cap with on_met fault-free stop; a run ending on the cap is reported not converged and is not a relaxation time. The criterion is declared before the run and not chosen after seeing psi6(t).",
                                "basis": ["n_seeds_min"]}),
        ],
        note="The trajectory length is not a free parameter here: it ends when the observable's own criterion fires. What A2 owns is how many times that has to happen.",
    )


def a3(goal, numbers, assumptions):
    _spacing(goal, numbers, assumptions)
    a = _value(numbers, "mean_spacing")
    numbers.append(cards.num("finite_size_factor", 30, "1", "assumed:a_finite_size", precision="order_of_magnitude",
                             note="box edge in mean spacings"))
    numbers.append(cards.num("box_length_min", _oom(30 * a), "um", "computed:factor_times_spacing",
                             formula="finite_size_factor*mean_spacing", inputs=[("finite_size_factor", "E5"), ("mean_spacing", "E5")],
                             precision="order_of_magnitude"))
    numbers.append(cards.num("n_particles_min", 900, "1", "computed:spacings_squared",
                             formula="finite_size_factor**2", inputs=[("finite_size_factor", "E5")], precision="order_of_magnitude",
                             note="(L/a)**2 at the reference density"))
    assumptions.append({
        "rationale_id": "a_finite_size", "gap_ref": "psi6_finite_size_margin_absent",
        "statement": "The psi6 correlation length grows toward the box as the structure orders, so finite size is never absent here and the box can only be made large against the spacing. Thirty spacings keeps the ordering time from being set by the box for the part of the sweep that orders, and is a margin rather than a measured threshold.",
        "numbers": ["finite_size_factor"],
        "falsifier": "two box sizes a factor of two apart giving the same relaxation time within its error retire the margin at that sweep point",
    })
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[_interval("box_length", "um", "box_length_min", min=_oom(30 * a)),
                     _interval("n_particles", "1", "n_particles_min", min=900)],
        inequalities=[
            _ineq("L >> a", "box_length", interval=_interval("box_length", "um", "box_length_min", min=_oom(30 * a))),
            _ineq("N = (L/a)**2 at the reference density", "n_particles", interval=_interval("n_particles", "1", "n_particles_min", min=900)),
            _ineq("the periodic box is commensurate with a triangular lattice", "box_aspect",
                  precondition={"parameter": "box_aspect",
                                "requires": "Choose n_particles = 2*m*n and a box with Ly/Lx = n*sqrt(3)/(2*m) at the target density, so that a defect-free triangular lattice fits the periodic cell. Otherwise the psi6 plateau is capped by frustration and the relaxation time measures the box, not the suspension.",
                                "basis": ["n_particles_min"]}),
            _ineq("the potential cutoff is inside half the box and outside the potential's reach", "potential_cutoff",
                  precondition={"parameter": "potential_cutoff",
                                "requires": "Set the pair cutoff so that u(r_cut)/kT is below one thousandth at the largest Gamma and longest range of the sweep, and below half the box edge; declare it in the plan.",
                                "basis": ["box_length_min"]}),
        ],
        note="Two of the four inequalities are preconditions rather than intervals because they restrict a shape and not a value; S4 must carry them, not intersect them.",
    )


def a4(goal, numbers, assumptions):
    _spacing(goal, numbers, assumptions)
    tau_b = _value(numbers, "brownian_time")
    numbers.append(cards.num("sampling_factor", 0.1, "1", "assumed:a_sampling", precision="order_of_magnitude",
                             note="save interval as a fraction of the Brownian time"))
    numbers.append(cards.num("save_interval_max", _oom(0.1 * tau_b), "s", "computed:factor_times_brownian_time",
                             formula="sampling_factor*brownian_time", inputs=[("sampling_factor", "E5"), ("brownian_time", "E5")],
                             precision="order_of_magnitude"))
    numbers.append(cards.num("plateau_fraction", 0.9, "1", "assumed:a_plateau", precision="order_of_magnitude",
                             note="the fraction of the psi6 plateau at which the relaxation time is read; a condition the plan carries, because the vocabulary's window_parameter holds only the fit window"))
    numbers.append(cards.num("fit_window_frames_min", 10, "1", "assumed:a_fit_frames", precision="order_of_magnitude",
                             note="saved frames the relaxation_fit_window must span"))
    assumptions += [
        {"rationale_id": "a_sampling", "gap_ref": "save_interval_fraction_of_brownian_time_absent",
         "statement": "psi6(t) rises on the Brownian-time scale; a tenth of it per frame resolves the rise with ten points per e-fold of the slowest part and does not alias the fast local rearrangements into it, which are averaged out by the particle mean anyway.",
         "numbers": ["sampling_factor"],
         "falsifier": "the fitted relaxation time unchanged when every second frame is dropped retires the factor"},
        {"rationale_id": "a_plateau", "gap_ref": "psi6_plateau_fraction_absent",
         "statement": "Nine tenths of the plateau is high enough that the structure is recognisably ordered and low enough that the approach is not dominated by the last defects annealing, whose time is a different quantity. A threshold nobody has chosen is UNDECIDED and not satisfied; this is S3's choice, written down so S4 and the plan carry it as a condition.",
         "numbers": ["plateau_fraction"],
         "falsifier": "a person choosing the fraction, or the vocabulary gaining a second window parameter for it"},
        {"rationale_id": "a_fit_frames", "gap_ref": "relaxation_fit_window_frames_absent",
         "statement": "A window of fewer than ten frames fits a plateau through noise.",
         "numbers": ["fit_window_frames_min"],
         "falsifier": "a fit over a shorter window giving the same time within error"},
    ]
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[_interval("save_interval", "s", "save_interval_max", max=_oom(0.1 * tau_b))],
        inequalities=[
            _ineq("save_interval << tau_B", "save_interval", interval=_interval("save_interval", "s", "save_interval_max", max=_oom(0.1 * tau_b))),
            _ineq("the plan carries the plateau fraction as a condition", "plateau_fraction",
                  precondition={"parameter": "plateau_fraction",
                                "requires": "Carry plateau_fraction as a condition of the observable beside relaxation_fit_window, with the value in this card's numbers[] until a person chooses one.",
                                "basis": ["plateau_fraction"]}),
            _ineq("relaxation_fit_window spans at least fit_window_frames_min saved frames", "relaxation_fit_window",
                  precondition={"parameter": "relaxation_fit_window",
                                "requires": "Set relaxation_fit_window to at least fit_window_frames_min times the save interval and declare it as the observable's window (check 40).",
                                "basis": ["fit_window_frames_min"]}),
        ],
    )


def a5(goal, numbers, assumptions):
    env = json.loads(ENVELOPE.read_text())
    local = next(t for t in env["targets"] if t["target"] == "local")
    wall = local["limits"]["wall_clock_max"]; store = local["limits"]["storage_max"]
    numbers.append(cards.num("wall_clock_max", wall["value"], wall["unit"], "spec:simulation_agent/envelope/budget.json",
                             note="the local target's ceiling, chosen by " + wall["chosen_by"]["by"] + " on " + wall["chosen_by"]["on"] + "; a policy, not a measurement"))
    numbers.append(cards.num("storage_max", store["value"], store["unit"], "spec:simulation_agent/envelope/budget.json",
                             note="the local target's ceiling, same provenance"))
    numbers.append(cards.num("cost_per_particle_step", 1e-7, "s", "assumed:a_cost_reference", precision="order_of_magnitude",
                             note="wall seconds per particle per step for a 2D Yukawa neighbour-list integrator on this workstation's CPU"))
    numbers.append(cards.num("particle_steps_max", 7e10, "1", "computed:wall_clock_over_cost",
                             formula="wall_clock_max/cost_per_particle_step",
                             inputs=[("wall_clock_max", "E3"), ("cost_per_particle_step", "E5")], precision="order_of_magnitude",
                             note="the product n_particles * steps * n_seeds * sweep_points must sit under this"))
    numbers.append(cards.num("storage_per_particle_frame", 2e-8, "GB", "assumed:a_frame_bytes", precision="order_of_magnitude",
                             note="two double coordinates per particle per frame"))
    numbers.append(cards.num("particle_frames_max", 5e8, "1", "computed:storage_over_frame_cost",
                             formula="storage_max/storage_per_particle_frame",
                             inputs=[("storage_max", "E3"), ("storage_per_particle_frame", "E5")], precision="order_of_magnitude"))
    assumptions += [
        {"rationale_id": "a_cost_reference", "gap_ref": "cost_per_particle_step_yukawa_2d_absent",
         "statement": "Of order ten million particle-steps per second is what a CPU neighbour-list integrator with a short-ranged pair force manages; nothing on this machine has measured it for this potential.",
         "numbers": ["cost_per_particle_step"],
         "falsifier": "a smoke run of this configuration that writes its trajectory replaces this with its own log's wall time per particle-step"},
        {"rationale_id": "a_frame_bytes", "statement": "Positions only, in double precision, two coordinates in 2D.",
         "numbers": ["storage_per_particle_frame"], "gap_ref": "cost_per_particle_step_yukawa_2d_absent",
         "falsifier": "the trajectory writer's declared frame format replaces the estimate"},
    ]
    return dict(
        method="deterministic", verdict="feasible",
        constraints=[_interval("particle_steps_total", "1", "particle_steps_max", max=7e10),
                     _interval("particle_frames_total", "1", "particle_frames_max", max=5e8)],
        inequalities=[
            _ineq("n_particles * steps * seeds * sweep_points * cost <= wall_clock_max", "particle_steps_total",
                  interval=_interval("particle_steps_total", "1", "particle_steps_max", max=7e10)),
            _ineq("n_particles * frames * seeds * sweep_points * bytes <= storage_max", "particle_frames_total",
                  interval=_interval("particle_frames_total", "1", "particle_frames_max", max=5e8)),
        ],
        note="A5 constrains the product of the settable parameters and takes no sibling's output (4.5.3 rule b). At A1's stiff corner the product will not fit, and that conflict is S4's to surface with the counterexample, not this card's to hide.",
    )


def a7(goal, numbers, assumptions):
    return dict(
        method="deterministic", verdict="abstain",
        abstain_reason="bd_pairwise drives nothing: no particle has an imposed position or velocity and no field acts, so quasi-staticity, strain to steady state and the validity range of the overdamped model under drive are all empty inequalities here. bd_pairwise_driven_tracer is the configuration where A7 speaks.",
        inequalities=[
            {"inequality": "v a / D0 << 1 (quasi-static drive)", "parameter": "driving_velocity", "state": "abstained",
             "kind": "not_constraining", "reason": "undriven configuration: there is no driving velocity"},
            {"inequality": "strain to steady state under drive", "parameter": "driving_direction", "state": "abstained",
             "kind": "not_constraining", "reason": "undriven configuration: there is no driving direction"},
        ],
        note="Abstaining leaves a card (P1). A7 is numbered the same on both sides so the bridge can lay two a7 cards side by side; here the card says there is nothing to lay.",
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


# --------------------------------------------------------------------------- #
# S4 -- where the conflict surfaces (4.2, 4.5.4)
# --------------------------------------------------------------------------- #

def s4_refusal(qid: str, revision: int, created_at: str) -> dict:
    """The budget conflict A1 x A2 x A3 x A5 produce together, as a refusal.

    No single axis sees it: A1 bounds the step, A2 the seeds, A3 the
    particles, A5 the product, and the product needs a run length that no
    axis owns -- the run ends when psi6 reaches its plateau, and how long that
    takes is the observable itself. So S4 has to CHOOSE a cap on the run to
    cost it at all, the way the free-tracer synthesis chose ten diffusive
    times. Ten Brownian times is the lenient choice: if the stiff corner does
    not fit under it, no honest cap makes it fit.

    4.2 fixes the shape of the answer: compute the resources the question
    needs, present them as a counterexample against the ceiling, attach one
    relaxation option, refuse. No new lookups; every number here is carried
    from an axis card or is arithmetic on carried numbers, computed from the
    ROUNDED values the cards hold (check 17), plus the two decisions -- the
    cap and the relaxed corner -- which are marked assumed: and say so.
    """
    from . import synthesis
    a = lambda ax: cards.artifact_name(f"axis_bd_pairwise_{ax}.json", revision)
    wanted = [(a("a1"), n) for n in ("brownian_time", "dt_max_curvature", "gamma_max", "kappa_a_max",
                                    "dt_resolution_factor")]
    wanted += [(a("a2"), "n_seeds_min"), (a("a3"), "n_particles_min"), (a("a5"), "particle_steps_max")]
    numbers = synthesis.carry_from(qid, "bd_pairwise", wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)
    g = {n["name"]: n["grade"] for n in numbers}
    v = lambda name: _value(numbers, name)

    def add(name, value, unit, source, formula=None, inputs=(), **kw):
        n = cards.num(name, value, unit, source, precision="order_of_magnitude",
                      **({"formula": formula, "inputs": [(i, g[i]) for i in inputs]} if formula else {}), **kw)
        numbers.append(n); g[name] = n["grade"]

    add("run_cap_factor", 10, "1", "assumed:a_run_cap",
        note="the run is capped at this many Brownian times; a run ending on the cap is reported not converged")
    add("run_time_cap", _oom(10 * v("brownian_time")), "s", "computed:cap_times_brownian_time",
        "run_cap_factor*brownian_time", ("run_cap_factor", "brownian_time"))
    add("steps_required_stiff", _oom(v("run_time_cap") / v("dt_max_curvature")), "1", "computed:cap_over_step",
        "run_time_cap/dt_max_curvature", ("run_time_cap", "dt_max_curvature"),
        note="steps for ONE run at the stiff corner of the sweep, Gamma 1000 at kappa a 10")
    add("particle_steps_required_stiff", _oom(v("steps_required_stiff") * v("n_particles_min") * v("n_seeds_min")), "1",
        "computed:steps_times_particles_times_seeds", "steps_required_stiff*n_particles_min*n_seeds_min",
        ("steps_required_stiff", "n_particles_min", "n_seeds_min"),
        note="one sweep point at the stiff corner, at A3's smallest box and A2's fewest seeds -- the cheapest honest version of that point")
    add("gamma_relaxed", 100, "1", "assumed:a_relaxed_corner",
        note="the largest coupling of the relaxation option; still above the 2D Yukawa ordering transition for kappa a of order one")
    add("kappa_a_relaxed", 3, "1", "assumed:a_relaxed_corner",
        note="the shortest range of the relaxation option")
    add("curvature_factor_relaxed", _oom(100 * (9 + 6 + 2)), "1", "computed:yukawa_curvature_at_spacing",
        "gamma_relaxed*(kappa_a_relaxed**2 + 2*kappa_a_relaxed + 2)", ("gamma_relaxed", "kappa_a_relaxed"))
    add("dt_relaxed", _oom(v("dt_resolution_factor") * v("brownian_time") / v("curvature_factor_relaxed")), "s",
        "computed:factor_times_curvature_time", "dt_resolution_factor*brownian_time/curvature_factor_relaxed",
        ("dt_resolution_factor", "brownian_time", "curvature_factor_relaxed"))
    add("particle_steps_required_relaxed", _oom(v("run_time_cap") / v("dt_relaxed") * v("n_particles_min") * v("n_seeds_min")), "1",
        "computed:cap_over_step_times_particles_times_seeds", "run_time_cap/dt_relaxed*n_particles_min*n_seeds_min",
        ("run_time_cap", "dt_relaxed", "n_particles_min", "n_seeds_min"),
        note="one sweep point at the relaxed corner")
    add("sweep_points_affordable", _oom(v("particle_steps_max") / v("particle_steps_required_relaxed")), "1",
        "computed:budget_over_point_cost", "particle_steps_max/particle_steps_required_relaxed",
        ("particle_steps_max", "particle_steps_required_relaxed"),
        note="how many relaxed-corner points fit under the local wall clock; points away from the corner are cheaper, so this is the floor")
    assumptions += [
        {"rationale_id": "a_run_cap", "gap_ref": "structural_relaxation_time_absent",
         "statement": "How long psi6 takes to reach its plateau is the observable, so no axis can bound the run length in advance; S4 caps it to cost the run at all. Ten Brownian times is lenient -- ordering from a random start in a stiff Yukawa system is more likely to take a hundred -- and is chosen so that a corner that fails under it fails under any honest cap.",
         "numbers": ["run_cap_factor"],
         "falsifier": "the first run's own psi6(t) replaces the cap with a measured relaxation time and its spread"},
        {"rationale_id": "a_relaxed_corner", "gap_ref": "yukawa_coupling_sweep_range_absent",
         "statement": "A proposal for revision 2 and not a decision: pulling the stiff corner in by a decade in coupling and a factor of three in kappa a loosens A1's step by a factor of about fifty, which is what brings one sweep point under the ceiling. The physics of interest -- ordering from a random start -- is still inside this range for kappa a of order one. S3 must re-run with these corners as its assumptions; S4 does not set them.",
         "numbers": ["gamma_relaxed", "kappa_a_relaxed"],
         "falsifier": "a person choosing different corners, or a first run showing psi6 already ordered at Gamma 100"},
    ]
    card = cards.head(
        "refusal", f"refusal-{qid}-s4" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, status="REFUSED", stage="S4",
        refused_what=("Run the sweep sim-20260923-001 asks for -- Gamma from 10 to 1000 and kappa a from 1 to 10 on "
                      "bd_pairwise -- inside the local execution target's 2 h wall clock. The intersection of the six "
                      "axis intervals is not empty; what does not fit is their PRODUCT at the stiff corner."),
        reason_code="budget_exceeded",
        counterexample=[{
            "parameter": "particle_steps_total",
            "required_number": "particle_steps_required_stiff",
            "limit_number": "particle_steps_max",
            "statement": ("One sweep point at Gamma 1000, kappa a 10, at A3's smallest box (900 particles) and A2's fewest "
                          "seeds (9), capped at ten Brownian times, needs of order 1e12 particle-steps; the local wall clock "
                          "at A5's assumed cost per particle-step allows 7e10. One point is a decade over, before the other "
                          "points of the sweep are counted. The binding chain is A1's curvature bound: at that corner the "
                          "step is 1e-4 s against a Brownian time of 1000 s, seven decades of steps per Brownian time."),
        }],
        alternatives=[{
            "what": ("Narrow the sweep to Gamma <= 100 and kappa a <= 3. The step loosens to about 5e-3 s, one point costs "
                     "of order 2e10 particle-steps, and about four points fit under the ceiling -- more if points away from "
                     "the corner are cheaper, which they are. Ordering from a random start is still inside this range. "
                     "This is a revision-2 goal for S3 to re-run with the new corners as its assumptions; S4 does not choose them."),
            "requires": ("the person's ruling, because an over-budget job is Tier 2 (4.2): either accept the narrowed sweep, "
                         "raise the local wall clock in envelope/budget.json, or name a second execution target"),
        }, {
            "what": ("Keep the full sweep and accept that the stiff corner is reported not converged at the cap -- which "
                     "measures the cap, not the suspension. Recorded as the option it is; not recommended."),
        }],
    )
    # The gaps the carried assumptions point at live on the AXIS cards, not on
    # the goal (check 39 reads this card's own kb_gaps): union them by gap_id.
    gaps = {gp["gap_id"]: gp for gp in synthesis.kb_gaps_for(qid)}
    for ax in ("a1", "a2", "a3", "a4", "a5", "a7"):
        for gp in json.loads((cards.question_dir(qid) / a(ax)).read_text()).get("kb_gaps") or []:
            gaps.setdefault(gp["gap_id"], gp)
    card.update(cards.tail(numbers, assumptions=assumptions, kb_refs=synthesis.kb_refs_for(qid, numbers),
                           kb_gaps=[gaps[k] for k in sorted(gaps)], degraded=[]))
    return card


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4 or sys.argv[1] != "s4":
        raise SystemExit("usage: python3 -m src.config_bd_pairwise s4 <qid> <created_at>")
    qid, created_at = sys.argv[2], sys.argv[3]
    revision = cards.question_revision(qid)
    target = cards.question_dir(qid) / cards.artifact_name(f"refusal_s4_{qid}.json", revision)
    card = s4_refusal(qid, revision, created_at)
    cards.refuse_overwrite(target, revision, card)
    print(cards.write(target, card).relative_to(cards.REPO))
