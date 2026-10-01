"""Stage 1 of sim-20260930-401: what a bleach-and-recovery of 100 nm beads
shows, from closed forms and a deterministic diffusion equation, before any
particle is simulated (task 025).

Everything here is deterministic. No random numbers, no engine: the recovery
of non-interacting beads is the diffusion equation for the bleached fraction,
so a particle simulation adds nothing to the mean curve and is kept for what it
does add (Stage 2: integrator check, spread across single curves, camera
sampling).

Inputs and where each came from -- the grade travels with the number:

  temperature  293 K      kb:lab_ambient_temperature, E3. The ROOM, read off
                          a thermometer; nothing reads or actuates the sample.
  viscosity    1e-3 Pa*s  kb:water_viscosity_293k, E3, pure water 288-298 K;
                          asked over 292-294 K and the store answered `full`.
  diameter     100 nm     the person's nominal size, 2026-09-30. NOT in the
                          store and not measured: the store's tracer_* entries
                          describe a different bottle (5 um, AFR-0500-COOH).
                          assumed:, E5.
  density      1.03 g/cm3 kb:tracer_particle_density, E3 -- the 5 um
                          product's polystyrene, applied to the 100 nm beads
                          on the assumption that both are polystyrene. Used for
                          sedimentation only, which turns out negligible.

So D is computed at E5 (worst input) and carried to one significant figure:
explore mode, decades, ties under 10x.

Geometries (all lengths in units of the bleach radius w, all times in units of
tau_D = w**2 / (4 D)):

  column_uniform   bleach uniform through the chamber depth, sharp-edged disc
                   of radius w; detection = mean over a disc ROI of radius w.
                   Instantaneous complete bleach is Soumpasis's closed form,
                   used here to validate the solver.
  column_gaussian  bleach uniform through depth, Gaussian edge
                   b0 = exp(-K exp(-2 r^2 / w^2)), w the 1/e^2 radius, K the
                   bleach depth parameter; same disc ROI.

The registered estimator (contracts/observables.json,
bleach_recovery_diffusivity) fixes the geometry as column_uniform and the fit
as Soumpasis with F0, Finf, tau free and w the half-contrast radius of the
first post-bleach profile. column_gaussian is kept only as a test of that edge
assumption: a DMD pattern blurred by defocus has soft edges, and the question
is how far the sharp-edged fit is then off. A 3-D ellipsoidal bleach is not
computed: the only light-confining device on this instrument is a DMD on the
widefield branch, which does not confine in depth, so it has no experimental
counterpart.

Detection is widefield, so the camera counts every bead in the column
pi w^2 L through the chamber depth L -- not an optical section.

Run in the sim environment from the repository root:

    .pixi/envs/sim/bin/python simulation_agent/src/frap_stage1.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy.linalg import solve_banded
from scipy.optimize import curve_fit
from scipy.special import i0e, i1e

from contracts.validate import round_to_sig

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
QDIR = REPO / "simulation_agent" / "questions" / "sim-20260930-401"
UNITS = json.loads((REPO / "contracts" / "units.json").read_text())
K_B = float(UNITS["constants"]["k_B"]["value"])
G = 9.81  # m/s^2, standard gravity; exact enough for an order of magnitude

TEMPERATURE = 293.0          # K
VISCOSITY = 1.0e-3           # Pa*s
DIAMETER = 100e-9            # m
PS_DENSITY = 1030.0          # kg/m^3
WATER_DENSITY = 998.0        # kg/m^3 -- see density_note below

SPOT_RADII_UM = [0.3, 0.5, 1, 2, 3, 5, 10, 30, 100]   # assumed range, widened 2026-09-30
FRAME_INTERVALS_MS = [1, 3, 10, 30, 100, 300, 1000]
VOLUME_FRACTIONS = [1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2]
DEPTH_UM = 10.0              # assumed chamber depth; bead counts scale with it
BEADS_NEEDED = 10            # assumed: beads in the bleached column
# the estimator's own refusal bounds, on the fitted tau (= tau_D for a sharp disc)
BLEACH_MAX = 0.1             # bleach duration <= tau/10
FRAME_MAX = 0.2              # frame interval <= tau/5
WINDOW_MIN = 10.0            # max_recovery_time >= 10 tau

# --------------------------------------------------------------------------- #
# the radial diffusion solver (2-D, column geometries)
# --------------------------------------------------------------------------- #

DR = 0.01                    # in units of w; the ROI edge r = 1 is a cell face
R_MAX = 15.0
N = int(round(R_MAX / DR))
R_C = (np.arange(N) + 0.5) * DR          # cell centres
R_F = np.arange(N + 1) * DR              # faces
AREA = R_C * DR                          # 2*pi omitted throughout
ROI = R_C < 1.0
D_DIMLESS = 0.25                         # D in units of w^2 / tau_D


def _matrix(dt: float, sink: np.ndarray) -> np.ndarray:
    """Banded (1,1) matrix of backward Euler for db/dt = D lap b - sink*b,
    zero flux at r = 0, b = 1 held one cell beyond R_MAX (reservoir)."""
    up = D_DIMLESS * R_F[1:] / (AREA * DR)   # coupling to i+1
    lo = D_DIMLESS * R_F[:-1] / (AREA * DR)  # coupling to i-1
    ab = np.zeros((3, N))
    ab[0, 1:] = -dt * up[:-1]
    ab[2, :-1] = -dt * lo[1:]
    ab[1] = 1.0 + dt * (up + lo + sink)
    return ab


def _step(ab: np.ndarray, b: np.ndarray, dt: float) -> np.ndarray:
    rhs = b.copy()
    rhs[-1] += dt * D_DIMLESS * R_F[-1] / (AREA[-1] * DR) * 1.0  # reservoir
    return solve_banded((1, 1), ab, rhs)


def roi_mean(b: np.ndarray) -> float:
    return float(np.sum(b[ROI] * AREA[ROI]) / np.sum(AREA[ROI]))


def evolve(b: np.ndarray, times: np.ndarray, sink: np.ndarray | None = None,
           substeps: int = 20) -> np.ndarray:
    """ROI mean of b at each of `times` (ascending, starting from 0)."""
    sink = np.zeros(N) if sink is None else sink
    out = [roi_mean(b)]
    t = 0.0
    cache: dict[float, np.ndarray] = {}
    for t_next in times[1:]:
        span = t_next - t
        dt = span / substeps
        key = round(dt, 14)
        ab = cache.get(key)
        if ab is None:
            ab = cache[key] = _matrix(dt, sink)
        for _ in range(substeps):
            b = _step(ab, b, dt)
        out.append(roi_mean(b))
        t = t_next
    return np.array(out), b


def soumpasis(s: np.ndarray) -> np.ndarray:
    """Normalised recovery, complete instantaneous uniform-disc bleach,
    detected over the same disc. s = t / tau_D, tau_D = w^2/(4D)."""
    s = np.asarray(s, dtype=float)
    x = 2.0 / np.maximum(s, 1e-12)
    return np.where(s > 0, i0e(x) + i1e(x), 0.0)


def log_times(t_end: float, n: int = 400, t_first: float = 1e-4) -> np.ndarray:
    return np.concatenate([[0.0], np.geomspace(t_first, t_end, n)])


def half_time(s: np.ndarray, rec: np.ndarray) -> float:
    """First s at which the normalised recovery reaches 1/2."""
    i = int(np.argmax(rec >= 0.5))
    if i == 0:
        raise ValueError("recovery never reaches one half in the window")
    s0, s1, r0, r1 = s[i - 1], s[i], rec[i - 1], rec[i]
    return float(s0 + (0.5 - r0) * (s1 - s0) / (r1 - r0))


# --------------------------------------------------------------------------- #
# the pieces of Stage 1
# --------------------------------------------------------------------------- #


def diffusivity() -> float:
    return K_B * TEMPERATURE / (3 * math.pi * VISCOSITY * DIAMETER)


def sedimentation() -> dict:
    r = DIAMETER / 2
    v_bead = math.pi * DIAMETER**3 / 6
    drho = PS_DENSITY - WATER_DENSITY
    v_s = 2.0 / 9.0 * drho * G * r**2 / VISCOSITY
    l_g = K_B * TEMPERATURE / (v_bead * drho * G)
    return {"velocity_m_per_s": v_s, "gravitational_length_m": l_g}


def validate_solver() -> dict:
    """The solver against Soumpasis's closed form, before it is trusted."""
    s = log_times(20.0)
    b0 = np.where(R_C < 1.0, 0.0, 1.0)
    rec, _ = evolve(b0, s)
    exact = soumpasis(s)
    err = float(np.max(np.abs(rec - exact)))
    return {"max_abs_error": err, "half_time_numeric": half_time(s, rec),
            "half_time_closed_form": half_time(s, exact)}


