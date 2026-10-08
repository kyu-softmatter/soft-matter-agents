"""Stage 1 of sim-20261008-001: which plane an observation depends on, how
much a wrong plane moves the answer, and which plane a sharpness-maximum focus
search will find (task 026). Closed forms and deterministic integrals only: no
random numbers, no engine, no declared model changed, no image rendered.

Four items, each a function below:

  1. the bleach column is not a column   -- bleach_tables()
  2. which plane a sharpness maximum finds -- focus_planes()
  3. the wall                             -- wall_tables()
  4. holding focus over the record        -- drift_tables()

Item 1, the model. Lengths are in units of the nominal disc radius w and
times in tau_D = w**2 / (4 D), so D = 1/4. A widefield-projected disc focused
at depth z_f is, at depth z, the disc convolved with a defocus kernel. In
geometric optics a pupil filled uniformly in sin(theta) maps the ray at
q = tan(theta) to a lateral offset |z - z_f| * q, with weight
2q / (1 + q**2)**2 dq (normalised by sin(theta_max)**2). Its Hankel transform
is

    kappa(u) = (1/s_max**2) * int_0^q_max 2q / (1 + q**2)**2 J0(u q) dq,

u = k |z - z_f|, which is u K1(u) exactly for a full propagating cone
(s_max = 1) and is tabulated by quadrature otherwise. Near focus diffraction
sets the width, which the geometric kernel does not have; it is added as a
Gaussian of sigma = 0.21 lambda / NA, multiplied in Fourier space. Both are
approximations: the first fails within about a depth of field of focus, the
second is the usual Gaussian stand-in for an Airy disc, and neither has
aberration (a dry lens focusing into water, an oil lens into water).

The camera sees each depth through the same kind of kernel, focused at z_d.
Beads diffuse in three dimensions between two reflecting walls at z = 0 and
z = L, so the signal is solved exactly in cosine modes of z:

    S(k, t) = exp(-D k^2 t) * sum_n c_n a_n(k) b_n(k) exp(-D (n pi / L)^2 t),

a_n and b_n the cosine coefficients over depth of the bleach and detection
kernels, c_0 = 1 and c_n = 2. With a depth-blind camera b_n vanishes for
n >= 1 and S is the depth-averaged bleach -- so for that camera the depth
average is not an approximation but exact, which answers Stage 2's candidate
question for that case without a particle run. The bleach is linear (a weak
bleach); the beads are uniform in depth (their gravitational length is
centimetres); walls are hydrodynamically absent here and are item 3.

The recovery in a disc ROI of radius w and the first frame's profile are
Hankel integrals of S. They are fitted exactly as the registered estimator
does (contracts/observables.json, bleach_recovery_diffusivity): Soumpasis's
sharp-disc form with F0, Finf and tau free, w taken as the half-contrast
radius of the first post-bleach profile, D = w_half**2 / (4 tau), and the
record made ten fitted recovery times long. What is reported per case is
D fitted / D, the bleach contrast relative to a true column ("dip"), and the
mobile fraction the fit reports.

Inputs, with where each came from -- the grade travels with the number. The
store was read from this agent's snapshot copy, not asked: the librarian's
server did not connect in this session, so every card here is on the degraded
path and says so.

  temperature        293 K       kb:lab_ambient_temperature, E3 (the room's)
  viscosity          1e-3 Pa*s   kb:water_viscosity_293k, E3
  water density      998.2       kb:water_density_293k, E3
  water index        1.3325      kb:water_refractive_index_605nm_293k, E3
  objective NA       per lens    kb:objective_mrd70040 ... mrd71970, E3
  pixel size         per lens    kb:pixel_size_<lens>_zoom_1x, E2
  100 nm diameter    0.1 um      kb:f8801_nominal_diameter, E3 -- but the
                                 bench's beads being F8801 is the person's
                                 statement (particle_suspension_b_identity, E5)
  100 nm emission    605 nm      kb:f8801_emission_peak, E3
  100 nm excitation  580 nm      kb:f8801_excitation_peak, E3
  5 um diameter      5 um        kb:tracer_diameter_measured, E2
  5 um emission      680 nm      kb:tracer_emission_peak, E3
  polystyrene        1.03 g/cm3  kb:tracer_particle_density, E3 -- the 5 um
                                 product's; assumed for the 100 nm beads
  polystyrene index  1.592       kb:polystyrene_refractive_index_587_6nm, E3
  chamber depth      10-100 um   assumed, a span of decades (absent)
  pupil fill         1 and 0.3   assumed: whether the patterning light fills
                                 the objective's pupil is absent from the store

Run from the repository root, with the repository on the path so the shared
rounding rule imports:

    python simulation_agent/src/focus_stage1.py            # compute, ~1 h
    python simulation_agent/src/focus_stage1.py --report   # md and png only
"""

