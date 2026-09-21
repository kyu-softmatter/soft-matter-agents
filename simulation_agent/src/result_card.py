"""O4's last artifact: the result card (plan.md 5.1, 4.6).

A run leaves four files behind -- `config.json`, `log.json`,
`trajectory_meta.json`, `observables.json` -- and none of them is a card. The
result card is what turns them into one: the observable, its uncertainty, every
criterion the plan declared evaluated against what the run reached, and the
deviations between what was planned and what happened. Until something writes
one, a run is **recorded and not done** by this agent's own contract.

Four rulings decide most of what is here, and none of them was this module's to
make:

**A run of `bd_overdamped` may say what it read and may not claim it.** 5.3,
ruled 2026-09-20 (`a8c6470`, carried into the gate at `88c496a`): `simulated:`
is one source kind with two roles, and the field that names a number says which
role it is in. `values[]` is the card asserting something about the system;
`criteria_evaluation[].observed_number` and `deviations[]`' two sides are the
comparison terms and assert nothing beyond the run. For a configuration whose
output its input fixes -- which is what
`capabilities/simulation.json` declares of this one -- the gate refuses the
first and allows the other two. So the diffusivity this run fitted appears here
**only** as a comparison term, and `values[]` carries the prediction the plan
already held. That is the honest shape of a verification run: the claim is the
model's, the reading is the run's, and the card shows them meeting.

**The error bar is the block estimate and not the fit's own.** Task 006: the
weighted fit treats a hundred MSD points as independent observations when every
lag comes from the same trajectories, and its quoted error is about 36 times too
small, measured over 32 seeds. `statistics_met` compares a relative standard
error against a target, and a result card carries that comparison permanently --
so a card written against the fit's own error would record `met: true` beside a
number wrong by more than an order of magnitude. This module **refuses** a run
record that carries no block estimate rather than falling back to the one that
is always there.

**`met` is computed, never asserted.** Each criterion is evaluated with the
plan's own comparator against the plan's own threshold, in SI, using the same
`operator.COMPARATORS` and `operator.si` the run was compiled with -- a private
copy of either would be free to drift from the thing it has to agree with. A
stop criterion that fired during the run is additionally cross-checked against
the run's own record, and a disagreement raises rather than being written down.

**`within_tolerance` is exact reproduction, because no tolerance is declared.**
The plan states no per-parameter tolerance and neither does the envelope, so any
figure here would be one this module invented -- 11-2's "a threshold nobody has
chosen is not a satisfied threshold". A parameter the backend reproduced exactly
is within tolerance and anything else is a deviation a person should look at.
All four of the read-back parameters are exact today, so the strict rule costs
nothing and stays honest the day one of them stops being.

**Two things could not be written when this module was first built, and both
were answered by trying to write them.** `time_base.alignment` had no honest
value on this side until 4.6.9 gained `model_step_index` (`53e5561`), and a
criterion could not report that it was not evaluable until `met` became
nullable (`1b2276a`). Neither was found by reading the contracts. See
`time_base` and `evaluate_criteria`.

Every refusal branch in here has been run, against synthetic records built by
altering a real run's four files -- diverged, aborted, a record too short to
fit, a run with no honest error bar, a half-written run directory, a run that
does not exist. That exercise found one defect in this module, in the refusal
path that reports a missing run: it built a repository-relative path, which
raises when `RUNS` points outside the repository, and pointing `RUNS` outside
the repository is exactly how the exercise is run. A refusal that raises
instead of refusing is 005's shape and was fixed rather than noted.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

from . import cards
from . import operator

RUNS = cards.AGENT / "runs"

AUTHOR = cards.AUTHOR


class Blocked(Exception):
    """A required field no contract can express honestly yet.

    Not an error in the run and not a bug here: the card is complete except for
    this, and what is missing is a ruling. Raised rather than guessed, because
    the value nearest to hand is always the one that reads as a claim nobody
    made.
    """


class Unwritable(Exception):
    """The run record cannot support a card that would be true."""


# --------------------------------------------------------------------------- #
# reading what a run left behind
# --------------------------------------------------------------------------- #


def shown(path: Path) -> str:
    """A path as a message should print it: repository-relative when it is
    inside the repository, and absolute when it is not."""
    try:
        return str(path.relative_to(cards.REPO))
    except ValueError:
        return str(path)


def read_run(run_id: str) -> dict:
    """The four files of a run, or a refusal naming the one that is missing."""
    d = RUNS / run_id
    if not d.is_dir():
        # `relative_to` and not a plain path, because a repository-relative one
        # is what every other message here prints -- but it RAISES when the
        # path is outside the repository, and `RUNS` is a module attribute
        # precisely so it can be pointed at a scratch directory (the same move
        # CLAUDE.md prescribes for `operator.ENVELOPE`). So the documented way
        # to exercise this module made its refusal raise ValueError instead of
        # refusing: the behaviour was right and the reporting was not, which is
        # 005's defect in a second place. Found by pointing RUNS at a scratch
        # directory and asking for a run that was not there.
        raise Unwritable(f"{shown(d)} does not exist; there is no run to report")
    out = {}
    for key, name in (
        ("config", "config.json"),
        ("log", "log.json"),
        ("meta", "trajectory_meta.json"),
        ("observables", "observables.json"),
    ):
        p = d / name
        if not p.exists():
            raise Unwritable(
                f"{run_id} has no {name}; the operator writes all four together, so one missing "
                "means the run did not reach O4 and what happened is in the log rather than in a card"
            )
        out[key] = json.loads(p.read_text())
    return out


def plan_of(run: dict) -> tuple[dict, Path]:
    """The plan a run carried out, read back from disk rather than from the run.

    **Resolved by the revision the RUN carried, not the one the question is on
    now.** `operator.run` resolves the latest revision because it is about to
    execute one; a result is about a run that already happened, so it cites the
    revision that ran and keeps citing it after the question has moved on. The
    two resolutions differ on purpose and both go through `cards.artifact_name`,
    which is the one place that knows a revision's filename.

    This read `plan_simulation_<qid>.json` until 2026-09-21 -- the same
    hardcoded revision-1 filename `009` found in `operator.py:447`, written into
    this module before that card existed. **The consequence differed, because
    one of the two checks a hash.** The operator ran the discarded plan and
    finished green; here the hash from `config.json` did not match and the card
    was refused -- correctly, and with a message saying the plan had changed
    since the run, when what had happened was that the wrong revision's file was
    opened. Right behaviour, wrong reporting: `005`'s shape, and the third time
    today.

    The hash check stays. It is the second of two independent gates: the
    revision says which file, and the hash says the file has not moved since the
    run read it.
    """
    qid = run["config"]["qid"]
    revision = int(run["config"].get("plan_revision") or 1)
    path = cards.question_dir(qid) / cards.artifact_name(
        f"plan_simulation_{qid}.json", revision)
    if not path.exists():
        raise Unwritable(
            f"{run['config'].get('run_id')} carried revision {revision} of {qid} and "
            f"{shown(path)} does not exist. A revision is a different experiment, so there is "
            "nothing to fall back to: citing another revision's plan under this run's number "
            "would be the fault this resolution exists to stop"
        )
    plan = json.loads(path.read_text())
    if int(plan.get("revision", -1)) != revision:
        raise Unwritable(
            f"{path.name} is revision {revision} by its name and {plan.get('revision')!r} by its "
            "own field. Two independent claims disagree and this card cannot say which plan the "
            "run stood on"
        )
    now = operator.plan_hash(plan)
    was = run["config"]["plan_hash"]
    if now != was:
        raise Unwritable(
            f"{path.name} hashes {now} and the run carried {was}. The plan has changed since the "
            "run, so its numbers are not the ones this run was given; 4.5.5 says a changed "
            "question is a new revision, and a result cites the revision it ran"
        )
    return plan, path


# --------------------------------------------------------------------------- #
# units and the vocabulary pin
# --------------------------------------------------------------------------- #


def si_factor(unit: str) -> float:
    units = json.loads((cards.CONTRACTS / "units.json").read_text())["units"]
    factor = units[unit]["si_factor"]
    if factor is None:
        raise Unwritable(f"{unit!r} has no fixed SI factor, so nothing measured can be written in it")
    return float(factor)


def in_unit(value_si: float, unit: str) -> float:
    """SI back into the unit a card is written in (D7).

    The other direction is `operator.si`, which is imported rather than copied.
    This one has no counterpart anywhere because nothing until now had to write
    a measured SI quantity into a card.
    """
    return value_si / si_factor(unit)


def vocabulary_version() -> str:
    """The version of the observable vocabulary this run's estimator came from.

    Derived by `contracts/validate.py` and imported from there, because
    `result.schema.json` says so in as many words -- "Get the current version
    from validate.vocabulary_version()". A second implementation of a content
    hash is a second answer waiting to happen, and the pin is the whole basis of
    `comparable`.
    """
    path = cards.CONTRACTS / "validate.py"
    spec = importlib.util.spec_from_file_location("contracts_validate", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module          # dataclasses in it need this
    spec.loader.exec_module(module)
    return module.vocabulary_version()


# --------------------------------------------------------------------------- #
# numbers
# --------------------------------------------------------------------------- #


def carried(plan: dict, plan_path: Path, source_name: str, as_name: str | None = None) -> dict:
    """A plan number, carried with the origin that lets check 12 compare it.

    Copied whole and then renamed, rather than rebuilt field by field: check 12
    compares value, unit, grade, formula and symbol against the source, and a
    rebuild is a chance for one of them to differ for no reason. The `origin`
    is replaced -- the plan's numbers carry their own, pointing back at the
    synthesis, and keeping that would say this card took the number from a file
    it never opened.
    """
    by_name = {n["name"]: n for n in plan["numbers"]}
    if source_name not in by_name:
        raise Unwritable(f"{plan_path.name} has no number named {source_name!r}")
    out = dict(by_name[source_name])
    out["name"] = as_name or source_name
    out["origin"] = f"{plan_path.name}#{source_name}"
    return out


def reading(name: str, value_si: float, unit: str, run_id: str,
            inputs: list[dict], note: str | None = None) -> dict:
    """A number this run read, in the unit a card is written in.

    `inputs` are the card's own numbers the reading stands on, passed as whole
    number dicts so the grade is taken from them rather than restated. The grade
    lands at max(E4, worst input), which for this plan is E5 -- and that is the
    true thing rather than a defect to tidy: the reading is no stronger than the
    bead diameter and the ensemble size that were assumed into it.
    """
    kw = {"inputs": [(n["name"], n["grade"]) for n in inputs]}
    if note:
        kw["note"] = note
    return cards.num(name, in_unit(value_si, unit), unit, f"simulated:{run_id}", **kw)


# --------------------------------------------------------------------------- #
# the one field that is blocked
# --------------------------------------------------------------------------- #


def time_base(log: dict) -> dict:
    """Which clock the physics rests on -- and on this side, none of them.

    `model_step_index`, the fourth means, added to 4.6.9 on 2026-09-21
    (`53e5561`, schema at `85508a9`) after this module could not write the
    field at all. The three that existed were written for an instrument: two
    name hardware the engine does not have, and `software_monotonic` says the
    physics rides the soft clock, which here it does not. A simulation's time
    is `steps_taken * dt` -- an integer count times a fixed step -- which is
    why the operator records it in `trajectory_meta.json` and says so in the
    log's own `time_base_note`.

    **It is ranked with the first means and for the same reason**: the index IS
    the time and there is no jitter. And it is not an exception to 4.6.9's
    rule but a case the rule never reached -- the rule forbids computing
    physics from a software TIMESTAMP, and a step index is not a timestamp. The
    guard is live on this side too, and bites the day a run here reads a clock.

    `t0_wall` and `t0_mono` still come off the log. They place the run in
    history and order its events; no number in this card is computed from
    them, which is the whole distinction the fourth value exists to record.

    Check 37 accepts this value only where the configuration is declared in the
    simulation capability table, so an instrument result cannot leave by this
    door. Nothing here has to assert which side it is on -- the plan names the
    configuration and the table answers.
    """
    return {
        "t0_wall": log["t0_wall"],
        "t0_mono": log["t0_mono"],
        "alignment": "model_step_index",
    }


# --------------------------------------------------------------------------- #
# the card
# --------------------------------------------------------------------------- #


# Which number answers which criterion. Written out rather than matched on the
# criterion's `metric` string: a metric is prose in the plan and a number name
# is an identifier here, and pairing them by string similarity is the kind of
# guess that fails silently when a plan is reworded.
# The second element says whether the number came out of the ESTIMATOR rather
# than off the trajectory record, and that decides whether the criterion is
# evaluable when the estimator did not run as declared. A duration and a step
# displacement are read off the record and mean the same thing however the fit
# went; a decade count and a relative standard error are the fit's output and
# mean nothing once the fit range is not the one the vocabulary pins.
OBSERVED = {
    "planned_duration_reached": ("total_simulated_time_actual", False),
    "step_displacement_diverged": ("max_step_displacement", False),
    "within_target_decade": ("decades_from_prediction", True),
    "statistics_met": ("relative_standard_error", True),
    # Revision 2's two. Both are the estimator's output and both are new
    # measurements rather than new readings of old ones: the intercept in
    # block sigma came with the honest error bar, and the window split had to
    # be added to the backend because a criterion was declared against a
    # quantity nothing computed.
    "free_regime_intercept": ("intercept_in_block_sigma", True),
    "window_insensitive": ("window_half_disagreement", True),
}

# A plan number this card renames on the way in, because the card holds a
# planned and an actual side where the plan holds one. Read by the carry loop
# and by the threshold lookup, so the two cannot drift.
RENAMED = {
    "total_simulated_time_point": "total_simulated_time_planned",
    "box_length_min_dilution": "box_length",
    "max_lag_time": "max_lag_time_planned",
    "integration_timestep_point": "integration_timestep_planned",
    "save_interval_max": "save_interval_planned",
}


def build(run_id: str, clock=None) -> dict:
    """The card for one run.

    `clock` is the time-base function, injected rather than called directly,
    because it is the one part that cannot be written yet: `preview` passes a
    substitute so the other fields can be read and checked while that field
    waits on a ruling. Nothing else in this module knows the difference, which
    is what task 007 asked for when the blocked field was the source kind.
    """
    clock = clock or time_base
    run = read_run(run_id)
    plan, plan_path = plan_of(run)
    qid = run["config"]["qid"]
    fit = run["observables"]["fit"]
    unc = run["observables"].get("uncertainty") or {}
    meta = run["meta"]

    if fit.get("diffusivity") is None:
        raise Unwritable(
            f"{run_id} produced no fitted diffusivity -- {fit.get('reason')!r}. A run that stopped "
            "before the estimator could be applied is a result and is recorded in the run's own "
            "files; what it is not is a result card carrying an observable it does not have"
        )
    if unc.get("standard_error") is None:
        raise Unwritable(
            f"{run_id} carries no block standard error ({unc.get('reason') or 'the field is absent'}). "
            "The fit's own error is about 36 times too small for this configuration (task 006), and "
            "`statistics_met` is evaluated against a relative standard error, so writing this card "
            "from what is on disk would record a margin wrong by more than an order of magnitude. "
            "Re-run: the operator has recorded the block estimate since 2026-09-20"
        )

    # -- numbers carried from the plan ------------------------------------- #
    numbers: list[dict] = []

    def carry(source_name: str, as_name: str | None = None) -> dict:
        n = carried(plan, plan_path, source_name, as_name)
        numbers.append(n)
        return n

    # The model inputs the reading stands on. They are here to be named as the
    # reading's `inputs`, which is what makes its grade follow from them
    # instead of being chosen.
    temperature = carry("temperature")
    viscosity = carry("viscosity")
    bead_diameter = carry("bead_diameter")
    n_particles = carry("n_particles")

    # The planned side of every deviation, and the thresholds every criterion
    # is compared against.
    dt_planned = carry("integration_timestep_point", "integration_timestep_planned")
    duration_planned = carry("total_simulated_time_point", "total_simulated_time_planned")
    save_planned = carry("save_interval_max", "save_interval_planned")
    window_planned = carry("max_lag_time", "max_lag_time_planned")
    box_length = carry("box_length_min_dilution", "box_length")
    # Every OTHER number a criterion compares against, taken from the plan's
    # own criteria rather than listed here. Revision 1 names
    # `target_decade_resolution` and `target_relative_error`; revision 2 has no
    # `target_decade_resolution` at all -- the target left numbers[] for the
    # inline `targets[]` shape -- and adds `intercept_sigma_max`. A hardcoded
    # list refused revision 2 with "the plan has no number named
    # target_decade_resolution", which was true and not the point.
    held = {n.get("origin", "").split("#")[-1] for n in numbers}
    for cr in (plan.get("stop_criteria") or []) + (plan.get("success_criteria") or []):
        source = cr.get("number")
        if source and source not in held:
            carry(source, RENAMED.get(source))
            held.add(source)

    # What the card asserts about the system. For this configuration that is
    # the prediction and not the reading (5.3): the diffusivity of free
    # Brownian tracers is fixed analytically by the inputs, so citing the run
    # would launder the inputs' grade through an integrator.
    predicted = carry("diffusivity", "diffusivity_predicted")

    model_inputs = [temperature, viscosity, bead_diameter, n_particles,
                    dt_planned, save_planned, window_planned]

    # -- numbers this run read ---------------------------------------------- #
    # **A reading is in this card because a field names it.** The criteria one
    # revision declares are not the criteria another does, and a number no
    # field names is refused outright by check 21 -- rightly, since nothing
    # then says it is this run's reading rather than a claim. Revision 1 does
    # not declare `free_regime_intercept`, and its run record carries the
    # intercept anyway, so emitting every reading the record can supply would
    # put an unnamed `simulated:` number on a revision-1 card.
    wanted = {name for cr in (plan.get("stop_criteria") or []) + (plan.get("success_criteria") or [])
              for name, _ in [OBSERVED.get(cr["id"], (None, None))] if name}
    wanted |= {"integration_timestep_actual", "total_simulated_time_actual",
               "save_interval_actual", "max_lag_time_actual"}   # the deviation side

    def read(name, value_si, unit, inputs, note=None):
        if name not in wanted:
            return None
        # A metric the record does not carry produces NO number, rather than a
        # number standing on nothing. The criterion that wanted it then comes
        # out `met: null` -- which is the operator's own rule, that a metric
        # the backend did not report is not a pass but simply not evaluated.
        # Runs made before the operator recorded the step displacement land
        # here.
        if value_si is None:
            return None
        n = reading(name, value_si, unit, run_id, inputs, note)
        numbers.append(n)
        return n

    # **The value this run fitted is not a number of this card**, and that is the
    # independence ruling doing what it says rather than a gap. Under
    # `independent: false` a `simulated:` number may be named ONLY from
    # `criteria_evaluation[].observed_number` and `deviations[]`' two sides, and
    # check 21 refuses one that no field names -- "undeclared is not a
    # permission". Being an input of another number is not one of those fields.
    # So `2.1277e-13 m^2/s` and its absolute standard error stay where a reading
    # belongs, in `runs/<run_id>/observables.json`, and what the card carries is
    # the two comparison terms derived from them: how far the reading sits from
    # the prediction, and how precise it is. A reader wanting the value itself
    # opens the run. For a configuration whose output its inputs do NOT fix,
    # none of this applies: the reading goes straight into values[] and this
    # paragraph is about the other case.
    rel_error = read(
        "relative_standard_error", unc["relative_standard_error"], "1", model_inputs,
        note=(f"the block standard error over the estimate: {unc.get('blocks')} blocks of "
              f"{unc.get('tracers_per_block')} tracers refitted with the same estimator. The tracers "
              "do not interact here, so the blocks are independent by construction. The fit's own "
              "relative error is in the run record and is about 36 times smaller than the spread "
              "this configuration actually shows"),
    )
    decades = read(
        "decades_from_prediction",
        abs(math.log10(fit["diffusivity"] / (predicted["value"] * si_factor(predicted["unit"])))),
        "count", model_inputs + [predicted],
        note=("log10 of the fitted diffusivity over the plan's Stokes-Einstein expectation, in "
              "absolute value so that a factor low fails the same way as a factor high. Not a "
              "computed: number: check 17's formula language has + - * / ** and no logarithm, so "
              "a decade count cannot be written as an arithmetic the validator can redo"),
    )
    # Every one of these is `.get`, and the arithmetic below guards for None,
    # for the reason `read` returns None at all: a field the record does not
    # carry must reach the criterion as "not evaluated" rather than as a
    # KeyError. `max_single_step_displacement` is the live case -- the operator
    # has only recorded it since 2026-09-21, so the two runs before that lack
    # it, and a subscript here would have crashed on them instead of saying so.
    steps, frames = meta.get("steps_taken"), meta.get("frames_saved")
    sim_time = meta.get("simulated_time")
    # Revision 2's two, from the same run record. Both are absent from a
    # revision-1 run and neither revision-1 criterion asks for them, so `read`
    # returning None is never reached there -- but it is the honest behaviour
    # if a plan ever asks a run that predates the measurement.
    read(
        "intercept_in_block_sigma", unc.get("intercept_in_sigma"), "1", model_inputs,
        note=("the MSD fit's intercept over the block-resampled error on it. This backend has no "
              "localisation error for a free intercept to absorb, so a nonzero one is the window "
              "and not the physics"),
    )
    read(
        "window_half_disagreement",
        (run["observables"].get("window_sensitivity") or {}).get("log10_ratio"),
        "count", model_inputs,
        note=("log10 of the diffusivity fitted over the first half of the lag range against the "
              "second, in absolute value. It is what separates converged from precise: a fit "
              "reaching past the free regime disagrees with itself across the window while each "
              "half stays tight, and neither error bar can report that because every block spans "
              "the same lags"),
    )
    duration_actual = read(
        "total_simulated_time_actual", sim_time, duration_planned["unit"],
        [dt_planned, duration_planned],
        note=("steps_taken * dt, read off an integer step count rather than accumulated. Summing "
              "dt ten thousand times gives 19.999999999999794 against a planned end of 20 s, and "
              "a comparison at a boundary is a decision rather than a measurement"),
    )
    max_step = read(
        "max_step_displacement", meta.get("max_single_step_displacement"), box_length["unit"],
        [dt_planned, temperature, viscosity, bead_diameter],
        note="the largest single-step displacement any tracer took, which is what the divergence criterion watches",
    )
    dt_actual = read(
        "integration_timestep_actual", (sim_time / steps) if sim_time is not None and steps else None,
        dt_planned["unit"], [dt_planned, duration_planned],
        note="the timestep the run actually integrated at, as simulated time over steps taken",
    )
    save_actual = read(
        "save_interval_actual",
        (sim_time / (frames - 1)) if sim_time is not None and frames and frames > 1 else None,
        save_planned["unit"], [save_planned, duration_planned],
        note="the interval frames actually landed at, as simulated time over saved intervals",
    )
    window_actual = read(
        "max_lag_time_actual", fit["longest_lag"], window_planned["unit"],
        [window_planned, save_planned],
        note=("the longest lag the estimator actually fitted. It is shorter than the plan's window "
              "whenever the record ended early, which is the case the estimator's own window bound "
              "cannot see from inside"),
    )

    # -- criteria ----------------------------------------------------------- #
    # `estimation` is computed BEFORE the criteria and handed to them, because
    # whether the declared estimator actually ran is what decides whether the
    # criteria standing on its output can be evaluated at all.
    estimation = estimation_of(run, save_planned, window_planned)
    targets = targets_from(plan, qid)
    by_name = {n["name"]: n for n in numbers}
    criteria = evaluate_criteria(plan, by_name, meta, estimation, targets)

    # -- deviations ---------------------------------------------------------- #
    # A deviation row needs both sides. When the record does not carry the
    # actual the row is dropped rather than written against nothing -- and
    # unlike a criterion, `deviations` has no third state to say so, which is
    # the same hole `met` had until 1b2276a. Noted rather than worked around:
    # every row here has both sides today.
    deviations = [d for d in (
        deviation("integration_timestep", dt_planned, dt_actual),
        deviation("total_simulated_time", duration_planned, duration_actual),
        deviation("save_interval", save_planned, save_actual),
        deviation("max_lag_time", window_planned, window_actual),
    ) if d is not None]

    outcome = outcome_of(meta)

    card = cards.head(
        "result",
        f"result-{qid}-{run_id}",
        qid,
        run["log"]["finished_at"],
        thread=plan.get("thread", f"solo-{qid}"),
        round=plan.get("round", 0),
        revision=1,
        status="FAILED" if outcome == "FAILED" else "DONE",
    )
    card.update({
        "plan_id": plan["id"],
        "plan_revision": plan["revision"],
        "plan_hash": run["config"]["plan_hash"],
        "approval_id": (run["config"].get("approval") or {}).get("id"),
        "run_id": run_id,
        "observable": cards.observable(plan["observable"]["name"]),
        "outcome": outcome,
        "values": [{
            "metric": plan["observable"]["name"],
            "number": predicted["name"],
            # The prediction carries no uncertainty number: the plan states it
            # to one significant figure as an order of magnitude, and inventing
            # a spread for it here would be this module deciding how well
            # Stokes-Einstein is known. null says there is none, which is a
            # different thing from an uncertainty that was not written down.
            "uncertainty": None,
        }],
        "criteria_evaluation": criteria,
        "deviations": deviations,
        "time_base": clock(run["log"]),
        "targets": targets,
        "estimation": estimation,
    })
    card.update(cards.tail(
        numbers,
        assumptions=assumptions_for(plan, numbers),
        # Carried with the numbers that cite them, not because this card asked
        # the librarian -- it did not, and `degraded` says so -- but because
        # check 25 requires a kb: number to travel with its reference, and it
        # is right to: a value whose grade came from an entry is unreadable
        # without the entry's id, grade and pin. Only the entries this card's
        # own numbers cite come across; the plan's other references stay in the
        # plan, where the lookup happened.
        kb_refs=kb_refs_for(plan, numbers),
        kb_gaps=[],
        # Check 10: a result carries its plan's degraded list. It is also true
        # of this card on its own terms -- nothing here reached the librarian.
        degraded=list(plan.get("degraded") or []),
    ))
    return card


def threshold_si(criterion: dict, plan: dict, by_name: dict, targets: list[dict]) -> float | None:
    """What a criterion compares against, in SI, from either shape it takes.

    A threshold is a claim about the world or a decision (5.3.1), and revision 2
    moved one of them from `numbers[]` to inline `targets[]` -- where a grade is
    inexpressible rather than merely absent, because a decision is correct by
    being made. So a criterion carries either `number:` or `target:`, and both
    resolve here. Check 6 recomputes only the first kind, skipping a
    target-valued threshold; this module answers both, so the two agree where
    they overlap and this one goes further.
    """
    if criterion.get("number"):
        return operator.si({**by_name[threshold_name(criterion, plan)], "name": criterion["id"]})
    metric = criterion.get("target")
    for t in targets:
        if t.get("metric") == metric:
            return operator.si({"value": t["value"], "unit": t["unit"], "name": criterion["id"]})
    return None


def evaluate_criteria(plan: dict, by_name: dict, meta: dict, estimation: dict,
                      targets: list[dict]) -> list[dict]:
    """Every stop and success criterion the plan declares, evaluated.

    Every one, not the ones with an obvious answer: `minItems: 1` in the schema
    is a floor and the plan's four are the target. A criterion this module has
    no number for stops the card rather than being dropped -- a criterion
    silently missing from the evaluation reads as a criterion that was met.

    **A criterion can say it was not evaluated, and two things here make it.**
    `met` became `boolean | null` on 2026-09-21 (`1b2276a`), with a
    `why_unevaluated` the schema demands whenever it is null and refuses
    otherwise -- the same idiom as `approval_id`, where the key stays required
    so that "could not" cannot be written the same way as "did not say". This
    module asked for the field against its own output and is the first thing
    to write it.

    **The estimator did not run as declared.** On an aborted run the record
    ends early, the estimator fits the lags that exist, and
    `estimation.followed` goes false because the window it fitted is shorter
    than the one the plan declared. A criterion standing on the fit's output
    then compares a number the vocabulary's estimator did not produce -- which
    is the failure `estimation` exists to prevent, one level down, since
    `comparable` rests on the same estimator having run. Those criteria come
    out null; the ones read off the trajectory record do not, because a
    duration and a step displacement mean the same thing however the fit went.

    **The record does not carry the metric.** Then there is no number to
    compare and the criterion is null for the operator's own stated reason: a
    metric the backend did not report is not a pass, it is simply not
    evaluated. A criterion this module has no mapping for at all is a different
    thing and still stops the card -- silently missing from the evaluation, it
    would read as met.

    `observed_number` is kept on a null criterion. The number exists and is
    real; what is withheld is the verdict. Dropping it would also leave a
    `simulated:` number named by no field, which check 21 refuses outright --
    two rules pointing the same way.
    """
    out = []
    for kind, key in (("stop", "stop_criteria"), ("success", "success_criteria")):
        for cr in plan.get(key) or []:
            cid = cr["id"]
            mapping = OBSERVED.get(cid)
            if mapping is None:
                raise Unwritable(
                    f"the plan declares criterion {cid!r} and this module has no number for it. "
                    "result.schema.json requires every criterion to be evaluated, so the card "
                    "stops here rather than shipping one the reader would count as met. This is "
                    "not the null case: null says a run could not answer a criterion this module "
                    "knows how to ask, and here it does not know how to ask"
                )
            name, from_estimator = mapping

            if name not in by_name:
                out.append(unevaluated(cid, kind, None,
                    f"the run record carries no value for {cr.get('metric')!r}, so there is nothing "
                    "to compare. A metric the run did not report is not a pass"))
                continue
            if from_estimator and not estimation.get("followed", True):
                why = "; ".join(estimation.get("deviations") or ["the declared estimator did not run"])
                out.append(unevaluated(cid, kind, name,
                    f"this criterion reads the estimator's output and the estimator did not run as "
                    f"the vocabulary declares -- {why}. Comparing it would compare a number that "
                    f"estimator did not produce"))
                continue

            threshold = threshold_si(cr, plan, by_name, targets)
            if threshold is None:
                out.append(unevaluated(cid, kind, name,
                    f"the plan compares this against the target on {cr.get('target')!r} and this "
                    "card states no target for that metric, so there is no threshold to compare "
                    "against"))
                continue
            observed = operator.si(by_name[name])
            met = operator.COMPARATORS[cr["comparator"]](observed, threshold)
            # A stop criterion that ended the run has already been evaluated
            # once, live, by the operator. If this card disagrees with the run's
            # own record then one of the two is wrong about what happened, and
            # that is not something to write down and move past.
            if kind == "stop" and meta.get("stopped_by") == cid and not met:
                raise Unwritable(
                    f"{cid!r} stopped the run and does not evaluate as met against the final "
                    f"record ({observed} {cr['comparator']} {threshold} is false). The run log and "
                    "this card cannot both be right"
                )
            out.append({"id": cid, "kind": kind, "met": met, "observed_number": name})
    return out


def unevaluated(cid: str, kind: str, name: str | None, why: str) -> dict:
    """A criterion that could not be evaluated, with the reason the schema
    demands. `observed_number` travels when there is one: the number is real
    and only the verdict is withheld."""
    out = {"id": cid, "kind": kind, "met": None}
    if name:
        out["observed_number"] = name
    out["why_unevaluated"] = why
    return out


def threshold_name(criterion: dict, plan: dict) -> str:
    """The card's own name for the number a criterion compares against."""
    return RENAMED.get(criterion["number"], criterion["number"])


