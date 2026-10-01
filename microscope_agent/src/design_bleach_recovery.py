"""S3 for bleach_recovery_diffusivity: the seven axes of a bleach-and-recover design.

Written for mic-20260930-001 (card 051). The seven axis modules beside this
one were built for single-particle questions -- tracer_diffusivity,
tracer_brightness -- and every bound they own sizes a displacement fit or a
photon count per particle. A disc bleached as a column and watched refill has
different bounds: a spot radius, a bleach duration and a frame interval that
are all set against the recovery time tau = w^2 / (4 D), a chamber depth set
against the radius by the defocus cone, and a bead count in the bleached
column. So this module owns those bounds for all seven axes rather than
growing a branch in each of seven shared files (the card's instruction: keep
an axis's helpers in its own module, not in axis_common.py).

Deterministic Python, no model, and no device imported. It reads the goal
card, the librarian's answers for one caller_id, and nothing else.

WHY MOST BOUNDS HERE ARE PRECONDITIONS AND NOT INTERVALS. The estimator fixes
its validity as ratios to the fitted tau: bleach <= tau/10, frame interval
<= tau/5, window >= 10 tau. tau is set by the radius, which S4 chooses, so a
frame-interval interval in seconds would have to be a function of a value not
yet chosen. An interval carrying `varies_with` would still need numbers at a
point. A precondition says exactly what is true -- set the frame interval to
at most a fifth of the expected recovery time at the chosen radius -- and it
propagates to the plan instead of being intersected. The radius itself is an
absolute interval, because both of its ends are fixed by the optics.

The responses file is built from librarian_agent/queries/log.jsonl (what the
service returned, under this caller_id) and the store at the pinned commit
(the claim text of what it returned). Both are the service's record; nothing
here reads the store to answer a question the service was not asked.
"""

from __future__ import annotations

import os
import sys

# The same shadowing guard every module in this directory carries: this
# directory holds operator.py, which shadows the standard library's operator.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
import math                                                      # noqa: E402
import subprocess                                                # noqa: E402
from pathlib import Path                                         # noqa: E402

_spec = importlib.util.spec_from_file_location("axis_common", os.path.join(_HERE, "axis_common.py"))
ac = importlib.util.module_from_spec(_spec)
sys.modules["axis_common"] = ac          # dataclasses resolve their module by name
_spec.loader.exec_module(ac)

REPO = ac.REPO
AGENT = ac.AGENT
K_B = 1.380649e-23
GRADES = ["E1", "E2", "E3", "E4", "E5", "E6"]
OBSERVABLE = "bleach_recovery_diffusivity"


# --------------------------------------------------------------------------- #
# the service's answers, for one caller_id
# --------------------------------------------------------------------------- #

# The service's `near_names` for each absent name asked here, transcribed from
# its replies because the query log does not record them. An empty list is the
# service's answer "searched, nothing near"; the one non-empty answer is kept as
# it came. Every name an axis below asks must appear, or the card is refused.
NEAR_NAMES_SERVED = {
    "tracer_brightness": [], "F8801": [], "bleaching_rate": [], "dmd": [],
    "light_engine_channel_sets": [], "light_engine_output_power": [], "drift": [],
    "illumination_numerical_aperture": [], "dmd_pixel_size_at_sample": ["pixel_size"],
}


def build_responses(caller_id: str, pin: str, commit: str) -> dict:
    log = REPO / "librarian_agent" / "queries" / "log.jsonl"
    entries: dict[str, dict] = {}
    gaps: list[dict] = []
    for line in log.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("caller_id") != caller_id or rec.get("kb_version") != pin:
            continue
        answered = {"kb_version": pin, "commit": commit}
        for got in rec.get("returned") or []:
            eid = got["entry_id"] if isinstance(got, dict) else got
            body = json.loads(subprocess.check_output(
                ["git", "show", f"{commit}:librarian_agent/kb/entries/{eid}.json"], cwd=REPO))
            entries[eid] = {"grade": body["grade"], "claim": body["claim"], "answered_from": answered}
        for kind in rec.get("gaps") or []:
            if any(g["observable"] == rec["observable"] for g in gaps):
                continue
            gaps.append({"observable": rec["observable"], "kind": kind, "tool": rec["tool"],
                         "searched": ["kb/entries", "kb/exports"], "asked_at": rec["asked_at"],
                         "answered_from": answered,
                         "near_names": rec.get("near_names", NEAR_NAMES_SERVED.get(rec["observable"]))})
            if gaps[-1]["near_names"] is None:
                raise ac.AxisError(f"no near_names on record for {rec['observable']!r}")
    return {"pin": pin, "caller_id": caller_id, "entries": entries, "gaps": gaps}