from __future__ import annotations

import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np
from scipy.fft import dct
from scipy.integrate import cumulative_trapezoid
from scipy.optimize import brentq, curve_fit
from scipy.special import i0e, i1e, j0, j1, k1

from contracts.validate import round_to_sig

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
QID = "sim-20261008-001"
QDIR = REPO / "simulation_agent" / "questions" / QID
OUT = QDIR / "stage1_focus_planes.json"
UNITS = json.loads((REPO / "contracts" / "units.json").read_text(encoding="utf-8"))
K_B = float(UNITS["constants"]["k_B"]["value"])
G = 9.81                      # m/s^2, standard gravity

TEMPERATURE = 293.0           # K
VISCOSITY = 1.0e-3            # Pa*s
WATER_DENSITY = 998.201       # kg/m^3
N_WATER = 1.3325138
PS_DENSITY = 1030.0           # kg/m^3
N_PS = 1.592
D100 = 0.1e-6                 # m
D5 = 5.0e-6                   # m
LAM_EX_100, LAM_EM_100 = 0.580, 0.605   # um
LAM_EM_5 = 0.680              # um

# name, store entry, NA, immersion, sample-plane pixel (um) and its entry
OBJECTIVES = [
    ("4x", "objective_mrd70040", 0.20, "air", 1.625, "pixel_size_4x_zoom_1x"),
    ("10x", "objective_mrd70170", 0.45, "air", 0.65, "pixel_size_10x_zoom_1x"),
    ("20x", "objective_mrd70270", 0.80, "air", 0.32373, "pixel_size_20x_zoom_1x"),
    ("40x water", "objective_mrd77400", 1.25, "water", 0.1625, "pixel_size_40x_zoom_1x"),
    ("60x oil", "objective_mrd71670", 1.42, "oil", 0.10833, "pixel_size_60x_zoom_1x"),
    ("100x oil", "objective_mrd71970", 1.45, "oil", 0.065, "pixel_size_100x_zoom_1x"),
]
DISC_RADII_UM = [1, 3, 10, 30]
DEPTHS_UM = [10, 30, 100]
PUPIL_FILLS = [1.0, 0.3]
VOLUME_FRACTIONS = [1e-7, 1e-6, 1e-5, 1e-4, 1e-3]
EXPOSURES_S = [1e-3, 1e-2, 1e-1]
BEADS_FOR_A_TIE = 300         # stage2_runs.json of sim-20260930-401, the measured threshold
RECORD_TAUS = 10.0            # the estimator's minimum window

# --------------------------------------------------------------------------- #
# numerical grids (units of w)
# --------------------------------------------------------------------------- #

KK = np.linspace(1e-4, 60.0, 2401)
J1K = j1(KK)
RR = np.linspace(0.0, 4.0, 401)
J0KR = j0(np.outer(RR, KK))
T_FIRST = 3e-3                # the first frame, in fitted recovery times
NZ, NMODES = 8192, 4096


def soumpasis(s):
    s = np.asarray(s, dtype=float)
    x = 2.0 / np.maximum(s, 1e-12)
    return np.where(s > 0, i0e(x) + i1e(x), 0.0)


def s_max(NA: float, fill: float) -> float:
    """sin of the widest propagating ray in water."""
    return min(fill * NA / N_WATER, 1.0)


