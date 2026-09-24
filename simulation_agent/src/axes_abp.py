"""The six axes for the active configurations, `abp_wca_2d` and `abp_free` (plan.md 4.5.3).

The axis modules `axis_a1_stability` to `axis_a5_budget` were written for
`bd_overdamped`, and every number in them is that configuration's: the
shortest time is the diffusive time because nothing interacts, the box is
bounded by dilution because nothing interacts, and A5 abstains because no
ceiling existed when it was written. None of that is true of an active
particle with a WCA repulsion, so each of those modules dispatches here when
the configuration is an active one, and its own code is left exactly as it
was so the `bd_overdamped` cards regenerate byte for byte.

What changes, axis by axis, and why:

* **A1** -- three more times compete with the diffusive time for shortest:
  the persistence time 1/D_R, the time to self-propel one diameter d/v0 at the
  top of the Peclet range, and the contact relaxation time gamma/k of the WCA
  potential. Which one binds depends on where the sweep sits, so the card
  lists all four and names the smallest. There is no `min` in the formula
  grammar, so the choice is made here and the formula names the winner.
* **A2** -- the fitted quantity is the long-time effective diffusivity, read
  at lags ABOVE the persistence time, so the longest lag in the fit is tens
  of persistence times and the record has to be longer still.
* **A3** -- the length the box is compared against is the persistence length
  v0/D_R = Pe*d, not the rms displacement, and for a compare over box_size the
  box is the question and this axis abstains rather than answering it.
* **A4** -- the save interval resolves lags BELOW the persistence time, where
  the ballistic regime and the crossover sit; the window has a lower bound
  (the plateau) and an upper bound (the span), both on the same card.
* **A5** -- `envelope/budget.json` exists, so the ceiling side of the
  inequality is a person's number and this axis turns it into an interval
  over two products of settable parameters: particle-steps against the wall
  clock and stored coordinates against the disk. That closes the abstention
  the bd_overdamped card describes as this agent's unfinished work.
* **A7** -- unchanged: `axis_a7_driving` reads the goal and the capability
  table and abstains for any undriven configuration.

`abp_free` is screened alongside `abp_wca_2d` because both produce the MSD.
For it A1 keeps one inequality, D_R*dt << 1, and A3 abstains -- nothing
couples a free particle to the box. Which of the two S4 selects is THIS
question's ruling and not a property of the configurations: for
sim-20260923-041/042 the person ruled WCA on 2026-09-23, so abp_free is the
rejected arm there, and a free-particle question rejects the other way.

**A1 for abp_free was wrong in revision 2 of 041 and 042, and the cards on
disk keep it.** The first version computed the same candidate times for the
free configuration as for the interacting one -- the diffusive time and the
time to self-propel one diameter, both of which use a diameter the free model
does not have and a Peclet convention (steric) the registry defines only
where an interaction length exists. The bound came out a factor Pe_steric
too tight: safe, and two decades of compute at Pe 100, resting on a quantity
the model lacks. simulation-9 (window 3) found it reading the module and
measured the free model's actual error: with orientation held fixed over a
step the relative bias in the effective diffusivity is +12 per cent at
D_R*dt = 1, +0.6 per cent at 0.2 and +0.02 per cent at 0.02, invariant when
D_T is moved four decades -- so the one dimensionless group is D_R*dt. The
free branch below now emits that inequality alone. The revision-2 cards are
not rewritten (4.5.5); the correction reaches the record at the next
revision, and this paragraph is the record until then.

Every value is written at one significant figure from the SI recomputation,
the way check 17 compares an order-of-magnitude number.
"""

from __future__ import annotations

import json
import math
import sys

from . import cards

# The validator's own rounding, so a value written here rounds exactly as
# check 17 recomputes it. Python's round() sends ties to even (25 -> 20) and
# round_to_sig sends them away from zero (25 -> 30); two rules for one
# comparison is the shape this repository counted three times on 2026-09-23.
_ROOT = str(cards.REPO)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from contracts.validate import round_to_sig  # noqa: E402

BUDGET = cards.AGENT / "envelope" / "budget.json"

# SI factors for the units this module writes. Kept tiny on purpose: the
# validator holds the registry, and a card that used a unit not here would
# fail there rather than silently pass here.
_SI = {"1": 1.0, "count": 1.0, "s": 1.0, "1/s": 1.0, "um": 1e-6, "um/s": 1e-6,
       "um^2/s": 1e-12, "J": 1.0, "K": 1.0, "h": 3600.0, "min": 60.0, "GB": 1e9}


def oom(value_si: float, unit: str) -> float:
    """One significant figure, rounded in SI and expressed in `unit`."""
    if value_si == 0:
        return 0.0
    rounded = round_to_sig(value_si, 1)
    # Rounded ONCE, in SI, the way check 17 rounds before comparing. A second
    # rounding in the card's unit moved 600 s to 0.2 h and failed the check.
    # The division back into the card's unit then leaves binary residue --
    # 0.001 / 1e-6 is 1000.0000000000001, which check 28 counts as seventeen
    # significant figures. `.12g` strips that residue and rounds nothing a
    # reader could see: 0.16666666666666666 stays 0.166666666667. Measured
    # and reported by simulation-9, whose A3 card it was refusing.
    return float(f"{rounded / _SI[unit]:.12g}")


def _val(numbers: list[dict], name: str) -> float:
    n = next(n for n in numbers if n["name"] == name)
    return float(n["value"]) * _SI[n["unit"]]


def _is_wca(config: str) -> bool:
    return "wca" in config