def half_times() -> dict:
    """t_1/2 / tau_D for each geometry."""
    s = log_times(50.0)
    out = {}
    rec = soumpasis(s)
    out["column_uniform"] = half_time(s, rec)
    for K in (0.5, 2.0, 5.0):
        b0 = np.exp(-K * np.exp(-2 * R_C**2))
        F, _ = evolve(b0, s)
        F0, Finf = F[0], 1.0
        out[f"column_gaussian_K{K:g}"] = half_time(s, (F - F0) / (Finf - F0))
    return out


def half_contrast_radius(b: np.ndarray) -> float:
    """The estimator's w: the radius at half the bleach contrast of the
    azimuthally averaged profile, contrast = 1 - b."""
    c = 1.0 - b
    half = 0.5 * c[0]
    i = int(np.argmax(c <= half))
    r0, r1, c0, c1 = R_C[i - 1], R_C[i], c[i - 1], c[i]
    return float(r0 + (half - c0) * (r1 - r0) / (c1 - c0))


def _fit_tau(s: np.ndarray, F: np.ndarray, shape) -> tuple[float, float, float]:
    """Fit F = F0 + (Finf - F0) * shape(s / tau), free tau, F0, Finf."""
    model = lambda x, tau, F0, Finf: F0 + (Finf - F0) * shape(x / tau)
    p0 = (1.0, float(F[0]), float(F[-1]))
    popt, _ = curve_fit(model, s, F, p0=p0, maxfev=20000)
    return tuple(float(x) for x in popt)


