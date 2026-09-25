"""Stage 3 of task 024, the half that needs no simulation: the double well's closed-form map in SI.

    cd simulation_agent && python -m src.double_well_map <out.json>

Over trap width w (equal for both traps), holding stiffness k1, stiffness ratio
k2/k1 and separation d, everything here is COMPUTED FROM THE POTENTIAL -- no
run enters it:

- each well's depth eps_i = k_i w^2 / kT, since k_i = eps_i / w^2 exactly;
- the minima and the saddle on the joining line, and the barrier from each well;
- the Boltzmann occupancy of well 1, split at the saddle, on a 2-D grid;
- the separation window where the barrier from the deeper well lies in 1-10 kT,
  and the slope of that barrier in kT per 10 nm -- the number that says whether
  trap positioning precision decides feasibility before anything else does.

Inputs that are not computed here are stated, with provenance, in the output's
`inputs`: the bead diameter and the temperature and viscosity. Reduced units
(length w, energy kT) are internal; the output is in SI.
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np

from . import double_well as dw

INPUTS = {
    "bead_diameter_m": {"value": 5.0e-6, "provenance": "the bead the microscope side expects (microscope task 047); "
                        "the store holds it as a measured diameter -- to be cited through the pipeline"},
    "temperature_K": {"value": 293.0, "provenance": "the room reading the person gave; assumed for the sample"},
    "viscosity_Pa_s": {"value": 1.0e-3, "provenance": "water near 20 C, assumed; the re-prediction takes the "
                       "in-situ diffusivity instead"},
}
WIDTHS_M = [1.0e-6, 1.5e-6, 2.5e-6]
K1_N_PER_M = list(np.logspace(-7, -5, 9))      # two decades around 1 pN/um, 4 points per decade
RATIOS = [1.0, 0.5, 0.2, 0.1, 0.01]


def _bshallow_1kT(eps1: float, eps2: float) -> tuple[float, dict] | None:
    """The separation where the shallower well's own barrier is 1 kT, and the landscape there."""
    lo, hi = 0.5, 12.0
    for _ in range(40):
        m = 0.5 * (lo + hi)
        L = dw.Wells(eps1, eps2, m).landscape()
        b = 0.0 if L["merged"] else L["barrier_from_2"]
        lo, hi = (m, hi) if b < 1.0 else (lo, m)
    L = dw.Wells(eps1, eps2, hi).landscape()
    return None if L["merged"] else (hi, L)


def mismatch_tolerance(eps1: float, deep_limit: float = 10.0) -> dict:
    """How unequal the two stiffnesses may be and still leave hops both ways.

    For k2/k1 = r < 1 the shallower well vanishes first. Take the separation where
    its own barrier is 1 kT -- the least it can hold and still be a well -- and ask
    what the barrier from the deeper well is there. The tolerance is the r at which
    that reaches `deep_limit` kT. Widths are equal, so a width mismatch enters the
    same way through eps_i = k_i w_i^2: a width mismatch of half this fraction costs the same.
    """
    def excess(r):
        s = _bshallow_1kT(eps1, r * eps1)
        return (float("inf") if s is None else s[1]["barrier_from_1"]) - deep_limit
    lo, hi = 0.0, 1.0            # excess(lo) > 0 (hopeless), excess(1) < 0 (symmetric: 1 kT both ways)
    lo = 1.0 - min(1.0, 50.0 / eps1)
    if excess(lo) < 0:
        lo = 0.0
    for _ in range(25):          # r to 3e-8 of its bracket
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if excess(m) > 0 else (lo, m)
    r = hi
    return {"k2_over_k1_min": r, "stiffness_mismatch_tolerance_percent": 100 * (1 - r),
            "depth_difference_kT": (1 - r) * eps1}


def scan_separation(eps1: float, eps2: float, d_lo: float, d_hi: float, n: int) -> list[dict]:
    rows = []
    for d in np.linspace(d_lo, d_hi, n):
        L = dw.Wells(eps1, eps2, d).landscape()
        L["d_over_w"] = float(d)
        rows.append(L)
    return rows


