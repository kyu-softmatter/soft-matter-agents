"""A3: sample integrity -- what the measurement costs the thing being measured.

4.5.3 gives this axis photodamage, bleaching, heating and concentration. The
inequality list below is derived from that cell rather than declared here
(4.5.2.1), and each entry names where it comes from.

Answered by the service, like A2 and A4: it takes the librarian's recorded
answers, never opens the store, and `degraded` is empty and checkable against
queries/log.jsonl (0.3-4).

All four bounds abstain for want of a number. Three things make the card more
than four empty slots, and each is a fact about the instrument rather than a
missing measurement.

**Bleaching is irreversible and the sample cannot be remounted.** That is this
axis's own content and no other axis owns it. Every photon spent finding focus,
centring the field or checking alignment is subtracted from the measurement's
budget, permanently, on the only mount there will be. A1 owns the other side of
the same mechanism -- whether signal-to-noise survives the window -- and this is
not that inequality repeated: A1's floor comes from detectability and this
one's from the sample being consumed. 4.5.3 allows several axes to bound one
parameter; what it forbids is one inequality living in two axes.

**The heating bound could not be checked even with the number.** Nothing
actuates the sample temperature, so optical heating cannot be counteracted; and
the ambient reading is not established to be the sample's, because where the
thermometer sits was never recorded. So the abstention is not merely "no
heating rate" -- it is that this instrument has no way to confirm the sample
stayed inside the bound. Same shape as A4's read-back finding, reached from a
different direction.

**And one conflation to refuse out loud.** The temperature entries say that in
explore mode a drift of about a kelvin does not move a decade and can be
ignored. That is about the ROOM's drift and the viscosity it feeds. Illumination
heating of the sample is a different quantity, nothing bounds it, and borrowing
the room's tolerance for it would be reading a permission out of an unrelated
measurement.

**The photodamage ceiling is not this axis's to state.** Total illumination
meets P0's safety limit before it meets the sample's tolerance (4.5.3 A7), and
those limits live in envelope/safety.json, which a person writes and which does
not exist. A3 bounds what the sample can take; it does not bound what the
instrument is allowed to emit, and it may not supply the second from the first.

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

AXIS = "a3"

OWNED = (
    axc.Inequality(
        id="photodamage_dose",
        parameter="illumination_dose",
        statement="the cumulative dose the sample receives stays below what damages it",
        needs=("photodamage_threshold",),
        derived_from="4.5.3 A3 'photodamage'",
    ),
    axc.Inequality(
        id="bleaching_over_record",
        parameter="record_duration",
        statement="the label surviving at the end of the record is enough that the observable is "
                  "read from the sample rather than from its depletion",
        needs=("bleaching_rate",),
        derived_from="4.5.3 A3 'bleaching'",
    ),
    axc.Inequality(
        id="heating_budget",
        parameter="illumination_power",
        statement="optical heating leaves the sample temperature inside the band the observable "
                  "can tolerate",
        needs=("sample_heating_rate",),
        derived_from="4.5.3 A3 'heating'",
    ),
    axc.Inequality(
        id="concentration_window",
        parameter="tracer_number_density",
        statement="dense enough that a field carries trackable tracers, dilute enough that they "
                  "neither interact nor overlap in the image",
        needs=("tracer_number_density",),
        derived_from="4.5.3 A3 'concentration'",
    ),
)

GAP_IDS = {
    "photodamage_threshold": "photodamage_threshold",
    "bleaching_rate": "tracer_photophysics",
    "sample_heating_rate": "optical_heating",
    "tracer_number_density": "tracer_loading",
}

ABSENT = {
    "photodamage_threshold":
        "no damage threshold exists for this sample. The service was asked and answered absent",
    "bleaching_rate":
        "no bleaching rate exists for this fluorophore -- not a rate, not a dye, not a photon "
        "budget",
    "sample_heating_rate":
        "nothing relates illumination power to a temperature rise in this sample",
    "tracer_number_density":
        "nothing states how many tracers are in the sample or in a field: no concentration, no "
        "count, no dilution record",
}


def no_remount(goal: dict) -> str | None:
    """The goal's own statement that the sample is spent, quoted rather than paraphrased."""
    for note in goal.get("constraint_notes", []):
        if "remounted" in note or "consumed" in note:
            return note
    return None