# --------------------------------------------------------------------------- #
# numbers
# --------------------------------------------------------------------------- #

def sig1(x: float) -> float:
    if x == 0:
        return 0.0
    e = math.floor(math.log10(abs(x)))
    return float(round(x / 10 ** e) * 10 ** e)


def worst(*grades: str) -> str:
    return max(grades, key=GRADES.index)


class Numbers:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.by: dict[str, dict] = {}

    def add(self, row: dict) -> dict:
        self.rows.append(row)
        self.by[row["name"]] = row
        return row

    def from_kb(self, name: str, entry_id: str, value: float, unit: str, grade: str,
                note: str = "", precision: str = "significant_figures") -> dict:
        row = {"name": name, "value": value, "unit": unit, "source": f"kb:{entry_id}",
               "grade": grade, "precision": precision}
        if note:
            row["note"] = note
        return self.add(row)

    def computed(self, name: str, label: str, value_si: float, si_per_unit: float, unit: str,
                 formula: str, inputs: list[str], note: str) -> dict:
        grade = worst("E4", *(self.by[i]["grade"] for i in inputs))
        value = sig1(value_si / si_per_unit)
        return self.add({"name": name, "value": value, "unit": unit,
                         "source": f"computed:{label}", "grade": grade,
                         "precision": "order_of_magnitude", "formula": formula,
                         "inputs": inputs, "note": note})

    def si(self, name: str, per_unit: float) -> float:
        return float(self.by[name]["value"]) * per_unit


def kb_value(responses: dict, entry_id: str) -> bool:
    return entry_id in responses["entries"]


def expected_diffusivity(nums: Numbers, goal: dict, responses: dict, run: ac.AxisRun) -> bool:
    """Stokes-Einstein over the store's water and room, and the goal's nominal size.

    Returns False (and records why) when the store did not serve an input. The
    value is E5, because the diameter is the catalogue's nominal size reaching
    the bench through the person's identification; it sizes ranges and is
    replaced by the simulation's prediction and, at E3, by the lot certificate.
    """
    need = ["lab_ambient_temperature", "water_viscosity_293k"]
    if not all(kb_value(responses, e) for e in need):
        return False
    d = ac.goal_number(goal, "tracer_diameter")
    if d is None:
        raise ac.AxisError("the goal card carries no tracer_diameter")
    nums.from_kb("ambient_temperature", "lab_ambient_temperature", 293, "K", "E3",
                 note="the room, read; the sample is not actuated and has no thermometer, so this "
                      "stands in for the sample. A kelvin moves water's viscosity about 2 per cent, "
                      "a tie in explore mode")
    nums.from_kb("viscosity", "water_viscosity_293k", 0.001, "Pa*s", "E3",
                 note="pure water, valid 288 to 298 K. The beads are suspended in what the vendor "
                      "ships them in, diluted by the person; if the diluent is not water this "
                      "number is the wrong one")
    if "F8801" not in {g["observable"] for g in responses["gaps"]}:
        raise ac.AxisError("an axis standing on the bead identity must have asked the store for "
                           "it (F8801) under its own caller_id, so its assumption can name the gap")
    run.assumptions = [a for a in goal.get("assumptions", []) if "tracer_diameter" in a.get("numbers", [])]
    nums.add({"name": "tracer_diameter", "value": d["value"], "unit": d["unit"],
              "source": d["source"], "grade": d["grade"], "precision": d["precision"],
              "origin": "goal.json#tracer_diameter"})
    t = nums.si("ambient_temperature", 1.0)
    eta = nums.si("viscosity", 1.0)
    dia = nums.si("tracer_diameter", 1e-6)
    nums.computed("tracer_diffusivity_expected", "stokes_einstein",
                  K_B * t / (3 * math.pi * eta * dia), 1e-12, "um^2/s",
                  "k_B*ambient_temperature/(3*pi*viscosity*tracer_diameter)",
                  ["ambient_temperature", "viscosity", "tracer_diameter"],
                  "Stokes-Einstein, unbounded medium. FOR SCALE ONLY: it sets which radii are "
                  "worth weighing and is not a prediction this plan reports. The simulation's "
                  "recovery times are awaited and replace the tau it implies; the lot "
                  "certificate's measured diameter would replace the nominal one at E3")
    run.kb_refs = ac.refs_from(responses, run.kb_version)
    return True


