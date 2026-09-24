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
    "read_noise": "the service answered `absent` for the camera's read noise",
    "quantum_efficiency": "the service answered `absent` for the camera's quantum efficiency",
    "tracer_brightness": "no photon rate per particle exists for this sample on this "
                         "instrument, and none can be asked for: it depends on the dye, the "
                         "lot, the illumination and the camera together",
    "background_rate": "no background measurement exists on this instrument",
    "pixel_size": "no sample-plane pixel size is served at this pin under the registered "
                  "quantity name, and the pixel size is keyed by the objective-and-zoom pair, "
                  "which the goal has to declare before one row applies",
    "tracer_diffusivity_expected":
        "no expected diffusivity is served at this pin. The remedy is a re-pin and not a "
        "computation here: knowledge lives in one place (P14), and computing it in this axis "
        "would put the drag in two files, which 4.5.2.1 forbids because the two would "
        "eventually disagree",
    "bleaching_rate": "no bleaching rate exists for this fluorophore",
}


def _values_for(responses: dict, name: str) -> list[tuple[str, object]]:
    """Every served value carrying this quantity's name, with the entry it is in."""
    return [(eid, num.get("value"))
            for eid, e in sorted(responses["entries"].items())
            for num in (e.get("numbers") or []) if num.get("name") == name]


def _one_value(responses: dict, name: str) -> bool:
    """A name is answered when exactly one served value carries it.

    THREE WAYS AN ANSWER IS NOT A VALUE, AND THIS AXIS MEETS ALL THREE.

    Nothing carries the name -- the store said something and holds no
    number for it. That is the relation case A2 met, where
    tracer_diffusivity_expected arrived as a formula with `numbers: []`, and
    the librarian measured it at 49 of 106 entries.

    SEVERAL THINGS CARRY IT, which is this axis's case and the sharpest of
    the three. `read_noise` returns FOUR entries -- 1.6, 2.0, 1.2 and 0.7
    electrons across the Kinetix22's DynamicRange, Speed, Sensitivity and
    SubElectron modes, a span of 2.9x -- and the store says in the entries
    themselves that a caller who does not name a mode gets four and no
    single answer, and that this is the correct refusal. `quantum_efficiency`
    returns two, the datasheet's peak 0.95 and a 600 nm point of 0.96 read
    by eye off the WRONG BODY'S graph, which the source refused to
    normalise. Taking the first of either would be picking a number by
    iteration order and calling it evidence.

    And the subject case, which A6 carries: one value, right name, wrong
    thing -- an index for a medium this lens is not in.

    So what selects among four read noises is the CAMERA MODE, and no plan
    has chosen one. That is a condition a plan must carry, not a number the
    store is missing, and naming it is more useful than an abstention that
    says `read_noise` and stops.
    """
    return len({v for _, v in _values_for(responses, name)}) == 1


# What closes a gap, where that is an acquisition rather than a question. The
# person settled on 2026-09-19 that brightness and bleaching depend on this dye,
# this lot, this illumination and this camera together, so no store can hold
# them for a sample nobody has imaged -- and an abstention that names only the
# absence leaves the reader to work out what it wants.
REMEDY = {
    "tracer_brightness": (
        "It closes by acquiring, not by asking: image the bare particles on a coverslip under "
        "the illumination the record will use, which gives the photon rate per particle and "
        "its decay in one short run. On mic-20260924-001 that run is the preparatory run of "
        "2026-09-24 (card 033), and it becomes citable once its run log is in runs/ with a "
        "run_id. Bare particles are not the mount, so the run spends nothing a later "
        "measurement needs"
    ),
    "bleaching_rate": (
        "It closes by the same bare-particle run that closes tracer_brightness: the decay over "
        "the record is the bleaching rate, so one acquisition closes both"
    ),
}

# Which condition selects among several served values, where the store says so.
SELECTED_BY = {
    "read_noise": "the camera mode, and this plan names none",
    "quantum_efficiency": ("the wavelength the path collects; one value is the datasheet's "
                           "peak, a maximum over the range and not a value at any band, and "
                           "the other is a point read off a different body's graph"),
}