def diffraction_sigma_um(NA: float, lam_um: float) -> float:
    return 0.21 * lam_um / min(NA, N_WATER)


_KAPPA: dict[float, tuple] = {}


def kappa_table(sm: float, U: float = 600.0, du: float = 0.02):
    key = round(sm, 6)
    if key in _KAPPA:
        return _KAPPA[key]
    u = np.arange(0.0, U + du, du)
    if sm >= 1.0:
        k = np.where(u > 0, u * k1(np.maximum(u, 1e-300)), 1.0)
        i_inf = math.pi / 2
    else:
        qm = sm / math.sqrt(1 - sm**2)
        q = np.linspace(0.0, qm, int(max(4000, 30 * U * qm / math.pi)) + 1)
        wq = 2 * q / (1 + q**2) ** 2
        k = np.empty_like(u)
        for i in range(0, len(u), 500):
            k[i:i + 500] = np.trapezoid(wq * j0(u[i:i + 500, None] * q), q, axis=1)
        k /= sm**2
        i_inf = (qm / (1 + qm**2) + math.atan(qm)) / sm**2
    cum = cumulative_trapezoid(k, u, initial=0.0)
    _KAPPA[key] = (u, k, cum, i_inf)
    return _KAPPA[key]


def kappa(sm: float):
    u, k, _, _ = kappa_table(sm)
    return lambda x: np.where(x < u[-1], np.interp(x, u, k), 0.0)


def kappa_integral(sm: float):
    u, _, cum, i_inf = kappa_table(sm)
    return lambda x: np.where(x < u[-1], np.interp(x, u, cum), i_inf)


# --------------------------------------------------------------------------- #
# the signal
# --------------------------------------------------------------------------- #


def transfer_depth_blind(sm, sig_w, Lw, zf):
    """The depth-averaged bleach, exact for a camera that weighs every depth
    the same: (1/L) int kappa(k|z - z_f|) dz in closed form, z_f anywhere."""
    I = kappa_integral(sm)
    a, b = KK * (0.0 - zf), KK * (Lw - zf)        # signed ends of the depth range
    def signed(x):
        return np.sign(x) * I(np.abs(x))
    m = (signed(b) - signed(a)) / (KK * Lw)
    return m * np.exp(-0.5 * KK**2 * sig_w**2)


def modes(sm_i, sig_i, sm_d, sig_d, Lw, zf, zd):
    """a_n b_n c_n per k and the mode decay rates, for bleach focus zf and
    camera focus zd (either may lie outside the chamber)."""
    z = (np.arange(NZ) + 0.5) * Lw / NZ
    ki, kd = kappa(sm_i), kappa(sm_d)
    P = np.empty((len(KK), NMODES))
    c = np.full(NMODES, 2.0)
    c[0] = 1.0
    for i, k in enumerate(KK):
        a = dct(ki(k * np.abs(z - zf)), type=2)[:NMODES] / (2 * NZ)
        b = dct(kd(k * np.abs(z - zd)), type=2)[:NMODES] / (2 * NZ)
        P[i] = a * b * c
    P *= np.exp(-0.5 * KK**2 * (sig_i**2 + sig_d**2))[:, None]
    lam = 0.25 * (np.arange(NMODES) * math.pi / Lw) ** 2
    return P, lam


def first_frame_transfer(sm_i, sig_i, sm_d, sig_d, Lw, zf, zd):
    """S(k, 0) = (1/L) int bleach * camera dz, by direct quadrature -- the
    first frame needs no modes."""
    z = (np.arange(NZ) + 0.5) * Lw / NZ
    ki, kd = kappa(sm_i), kappa(sm_d)
    S = np.array([np.mean(ki(k * np.abs(z - zf)) * kd(k * np.abs(z - zd))) for k in KK])
    return S * np.exp(-0.5 * KK**2 * (sig_i**2 + sig_d**2))


def roi(S):
    return 2 * np.trapezoid(J1K**2 / KK * S, KK, axis=-1)