def finite_bleach() -> list[dict]:
    """Uniform-disc bleach of finite duration s_b at rate k (both in units of
    tau_D of the nominal radius), t = 0 at the end of the bleach, then the
    registered fit over 10 tau_D. D_fit/D is reported two ways: with the
    nominal radius, and with the estimator's half-contrast radius measured on
    the post-bleach profile -- the second is what the estimator reports."""
    rows = []
    sink_shape = np.where(R_C < 1.0, 1.0, 0.0)
    for k in (3.0, 10.0, 30.0, 100.0, 300.0):
        for s_b in (0.03, 0.1, 0.3, 1.0):
            b = np.ones(N)
            tb = np.linspace(0.0, s_b, 61)
            Fb, b = evolve(b, tb, sink=k * sink_shape, substeps=10)
            dip = 1.0 - Fb[-1]
            w_half = half_contrast_radius(b)
            s = log_times(10.0, 300, 1e-3)
            F, _ = evolve(b, s)
            tau, F0, Finf = _fit_tau(s[1:], F[1:], soumpasis)
            rows.append({"k_tauD": k, "bleach_tauD": s_b, "dip": dip,
                         "half_contrast_radius_over_w": w_half,
                         "D_fit_over_D_nominal_w": 1.0 / tau,
                         "D_fit_over_D_estimator_w": w_half**2 / tau,
                         "bleach_over_fitted_tau": s_b / tau,
                         "refused_by_bleach_bound": s_b / tau > BLEACH_MAX,
                         "F_inf": Finf})
    return rows


def edge_cross_fit() -> dict:
    """The edge assumption against the registered fit: an instantaneous
    Gaussian-edged bleach of depth K, fitted with the sharp-edged closed form
    over 10 tau_D, w taken at half contrast as the estimator takes it."""
    out = {}
    s = log_times(10.0, 300, 1e-3)
    for K in (0.5, 2.0, 5.0):
        b_g = np.exp(-K * np.exp(-2 * R_C**2))
        w_half = half_contrast_radius(b_g)
        F_g, _ = evolve(b_g, s)
        tau_g, _, _ = _fit_tau(s[1:], F_g[1:], soumpasis)
        out[f"K{K:g}"] = {"half_contrast_radius_over_w": w_half,
                          "D_fit_over_D_estimator_w": w_half**2 / tau_g}
    return out


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #


def sig(x: float, n: int = 2) -> float:
    return round_to_sig(x, n)


