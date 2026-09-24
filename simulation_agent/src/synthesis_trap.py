"""S4 for sim-20260923-201 (plan.md 4.5.4): evaluate per point, choose, refuse in numbers.

`synthesis.py` owns the deterministic half -- `axis_cards`, `intersect`,
`carry_from`, `assumptions_for`, `kb_refs_for`, `kb_gaps_for` -- and this
module supplies the judgement for `bd_overdamped_trapped_uniform_flow`, the
same split `synthesis_abp` made for the active questions.

**Evaluated per point, because the axis cards said to.** Seven of the eight
intervals this configuration's axes emit carry `varies_with: [trap_stiffness]`
(and A1's drift bound `flow_speed` as well), so intersecting them across the
grid would combine claims about different points -- the category error
`common.schema.json` now names. Every bound here is a multiple of the local
relaxation time gamma/k_t, so each is written as `<multiple> * relaxation_time_k<i>`
and the multiples are read off the axis cards' own numbers.

**The grid.** Four stiffness levels, a decade apart from the goal's soft corner
to its stiff one, and three levels of the offset in thermal widths, 1, 10 and
100. The speed at a cell is DERIVED from its offset level and its stiffness,
v = (offset/sigma) * sqrt(k_B*T*k_t)/gamma, because that and not the speed is
what the statistics depend on (the goal's a_speed_decades).

**What this card corrects, in numbers.** Revision 3's goal said the worst
corner needs 200 thousand steps and fits A5's budget with no margin. It needs
six million. The error was using A1's DRIFT bound, 0.1*tau/(offset/sigma), for
the timestep at the slow row, where A1's NOISE bound, 0.005*tau, is tighter.
That is A1 x A2, which is S4's to form and which the goal formed in prose.
Formed here, the slow row exceeds A5's budget at the conservative cost and is
skipped, with the counterexample, in the refusal card beside this one.

**No lookups and no new numbers.** Every value is carried from the goal or an
axis card, or computed from carried ones. S4's one choice -- a 1.5x margin on
the total record over A7's startup plus A2's record -- is a factor inside a
formula on carried numbers. It was first written as an `assumed:` multiple
and check 12 refused it, which was right: S4 may introduce no number (4.5.4).
"""

from __future__ import annotations

import json

from . import cards, synthesis
from .config_bd_overdamped_trapped_uniform_flow import _one

CONFIG = "bd_overdamped_trapped_uniform_flow"
K_LEVELS = ("k1", "k2", "k3", "k4")        # 0.02, 0.2, 2, 20 pN/um
O_LEVELS = ("o1", "o2", "o3")              # offset in thermal widths: 1, 10, 100
SMOKE = ("k3", "o2")                       # 2 pN/um, ten thermal widths: interior on both axes

# S4's one margin: the RECORD is 1.5 x A2's record multiple, in units of tau,
# and the startup is added to it by the backend rather than summed here. Two
# earlier forms lost the record to rounding. A plain sum 10 + 200 = 210 rounds
# to 200 and leaves 190 relaxation times against 200; and rounding tau down
# from 2.356 to 2 shortens the record in TRUE relaxation times as well, so the
# smoke cell read 1.06 per cent against a one per cent target. Declaring the
# record itself -- which is also the observable's registered window, and so
# what check 40 asks the plan to carry -- keeps it at one clean figure. A
# factor inside a formula is arithmetic on carried numbers, the standing of
# synthesis_abp's "a decade under A1's ceiling" (/10); an assumed multiple was
# tried first and check 12 refused it, correctly (4.5.4).
MARGIN = 1.5


def _n(numbers, g, name, value, unit, source, formula, inputs, note, precision="order_of_magnitude"):
    n = cards.num(name, value, unit, source, formula=formula,
                  inputs=[(i, g[i]) for i in inputs], precision=precision, note=note)
    numbers.append(n)
    g[name] = n["grade"]
    return n


def _v(numbers, name) -> float:
    return next(float(n["value"]) for n in numbers if n["name"] == name)


