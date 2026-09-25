"""Stage 1 of task 024: one validation job for the double well, NumPy or HOOMD.

    cd simulation_agent && python -m src.double_well_validate <engine> <seed> <dt> <out.json>
        [--walkers N] [--t 400] [--burn 20] [--eps 6 5] [--d 3] [--frame 0.01]

Reduced units (length w_1, energy kT, time w_1^2/D). Each job is one replicate;
the standard error is taken across jobs with different seeds, never as one over
root-N inside a job. Two definitions are reported for every job:

- `disk_every_step`: 2-D disk of radius 0.5 w tested at every step -- the
  manager's scratch definition, kept only to close the rate-gap question;
- `projection`: |x - c_i| < R on the joining line at the frame interval -- the
  one the experiment can apply, for R in {0.25, 0.5, 1.0}.
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np

from . import double_well as dw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("engine", choices=["numpy", "hoomd"])
    ap.add_argument("seed", type=int)
    ap.add_argument("dt", type=float)
    ap.add_argument("out")
    ap.add_argument("--walkers", type=int, default=500)
    ap.add_argument("--t", type=float, default=400.0)
    ap.add_argument("--burn", type=float, default=20.0)
    ap.add_argument("--eps", type=float, nargs=2, default=[6.0, 5.0])
    ap.add_argument("--d", type=float, default=3.0)
    ap.add_argument("--frame", type=float, default=0.01)
    ap.add_argument("--disk", type=float, default=0.5)
    ap.add_argument("--no-disk", action="store_true",
                    help="skip the every-step disk definition, which costs a readout per step on HOOMD")
    ap.add_argument("--cores", choices=["centres", "minima"], default="centres",
                    help="milestone cores around the trap centres, or around the minima of the "
                         "potential on the joining line with radii 0.1/0.2/0.3 of their spacing")
    a = ap.parse_args()
    w = dw.Wells(a.eps[0], a.eps[1], a.d)
    save = max(1, int(round(a.frame / a.dt)))
    tracker = None if a.no_disk else dw.DiskTracker(w, a.walkers, a.disk)
    t0 = time.perf_counter()
    if a.engine == "numpy":
        x = dw.integrate_numpy(w, a.walkers, a.t, a.dt, save, a.burn, a.seed, tracker=tracker)
        timing = {"wall_s": time.perf_counter() - t0}
    else:
        from . import double_well_hoomd_backend as hb
        x, timing = hb.integrate_hoomd(w, a.walkers, a.t, a.dt, save, a.burn, a.seed, tracker=tracker)
    out = {"args": vars(a), "timing": timing, "projection": {}}
    if tracker is not None:
        d = tracker.result(a.dt)
        out["disk_every_step"] = {"occupancy_1": float(d["occupancy_1_per_walker"].mean()),
                                  "rate": float(d["rate_per_walker"].mean())}
    L = w.landscape()
    out["landscape"] = L
    if not L["merged"]:
        # definition-free occupancy: the fraction of frames on well 1's side of the saddle,
        # against the exact Boltzmann weight split at the same line
        out["fraction_below_saddle"] = float((x < L["x_saddle"]).mean())
        out["boltzmann_split_at_saddle"] = w.boltzmann_weight_1(L["x_saddle"], n=801)
    if a.cores == "minima":
        c1, c2 = L["x1"], L["x2"]
        radii = [f * (c2 - c1) for f in (0.1, 0.2, 0.3)]
    else:
        c1, c2 = w.c1, w.c2
        radii = [0.25, 0.5, 1.0]
    out["cores"] = {"from": a.cores, "c1": c1, "c2": c2, "radii": radii}
    for i, R in enumerate(radii):
        est = dw.estimate(x, save * a.dt, c1, c2, R)
        ok = [e for e in est if e is not None]
        key = str(R) if a.cores == "centres" else f"r{i}"
        out["projection"][key] = {k: float(np.nanmean([e[k] for e in ok]))
                                  for k in ("occupancy_1", "rate", "rate_12", "rate_21", "residence_1", "residence_2")}
        out["projection"][key]["unassigned_walkers"] = len(est) - len(ok)
        out["projection"][key]["radius"] = R
    # the projected free-energy barrier needs the pooled histogram, not per walker
    out["projection"]["barrier_pooled"] = dw._hist_barrier(x.ravel(), c1, c2, 120)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