def _pe_and_phi(goal: dict) -> tuple[str, str]:
    """The goal names the sweep's top (041) or its single point (042)."""
    names = {n["name"] for n in goal.get("numbers", [])}
    pe = "peclet_max" if "peclet_max" in names else "peclet"
    phi = "packing_fraction_max" if "packing_fraction_max" in names else "packing_fraction"
    return pe, phi


def _head(axis, qid, config, created_at, caller_id, kb_version, revision, **kw):
    return cards.head(
        "axis",
        f"axis-{qid}-{config}-{axis}" + ("" if revision == 1 else f"-r{revision}"),
        qid, created_at, revision=revision, caller_id=caller_id, config=config,
        axis=axis, kb_version=kb_version, **kw,
    )


def _sweep_axes(goal: dict) -> list[str]:
    """The sweep axes this goal names, as parameter names: a goal carrying
    peclet_min/_max sweeps the Peclet number, packing_fraction_min/_max the
    packing fraction. Empty for a single-point question."""
    names = {n["name"] for n in goal.get("numbers", [])}
    axes = []
    if "peclet_min" in names and "peclet_max" in names:
        axes.append("peclet_number_steric")
    if "packing_fraction_min" in names and "packing_fraction_max" in names:
        axes.append("packing_fraction")
    return axes


def _ineq(text: str, parameter: str, interval: dict | None = None, varies_with: list[str] | None = None,
          precondition: dict | None = None, abstain: tuple[str, str] | None = None) -> dict:
    """One entry of an axis card's `inequalities[]`. A returned interval says
    what it is a function of: `varies_with` names the sweep axes it depends
    on, and its ABSENCE claims the bound is constant over the sweep (schema,
    7e5de1a) -- so every interval here says one or the other on purpose."""
    out = {"inequality": text, "parameter": parameter}
    if abstain is not None:
        out["state"] = "abstained"; out["kind"], out["reason"] = abstain
        return out
    out["state"] = "returned"
    if interval is not None:
        iv = dict(interval)
        if varies_with:
            iv["varies_with"] = list(varies_with)
        out["interval"] = iv
    if precondition is not None:
        out["precondition"] = precondition
    return out


TAU_D_REF = {
    "entry_id": "tau_d", "grade": "E4",
    "claim": "The diffusive time is the time a sphere needs to diffuse its own diameter, and it sets the shortest record length from which a mean squared displacement can be read.",
}


# --------------------------------------------------------------------------- #
# A1 -- integration stability
# --------------------------------------------------------------------------- #