def evaluate(goal: dict, config: str, caller_id: str, responses: dict, pin: str) -> axc.AxisRun:
    """Every inequality A3 owns, each with a range or a reason it has none."""
    run = axc.AxisRun(axis=AXIS, caller_id=caller_id, config=config, kb_version=pin,
                      owned=OWNED, degraded=[])

    absent = {g["observable"]: g for g in responses["gaps"]}
    run.kb_refs = axc.refs_from(responses, pin)
    run.kb_gaps = axc.gaps_from(responses, pin, caller_id, GAP_IDS)
    served = responses["entries"]
    spent = no_remount(goal)

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

        if ineq.id == "photodamage_dose":
            reason += (
                ". And the number that is missing is not the one that binds first: total "
                "illumination meets P0's safety limit before it meets the sample's tolerance "
                "(4.5.3 A7), and those limits are policy in envelope/safety.json, written by a "
                "person who confirmed them physically and deliberately not extracted from the "
                "prior project (10.3 rule 4). Whether that file exists does not change this bound, "
                "which does not read it. This axis bounds what the "
                "sample can take and not what the instrument may emit, and it may not supply the "
                "second from the first"
            )

        if ineq.id == "bleaching_over_record":
            reason += (
                ". It closes by acquiring, not by asking: image the bare particles under the "
                "illumination the record will use, and the decay over that record is the rate. "
                "On mic-20260924-001 that run is the preparatory run of 2026-09-24 (card 033), "
                "citable once its run log is in runs/ with a run_id; bare particles are not the "
                "mount, so the run spends nothing a later measurement needs"
            )

        if ineq.id == "bleaching_over_record" and spent:
            reason += (
                ". What makes this A3's bound and not A1's is that the loss is irreversible and "
                f"the sample is not replaceable: {spent!r}. So every photon spent before the "
                "record -- finding focus, centring the field, checking alignment -- is subtracted "
                "from the measurement's budget permanently, on the only mount there will be, and "
                "a plan that budgets only the record has already spent part of it. A1 owns the "
                "other side of the same mechanism, whether signal-to-noise survives the window; "
                "its floor comes from detectability and this one's from the sample being "
                "consumed. 4.5.3 lets several axes bound one parameter and forbids one inequality "
                "living in two axes, and these are two"
            )

        if ineq.id == "heating_budget":
            refs = [e for e in ("sample_temperature_not_actuated", "lab_ambient_temperature")
                    if e in served]
            if refs:
                reason += (
                    ". The rate is the smaller half of it: even with a rate, this instrument "
                    "could not confirm the sample stayed inside the bound. Nothing actuates the "
                    "sample temperature -- a stage exists and has never been connected, so there "
                    "is no setpoint to appeal to -- and the ambient reading is not established to "
                    "be the sample's, because where the thermometer sits was never recorded. So "
                    "the bound would be unverifiable rather than merely uncomputed. One "
                    "conflation to refuse while these entries are in hand: they say that in "
                    "explore mode a drift of about a kelvin does not move a decade and can be "
                    "ignored, and that is the ROOM's drift feeding the viscosity. Illumination "
                    "heating of the sample is a different quantity that nothing here bounds, and "
                    "borrowing the room's tolerance for it would be reading a permission out of "
                    "an unrelated measurement"
                )

        if ineq.id == "concentration_window":
            reason += (
                ". The same number is what A2's ensemble size wants, and the two bounds are not "
                "the same: A2 asks how many tracers the statistics need, this one asks what "
                "loading the sample tolerates before tracers interact or their images overlap. "
                "One measurement closes both"
            )

        run.outcomes.append(axc.Outcome(
            inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
            kind="no_input", missing=missing, reason=reason,
        ))

    run.notes.append(
        f"Answered by the librarian service rather than by reading the store, which is what "
        f"makes degraded empty: {len(run.kb_refs)} entries came back with their own grades and "
        f"{len(run.kb_gaps)} questions came back absent, all at the pinned {pin}, and every call "
        f"is in librarian_agent/queries/log.jsonl under this caller_id. The counts and the "
        f"version in this sentence are computed rather than typed -- three cards carried a stale "
        f"pin here after a re-pin because they were typed."
    )
    run.notes.append(
        "Four bounds, four missing numbers, and three of the four are one experiment: point this "
        "illumination at these tracers and watch them bleach. That run yields the bleaching rate, "
        "a damage threshold and -- with a thermometer at the sample -- a heating rate, and it is "
        "the single cheapest thing anyone could do for this fan-out. The fourth, the tracer "
        "loading, is not an experiment but a record nobody kept."
    )
    if spent:
        run.notes.append(
            "The sharpest thing in this card is not a number and not this axis's alone: the "
            "sample is spent by the measurement. A2 reads that as one mount, so no repeat can "
            "average anything away. A3 reads it as an illumination budget that setup draws down "
            "before the record begins. Both follow from one sentence on the goal card, and it is "
            "worth S4 seeing that the two axes are not making the same point twice."
        )
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A3: sample integrity (4.5.3).")
    parser.add_argument("goal", type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--caller-id", required=True)
    parser.add_argument("--kb-version", required=True,
                        help="the pin to answer at. Not read from the store: the store moves and "
                             "siblings have to agree (check 33)")
    parser.add_argument("--prefix", default="",
                        help="filename prefix for a re-run of the whole fan-out, e.g. v2_ "
                             "(4.5.5); empty overwrites the card in place")
    parser.add_argument("--revision", type=int, default=1,
                        help="the card revision; v<N> in the caller_id follows it")
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
    return axc.write(run, goal, goal.get("qid", ""), created_at, args.revision, args.prefix)


if __name__ == "__main__":
    raise SystemExit(main())
