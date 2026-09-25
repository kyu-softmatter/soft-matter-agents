"""Stage 3 of task 024: the simulated operating points, chosen from the closed form, with their cost.

    cd simulation_agent && python -m src.double_well_points <out.json>

The reduced dynamics depend on eps_1, eps_2 and d/w only, so a point is chosen
in those and maps onto every (k_1, w) with k_1 w^2 = eps_1 kT. Points:

- symmetric wells, eps in {24.7, 78.2, 247, 782, 2472} kT -- k1 = 1e-7 ... 1e-5 N/m at
  w = 1 um -- times barrier {1, 2, 4, 7, 10} kT, d solved from the potential;
- unequal wells at eps_1 = 247 kT, depth differences near 1 and 3 kT, barrier from the
  deeper well 5 kT.

The timestep is dt = 0.025/eps (w^2/D): 1e-4 at 247 kT, where Stage 1 showed the rate
within its error between 2e-4, 1e-4 and 5e-5. The record per point is sized from a
rate GUESS, rate ~ 0.06 (eps/247) exp(-(B - 5)), anchored on the one measured stiff point;
the guess sizes the run and is replaced by what the run returns.
"""

from __future__ import annotations

import json
import math
import sys

from . import double_well as dw

EPS = [24.72, 78.18, 247.2, 781.7, 2472.0]
BARRIERS = [1.0, 2.0, 4.0, 7.0, 10.0]
HOPS_TARGET = 4000          # pooled over walkers: about 2 per cent on a rate
WALKERS = 1000
T_MIN = 20.0


def d_for(eps1: float, eps2: float, level: float, which: str = "barrier_from_deeper") -> float:
    lo, hi = 0.5, 12.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        L = dw.Wells(eps1, eps2, m).landscape()
        b = 0.0 if L["merged"] else L[which]
        lo, hi = (m, hi) if b < level else (lo, m)
    return hi


def point(eps1, eps2, d, tag):
    L = dw.Wells(eps1, eps2, d).landscape()
    B = L["barrier_from_deeper"]
    guess = 0.06 * (eps1 / 247.2) * math.exp(-(B - 5.0))
    T = max(T_MIN, HOPS_TARGET / (WALKERS * guess))
    dt = 0.025 / eps1
    frames = 20000
    return {"tag": tag, "eps1": eps1, "eps2": eps2, "d": d, "landscape": L, "rate_guess": guess,
            "t": T, "dt": dt, "burn": min(T / 4, 5.0 / guess), "frame": T / frames,
            "walker_steps": WALKERS * (T + min(T / 4, 5.0 / guess)) / dt}


def main() -> None:
    pts = []
    for e in EPS:
        for B in BARRIERS:
            pts.append(point(e, e, d_for(e, e, B), f"sym_e{e:g}_B{B:g}"))
    e = 247.2
    for dep in (1.0, 3.0):
        r = 1 - dep / e * 1.0            # depth difference about dep kT; refined below by the landscape
        e2 = r * e
        pts.append(point(e, e2, d_for(e, e2, 5.0), f"asym_e{e:g}_dU{dep:g}_B5"))
    total = sum(p["walker_steps"] for p in pts)
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump({"walkers": WALKERS, "hops_target": HOPS_TARGET, "total_walker_steps": total,
                   "points": pts}, f, indent=1, default=float)
    for p in pts:
        print(f'{p["tag"]:28s} d={p["d"]:.4f} B={p["landscape"]["barrier_from_deeper"]:.2f} '
              f'Bsh={p["landscape"]["barrier_from_2"]:.2f} T={p["t"]:.0f} dt={p["dt"]:.1e} ws={p["walker_steps"]:.2e}')
    print("total walker-steps", f"{total:.2e}")


if __name__ == "__main__":
    main()