def main() -> dict:
    D = diffusivity()                       # m^2/s
    D_um2 = D * 1e12
    v_bead_um3 = math.pi * (DIAMETER * 1e6) ** 3 / 6
    sed = sedimentation()
    val = validate_solver()
    th = half_times()
    fb = finite_bleach()
    ex = edge_cross_fit()

    t12 = th["column_uniform"]
    spots = []
    for w in SPOT_RADII_UM:
        tau = w**2 / (4 * D_um2)
        row = {"spot_radius_um": w, "tau_D_s": sig(tau),
               "half_time_s": {k: sig(v * tau) for k, v in th.items()}}
        row["bleach_max_ms"] = sig(BLEACH_MAX * tau * 1e3)
        row["frame_interval_max_ms"] = sig(FRAME_MAX * tau * 1e3)
        row["window_min_s"] = sig(WINDOW_MIN * tau)
        row["frames_in_window_at_max_interval"] = round(WINDOW_MIN / FRAME_MAX)
        row["bleach_rate_needed_per_s"] = sig(1.0 / (BLEACH_MAX * tau))
        row["frame_interval_passes_ms"] = [dt for dt in FRAME_INTERVALS_MS
                                           if dt * 1e-3 <= FRAME_MAX * tau]
        row["beads_in_column"] = {
            f"{phi:g}": sig(phi * math.pi * w**2 * DEPTH_UM / v_bead_um3)
            for phi in VOLUME_FRACTIONS}
        row["volume_fraction_for_enough_beads"] = sig(
            BEADS_NEEDED * v_bead_um3 / (math.pi * w**2 * DEPTH_UM))
        row["reference_region_distance_um"] = 5 * w
        row["engine_box_min_um"] = 10 * w
        spots.append(row)


    result = {
        "kind": "stage1_closed_forms",
        "qid": "sim-20260930-401",
        "generated_by": "simulation_agent/src/frap_stage1.py",
        "inputs": [
            {"name": "temperature", "value": TEMPERATURE, "unit": "K",
             "source": "kb:lab_ambient_temperature", "grade": "E3",
             "note": "the room's thermometer reading; the sample is neither read nor actuated"},
            {"name": "viscosity", "value": VISCOSITY, "unit": "Pa*s",
             "source": "kb:water_viscosity_293k", "grade": "E3",
             "note": "pure water; asked over 292-294 K, answered full"},
            {"name": "bead_diameter", "value": 100, "unit": "nm",
             "source": "assumed:a_nominal_diameter", "grade": "E5",
             "note": "the person's nominal size; the store holds nothing on these beads"},
            {"name": "bead_material_density", "value": 1.03, "unit": "g/cm^3",
             "source": "kb:tracer_particle_density", "grade": "E3",
             "note": "the 5 um AFR-0500-COOH product's polystyrene, assumed the same material; sedimentation only"},
            {"name": "chamber_depth", "value": DEPTH_UM, "unit": "um",
             "source": "assumed:a_chamber_depth", "grade": "E5",
             "note": "the widefield camera counts the whole column; the store has no chamber depth, bead counts scale linearly with it"},
        ],
        "diffusivity": {"name": "diffusivity", "value": sig(D_um2, 1), "unit": "um^2/s",
                        "source": "computed:stokes_einstein", "grade": "E5",
                        "precision": "order_of_magnitude",
                        "unrounded": D_um2,
                        "formula": "k_B*temperature/(3*pi*viscosity*bead_diameter)"},
        "sedimentation": {
            "velocity_nm_per_s": sig(sed["velocity_m_per_s"] * 1e9, 1),
            "gravitational_length_mm": sig(sed["gravitational_length_m"] * 1e3, 1),
            "density_note": "water density 998 kg/m^3 at 293 K is this script's constant, not a store citation; at a 3 per cent density contrast a 0.2 per cent change in it moves nothing",
        },
        "solver_validation": {k: (sig(v, 3) if isinstance(v, float) else v) for k, v in val.items()},
        "half_time_over_tau_D": {k: sig(v, 3) for k, v in th.items()},
        "spots": spots,
        "finite_bleach": [{k: (sig(v, 2) if isinstance(v, float) else v) for k, v in r.items()} for r in fb],
        "edge_profile_cross_fit": {k: {kk: sig(vv, 2) for kk, vv in v.items()} for k, v in ex.items()},
        "assumed_thresholds": {
            "beads_in_column": BEADS_NEEDED,
            "note": "this seat's working threshold, not measured; Stage 2 measures the spread a single curve shows at a given bead count and replaces it. The bleach, frame and window bounds are the registered estimator's and are not assumptions",
        },
    }
    QDIR.mkdir(parents=True, exist_ok=True)
    (QDIR / "stage1_closed_forms.json").write_text(json.dumps(result, indent=2) + "\n")
    _figure(result, D_um2)
    (QDIR / "stage1_closed_forms.md").write_text(_markdown(result))
    return result


