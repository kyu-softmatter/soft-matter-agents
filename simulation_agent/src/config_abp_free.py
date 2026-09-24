"""`abp_free`'s S4 operating point and S5 plan (plan.md 4.5.2, 4.5.4).

**This module defines no `build`, on purpose.** The six axis modules hand
`abp_free` to `axes_abp` before they reach `configs.dispatch`, so an axis
`build` here would never be called and two files would appear to answer for
one configuration. What lives here is the part nothing else covers: the
operating point S4 picks inside the axis intervals, and the plan card S5
writes from it.

What makes this configuration's plan different from `bd_overdamped`'s is not
a preference:

* **There is no diffusive time and no `tau_d`.** A free active particle has
  no length -- no pair potential, no wall, no obstacle, no diameter -- so the
  two times that matter are the rotational time `tau_R = 1/((d-1) D_R)` and
  the early crossover `tau_1 = D_T/v0^2`, and the plan is written against
  those.
* **There is no box bound.** A3 abstains because nothing couples a free
  particle to its periodic image, so `box_length` is not an interval S4 picks
  inside; it is a number the engine needs and the plan states, and the card
  says which of those it is.
* **The success criterion cannot be `tracer_diffusivity`.** That observable's
  estimator is the short-time free-regime slope and this run's answer is the
  long-time plateau -- opposite ends of the curve, which is why
  `effective_translational_diffusivity` was registered separately with a
  LOWER bound on its fit range.
"""

from __future__ import annotations

from . import cards, synthesis


# --- S4: the operating point ------------------------------------------- #
#
# Every value below was checked against the axis intervals before being
# written, not after: dt 1e-3 s under A1's 1 s, T 40000 s over A2's 10000 s
# floor, lag-to-record 0.075 under A2's 0.1, save 0.01 s under A4's 1 s,
# max_lag 3000 s over A4's 3000 s floor, 4e9 particle-steps under A5's 7e10
# and 8e8 stored coordinates under A5's 1e9.
#
# THE RECORD IS LONGER THAN A2'S FLOOR AND A2 IS NOT WHY. A4 wants a window
# of at least 3000 s and A2 wants the window to be at most a tenth of the
# record, so the two together force T >= 30000 s -- three times A2's own
# floor. Neither axis says that on its own and S4 is where it appears, which
# is what 4.5.4 means by the conflict surfacing here.