def a1(qid, config, created_at, caller_id, kb_version, kb_result, revision):
    goal = cards.load_goal(qid, revision)
    pe, _ = _pe_and_phi(goal)
    carried = ["bead_diameter", "translational_diffusivity", "rotational_diffusivity",
               "persistence_time_expected", "temperature", pe]
    if _is_wca(config):
        carried.append("wca_epsilon")
    numbers, assumptions = cards.carry(goal, carried)
    g = {n["name"]: n["grade"] for n in numbers}

    d = _val(numbers, "bead_diameter"); D = _val(numbers, "translational_diffusivity")
    DR = _val(numbers, "rotational_diffusivity"); T = _val(numbers, "temperature")
    Pe = _val(numbers, pe)

    candidates = {}
    if not _is_wca(config):
        # The free model has no length: no contact, no neighbour, no diameter
        # for the step to be compared against. One step must not rotate the
        # orientation appreciably, and that is the whole of A1 here.
        return _a1_free(qid, config, created_at, caller_id, kb_version, kb_result, revision,
                        goal, numbers, assumptions, g, DR)
    tau_d = d * d / D
    numbers.append(cards.num("diffusive_time", oom(tau_d, "s"), "s", "computed:diffusive_time",
        formula="bead_diameter**2/translational_diffusivity",
        inputs=[("bead_diameter", g["bead_diameter"]), ("translational_diffusivity", g["translational_diffusivity"])],
        precision="order_of_magnitude",
        note="kb:tau_d's relation, d**2/D, applied to this card's inputs. NOT carried under the symbol tau_d: check 36 compares a symbol's formula text across cards and the store spells the input `diffusivity`, while this goal names the same quantity translational_diffusivity to keep it apart from the rotational one. Same relation, different formal-parameter name, so the symbol is left off rather than a second spelling registered. For an active particle it is the LONGEST of the candidate times, not the one that binds"))
    candidates["diffusive_time"] = tau_d
    candidates["persistence_time_expected"] = 1.0 / DR

    v0 = Pe * d * DR
    numbers.append(cards.num("self_propulsion_speed_max", oom(v0, "um/s"), "um/s", "computed:steric_peclet_number",
        formula=f"{pe}*bead_diameter*rotational_diffusivity",
        inputs=[(pe, g[pe]), ("bead_diameter", g["bead_diameter"]), ("rotational_diffusivity", g["rotational_diffusivity"])],
        precision="order_of_magnitude",
        note="v0 at the top of the Peclet range, from Pe = v0/(d*D_R), the steric convention (peclet_number_steric). The fastest particle sets the shortest active time"))
    t_active = d / v0
    numbers.append(cards.num("active_step_time", oom(t_active, "s"), "s", "computed:diameter_over_speed",
        formula="bead_diameter/self_propulsion_speed_max",
        inputs=[("bead_diameter", g["bead_diameter"]), ("self_propulsion_speed_max", numbers[-1]["grade"])],
        precision="order_of_magnitude",
        note="the time to self-propel one diameter; a step longer than a fraction of it moves a particle through a neighbour"))
    candidates["active_step_time"] = t_active

    if _is_wca(config):
        eps = _val(numbers, "wca_epsilon")
        numbers.append(cards.num("wca_curvature_prefactor", 57, "1", "literature:wca_potential_curvature_at_minimum",
            precision="significant_figures",
            note="U''(r_min) of the WCA potential in units of epsilon over sigma squared: 4*(156/2**(7/3) - 42/2**(4/3)) = 57.1. Exact arithmetic on the published form, not a fit"))
        t_contact = cards_kT(T) * d * d / (57.0 * eps * D)
        numbers.append(cards.num("contact_relaxation_time", oom(t_contact, "s"), "s", "computed:drag_over_stiffness",
            formula="k_B*temperature*bead_diameter**2/(wca_curvature_prefactor*wca_epsilon*translational_diffusivity)",
            inputs=[("temperature", g["temperature"]), ("bead_diameter", g["bead_diameter"]),
                    ("wca_curvature_prefactor", "E3"), ("wca_epsilon", g["wca_epsilon"]),
                    ("translational_diffusivity", g["translational_diffusivity"])],
            precision="order_of_magnitude",
            note="gamma/k with gamma = k_B*T/D_T and k = 57*epsilon/d**2: the time an overlap relaxes at the potential minimum. Under strong activity particles sit deeper in the wall where the curvature is larger, so this is a LOWER estimate of the stiffness and an UPPER one of the time; the falsifier on a_wca_stiffness is what catches that"))
        candidates["contact_relaxation_time"] = t_contact

    shortest_name = min(candidates, key=candidates.get)
    shortest = candidates[shortest_name]
    numbers.append(cards.num("shortest_resolved_time", oom(shortest, "s"), "s", "computed:smallest_candidate_time",
        formula=shortest_name,
        inputs=[(shortest_name, next(n["grade"] for n in numbers if n["name"] == shortest_name))],
        precision="order_of_magnitude",
        note="the smallest of " + ", ".join(f"{k} ({oom(v, 's'):g} s)" for k, v in sorted(candidates.items(), key=lambda kv: kv[1]))
             + ". The formula grammar has no min(), so the comparison is made here and the formula names the winner"))
    numbers.append(cards.num("dt_resolution_factor", 0.01, "1", "assumed:a_dt_factor", precision="order_of_magnitude",
        note="how far below the shortest resolved time the step must sit: two decades"))
    dt_max = 0.01 * shortest
    numbers.append(cards.num("integration_timestep_max", oom(dt_max, "s"), "s", "computed:resolution_of_shortest_time",
        formula="dt_resolution_factor*shortest_resolved_time",
        inputs=[("dt_resolution_factor", "E5"), ("shortest_resolved_time", numbers[-2]["grade"])],
        precision="order_of_magnitude", note="upper bound only; nothing in A1 bounds the step from below"))
    assumptions.append({
        "rationale_id": "a_dt_factor", "gap_ref": "integration_timestep_resolution_factor_absent",
        "statement": "Two decades below the shortest resolved time is the usual margin for an overdamped integrator; it is a convention and no convergence scan on this model has been run.",
        "numbers": ["dt_resolution_factor"],
        "falsifier": "a timestep scan on this configuration showing the effective diffusivity flat over a wider range of steps replaces this factor with a measured one",
    })
    dt_iv = {"parameter": "integration_timestep", "unit": "s", "max": oom(dt_max, "s"),
             "basis": ["integration_timestep_max"], "precision": "order_of_magnitude"}
    sweep = _sweep_axes(goal)
    pe_dependent = [a for a in sweep if a == "peclet_number_steric"]
    # On constraints[] as well as on the inequality: the sweep invariant (plan
    # schema, 92602c2) lets a point condition differ exactly when SOME axis
    # card's constraint on that parameter carries varies_with, and a check
    # reads constraints[]. Revision 3's cards carried it on inequalities[]
    # alone; from the next revision it is on both.
    if pe_dependent:
        dt_iv["varies_with"] = list(pe_dependent)
    card = _head("a1", qid, config, created_at, caller_id, kb_version, revision,
        method="deterministic", verdict="feasible",
        constraints=[dt_iv],
        inequalities=[
            _ineq("dt << bead_diameter / v0(Pe): the step must not carry a particle through a neighbour", "integration_timestep",
                  interval=dt_iv if shortest_name == "active_step_time" else None,
                  varies_with=pe_dependent or None) if shortest_name == "active_step_time" else
            _ineq("dt << bead_diameter / v0(Pe): the step must not carry a particle through a neighbour", "integration_timestep",
                  abstain=("not_constraining", f"at the top of the sweep this time is {oom(candidates['active_step_time'], 's'):g} s and {shortest_name} is shorter; the returned interval below is the binding one")),
            _ineq("dt << gamma/k at WCA contact: an overlap must relax over many steps", "integration_timestep",
                  interval=dt_iv if shortest_name == "contact_relaxation_time" else None) if shortest_name == "contact_relaxation_time" else
            _ineq("dt << gamma/k at WCA contact: an overlap must relax over many steps", "integration_timestep",
                  abstain=("not_constraining", f"the contact time is {oom(candidates['contact_relaxation_time'], 's'):g} s and {shortest_name} is shorter at the top of the sweep; it is constant over the sweep, and at low Pe it becomes the binding one -- S4 evaluates the pair per point")),
            _ineq("dt << 1/D_R: the orientation must not turn appreciably in one step", "integration_timestep",
                  abstain=("not_constraining", f"1/D_R is {oom(candidates['persistence_time_expected'], 's'):g} s, above the binding time; constant over the sweep")),
            _ineq("dt << tau_d: the diffusive time", "integration_timestep",
                  abstain=("not_constraining", f"tau_d is {oom(candidates['diffusive_time'], 's'):g} s, the longest of the four; constant over the sweep")),
        ])
    card.update(cards.tail(numbers, assumptions=assumptions,
        **cards.evidence(kb_result, [dict(TAU_D_REF, kb_version=kb_version)] + cards.carried_kb_refs(goal, numbers))))
    card["note"] = (
        f"The binding time is {shortest_name}, not the diffusive time bd_overdamped uses. "
        + ("The interval is stated at the top of the Peclet range and VARIES WITH the Peclet number: at lower Pe the self-propulsion "
           "step lengthens as 1/Pe and the constant contact time takes over, so S4 must evaluate the pair per grid point rather than "
           "intersect this corner's value across the sweep. " if sweep else "")
        + ("For the free active configuration there is no contact time, so activity alone binds. " if not _is_wca(config) else
           "The contact time is estimated at the potential minimum and is the weakest number here. ")
        + "S4 picks the step inside the interval (4.5.2)."
    )
    return card


