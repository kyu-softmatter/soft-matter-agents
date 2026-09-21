"""S5 -- the plan and its identifiers (plan.md 4.5.5, 5.4).

The plan is assembly, not judgement: everything in it was decided in S3 and
S4, and this stage puts it where a person can read it and where the operator
can execute it. So every number is carried with an `origin` and nothing new
is introduced.

Three things here are worth knowing before reading the code.

**The stop and success criteria are declared now, before the run.** That is
the single most important line in this design (5.4): chosen afterwards they
would be narration rather than results. Each one points at a number the card
already carries, so there is nothing to negotiate later.

**Every stop criterion also declares `on_met`.** Without it `met: true` is not
comparable between cards -- a drift guard is met when it held, a divergence
monitor is met when the run broke -- and `outcome` is derived from exactly that
distinction. The plan schema cannot require the field, because the cards that
would gain it are pinned by a signed approval and a new field changes the hash
(5.5); that constrains the contract and not this agent, since nothing here is
signed. Declaring it lets the operator read the difference instead of guessing
it from when a criterion fired.

**The envelope check reports `unavailable`, not `inside`.** There is no
resource envelope to compare against -- A5 abstained for the same reason --
and reporting `inside` would be a claim nobody checked. `unavailable` is a
declared value of that field precisely so this case does not have to lie.

**The plan is for the declared engine, and it cannot run without a person.**
`hoomd_backend` is what `contracts/capabilities/simulation.json` says this
configuration executes with. A smoke run on the mock backend is a substituted
backend and the run log records it as such (4.6.5); either way check 15 refuses
a run directory that no approval card precedes, and only a person writes one
(6.1).
"""

from __future__ import annotations

import json
import sys

from . import cards
from . import synthesis

MODEL = (
    "overdamped Brownian dynamics of spherical tracers in an implicit solvent, "
    "no pair interactions, periodic boundaries in all three directions"
)


