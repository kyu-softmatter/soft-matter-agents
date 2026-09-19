"""A2: statistical requirement -- how much record, how many tracers, how many repeats.

4.5.3 gives this axis sample count, record length and repeats. The inequality
list below is derived from that cell rather than declared here (4.5.2.1), and
each entry names where it comes from.

Answered by the service, like A4 and unlike A1 and A7: it takes the librarian's
recorded answers and never opens the store, so `degraded` is empty and the
emptiness is checkable against queries/log.jsonl (0.3-4).

All four bounds abstain, which 001 expected. Two things make the card more than
an empty one, and both are about the *shape* of what is missing rather than the
fact of it.

**The record-length relation is served and only its value is missing.** tau_d
comes back at E4: the diffusive time is what a sphere needs to diffuse its own
diameter, and it sets the shortest record length an MSD can be read from. So
this bound is one number away from returning, and that number --
tracer_diffusivity_expected -- is computable from three entries that all exist:
the water viscosity, the tracer diameter and the ambient temperature. It is not
computed here. P14 puts knowledge in one place, and a diffusivity computed
inside an axis would sit in this file and in whatever else needs it, which
4.5.2.1 forbids for the reason that the two copies eventually disagree. A1 made
the same refusal for the same input; two axes needing one number is normal
(4.5.3), two axes each deriving it is not.

**The repeats bound is blocked twice over, and the second block is the goal's.**
The statistics need a per-repeat variance nobody has measured. Separately, the
goal card records that the sample is consumed by the measurement and cannot be
remounted -- so the repeat count is capped at one by the experiment, whatever
the statistics turn out to want. That is a coupling S4 has to see: if the
statistical requirement ever exceeds one independent mount, the question is
infeasible as posed rather than expensive. It is recorded in the reason and not
as an interval, because how many repeats are POSSIBLE is the goal's constraint
and not this axis's bound -- A2 owns how many are NEEDED.

It reads contracts/, the goal card and the recorded responses, and imports no
device (7.2 rule 2).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
from datetime import datetime, timezone                           # noqa: E402
from pathlib import Path                                          # noqa: E402


def _load(name: str, filename: str):
    path = os.path.join(_HERE, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                               # type: ignore[union-attr]
    return module


axc = _load("_mic_axis_common", "axis_common.py")

AXIS = "a2"

OWNED = (
    axc.Inequality(
        id="record_length_vs_diffusive_time",
        parameter="record_duration",
        statement="the record spans enough diffusive times that a mean squared displacement has "
                  "a slope to fit",
        needs=("tracer_diffusivity_expected",),
        derived_from="4.5.3 A2 'record length'",
    ),
    axc.Inequality(
        id="displacement_samples_per_lag",
        parameter="frame_count",
        statement="each lag time carries enough independent displacements that the fitted slope "
                  "reaches the target relative error",
        needs=("target_relative_error", "localisation_error"),
        derived_from="4.5.3 A2 'sample count', over the lag times the record length allows",
    ),
    axc.Inequality(
        id="ensemble_size",
        parameter="tracer_count",
        statement="enough tracers are in the field at once to supply those displacements without "
                  "extending the record",
        needs=("tracer_number_density",),
        derived_from="4.5.3 A2 'sample count', the ensemble rather than the time average",
    ),
    axc.Inequality(
        id="independent_repeats",
        parameter="repeat_count",
        statement="enough independent repeats to separate the sample's spread from the "
                  "measurement's",
        needs=("target_relative_error", "localisation_error"),
        derived_from="4.5.3 A2 'repeats'",
    ),
)

GAP_IDS = {
    "tracer_diffusivity_expected": "expected_diffusivity",
    "target_relative_error": "target_relative_error_never_stated",
    "localisation_error": "localisation_error",
    "tracer_number_density": "tracer_loading",
}

ABSENT = {
    "tracer_diffusivity_expected":
        "no expected diffusivity is in the store. The service was asked and answered absent",
    "target_relative_error":
        "no target relative error exists anywhere. It is not the goal's decade resolution and not "
        "its signal-to-noise target: a decade says how coarsely the answer may land, SNR says "
        "whether the tracer is detectable, and neither says how precisely a displacement has to "
        "be resolved. Only the operator can state it",
    "localisation_error":
        "no localisation error has been measured on this instrument, and it cannot be derived "
        "here either, since it needs the pixel size and the signal-to-noise actually achieved",
    "tracer_number_density":
        "nothing states how many tracers are in the sample or in a field: no concentration, no "
        "count, no dilution record",
}


def consumed_sample_note(goal: dict) -> str | None:
    """The goal's own constraint on remounting, quoted rather than paraphrased.

    Read off the goal card, which is this axis's input. It is not another axis's
    output, so rule (b) of 4.5.3 is not in play.
    """
    for note in goal.get("constraint_notes", []):
        if "remounted" in note or "consumed" in note:
            return note
    return None


def evaluate(goal: dict, config: str, caller_id: str, responses: dict, pin: str) -> axc.AxisRun:
    """Every inequality A2 owns, each with a range or a reason it has none."""
    run = axc.AxisRun(axis=AXIS, caller_id=caller_id, config=config, kb_version=pin,
                      owned=OWNED, degraded=[])

    absent = {g["observable"]: g for g in responses["gaps"]}
    run.kb_refs = axc.refs_from(responses, pin)
    run.kb_gaps = axc.gaps_from(responses, pin, caller_id, GAP_IDS)
    served = responses["entries"]
    no_remount = consumed_sample_note(goal)

    for ineq in OWNED:
        missing = [n for n in ineq.needs if n in absent]
        if not missing:
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="failed",
                reason="every input is present and this axis has no code to emit the range: that "
                       "is a gap in this file, not an abstention (4.5.2.1)",
            ))
            continue

        reason = "; ".join(ABSENT[m] for m in missing)

        if ineq.id == "record_length_vs_diffusive_time" and "tau_d" in served:
            reason += (
                ". What is served is the relation and not the value: tau_d came back at E4 -- the "
                "diffusive time is what a sphere needs to diffuse its own diameter, and it sets "
                "the shortest record length an MSD can be read from. So this bound returns the "
                "moment a diffusivity exists, and the diffusivity is computable from three "
                "entries that already do: the water viscosity, the tracer diameter and the "
                "ambient temperature. It is not computed here. Knowledge lives in one place "
                "(P14), and a diffusivity derived inside this axis would sit in this file and in "
                "every other axis that needs it, which 4.5.2.1 forbids because the copies "
                "eventually disagree. The entry also carries its own warning for whoever does "
                "compute it: near a wall the drag is corrected separately rather than absorbed "
                "into this time, or the time unit moves with stage position and nothing can be "
                "compared"
            )

        if ineq.id == "independent_repeats" and no_remount:
            reason += (
                ". And this bound is blocked a second time, by the goal rather than by the store: "
                f"{no_remount!r}. So the repeat count is capped at one independent mount whatever "
                "the statistics turn out to need. That is a coupling S4 has to see rather than a "
                "bound this axis states -- how many repeats are POSSIBLE is the goal's "
                "constraint, how many are NEEDED is A2's -- and if the requirement ever exceeds "
                "one mount the question is infeasible as posed rather than merely expensive"
            )

        run.outcomes.append(axc.Outcome(
            inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
            kind="no_input", missing=missing, reason=reason,
        ))

    run.notes.append(
        "Answered by the librarian service rather than by reading the store, which is what makes "
        "degraded empty: one entry came back with its own grade and four questions came back "
        "absent, all at the pinned kbv-49feb73662b7, and every call is in "
        "librarian_agent/queries/log.jsonl under this caller_id. The served digest was checked "
        "byte for byte against the pinned commit's blob."
    )
    run.notes.append(
        "All four bounds abstain and the four missing inputs are not alike. Two are measurements "
        "nobody has taken here -- the localisation error and the tracer loading. One is "
        "derivable and deliberately not derived: the expected diffusivity, which belongs in the "
        "store as an entry because two axes already need it. The fourth is not a measurement at "
        "all: the target relative error is a decision only the operator can make, and the goal's "
        "decade resolution and SNR target are neither substitute. Read as a to-do list, that is "
        "two experiments, one KB entry and one question for a person."
    )
    if no_remount:
        run.notes.append(
            "The repeats bound carries the sharpest thing in this card and it is not a number: "
            "the sample cannot be remounted, so one mount is all there is. Every statistical "
            "demand this axis cannot yet compute has to fit inside a single record on a single "
            "mount, and if it does not, no amount of instrument time buys the difference."
        )
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A2: statistical requirement (4.5.3).")
    parser.add_argument("goal", type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--caller-id", required=True)
    parser.add_argument("--kb-version", required=True,
                        help="the pin to answer at. Not read from the store: the store moves and "
                             "siblings have to agree (check 33)")
    parser.add_argument("--responses", required=True, type=Path,
                        help="what the librarian returned for this caller_id at that pin")
    args = parser.parse_args(argv)

    goal = json.loads(args.goal.read_text())
    if goal.get("card") != "goal":
        print(f"{args.goal} is not a goal card", file=sys.stderr)
        return 2
    try:
        responses = axc.load_responses(args.responses, args.kb_version, args.caller_id)
    except axc.AxisError as exc:
        print(f"no card written: {exc}", file=sys.stderr)
        return 3
    run = evaluate(goal, args.config, args.caller_id, responses, args.kb_version)
    axc.report(run)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return axc.write(run, goal, goal.get("qid", ""), created_at)


if __name__ == "__main__":
    raise SystemExit(main())