def _a1_free(qid, config, created_at, caller_id, kb_version, kb_result, revision,
             goal, numbers, assumptions, g, DR):
    """A1 for a free active particle: D_R*dt << 1 and nothing else."""
    # Drop the carried numbers a free model has no use for; the persistence
    # time and the rotational diffusivity are what the bound reads.
    keep = {"rotational_diffusivity", "persistence_time_expected"}
    numbers = [n for n in numbers if n["name"] in keep]
    assumptions = [a for a in assumptions if any(n in keep for n in a.get("numbers", []))]
    numbers.append(cards.num("dt_resolution_factor", 0.01, "1", "assumed:a_dt_factor", precision="order_of_magnitude",
        note="how far below the persistence time the step must sit: two decades. Measured on a reference Euler-Maruyama integrator by simulation-9: the bias in the effective diffusivity is +0.6 per cent at D_R*dt = 0.2 and +0.02 per cent at 0.02, so two decades holds it under the statistical error; the declared engine's scheme may carry a different coefficient and the same group"))
    dt_max = 0.01 / DR
    numbers.append(cards.num("integration_timestep_max", oom(dt_max, "s"), "s", "computed:resolution_of_persistence_time",
        formula="dt_resolution_factor*persistence_time_expected",
        inputs=[("dt_resolution_factor", "E5"), ("persistence_time_expected", g["persistence_time_expected"])],
        precision="order_of_magnitude",
        note="upper bound only. The free model has no length scale, so no displacement per step is constrained; the orientation held fixed over one step is the only error the integrator makes, and D_R*dt is the only group it can depend on"))
    assumptions.append({
        "rationale_id": "a_dt_factor", "gap_ref": "integration_timestep_resolution_factor_absent",
        "statement": "Two decades below the persistence time is a convention; a reference integrator measured the bias at that factor as two hundredths of a per cent, which is far inside the target error, but the declared engine has not been scanned.",
        "numbers": ["dt_resolution_factor"],
        "falsifier": "a timestep scan on hoomd_backend showing the effective diffusivity flat over a wider range of D_R*dt replaces this factor with a measured one",
    })
    card = _head("a1", qid, config, created_at, caller_id, kb_version, revision,
        method="deterministic", verdict="feasible",
        constraints=[{"parameter": "integration_timestep", "unit": "s", "max": oom(dt_max, "s"),
                      "basis": ["integration_timestep_max"], "precision": "order_of_magnitude"}])
    card.update(cards.tail(numbers, assumptions=assumptions,
        **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
    card["note"] = (
        "One inequality, D_R*dt << 1. The diffusive time and the self-propulsion step of the "
        "interacting branch are not computed here because the free model has no diameter for "
        "them to stand on; a bound resting on an absent quantity is not a safe bound but an "
        "expensive one. Revision 2's cards carried that bound and are left as written (4.5.5)."
    )
    return card


def cards_kT(T: float) -> float:
    from . import physics
    return physics.K_B * T


# --------------------------------------------------------------------------- #
# A2 -- statistics
# --------------------------------------------------------------------------- #

def a2(qid, config, created_at, caller_id, kb_version, kb_result, revision):
    goal = cards.load_goal(qid, revision)
    numbers, assumptions = cards.carry(goal, ["persistence_time_expected"])
    g = {n["name"]: n["grade"] for n in numbers}
    tau_p = _val(numbers, "persistence_time_expected")

    numbers.append(cards.num("plateau_factor", 10, "1", "assumed:a_plateau", precision="order_of_magnitude",
        note="how many persistence times into the lag the MSD slope is read as the long-time value"))
    lag = 10 * tau_p
    numbers.append(cards.num("fit_lag_reference", oom(lag, "s"), "s", "computed:plateau_lag",
        formula="plateau_factor*persistence_time_expected",
        inputs=[("plateau_factor", "E5"), ("persistence_time_expected", g["persistence_time_expected"])],
        precision="order_of_magnitude",
        note="the longest lag whose displacements the fit needs many of; A2's reference, not A4's window -- the two axes derive it from the same goal input (4.5.3 rule b)"))
    numbers.append(cards.num("lag_to_record_ratio_max", 0.1, "1", "assumed:a_window_statistics", precision="order_of_magnitude",
        note="the largest share of the record one lag may span"))
    T_min = lag / 0.1
    numbers.append(cards.num("total_simulated_time_min", oom(T_min, "s"), "s", "computed:record_over_ratio",
        formula="fit_lag_reference/lag_to_record_ratio_max",
        inputs=[("fit_lag_reference", numbers[-2]["grade"]), ("lag_to_record_ratio_max", "E5")],
        precision="order_of_magnitude",
        note="floor only; A5 bounds the run from above"))
    numbers.append(cards.num("target_relative_error", 0.1, "1", "assumed:a_statistics", precision="order_of_magnitude",
        note="ten per cent on the effective diffusivity, well inside the decade the goal asks for"))
    numbers.append(cards.num("independent_samples_min", 100, "count", "assumed:a_statistics", precision="order_of_magnitude",
        note="one over the square of the target error. The product n_particles*total_simulated_time/fit_lag_reference must exceed it; at the record floor above that holds for any ensemble of ten or more particles, so the record length and not the sample count is what binds here"))
    assumptions += [
        {"rationale_id": "a_plateau", "gap_ref": "plateau_factor_absent",
         "statement": "Ten persistence times is where the free active MSD is within a few per cent of its asymptotic slope, since the memory term decays as exp(-t/tau_p). Interactions can lengthen the approach, which is a result and not something to assume away.",
         "numbers": ["plateau_factor"],
         "falsifier": "a fitted slope that still drifts between ten and thirty persistence times raises this factor"},
        {"rationale_id": "a_window_statistics", "gap_ref": "lag_to_record_ratio_absent",
         "statement": "A lag may span at most a tenth of the record so that every lag in the fit is determined by many displacements rather than by one.",
         "numbers": ["lag_to_record_ratio_max"],
         "falsifier": "a weighted fit whose slope is unchanged when the longest lag is shortened retires this fraction"},
        {"rationale_id": "a_statistics", "gap_ref": "independent_samples_prefactor_absent",
         "statement": "A ten per cent statistical error needs of order one hundred independent displacements at the longest fit lag, from the square-root scaling of an ensemble mean; the prefactor for a weighted slope estimator on an active MSD has not been measured.",
         "numbers": ["target_relative_error", "independent_samples_min"],
         "falsifier": "a seed-to-seed spread wider than ten per cent at this sample count raises the floor"},
    ]
    t_iv = {"parameter": "total_simulated_time", "unit": "s", "min": oom(T_min, "s"), "basis": ["total_simulated_time_min"], "precision": "order_of_magnitude"}
    r_iv = {"parameter": "lag_to_record_ratio", "unit": "1", "max": 0.1, "basis": ["lag_to_record_ratio_max"], "precision": "order_of_magnitude"}
    card = _head("a2", qid, config, created_at, caller_id, kb_version, revision,
        method="deterministic", verdict="feasible",
        constraints=[t_iv, r_iv],
        inequalities=[
            _ineq("T >= plateau lag / lag_to_record_ratio_max: the record must hold many of the longest fitted displacements", "total_simulated_time", interval=t_iv),
            _ineq("max lag / T <= lag_to_record_ratio_max", "lag_to_record_ratio", interval=r_iv),
        ])
    card.update(cards.tail(numbers, assumptions=assumptions, **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
    card["note"] = (
        "The record must be a hundred persistence times long before the long-time slope can be read "
        "with ten per cent error, whatever the ensemble. The ensemble is not free here as it was for "
        "bd_overdamped: with interactions it is a density, and A3 and A5 own what that costs."
    )
    return card


# --------------------------------------------------------------------------- #
# A3 -- finite size
# --------------------------------------------------------------------------- #

def a3(qid, config, created_at, caller_id, kb_version, kb_result, revision):
    goal = cards.load_goal(qid, revision)
    pe, phi = _pe_and_phi(goal)
    compare_box = goal.get("compare_variable") == "box_size"

    if compare_box:
        numbers, assumptions = cards.carry(goal, ["bead_diameter", "persistence_length_expected", phi,
                                                  "box_over_persistence_length_min", "box_over_persistence_length_max"])
        g = {n["name"]: n["grade"] for n in numbers}
        d = _val(numbers, "bead_diameter"); lp = _val(numbers, "persistence_length_expected")
        f = _val(numbers, phi)
        lo = _val(numbers, "box_over_persistence_length_min"); hi = _val(numbers, "box_over_persistence_length_max")
        numbers.append(cards.num("box_length_smallest_arm", oom(lo * lp, "um"), "um", "computed:arm_times_persistence_length",
            formula="box_over_persistence_length_min*persistence_length_expected",
            inputs=[("box_over_persistence_length_min", g["box_over_persistence_length_min"]), ("persistence_length_expected", g["persistence_length_expected"])],
            precision="order_of_magnitude", note="the smallest arm: a particle meets its own image within one persistence length"))
        numbers.append(cards.num("box_length_largest_arm", oom(hi * lp, "um"), "um", "computed:arm_times_persistence_length",
            formula="box_over_persistence_length_max*persistence_length_expected",
            inputs=[("box_over_persistence_length_max", g["box_over_persistence_length_max"]), ("persistence_length_expected", g["persistence_length_expected"])],
            precision="order_of_magnitude", note="the largest arm"))
        n_max = 4 * f * (hi * lp) ** 2 / (math.pi * d * d)
        numbers.append(cards.num("n_particles_largest_arm", oom(n_max, "1"), "1", "computed:area_fraction_times_box",
            formula=f"4*{phi}*box_length_largest_arm**2/(pi*bead_diameter**2)",
            inputs=[(phi, g[phi]), ("box_length_largest_arm", numbers[-1]["grade"]), ("bead_diameter", g["bead_diameter"])],
            precision="order_of_magnitude", note="what the largest arm costs in particles at the held packing fraction; A5 says whether it is affordable"))
        card = _head("a3", qid, config, created_at, caller_id, kb_version, revision,
            method="deterministic", verdict="abstain",
            abstain_reason=(
                "The box is the compare variable of this question. The inequality this axis owns -- the box "
                "against the persistence length and the other dynamical lengths -- is the hypothesis the arms "
                "test, so bounding the box here would forbid the arms the question exists to run. The arms are "
                "recorded in numbers[] and the abstention is the record that the axis was asked (P1)."
                + (" For the free configuration the abstention is doubled: nothing couples a free particle to its image, so no arm can differ from another." if not _is_wca(config) else "")
            ))
        card.update(cards.tail(numbers, assumptions=assumptions, **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
        card["note"] = "Periodic in both directions; unwrapped coordinates in the estimator, or the image bound becomes an artefact of the analysis and not of the system."
        return card

    if not _is_wca(config):
        numbers, assumptions = cards.carry(goal, ["bead_diameter", pe])
        g = {n["name"]: n["grade"] for n in numbers}
        d = _val(numbers, "bead_diameter"); Pe = _val(numbers, pe)
        numbers.append(cards.num("persistence_length_max", oom(Pe * d, "um"), "um", "computed:steric_peclet_number",
            formula=f"{pe}*bead_diameter", inputs=[(pe, g[pe]), ("bead_diameter", g["bead_diameter"])],
            precision="order_of_magnitude", note="v0/D_R in 2D with v0 = Pe*d*D_R; recorded so the box can be compared to it even though nothing here bounds the box"))
        card = _head("a3", qid, config, created_at, caller_id, kb_version, revision,
            method="deterministic", verdict="abstain",
            abstain_reason=(
                "Nothing couples a free active particle to its periodic image: with no pair potential and "
                "unwrapped coordinates the MSD and every quantity read off it are independent of the box. "
                "There is no inequality to emit. The box has only to hold the ensemble, which is A5's cost and not A3's physics."
            ))
        card.update(cards.tail(numbers, assumptions=assumptions, **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
        card["note"] = "The abstention is the physics of the free model, not a missing input."
        return card

    numbers, assumptions = cards.carry(goal, ["bead_diameter", pe, phi])
    g = {n["name"]: n["grade"] for n in numbers}
    d = _val(numbers, "bead_diameter"); Pe = _val(numbers, pe); f = _val(numbers, phi)
    lp = Pe * d
    numbers.append(cards.num("persistence_length_max", oom(lp, "um"), "um", "computed:steric_peclet_number",
        formula=f"{pe}*bead_diameter", inputs=[(pe, g[pe]), ("bead_diameter", g["bead_diameter"])],
        precision="order_of_magnitude", note="v0/D_R in 2D with v0 = Pe*d*D_R, at the top of the sweep: the longest persistence length any operating point has"))
    numbers.append(cards.num("box_margin_factor", 10, "1", "assumed:a_box_margin", precision="order_of_magnitude",
        note="how many persistence lengths of box before a particle's image is uncorrelated with it"))
    L_min = 10 * lp
    numbers.append(cards.num("box_length_min", oom(L_min, "um"), "um", "computed:margin_over_persistence_length",
        formula="box_margin_factor*persistence_length_max",
        inputs=[("box_margin_factor", "E5"), ("persistence_length_max", numbers[-2]["grade"])],
        precision="order_of_magnitude", note="a particle must not run into its own image while it still remembers its direction"))
    n_min = 4 * f * L_min ** 2 / (math.pi * d * d)
    numbers.append(cards.num("n_particles_at_box_min", oom(n_min, "1"), "1", "computed:area_fraction_times_box",
        formula=f"4*{phi}*box_length_min**2/(pi*bead_diameter**2)",
        inputs=[(phi, g[phi]), ("box_length_min", numbers[-1]["grade"]), ("bead_diameter", g["bead_diameter"])],
        precision="order_of_magnitude", note="what the minimum box costs in particles at the densest point of the sweep. With interactions the ensemble is a density and not a statistics knob, so this number is where A3 and A5 meet"))
    assumptions.append({
        "rationale_id": "a_box_margin", "gap_ref": "box_margin_factor_absent",
        "statement": "Ten persistence lengths of box keeps the image contribution to the long-time MSD below the statistical error; it is a margin and not a measured threshold. The correlation length of motility-induced clusters at the dense, high-Peclet corner can exceed the persistence length and is an output of the run, so this bound is a precondition there and not a guarantee.",
        "numbers": ["box_margin_factor"],
        "falsifier": "sim-20260923-042's arms: a box at fewer persistence lengths that reproduces the same effective diffusivity retires the margin, and one at more that does not raises it",
    })
    box_iv = {"parameter": "box_length", "unit": "um", "min": oom(L_min, "um"), "basis": ["box_length_min"], "precision": "order_of_magnitude"}
    sweep = _sweep_axes(goal)
    if any(a == "peclet_number_steric" for a in sweep):
        box_iv["varies_with"] = ["peclet_number_steric"]      # see A1: on constraints[] too
    card = _head("a3", qid, config, created_at, caller_id, kb_version, revision,
        method="deterministic", verdict="feasible",
        constraints=[box_iv],
        inequalities=[
            _ineq("L >> persistence length v0/D_R = Pe*d: a particle must not meet its own image while it remembers its direction",
                  "box_length", interval=box_iv, varies_with=[a for a in sweep if a == "peclet_number_steric"] or None),
            _ineq("L >> cluster correlation length in the motility-induced regime", "box_length",
                  abstain=("no_input", "the correlation length of clusters at the dense, high-Peclet corner is an output of the run and the store holds nothing on it; the persistence-length bound is a precondition there, not a guarantee")) | {"missing": ["cluster_correlation_length"]},
        ])
    card.update(cards.tail(numbers, assumptions=assumptions, **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
    card["note"] = (
        "Periodic in both directions. The bound is set at the top of the Peclet range because one box per "
        "sweep is simpler to compare across; S4 may instead scale the box per operating point, and the "
        "record here says what that would relax."
    )
    return card


# --------------------------------------------------------------------------- #
# A4 -- sampling
# --------------------------------------------------------------------------- #

def a4(qid, config, created_at, caller_id, kb_version, kb_result, revision):
    goal = cards.load_goal(qid, revision)
    numbers, assumptions = cards.carry(goal, ["persistence_time_expected"])
    g = {n["name"]: n["grade"] for n in numbers}
    tau_p = _val(numbers, "persistence_time_expected")

    numbers.append(cards.num("lag_coverage_factor", 0.01, "1", "assumed:a_lag_coverage", precision="order_of_magnitude",
        note="save interval as a fraction of the persistence time: two decades of ballistic lag below the crossover"))
    save_max = 0.01 * tau_p
    numbers.append(cards.num("save_interval_max", oom(save_max, "s"), "s", "computed:two_decades_below_persistence",
        formula="lag_coverage_factor*persistence_time_expected",
        inputs=[("lag_coverage_factor", "E5"), ("persistence_time_expected", g["persistence_time_expected"])],
        precision="order_of_magnitude", note="upper bound. The crossover and the short-time slope live below tau_p, and a save interval near tau_p would record only the diffusive tail"))
    numbers.append(cards.num("plateau_factor", 10, "1", "assumed:a_plateau", precision="order_of_magnitude",
        note="how many persistence times into the lag the effective diffusivity is read; the same input A2 derives its reference lag from, not A2's output (4.5.3 rule b)"))
    lower = 10 * tau_p
    numbers.append(cards.num("fit_lag_range_lower_bound_min", oom(lower, "s"), "s", "computed:plateau_lag",
        formula="plateau_factor*persistence_time_expected",
        inputs=[("plateau_factor", "E5"), ("persistence_time_expected", g["persistence_time_expected"])],
        precision="order_of_magnitude", note="the window parameter of effective_translational_diffusivity; a value read earlier is D_T under that name (contracts/observables.json)"))
    numbers.append(cards.num("window_span_factor", 3, "1", "assumed:a_window_span", precision="order_of_magnitude",
        note="how many times the lower bound the MSD window extends, so the fit has lags to fit"))
    span = 3 * lower
    numbers.append(cards.num("max_lag_time_min", oom(span, "s"), "s", "computed:span_over_lower_bound",
        formula="window_span_factor*fit_lag_range_lower_bound_min",
        inputs=[("window_span_factor", "E5"), ("fit_lag_range_lower_bound_min", numbers[-2]["grade"])],
        precision="order_of_magnitude", note="the window parameter of mean_squared_displacement, bounded from BELOW here: opposite to tracer_diffusivity, whose window is bounded from above to stay free"))
    assumptions += [
        {"rationale_id": "a_lag_coverage", "gap_ref": "lag_coverage_factor_absent",
         "statement": "Two decades of lag below the persistence time is what it takes to see the ballistic slope of two, the crossover, and the approach to one on one curve; fewer would fit a slope through a crossover nobody resolved.",
         "numbers": ["lag_coverage_factor"],
         "falsifier": "an msd_loglog_slope that reads two over the whole first decade retires the second"},
        {"rationale_id": "a_plateau", "gap_ref": "plateau_factor_absent",
         "statement": "Ten persistence times is where the free active MSD is within a few per cent of its asymptotic slope. Interactions can lengthen the approach, which is a result.",
         "numbers": ["plateau_factor"],
         "falsifier": "a fitted slope that still drifts between ten and thirty persistence times raises this factor"},
        {"rationale_id": "a_window_span", "gap_ref": "window_span_factor_absent",
         "statement": "A fit over lags from ten to thirty persistence times spans half a decade, enough for a weighted slope and short enough that the longest lag stays inside A2's record ratio.",
         "numbers": ["window_span_factor"],
         "falsifier": "a slope that changes with the upper end of the fit by more than the statistical error widens the span"},
    ]
    s_iv = {"parameter": "save_interval", "unit": "s", "max": oom(save_max, "s"), "basis": ["save_interval_max"], "precision": "order_of_magnitude"}
    l_iv = {"parameter": "fit_lag_range_lower_bound", "unit": "s", "min": oom(lower, "s"), "basis": ["fit_lag_range_lower_bound_min"], "precision": "order_of_magnitude"}
    w_iv = {"parameter": "max_lag_time", "unit": "s", "min": oom(span, "s"), "basis": ["max_lag_time_min"], "precision": "order_of_magnitude"}
    card = _head("a4", qid, config, created_at, caller_id, kb_version, revision,
        method="deterministic", verdict="feasible",
        constraints=[s_iv, l_iv, w_iv],
        inequalities=[
            _ineq("save_interval << persistence time: resolve the ballistic lags and the crossover", "save_interval", interval=s_iv),
            _ineq("fit lower bound >> persistence time: read the plateau and not D_T", "fit_lag_range_lower_bound", interval=l_iv),
            _ineq("max_lag_time >= a span above the lower bound: lags to fit", "max_lag_time", interval=w_iv),
        ])
    card.update(cards.tail(numbers, assumptions=assumptions, **cards.evidence(kb_result, cards.carried_kb_refs(goal, numbers))))
    card["note"] = (
        "Three windows, one per registered observable that this plan reads: the save interval for "
        "msd_loglog_slope and the crossover, the lower bound for effective_translational_diffusivity, "
        "and the span for mean_squared_displacement. A4 says nothing about the integration step."
    )
    return card


# --------------------------------------------------------------------------- #
# A5 -- resource budget
# --------------------------------------------------------------------------- #

def a5(qid, config, created_at, caller_id, kb_version, kb_result, revision):
    goal = cards.load_goal(qid, revision)
    budget = json.loads(BUDGET.read_text())
    local = next(t for t in budget["targets"] if t["target"] == "local")["limits"]
    wall = local["wall_clock_max"]; store = local["storage_max"]
    src = "spec:simulation_agent/envelope/budget.json:local"

    numbers: list[dict] = []
    numbers.append(cards.num("wall_clock_max", wall["value"], wall["unit"], src, precision="significant_figures",
        note=f"the ceiling a person chose ({wall['chosen_by']['by']}, {wall['chosen_by']['on']}); carried so the interval below has a basis the card holds. A ceiling is a decision, and spec: is the nearest kind for a number read off a policy file"))
    numbers.append(cards.num("storage_max", store["value"], store["unit"], src, precision="significant_figures",
        note="the disk ceiling of the same target"))
    numbers.append(cards.num("particle_step_rate", 1e7, "1/s", "assumed:a_cost_reference", precision="order_of_magnitude",
        note="particle-steps per second for a 2D WCA active system with a neighbour list on this workstation's CPU: of order ten million. A guess until the smoke run measures it"))
    steps_max = _val(numbers, "wall_clock_max") * 1e7
    numbers.append(cards.num("particle_steps_max", oom(steps_max, "1"), "1", "computed:ceiling_times_rate",
        formula="wall_clock_max*particle_step_rate",
        inputs=[("wall_clock_max", "E3"), ("particle_step_rate", "E5")],
        precision="order_of_magnitude",
        note="the product n_particles*total_simulated_time/integration_timestep may not exceed this. A5 constrains the product and not any factor, and takes none of them from A1 or A2 (4.5.3 rule b)"))
    numbers.append(cards.num("bytes_per_coordinate", 8e-9, "GB", "spec:ieee754_double", precision="significant_figures",
        note="one double-precision coordinate, in the unit the ceiling is written in"))
    coords_max = _val(numbers, "storage_max") / 8.0
    numbers.append(cards.num("coordinates_stored_max", oom(coords_max, "1"), "1", "computed:ceiling_over_bytes",
        formula="storage_max/bytes_per_coordinate",
        inputs=[("storage_max", "E3"), ("bytes_per_coordinate", "E3")],
        precision="order_of_magnitude",
        note="the product 2*n_particles*total_simulated_time/save_interval may not exceed this, two coordinates per particle per frame in two dimensions"))
    assumptions = [{
        "rationale_id": "a_cost_reference", "gap_ref": "particle_step_rate_absent",
        "statement": "The cost model is one pair-force evaluation per particle per step through a neighbour list, at a rate guessed from the engine's class of hardware. Nothing on this machine has run this configuration.",
        "numbers": ["particle_step_rate"],
        "falsifier": "a run that WRITES THE TRAJECTORY THIS PLAN DECLARES on hoomd_backend replaces the rate with the value measured off that run's own log and the ceiling interval moves with it",
    }]
    p_iv = {"parameter": "particle_steps", "unit": "1", "max": oom(steps_max, "count"), "basis": ["particle_steps_max"], "precision": "order_of_magnitude"}
    c_iv = {"parameter": "coordinates_stored", "unit": "1", "max": oom(coords_max, "count"), "basis": ["coordinates_stored_max"], "precision": "order_of_magnitude"}
    card = _head("a5", qid, config, created_at, caller_id, kb_version, revision,
        method="llm_estimate", verdict="feasible",
        constraints=[p_iv, c_iv],
        inequalities=[
            _ineq("N * T / dt <= wall_clock_max * particle_step_rate", "particle_steps", interval=p_iv),
            _ineq("2 * N * T / save_interval <= storage_max / bytes_per_coordinate", "coordinates_stored", interval=c_iv),
        ])
    card.update(cards.tail(numbers, assumptions=assumptions, **cards.evidence(kb_result, [])))
    card["note"] = (
        "This axis no longer abstains: the ceiling exists and is a person's, the cost model is this "
        "agent's, and the interval is over two products of settable parameters. The smoke budget "
        f"({local['smoke_budget']['wall_clock_max']['value']} {local['smoke_budget']['wall_clock_max']['unit']}, "
        f"{local['smoke_budget']['storage_max']['value']} {local['smoke_budget']['storage_max']['unit']}) is the operator's "
        "gate at run time and not a plan-time interval."
    )
    return card


BUILDERS = {"a1": a1, "a2": a2, "a3": a3, "a4": a4, "a5": a5}


def is_active(config: str) -> bool:
    return config.startswith("abp")


def build(axis: str, qid, config, created_at, caller_id, kb_version, kb_result=None, revision=1):
    if not caller_id.endswith(f":{axis}"):
        raise ValueError(f"{caller_id!r} was issued to another axis; this module is {axis}")
    return BUILDERS[axis](qid, config, created_at, caller_id, kb_version, kb_result, revision)