def window(eps1: float, eps2: float) -> dict:
    """Where the barrier from the deeper well is 1-10 kT, found by bisection on d/w."""
    def bdeep(d):
        L = dw.Wells(eps1, eps2, d).landscape()
        return (0.0 if L["merged"] else L["barrier_from_deeper"]), L

    # barrier rises with separation from the merge point: bracket then bisect for each level
    def solve(level):
        lo, hi = 0.5, 12.0
        if bdeep(hi)[0] < level:
            return None
        for _ in range(60):
            m = 0.5 * (lo + hi)
            if bdeep(m)[0] < level:
                lo = m
            else:
                hi = m
        return 0.5 * (lo + hi)

    d1, d10 = solve(1.0), solve(10.0)
    out = {"d_over_w_at_1kT": d1, "d_over_w_at_10kT": d10}
    if d1 is None or d10 is None:
        return out
    # With unequal wells the shallow one vanishes first, and at that separation the barrier
    # from the deeper well is still about the depth difference -- it JUMPS to zero rather
    # than passing through 1-10 kT. Bisection then lands on the merge point; say so.
    b_lo = bdeep(d1 + 1e-9)[0]
    if b_lo > 10.0:
        out.update({"d_over_w_at_1kT": None, "d_over_w_at_10kT": None,
                    "no_window": f"the shallower well vanishes at d/w = {d1:.6f} while the barrier from the "
                                 f"deeper one is still {b_lo:.1f} kT: it never lies in 1-10 kT",
                    "merge_d_over_w": d1, "barrier_from_deeper_at_merge_kT": b_lo})
        return out
    pts = {}
    for name, d in (("at_1kT", d1), ("mid", 0.5 * (d1 + d10)), ("at_10kT", d10)):
        W = dw.Wells(eps1, eps2, d)
        L = W.landscape()
        h = 1e-4
        slope = (bdeep(d + h)[0] - bdeep(d - h)[0]) / (2 * h)       # kT per w
        L["slope_kT_per_w"] = slope
        L["d_over_w"] = d
        L["occupancy_1_boltzmann"] = None if L["merged"] else W.boltzmann_weight_1(L["x_saddle"], n=601)
        pts[name] = L
    out["points"] = pts
    return out


def main() -> None:
    kT = dw.K_B * INPUTS["temperature_K"]["value"]
    sc = dw.si_scales(INPUTS["temperature_K"]["value"], INPUTS["viscosity_Pa_s"]["value"],
                      INPUTS["bead_diameter_m"]["value"], 1.0)
    rows = []
    tol = []
    for w in WIDTHS_M:
        for k1 in K1_N_PER_M:
            t = mismatch_tolerance(k1 * w ** 2 / kT)
            t.update({"w_m": w, "k1_N_per_m": float(k1), "eps1_kT": k1 * w ** 2 / kT})
            tol.append(t)
    rows = []
    for w in WIDTHS_M:
        for k1 in K1_N_PER_M:
            for ratio in RATIOS:
                eps1 = k1 * w ** 2 / kT
                eps2 = ratio * eps1
                r = {"w_m": w, "k1_N_per_m": float(k1), "k2_over_k1": ratio,
                     "eps1_kT": eps1, "eps2_kT": eps2, "time_unit_s": w ** 2 / sc["D_m2_s"]}
                win = window(eps1, eps2)
                r.update(win)
                if win.get("points"):
                    for p in win["points"].values():
                        p["d_m"] = p["d_over_w"] * w
                        p["slope_kT_per_10nm"] = p["slope_kT_per_w"] * 10e-9 / w
                    r["window_width_nm"] = (win["d_over_w_at_10kT"] - win["d_over_w_at_1kT"]) * w * 1e9
                rows.append(r)
    out = {"inputs": INPUTS, "kT_J": kT, "D_free_m2_s": sc["D_m2_s"],
           "provenance": "every number below is computed from the potential; none is measured or simulated",
           "stiffness_mismatch_tolerance": tol,
           "rows": rows}
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)


if __name__ == "__main__":
    main()