def half_contrast_radius(S0) -> float:
    c = np.trapezoid(J1K * S0 * J0KR, KK, axis=-1)
    half = 0.5 * c[0]
    i = int(np.argmax(c <= half))
    if i == 0:
        return float("nan")
    return float(RR[i - 1] + (half - c[i - 1]) * (RR[i] - RR[i - 1]) / (c[i] - c[i - 1]))


def fit_registered(signal) -> dict:
    """signal(s) -> S(k) rows at times s. The registered fit, record ten
    fitted recovery times long, iterated until the record is self-consistent."""
    tau = 1.0
    S0 = signal(np.array([T_FIRST]))[0]
    w_half = half_contrast_radius(S0)
    for _ in range(8):
        s = np.geomspace(T_FIRST * tau, RECORD_TAUS * tau, 150)
        F = 1.0 - roi(signal(s))
        model = lambda x, ta, F0, Fi: F0 + (Fi - F0) * soumpasis(x / ta)
        (ta, F0, Fi), _ = curve_fit(model, s, F, p0=(tau, F[0], F[-1]),
                                    bounds=([1e-4, -np.inf, -np.inf], [1e4, np.inf, np.inf]),
                                    maxfev=20000)
        done = abs(ta / tau - 1) < 1e-3
        tau = float(ta)
        if done:
            break
    return {"D_fit_over_D": w_half**2 / tau, "dip": float(roi(S0)),
            "mobile_fraction": float((Fi - F0) / (1 - F0)), "w_half_over_w": w_half,
            "tau_fit_over_tau_D": tau}


def case(obj, w_um, L_um, zf_um, zd_um=None, fill=1.0, camera="focused"):
    """One (objective, disc, chamber, focus) case. camera: 'focused' -- the
    camera sees each depth through its own defocus, focused at zd (default:
    with the pattern, i.e. a DMD conjugate to the camera's image plane);
    'depth_blind' -- the column model's camera, kept as the reference."""
    name, _, NA, *_ = obj
    sm_i, sm_d = s_max(NA, fill), s_max(NA, 1.0)
    sig_i = diffraction_sigma_um(NA, LAM_EX_100) / w_um
    sig_d = diffraction_sigma_um(NA, LAM_EM_100) / w_um
    Lw, zf = L_um / w_um, zf_um / w_um
    zd = zf if zd_um is None else zd_um / w_um
    if camera == "depth_blind":
        M = transfer_depth_blind(sm_i, sig_i, Lw, zf)
        sig = lambda s: M[None, :] * np.exp(-0.25 * np.outer(s, KK**2))
    else:
        P, lam = modes(sm_i, sig_i, sm_d, sig_d, Lw, zf, zd)
        sig = lambda s: (P @ np.exp(-np.outer(lam, s))).T * np.exp(-0.25 * np.outer(s, KK**2))
    return fit_registered(sig)


_PRODUCT: dict[tuple, tuple] = {}


def dip_only(obj, w_um, L_um, zf_um, fill=1.0):
    """The first frame's contrast with the camera focused with the pattern.
    Both kernels then depend on the same |z - z_f|, so the depth integral is
    one cumulative table of kappa_i * kappa_d -- the same quantity
    first_frame_transfer computes by brute force, which validate() checks."""
    name, _, NA, *_ = obj
    sm_i, sm_d = s_max(NA, fill), s_max(NA, 1.0)
    key = (round(sm_i, 6), round(sm_d, 6))
    if key not in _PRODUCT:
        u, ki, _, _ = kappa_table(sm_i)
        _, kd, _, _ = kappa_table(sm_d)
        _PRODUCT[key] = (u, cumulative_trapezoid(ki * kd, u, initial=0.0))
    u, cum = _PRODUCT[key]
    G = lambda x: np.sign(x) * np.interp(np.abs(x), u, cum)
    Lw, zf = L_um / w_um, zf_um / w_um
    sig_i = diffraction_sigma_um(NA, LAM_EX_100) / w_um
    sig_d = diffraction_sigma_um(NA, LAM_EM_100) / w_um
    S0 = (G(KK * (Lw - zf)) - G(-KK * zf)) / (KK * Lw)
    S0 = S0 * np.exp(-0.5 * KK**2 * (sig_i**2 + sig_d**2))
    return float(roi(S0 * np.exp(-0.25 * KK**2 * T_FIRST)))


