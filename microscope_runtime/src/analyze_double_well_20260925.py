"""Analyse the 2026-09-25 trap-strength recordings by the method declared before any data.

    python src/analyze_double_well_20260925.py <rec_dir> [label ...]

The declaration is questions/mic-20260925-001/analysis_method_declared.json,
committed at 5cd2b54 before this seat opened any frame. What follows it and
where this departs from it are both stated in each output file, so a reader
never has to compare the two by hand.

Per recording (<label>.raw, uint16, 256 x 256, C order; <label>_meta.jsonl):
  1. localisation: intensity-weighted centroid of a fixed window around the
     previous frame's centre, after subtracting the window's median. A frame
     whose centroid jumps more than half the window, or whose window touches
     the edge, is marked lost, never interpolated
  2. scale: 0.065 um per pixel, pixel_size_100x_zoom_1x (calibration, E2),
     never frame metadata. x is the camera's column axis; the tweezers' +x is
     right on screen (tweez300_positive_x_is_right_on_screen), so the trap
     axis is x and y is the perpendicular, kept and reported
  3. stiffness, where only trap_1 holds the bead (trap_2 at 0): the power
     spectrum of x and of y, fitted by maximum likelihood to the spectrum of
     an overdamped oscillator sampled every frame and averaged over the
     exposure, which returns the corner time and the diffusivity together;
     k = k_B*T/(D*tau_c). Equipartition, k_B*T/var, beside it, never averaged;
     a factor-two disagreement reports the stiffness as not determined
  4. two wells: the simulation's milestone rule -- cores around the two
     highest peaks of the projected histogram, radius 0.2 of their spacing,
     sticky at the frame interval. If two peaks cannot be found the record is
     reported as one basin and no well statistics are computed
Temperature: lab_ambient_temperature, 20 C, operator reading E3, the room's
and not the sample's.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import json                                                      # noqa: E402
import math                                                      # noqa: E402
from pathlib import Path                                         # noqa: E402

import numpy as np

N_PX = 256
UM_PER_PX = 0.065                      # pixel_size_100x_zoom_1x, E2
KT = 1.380649e-23 * 293.15             # lab_ambient_temperature, 20 C, E3
WINDOW = 150                           # px, larger than the ~100 px bead image
CORE_FRACTION = 0.2                    # the simulation's milestone_core_fraction


def frames(raw: Path):
    n = raw.stat().st_size // (N_PX * N_PX * 2)
    return np.memmap(raw, dtype=np.uint16, mode="r", shape=(n, N_PX, N_PX))


def localise(stack) -> dict:
    n = stack.shape[0]
    xs, ys = np.full(n, np.nan), np.full(n, np.nan)
    lost = 0
    first = stack[0].astype(float)
    bg = np.median(first)
    w = np.clip(first - bg, 0, None)
    yy, xx = np.indices(first.shape)
    cx, cy = float((w * xx).sum() / w.sum()), float((w * yy).sum() / w.sum())
    h = WINDOW // 2
    for i in range(n):
        x0, y0 = int(round(cx)) - h, int(round(cy)) - h
        if x0 < 0 or y0 < 0 or x0 + WINDOW > N_PX or y0 + WINDOW > N_PX:
            lost += 1
            continue
        win = stack[i, y0:y0 + WINDOW, x0:x0 + WINDOW].astype(float)
        win = np.clip(win - np.median(win), 0, None)
        s = win.sum()
        if s <= 0:
            lost += 1
            continue
        wy, wx = np.indices(win.shape)
        nx, ny = x0 + (win * wx).sum() / s, y0 + (win * wy).sum() / s
        if math.hypot(nx - cx, ny - cy) > h:
            lost += 1
            continue
        xs[i], ys[i], cx, cy = nx, ny, nx, ny
    return {"x_px": xs, "y_px": ys, "lost": lost}


def ou_blur_psd(f, tau, D, dt):
    """One-sided PSD of an OU process averaged over a full-frame exposure and sampled every dt."""
    a = math.exp(-dt / tau)
    var = D * tau                                    # k_B*T/k in m^2
    r = dt / tau
    c0 = var * 2.0 / r**2 * (r - 1.0 + a)            # lag-0 covariance of the exposure average
    c1 = var * (1.0 - a) ** 2 / r**2                 # lag-1; lag k is c1 * a**(k-1)
    z = np.exp(-2j * np.pi * f * dt)
    s = c0 + 2.0 * np.real(c1 * z / (1.0 - a * z))
    return 2.0 * dt * s


def fit_psd(x_m: np.ndarray, dt: float, blocks: int = 20) -> dict:
    x = x_m[np.isfinite(x_m)]
    x = x - x.mean()
    m = len(x) // blocks
    segs = x[: m * blocks].reshape(blocks, m)
    f = np.fft.rfftfreq(m, dt)[1:]
    P = (2.0 * dt / m) * np.abs(np.fft.rfft(segs, axis=1)[:, 1:]) ** 2
    P = P.mean(axis=0)
    keep = f <= 0.8 * (0.5 / dt)
    f, P = f[keep], P[keep]

    def nll(logp):
        tau, D = math.exp(logp[0]), math.exp(logp[1])
        model = ou_blur_psd(f, tau, D, dt)
        return float(np.sum(blocks * (P / model + np.log(model))))

    best = None
    var = float(np.var(x))
    for tau0 in np.logspace(-3, 1, 25):
        D0 = var / tau0
        v = nll([math.log(tau0), math.log(D0)])
        if best is None or v < best[0]:
            best = (v, math.log(tau0), math.log(D0))
    p = np.array(best[1:])
    step = 0.5
    for _ in range(400):                              # coordinate descent, then shrink
        improved = False
        for j in range(2):
            for s in (step, -step):
                q = p.copy(); q[j] += s
                if nll(q) < nll(p):
                    p, improved = q, True
        if not improved:
            step /= 2
            if step < 1e-5:
                break
    tau, D = math.exp(p[0]), math.exp(p[1])
    k_psd = KT / (D * tau)
    k_eq = KT / var
    agree = max(k_psd, k_eq) / min(k_psd, k_eq) <= 2.0
    return {"tau_c_s": tau, "D_m2_per_s": D, "D_um2_per_s": D * 1e12,
            "k_psd_N_per_m": k_psd, "k_psd_pN_per_um": k_psd * 1e6,
            "k_equipartition_pN_per_um": k_eq * 1e6, "var_um2": var * 1e12,
            "agree_within_2x": bool(agree),
            "stiffness_reported": (k_psd * 1e6) if agree else None,
            "fit": {"blocks": blocks, "points_per_block": m, "f_max_hz": float(f.max()),
                    "f_min_hz": float(f.min())}}


def milestones(x_um: np.ndarray, dt: float) -> dict:
    x = x_um[np.isfinite(x_um)]
    spacing0 = 0.02
    edges = np.arange(x.min(), x.max() + spacing0, spacing0)
    hist, e = np.histogram(x, bins=edges)
    c = 0.5 * (e[1:] + e[:-1])
    sm = np.convolve(hist, np.ones(5) / 5, mode="same")
    peaks = [i for i in range(1, len(sm) - 1) if sm[i] >= sm[i - 1] and sm[i] > sm[i + 1]]
    peaks = sorted(peaks, key=lambda i: sm[i], reverse=True)[:2]
    if len(peaks) < 2 or sm[min(peaks)] <= 0 or abs(c[peaks[0]] - c[peaks[1]]) < 5 * spacing0:
        return {"basins": 1, "note": "two peaks could not be found; reported as one basin and no well "
                                      "statistics computed, as declared"}
    m1, m2 = sorted([c[peaks[0]], c[peaks[1]]])
    r = CORE_FRACTION * (m2 - m1)
    state, assigned, exits = 0, [], {1: 0, 2: 0}
    for v in x:
        new = 1 if abs(v - m1) <= r else 2 if abs(v - m2) <= r else state
        if state and new != state:
            exits[state] += 1
        state = new
        assigned.append(state)
    a = np.array(assigned)
    t1, t2 = (a == 1).sum() * dt, (a == 2).sum() * dt
    return {"basins": 2, "minima_um": [m1, m2], "core_radius_um": r,
            "occupancy_well_1": t1 / (t1 + t2), "occupancy_well_2": t2 / (t1 + t2),
            "transitions_1_to_2": exits[1], "transitions_2_to_1": exits[2],
            "rate_1_to_2_per_s": exits[1] / t1 if t1 else None,
            "rate_2_to_1_per_s": exits[2] / t2 if t2 else None,
            "residence_renewal_1_s": t1 / exits[1] if exits[1] else None,
            "residence_renewal_2_s": t2 / exits[2] if exits[2] else None,
            "frames_before_first_core": int((a == 0).sum())}


def analyse(rec_dir: Path, label: str) -> dict:
    raw = rec_dir / f"{label}.raw"
    meta = [json.loads(l) for l in (rec_dir / f"{label}_meta.jsonl").open()]
    t = np.array([float(m["ElapsedTime-ms"]) for m in meta]) / 1000.0
    dt = float(np.median(np.diff(t)))
    gaps = int((np.diff(t) > 1.5 * dt).sum())
    loc = localise(frames(raw))
    x_um, y_um = loc["x_px"] * UM_PER_PX, loc["y_px"] * UM_PER_PX
    out = {"label": label, "frames": len(meta), "frame_interval_s": dt, "timestamp_gaps": gaps,
           "record_length_s": float(t[-1] - t[0]), "lost_frames": loc["lost"],
           "mean_position_um": [float(np.nanmean(x_um)), float(np.nanmean(y_um))],
           "std_um": [float(np.nanstd(x_um)), float(np.nanstd(y_um))],
           "drift_um_first_to_last_minute": [
               float(np.nanmean(x_um[-2000:]) - np.nanmean(x_um[:2000])),
               float(np.nanmean(y_um[-2000:]) - np.nanmean(y_um[:2000]))],
           "psd_x": fit_psd(x_um * 1e-6, dt), "psd_y": fit_psd(y_um * 1e-6, dt),
           "milestoning_x": milestones(x_um, dt),
           "method": "questions/mic-20260925-001/analysis_method_declared.json at 5cd2b54",
           "departures": [
               "Single-trap records are the 1/0 recordings (trap_2 at strength 0, still on), not "
               "records with trap_2 off, as the declaration imagined",
               "The exposure is taken equal to the frame interval (30 ms) in the blur model; the "
               "camera's exposure/readout overlap was not measured",
               "No localisation-noise floor is fitted; the declaration named none"]}
    np.save(rec_dir / f"{label}_xy_um.npy", np.stack([x_um, y_um]))
    (rec_dir / f"{label}_analysis.json").write_text(json.dumps(out, indent=2, default=float))
    return out


def main() -> int:
    rec_dir = Path(sys.argv[1])
    labels = sys.argv[2:] or sorted(p.stem for p in rec_dir.glob("strength_*.raw"))
    for label in labels:
        r = analyse(rec_dir, label)
        px, py = r["psd_x"], r["psd_y"]
        print(f"{label}: frames {r['frames']} lost {r['lost_frames']} gaps {r['timestamp_gaps']} | "
              f"mean ({r['mean_position_um'][0]:.2f},{r['mean_position_um'][1]:.2f}) um "
              f"std ({r['std_um'][0]*1000:.0f},{r['std_um'][1]*1000:.0f}) nm | "
              f"k_x psd {px['k_psd_pN_per_um']:.3g} eq {px['k_equipartition_pN_per_um']:.3g} pN/um, "
              f"D_x {px['D_um2_per_s']:.3g} um2/s | basins {r['milestoning_x']['basins']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
