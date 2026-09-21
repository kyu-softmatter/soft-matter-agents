"""A6: spatial resolution, field of view and optical sectioning.

4.5.3 gives this axis NA, magnification, pixel size, pinhole and axial
resolution. The inequality list below is derived from that cell rather than
declared here (4.5.2.1), and each row names where it comes from.

**Answered by the service, not by reading the store.** Like A4 and unlike A1
and A7, this axis never calls axis_common.kb_entry(): it takes a --responses
file holding what the librarian actually returned, and axis_common refuses any
response not stamped with the pin it was asked at. Reading the files is not the
service answering (0.3), so that is what makes `degraded` empty here.

What the pass found, and it is the content of the card rather than a caveat:

  **NA is served six times over and the query for it comes back absent.**
  `kb_query(observable=numerical_aperture)` answers `absent` while
  objective_mrd70040 and five siblings each carry numbers[].name = "na" at E3.
  Nothing is indexed under that observable name. This axis therefore reaches
  the six by entry id, and the six NA values are on the card. An empty query is
  not evidence of absence in this store today, and a gap written off one would
  have been false.

  **And the diffraction limit still does not compute.** 001 and 004 both
  expected it to, because the six objectives carry the inputs -- but NA is one
  input of two. d ~ lambda/NA needs a wavelength, and this store holds none at
  any name this axis could find. The other half is worse: nothing states what
  has to be resolved. The goal's only target is one decade on the diffusivity,
  which is not a length, so there is no required resolution for an NA to be
  compared against. Two inputs short, both named, neither guessed (P5).

  **Nyquist cannot be closed by a lookup at all**, and that is sharper than a
  missing number. Pixel size is the store's one honest absent. Magnification is
  absent *by construction*: the nosepiece entry states that a magnification
  written there is a nominal designation and a string identifier rather than a
  number, and 5.3 refuses back-deriving one from a calibrated pixel size -- the
  prior project's 20.078x is exactly that refusal's precedent. So the effective
  pixel size is closed by one calibration per configuration, not by an entry.

All five bounds abstain, each for its own reason, and `constraints` is empty.
A6's one candidate for a returned interval is the available NA set, and it is a
discrete set of six values: stating it as a continuous interval would let S4
choose 0.9, which this nosepiece does not have. That is the same contract gap
A4 raised from the other side, met independently here.

It reads contracts/ and the recorded responses, and imports no device
(7.2 rule 2).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
import re                                                        # noqa: E402
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

AXIS = "a6"

# The six lenses on the nosepiece. Read from the responses rather than from the
# store, and listed here only so that a lens that stops being served is a
# KeyError rather than a quietly shorter set.
OBJECTIVE_ENTRIES = (
    "objective_mrd70040",
    "objective_mrd70170",
    "objective_mrd70270",
    "objective_mrd77400",
    "objective_mrd71670",
    "objective_mrd71970",
)

OWNED = (
    axc.Inequality(
        id="lateral_resolution",
        parameter="objective_na",
        statement="the diffraction-limited spot must be no larger than the smallest feature the "
                  "observable needs resolved: k*lambda/NA <= required_lateral_resolution",
        needs=("emission_wavelength", "required_lateral_resolution"),
        derived_from="4.5.3 A6 'NA, spatial resolution'",
    ),
    axc.Inequality(
        id="nyquist_sampling",
        parameter="effective_pixel_size",
        statement="the pixel projected into the sample must be at most half the diffraction-"
                  "limited spot: pixel_size/magnification <= k*lambda/(2*NA)",
        needs=("pixel_size", "magnification"),
        derived_from="4.5.3 A6 'magnification, pixel size'",
    ),
    axc.Inequality(
        id="field_of_view",
        parameter="field_of_view",
        statement="the imaged area must cover what the question needs to see at once: "
                  "sensor_active_area/magnification >= required_field_of_view",
        needs=("sensor_active_area", "magnification", "required_field_of_view"),
        derived_from="4.5.3 A6 'field of view'",
    ),
    axc.Inequality(
        id="optical_sectioning",
        parameter="pinhole_diameter",
        statement="out-of-focus rejection must be enough that the observable is not contaminated "
                  "by tracers outside the focal plane",
        needs=("pinhole_diameter",),
        derived_from="4.5.3 A6 'pinhole, optical sectioning'",
    ),
    axc.Inequality(
        id="depth_of_field",
        parameter="axial_range",
        statement="the axial range that stays in focus must cover the tracer's axial excursion "
                  "over the record: n*lambda/NA**2 >= axial_excursion",
        needs=("emission_wavelength", "refractive_index"),
        derived_from="4.5.3 A6 'axial resolution'",
    ),
)

# Every gap in the responses file needs one, because a gap without an id is
# something an assumption cannot point at (common.schema.json kb_gap.gap_id).
GAP_IDS = {
    "pixel_size": "sample_plane_pixel_size_absent",
    "magnification": "magnification_is_not_a_number",
    "sensor_active_area": "sensor_active_area_absent",
    "emission_wavelength": "emission_wavelength_absent",
    # REVISION 3 ASKED `immersion_refractive_index` AND REVISION 4 UNDOES IT.
    # The hazard revision 3 named is real and is unchanged: the bare name
    # returns eight polystyrene entries at E3, which is the TRACER's material
    # and not the immersion medium, and an axis that took them would compute
    # an axial range from the wrong substance with nothing going red.
    #
    # The remedy was in the wrong place. quantities.json rule 1: a name states
    # the quantity and never its subject -- and the rule says in its own text
    # why, that when check 44 refused the subject field the claim moved into
    # the name, "where nothing checks it. A name that asserts its own subject
    # is a subject nothing can refuse." That is exactly what happened here:
    # gluing `immersion` onto the front made the query miss, the miss read as
    # `absent`, and the axis abstained for a reason that was not true. The
    # wrong name produced the safer outcome, which is why it survived a day.
    #
    # Asking the registered name and REFUSING THE ANSWER IN PROSE is the form
    # that keeps both: the name is checkable, and the eight entries are
    # recorded as near-misses on the subject rather than silently missed.
    "refractive_index": "immersion_medium_refractive_index_gap",
}

# The name a missing input goes by on the card, where that differs from the
# name it was asked under. One case, and it matters: `pixel_size` was asked and
# answered absent, but what Nyquist needs is the pixel size *at the sample*,
# which is the sensor pitch divided by a magnification this instrument has
# never measured. A sensor pitch arriving in the store would be a new kb_ref
# and would not close this -- so the card names what is actually missing.
MISSING_NAMES = {"pixel_size": "sample_plane_pixel_size"}

# Inputs this axis needs that the librarian was never asked for, because they
# are not the store's to hold: they are the question's. A gap is what the
# librarian could not supply (4.3.1), so naming these in kb_gaps would claim a
# call that was never made. They are named in `missing` instead.
GOAL_SIDE = ("required_lateral_resolution", "required_field_of_view")

# The second-name check 004 requires, which revision 1 could not finish. Every
# gap above was asked twice: once under the name in GAP_IDS, and once against
# the entries at this pin that could plausibly hold it, fetched by id. These
# four are the ones fetched for the wavelength and the index, and none of them
# carries a number -- the dichroic entry is about which slots are occupied, the
# splitter entry about two names for one mechanism, and the two shutter entries
# about gating. Named here rather than cited as kb_refs: they are evidence that
# nothing is there, and a kb_ref is a dependency, which they are not.
NEGATIVE_EVIDENCE = ("csuw1_dichroic_slots", "csuw1_port_is_the_camera_splitter",
                     "csuw1_shutter_gates_confocal_excitation", "laser_shutter_on_the_combiner")


def _na_numbers(responses: dict) -> list[dict]:
    """The six NA values, carried as the entries served them.

    Grade and source come off the entry rather than being restated (check 21),
    and the precision stays whatever the catalog designated: 004 says not to
    improve on `0.20 is not 0.2 rounded`, and JSON renders that 0.2 -- so the
    figure count lives in `precision` and in the note, which is the only place
    it can live.
    """
    out = []
    for entry_id in OBJECTIVE_ENTRIES:
        entry = responses["entries"][entry_id]
        na = next(n for n in entry["numbers"] if n["name"] == "na")
        nominal = (entry.get("identifiers") or {}).get("nominal_magnification", "")
        out.append({
            "name": f"na_{entry_id.split('_')[-1]}",
            "value": na["value"],
            "unit": na["unit"],
            "source": f"kb:{entry_id}",
            "grade": entry["grade"],
            "precision": na.get("precision", "significant_figures"),
            "note": f"the {nominal} lens on this nosepiece, as the catalog designates it. The "
                    "designation is a string identifier and is deliberately not a number here "
                    "(5.3); what is a number is this NA.",
        })
    return out


def _nyquist(responses: dict):
    """Which (objective, zoom) pairs sample the diffraction-limited spot finely enough.

    Returns (satisfying, failing, band, table) or None when an input is missing.

    Three things this could get wrong, and does not:

    **The pixel size is not a free parameter.** It is selected by a discrete
    pair, and 0.10833 um appears twice -- 40x at 1.5x and 60x at 1x -- with
    opposite verdicts, because the limit moves with NA. So the permitted thing
    is the pair, not the length, and an interval on `effective_pixel_size`
    would be false on its face.

    **Lambda is a band and stays one.** 008 is explicit: four bandpasses
    bracket a band, they do not locate a peak, so the limit is evaluated at
    579.5 and at 610.5 rather than at a centre. A pair counts as satisfying
    only if it satisfies at both edges; one that satisfies at one edge and not
    the other is reported as edge-dependent rather than rounded either way.
    None is, here -- the band's width changes no verdict, which is worth
    knowing and is not a reason to have skipped the care.

    **Objectives are paired to pixel entries by nominal designation.** `20X` in
    an objective's claim against `20x` in a pixel entry's id. 5.3 makes a
    nominal designation a string identifier exact by definition, so matching on
    it is identity and not arithmetic -- which is the one thing 5.3's
    `20.078x` precedent forbids doing with these two quantities.
    """
    served = responses["entries"]
    band = (served.get("filter_ff01_595_31_32_passband") or {}).get("validity", {}).get("wavelength")
    if not band:
        return None
    na_by_designation = {}
    for eid, e in served.items():
        if not eid.startswith("objective_"):
            continue
        m = re.search(r"(\d+)X", e.get("claim", ""))
        na = next((n["value"] for n in e.get("numbers", []) if n["name"] == "na"), None)
        if m and na is not None:
            na_by_designation[m.group(1) + "x"] = (eid, na)
    satisfying, failing, table = [], [], []
    for eid, e in sorted(served.items()):
        m = re.match(r"pixel_size_(\d+x)_zoom_(1x|1_5x)$", eid)
        if not m:
            continue
        pitch = next((n["value"] for n in e.get("numbers", []) if n["name"] == "pixel_size"), None)
        pair = na_by_designation.get(m.group(1))
        if pitch is None or pair is None:
            continue
        obj_id, na = pair
        lo = band["min"] / (4 * na) / 1000.0        # nm -> um
        hi = band["max"] / (4 * na) / 1000.0
        name = f"{m.group(1)}@{m.group(2).replace('_', '.')}"
        (satisfying if pitch <= lo else failing).append(name)
        table.append((name, obj_id, eid, na, pitch, lo, hi))
    if not table:
        return None
    return satisfying, failing, band, table


def evaluate(goal: dict, config: str, caller_id: str, responses: dict, pin: str) -> axc.AxisRun:
    """Every inequality A6 owns, each with a constraint or a reason it has none."""
    run = axc.AxisRun(axis=AXIS, caller_id=caller_id, config=config, kb_version=pin,
                      owned=OWNED, degraded=[])

    absent = {g["observable"] for g in responses["gaps"]}
    # The service answers `absent` to `emission_wavelength`, and the wavelength is
    # nonetheless served -- as a passband on the filter in the red arm, which is
    # the right shape for it. 008: four bandpasses bracket a band, they do not
    # locate a peak. So the name is absent and the quantity is not, and a bound
    # that named it missing while nyquist below computed from it would be two
    # answers to one question inside one card.
    if "filter_ff01_595_31_32_passband" in responses["entries"]:
        absent.discard("emission_wavelength")
    run.kb_refs = axc.refs_from(responses, pin)
    run.kb_gaps = axc.gaps_from(responses, pin, caller_id, GAP_IDS)
    run.numbers = _na_numbers(responses)

    # Stated rather than assumed: a spatial target is on the goal card, and the
    # axis looks for one before saying there is none.
    #
    # BOTH TARGET FORMS, because the one this read is the superseded one. A
    # target names numbers[] in the old form and carries its own value inline
    # in the new one (5.3.1), and the new form is the only one a requirement
    # may use: common.schema.json's `source` says a number the operator CHOSE
    # -- a target, a tolerance, a budget -- carries neither source nor grade,
    # and numbers[] forces both. So reading `number` alone looked past exactly
    # the form a correctly written target has to take. Found 2026-09-20 when
    # the person answered this axis's own abstention with 100 nm and the
    # answer would have been invisible.
    goal_targets = {t.get("number") for t in goal.get("targets", [])}
    goal_targets |= {t.get("metric") for t in goal.get("targets", [])}
    goal_targets.discard(None)
    goal_side_absent = [n for n in GOAL_SIDE
                        if axc.goal_number(goal, n) is None and n not in goal_targets]

    for ineq in OWNED:
        missing = [MISSING_NAMES.get(n, n) for n in ineq.needs
                   if n in absent or n in goal_side_absent]

        if ineq.id == "lateral_resolution":
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                kind="no_input", missing=missing,
                reason="Half of this bound is fully served and the other half is empty. NA came "
                       "back for all six objectives at E3, from 0.20 on the 4x to 1.45 on the "
                       "100x, and it came back only because this axis asked by entry id: "
                       "kb_query(observable=numerical_aperture) answers absent while six entries "
                       "carry numbers[].name = na. What is missing is a wavelength -- asked "
                       "under emission_wavelength and under wavelength, absent both times, and "
                       "then looked for by id in the four entries at this pin that could "
                       "plausibly hold a band: the dichroic slots, the port-is-the-splitter "
                       "entry and the two shutter entries. None of the four carries a number. "
                       "That is the second-name check 004 requires, finished -- and a required "
                       "lateral resolution, "
                       "which the goal does not state -- its one target is one decade on the "
                       "diffusivity, and a decade on a diffusivity is not a length. Without "
                       "lambda the spot size is not computable; without a required resolution "
                       "there is no inequality to compare it against. Either input alone would "
                       "still leave this abstaining, and neither is guessed (P5).",
            ))
            continue

        if ineq.id == "nyquist_sampling":
            computed = _nyquist(responses)
            if computed is None:
                run.outcomes.append(axc.Outcome(
                    inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                    kind="no_input", missing=missing,
                    reason="the calibrated pixel sizes or the passband are not in this response, "
                           "so the comparison cannot be made",
                ))
                continue
            satisfying, failing, band, table = computed
            basis = ["kb:filter_ff01_595_31_32_passband"]
            basis += sorted({f"kb:{obj}" for _, obj, _, _, _, _, _ in table})
            basis += sorted({f"kb:{pix}" for _, _, pix, _, _, _, _ in table})
            rows = "; ".join(
                f"{name} pixel {pitch:.5f} um against {lo:.4f}-{hi:.4f} um at NA {na}"
                for name, _, _, na, pitch, lo, hi in sorted(table)
            )
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter="objective_zoom_pair", state="returned",
                allowed_set={
                    "parameter": "objective_zoom_pair",
                    "values": sorted(satisfying),
                    "excluded": sorted(failing),
                    "basis": basis,
                },
                reason=(
                    "This is the bound this axis said would close on one calibration per "
                    "configuration, and it has. Twelve sample-plane pixel sizes at E2 measured on "
                    "this instrument, six objective NAs at E3, and the red arm's passband at E3 "
                    "are enough to compare a pixel against a diffraction-limited spot without "
                    "back-deriving anything. " + rows + ". Four of twelve satisfy "
                    "pixel <= lambda/(4*NA) at both edges of the band and eight fail at both; "
                    "none is edge-dependent, so the band's width changes no verdict here. "
                    "**The permitted thing is the pair and not the pixel size**, which is why "
                    "this is a set and not an interval: 0.10833 um appears twice, at 40x with "
                    "1.5x zoom and at 60x with 1x, and it satisfies in the first and fails in the "
                    "second because the limit moves with NA. A bound stated on the length alone "
                    "would be false for one of them whichever way it was written. "
                    "**Magnification is not an input any more and that is the real change.** The "
                    "earlier revision named it missing because the pixel size then available "
                    "would have been a sensor pitch needing division by a magnification this "
                    "instrument has never measured -- 5.3's 20.078x precedent. These twelve are "
                    "measured at the sample plane already, so nothing is divided and the "
                    "refusal that blocked this bound no longer applies to it."
                ),
            ))
            continue
            continue

        if ineq.id == "field_of_view":
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                kind="no_input", missing=missing,
                reason="Three inputs and none of them present. The sensor's active area is not "
                       "in the store; magnification is the designation described above; and "
                       "nothing states how much area has to be in frame at once. That last one "
                       "is where this axis has to stop rather than reason: how many tracers a "
                       "measurement needs in view is A2's question, and 4.5.3 rule (b) forbids "
                       "taking a sibling's output as input, so the requirement can only arrive "
                       "on the goal card. It is not there.",
            ))
            continue

        if ineq.id == "optical_sectioning":
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                kind="not_constraining",
                reason="This configuration runs with the spinning disk out -- the served entry "
                       "states that with the disk out the same hardware serves widefield "
                       "fluorescence and brightfield, and that disk-out is a required selector "
                       "value on configurations that already exist rather than a configuration "
                       "of its own. With the disk out there is no pinhole in the path, so there "
                       "is no sectioning parameter for this bound to constrain. Recorded as "
                       "not_constraining and not as no_input, and the difference is the next "
                       "action: nothing to measure here, because the parameter does not exist on "
                       "this configuration. What does not vanish with the pinhole is the "
                       "out-of-focus light it would have rejected; that lands on depth_of_field "
                       "below, which is where this axis carries it rather than dropping it.",
            ))
            continue

        if ineq.id == "depth_of_field":
            run.outcomes.append(axc.Outcome(
                inequality_id=ineq.id, parameter=ineq.parameter, state="abstained",
                kind="no_input", missing=missing,
                reason="One of three inputs is present, and the split between the other two is "
                       "worth reading. NA is served for all six objectives. The immersion medium "
                       "is answered and its refractive index is not, and the second half needs "
                       "saying precisely because the query does not say it: asking for "
                       "`immersion` returns in_published_table, pointing at the devices table's "
                       "immersion column, while asking for `refractive_index` returns EIGHT "
                       "entries at E3 and every one of them is polystyrene -- the tracer's "
                       "material, not the medium the lens sits in. The name is answered and the "
                       "subject is not, and kb_query has no subject argument, so the server "
                       "reports no gap at all and the discrimination is the caller's: its own "
                       "description says to read `identifiers` on each row to tell a class "
                       "apart. Asking from the subject side instead -- kb_query(water) -- "
                       "returns the 40x water objective and nothing about water. So the store "
                       "knows which medium each lens takes and holds no index for any of the "
                       "three. A medium name is a string identifier; turning one into a "
                       "number here would be this axis inventing knowledge, which P14 puts in "
                       "the librarian's hands and P2 grades E6 and refuses. And the eight are "
                       "not a fallback at any grade: a bead is not an immersion medium, so they "
                       "are not a worse answer to this question, they are an answer to another "
                       "one. One literature entry per medium closes it. The wavelength is the "
                       "same input missing from lateral_resolution, and it is not independent "
                       "of this one -- the index is dispersive, so pinning it at a measured "
                       "wavelength may move this gap from absent to condition_mismatch rather "
                       "than close it. Worth recording even if all three arrived: the "
                       "requirement side is not available to this axis either, because how far a "
                       "tracer wanders out of focus during a record is the diffusivity -- which "
                       "is this question's observable, the thing being measured -- times the "
                       "record length, which is A2's parameter. So this bound would still state "
                       "a range and let S4 intersect it, rather than deciding it here.",
            ))
            continue

        run.outcomes.append(axc.Outcome(
            inequality_id=ineq.id, parameter=ineq.parameter, state="failed",
            reason="every input is present and this axis has no code to emit the constraint: "
                   "that is a gap in this file, not an abstention (4.5.2.1)",
        ))

    run.notes.append(
        "Answered by the librarian service rather than by reading the store, which is what makes "
        f"degraded empty here: {len(run.kb_refs)} entries came back with their own grades and "
        f"{len(run.kb_gaps)} questions came back absent, all at the pinned {pin}, and every call "
        "is in librarian_agent/queries/log.jsonl under this caller_id. The transport was a stdio "
        "client rather than this session's attached server, which has failed every call since "
        "07:47:44Z: same server file, same pin, same caller_id, same log, and the answers carry "
        "the same answered_from. What the transport cannot change is what the service said."
    )
    run.notes.append(
        "The finding this axis exists to report: NA is in the store six times and the query for "
        "it says absent. kb_query(observable=numerical_aperture) returns kind=absent at this "
        "pin, while objective_mrd70040 and its five siblings each carry numbers[].name = na at "
        "E3. Nothing is indexed under that observable name, so the query misses what the store "
        "holds. A gap recorded off that query would have been false, and this card would have "
        "been the second in this fan-out to carry one."
    )
    run.notes.append(
        "001 and 004 both expected the diffraction limit to compute here, and it still does "
        "not, but only half of the reason survives. The wavelength has arrived and it is a "
        "band rather than a peak -- the red arm is position 3 and the filter there passes "
        "579.5 to 610.5 nm, at E3 -- so the inputs the six objectives were said to carry are "
        "now complete on the instrument side, and nyquist above computes from exactly them. "
        "What is still missing is not the librarian's: a required lateral resolution is a "
        "property of the question, and this goal card states no spatial target at all. Its "
        "only target is one decade on a diffusivity, which is not a length. So the "
        "diffraction limit is computable and there is nothing to compare it against."
    )
    run.notes.append(
        "Revision 2 exists to finish the second-name check revision 1 could not. 004 requires it "
        "because an empty kb_query is not evidence of absence in this store -- eight of ten such "
        "calls missed knowledge held under another name. Every one of the five gaps here was "
        "asked twice: under its own name, and then by entry id against whatever at this pin "
        "could hold it. The wavelength and the index were the two left open, and both are now "
        "settled as absent -- " + ", ".join(NEGATIVE_EVIDENCE) + " were fetched and none of "
        "them carries a number. Nothing in the five verdicts moved; what moved is that they are "
        "now checked rather than assumed."
    )
    run.notes.append(
        "One answer came back as neither an entry nor an absence. `immersion` returns "
        "in_published_table, naming the devices table in this agent's own snapshot and the "
        "column, with a sha256. It is not recorded as a gap on this card, for two reasons worth "
        "separating. The medium is already in hand from the six objective entries' identifiers, "
        "so nothing here depends on the pointer. And the pointer does not resolve against this "
        "agent's envelope: the served hash is the table as of the pinned kbv-49feb73662b7, while "
        "envelope/snapshot.json holds kbv-67f9ad766d92, and the two tables differ. A caller that "
        "pins an older version than its snapshot is told to look somewhere its own copy does not "
        "match. That is a finding for the librarian and the manager, not something to bake into "
        "a card as a hash nobody can verify."
    )
    run.notes.append(
        "constraints[] is empty and there is one candidate it could have held: the NA set. It is "
        "six discrete values and `interval` can only say a continuous range, so returning it "
        "would license S4 to choose an NA of 0.9 that this nosepiece does not have. Abstaining "
        "is the honest outcome, and the contract gap is the same one A4 raised from the other "
        "side -- a bound with grounds that constrains something other than a number. Two axes "
        "met it independently; it is raised with manager-microscope, not worked around."
    )
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A6: resolution, field of view, sectioning (4.5.3).")
    parser.add_argument("goal", type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--caller-id", required=True)
    parser.add_argument("--kb-version", required=True,
                        help="the pin to answer at. Not read from the store: the store moves and "
                             "siblings have to agree (check 33)")
    parser.add_argument("--responses", required=True, type=Path,
                        help="what the librarian returned for this caller_id at that pin")
    parser.add_argument("--revision", type=int, default=1,
                        help="the card's revision. Raised on any edit (5.4), and the caller_id "
                             "has to carry the same number: check 33 wants qid:v<revision>:"
                             "config:axis, because the id is the server's isolation unit and a "
                             "re-run must not inherit the session it replaces")
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
    rc = axc.write(run, goal, goal.get("qid", ""), created_at)
    if rc == 0 and args.revision != 1:
        # axis_common.to_card() writes revision 1, which is right for a first
        # run and wrong for every re-run. Patched here rather than there: that
        # file is shared with the other microscope seat and nothing refuses a
        # collision in it, so a change to it is asked for by card (6.2.1).
        out = (axc.AGENT / "questions" / goal.get("qid", "")
               / f"axis_{args.config}_{AXIS}.json")
        card = json.loads(out.read_text())
        card["revision"] = args.revision
        out.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n")
        print(f"revision -> {args.revision}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