def operating_point() -> dict:
    return {
        "carry": [
            ("goal.json", "bead_diameter"),
            ("goal.json", "temperature"),
            ("goal.json", "viscosity"),
            ("goal.json", "translational_diffusivity"),
            ("goal.json", "rotational_diffusivity"),
            ("goal.json", "self_propulsion_speed"),
            ("goal.json", "persistence_time_expected"),
            ("goal.json", "thermal_crossover_time"),
            ("goal.json", "persistence_length_expected"),
            ("goal.json", "peclet_thermal"),
            ("goal.json", "n_particles"),
            ("axis_abp_free_a1.json", "integration_timestep_max"),
            ("axis_abp_free_a2.json", "total_simulated_time_min"),
            ("axis_abp_free_a2.json", "lag_to_record_ratio_max"),
            ("axis_abp_free_a4.json", "save_interval_max"),
            ("axis_abp_free_a4.json", "fit_lag_range_lower_bound_min"),
            ("axis_abp_free_a4.json", "max_lag_time_min"),
            # A5 owns cost. `wall_clock_estimate` and `storage_estimate` are
            # what envelope_check compares against ceilings, and the active
            # budget axis does not emit them yet -- the passive one does. S4
            # MAY NOT SUPPLY THEM: 4.5.4 forbids introducing a number here and
            # check 12 enforces it, correctly. Requested from the seat that
            # owns axes_abp; until they arrive the envelope check reads
            # `unavailable` and the operator refuses a Tier 1 run, which is
            # the gate working rather than failing.
            ("axis_abp_free_a5.json", "particle_step_rate"),
            ("axis_abp_free_a5.json", "bytes_per_coordinate"),
            ("axis_abp_free_a5.json", "particle_steps_max"),
            ("axis_abp_free_a5.json", "coordinates_stored_max"),
        ],
        "computed": [
            {
                "name": "total_simulated_time_point",
                "value": 40000,
                "unit": "s",
                "source": "computed:four_hundred_persistence_times",
                "formula": "400 * persistence_time_expected",
                "inputs": ["persistence_time_expected"],
                "note": (
                    "four hundred persistence times. NOT A2's floor, which is a hundred: A4 "
                    "requires a window of at least 3000 s and A2 requires the window to be at "
                    "most a tenth of the record, so the pair forces at least 30000 s and 400 "
                    "tau_R is the next round multiple above it. The 400 is a decision and "
                    "carries no grade; the seconds inherit E4 from the persistence time"
                ),
            },
            {
                "name": "save_interval_point",
                "value": 0.1,
                "unit": "s",
                "source": "computed:tenth_of_the_a4_ceiling",
                "formula": "save_interval_max / 10",
                "inputs": ["save_interval_max"],
                "note": (
                    "a decade under A4's ceiling. STORAGE IS WHAT SETS IT, not the physics: at "
                    "the early crossover tau_1 = D_T/v0^2 it would resolve all three regimes "
                    "and cost 6.4 GB against a 10 GB ceiling for one run, and this buys the "
                    "ballistic peak and the whole crossover to diffusion for 0.6 GB. The "
                    "shortest lag is then ten times tau_1, so the run enters the ballistic "
                    "regime already risen and does not show it rise -- recorded as a rejection "
                    "rather than left to be discovered in the output"
                ),
            },
            {
                "name": "integration_timestep_point",
                "value": 0.01,
                "unit": "s",
                "source": "computed:tenth_of_the_save_interval",
                "formula": "save_interval_point / 10",
                "inputs": ["save_interval_point"],
                "note": (
                    "a decade below the save interval so a saved frame never falls between "
                    "steps. Three decades under A1's ceiling, which for this configuration is "
                    "D_R*dt <= 0.01 and nothing else -- there is no length in the free model "
                    "for a displacement-per-step bound to compare against"
                ),
            },
            {
                "name": "box_length_point",
                "value": 3000,
                "unit": "um",
                "source": "computed:ten_persistence_lengths",
                "formula": "10 * persistence_length_expected",
                "inputs": ["persistence_length_expected"],
                "note": (
                    "NOT A BOUND AND THE CARD SAYS SO. A3 abstains because nothing couples a "
                    "free particle to its periodic image, so no axis constrains the box; the "
                    "engine needs one and this is it. Ten persistence lengths keeps the "
                    "wrapping sparse for a reader looking at raw coordinates, and the "
                    "estimator reads unwrapped positions regardless"
                ),
            },
            {
                "name": "particle_steps_point",
                "value": 400000000,
                "unit": "1",
                "source": "computed:particles_times_steps",
                "formula": "n_particles * total_simulated_time_point / integration_timestep_point",
                "inputs": ["n_particles", "total_simulated_time_point", "integration_timestep_point"],
                "note": (
                    "a hundred particles over four million steps. Declared dimensionless "
                    "because it is what the budget divides by a rate, and an amount divided "
                    "by a rate is not a time -- the same convention the interacting active "
                    "question uses for its per-arm counts"
                ),
            },
            {
                "name": "coordinates_stored_point",
                "value": 80000000,
                "unit": "1",
                "source": "computed:particles_times_frames_times_dimensions",
                "formula": "n_particles * total_simulated_time_point / save_interval_point * 2",
                "inputs": ["n_particles", "total_simulated_time_point", "save_interval_point"],
                "note": (
                    "four hundred thousand frames of a hundred particles at TWO coordinates "
                    "each, because this configuration is two-dimensional; the same run in "
                    "three would be half as much again. An order under A5's own ceiling"
                ),
            },
            {
                "name": "max_lag_time_point",
                "value": 3000,
                "unit": "s",
                "source": "computed:a4_window_floor",
                "formula": "1 * max_lag_time_min",
                "inputs": ["max_lag_time_min"],
                "note": (
                    "at A4's floor, thirty persistence times. Taking more window would push "
                    "the record longer still through A2's ratio without buying a regime the "
                    "run does not already cover"
                ),
            },
        ],
        "ratio": {
            "name": "lag_to_record_ratio",
            "value": 0.08,
            "unit": "1",
            "formula": "max_lag_time_point / total_simulated_time_point",
            "inputs": ["max_lag_time_point", "total_simulated_time_point"],
            "note": (
                "the window as a share of the record, under A2's 0.1. This is the number "
                "that made the record four times A2's floor rather than equal to it. 3000/40000 "
                "is 0.075 and one significant figure is 0.08, which is what explore mode allows "
                "a value whose inputs carry one figure each -- writing 0.075 claimed a precision "
                "neither input has"
            ),
        },
        "point": [
            ("integration_timestep", "integration_timestep_point"),
            ("total_simulated_time", "total_simulated_time_point"),
            ("save_interval", "save_interval_point"),
            ("box_length", "box_length_point"),
            ("max_lag_time", "max_lag_time_point"),
            ("n_particles", "n_particles"),
            ("self_propulsion_speed", "self_propulsion_speed"),
            ("rotational_diffusivity", "rotational_diffusivity"),
        ],
        "rejected": [
            {
                "what": "a save interval fine enough to resolve the thermal regime",
                "kind": "operating_point",
                "reason": (
                    "the MSD has THREE regimes and this plan resolves two of them. Below "
                    "tau_1 = D_T/v0^2 the translational noise beats the propulsion and the "
                    "slope returns to 1; seeing that needs a save interval a decade under "
                    "tau_1, which at this record length is 4e9 stored coordinates against "
                    "A5's ceiling of 1e9. The window is bounded here and not resolved, and "
                    "the short-lag end is a second plan rather than a finer version of this one"
                ),
                "grounds": ["thermal_crossover_time", "save_interval_point", "storage_estimate"],
            },
            {
                "what": "the integration timestep at A1's ceiling",
                "kind": "operating_point",
                "reason": (
                    "A1 allows a step three decades coarser, because for a free active "
                    "particle the only discretisation error is holding the orientation fixed "
                    "across a step. A saved frame would then fall between steps, so the step "
                    "follows the save interval instead"
                ),
                "grounds": ["integration_timestep_max", "save_interval_point"],
            },
            {
                "what": "the record at A2's own floor of a hundred persistence times",
                "kind": "operating_point",
                "reason": (
                    "A2's floor and A4's window floor cannot both be met at that record: "
                    "3000 s of window in 10000 s of record is a ratio of 0.3 against A2's "
                    "own ceiling of 0.1. Two axes that never see each other conflict, and S4 "
                    "resolves it by lengthening the record rather than shortening the window"
                ),
                "grounds": ["total_simulated_time_min", "max_lag_time_min", "lag_to_record_ratio_max"],
            },
        ],
    }