# --------------------------------------------------------------------------- #
# checks before anything is trusted
# --------------------------------------------------------------------------- #


def validate() -> dict:
    out = {}
    # the column limit is Soumpasis
    s = np.geomspace(1e-2, 10, 60)
    C = roi(np.exp(-0.25 * np.outer(s, KK**2)))
    out["column_limit_vs_soumpasis_max_abs_error"] = float(np.max(np.abs((1 - C) - soumpasis(s))))
    # the kernel's integral against its closed form
    errs = []
    for obj in OBJECTIVES:
        for fill in PUPIL_FILLS:
            u, k, cum, i_inf = kappa_table(s_max(obj[2], fill))
            errs.append(abs(cum[-1] / i_inf - 1))
    out["kernel_integral_vs_closed_form_max_rel_error"] = float(max(errs))
    # a Gaussian-blurred disc against sim-20260930-401's real-space solver
    try:
        sys.path.insert(0, str(HERE.parent))
        import frap_stage1 as fs
        sig = 0.4
        M = np.exp(-0.5 * KK**2 * sig**2)
        st = np.concatenate([[0.0], np.geomspace(1e-2, 10, 40)])
        Ck = roi(M[None, :] * np.exp(-0.25 * np.outer(st, KK**2)))
        prof = np.trapezoid(j1(KK) * M * j0(np.outer(fs.R_C, KK)), KK, axis=-1)
        eps = 1e-3
        F, _ = fs.evolve(1 - eps * prof, st)
        out["gaussian_disc_vs_401_solver_max_rel_error"] = float(np.max(np.abs((1 - F) / eps - Ck)) / Ck[0])
    finally:
        sys.path.remove(str(HERE.parent))
    # the mode solution with a depth-blind camera is the depth average
    obj = OBJECTIVES[2]
    P, lam = modes(s_max(obj[2], 1.0), 0.0, 1e-9, 0.0, 10.0, 5.0, 5.0)
    sm = s_max(obj[2], 1.0)
    M = transfer_depth_blind(sm, 0.0, 10.0, 5.0)
    S_modes = (P @ np.exp(-np.outer(lam, [0.1, 1.0]))).T
    S_avg = M[None, :] * np.ones((2, 1))
    out["modes_depth_blind_vs_depth_average_max_abs_error"] = float(
        np.max(np.abs(roi(S_modes * np.exp(-0.25 * np.outer([0.1, 1.0], KK**2)))
                      - roi(S_avg * np.exp(-0.25 * np.outer([0.1, 1.0], KK**2))))))
    # the fast first-frame contrast against brute-force depth quadrature
    errs = []
    for obj in (OBJECTIVES[0], OBJECTIVES[4]):
        for zf in (0.0, 5.0, -10.0):
            NA = obj[2]
            S0 = first_frame_transfer(s_max(NA, 1.0), diffraction_sigma_um(NA, LAM_EX_100) / 3,
                                      s_max(NA, 1.0), diffraction_sigma_um(NA, LAM_EM_100) / 3,
                                      10 / 3, zf / 3, zf / 3)
            brute = float(roi(S0 * np.exp(-0.25 * KK**2 * T_FIRST)))
            errs.append(abs(dip_only(obj, 3, 10, zf) - brute))
    out["first_frame_contrast_fast_vs_brute_max_abs_error"] = float(max(errs))
    return out


# --------------------------------------------------------------------------- #
# item 1 and item 4
# --------------------------------------------------------------------------- #


def diffusivity_100() -> float:
    return K_B * TEMPERATURE / (3 * math.pi * VISCOSITY * D100) * 1e12   # um^2/s


