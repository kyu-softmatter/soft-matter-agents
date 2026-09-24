"""S5 for sim-20260923-201: the smoke cell of the drag calibration, as a plan and its Markdown twin.

`plan_card.py` is `bd_overdamped`'s and `plan_abp.py` the active questions'.
This module assembles the plan for `bd_overdamped_trapped_uniform_flow` from
`v<N>_synthesis.json` the same way: every number carried with an `origin`,
criteria declared before the run, the envelope check run rather than written,
the Markdown generated from the JSON (P3), and the status promoted from DRAFT
only by the validator's exit code (P4).

**One cell, not the grid.** S4 evaluated all twelve cells per point and kept
eight, and then chose ONE as this revision's operating point: `k3_o2`, two
piconewtons per micrometre at ten thermal widths, interior on both axes. The
per-step cost every budget here rests on is a bracket three decades wide,
measured at 1000 particles for a configuration that runs one, so planning
eight cells on it plans most of them on a number known to be off. This cell
measures it. At the CONSERVATIVE cost its 6e4 steps take 200 s against the
300 s smoke budget, so the gate passes on the pessimistic estimate and not on
the optimistic one. The sweep is the next revision's.

**It had to be one cell for a second reason, found by running the sweep.**
Check 40 requires a window-dependent observable's window as a plan condition,
and it reads only the plan's top-level `conditions`. This observable's window,
`record_length`, is a multiple of the local relaxation time, so it differs at
every point of the sweep -- which `varies_with` permits and the sweep schema's
invariant allows -- and a per-point window has nowhere check 40 will look.
A one-cell plan carries it at the top level. Raised to manager-simulation.

**The window is declared and the duration derived.** The plan carries
`record_length` and `startup_discard`, and the backend integrates their sum.
Summed here and rounded to one figure, 0.2 + 6 = 6.2 becomes 6, and the
startup silently comes out of the record.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import cards, plan_card, synthesis
from .config_bd_overdamped_trapped_uniform_flow import _one
from .synthesis_trap import CONFIG, SMOKE

MODEL = ("one overdamped sphere, a harmonic external potential of stiffness k_t centred at the origin, "
         "and a uniform background fluid velocity along +x; Euler-Maruyama in SI, no pair interaction, "
         "no wall")


def build(qid: str, created_at: str, revision: int) -> dict:
    goal = cards.load_goal(qid, revision)
    S = cards.artifact_name("synthesis.json", revision)
    syn = __import__("json").loads((cards.question_dir(qid) / S).read_text())
    A3 = cards.artifact_name(f"axis_{CONFIG}_a3.json", revision)
    k, o = SMOKE
    c = f"{k}_{o}"

    wanted = [(S, n) for n in (
        "temperature", "viscosity", "bead_diameter", "target_relative_error", "particle_step_rate",
        "steps_max_per_point", f"trap_stiffness_{k}", f"offset_over_sigma_{o}", f"relaxation_time_{k}",
        f"save_interval_{k}", f"startup_discard_{k}", f"flow_speed_{c}", f"integration_timestep_{c}",
        f"record_length_{c}", f"particle_steps_{c}", f"coordinates_stored_{c}")] + [(A3, "box_edge_min")]
    numbers = synthesis.carry_from(qid, CONFIG, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)
    g = {n["name"]: n["grade"] for n in numbers}
    V = lambda name: next(float(n["value"]) for n in numbers if n["name"] == name)

    # A format constant of the trajectory writer, not knowledge about the world.
    # It enters here and not in S4 because check 12 lets S4 introduce no number,
    # and S4 never needed it: storage is the plan's comparison against the ceiling.
    numbers.append(cards.num("bytes_per_coordinate", 4e-09, "GB", "spec:ieee754_single",
                             precision="significant_figures",
                             note="float32, the trajectory writer's dtype (013); the free-diffusion plans "
                                  "carried float64's 8e-9"))
    g["bytes_per_coordinate"] = "E3"
    numbers.append(cards.num(
        "wall_clock_estimate", _one(V(f"particle_steps_{c}") / V("particle_step_rate")), "s",
        "computed:particle_steps_over_rate", formula=f"particle_steps_{c}/particle_step_rate",
        inputs=[(f"particle_steps_{c}", g[f"particle_steps_{c}"]), ("particle_step_rate", g["particle_step_rate"])],
        precision="order_of_magnitude",
        note="one seed at the CONSERVATIVE rate; compared against the smoke budget's wall clock. The run's "
             "own cost block replaces the rate with a measured one"))
    numbers.append(cards.num(
        "storage_estimate", _one(V(f"coordinates_stored_{c}") * V("bytes_per_coordinate")), "GB",
        "computed:coordinates_times_bytes", formula=f"coordinates_stored_{c}*bytes_per_coordinate",
        inputs=[(f"coordinates_stored_{c}", g[f"coordinates_stored_{c}"]), ("bytes_per_coordinate", "E3")],
        precision="order_of_magnitude", note="the trajectory in single precision"))

    cond = lambda p, n: {"parameter": p, "number": n}
    conditions = [
        cond("temperature", "temperature"), cond("viscosity", "viscosity"),
        cond("bead_diameter", "bead_diameter"), cond("box_length", "box_edge_min"),
        cond("trap_stiffness", f"trap_stiffness_{k}"), cond("offset_over_sigma", f"offset_over_sigma_{o}"),
        cond("flow_speed", f"flow_speed_{c}"), cond("integration_timestep", f"integration_timestep_{c}"),
        cond("save_interval", f"save_interval_{k}"), cond("startup_discard", f"startup_discard_{k}"),
        cond("record_length", f"record_length_{c}"),
    ]

    card = cards.head(
        "plan", f"plan-{qid}" + ("" if revision == 1 else f"-r{revision}"), qid, created_at,
        revision=revision, goal_id=goal["id"], synthesis_id=syn["id"],
        purpose=goal["purpose"], intent=goal["intent"],
        observable=cards.observable(goal["observable"]["name"]),
        system_configuration={"config": CONFIG, "optical_path": None, "devices": ["trap_backend"], "model": MODEL},
        targets=[dict(t) for t in goal.get("targets", [])],
        conditions=conditions,
        actions=[
            {"id": "integrate", "device": "trap_backend",
             "action": "integrate one sphere from the trap centre with the flow on, for startup_discard plus "
                       "record_length, saving its unwrapped position at save_interval",
             "reversible": True, "parameters": [x["parameter"] for x in conditions], "tier": 1},
            {"id": "estimate", "device": "trap_backend",
             "action": "after startup_discard: the mean along-flow displacement from the DECLARED trap centre, "
                       "with a block standard error over blocks of ten declared relaxation times and the OU "
                       "prediction beside it; the stiffness recovered through the drag and, separately, through "
                       "equipartition; the along-flow relaxation time; the transverse means; the cost per step",
             "reversible": True, "parameters": ["startup_discard", "record_length", "save_interval"], "tier": 0},
        ],
        envelope_check=plan_card.envelope_check(numbers),
        cost={"wall_clock": "about three minutes at the conservative rate; the smoke budget is five",
              "numbers": ["wall_clock_estimate", "storage_estimate"],
              "note": "at the conservative end of A5's bracket, measured at 1000 particles. This run measures "
                      "the rate at N=1, which is its second purpose"},
        # NO COMPLETION MONITOR. The planned end is startup_discard plus
        # record_length, both CONDITIONS; the backend derives their sum,
        # integrates exactly that many integer steps and reports COMPLETE, and
        # the operator records it on its terminal-state path with stopped_early
        # false. A `simulated_time >=` monitor would need the sum as a number,
        # and one significant figure of 0.2 + 6 is 6 -- a monitor that fired
        # 0.2 s early and cut the record it exists to protect.
        stop_criteria=[
            {"id": "step_displacement_diverged", "metric": "max_single_step_displacement", "comparator": ">",
             "number": "bead_diameter", "on_met": "fault",
             "statement": "a sphere moving more than its own diameter in one step means the drift term has run "
                          "away and Euler-Maruyama has diverged. Stop and keep the run: divergence is a result"},
        ],
        success_criteria=[
            {"id": "statistics_met", "metric": "relative_block_standard_error_of_drag_offset", "comparator": "<=",
             "target": "trap_stiffness", "window": "record_length, after startup_discard",
             "statement": "the person's target, which is on the UNCERTAINTY: the block standard error of the "
                          "mean offset, as a fraction of it, at or below one per cent. The recovered stiffness is "
                          "gamma*v over the offset, so its relative error is the offset's"},
            {"id": "recovered_stiffness_within_target", "metric": "relative_deviation_of_stiffness_recovered_through_drag",
             "comparator": "<=", "target": "trap_stiffness", "window": "record_length, after startup_discard",
             "statement": "the recovered stiffness within one per cent of the declared one. STRICTER THAN THE "
                          "TARGET AND DECLARED ANYWAY, because it is what `can the known stiffness be recovered` "
                          "asks in so many words. At the planned error it is met about three runs in four by "
                          "chance alone; see open_risks"},
        ],
        alternatives_rejected=[{"what": r["what"], "reason": r["reason"], "grounds": r["grounds"]}
                               for r in syn.get("rejected", [])] + [{
            "what": "the seven other kept cells of the grid, in this revision",
            "reason": "planned on a per-step cost that is a bracket three decades wide; this cell measures it, and "
                      "the sweep is the next revision's against the measured rate",
            "grounds": ["particle_step_rate"]}],
        open_risks=[
            "THE RECOVERED STIFFNESS IS NOT EVIDENCE ABOUT ANY TRAP. gamma and k_t both go in and the estimator "
            "inverts the equation the integrator solved (output_independent_of_input false). A pass tests the "
            "integrator and the estimator; what carries information is the error model -- whether the block "
            "error agrees with sigma*sqrt(2*tau/T), in which the stiffness has cancelled.",
            "The two success criteria are not the same test. The target is on the uncertainty, and a cell sized "
            "for one per cent of uncertainty recovers the stiffness within one per cent only about three times "
            "in four. A miss on recovered_stiffness_within_target with statistics_met is expected at that rate "
            "and is not the method failing; holding the deviation at 95 per cent would need about four times "
            "the record.",
            "ONE CELL OF TWELVE. The slow row is refused at the conservative cost (S4 refusal card) and the "
            "other seven kept cells wait for this run's measured rate. The sweep as a plan also meets a check "
            "that cannot read it: check 40 reads only top-level conditions, so a window that varies across a "
            "sweep's points -- which varies_with permits -- has nowhere to stand. Raised to manager-simulation.",
            "This runs on trap_backend, a NumPy Euler-Maruyama integrator, and not on HOOMD. The capability table "
            "declares hoomd_backend; that field records which engine ran and moves after the run.",
            "The trap is harmonic by declaration: no escape and no anharmonicity (A7). This cell's offset is ten "
            "thermal widths, about half a micrometre, well inside any real trap's range; the fast row is not.",
            "The viscosity is E3 and of order one millipascal second, and it cancels out of the recovered over "
            "declared ratio because the same gamma imposes and inverts the drag. On the bench it does not "
            "cancel, and the sample temperature is neither actuated nor read.",
        ],
    )
    card["status"] = "DRAFT"
    card.update(cards.tail(numbers, assumptions=assumptions,
                           kb_refs=synthesis.kb_refs_for(qid, numbers), kb_gaps=synthesis.kb_gaps_for(qid),
                           degraded=["librarian_agent"]))
    return card


def render(card: dict) -> str:
    """The Markdown twin. Every number it states is one the card holds (P3, check 9).

    Counts are written as integers and never in exponent form: `6e+04` reads to
    check 9 as the number 6 in the unit `e`, the elementary charge, and it
    refused the first draft for stating a charge the card does not hold.
    """
    N = {n["name"]: n for n in card["numbers"]}
    q = lambda name: f"{N[name]['value']:g} {N[name]['unit']}"
    k, o = SMOKE
    c = f"{k}_{o}"
    L = [f"# {card['id']}: the smoke cell of a drag calibration", "",
         f"*Generated from the JSON beside this file, which is authoritative (P3). Status: {card['status']}.*", "",
         f"One sphere in a harmonic trap of {q(f'trap_stiffness_{k}')}, fluid at {q(f'flow_speed_{c}')}, "
         f"timestep {q(f'integration_timestep_{c}')}, startup {q(f'startup_discard_{k}')} discarded, then a "
         f"record of {q(f'record_length_{c}')} saved every {q(f'save_interval_{k}')}.", "",
         f"At the conservative per-step cost the run takes {q('wall_clock_estimate')} and stores "
         f"{q('storage_estimate')}.", "",
         "## Success criteria", ""]
    for cr in card["success_criteria"]:
        L.append(f"- **{cr['id']}**: {cr['statement']}")
    L += ["", "## Open risks", ""]
    for r in card["open_risks"]:
        L.append(f"- {r}")
    L.append("")
    return "\n".join(L)


def emit(qid: str, created_at: str) -> tuple[Path, str]:
    """Write the pair as a DRAFT and let the validator's exit code promote it (P4)."""
    directory = cards.question_dir(qid)
    revision = cards.question_revision(qid)
    card = build(qid, created_at, revision)
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
    path, status = emit(sys.argv[1], sys.argv[2])
    print(path.relative_to(cards.REPO), status)