# --- S5: the plan ------------------------------------------------------- #

MODEL = (
    "a free active Brownian particle in two dimensions: one orientation diffusing at "
    "D_R, self-propulsion at a fixed speed v0 along it, translational noise D_T, no "
    "pair interaction, no wall, no obstacle, periodic in both directions with "
    "unwrapped coordinates"
)


def build_plan(qid: str, created_at: str, revision: int = 1) -> dict:
    """The plan card for `abp_free`.

    Written here rather than in `plan_card.build` because almost every line of
    that function is `bd_overdamped`'s: it carries `tau_d` and `diffusivity`,
    reads three `axis_bd_overdamped_*` files, and stops the run on a step
    displacement exceeding `box_length_min_dilution`. None of those exist for
    a free active particle.
    """
    import json

    from . import plan_card

    goal = cards.load_goal(qid, revision)
    syn = json.loads((cards.question_dir(qid) / cards.artifact_name(
        "synthesis.json", revision)).read_text())
    config = syn["chosen_config"]
    point = {p["parameter"]: p["number"] for p in syn["operating_point"]}

    extra = [
        "temperature", "viscosity", "bead_diameter",
        "translational_diffusivity", "persistence_time_expected",
        "thermal_crossover_time", "peclet_thermal",
        "lag_to_record_ratio", "lag_to_record_ratio_max",
        # The grounds every rejection points at, so `alternatives_rejected`
        # resolves against numbers this card holds rather than names only the
        # synthesis remembers.
        "integration_timestep_max", "total_simulated_time_min",
        "max_lag_time_min", "fit_lag_range_lower_bound_min",
        # The two dimensionless counts S4 computed, and the rate the wall
        # clock divides by: the estimates below are arithmetic over these and
        # a formula whose inputs the card does not hold resolves to nothing.
        "particle_steps_point", "coordinates_stored_point", "particle_step_rate",
        "particle_steps_max", "coordinates_stored_max",
    ]
    wanted = [("synthesis.json", n) for n in dict.fromkeys(point.values())]
    wanted += [("synthesis.json", n) for n in extra]
    wanted += [("axis_abp_free_a2.json", "target_relative_error")]
    wanted += [("axis_abp_free_a5.json", "bytes_per_coordinate")]

    wanted = [(cards.artifact_name(f, revision), n) for f, n in wanted]
    numbers = synthesis.carry_from(qid, config, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)

    # THE COST ESTIMATES ARE S5's AND NOT S4's OR A5's, and which stage owns
    # them is not a filing question. S4 may not introduce a number (4.5.4),
    # and A5 cannot see the operating point (4.5.3 rule b) -- an estimate
    # written there would be a guess about a point that axis does not know,
    # and the gate would then read it as inside on a number that was never
    # about this run. The seat holding the interacting active question
    # measured that exact failure today: an assumed rate said inside and the
    # measured rate said 2.6 h. Here the estimate is arithmetic over the
    # chosen point, and the rate underneath it is still A5's guess.
    grades = {n["name"]: n["grade"] for n in numbers}
    value = lambda name: next(float(n["value"]) for n in numbers if n["name"] == name)

    wall_s = value("particle_steps_point") / value("particle_step_rate")
    numbers.append(cards.num(
        # IN SECONDS, and the unit is forced by the two checks together:
        # one rounds in SI to a single figure and the other wants a single
        # figure in the card's own unit. 40 s satisfies both; the same value
        # is 0.667 min and 0.0111 h, and neither is one figure. The envelope
        # check converts to SI before comparing, so the unit costs nothing.
        "wall_clock_estimate", float(f"{wall_s:.1g}"), "s", "computed:particle_steps_over_rate",
        formula="particle_steps_point / particle_step_rate",
        inputs=[(n, grades[n]) for n in ("particle_steps_point", "particle_step_rate")],
        precision="order_of_magnitude",
        note=(
            "the rate underneath is A5's "
            "assumption and this configuration has never been timed, so the run's own log is "
            "what replaces it"
        ),
    ))
    store = value("coordinates_stored_point") * value("bytes_per_coordinate")
    numbers.append(cards.num(
        "storage_estimate", float(f"{store:.1g}"), "GB", "computed:coordinates_times_bytes",
        formula="coordinates_stored_point * bytes_per_coordinate",
        inputs=[(n, grades[n]) for n in ("coordinates_stored_point", "bytes_per_coordinate")],
        precision="order_of_magnitude",
        note="eighty million coordinates in double precision, compared against the storage ceiling",
    ))

    conditions = [{"parameter": p, "number": n} for p, n in point.items()]
    conditions += [
        {"parameter": "temperature", "number": "temperature"},
        {"parameter": "viscosity", "number": "viscosity"},
        {"parameter": "bead_diameter", "number": "bead_diameter"},
        # The window the observable is read over. `effective_translational_
        # diffusivity` is window_required with a LOWER bound, the opposite way
        # round from `tracer_diffusivity`, so the plan carries both ends.
        {"parameter": "fit_lag_range_lower_bound", "number": "fit_lag_range_lower_bound_min"},
    ]

    card = cards.head(
        "plan",
        f"plan-{qid}" + ("" if revision == 1 else f"-r{revision}"),
        qid,
        created_at,
        revision=revision,
        goal_id=goal["id"],
        synthesis_id=syn["id"],
        purpose=goal["purpose"],
        intent=goal["intent"],
        observable=cards.observable(goal["observable"]["name"]),
        system_configuration={
            "config": config,
            "optical_path": None,
            "devices": ["hoomd_backend"],
            "model": MODEL,
        },
        targets=[dict(t) for t in goal.get("targets", [])],
        conditions=conditions,
        actions=[
            {
                "id": "integrate",
                "device": "hoomd_backend",
                "action": (
                    "integrate the declared configuration for the planned duration, saving "
                    "frames at the planned interval"
                ),
                "reversible": True,
                "parameters": [c["parameter"] for c in conditions],
                "tier": 1,
            },
            {
                "id": "estimate_msd",
                "device": "hoomd_backend",
                "action": (
                    "compute the mean squared displacement on a logarithmic lag grid from "
                    "unwrapped positions, averaging over particles and over time origins, and "
                    "report its log-log slope and the effective diffusivity read above the "
                    "declared lower bound of the fit range"
                ),
                "reversible": True,
                "parameters": ["max_lag_time", "fit_lag_range_lower_bound", "n_particles"],
                "tier": 0,
            },
        ],
        envelope_check=plan_card.envelope_check(numbers),
        cost={
            "wall_clock": (
                "four thousand million particle-steps, no pair interactions and no neighbour "
                "list; measured at about twenty thousand steps a second on this machine, so "
                "roughly half an hour"
            ),
            "numbers": ["wall_clock_estimate", "storage_estimate"],
            "note": (
                "A5's own estimate rests on a particle-step rate that has never been measured "
                "for this configuration. The rate quoted here was measured on an earlier "
                "unplanned run of the same model and is carried as prose rather than as a "
                "number, because a measurement from a run this plan does not cite is not this "
                "plan's evidence"
            ),
        },
        stop_criteria=[
            {
                "id": "planned_duration_reached",
                "metric": "simulated_time",
                "comparator": ">=",
                "number": "total_simulated_time_point",
                "on_met": "complete",
                "statement": (
                    "stop when the run reaches the planned duration; running longer would be a "
                    "different plan"
                ),
            },
            {
                "id": "step_displacement_diverged",
                "metric": "max_single_step_displacement",
                "comparator": ">",
                "number": "box_length_point",
                "on_met": "fault",
                "statement": (
                    "a particle moving more than the box in one step is a diverged "
                    "integration; stop and keep the run, because divergence is a result. The "
                    "box bounds nothing physical here -- A3 abstains -- so this is a "
                    "divergence guard and not an image bound"
                ),
            },
        ],
        success_criteria=[
            {
                "id": "ballistic_regime_present",
                "metric": "maximum_log_log_slope_of_msd",
                "comparator": ">=",
                "target": "msd_loglog_slope",
                "window": "lags between the thermal crossover and the persistence time",
                "statement": (
                    "the maximum log-log slope reaches at least 1.9. It cannot reach 2: the "
                    "limit is a function of v0^2/((d-1) D_R D_T) alone and is 1.98 at this "
                    "operating point, so a run below 1.9 means the sweep does not reach the "
                    "regime it was chosen to reach. This is the falsifier of a_peclet_point"
                ),
            },
            {
                "id": "long_time_diffusive",
                "metric": "log_log_slope_at_the_longest_lag",
                "comparator": "<=",
                "target": "msd_loglog_slope",
                "window": "lags above the declared lower bound of the fit range",
                "statement": (
                    "the slope returns to 1 within a tenth at the longest lags, which is what "
                    "says the plateau was entered rather than approached. If it has not, the "
                    "effective diffusivity read from this record is a lower bound and not a "
                    "value"
                ),
            },
            {
                "id": "statistics_met",
                "metric": "relative_standard_error_of_effective_diffusivity",
                "comparator": "<=",
                "number": "target_relative_error",
                "window": "lags above the declared lower bound of the fit range",
                "statement": (
                    "the spread on the effective diffusivity is inside A2's target, read from "
                    "a block resample rather than from the fit's own standard error"
                ),
            },
        ],
        alternatives_rejected=[
            {"what": r["what"], "reason": r["reason"], "grounds": r["grounds"]}
            for r in syn.get("rejected", [])
        ],
        open_risks=[
            "This run measures no dependence, and the capability table says so: the mean "
            "squared displacement of a non-interacting active Brownian particle is a closed "
            "form in v0, D_R and D_T, so the run confirms the integrator, the estimator and "
            "the crossover machinery and cannot be cited as evidence about the dependence "
            "itself. Interaction or confinement would change that.",
            "The plan resolves two of the three regimes. Below the thermal crossover the "
            "translational noise beats the propulsion and the slope returns to 1; the save "
            "interval sits AT that crossover, so the run bounds that regime and does not "
            "resolve it. A finer save interval at this record length exceeds A5's storage "
            "ceiling by a factor of four, which is why it is a second plan.",
            "The rotational diffusivity is a chosen value and not a measured one. The store "
            "holds no rotational diffusivity for this tracer; the value used is the "
            "Stokes-Einstein-Debye figure for a sphere of the measured diameter, so it is a "
            "prediction from the same relation that produced the translational diffusivity, "
            "not an independent input.",
            "The temperature is a coordinate of this model and not a measurement of it. The "
            "integrator represents no velocity, so there is nothing to thermostat and the "
            "declared value enters as a noise amplitude. Citing the laboratory reading "
            "records why the number was chosen; it is not evidence about the model.",
            "Nothing here is fitted to experimental data and no experimental counterpart "
            "exists. The observables this plan produces are declared producible by simulation "
            "only, so there is no bridge round to compare against and comparability is not "
            "claimed.",
        ],
    )
    card["status"] = "DRAFT"
    card.update(cards.tail(
        numbers,
        assumptions=assumptions,
        kb_refs=synthesis.kb_refs_for(qid, numbers),
        kb_gaps=synthesis.kb_gaps_for(qid),
        degraded=["librarian_agent"],
    ))
    return card