# --------------------------------------------------------------------------- #
# the seven axes
# --------------------------------------------------------------------------- #

def ineq(id_: str, parameter: str, statement: str, needs: tuple[str, ...], derived: str) -> ac.Inequality:
    return ac.Inequality(id_, parameter, statement, needs, derived)


AXIS_BOUNDS: dict[str, tuple[ac.Inequality, ...]] = {
    "a1": (
        ineq("bead_count_in_bleached_column", "bead_count_in_bleached_column",
             "enough beads in the bleached column that one recovery curve resolves tau",
             ("recovery_fit_scatter_vs_bead_count", "bleaching_rate"), "the estimator's fit"),
        ineq("photon_budget_per_frame", "exposure_time",
             "an exposure long enough to count the column's photons, short against tau",
             ("tracer_brightness",), "signal per frame"),
        ineq("number_density_under_the_objective", "tracer_number_density",
             "the number density the person's dilution produces",
             ("tracer_stock_concentration", "dilution_factor"), "the stock and the dilution"),
    ),
    "a2": (
        ineq("frame_interval_resolves_recovery", "frame_interval",
             "frame interval <= tau/5", ("tracer_diffusivity_expected",), "estimator validity"),
        ineq("window_reaches_plateau", "max_recovery_time",
             "max_recovery_time >= 10 tau", ("tracer_diffusivity_expected",), "estimator validity"),
        ineq("pre_bleach_baseline", "pre_bleach_frame_count",
             "enough pre-bleach frames that the normalisation is not the noisiest term",
             ("tracer_diffusivity_expected",), "normalisation"),
        ineq("independent_repeats", "repeat_count",
             "repeats enough to state a spread of D", ("recovery_fit_scatter_vs_bead_count",),
             "the scatter of one curve"),
    ),
    "a3": (
        ineq("imaging_bleach_small_against_recovery", "imaging_dose_rate",
             "bleaching by the imaging light over the window small against the bleach dip",
             (), "the estimator's reference normalisation"),
        ineq("sealed_still_chamber", "chamber_seal",
             "no evaporation-driven flow across the record", (), "the column must not be advected"),
        ineq("sample_temperature_uncontrolled", "sample_temperature",
             "temperature carried as an uncontrolled condition", ("kb:sample_temperature_not_actuated",),
             "viscosity's temperature dependence"),
    ),
    "a4": (
        ineq("patterned_source_is_the_spectra", "excitation_source",
             "the DMD patterns the Spectra III, named by its MM label", ("kb:mm_label_lightengine_is_the_spectra_iii",),
             "the staging pairing"),
        ineq("excitation_line_for_580", "excitation_line",
             "the Spectra line that excites near 580 nm", ("light_engine_channel_sets",), "the dye"),
        ineq("dmd_core_and_power_known", "bleach_power_at_sample",
             "the power the bleach delivers at the sample", ("light_engine_output_power",),
             "the dose the person decides"),
    ),
    "a5": (
        ineq("drift_small_against_radius", "max_recovery_time",
             "lateral drift over the window <= w/10", ("drift",), "the fixed analysis disc"),
    ),
    "a6": (
        ineq("edge_sharp_against_radius", "bleach_radius",
             "w >= 10 x the lateral resolution, so the in-focus edge is sharp against w",
             ("kb:objective_mrd70270", "kb:filter_ff01_595_31_32_passband"), "the sharp-disc model"),
        ineq("radius_sampled_by_camera", "bleach_radius",
             "w >= 10 camera pixels", ("kb:pixel_size_20x_zoom_1x",), "the radial profile"),
        ineq("reference_region_in_field", "bleach_radius",
             "6 w <= half the camera field, so a reference region 5 w away fits",
             ("kb:camera_sensor_geometry", "kb:pixel_size_20x_zoom_1x"), "the estimator's reference"),
        ineq("dmd_field_covers_reference", "bleach_radius",
             "the DMD's illuminated field holds the disc and the reference region",
             ("dmd_pixel_size_at_sample",), "the estimator's reference"),
        ineq("column_holds_through_depth", "chamber_depth",
             "defocus blur at the chamber faces <= w/10", ("kb:objective_mrd70270",
             "kb:water_refractive_index_605nm_293k"), "the column geometry"),
        ineq("objective_choice", "objective_zoom_pair",
             "objectives whose cone permits a column and whose pixel size is calibrated",
             ("kb:objective_mrd70270", "kb:objective_mrd70170"), "column geometry"),
    ),
    "a7": (
        ineq("bleach_short_against_recovery", "bleach_duration",
             "bleach duration <= tau/10, and as short as the bleach rate allows",
             ("tracer_diffusivity_expected",), "estimator validity"),
        ineq("bleach_fast_enough_for_radius", "bleach_radius",
             "w >= sqrt(40 D t_bleach), the radius whose tau/10 holds the bleach",
             ("bleaching_rate",), "estimator validity and the bleach rate"),
    ),
}