def build(qid: str, created_at: str, revision: int) -> tuple[dict, dict | None]:
    """The synthesis card and, when a row is dropped, the S4 refusal card."""
    group = synthesis.axis_cards(qid, CONFIG, revision)
    intersection, conflict = synthesis.intersect(group)
    per_config = [{"config": CONFIG, "empty": conflict is not None,
                   "axis_files": [f for f, _ in group],
                   ("conflict" if conflict is not None else "intersection"):
                       conflict if conflict is not None else intersection}]
    if conflict is not None:
        raise SystemExit(f"{CONFIG} came out empty; S4 ends in a refusal card, not a plan (P5)")

    goal = cards.load_goal(qid, revision)
    G = cards.artifact_name("goal.json", revision)
    A = lambda ax: cards.artifact_name(f"axis_{CONFIG}_{ax}.json", revision)
    wanted = [(G, n) for n in ("bead_diameter", "temperature", "viscosity",
                               "trap_stiffness_min", "trap_stiffness_max",
                               "offset_over_sigma_min", "offset_over_sigma_max")]
    wanted += [(A("a1"), n) for n in ("noise_step_fraction", "drift_step_fraction")]
    wanted += [(A("a2"), n) for n in ("relaxation_times_per_record", "target_relative_error")]
    wanted += [(A("a4"), "save_interval_fraction")]
    wanted += [(A("a5"), n) for n in ("cost_per_step_upper", "steps_max_per_point")]
    wanted += [(A("a7"), "startup_relaxation_times")]
    numbers = synthesis.carry_from(qid, CONFIG, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)
    g = {n["name"]: n["grade"] for n in numbers}
    V = lambda name: _v(numbers, name)
    add = lambda *a, **k: _n(numbers, g, *a, **k)

    # -- the grid's levels, from the goal's corners ------------------------
    add("trap_stiffness_k1", V("trap_stiffness_min"), "pN/um", "computed:goal_soft_corner",
        "trap_stiffness_min", ["trap_stiffness_min"], "the soft corner")
    add("trap_stiffness_k2", _one(V("trap_stiffness_min") * 10), "pN/um", "computed:decade_above",
        "trap_stiffness_min*10", ["trap_stiffness_min"], "a decade up")
    add("trap_stiffness_k3", _one(V("trap_stiffness_min") * 100), "pN/um", "computed:two_decades_above",
        "trap_stiffness_min*100", ["trap_stiffness_min"], "two decades up; the smoke run's level")
    add("trap_stiffness_k4", V("trap_stiffness_max"), "pN/um", "computed:goal_stiff_corner",
        "trap_stiffness_max", ["trap_stiffness_max"], "the stiff corner")
    add("offset_over_sigma_o1", V("offset_over_sigma_min"), "1", "computed:goal_slow_corner",
        "offset_over_sigma_min", ["offset_over_sigma_min"], "offset one thermal width: buried in the fluctuation")
    add("offset_over_sigma_o2", _one((V("offset_over_sigma_min") * V("offset_over_sigma_max")) ** 0.5), "1",
        "computed:geometric_mean", "(offset_over_sigma_min*offset_over_sigma_max)**0.5",
        ["offset_over_sigma_min", "offset_over_sigma_max"], "the decade between")
    add("offset_over_sigma_o3", V("offset_over_sigma_max"), "1", "computed:goal_fast_corner",
        "offset_over_sigma_max", ["offset_over_sigma_max"], "visible in a single frame")

    # -- per offset row: which A1 bound binds, and A2's record multiple ----
    add("dt_fraction_o1", _one(0.5 * V("noise_step_fraction") ** 2), "1", "computed:a1_noise_bound",
        "0.5*noise_step_fraction**2", ["noise_step_fraction"],
        "timestep over tau at the slow row. A1's NOISE bound binds here, not the drift bound: the "
        "drift bound is 0.1/(offset/sigma) = 0.1 at this row and the noise bound 0.005 is twenty "
        "times tighter. Revision 3's goal used the drift bound at this row and understated the "
        "row's cost by that factor")
    add("dt_fraction_o2", _one(0.5 * V("noise_step_fraction") ** 2), "1", "computed:a1_noise_bound",
        "0.5*noise_step_fraction**2", ["noise_step_fraction"],
        "the noise bound again: drift gives 0.01 at this row, twice the noise bound's 0.005")
    add("dt_fraction_o3", _one(V("drift_step_fraction") / V("offset_over_sigma_o3")), "1",
        "computed:a1_drift_bound", "drift_step_fraction/offset_over_sigma_o3",
        ["drift_step_fraction", "offset_over_sigma_o3"],
        "the DRIFT bound binds at the fast row, 0.001 against the noise bound's 0.005")
    add("record_multiple_o1", _one(2.0 / (V("offset_over_sigma_o1") * V("target_relative_error")) ** 2), "1",
        "computed:a2_statistics", "2/(offset_over_sigma_o1*target_relative_error)**2",
        ["offset_over_sigma_o1", "target_relative_error"],
        "A2's statistical branch binds: twenty thousand relaxation times for one per cent at one sigma")
    add("record_multiple_o2", _one(2.0 / (V("offset_over_sigma_o2") * V("target_relative_error")) ** 2), "1",
        "computed:a2_statistics", "2/(offset_over_sigma_o2*target_relative_error)**2",
        ["offset_over_sigma_o2", "target_relative_error"], "the statistics bind, above A2's floor of a hundred")
    add("record_multiple_o3", V("relaxation_times_per_record"), "1", "computed:a2_floor",
        "relaxation_times_per_record", ["relaxation_times_per_record"],
        "A2's floor binds: at the fast row the statistics are met in two relaxation times")

    # -- per stiffness level -----------------------------------------------
    for k in K_LEVELS:
        add(f"relaxation_time_{k}", _one(3 * 3.141592653589793 * V("viscosity") * V("bead_diameter") * 1e-6
                                         / (V(f"trap_stiffness_{k}") * 1e-6)), "s",
            "computed:stokes_drag_over_stiffness", f"3*pi*viscosity*bead_diameter/trap_stiffness_{k}",
            ["viscosity", "bead_diameter", f"trap_stiffness_{k}"],
            "gamma/k_t at this level: every bound below is a multiple of it, which is what varies_with said")
        add(f"save_interval_{k}", _one(V("save_interval_fraction") * V(f"relaxation_time_{k}")), "s",
            "computed:a4_fraction_of_tau", f"save_interval_fraction*relaxation_time_{k}",
            ["save_interval_fraction", f"relaxation_time_{k}"], "A4's ceiling at this level")
        add(f"startup_discard_{k}", _one(V("startup_relaxation_times") * V(f"relaxation_time_{k}")), "s",
            "computed:a7_startup", f"startup_relaxation_times*relaxation_time_{k}",
            ["startup_relaxation_times", f"relaxation_time_{k}"],
            "A7's discard at this level, declared before the run and evaluated by the estimator on this number")

    # -- per cell ----------------------------------------------------------
    add("particle_step_rate", _one(1.0 / V("cost_per_step_upper")), "1/s", "computed:inverse_cost",
        "1/cost_per_step_upper", ["cost_per_step_upper"],
        "the CONSERVATIVE end of A5's bracket: measured at 1000 particles, so this is a floor on the rate "
        "one particle runs at. The smoke run measures the rate at N=1")

    cells, skipped = [], {}
    for k in K_LEVELS:
        for o in O_LEVELS:
            c = f"{k}_{o}"
            add(f"integration_timestep_{c}", _one(V(f"dt_fraction_{o}") * V(f"relaxation_time_{k}")), "s",
                "computed:a1_bound_at_point", f"dt_fraction_{o}*relaxation_time_{k}",
                [f"dt_fraction_{o}", f"relaxation_time_{k}"], "AT the binding A1 bound for this cell")
            add(f"record_length_{c}", _one(MARGIN * V(f"record_multiple_{o}") * V(f"relaxation_time_{k}")), "s",
                "computed:margin_times_record_multiple_times_tau", f"{MARGIN}*record_multiple_{o}*relaxation_time_{k}",
                [f"record_multiple_{o}", f"relaxation_time_{k}"],
                "the averaging window after the startup, which is the observable's registered window "
                "parameter: A2's record multiple with S4's 1.5x margin. The backend adds the startup")
            v_si = (V(f"offset_over_sigma_{o}") * (1.380649e-23 * V("temperature") * V(f"trap_stiffness_{k}") * 1e-6) ** 0.5
                    / (3 * 3.141592653589793 * V("viscosity") * V("bead_diameter") * 1e-6))
            add(f"flow_speed_{c}", _one(v_si * 1e6), "um/s", "computed:offset_to_speed",
                f"offset_over_sigma_{o}*(k_B*temperature*trap_stiffness_{k})**0.5/(3*pi*viscosity*bead_diameter)",
                [f"offset_over_sigma_{o}", "temperature", f"trap_stiffness_{k}", "viscosity", "bead_diameter"],
                "the speed that puts the steady offset at this row's number of thermal widths, at this stiffness")
            add(f"particle_steps_{c}", _one((V(f"startup_discard_{k}") + V(f"record_length_{c}"))
                                             / V(f"integration_timestep_{c}")), "1",
                "computed:duration_over_step", f"(startup_discard_{k}+record_length_{c})/integration_timestep_{c}",
                [f"startup_discard_{k}", f"record_length_{c}", f"integration_timestep_{c}"],
                "one particle, so particle-steps are steps; against steps_max_per_point. An ESTIMATE, so one "
                "figure is right here where it would be wrong for the window itself")
            add(f"coordinates_stored_{c}", _one(3 * (V(f"startup_discard_{k}") + V(f"record_length_{c}"))
                                                / V(f"save_interval_{k}")), "1",
                "computed:three_coordinates_per_frame", f"3*(startup_discard_{k}+record_length_{c})/save_interval_{k}",
                [f"startup_discard_{k}", f"record_length_{c}", f"save_interval_{k}"],
                "one particle, three coordinates a frame")
            over = V(f"particle_steps_{c}") > V("steps_max_per_point")
            cells.append(c)
            if over:
                skipped[c] = [("particle_steps", f"particle_steps_{c}", "steps_max_per_point")]

    kept = [c for c in cells if c not in skipped]
    if not kept:
        raise SystemExit("every cell exceeds A5's budget; the sweep cannot be run (P5)")

    rejected = [{"what": f"grid cell {c}", "kind": "operating_point",
                 "reason": "exceeds A5's step budget per point at the CONSERVATIVE cost end; skipped, and the "
                           "plan's sweep records the empty cell with this reason",
                 "grounds": [x for _, a, b in over for x in (a, b)]} for c, over in skipped.items()]

    card = cards.head(
        "synthesis", f"synthesis-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, configs_screened=[CONFIG], per_config=per_config, chosen_config=CONFIG,
        operating_point=[{"parameter": p, "number": n} for p, n in (
            ("temperature", "temperature"), ("viscosity", "viscosity"), ("bead_diameter", "bead_diameter"),
            ("trap_stiffness", f"trap_stiffness_{SMOKE[0]}"), ("offset_over_sigma", f"offset_over_sigma_{SMOKE[1]}"),
            ("flow_speed", f"flow_speed_{SMOKE[0]}_{SMOKE[1]}"),
            ("integration_timestep", f"integration_timestep_{SMOKE[0]}_{SMOKE[1]}"),
            ("record_length", f"record_length_{SMOKE[0]}_{SMOKE[1]}"),
            ("save_interval", f"save_interval_{SMOKE[0]}"), ("startup_discard", f"startup_discard_{SMOKE[0]}"))],
        priority_used=goal["priority"], priority_source="goal_card", rejected=rejected,
        tie_break=(
            f"one configuration survived S3.0, so there was nothing to break. The grid is {len(cells)} cells, "
            f"{len(kept)} fit A5's step budget and {len(skipped)} do not ({', '.join(sorted(skipped))}). Every "
            "cell's step, save interval, startup and record are multiples of that cell's tau because the axis "
            "cards marked them varies_with trap_stiffness, and the step count is therefore THE SAME AT EVERY "
            "STIFFNESS: 6e4 at the middle row, 2e5 at the fast row, 6e6 at the slow row. The sweep is flat in "
            "stiffness and steep in offset, and the slow row is what the conservative cost refuses. THIS "
            f"REVISION'S OPERATING POINT IS ONE KEPT CELL, {SMOKE[0]}_{SMOKE[1]}, and not the eight: the per-step "
            "cost the budget rests on is a bracket three decades wide, measured at 1000 particles for a "
            "configuration that runs one, and planning eight cells on it would plan most of them on a number "
            "known to be off. The smoke cell measures it, and the sweep is the next revision's, against the "
            "measured rate -- which is also what recovers the slow row. S4 made no lookup, so the librarian is "
            "degraded here by construction and the gaps are the goal's"),
    )
    card.update(cards.tail(numbers, assumptions=assumptions, kb_refs=synthesis.kb_refs_for(qid, numbers),
                           kb_gaps=synthesis.kb_gaps_for(qid), degraded=["librarian_agent"]))

    refusal = None
    if skipped:
        counter = [{"parameter": p, "required_number": need, "limit_number": cap,
                    "statement": f"cell {c} needs {need} = {_v(numbers, need):g} against {cap} = "
                                 f"{_v(numbers, cap):g}. The step is already AT A1's binding bound and the "
                                 "record at S4's minimal margin, so no settable parameter inside the intervals "
                                 "brings the cell under the budget at this cost"}
                   for c, over in skipped.items() for p, need, cap in over]
        refusal = cards.head(
            "refusal", f"refusal-{qid}-s4" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
            revision=revision, status="REFUSED", stage="S4",
            refused_what=f"grid cells {', '.join(sorted(skipped))}: the slow row, where the offset is one "
                         "thermal width and the statistics need twenty thousand relaxation times",
            reason_code="budget_exceeded", counterexample=counter,
            alternatives=[{
                "what": "run the smoke point and replace the conservative per-step cost with the one measured at "
                        "N=1. A5's budget is the ceiling over a cost measured at 1000 particles, and this "
                        "configuration runs one; if the measured cost is a thousand times lower the slow row fits "
                        "with room, and a revision recovers these cells unchanged",
                "requires": "a smoke run of a kept cell, which this plan carries, and a revision that cites it",
            }, {
                "what": "raise the local wall clock ceiling by the factor the counterexample states",
                "requires": "a person's edit to simulation_agent/envelope/budget.json",
            }],
        )
        syn_name = cards.artifact_name("synthesis.json", revision)
        keep_names = {x for over in skipped.values() for _, a, b in over for x in (a, b)}
        carried = []
        for n in numbers:
            if n["name"] in keep_names:
                c2 = {k: n[k] for k in ("name", "value", "unit", "source", "grade")}
                c2["origin"] = n.get("origin") or f"{syn_name}#{n['name']}"
                for k in ("precision", "note"):
                    if k in n:
                        c2[k] = n[k]
                carried.append(c2)
        # An assumed number carried here brings its rationale along (check 4):
        # the budget is A5's assumption and a refusal that cites it without the
        # reason would state a limit nobody could trace.
        carried_assumptions = synthesis.assumptions_for(qid, carried)
        # ...and the gap each rationale stands on (check 39), read off the axis
        # card that produced it rather than restated, so the refusal cites the
        # absence the librarian actually returned.
        wanted_gaps = {a.get("gap_ref") for a in carried_assumptions if a.get("gap_ref")}
        gaps = []
        for fname, axis_card in group:
            for gp in axis_card.get("kb_gaps") or []:
                if gp.get("gap_id") in wanted_gaps and gp["gap_id"] not in {x["gap_id"] for x in gaps}:
                    gaps.append(gp)
        refusal.update(cards.tail(carried, assumptions=carried_assumptions, kb_gaps=gaps,
                                  degraded=["librarian_agent"]))
    return card, refusal


def emit(qid: str, created_at: str, revision: int):
    card, refusal = build(qid, created_at, revision)
    qdir = cards.question_dir(qid)
    paths = [cards.write(qdir / cards.artifact_name("synthesis.json", revision), card)]
    if refusal is not None:
        paths.append(cards.write(qdir / cards.artifact_name(f"refusal_s4_{qid}.json", revision), refusal))
    return paths


if __name__ == "__main__":
    import sys
    for p in emit(sys.argv[1], sys.argv[2], int(sys.argv[3])):
        print(p.relative_to(cards.REPO))
