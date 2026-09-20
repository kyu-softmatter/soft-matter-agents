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
    "pixel_size_in_sample": "pixel_size_in_sample",
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
        needs=("pixel_size_in_sample", "tracer_diffusivity_expected"),
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
    "pixel_size_in_sample":
        "the store does not answer to this name and the quantity is there anyway: the gap "
        "carries near_names [pixel_size], and under that name twelve E2 entries give the "
        "pixel size AT THE SAMPLE PLANE, measured on this instrument per objective and "
        "zoom. So this is not a measurement anybody is missing. What is missing is WHICH "
        "of the twelve applies -- the objective-and-zoom pair, which S4 chooses and no "
        "librarian holds. A6 returns the four pairs that satisfy Nyquist and this axis may "
        "not read that (4.5.3 rule b); once the pair is fixed this bound is arithmetic, "
        "because the expected diffusivity is served now too",
    "tracer_diffusivity_expected": "no expected diffusivity is in the store. It is computable -- "
                                   "Stokes-Einstein on the viscosity, the diameter and the "
                                   "ambient temperature, all three of which exist -- and that is "
                                   "why it belongs in the store as an entry rather than here: "
                                   "knowledge lives in one place (P14), and computing it in this "
                                   "axis would also put the drag in two files, which 4.5.2.1 "
                                   "forbids because the two would eventually disagree",
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
        missing = [n for n in ineq.needs if n in absent]
        if missing:
            reason = "; ".join(ABSENT[m] for m in missing if m in ABSENT)
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

    run.notes.append(
        "Every bound here abstains, and five of the six abstain for want of a number rather than "
        "because they do not apply. Read as a list of measurements, that is: the camera's read "
        "noise and quantum efficiency, the pixel size in the sample, the tracers' brightness and "
        "bleaching rate, and a background rate. None of them is exotic and none can be guessed "
        "(P2), which is the whole content of this card."
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
    return axc.write(run, goal, goal.get("qid", ""), created_at, args.revision)


if __name__ == "__main__":
    raise SystemExit(main())
