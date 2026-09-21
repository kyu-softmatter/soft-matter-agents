"""A1: signal and noise -- whether the tracer is visible enough to be measured.

4.5.3 gives this axis SNR, the detection limit, background and artifacts, and
names one artifact explicitly: through a spinning disk an exposure has to last
an integer multiple of the disk period or stripes stay in the image. The
inequality list below is derived from that sentence rather than declared here
(4.5.2.1), and each entry names where it comes from.

The disk rule is worth reading twice, because it is why an abstention needs a
kind and not a sentence. The same inequality resolves two different ways
depending on the configuration:

  widefield_inline   the disk is out of the light path, so the rule does not
                     bite -- `not_constraining`, which is a fact about the
                     instrument
  confocal           the disk is in the path, so the rule does bite, and the
                     disk period is not in the store -- `no_input`, which is a
                     missing measurement

One word for both would erase the difference, and S4 would read either as "A1
does not constrain the exposure here". One of those is headroom and the other
is an experiment nobody has run.

It reads contracts/ and the store, and imports no device (7.2 rule 2).
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

AXIS = "a1"
GAP_IDS = {
    "disk_period": "disk_period",
    "read_noise": "camera_sensor_numbers",
    "quantum_efficiency": "camera_quantum_efficiency",
    "tracer_brightness": "tracer_photophysics",
    "background_rate": "background_rate",
    "pixel_size": "pixel_size",
    "tracer_diffusivity_expected": "expected_diffusivity",
    "bleaching_rate": "tracer_bleaching",
}

OWNED = (
    axc.Inequality(
        id="disk_period_multiple",
        parameter="exposure_time",
        statement="through the spinning disk, exposure = n * disk_period, or stripes remain",
        needs=("disk_period",),
        derived_from="4.5.3 A1, the artifact it names explicitly",
    ),
    axc.Inequality(
        id="snr_floor",
        parameter="exposure_time",
        statement="exposure long enough that the tracer's signal-to-noise reaches the target",
        needs=("read_noise", "quantum_efficiency", "tracer_brightness"),
        derived_from="4.5.3 A1 'signal and noise (SNR)'",
    ),
    axc.Inequality(
        id="detection_limit",
        parameter="tracer_signal_per_frame",
        statement="the tracer has to clear the detection limit in a single frame, since a "
                  "centroid is fitted per frame and not to a sum",
        needs=("read_noise", "tracer_brightness"),
        derived_from="4.5.3 A1 'detection limit'",
    ),
    axc.Inequality(
        id="background_budget",
        parameter="background_rate",
        statement="background stays below the tracer signal by the margin the target needs",
        needs=("background_rate", "tracer_brightness"),
        derived_from="4.5.3 A1 'background'",
    ),
    axc.Inequality(
        id="motion_blur",
        parameter="exposure_time",
        statement="exposure short enough that a freely diffusing tracer does not smear across "
                  "more than one pixel within a frame",
        needs=("pixel_size", "tracer_diffusivity_expected"),
        derived_from="4.5.3 A1 'artifacts', the blur case",
    ),
    axc.Inequality(
        id="snr_sustained_over_window",
        parameter="record_duration",
        statement="the signal-to-noise holds for the whole record, not only at its start",
        needs=("bleaching_rate",),
        derived_from="4.5.3 A1 'signal and noise', over the window 4.5.3 A2 sets",
    ),
)

ABSENT = {
    "disk_period": "the disk period is not in the store: the entry states the relation an "
                   "exposure must satisfy and says in its own text that it does not carry the "
                   "number to satisfy it against",
    "read_noise": "the camera entry enters no sensor number, and says so explicitly",
    "quantum_efficiency": "same entry, same absence",
    "tracer_brightness": "nothing describes the fluorophore on these beads -- not the dye, not "
                         "a photon rate, not a labelling density",
    "background_rate": "no background measurement exists on this instrument",
    "pixel_size": "no sample-plane pixel size is served at this pin under the registered "
                  "quantity name. Through revision 4 this axis asked under "
                  "`pixel_size_in_sample` and read the empty answer as a missing "
                  "measurement, while twelve calibrations sat in this card's own kb_refs the "
                  "whole time: quantities.json rule 1, the locus glued on behind the name",
    "tracer_diffusivity_expected":
        "no expected diffusivity is served at this pin, and the name is not what is wrong. "
        "`tracer_diffusivity_expected` is a registered quantity, and kb_group -- the tool for "
        "an entry shaped like a derivation rather than a value -- is REFUSED here: no formula "
        "carries that symbol at this version. Following the service's own near name returns "
        "one E4 entry about how a temperature enters an experiment differently from a "
        "simulation, which is not a diffusivity. So the remedy is a re-pin and not a rename, "
        "and not a computation here either: knowledge lives in one place (P14), and computing "
        "it in this axis would put the drag in two files, which 4.5.2.1 forbids because the "
        "two would eventually disagree",
    "bleaching_rate": "no bleaching rate exists for this fluorophore",
}


def evaluate(goal: dict, config: str, caller_id: str, responses: dict, pin: str) -> axc.AxisRun:
    """Every inequality A1 owns, each with a range or a reason it has none."""
    run = axc.AxisRun(axis=AXIS, caller_id=caller_id, config=config,
                      kb_version=pin, owned=OWNED, degraded=[])

    configuration = axc.configuration(config)
    path = configuration.get("optical_path")
    through_the_disk = path == "confocal"

    run.kb_refs = axc.refs_from(responses, pin)
    run.kb_gaps = axc.gaps_from(responses, pin, caller_id, GAP_IDS)
    absent = {g["observable"] for g in responses["gaps"]}

    # A gap's `searched` is the record of the calls that came back empty, and one
    # call is not always the whole search: when the service offers a near name,
    # following it is a second call and the answer to it is part of what this
    # axis found out. gaps_from writes one line, from the response it was given,
    # so the extra lines come from the responses file too -- never from a table
    # here. A table would print a call that a later run did not make, which is
    # the same false-record shape the comment below this one is about.
    for extra in responses.get("follow_ups") or []:
        for gap in run.kb_gaps:
            if gap["observable"] == extra["observable"]:
                gap["searched"].append(extra["line"])

    for ineq in OWNED:
        if ineq.id == "disk_period_multiple":
            if not through_the_disk:
                run.outcomes.append(axc.Outcome(
                    inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                    kind="not_constraining",
                    reason=(f"this configuration's optical path is {path!r} and the disk is out "
                            "of it: the store records that disk-in is the confocal path while "
                            "disk-out serves widefield fluorescence and brightfield, and the "
                            "exposure rule applies to an exposure taken through the disk. So "
                            "the rule was evaluated and does not bite here. On the confocal "
                            "configuration the same inequality would abstain with kind "
                            "no_input instead, because the disk period itself is not in the "
                            "store -- which is why the two cannot be one word"),
                ))
            else:
                run.outcomes.append(axc.Outcome(
                    inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                    kind="no_input", missing=["disk_period"], reason=ABSENT["disk_period"],
                ))
            continue

        # From the service's gaps, not from ABSENT. Built from the static table,
        # an input the store gained went on being reported missing -- the false
        # absence check 49 exists against, arriving through a hardcoded list.
        # An entry answering to a name is not a value for it. A2 met this when
        # tracer_diffusivity_expected arrived as a formula carrying
        # `numbers: []`, and the librarian then measured the scope: 49 of 106
        # entries come back with no numbers, mostly `claim`s that correctly
        # hold none. So `not a gap` means the store said something, not that
        # this axis has a number -- and testing only `n in absent` sends a
        # bound with nothing to evaluate into the `failed` branch, which says
        # the axis has no code when what it has is no value.
        missing = [n for n in ineq.needs
                   if n in absent or not any(
                       num.get("name") == n
                       for e in responses["entries"].values()
                       for num in (e.get("numbers") or []))]
        if missing:
            reason = "; ".join(ABSENT[m] for m in missing if m in ABSENT)
            if ineq.id == "motion_blur" and "pixel_size" not in missing:
                reason += (
                    ". The other side of this bound is served, and saying so is the point of this "
                    "revision: asking for `pixel_size` -- the registered quantity, with the locus "
                    "out of the name -- returns twelve entries at E2, measured at the sample plane "
                    "on this instrument and keyed by objective and intermediate magnification. They "
                    "are in this card's kb_refs and were in revision 4's too, while revision 4 "
                    "recorded the same quantity as a gap. What is still not a librarian's to hold is "
                    "WHICH of the twelve applies: that is the objective-and-zoom pair, S4 chooses it, "
                    "and A6 returns the pairs that satisfy Nyquist where this axis may not read them "
                    "(4.5.3 rule b). One condition rides with them -- every one is valid at 1x1 "
                    "binning and the query passed no binning, so the service reported binning "
                    "`unasked`; at another binning the value scales and this bound needs re-asking "
                    "rather than re-using"
                )
            if ineq.id == "snr_sustained_over_window":
                reason += (
                    ". The coupling is what makes this bound matter on this configuration rather "
                    "than in general: widefield fluorescence bleaches while the record runs, and "
                    "the observable is a diffusivity read from the mean squared displacement over "
                    "the whole window. Falling signal-to-noise raises the localisation error, so "
                    "the displacement variance is inflated in the later part of the record and "
                    "the fitted slope is biased. A bleaching rate is what turns that from a "
                    "direction into a bound"
                )
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                kind="no_input", missing=missing, reason=reason,
            ))
            continue
        run.outcomes.append(axc.Outcome(
            inequality_id=ineq.id, parameter=ineq.parameter, state="failed",
            reason="every input is present and this axis has no code to emit the range: that is "
                   "a gap in this file, not an abstention (4.5.2.1)",
        ))

    # Counted off this run, not written out. The sentence this replaces listed the
    # missing inputs by hand and went on listing `the pixel size in the sample`
    # after the quantity turned out to be served -- a prose count outliving the
    # thing it counted, which is the failure this repository keeps naming.
    no_input = sum(1 for o in run.outcomes if o.kind == "no_input")
    measurements = sorted(absent - {"tracer_diffusivity_expected"})
    run.notes.append(
        f"Every bound here abstains, and {no_input} of the {len(OWNED)} abstain for want of an "
        f"input rather than because they do not apply. Read as a list, the inputs are: "
        f"{', '.join(measurements)} -- none of them exotic and none guessable (P2) -- and, "
        "separately, tracer_diffusivity_expected, which no one measures: it is a derived entry the "
        "store holds at a later version than this card's pin."
    )
    run.notes.append(
        "Revisions 1 and 2 of this card read the store's files and carried "
        "degraded: [librarian_agent]; revision 3 asked the service and carries none. Not one "
        "bound moved -- the same six, the same kinds, the same reasons -- so what changed is the "
        "standing of the claim rather than the claim. Two differences are worth naming. The gaps "
        "went from four to eight because each observable is now its own call and its own answer, "
        "where before this axis chose what to group. And the near-misses are gone: revision 2 "
        "named cameras_both_kinetix22 against read_noise, and the viscosity and ambient "
        "temperature against the expected diffusivity, all judged by this axis; the service "
        "returns nearest empty for every one. Those were the axis answering its own question in "
        "a field that says the service answered it, so their absence is the more honest state -- "
        "but the entries they named are still there and still nearly relevant, and at this pin "
        "the service cannot see that, because 17 of the 25 entries carry no machine-readable "
        "validity to match against."
    )
    run.notes.append(
        "What changed in this revision is one name and no number. The pixel-size input was asked "
        "under `pixel_size_in_sample` through revision 4 and is asked under `pixel_size` from here "
        "on: the registered quantity is the pixel size and `in_sample` is the locus, which "
        "quantities.json rule 1 keeps out of a name, and the gap this axis recorded under the long "
        "name was answered under the short one by twelve E2 entries that were already in its own "
        "kb_refs. A6 had the same rule broken in the other direction, with the subject in front. "
        "Nothing here re-grades, re-computes or re-pins anything."
    )
    if "tracer_diffusivity_expected" in absent and pin == "kbv-7c77fa74ee5a":
        run.notes.append(
            "The second gap card 015 expected to close does not close at this pin, and it was "
            "measured rather than argued: an entry named tracer_diffusivity_expected exists in this "
            "repository's store and is outside this pin's history -- it was added at 03fe7a3, which "
            "is not an ancestor of a4e1449, the commit the service says kbv-7c77fa74ee5a resolves "
            "to. The same fan-out asked for it at kbv-bf4f559baf68 earlier on 2026-09-20 and got "
            "coverage rather than a gap, so the absence is this pin's and not the store's. It "
            "closes by re-pinning the whole fan-out, which check 58 will not let one card do alone, "
            "and until then motion_blur stays unbounded on that input."
        )
    if not through_the_disk:
        run.notes.append(
            "The sixth is different and the difference is the point: the disk rule was evaluated "
            "against this configuration's optical path and does not constrain it. That is an "
            "answer, not a missing one, and recording it with the same word as the other five "
            "would lose it."
        )
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A1: signal and noise (4.5.3).")
    parser.add_argument("goal", type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--caller-id", required=True)
    parser.add_argument("--kb-version", required=True,
                        help="the pin to answer at; the store moves and siblings must agree")
    parser.add_argument("--responses", required=True, type=Path,
                        help="what the librarian returned for this caller_id at that pin")
    parser.add_argument("--prefix", default="",
                        help="filename prefix for a re-run of the whole fan-out, e.g. v2_ "
                             "(4.5.5); empty overwrites the card in place")
    parser.add_argument("--revision", type=int, default=1,
                        help="the card revision; v<N> in the caller_id follows it")
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
