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
SEARCHED = ["librarian_agent/kb/entries/", "librarian_agent/kb/staging/",
            "contracts/capabilities/microscope.json"]

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
    "pixel_size_in_sample": "no pixel size exists: it needs the camera's sensor pitch, which the "
                            "camera entry does not carry, and the magnification actually in use",
    "tracer_diffusivity_expected": "no expected diffusivity is in the store. It is computable -- "
                                   "Stokes-Einstein on the viscosity, the diameter and the "
                                   "ambient temperature, all three of which exist -- and that is "
                                   "why it belongs in the store as an entry rather than here: "
                                   "knowledge lives in one place (P14), and computing it in this "
                                   "axis would also put the drag in two files, which 4.5.2.1 "
                                   "forbids because the two would eventually disagree",
    "bleaching_rate": "no bleaching rate exists for this fluorophore",
}


def evaluate(goal: dict, config: str, caller_id: str) -> axc.AxisRun:
    """Every inequality A1 owns, each with a range or a reason it has none."""
    run = axc.AxisRun(axis=AXIS, caller_id=caller_id, config=config,
                      kb_version=axc.kb_version(), owned=OWNED,
                      degraded=["librarian_agent"])

    configuration = axc.configuration(config)
    path = configuration.get("optical_path")
    through_the_disk = path == "confocal"

    disk_states = axc.kb_entry("csuw1_disk_position_states")
    disk_rule = axc.kb_entry("csuw1_disk_speed_exposure_constraint")
    if disk_states and disk_rule:
        run.kb_refs.append(axc.kb_ref("csuw1_disk_position_states", run.kb_version))
        run.kb_refs.append(axc.kb_ref("csuw1_disk_speed_exposure_constraint", run.kb_version))

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

        missing = [n for n in ineq.needs if n in ABSENT]
        if missing:
            reason = "; ".join(ABSENT[m] for m in missing)
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

    run.gap("camera_sensor_numbers", "read_noise", SEARCHED,
            nearest=[{"entry_id": "cameras_both_kinetix22", "overlap": "partial"}])
    run.gap("tracer_photophysics", "tracer_brightness", SEARCHED)
    run.gap("expected_diffusivity", "tracer_diffusivity_expected", SEARCHED,
            nearest=[{"entry_id": "water_viscosity_293k", "overlap": "partial"},
                     {"entry_id": "lab_ambient_temperature", "overlap": "partial"}])
    run.gap("disk_period", "disk_period", SEARCHED,
            nearest=[{"entry_id": "csuw1_disk_speed_exposure_constraint", "overlap": "partial"}])

    run.notes.append(
        "Every bound here abstains, and five of the six abstain for want of a number rather than "
        "because they do not apply. Read as a list of measurements, that is: the camera's read "
        "noise and quantum efficiency, the pixel size in the sample, the tracers' brightness and "
        "bleaching rate, and a background rate. None of them is exotic and none can be guessed "
        "(P2), which is the whole content of this card."
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
    args = parser.parse_args(argv)

    goal = json.loads(args.goal.read_text())
    if goal.get("card") != "goal":
        print(f"{args.goal} is not a goal card", file=sys.stderr)
        return 2
    run = evaluate(goal, args.config, args.caller_id)
    axc.report(run)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return axc.write(run, goal, goal.get("qid", ""), created_at)


if __name__ == "__main__":
    raise SystemExit(main())