def blur_radius_um(NA: float, fill: float, dz_um: float) -> float:
    """The defocus kernel's median ray radius at defocus dz: half the light
    lands inside it."""
    sm = s_max(NA, fill) / math.sqrt(2)
    return abs(dz_um) * sm / math.sqrt(1 - sm**2)


def tolerance(xs, ys, ref, factor):
    """Smallest |x| in xs (sorted by distance) at which ys departs from ref by
    `factor` either way; None if it never does inside the scan."""
    for x, y in zip(xs, ys):
        if y <= ref / factor or y >= ref * factor:
            return x
    return None


def bleach_tables(log) -> dict:
    rows = []
    for obj in OBJECTIVES:
        for w in DISC_RADII_UM:
            for L in DEPTHS_UM:
                row = {"objective": obj[0], "disc_radius_um": w, "chamber_depth_um": L}
                row["edge_blur_um_depth_average_mid_focus"] = blur_radius_um(obj[2], 1.0, L / 4)
                row["edge_blur_um_depth_average_coverslip_focus"] = blur_radius_um(obj[2], 1.0, L / 2)
                for label, zf in (("coverslip", 0.0), ("quarter", L / 4), ("mid", L / 2)):
                    row[f"focused_camera_{label}"] = case(obj, w, L, zf)
                    row[f"depth_blind_camera_{label}"] = case(obj, w, L, zf, camera="depth_blind")
                row["partial_pupil_0.3_mid"] = case(obj, w, L, L / 2, fill=0.3)
                # contrast against focus position, focused camera, focus from
                # 2L below the coverslip to mid-chamber (the scan is symmetric
                # about mid-chamber)
                zs = np.concatenate([-np.geomspace(3 * L, 0.003 * L, 40), np.linspace(0, L / 2, 41)])
                dips = [dip_only(obj, w, L, z) for z in zs]
                best = int(np.argmax(dips))
                d_from_best = np.abs(zs - zs[best])
                order = np.argsort(d_from_best)
                row["dip_scan"] = {"focus_um": [float(z) for z in zs], "dip": dips}
                row["best_focus_um"] = float(zs[best])
                row["best_dip"] = float(dips[best])
                for f in (2, 10):
                    t = tolerance(d_from_best[order], np.array(dips)[order], dips[best], f)
                    row[f"focus_tolerance_um_dip_factor_{f}"] = None if t is None else float(t)
                rows.append(row)
                log(f"item 1 {obj[0]} w={w} L={L}: mid {row['focused_camera_mid']['D_fit_over_D']:.2f}"
                    f"/{row['focused_camera_mid']['dip']:.2f} coverslip "
                    f"{row['focused_camera_coverslip']['D_fit_over_D']:.2f}/{row['focused_camera_coverslip']['dip']:.2f}")
    return {"rows": rows}


DRIFT_OFFSETS_UM = [0.3, 1, 3, 10, 30, 100]


def drift_tables(log) -> dict:
    """The camera focus away from the bleach plane by delta, bleach at
    mid-chamber: what a focus that moved after the bleach does to the fit."""
    D = diffusivity_100()
    rows = []
    for obj in OBJECTIVES:
        for w in DISC_RADII_UM:
            for L in DEPTHS_UM:
                ref = case(obj, w, L, L / 2)
                scan = []
                for d in DRIFT_OFFSETS_UM:
                    r = case(obj, w, L, L / 2, zd_um=L / 2 + d)
                    scan.append({"camera_offset_um": d, **r})
                record_s = RECORD_TAUS * w**2 / (4 * D)
                row = {"objective": obj[0], "disc_radius_um": w, "chamber_depth_um": L,
                       "record_s": record_s, "reference": ref, "scan": scan}
                for f in (2, 10):
                    tD = tolerance([x["camera_offset_um"] for x in scan],
                                   [x["D_fit_over_D"] for x in scan], ref["D_fit_over_D"], f)
                    tdip = tolerance([x["camera_offset_um"] for x in scan],
                                     [x["dip"] for x in scan], ref["dip"], f)
                    cands = [t for t in (tD, tdip) if t is not None]
                    t = min(cands) if cands else None
                    row[f"camera_tolerance_um_factor_{f}"] = t
                    row[f"drift_rate_um_per_s_factor_{f}"] = None if t is None else t / record_s
                rows.append(row)
                log(f"item 4 {obj[0]} w={w} L={L}: tol2={row['camera_tolerance_um_factor_2']}")
    return {"rows": rows, "diffusivity_um2_per_s": D}


