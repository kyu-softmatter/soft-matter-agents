"""What two equal traps predict for Friday's double-well observations, by trap shape (card 050).

    python src/diagnose_double_well_20260928.py

Touches no device and reads no frame. It takes one bead in the sum of two equal
single-trap potentials along the line joining them and computes, from Boltzmann
statistics, what each candidate shape predicts for the three things Friday's
records state in words (questions/mic-20260928-001/diagnosis_candidates.json):

  - at the first position the bead sat about 1 um toward trap_2 at equal
    strengths, in one basin, held more stiffly than by trap_1 alone
  - at a commanded 5 um trap_2 pulled nothing measurable
  - no hop anywhere

Every result is an illustration of an ASSUMED shape, so it is an estimate and
never a measurement: the trap's real profile is a gap in the store
(trap_potential_width_absent). One line of output checks the arithmetic
against the simulation's own number instead: its Gaussian at 1 pN/um and a
1 um width gives a 3.00 k_B*T barrier at 2.124 um (the ask at 735a1a0).

The last block reads the first-position observation against the simulation's
width without assuming the separation or equal traps: over every separation
and a trap_2 at half to all of trap_1's depth, how spread a bead is when it
sits 0.5 to 1.5 um toward trap_2 in one basin.

Inputs and where they come from:
  k_B*T     lab_ambient_temperature, 293 K, operator_read E3 -- the room's, not the sample's
  eta       water_viscosity_293k, 1e-3 Pa*s, E3
  a         half of tracer_diameter_measured, 5 um, calibration E2
  tau       "the bead relaxes in about 30 ms, one frame": Friday's analysis,
            stated in src/report_20260925.py; measured on preparatory recordings
  k1        6*pi*eta*a / tau, Stokes drag in an unbounded medium; the wall makes
            the drag, and so this stiffness, larger (wall_drag_correction_absent)
"""

from __future__ import annotations

import os
import sys

# The four lines every script in src/ carries: src/ holds operator.py, which
# shadows the standard module for anything imported after it (operator.py's header).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import math                                                      # noqa: E402

import numpy as np                                               # noqa: E402

UM = 1e-6
KT = 1.380649e-23 * 293.0              # lab_ambient_temperature, E3
ETA = 1e-3                             # water_viscosity_293k, E3
A = 2.5 * UM                           # tracer_diameter_measured / 2, E2
TAU = 0.030                            # Friday's stated relaxation time
GAMMA = 6 * math.pi * ETA * A
K1 = GAMMA / TAU
DX = 1e-9                              # grid step, 1 nm


def gaussian(w: float, k: float = K1):
    depth = k * w * w

    def u(r):
        return -depth * np.exp(-r * r / (2 * w * w))
    return u, depth


def bead_limited(r1: float, r2: float, k: float = K1):
    """Force k*r out to r1, then falling linearly to zero at r2, zero beyond."""
    depth = 0.5 * k * r1 * r2

    def u(r):
        r = np.abs(r)
        core = -depth + 0.5 * k * r * r
        fall = -0.5 * k * r1 * (r2 - r) ** 2 / (r2 - r1)
        return np.where(r <= r1, core, np.where(r <= r2, fall, 0.0))
    return u, depth


def scaled(u, factor: float):
    """The same shape at a fraction of the depth: an unequal trap_2."""
    return lambda r: factor * u(r)


def basin(u, d: float, u2=None) -> dict:
    """Trap_1's basin, as a bead left at trap_1's centre would find it.

    Descends from x = 0 to the first minimum, then climbs to the first maximum
    beyond it. A maximum short of trap_2's centre is the saddle; none means the
    two traps make one basin. The bead's statistics are Boltzmann weights over
    the basin, up to the saddle -- a bead that has not crossed.
    """
    x = np.arange(-6 * UM, d + 6 * UM, DX)
    U = u(x) + (u2 or u)(x - d)
    dU = np.diff(U)
    i0 = int(np.argmin(np.abs(x)))
    if dU[i0] < 0:                                            # downhill toward trap_2
        up = np.nonzero(dU[i0:] >= 0)[0]
        m = i0 + int(up[0]) if up.size else len(U) - 1
    else:
        m = i0
    down = np.nonzero(dU[m:] < 0)[0]
    s = m + int(down[0]) if down.size else None
    saddle = s if s is not None and x[s] < d else None
    hi = saddle if saddle is not None else len(U) - 1
    wgt = np.exp(-(U[:hi + 1] - U[m]) / KT)
    xs = x[:hi + 1]
    mean = float((wgt * xs).sum() / wgt.sum())
    var = float((wgt * (xs - mean) ** 2).sum() / wgt.sum())
    return {"minimum_um": x[m] / UM, "mean_um": mean / UM, "std_nm": math.sqrt(var) * 1e9,
            "barrier_kT": float((U[saddle] - U[m]) / KT) if saddle is not None else 0.0}