def build(qid: str, created_at: str, revision: int = 1) -> dict:
    goal = cards.load_goal(qid, revision)
    syn = json.loads((cards.question_dir(qid) / cards.artifact_name(
        "synthesis.json", revision)).read_text())
    config = syn["chosen_config"]

    point = {p["parameter"]: p["number"] for p in syn["operating_point"]}
    # tracer_diffusivity_expected is carried because a success criterion
    # compares the fitted value against it: a criterion whose comparand the
    # card does not hold cannot be evaluated, which would make it narration
    # after the fact -- the one thing 5.4 is written to prevent.
    extra = [
        "temperature",
        "viscosity",
        "bead_diameter",
        "diffusivity",
        # The window's two bounds. contracts/observables.json requires
        # max_lag_time to satisfy both -- below the diffusive time so the
        # tracer is still free, and short enough against the record that every
        # lag in the fit is determined -- and requires the plan to show them.
        # A value with one of its bounds invisible is a value a reader cannot
        # check.
        "tau_d",
        "lag_to_record_ratio",
        "lag_to_record_ratio_max",
    ]

    # Everything the plan states was produced upstream, so all of it is
    # carried. target_relative_error comes from A2 rather than the synthesis
    # because the synthesis had no reason to hold a success threshold.
    wanted = [("synthesis.json", n) for n in dict.fromkeys(point.values())]
    wanted += [("synthesis.json", n) for n in extra]
    wanted += [("axis_bd_overdamped_a2.json", "target_relative_error")]
    wanted += [("axis_bd_overdamped_a4.json", "intercept_sigma_max")]
    wanted += [
        ("axis_bd_overdamped_a5.json", "storage_estimate"),
        ("axis_bd_overdamped_a5.json", "wall_clock_estimate"),
    ]
    # The grounds of every rejection, so that `alternatives_rejected` resolves
    # to numbers this card holds rather than to names only it remembers. It is
    # also what keeps the generated Markdown honest: check 9 refuses a figure
    # in the prose that the card cannot back.
    wanted += [
        ("synthesis.json", "integration_timestep_max"),
        ("synthesis.json", "box_length_min_images"),
    ]
    # Derived cards resolve to this revision's filenames. `goal.json` does not:
    # its revisions 2 to 6 were written in place before 4.5.5's revision rule
    # The goal used to be exempted here -- `f if f == "goal.json" else ...` --
    # which is what kept one goal file on disk where 4.5.5 wants one per
    # revision. That exemption made revision 1 and revision 2 mutually
    # exclusive, because check 12 resolves an origin by filename alone. Every
    # card of a revision now takes that revision's name, the goal included.
    wanted = [(cards.artifact_name(f, revision), n) for f, n in wanted]
    numbers = synthesis.carry_from(qid, config, wanted)
    assumptions = synthesis.assumptions_for(qid, numbers)

    conditions = [{"parameter": p, "number": n} for p, n in point.items()]
    conditions += [
        {"parameter": "temperature", "number": "temperature"},
        {"parameter": "viscosity", "number": "viscosity"},
        {"parameter": "bead_diameter", "number": "bead_diameter"},
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
                "action": "integrate the declared configuration for the planned duration, saving frames at the planned interval",
                "reversible": True,
                "parameters": [c["parameter"] for c in conditions],
                "tier": 1,
            },
            {
                "id": "estimate_diffusivity",
                "device": "hoomd_backend",
                "action": "fit the mean squared displacement against lag over lags below the window and report the slope with its spread",
                "reversible": True,
                "parameters": ["max_lag_time", "n_particles"],
                "tier": 0,
            },
        ],
        envelope_check=envelope_check(numbers),
        cost={
            "wall_clock": "under a second of compute; the job is a million particle-steps with no pair interactions",
            "numbers": ["wall_clock_estimate", "storage_estimate"],
            "note": "estimates of an unrun job, from A5. The smoke run's own log replaces them with measured values",
        },
        stop_criteria=[
            {
                "id": "planned_duration_reached",
                "metric": "simulated_time",
                "comparator": ">=",
                "number": "total_simulated_time_point",
                "on_met": "complete",
                "statement": "stop when the run reaches the planned duration; running longer would be a different plan",
            },
            {
                "id": "step_displacement_diverged",
                "metric": "max_single_step_displacement",
                "comparator": ">",
                "number": "box_length_min_dilution",
                "on_met": "fault",
                "statement": "a tracer moving more than the box in one step is a diverged integration; stop and keep the run, because divergence is a result",
            },
        ],
        success_criteria=[
            {
                "id": "within_target_decade",
                "metric": "log10_ratio_of_measured_to_expected_diffusivity",
                "comparator": "<=",
                "target": "tracer_diffusivity",
                "window": "lags below max_lag_time",
                "statement": "the fitted diffusivity sits within the target decade of the free Stokes-Einstein expectation",
            },
            {
                "id": "statistics_met",
                "metric": "relative_standard_error_of_fitted_diffusivity",
                "comparator": "<=",
                "number": "target_relative_error",
                "window": "lags below max_lag_time",
                "statement": "the spread across tracers is small enough that the decade is decided by the physics and not by the sampling",
            },
            {
                "id": "free_regime_intercept",
                "metric": "msd_fit_intercept_in_block_sigma",
                "comparator": "<=",
                "number": "intercept_sigma_max",
                "window": "lags below max_lag_time",
                "statement": (
                    "the MSD fit's intercept is consistent with zero against the block-resampled "
                    "error, so the lags that were fitted are in the free regime the estimator "
                    "assumes. This backend has no localisation error for a free intercept to "
                    "absorb, so a nonzero one means the window and not the physics"
                ),
            },
            {
                "id": "window_insensitive",
                "metric": "log10_ratio_of_first_half_to_second_half_diffusivity",
                "comparator": "<=",
                "target": "tracer_diffusivity",
                "window": "lags below max_lag_time, split at the midpoint",
                "statement": (
                    "the fit agrees with itself across the window: D over the first half of the "
                    "lag range against D over the second. This is what separates converged from "
                    "precise -- a fit reaching past the free regime disagrees with itself across "
                    "the window while each half stays tight, and no error bar reports that"
                ),
            },
        ],
        alternatives_rejected=[
            {
                "what": r["what"],
                "reason": r["reason"],
                "grounds": r["grounds"],
            }
            for r in syn.get("rejected", [])
        ],
        open_risks=[
            "A5 abstains, so no interval in this plan is constrained by the budget. The ceilings exist in envelope/budget.json and the operator compares against them at run time, but at plan time the cost side stands alone -- a cheap run is not the same fact as a run inside a known allowance.",
            "The intercept guard cannot detect a systematic short-lag artifact. A bias shows in the mean intercept over an ensemble and a fluctuation shows in a single run, and no threshold on one run's intercept separates them. What catches an artifact is a campaign whose mean intercept is consistent with zero, and that is not a criterion one plan can carry.",
            "The fit's own standard errors understate the spread by roughly 36x for the diffusivity and 7x for the intercept, measured across 32 seeds: the weighted least squares treats correlated MSD points as independent. The criteria here read the block-resampled error instead, and any reader comparing against relative_standard_error is comparing against a number far too small.",
            "The expected diffusivity is what the run is checked against, and it was derived from the same Stokes-Einstein relation the engine is expected to reproduce. Agreement therefore tests the integration and the sampling, not the physical model.",
            "Nothing here is fitted to experimental data, and no experimental counterpart has been measured. A bridge round would be the first comparison, and comparable is still false for this observable. The store was asked at this revision and holds no measured tracer_diffusivity -- only the Stokes-Einstein prediction, which is the same relation this run is checked against.",
            "The temperature is the same number on both sides and not the same kind of number. Here the thermostat realises it exactly: it is a coordinate of the model, carrying no uncertainty of its own. The entry it was chosen from is an operator reading whose validity leaves the thermometer's position open, and nothing on the instrument actuates the sample temperature. So in a comparison the whole temperature uncertainty sits on the experimental side, and treating the two as equally certain -- or equally uncertain -- would misplace it.",
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


def envelope_check(numbers: list[dict]) -> dict:
    """The budget comparison at write time, run rather than written down.

    This block was a literal until 2026-09-20 and it said `unavailable`,
    "the file is absent", and `envelope/safety.json`. By then the file existed,
    was named `budget.json`, and the operator's own check reported `inside`:
    three false statements in one field, and **nothing reads it.** Check 8's
    `checked_against` is the bridge envelope's answerability against
    `contracts/capabilities/`; this field is compared to nothing by anything,
    so a wrong value here is never caught rather than caught late.

    So it is computed from the same code the operator runs, not restated. The
    operator re-reads the ceilings at run time regardless (4.6 O1) -- this is
    the write-time record of what was true when the plan was written, which is
    what a person reads before approving.

    `operator` is imported here rather than at module scope. S5 writes the plan
    and S6 runs it, so the dependency points the wrong way for a module-level
    import; what is being reused is one comparison, at one call site.
    """
    from . import operator

    envelope = operator.read_envelope()
    if envelope is None:
        return {
            "checked_against": [str(operator.ENVELOPE.relative_to(cards.REPO))],
            "status": "unavailable",
            "note": (
                "The ceilings file is absent, so there is no allowance to compare the "
                "estimated cost against, and A5 abstained for the same reason. This is not "
                "a claim that the run is inside budget; it is the record that nothing was "
                "available to check it against."
            ),
        }
    # The plan carries no execution target -- the target is part of the
    # operating point S4 chooses (standing orders, "the envelope"), and no
    # field holds it yet. While the envelope declares exactly one there is
    # nothing to choose; with two there would be, and guessing which machine a
    # plan is costed against is not a thing to do quietly.
    targets = [row["target"] for row in envelope.get("targets", [])]
    if len(targets) != 1:
        return {
            "checked_against": [str(operator.ENVELOPE.relative_to(cards.REPO))],
            "status": "unavailable",
            "note": (
                f"the envelope declares {len(targets)} execution targets ({', '.join(targets)}) "
                "and this plan names none. The target is part of the operating point and no "
                "field carries it yet, so which ceilings apply is undetermined -- and an "
                "undetermined ceiling is not a satisfied one."
            ),
        }
    checked = operator.check_budget({"numbers": numbers}, operator.FULL, targets[0])
    note = checked.get("reason") or (
        "; ".join(checked["exceeded"]) if checked.get("exceeded") else
        "every cost number of this plan that lines up with a ceiling is under it: "
        + ", ".join(f"{c['cost']} against {c['limit']}" for c in checked["compared"])
    )
    return {
        "checked_against": [str(operator.ENVELOPE.relative_to(cards.REPO))],
        "status": checked["status"],
        "note": f"target {targets[0]}: {note}. Re-confirmed at run time (4.6 O1).",
    }


def emit(qid: str, created_at: str) -> tuple[Path, str]:
    """Write the pair, then let the validator decide the status (5.5).

    The state machine is goal -> plan(DRAFT) -> validate(code) -> VALIDATED,
    and the middle arrow is deterministic code rather than an assertion by
    whoever wrote the card. So the card is written as a DRAFT, the validator is
    run, and only its exit code promotes it. A model saying "this looks valid"
    is not a transition (P4).
    """
    import subprocess

    directory = cards.question_dir(qid)
    revision = cards.question_revision(qid)
    card = build(qid, created_at, revision)
    json_path = directory / cards.artifact_name(f"plan_simulation_{qid}.json", revision)
    md_path = json_path.with_suffix(".md")
    cards.refuse_overwrite(json_path, revision, card)
    cards.write(json_path, card)
    md_path.write_text(render(card))

    verdict = subprocess.run(
        [sys.executable, str(cards.CONTRACTS / "validate.py"), "--quiet"],
        capture_output=True,
        text=True,
    )
    if verdict.returncode == 0:
        card["status"] = "VALIDATED"
        cards.write(json_path, card)
        md_path.write_text(render(card))
        return json_path, "VALIDATED"
    return json_path, f"DRAFT (validator exit {verdict.returncode}; {verdict.stdout.strip().splitlines()[-1] if verdict.stdout.strip() else 'see validate.py'})"




def fmt(value: float) -> str:
    return "%g" % value


def target_phrase(metric: str | None, t: dict | None) -> str:
    """A target in words, said by its kind rather than by its unit.

    A `decade_resolution` target of 1 is ONE DECADE, and rendering it as its
    raw pair -- "1 count" -- is accurate about the JSON and close to
    meaningless to a reader, which is the opposite of what the generated
    Markdown is for. 5.8 says an explore target is stated in decades, so this
    says it that way.

    **And it keeps check 9 honest about what it can see.** That check reads
    every number-and-unit pair out of the Markdown and asks for it in
    `numbers[]`. A target is deliberately NOT in `numbers[]` -- inline is what
    makes a grade inexpressible (5.3.1) -- so any target rendered as a
    quantity is a pair the check will refuse. "1 count" did refuse, the first
    time a plan with an inline target was ever rendered; manager-bridge's
    example plan had no Markdown, so this path had never run. An `uncertainty`
    target still renders as a real quantity and will hit the same wall: the
    blind spot is check 9's and is raised rather than worked around here.
    """
    if t is None:
        return f"the target for `{metric}`, which this plan does not carry"
    if t.get("kind") == "decade_resolution":
        n = fmt(t["value"])
        return f"the target for `{metric}`: {n} decade" + ("" if t["value"] == 1 else "s")
    return f"the target for `{metric}`: {fmt(t['value'])} {t['unit']}"


def render(card: dict) -> str:
    """The human-readable twin, generated from the JSON (P3, 5.6).

    Hand-editing this file has no effect: the system reads the JSON. Every
    quantity printed here is taken from `numbers[]` rather than retyped, which
    is what keeps check 9 from finding a figure in the prose that the card
    does not hold.
    """
    nums = {n["name"]: n for n in card["numbers"]}

    def quantity(name: str) -> str:
        n = nums[name]
        return f"{fmt(n['value'])} {n['unit']}"

    lines: list[str] = []
    add = lines.append

    add(f"# Plan {card['id']}")
    add("")
    add(f"*Generated from `plan_simulation_{card['qid']}.json`. The JSON is authoritative;")
    add("editing this file changes nothing (P3).*")
    add("")
    add(f"- **question** `{card['qid']}`, revision {card['revision']}, status `{card['status']}`")
    add(f"- **purpose** {card['purpose']} · **intent** {card['intent']}")
    add(f"- **from** goal `{card['goal_id']}` via synthesis `{card['synthesis_id']}`")
    if card.get("degraded"):
        add(f"- **degraded** {', '.join(card['degraded'])} — see the open risks")
    add("")

    add("## What is computed")
    add("")
    # Read from the vocabulary rather than from the card, so this line stays
    # right once the card carries the name alone.
    entry = cards.definition_entry(card["observable"]["name"])
    add(f"**{card['observable']['name']}** — {entry['definition']}")
    add("")
    add(f"*Estimator (from `contracts/observables.json`, which no card can carry):* "
        f"{entry['estimator']}")
    add("")
    sc = card["system_configuration"]
    add(f"Configuration `{sc['config']}` on `{', '.join(sc['devices'])}`.")
    add(f"Model: {sc['model']}.")
    add("")

    add("## Conditions")
    add("")
    add("| parameter | value | source | grade |")
    add("|---|---|---|---|")
    for cond in card["conditions"]:
        n = nums[cond["number"]]
        add(f"| `{cond['parameter']}` | {quantity(cond['number'])} | `{n['source']}` | {n['grade']} |")
    add("")

    add("## Declared before the run")
    add("")
    add("Stop and success criteria are fixed now. Chosen afterwards they would be narration,")
    add("not results (5.4).")
    add("")
    for kind, title in (("stop_criteria", "Stop"), ("success_criteria", "Success")):
        add(f"**{title}**")
        add("")
        for cr in card[kind]:
            # A criterion compares against a number OR against the target, and
            # check 6 has resolved either since d5af7b1. This rendered only the
            # first and raised KeyError on the second, so the pair that made a
            # target inline could not be written out at all.
            if "number" in cr:
                against = quantity(cr["number"])
            else:
                t = next((t for t in card.get("targets", []) if t["metric"] == cr.get("target")), None)
                against = target_phrase(cr.get("target"), t)
            add(f"- `{cr['metric']}` {cr['comparator']} {against} — {cr.get('statement', '')}")
        add("")

    add("## The window, and both of its bounds")
    add("")
    add("`tracer_diffusivity` is window-dependent, so the fit window is a condition and not a")
    add("detail. The vocabulary requires it to clear two bounds at once:")
    add("")
    add(f"- **physical** — below the diffusive time, so the tracer is still free: "
        f"window {quantity('max_lag_time')} against `tau_d` {quantity('tau_d')}")
    add(f"- **statistical** — short enough against the record that every lag in the fit is")
    add(f"  determined: ratio {quantity('lag_to_record_ratio')} against a ceiling of "
        f"{quantity('lag_to_record_ratio_max')}")
    add("")
    add("At a ratio of one the longest lag carries a single displacement per tracer, and an")
    add("equally weighted fit then hands the slope to its noisiest point.")
    add("")

    env = card["envelope_check"]
    add("## Envelope")
    add("")
    add(f"Status **{env['status']}**, checked against {', '.join(f'`{p}`' for p in env['checked_against'])}.")
    add("")
    add(env.get("note", ""))
    add("")

    add("## Cost")
    add("")
    for name in card["cost"]["numbers"]:
        add(f"- `{name}` {quantity(name)}")
    add("")
    add(card["cost"].get("note", ""))
    add("")

    if card.get("alternatives_rejected"):
        add("## Rejected")
        add("")
        for alt in card["alternatives_rejected"]:
            grounds = ", ".join(f"`{g}` {quantity(g)}" for g in alt["grounds"] if g in nums)
            add(f"- **{alt['what']}** — {alt['reason']}" + (f" ({grounds})" if grounds else ""))
        add("")

    add("## Open risks")
    add("")
    for risk in card["open_risks"]:
        add(f"- {risk}")
    add("")

    add("## Assumptions")
    add("")
    for a in card.get("assumptions", []):
        add(f"- **`{a['rationale_id']}`** {a['statement']}")
        if a.get("falsifier"):
            add(f"  - retired by: {a['falsifier']}")
    add("")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    qid = sys.argv[1] if len(sys.argv) > 1 else "sim-20260917-001"
    created_at = sys.argv[2] if len(sys.argv) > 2 else "2026-09-17T12:30:00Z"
    path, status = emit(qid, created_at)
    print(f"{path.relative_to(cards.REPO)} -> {status}")