def _markdown(r: dict) -> str:
    """The Stage 1 write-up, generated from the JSON beside it. Hand edits to
    the .md have no effect; edit this function or the inputs and re-run."""
    D = r["diffusivity"]
    rows = {row["spot_radius_um"]: row for row in r["spots"]}
    L = []
    a = L.append
    a("# sim-20260930-401, Stage 1: what bleaching a disc of 100 nm beads would show")
    a("")
    a("*Generated by `simulation_agent/src/frap_stage1.py` from `stage1_closed_forms.json`; "
      "the JSON is the record. Written by simulation-kyuhwan-macbook-20260930-4 for task 025.*")
    a("")
    a("## Can it be measured? Feasibility first")
    a("")
    a("**Yes on timing, for bleach discs of about 3 to 30 um radius. Below about 1 um it is hard, "
      "and at 0.3 um it needs sub-millisecond bleaching and frames. Above about 30 um the record runs "
      "to many minutes and drift and imaging bleach bind first.** The fit the two sides agreed "
      "refuses a curve whose bleach is longer than a tenth of the recovery time tau, whose frame "
      "interval is longer than a fifth of it, or whose record is shorter than ten of it. Those three "
      "limits against disc size:")
    a("")
    a("| disc radius (um) | tau (s) | longest bleach (ms) | longest frame interval (ms) | shortest record (s) | bleach rate needed (1/s) | volume fraction for 10 beads |")
    a("|---|---|---|---|---|---|---|")
    for w, row in rows.items():
        a(f"| {w:g} | {row['tau_D_s']:g} | {row['bleach_max_ms']:g} | {row['frame_interval_max_ms']:g} | "
          f"{row['window_min_s']:g} | {row['bleach_rate_needed_per_s']:g} | {row['volume_fraction_for_enough_beads']:g} |")
    a("")
    a("**What decides it is how fast the beads bleach, and nobody knows that yet.** To leave a dip "
      "of about 60 per cent inside the longest allowed bleach, the dye has to bleach at the rate in "
      "the sixth column under the patterning light: about 20 per second for a 3 um disc, 170 per "
      "second for 1 um. The knowledge base holds no bleaching rate for these beads or this light. **Measure "
      "the bleaching rate under the patterning illumination first**; it decides the smallest disc "
      "that can work before any recovery is recorded.")
    a("")
    big = rows[100]
    a("**Large discs are easy on every limit above and hard on the record itself.** At 30 um tau is "
      f"{rows[30]['tau_D_s']:g} s and at 100 um {big['tau_D_s']:g} s, so the shortest record the fit allows "
      f"is {rows[30]['window_min_s']:g} s and {big['window_min_s']:g} s -- many minutes to over an hour. "
      "Over a record that long, other things bind before diffusion does: bleaching by the imaging light "
      "(the fit's reference region corrects it only if that region sees exactly the same light), drift of "
      "the stage and focus, and the field of view, since the reference region must sit at least five disc "
      "radii away -- half a millimetre from a 100 um disc. None of these is in the model. The model's own "
      "numbers do not change with disc size: measured in recovery times and disc radii, the curve and the "
      "fit's biases below are the same at any w, so the second stage's runs at 3 um carry to any disc.")
    a("")
    a("The bead count is not the limit at ordinary dilutions: a 3 um disc through a 10 um chamber "
      "holds ten beads already at a volume fraction of 2e-5. The bead count only binds for "
      "sub-micrometre discs, which the timing has already ruled out.")
    a("")
    a("## How fast the beads diffuse")
    a("")
    a(f"**D ~ {D['value']:g} um^2/s** (Stokes-Einstein, {D['unrounded']:.2f} unrounded), from three "
      "inputs of different standing:")
    a("")
    a("- diameter 100 nm: **the person's nominal size, not a measurement**. The knowledge base "
      "holds nothing on these beads -- its bead entries describe a different, 5 um bottle -- so the "
      "result is an order of magnitude and is carried to one figure;")
    a("- viscosity 1 mPa s: pure water near 293 K, from the knowledge base (a textbook value). That "
      "the beads sit in water and not a buffer is assumed;")
    a("- temperature 293 K: the room's thermometer reading. Nothing reads the sample, and a kelvin "
      "either way moves D by about two per cent.")
    a("")
    a(f"Sedimentation does not matter: about {r['sedimentation']['velocity_nm_per_s']:g} nm/s, a "
      f"gravitational length of about {r['sedimentation']['gravitational_length_mm']:g} mm against a "
      "chamber tens of micrometres deep. That uses the density of a different bead's polystyrene "
      "and assumes these beads are polystyrene too.")
    a("")
    a("Concentration does not enter D in the model, because the model's beads do not interact. "
      "What concentration would change a real suspension's self-diffusion -- and how much larger "
      "charged beads in deionised water behave than they are -- is not in the knowledge base, so no "
      "number is given. The volume fractions the counts call for (1e-6 to 1e-3) are dilute; "
      "concentration is a signal question here unless that missing entry says otherwise.")
    a("")
    a("## The recovery against disc size")
    a("")
    a("The bleach is a column through the whole sample depth, because the only way this microscope "
      "confines light is a patterned (DMD) widefield beam, which is not confined in depth. So the "
      "depth-integrated signal refills by two-dimensional diffusion, and the half-recovery time is "
      f"{r['half_time_over_tau_D']['column_uniform']:g} tau with tau = w^2 / 4D for a sharp-edged disc of radius w:")
    a("")
    a("| disc radius (um) | half-recovery, sharp edge (s) | half-recovery, Gaussian edge (s) |")
    a("|---|---|---|")
    for w, row in rows.items():
        ht = row["half_time_s"]
        a(f"| {w:g} | {ht['column_uniform']:g} | {ht['column_gaussian_K0.5']:g} - {ht['column_gaussian_K5']:g} |")
    a("")
    a("A three-dimensional ellipsoidal bleach is not computed: this instrument cannot make one.")
    a("")
    a("## Two limits of this answer, and how far they reach")
    a("")
    a("Both were found by solving the diffusion equation with the bleach as it would really happen "
      "and fitting the result exactly as the agreed fit would. The solver reproduces the textbook "
      f"recovery to within {r['solver_validation']['max_abs_error']:g} and returns D exactly on an "
      "ideal bleach, so these are effects of the bleach, not of the arithmetic.")
    a("")
    fb = [x for x in r["finite_bleach"] if x["k_tauD"] == 300.0]
    a("1. **A bleach of finite length reads D low, even inside the allowed length.** Beads just "
      "outside the disc are bleached as they cross its edge. With a strong bleach the fitted D, "
      "using the radius measured on the first frame after the bleach as the fit does, comes out:")
    a("")
    a("   | bleach length / tau | D fitted / D |")
    a("   |---|---|")
    for x in fb:
        a(f"   | {x['bleach_tauD']:g} | {x['D_fit_over_D_estimator_w']:g} |")
    a("")
    a("   The fit's own bleach limit, a tenth of tau, still allows about 25 per cent low. That is a "
      "tie at the decade resolution asked for, and it would not be in a confirmatory measurement.")
    a("")
    a("2. **A soft-edged disc reads D two to four times low, and the fit's radius check does not "
      "catch it.** A defocus-blurred pattern has soft edges; fitted with the sharp-edged model, a "
      "fully Gaussian edge gives:")
    a("")
    a("   | bleach depth | radius at half contrast / nominal | D fitted / D |")
    a("   |---|---|---|")
    for k, x in r["edge_profile_cross_fit"].items():
        a(f"   | {k[1:]} | {x['half_contrast_radius_over_w']:g} | {x['D_fit_over_D_estimator_w']:g} |")
    a("")
    a("   A real blurred disc sits between these and a sharp one. Still inside the decade, but "
      "large. **What removes both:** send back the measured first post-bleach profile and the actual "
      "bleach length, and the simulation is re-run with them, so the same bias sits on both sides "
      "of the comparison.")
    a("")
    a("## What is assumed, and what replaces it")
    a("")
    a("- disc radius 3 um as the working point, chamber depth 10 um, volume fraction 1e-4, and ten "
      "beads as the least a single curve can use: this agent's working values. The microscope plan's "
      "disc, chamber and dilution replace the first three; the second stage of this question "
      "measures the fourth.")
    a("- the 100 nm diameter: replaced by a measured size or the product's specification.")
    s2 = QDIR / "stage2_runs.json"
    if s2.exists():
        th = json.loads(s2.read_text())["single_curve_threshold"]["beads_where_spread_is_a_tie"]
        if th:
            a(f"- **ten beads per curve has been replaced by a measurement**: the second stage finds one "
              f"curve needs about {int(float(f'{th:.1g}'))} beads in the disc before its scatter is inside a factor of ten "
              "(see stage2_runs.md). Read the bead-count column of the first table above with that in mind: "
              f"the volume fractions it needs are about {th / 10:.0f} times those shown.")
    a("")
    a("![Stage 1](stage1_closed_forms.png)")
    a("")
    a("---")
    a("References: task 025; observable `bleach_recovery_diffusivity`; goal card `goal.json`; "
      "knowledge-base version kbv-49b098a90994.")
    return "\n".join(L) + "\n"