def _single(u) -> dict:
    x = np.arange(-6 * UM, 6 * UM, DX)
    U = u(x)
    wgt = np.exp(-(U - U.min()) / KT)
    mean = float((wgt * x).sum() / wgt.sum())
    return {"std_nm": math.sqrt(float((wgt * (x - mean) ** 2).sum() / wgt.sum())) * 1e9}


def window(u, lo: float = 1.0, hi: float = 4.0) -> tuple[float, float] | None:
    """The separations at which trap_1's barrier lies between lo and hi k_B*T."""
    ds = np.arange(1.0, 7.0, 0.002) * UM
    inside = [d for d in ds if lo <= basin(u, d)["barrier_kT"] <= hi]
    return (min(inside) / UM, max(inside) / UM) if inside else None


def merge_separation(u) -> float:
    ds = np.arange(1.0, 7.0, 0.005) * UM
    merged = [d for d in ds if basin(u, d)["barrier_kT"] == 0.0]
    return max(merged) / UM if merged else float("nan")


def main() -> int:
    print(f"inputs: k_B*T {KT:.3e} J, gamma {GAMMA:.3e} N*s/m (unbounded), "
          f"k1 = gamma/tau {K1 * 1e6:.2f} pN/um, single-trap spread {math.sqrt(KT / K1) * 1e9:.0f} nm")

    # The arithmetic, checked against the simulation's own number.
    u_sim, _ = gaussian(1.0 * UM, k=1e-6)
    print(f"check: simulation's Gaussian, 1 pN/um, w 1 um, d 2.124 um -> barrier "
          f"{basin(u_sim, 2.124 * UM)['barrier_kT']:.2f} kT (the ask states 3.00)")

    shapes = [("gaussian w 1.0 um (the simulation's width)", gaussian(1.0 * UM)),
              ("gaussian w 1.5 um", gaussian(1.5 * UM)),
              ("gaussian w 2.0 um", gaussian(2.0 * UM)),
              ("gaussian w 2.5 um (the bead radius)", gaussian(2.5 * UM)),
              ("bead-limited, linear to 1.5 um, zero by 3.5 um", bead_limited(1.5 * UM, 3.5 * UM)),
              ("bead-limited, linear to 1.0 um, zero by 2.5 um", bead_limited(1.0 * UM, 2.5 * UM))]
    for name, (u, depth) in shapes:
        s1 = _single(u)["std_nm"]
        at2 = basin(u, 2.0 * UM)
        at5 = basin(u, 5.0 * UM)
        win = window(u)
        dc = merge_separation(u)
        wtxt = f"{win[0]:.3f}-{win[1]:.3f} um ({(win[1] - win[0]) * 1e3:.0f} nm wide)" if win else "none"
        print(f"\n{name}: depth {depth / KT:.0f} kT, one basin up to {dc:.2f} um")
        print(f"  d 2.0 um, equal: bead at {at2['mean_um']:.2f} um, spread {at2['std_nm']:.0f} nm "
              f"= {at2['std_nm'] / s1:.2f} x one trap's {s1:.0f} nm, barrier {at2['barrier_kT']:.1f} kT")
        print(f"  d 5.0 um, equal: bead pulled {at5['mean_um'] * 1e3:.0f} nm toward trap_2, "
              f"spread {at5['std_nm'] / s1:.2f} x one trap's, barrier {at5['barrier_kT']:.0f} kT")
        print(f"  barrier 1-4 kT at {wtxt}")
        tail = basin(u, (dc + 1.0) * UM)
        print(f"  d {dc + 1.0:.2f} um, 1 um beyond one basin: bead pulled {tail['mean_um'] * 1e3:.0f} nm "
              f"toward trap_2")

    # Friday's first position, read against the simulation's width without
    # assuming the separation or that the two traps were equal: every
    # separation and every trap_2 depth at which a bead left in trap_1 sits
    # "about 1 um" toward trap_2 in one basin, and how spread it is there.
    u, _ = gaussian(1.0 * UM)
    s1 = _single(u)["std_nm"]
    hits = []
    for ratio in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):
        for d in np.arange(1.0, 4.0, 0.01) * UM:
            b = basin(u, d, scaled(u, ratio))
            if b["barrier_kT"] == 0.0 and 0.5 <= b["mean_um"] <= 1.5:
                hits.append((b["std_nm"] / s1, ratio, d / UM, b["mean_um"]))
    print("\nsimulation's width, any separation, trap_2 at 0.5-1.0 of trap_1's depth, one basin:")
    for a, b in ((0.5, 0.7), (0.7, 0.9), (0.9, 1.1), (1.1, 1.3), (1.3, 1.5)):
        inbin = [h for h in hits if a <= h[3] < b]
        if inbin:
            lo, hi = min(inbin), max(inbin)
            print(f"  bead {a:.1f}-{b:.1f} um toward trap_2: spread {lo[0]:.2f}-{hi[0]:.2f} x one trap's "
                  f"(separations {min(h[2] for h in inbin):.2f}-{max(h[2] for h in inbin):.2f} um)")
        else:
            print(f"  bead {a:.1f}-{b:.1f} um toward trap_2: no separation or ratio does it in one basin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