def deviation(parameter: str, planned: dict, actual: dict | None) -> dict | None:
    """Planned against actual for one parameter the run reports back.

    Only parameters the run **reports back** are here -- four of the plan's
    nine conditions. The other five are handed to the backend and never read
    again, so a deviation row for them would compare a number against itself
    and report agreement that nothing measured. When a backend that quantises
    its inputs arrives, the row appears with it.
    """
    if actual is None:
        return None
    same = operator.si(planned) == operator.si(actual)
    return {
        "parameter": parameter,
        "planned_number": planned["name"],
        "actual_number": actual["name"],
        "within_tolerance": same,
        "note": ("exact reproduction; neither the plan nor the envelope declares a tolerance for "
                 "this parameter, so anything other than exact is reported as a deviation for a "
                 "person to read rather than measured against a figure this card invented"),
    }


def outcome_of(meta: dict) -> str:
    """DONE, FAILED or NOT_CONVERGED, off the criterion the plan declared.

    Read from `stop_outcome`, which the operator takes from the criterion's own
    `on_met` rather than inferring from the fact that it fired. A criterion
    declaring `fault` means the run broke; one declaring `complete` means it
    reached its planned end.

    A run that finished and missed a success criterion is **DONE**. The outcome
    is about the run, not about whether the answer was the hoped-for one; a
    missed target is `met: false` in the evaluation, where a reader can see
    which target and by how much.
    """
    if meta.get("stop_outcome") == "fault":
        return "FAILED"
    if meta.get("stopped_early") or not meta.get("completed_planned_duration"):
        return "NOT_CONVERGED"
    return "DONE"