# --------------------------------------------------------------------------- #
# item 2: which plane a sharpness maximum finds
# --------------------------------------------------------------------------- #


def depth_of_field_um(NA: float, lam_um: float, pixel_um: float) -> float:
    """kb:objective_depth_of_field, n the sample medium's (water), the
    detector's resolvable distance taken as one pixel."""
    return lam_um * N_WATER / NA**2 + N_WATER * pixel_um / NA


def gravitational_length_m(d: float) -> float:
    v = math.pi * d**3 / 6
    return K_B * TEMPERATURE / ((PS_DENSITY - WATER_DENSITY) * v * G)


def focus_planes() -> dict:
    v100_um3 = math.pi * (D100 * 1e6) ** 3 / 6
    D = diffusivity_100()
    out = {"gravitational_length_100nm_mm": gravitational_length_m(D100) * 1e3,
           "gravitational_length_5um_um": gravitational_length_m(D5) * 1e6,
           "rows": []}
    for name, entry, NA, imm, px, pxe in OBJECTIVES:
        dof100 = depth_of_field_um(NA, LAM_EM_100, px)
        dof5 = depth_of_field_um(NA, LAM_EM_5, px)
        psf = 0.21 * LAM_EM_100 / min(NA, N_WATER)
        psf_eff = max(psf, px / 2)
        row = {"objective": name, "depth_of_field_100nm_um": dof100, "depth_of_field_5um_um": dof5,
               "bead_5um_centre_above_glass_in_dofs": (D5 / 2 * 1e6) / dof5,
               "in_focus_bulk_beads_per_1e4_um2": {}, "stuck_density_threshold_per_1e4_um2": {}}
        for phi in VOLUME_FRACTIONS:
            n_b = phi / v100_um3                         # per um^3
            per_area = n_b * dof100 * 1e4                # per 100 um x 100 um
            row["in_focus_bulk_beads_per_1e4_um2"][f"{phi:g}"] = per_area
            row["stuck_density_threshold_per_1e4_um2"][f"{phi:g}"] = {
                f"{t * 1e3:g}ms": per_area * psf_eff**2 / (psf_eff**2 + 2 * D * t)
                for t in EXPOSURES_S}
        out["rows"].append(row)
    # the 5 um bead as a ball lens, for a transmitted-light search
    n_rel = N_PS / N_WATER
    out["ball_lens_focus_from_centre_um"] = n_rel * (D5 / 2 * 1e6) / (2 * (n_rel - 1))
    out["relative_index_5um"] = n_rel
    return out


# --------------------------------------------------------------------------- #
# item 3: the wall
# --------------------------------------------------------------------------- #


def d_parallel(h_over_a: float) -> float:
    """D_par / D0 for a sphere whose centre is h above a flat no-slip wall.
    Faxen's method-of-reflections series for gaps of a tenth of a radius and
    more; Goldman-Cox-Brenner's lubrication form below that. The two meet
    within about 8 per cent at the joint."""
    gap = h_over_a - 1.0
    if gap >= 0.1:
        x = 1.0 / h_over_a
        return 1 - 9 / 16 * x + x**3 / 8 - 45 / 256 * x**4 - x**5 / 16
    return 1.0 / (-(8 / 15) * math.log(gap) + 0.9588)


def d_perpendicular(h_over_a: float) -> float:
    """D_perp / D0, Brenner's exact series (1961)."""
    al = math.acosh(h_over_a)
    s = 0.0
    for n in range(1, 4000):
        num = 2 * math.sinh((2 * n + 1) * al) + (2 * n + 1) * math.sinh(2 * al)
        den = 4 * math.sinh((n + 0.5) * al) ** 2 - (2 * n + 1) ** 2 * math.sinh(al) ** 2
        term = n * (n + 1) / ((2 * n - 1) * (2 * n + 3)) * (num / den - 1)
        s += term
        if abs(term) < 1e-12 * abs(s):
            break
    return 1.0 / (4 / 3 * math.sinh(al) * s)