def _figure(result: dict, D_um2: float) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    s = np.geomspace(1e-3, 30, 300)
    ax[0].plot(s, soumpasis(s), label="sharp-edged disc, column (the registered fit)")
    ax[0].axvline(BLEACH_MAX, color="grey", ls=":", lw=0.8)
    ax[0].text(BLEACH_MAX * 1.1, 0.05, "longest bleach", fontsize=7, color="grey", rotation=90)
    ax[0].axvline(FRAME_MAX, color="grey", ls="--", lw=0.8)
    ax[0].text(FRAME_MAX * 1.1, 0.05, "longest frame interval", fontsize=7, color="grey", rotation=90)
    ax[0].axvline(WINDOW_MIN, color="grey", ls="-.", lw=0.8)
    ax[0].text(WINDOW_MIN * 1.1, 0.05, "shortest window", fontsize=7, color="grey", rotation=90)
    ax[0].set_xscale("log")
    ax[0].set_xlabel("time after the bleach / tau   (tau = w^2 / 4D)")
    ax[0].set_ylabel("recovered fraction")
    ax[0].set_title("Recovery shape and the fit's three limits")
    ax[0].legend(fontsize=8, loc="upper left")

    w = np.geomspace(0.3, 100, 100)
    tau = w**2 / (4 * D_um2)
    ax[1].plot(w, BLEACH_MAX * tau, label="longest bleach allowed")
    ax[1].plot(w, FRAME_MAX * tau, label="longest frame interval allowed")
    ax[1].plot(w, WINDOW_MIN * tau, label="shortest recording allowed")
    ax[1].plot(w, tau, "k", lw=1.5, label="tau")
    ax[1].axhspan(1e-3, 1e-2, color="red", alpha=0.07)
    ax[1].text(0.32, 1.3e-3, "1-10 ms", fontsize=7, color="red")
    ax[1].set_xscale("log"); ax[1].set_yscale("log")
    ax[1].set_xlabel("bleach disc radius w (um)")
    ax[1].set_ylabel("time (s)")
    ax[1].set_title(f"Timing against disc size, D ~ {result['diffusivity']['value']} um^2/s")
    ax[1].legend(fontsize=8)

    v_bead = math.pi * 0.1**3 / 6
    for phi in VOLUME_FRACTIONS:
        ax[2].plot(w, phi * np.pi * w**2 * DEPTH_UM / v_bead, label=f"volume fraction {phi:g}")
    ax[2].axhline(BEADS_NEEDED, color="k", lw=0.8, ls="--")
    ax[2].set_xscale("log"); ax[2].set_yscale("log")
    ax[2].set_xlabel("bleach disc radius w (um)")
    ax[2].set_ylabel(f"beads in the bleached column ({DEPTH_UM:g} um deep)")
    ax[2].set_title("How many beads one curve counts")
    ax[2].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(QDIR / "stage1_closed_forms.png", dpi=130)


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: r[k] for k in ("diffusivity", "sedimentation", "solver_validation",
                                         "half_time_over_tau_D",
                                         "edge_profile_cross_fit")}, indent=1))
    for row in r["spots"]:
        print(row["spot_radius_um"], row["tau_D_s"], row["bleach_max_ms"], row["frame_interval_max_ms"],
              row["window_min_s"], row["bleach_rate_needed_per_s"], row["volume_fraction_for_enough_beads"])
    for row in r["finite_bleach"]:
        print(row)