def targets_from(plan: dict, qid: str) -> list[dict]:
    """The accuracy the run was held to, carried inline from the goal.

    Inline -- value and unit, no source and no grade -- because a target is a
    decision and a decision is correct by being made (5.3.1). Taken from the
    goal rather than the plan: this plan predates `targets[]` on a plan card and
    carries the decision only as a graded number, which is the shape check 52
    calls the wrong copy to trust.
    """
    # Revision 2's plan carries `targets[]` itself, in the inline shape; the
    # revision-1 plan predates the field and states the decision only as a
    # graded number, which is the copy check 52 calls the wrong one to trust.
    # Prefer the plan and fall back to the goal, so a card is never without the
    # accuracy its run was held to.
    if plan.get("targets"):
        return [dict(t) for t in plan["targets"]]
    goal = cards.load_goal(qid)
    named = {n["name"]: n for n in goal.get("numbers") or []}
    out = []
    for t in goal.get("targets") or []:
        if "value" in t:
            out.append({k: t[k] for k in ("metric", "kind", "value", "unit") if k in t})
            continue
        n = named.get(t.get("number"))
        if n is None:
            continue
        out.append({"metric": t["metric"], "kind": t["kind"], "value": n["value"], "unit": n["unit"]})
    return out


def estimation_of(run: dict, save_planned: dict, window_planned: dict) -> dict:
    """Which estimator ran, by reference, and whether it ran unchanged.

    Derived rather than declared. `followed: true` written by hand would be the
    field being filled in rather than answered, and `comparable` between the two
    sides rests on it. What can be checked from the record is the fit range the
    vocabulary pins: lags from one save interval up to the window. Both ends are
    compared, and a short record -- an aborted or diverged run -- shows up here
    as a named deviation instead of as a silent difference in a later
    comparison.
    """
    fit = run["observables"]["fit"]
    deviations = []
    shortest, longest = fit.get("shortest_lag"), fit.get("longest_lag")
    if shortest != operator.si(save_planned):
        deviations.append(
            f"the shortest lag fitted was {shortest} s and the plan's save interval is "
            f"{operator.si(save_planned)} s; the vocabulary pins the fit range to start at one save interval"
        )
    if longest != operator.si(window_planned):
        deviations.append(
            f"the longest lag fitted was {longest} s against a declared max_lag_time of "
            f"{operator.si(window_planned)} s, so the record ended before the window the plan declared"
        )
    out = {
        "vocabulary_version": vocabulary_version(),
        "followed": not deviations,
        "note": ("the weighted least squares the vocabulary declares, run by the backend and citing "
                 "the contract in its own output. What is compared here is the fit range, which is "
                 "the part of the estimator a run can fail to honour by stopping early"),
    }
    if deviations:
        out["deviations"] = deviations
    return out