def height_where(fn, ratio, a) -> float:
    """Centre height (same unit as a) at which fn reaches `ratio` of bulk.
    Brenner's series needs ever more terms toward contact, so its bracket
    stops at a gap of 1e-4 radii, where D_perp is already far below 0.1."""
    low = 1 + (1e-4 if fn is d_perpendicular else 1e-12)
    return a * brentq(lambda x: fn(x) - ratio, low, 1e4)


def wall_tables() -> dict:
    a100, a5 = D100 / 2 * 1e6, D5 / 2 * 1e6       # um
    out = {}
    for label, a in (("100nm", a100), ("5um", a5)):
        out[label] = {
            "radius_um": a,
            "parallel_heights_um": {f"{r:g}": height_where(d_parallel, r, a) for r in (0.9, 0.5, 0.1)},
            "perpendicular_heights_um": {f"{r:g}": height_where(d_perpendicular, r, a) for r in (0.9, 0.5, 0.1)},
        }
    # 100 nm in a chamber: fraction of depth slower than 0.9, and the depth
    # average of D_par with both walls, drag increments added
    cham = []
    for L in DEPTHS_UM:
        z = np.linspace(a100 * 1.0001, L - a100 * 1.0001, 200001)
        g = (1 / np.array([d_parallel(x / a100) for x in z]) - 1
             + 1 / np.array([d_parallel((L - x) / a100) for x in z]) - 1 + 1)
        dpar = 1 / g
        cham.append({"chamber_depth_um": L, "fraction_slower_than_0.9": float(np.mean(dpar < 0.9)),
                     "depth_average_D_par_over_D0": float(np.mean(dpar))})
    out["100nm_chamber"] = cham
    # the trapped 5 um bead: timescales scale as D0 / D_par
    hs = [2.6, 2.75, 3.0, 3.5, 5, 7.5, 10, 25, 50]
    out["5um_by_height"] = [{"centre_height_um": h, "gap_um": h - a5,
                             "D_par_over_D0": d_parallel(h / a5),
                             "D_perp_over_D0": d_perpendicular(h / a5),
                             "timescale_factor": 1 / d_parallel(h / a5)} for h in hs]
    # a 5 um bead resting by gravity: gap of order the gravitational length
    lg = gravitational_length_m(D5) * 1e6
    out["5um_resting_gap_um"] = lg
    out["5um_resting_D_par_over_D0"] = d_parallel(1 + lg / a5)
    return out


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #


def main() -> None:
    t0 = time.time()

    def log(msg):
        print(f"[{time.time() - t0:7.0f}s] {msg}", flush=True)

    result = {
        "kind": "stage1_closed_forms",
        "qid": QID,
        "generated_by": "simulation_agent/src/focus_stage1.py",
        "interpreter": {"python": sys.version.split()[0], "platform": platform.platform(),
                        "numpy": np.__version__, "scipy": __import__("scipy").__version__,
                        "note": "run outside the sim pixi environment, which this computer does not have; uv with python 3.12, offline"},
        "validation": validate(),
    }
    log(f"validation {result['validation']}")
    result["item2_focus_planes"] = focus_planes()
    result["item3_wall"] = wall_tables()
    log("items 2 and 3 done")
    result["item1_bleach"] = bleach_tables(log)
    _write(result)
    result["item4_drift"] = drift_tables(log)
    _write(result)
    log("done")


def _round(x):
    if isinstance(x, float):
        return round_to_sig(x, 3) if x == x and x not in (float("inf"), float("-inf")) else None
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v) for v in x]
    return x


def _write(result) -> None:
    QDIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(_round(result), indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if "--report" in sys.argv:
        from report_focus import report
        report(json.loads(OUT.read_text(encoding="utf-8")), QDIR)
    else:
        main()