def run_axis(axis: str, goal: dict, caller_id: str, pin: str, responses: dict) -> ac.AxisRun:
    run = ac.AxisRun(axis=axis, caller_id=caller_id, config="widefield_inline",
                     kb_version=pin, owned=AXIS_BOUNDS[axis])
    if goal["observable"]["name"] != OBSERVABLE:
        raise ac.AxisError(f"this module owns the bounds of {OBSERVABLE}, and the goal asks for "
                           f"{goal['observable']['name']!r}")
    nums = Numbers()
    gap_ids = {g["observable"]: f"{g['observable'].lower()}_absent" for g in responses["gaps"]}
    run.kb_gaps = ac.gaps_from(responses, pin, caller_id, gap_ids)
    run.kb_refs = ac.refs_from(responses, pin)
    O = ac.Outcome
    out = run.outcomes

    if axis == "a1":
        out.append(O("bead_count_in_bleached_column", "bead_count_in_bleached_column", "abstained",
                     kind="no_input", missing=["recovery_fit_scatter_vs_bead_count", "bleaching_rate"],
                     reason="how many beads one curve needs depends on how deep the bleach is and on "
                            "how much one curve scatters at that count. The first closes by the bare-bead "
                            "pre-measurement (the bleach depth a given dose reaches), the second arrives "
                            "from the simulation as the scatter of the fitted D against beads in the disc. "
                            "Neither is guessed here; the plan carries a provisional count as an assumption"))
        out.append(O("photon_budget_per_frame", "exposure_time", "abstained", kind="no_input",
                     missing=["tracer_brightness"],
                     reason="no photon rate per bead exists for these beads under this light and cannot "
                            "be asked for: it depends on this dye, this lot, the Spectra line and this "
                            "camera together. One short run of bare beads on the coverslip under the "
                            "planned line through the DMD closes it, and the same run gives the bleaching "
                            "rate. That run spends no sample the measurement needs"))
        out.append(O("number_density_under_the_objective", "tracer_number_density", "abstained",
                     kind="no_input", missing=["tracer_stock_concentration", "dilution_factor"],
                     reason="the vendor page the person supplied gives no stock concentration, and no "
                            "dilution has been chosen. Both are the person's: the concentration printed "
                            "on the bottle or the lot certificate, and the dilution they plan. The bead "
                            "count the column needs is then that density times pi w^2 h"))
        run.notes.append("Every bound here waits on an acquisition or on the person, and each reason "
                         "names which.")

    elif axis == "a2":
        if expected_diffusivity(nums, goal, responses, run):
            basis = ["tracer_diffusivity_expected"]
            out.append(O("frame_interval_resolves_recovery", "frame_interval", "returned",
                         precondition={"parameter": "frame_interval", "basis": basis,
                                       "requires": "set the frame interval to at most one fifth of the "
                                       "expected recovery time tau = w^2/(4 D) at the chosen radius, and "
                                       "refuse the curve if the fitted tau comes out under five frame "
                                       "intervals, reporting D only as a lower bound"}))
            out.append(O("window_reaches_plateau", "max_recovery_time", "returned",
                         precondition={"parameter": "max_recovery_time", "basis": basis,
                                       "requires": "record at least ten expected recovery times after the "
                                       "bleach, and refuse the curve if the fitted tau exceeds a tenth of "
                                       "the window, reporting D only as an upper bound; the tail is slow "
                                       "(0.91 of full at 10 tau), so the plateau is not reached sooner"}))
            out.append(O("pre_bleach_baseline", "pre_bleach_frame_count", "returned",
                         precondition={"parameter": "pre_bleach_frame_count", "basis": basis,
                                       "requires": "record at least ten frames before the bleach at the same "
                                       "frame interval and exposure, so the pre-bleach mean that both "
                                       "normalisations divide by carries a third of one frame's noise"}))
        else:
            for i in AXIS_BOUNDS["a2"][:3]:
                out.append(O(i.id, i.parameter, "abstained", kind="no_input",
                             missing=["tracer_diffusivity_expected"],
                             reason="the store did not serve the room temperature and water's viscosity "
                                    "under this caller, so no expected recovery time can be set"))
        out.append(O("independent_repeats", "repeat_count", "abstained", kind="no_input",
                     missing=["recovery_fit_scatter_vs_bead_count"],
                     reason="the number of bleaches needed to state a spread of D depends on how much "
                            "one curve scatters at the planned bead count, which the simulation is "
                            "computing; awaited, not guessed. Each repeat is a fresh field, so repeats "
                            "cost time and not sample"))
        run.notes.append("The expected diffusivity is computed for scale from the nominal size and is "
                         "E5; every bound here is written as a rule in tau so that the simulation's "
                         "predicted recovery times, when they arrive, move the numbers and not the rules.")

    elif axis == "a3":
        out.append(O("imaging_bleach_small_against_recovery", "imaging_dose_rate", "returned",
                     precondition={"parameter": "imaging_dose_rate", "basis": [],
                                   "requires": "keep the imaging light's bleaching over the whole window under "
                                   "a tenth of the bleach dip: with a dip of at least 30 per cent made in at "
                                   "most tau/10 and a window of at least 10 tau, the bleach's dose rate must "
                                   "exceed the imaging's time-averaged dose rate about 360-fold. Reach it by "
                                   "lowering the imaging level and by exposing only during each frame, and "
                                   "verify it on the reference region, whose decay over the record is this "
                                   "loss measured directly"}))
        out.append(O("sealed_still_chamber", "chamber_seal", "returned",
                     precondition={"parameter": "chamber_seal", "basis": [],
                                   "requires": "seal the chamber on every edge before the record and let it "
                                   "settle; an open edge drives evaporation flow, and a flow that carries the "
                                   "bleached column sideways reads as fast recovery. Confirm stillness by "
                                   "watching the bleached disc's centre in the first post-bleach frames: it "
                                   "must not move"}))
        if kb_value(responses, "sample_temperature_not_actuated"):
            out.append(O("sample_temperature_uncontrolled", "sample_temperature", "returned",
                         precondition={"parameter": "sample_temperature",
                                       "basis": ["kb:sample_temperature_not_actuated"],
                                       "requires": "record the room temperature at the start and end of each "
                                       "record; nothing actuates the sample, so temperature is a condition "
                                       "of the result and not a setting of the plan"}))
        else:
            out.append(O("sample_temperature_uncontrolled", "sample_temperature", "abstained",
                         kind="no_input", missing=["sample_temperature_not_actuated"],
                         reason="the store did not answer whether the sample temperature is actuated"))
        run.notes.append("The dose-rate bound rests on the registered estimator's own validity ratios, "
                         "which are contract text and not numbers, so its basis is empty by design.")

    elif axis == "a4":
        if kb_value(responses, "mm_label_lightengine_is_the_spectra_iii"):
            out.append(O("patterned_source_is_the_spectra", "excitation_source", "returned",
                         precondition={"parameter": "excitation_source",
                                       "basis": ["kb:mm_label_lightengine_is_the_spectra_iii"],
                                       "requires": "drive the excitation as the Micro-Manager device "
                                       "LightEngine (the Spectra III), which the staging device table "
                                       "records as the engine the DMD patterns; load the DMD on a core "
                                       "pinned to device interface 71, which the same table requires; use "
                                       "the DMD for both the bleach disc and the full-field imaging pattern "
                                       "so the reference region sees the same imaging light; and set the "
                                       "light path to widefield, with the spinning disk out of it, by hand"}))
        else:
            out.append(O("patterned_source_is_the_spectra", "excitation_source", "abstained",
                         kind="no_input", missing=["mm_label_lightengine_is_the_spectra_iii"],
                         reason="the store did not answer which MM label the Spectra III carries"))
        out.append(O("excitation_line_for_580", "excitation_line", "abstained", kind="no_input",
                     missing=["light_engine_channel_sets"],
                     reason="the Spectra III has eight channels whose set is unread, so which line "
                            "excites these beads near 580 nm is not known. Closed by reading the "
                            "engine's channel names on the microscope computer before the run; the DMD "
                            "itself selects no wavelength"))
        out.append(O("dmd_core_and_power_known", "bleach_power_at_sample", "abstained", kind="no_input",
                     missing=["light_engine_output_power"],
                     reason="no power at the sample has been measured for the Spectra through the DMD; "
                            "every power the store holds there is for the confocal lasers or the trap. "
                            "Closed by a power-meter reading at the sample plane with the bleach disc "
                            "displayed, at the line and level the bleach will use. Separately, the safety "
                            "file holds no limit for the DMD or the Spectra, so the bleach dose is the "
                            "person's decision before anything on this path runs"))

    elif axis == "a5":
        out.append(O("drift_small_against_radius", "max_recovery_time", "abstained", kind="no_input",
                     missing=["drift"],
                     reason="no lateral drift rate is in the store. The bare-bead pre-measurement closes "
                            "it too if the beads stick to the glass: track them over the planned window "
                            "and the motion they share is the drift. Then the window must satisfy drift x "
                            "max_recovery_time <= w/10, and since the window grows as w^2 and the budget "
                            "as w, drift caps the radius from above"))

    elif axis == "a6":
        have = responses["entries"]
        need = ["objective_mrd70270", "objective_mrd70170", "pixel_size_20x_zoom_1x",
                "camera_sensor_geometry", "filter_ff01_595_31_32_passband",
                "water_refractive_index_605nm_293k"]
        missing = [e for e in need if e not in have]
        if missing:
            raise ac.AxisError(f"A6 was not served {missing}; ask before running")
        nums.from_kb("na", "objective_mrd70270", 0.8, "1", "E3", note="the 20x, MRD70270")
        nums.from_kb("filter_centre_wavelength", "filter_ff01_595_31_32_passband", 595, "nm", "E3",
                     note="the red path's emission band, which the bench calls 605. The beads emit near "
                          "605 nm by the vendor page; 595 against 605 is a tie")
        nums.from_kb("pixel_size", "pixel_size_20x_zoom_1x", 0.32373, "um", "E2")
        nums.from_kb("refractive_index", "water_refractive_index_605nm_293k", 1.3325138, "1", "E3",
                     note="water at 605 nm and 20 C. The suspension is mostly water once diluted")
        nums.computed("lateral_resolution", "rayleigh",
                      0.61 * 595e-9 / 0.8, 1e-6, "um",
                      "0.61*filter_centre_wavelength/na", ["filter_centre_wavelength", "na"],
                      "the in-focus edge width of the bleached disc as the camera sees it")
        nums.computed("bleach_radius_min", "ten_resolution_elements",
                      10 * nums.si("lateral_resolution", 1e-6), 1e-6, "um",
                      "10*lateral_resolution", ["lateral_resolution"],
                      "a soft edge read with the sharp-disc model biases D low by 2 to 4x (the "
                      "observable's note); an edge a tenth of w keeps that inside a tie")
        # The pixel count enters from the store rather than as a card number:
        # a count times a length has no unit in units.json, so this value is
        # resolved against kb:camera_sensor_geometry (2400 pixels) and not
        # recomputed. Everything downstream of it is recomputed.
        nums.add({"name": "field_width", "value": sig1(2400 * 0.32373), "unit": "um",
                  "source": "computed:sensor_times_pixel", "grade": "E4",
                  "precision": "order_of_magnitude", "formula": "sensor_pixels_x*pixel_size",
                  "inputs": ["kb:camera_sensor_geometry", "pixel_size"],
                  "note": "the camera's field at 20x and 1x zoom, full chip: 2400 pixels "
                          "(kb:camera_sensor_geometry) times the calibrated pixel"})
        nums.computed("bleach_radius_max", "reference_region_fits",
                      nums.si("field_width", 1e-6) / 12, 1e-6, "um",
                      "field_width/12", ["field_width"],
                      "disc at the centre, reference region 5 w from it and w wide, both inside half "
                      "the field: 6 w <= field/2")
        nums.computed("bleach_radius_min_sampling", "ten_pixels",
                      10 * 0.32373e-6, 1e-6, "um", "10*pixel_size", ["pixel_size"],
                      "ten pixels across the radius, so the radial profile has a half-contrast point "
                      "worth the name")
        s = 0.8 / 1.3325138
        nums.computed("defocus_cone_slope", "objective_na_in_water",
                      s / math.sqrt(1 - s * s), 1.0, "1",
                      "(na/refractive_index)/(1-(na/refractive_index)**2)**0.5",
                      ["na", "refractive_index"],
                      "tan of the steepest ray the objective admits in water. The DMD path's own "
                      "illumination NA is unknown (illumination_numerical_aperture_absent) and cannot "
                      "exceed the objective's, so this is the steepest the disc can spread: a "
                      "conservative slope")
        out.append(O("edge_sharp_against_radius", "bleach_radius", "returned",
                     interval={"parameter": "bleach_radius", "unit": "um",
                               "min": nums.by["bleach_radius_min"]["value"],
                               "basis": ["bleach_radius_min"], "precision": "order_of_magnitude"}))
        out.append(O("radius_sampled_by_camera", "bleach_radius", "returned",
                     interval={"parameter": "bleach_radius", "unit": "um",
                               "min": nums.by["bleach_radius_min_sampling"]["value"],
                               "basis": ["bleach_radius_min_sampling"], "precision": "order_of_magnitude"}))
        out.append(O("reference_region_in_field", "bleach_radius", "returned",
                     interval={"parameter": "bleach_radius", "unit": "um",
                               "max": nums.by["bleach_radius_max"]["value"],
                               "basis": ["bleach_radius_max"], "precision": "order_of_magnitude"}))
        out.append(O("dmd_field_covers_reference", "bleach_radius", "abstained", kind="no_input",
                     missing=["dmd_pixel_size_at_sample"],
                     reason="the DMD's projection onto the sample is unmeasured, so whether its field "
                            "is as large as the camera's is not known. Closed at the bench by "
                            "displaying a known pattern and imaging it, which gives the DMD pixel at the "
                            "sample and its field in one frame. If its field is smaller, it caps the "
                            "radius below the camera's bound"))
        slope = nums.by["defocus_cone_slope"]["value"]
        out.append(O("column_holds_through_depth", "chamber_depth", "returned",
                     precondition={"parameter": "chamber_depth", "basis": ["defocus_cone_slope"],
                                   "requires": f"make the chamber no deeper than 0.2 x bleach_radius / "
                                   f"defocus_cone_slope, which is {0.2 / slope:.2g} x the radius at the "
                                   f"20x, focused at mid-depth, so the disc spreads by at most a tenth of its "
                                   f"radius at either face. Measure the depth by focusing on the two glass "
                                   f"faces and record it beside the curve; a deeper chamber is a softer edge "
                                   f"and D reads low"}))
        out.append(O("objective_choice", "objective_zoom_pair", "returned",
                     allowed_set={"parameter": "objective_zoom_pair", "values": ["20x@1x", "10x@1x"],
                                  "excluded": ["40x@1x", "60x@1x", "100x@1x"],
                                  "basis": ["kb:objective_mrd70270", "kb:objective_mrd70170",
                                            "kb:pixel_size_20x_zoom_1x", "kb:pixel_size_10x_zoom_1x"]
                                  if "pixel_size_10x_zoom_1x" in have else
                                  ["kb:objective_mrd70270", "kb:objective_mrd70170", "kb:pixel_size_20x_zoom_1x"]}))
        run.notes.append(
            "The two dry objectives permit a column: the 20x's cone allows a chamber about a quarter "
            "of the radius deep and the 10x's (NA 0.45) about half. The 40x, 60x and 100x have NA of "
            "1.25 or more, a cone slope above 2 in water, and would hold the chamber under a tenth of "
            "the radius; the 4x and the 1.5x zoom settings were not evaluated. The radius bounds are written for the 20x at 1x, and the "
            "10x doubles both pixel-set ends.")
        run.kb_refs = ac.refs_from(responses, pin)

    elif axis == "a7":
        if expected_diffusivity(nums, goal, responses, run):
            out.append(O("bleach_short_against_recovery", "bleach_duration", "returned",
                         precondition={"parameter": "bleach_duration",
                                       "basis": ["tracer_diffusivity_expected"],
                                       "requires": "bleach for at most a tenth of the expected recovery time "
                                       "at the chosen radius, and aim for a thirtieth: even inside the tenth "
                                       "a strong bleach widens the edge and reads D low (the simulation side "
                                       "computed 0.74 of true D at a tenth and 0.87 at a thirtieth, at a bleach "
                                       "rate of a thousand per tau). Time the bleach from the hardware, record "
                                       "it, and refuse the curve if the fitted tau is under ten bleach "
                                       "durations, reporting D only as a lower bound"}))
        else:
            out.append(O("bleach_short_against_recovery", "bleach_duration", "abstained",
                         kind="no_input", missing=["tracer_diffusivity_expected"],
                         reason="no expected recovery time without the room temperature and viscosity"))
        out.append(O("bleach_fast_enough_for_radius", "bleach_radius", "abstained", kind="no_input",
                     missing=["bleaching_rate"],
                     reason="the time the bleach takes to dig a dip of a third depends on the beads' "
                            "bleaching rate under the bleach light, which is unmeasured. Once the bare-bead "
                            "run gives it at a known Spectra level, the shortest bleach t_b follows, and the "
                            "radius must be at least sqrt(40 D t_b) so that t_b stays under tau/10. A slow "
                            "bleach -- the vendor says the dye is shielded from bleaching -- pushes the "
                            "radius up, against the drift cap pushing it down"))

    run.numbers = nums.rows
    return run


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("goal", type=Path)
    p.add_argument("--axis", required=True, choices=sorted(AXIS_BOUNDS))
    p.add_argument("--caller-id", required=True)
    p.add_argument("--kb-version", required=True)
    p.add_argument("--created-at", required=True)
    p.add_argument("--pin-commit", required=True,
                   help="the commit the pinned kb_version was answered from, as each reply's "
                        "answered_from.commit states; the query log does not record it")
    p.add_argument("--write", action="store_true")
    a = p.parse_args(argv)
    goal = json.loads(a.goal.read_text())
    qid = goal["qid"]
    configs = json.loads((a.goal.parent / "configs.json").read_text())
    issued = {f["caller_id"] for f in configs.get("fan_out", [])}
    if a.caller_id not in issued:
        raise SystemExit(f"{a.caller_id} was not issued by S3.0 for {qid}")
    if configs["kb_version"] != a.kb_version:
        raise SystemExit(f"S3.0 pinned {configs['kb_version']}, not {a.kb_version}")
    commit = a.pin_commit
    responses = build_responses(a.caller_id, a.kb_version, commit)
    run = run_axis(a.axis, goal, a.caller_id, a.kb_version, responses)
    ac.report(run)
    if not a.write:
        return 0
    try:
        card = ac.to_card(run, goal, qid, a.created_at)
    except ac.AxisError as exc:
        print(f"no card written: {exc}", file=sys.stderr)
        return 3
    # axis_common's card has no assumptions field; an axis carrying the goal's
    # assumed diameter must explain it beside the number (check 4).
    if getattr(run, "assumptions", None):
        card["assumptions"] = run.assumptions
    out = AGENT / "questions" / qid / f"axis_{run.config}_{run.axis}.json"
    out.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
