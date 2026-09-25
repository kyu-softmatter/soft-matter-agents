"""Stage 4 of task 024: what ONE record shows, over many records, on the engine, streamed.

    cd simulation_agent && python -m src.double_well_spread <out.json> --k1 1e-6 --k2 1e-6 --w 1e-6
        --barrier 3 --walkers 200 --seed 1 [--dt 1e-3] [--hours 1] [--startup 10]

A bench record is one bead for 10-60 minutes at a 1-50 ms frame. A thousand
such records at 1 ms is billions of coordinates, far over the storage ceiling
as a trajectory, so nothing is stored: every walker's record goes through the
SAME estimator the experiment applies (`double_well.estimate`'s rule -- cores
around the two histogram peaks at a fraction of their spacing, sticky
milestoning on the projection), online, at three frame intervals at once, and
the per-record estimators are snapshotted at three record lengths.

The cores are placed the way the bench places them: from the pooled
histogram of the startup discard, at a 10 ms frame, before any record is
read. SI in and out; the engine runs in reduced units (`double_well_hoomd_backend`).

Per record, per (frame interval, record length): occupancy of well 1, both
ordered rates (transitions out of a well over time assigned to it), the hop
count, both mean completed residence times, and the projected free-energy
barrier from that record's own histogram.
"""

from __future__ import annotations

import argparse
import json
import math
import time

import numpy as np

from . import double_well as dw
from . import double_well_hoomd_backend as hb
from . import hoomd_backend

FRAMES_MS = (1, 10, 50)
RECORDS_MIN = (10, 30, 60)
BINS = 120
CORE_FRACTION = 0.2


class Online:
    """Sticky milestoning for every walker at one frame interval, with snapshot-able totals."""

    def __init__(self, n: int, c1: float, c2: float, radius: float, frame_s: float, lo: float, hi: float):
        self.c1, self.c2, self.R, self.f = c1, c2, radius, frame_s
        self.state = np.zeros(n, np.int8)
        self.t1 = np.zeros(n); self.t2 = np.zeros(n)
        self.n12 = np.zeros(n, np.int64); self.n21 = np.zeros(n, np.int64)
        self.dwell = np.zeros(n)                       # the current dwell, in s
        self.first = np.ones(n, bool)                  # the first dwell is cut by the record start
        self.d1s = np.zeros(n); self.d1n = np.zeros(n, np.int64)
        self.d2s = np.zeros(n); self.d2n = np.zeros(n, np.int64)
        self.edges = np.linspace(lo, hi, BINS + 1)
        self.hist = np.zeros((n, BINS), np.int64)
        self.frames = 0

    def update(self, x: np.ndarray) -> None:
        core = np.where(np.abs(x - self.c1) < self.R, 1, np.where(np.abs(x - self.c2) < self.R, 2, 0))
        new = np.where(core == 0, self.state, core).astype(np.int8)
        was = self.state
        ch12 = (was == 1) & (new == 2); ch21 = (was == 2) & (new == 1)
        ended = ch12 | ch21
        done = ended & ~self.first
        self.d1s += np.where(done & (was == 1), self.dwell, 0); self.d1n += done & (was == 1)
        self.d2s += np.where(done & (was == 2), self.dwell, 0); self.d2n += done & (was == 2)
        self.first &= ~ended
        self.dwell = np.where(ended, 0.0, self.dwell)
        self.n12 += ch12; self.n21 += ch21
        self.t1 += (was == 1) * self.f; self.t2 += (was == 2) * self.f
        self.dwell += (new > 0) * self.f
        self.state = new
        idx = np.clip(np.searchsorted(self.edges, x) - 1, 0, BINS - 1)
        np.add.at(self.hist, (np.arange(len(x)), idx), 1)
        self.frames += 1

    def snapshot(self) -> dict:
        with np.errstate(divide="ignore", invalid="ignore"):
            occ = self.t1 / (self.t1 + self.t2)
            r12 = np.where(self.t1 > 0, self.n12 / self.t1, np.nan)
            r21 = np.where(self.t2 > 0, self.n21 / self.t2, np.nan)
            res1 = np.where(self.d1n > 0, self.d1s / self.d1n, np.nan)
            res2 = np.where(self.d2n > 0, self.d2s / self.d2n, np.nan)
            mid = 0.5 * (self.edges[1:] + self.edges[:-1])
            inner = (mid > self.c1) & (mid < self.c2)
            p = self.hist / self.hist.sum(axis=1, keepdims=True)
            f = -np.log(p)
            left, right = mid < 0.5 * (self.c1 + self.c2), mid >= 0.5 * (self.c1 + self.c2)
            wells = np.minimum(np.min(np.where(left, f, np.inf), axis=1), np.min(np.where(right, f, np.inf), axis=1))
            barrier = np.max(np.where(inner, f, -np.inf), axis=1) - wells
        return {"occupancy_1": occ, "rate_12_per_s": r12, "rate_21_per_s": r21,
                "hops": (self.n12 + self.n21).astype(float), "residence_1_s": res1, "residence_2_s": res2,
                "barrier_projected_kT": barrier}