def render_plan(card: dict) -> str:
    """The plan in Markdown, generated from the card (P3).

    `plan_card.render` cannot be reused: it prints the window against `tau_d`,
    which this configuration does not have. Every figure below is read out of
    the card rather than written, so the prose cannot drift from the record.
    """
    nums = {n["name"]: n for n in card["numbers"]}

    def q(name: str) -> str:
        n = nums[name]
        return f"{n['value']} {n['unit']}"

    cond = {c["parameter"]: c["number"] for c in card["conditions"]}
    lines = [
        f"# {card['id']} — {card['observable']['name']} for a free active particle",
        "",
        "*Generated from the JSON card beside this file. If the two disagree the JSON wins.*",
        "",
        f"**Status** {card['status']}  ·  **Configuration** {card['system_configuration']['config']}"
        f"  ·  **Engine** {card['system_configuration']['devices'][0]}",
        "",
        "## The model",
        "",
        card["system_configuration"]["model"],
        "",
        "## The operating point",
        "",
        "| parameter | value |",
        "|---|---|",
    ]
    for parameter, number in cond.items():
        if number in nums:
            lines.append(f"| `{parameter}` | {q(number)} |")
    lines += [
        "",
        "## The three scales this run sits between",
        "",
        f"- the early crossover, where thermal motion gives way to propulsion: {q('thermal_crossover_time')}",
        f"- the persistence time, where propulsion gives way to effective diffusion: {q('persistence_time_expected')}",
        f"- the window the long-time answer is read over: from {q('fit_lag_range_lower_bound_min')} "
        f"to {q('max_lag_time_point')}, a share {q('lag_to_record_ratio')} of the record",
        "",
        "## What would make this run a failure",
        "",
    ]
    for c in card["success_criteria"]:
        lines.append(f"- **{c['id']}** — {c['statement']}")
    lines += ["", "## What was considered and dropped", ""]
    for r in card["alternatives_rejected"]:
        lines.append(f"- **{r['what']}** — {r['reason']}")
    lines += ["", "## What this run cannot settle", ""]
    for r in card["open_risks"]:
        lines.append(f"- {r}")
    return "\n".join(lines) + "\n"