def _reason(name: str, responses: dict, absent: set[str]) -> str:
    """Why this input is missing, from what the service answered and nothing else.

    Until 2026-09-24 this was a fixed table, and three of its eight sentences had
    gone false: the read noise and quantum efficiency were said to be absent from
    the store while the service returned four and two values for them, and the
    expected diffusivity was said to be unserved while it came back as an entry.
    A table written for one pin describes that pin; the answer describes this one.
    """
    if name in absent:
        base = ABSENT.get(name, f"the service answered `absent` for {name}")
        return f"{base}. {REMEDY[name]}" if name in REMEDY else base
    served = _values_for(responses, name)
    if len(served) > 1:
        listed = ", ".join(f"{v} ({eid})" for eid, v in served)
        why = SELECTED_BY.get(name, "nothing on this plan that selects one")
        return (f"the service returned {len(served)} values for {name} -- {listed} -- and "
                f"what selects among them is {why}. Taking one would be picking by "
                "iteration order and calling it evidence")
    carriers = sorted(eid for eid, e in responses["entries"].items()
                      if name in (eid, e.get("symbol")))
    if carriers:
        return (f"{name} was served as {', '.join(carriers)}, a relation with no value: it "
                "composes from inputs this axis does not bind, and computing it here would put "
                "the knowledge in two places (P14)")
    return f"nothing the service returned carries a value named {name}"


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
        missing = [n for n in ineq.needs if n in absent or not _one_value(responses, n)]
        if missing:
            reason = "; ".join(_reason(m, responses, absent) for m in missing)
            if ineq.id == "motion_blur" and "pixel_size" not in missing:
                pixels = _values_for(responses, "pixel_size")
                reason += (
                    ". The other side of this bound is served: pixel_size "
                    + ", ".join(f"{v} um ({eid})" for eid, v in pixels)
                    + ", the calibrated row for the objective-and-zoom pair the goal declares, "
                    "valid at 1x1 binning only -- at another binning the value scales and this "
                    "bound needs re-asking rather than re-using"
                )
            if ineq.id == "snr_sustained_over_window":
                observable = (goal.get("observable") or {}).get("name", "")
                if observable == "tracer_brightness":
                    reason += (
                        ". On this question the coupling runs through the observable itself: a "
                        "brightness measured over a record in which the sample bleaches is "
                        "depressed by the bleaching, so the window the brightness is read over "
                        "has to be short against the decay -- and the decay is this question's "
                        "own by-product, which is why the window is declared before the run and "
                        "judged by the fit after it"
                    )
                else:
                    reason += (
                        ". The coupling is what makes this bound matter on this configuration "
                        "rather than in general: widefield fluorescence bleaches while the record "
                        "runs, and the observable is read over the whole window. Falling "
                        "signal-to-noise raises the localisation error, so the later part of the "
                        "record is noisier and a fit across it is biased. A bleaching rate is what "
                        "turns that from a direction into a bound"
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
    run.notes.append(
        f"Every bound here abstains, and {no_input} of the {len(OWNED)} abstain for want of an "
        f"input rather than because they do not apply. Asked and absent: {', '.join(sorted(absent))}. "
        "Served but not a single value: "
        + (", ".join(n for n in ("read_noise", "quantum_efficiency", "tracer_diffusivity_expected")
                     if n not in absent and not _one_value(responses, n)) or "none")
        + ". The two are different next actions -- an absence is an acquisition or a question, "
        "several values are a condition the plan has not chosen -- and each bound's reason says "
        "which."
    )
    # History of the cards this module wrote for earlier questions, kept on those
    # questions. Emitted unconditionally until 2026-09-24, so mic-20260924-001's
    # first A1 card described revisions it never had.
    if goal.get("qid") in ("mic-20260918-001", "mic-20260920-001"):
        run.notes.append(
            "Revisions 1 and 2 of this card read the store's files and carried "
            "degraded: [librarian_agent]; revision 3 asked the service and carries none. Not one "
            "bound moved -- the same six, the same kinds, the same reasons -- so what changed is "
            "the standing of the claim rather than the claim. The pixel-size input was asked under "
            "`pixel_size_in_sample` through revision 4 and under `pixel_size` from then on: the "
            "registered quantity is the pixel size and `in_sample` is the locus, which "
            "quantities.json rule 1 keeps out of a name."
        )
    if "tracer_diffusivity_expected" in absent and pin == "kbv-7c77fa74ee5a":
        run.notes.append(
            "The second gap card 015 expected to close does not close at this pin, and it was "
            "measured rather than argued: an entry named tracer_diffusivity_expected exists in this "
            "repository's store and is outside this pin's history -- it was added at 03fe7a3, which "
            "is not an ancestor of a4e1449, the commit the service says kbv-7c77fa74ee5a resolves "
            "to. It closes by re-pinning the whole fan-out, which check 58 will not let one card do "
            "alone, and until then motion_blur stays unbounded on that input."
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