def summarise(v: np.ndarray) -> dict:
    v = np.asarray(v, float)
    fin = v[np.isfinite(v)]
    out = {"n_records": int(len(v)), "n_finite": int(len(fin))}
    if len(fin):
        out.update(mean=float(fin.mean()), sd=float(fin.std(ddof=1)) if len(fin) > 1 else None,
                   p05=float(np.percentile(fin, 5)), p25=float(np.percentile(fin, 25)),
                   p50=float(np.percentile(fin, 50)), p75=float(np.percentile(fin, 75)),
                   p95=float(np.percentile(fin, 95)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--k1", type=float, required=True); ap.add_argument("--k2", type=float, required=True)
    ap.add_argument("--w", type=float, required=True); ap.add_argument("--barrier", type=float, required=True)
    ap.add_argument("--walkers", type=int, default=200); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--dt", type=float, default=1e-3); ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--startup", type=float, default=10.0)
    ap.add_argument("--bead", type=float, default=5e-6); ap.add_argument("--T", type=float, default=293.0)
    ap.add_argument("--eta", type=float, default=1e-3)
    ap.add_argument("--records-min", type=float, nargs="+", default=list(RECORDS_MIN))
    a = ap.parse_args()
    p = {"temperature": a.T, "viscosity": a.eta, "bead_diameter": a.bead, "trap_stiffness_1": a.k1,
         "trap_stiffness_2": a.k2, "trap_width_1": a.w, "trap_width_2": a.w, "barrier_target": a.barrier,
         "integration_timestep": a.dt}
    r = hb.to_reduced(p)
    wells = dw.Wells(r["eps1"], r["eps2"], r["d"], 1.0, r["w2"])
    L = wells.landscape()
    hoomd = hoomd_backend._import_hoomd()
    sim, box = hb._build(hoomd, wells, a.walkers, r["dt"], a.seed)
    w1 = r["scales"]["length_m"]
    frame_steps = {ms: max(1, int(round(ms * 1e-3 / a.dt))) for ms in FRAMES_MS}
    base = min(frame_steps.values())

    def read():
        with sim.state.cpu_local_snapshot as s:
            order = np.argsort(s.particles.tag)
            x = np.array(s.particles.position[order, 0], float)
            img = np.array(s.particles.image[order, 0], float)
        return (x + img * box) * w1

    t0 = time.perf_counter()
    # startup: discard, but histogram it at 10 ms to place the cores as the bench would
    n_start = int(round(a.startup / a.dt))
    pooled = []
    for i in range(0, n_start, frame_steps[10]):
        sim.run(frame_steps[10]); pooled.append(read())
    pooled = np.concatenate(pooled)
    h, e = np.histogram(pooled, bins=400)
    mid = 0.5 * (e[1:] + e[:-1])
    c1 = float(mid[mid < 0][np.argmax(h[mid < 0])]); c2 = float(mid[mid >= 0][np.argmax(h[mid >= 0])])
    R = CORE_FRACTION * (c2 - c1)
    span = c2 - c1
    lo, hi = c1 - 1.5 * span / 2, c2 + 1.5 * span / 2
    trackers = {ms: Online(a.walkers, c1, c2, R, ms * 1e-3, lo, hi) for ms in FRAMES_MS}
    snaps = {}
    total_steps = int(round(a.hours * 3600 / a.dt))
    checkpoints = {int(round(m * 60 / a.dt)): m for m in a.records_min if m * 60 <= a.hours * 3600 + 1e-9}
    step = 0
    while step < total_steps:
        sim.run(base); step += base
        x = None
        for ms, k in frame_steps.items():
            if step % k == 0:
                x = read() if x is None else x
                trackers[ms].update(x)
        if step in checkpoints:
            m = checkpoints[step]
            snaps[m] = {ms: trackers[ms].snapshot() for ms in FRAMES_MS}
    wall = time.perf_counter() - t0
    out = {"args": vars(a), "engine": {"hoomd": hoomd.version.version, "gpu": bool(hoomd.version.gpu_enabled),
                                      "scheme": "hoomd.md.methods.Brownian (Euler-Maruyama)"},
           "engine_parameters": {k: v for k, v in r.items() if k != "scales"}, "scales": r["scales"],
           "landscape_reduced": L, "separation_m": r["separation_si"],
           "cores": {"peaks_m": [c1, c2], "radius_m": R, "fraction_of_spacing": CORE_FRACTION,
                     "placed_from": "pooled histogram of the startup discard at 10 ms"},
           "wall_s": wall, "walker_steps": a.walkers * (n_start + total_steps),
           "records": {}}
    for m, by in snaps.items():
        for ms, s in by.items():
            out["records"][f"{m}min_{ms}ms"] = {k: {"summary": summarise(v), "values": [None if not math.isfinite(z) else float(z) for z in v]}
                                                for k, v in s.items()}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f)


if __name__ == "__main__":
    main()