def assumptions_for(plan: dict, numbers: list[dict]) -> list[dict]:
    """The plan's rationales for the assumed numbers this card carries (check 4).

    Narrowed to the numbers that actually came along, the way `cards.carry`
    narrows them: a rationale pointing at a number this card does not hold would
    claim to explain something that is not here.
    """
    # A carried number may have been renamed on the way in -- `max_lag_time`
    # becomes `max_lag_time_planned` here, because this card holds a planned and
    # an actual side where the plan holds one. So the rationale is FOUND by the
    # plan-side name in the origin and REWRITTEN to the card-side name: check 4
    # reads the card's own numbers[], and a rationale still naming the plan's
    # name explains nothing that is here.
    renamed = {str(n.get("origin", "")).split("#")[-1]: n["name"]
               for n in numbers if n.get("origin")}
    out = []
    for a in plan.get("assumptions") or []:
        overlap = [renamed[x] for x in a.get("numbers") or [] if x in renamed]
        if overlap:
            out.append({**a, "numbers": overlap})
    return out


def kb_refs_for(plan: dict, numbers: list[dict]) -> list[dict]:
    """The plan's references for the store-sourced numbers this card carries.

    Verbatim, pin included. A reference re-derived here would be this card
    saying what the store holds now, and what the number stands on is what the
    store held when it was looked up -- which is the reason a kb_ref carries a
    `kb_version` at all.
    """
    cited = {str(n["source"]).split(":", 1)[1]
             for n in numbers if str(n.get("source", "")).startswith("kb:")}
    return [dict(r) for r in plan.get("kb_refs") or [] if r.get("entry_id") in cited]


# --------------------------------------------------------------------------- #
# writing
# --------------------------------------------------------------------------- #


def path_for(qid: str, run_id: str) -> Path:
    """Where a result card lives.

    `questions/<qid>/` and not `runs/<run_id>/`: 7.1 rule 1 puts everything
    about one question flat in one folder, and a result is a card of the
    question the way the goal and the plan are. The run id is in the filename
    because one question can have several runs and each gets its own card.

    Section 7's tree does not yet name this file, which is a gap in the prose of
    record rather than a refusal -- `ALLOWED_PATHS` accepts the folder, and
    check 13 needs both. Raised with the architecture seat.
    """
    return cards.question_dir(qid) / f"result_{run_id}.json"


def emit(run_id: str) -> Path:
    card = build(run_id)
    path = path_for(card["qid"], run_id)
    cards.refuse_overwrite(path, card["revision"], card)
    return cards.write(path, card)


def preview(run_id: str) -> dict:
    """The card with any blocked field replaced by the reason it is blocked.

    Not a card and never written into the tree: it exists so that the rest of
    the work can be read and checked while one field waits on a ruling. A file
    that looked like a card with a sentence where a value belongs is exactly the
    artifact the blocking is meant to prevent.
    """
    def blocked(log):
        try:
            return time_base(log)
        except Blocked as exc:
            return {"__blocked__": str(exc)}

    return build(run_id, clock=blocked)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "run-20260920-003"
    if "--preview" in sys.argv:
        print(json.dumps(preview(which), indent=2, ensure_ascii=False))
    else:
        try:
            print(emit(which).relative_to(cards.REPO))
        except (Blocked, Unwritable) as exc:
            print(f"BLOCKED: {exc}" if isinstance(exc, Blocked) else f"REFUSED: {exc}")
            raise SystemExit(3)
