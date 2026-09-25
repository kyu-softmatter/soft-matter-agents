"""psi6 and the structural relaxation time, read from saved frames.

The observable `structural_relaxation_time` (contracts/observables.json) is
the time at which the particle-averaged bond-orientational order parameter
psi6(t) first reaches a declared fraction of its plateau, the plateau being
fitted over a declared window at the end of the record. Both knobs -- the
fraction and the window -- are conditions the plan carries; nothing here
chooses either.

Neighbours are Voronoi neighbours, found by a Delaunay triangulation of the
positions FOLDED into the periodic box and tiled with their eight periodic
images, so a particle at the edge sees its true neighbours across the
boundary. Positions arrive UNWRAPPED (the trajectory convention, task 021)
and are folded here: folding is a one-way operation and the record keeps
the direction that can be undone.

    psi6_j     = | (1/n_j) sum_k exp(6 i theta_jk) |      per particle
    psi6(t)    = mean_j psi6_j                              the curve the criterion reads
    psi6_glob  = | mean_j (1/n_j) sum_k exp(6 i theta_jk) | reported beside it

The curve the relaxation time is read from is the mean of the per-particle
magnitudes (local order). The global magnitude is reported too, because the
two answer different questions -- locally ordered patches with mismatched
orientations score high on the first and low on the second -- and which one
the vocabulary's estimator means is stated here rather than left to a reader.
"""

from __future__ import annotations

import numpy as np


def fold(positions: np.ndarray, box: np.ndarray) -> np.ndarray:
    """Unwrapped -> inside [0, L) per axis."""
    return np.mod(positions, box)


def psi6_per_particle(positions: np.ndarray, box: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-particle psi6 magnitudes and the complex per-particle values.

    Voronoi neighbours from a Delaunay triangulation over the folded positions
    and their periodic images. scipy is in the sim environment; nothing else is
    imported.
    """
    from scipy.spatial import Delaunay

    pos = fold(np.asarray(positions, dtype=float)[:, :2], box[:2])
    n = len(pos)
    shifts = np.array([(i, j) for i in (-1, 0, 1) for j in (-1, 0, 1)], dtype=float) * box[:2]
    tiled = np.concatenate([pos + s for s in shifts])            # image 4 (0,0) is the centre copy
    centre_offset = 4 * n
    tri = Delaunay(tiled)
    # neighbour sets of the centre copy's particles, by original index
    neigh = [set() for _ in range(n)]
    for simplex in tri.simplices:
        for a in simplex:
            if centre_offset <= a < centre_offset + n:
                j = a - centre_offset
                for b in simplex:
                    if b != a:
                        neigh[j].add(int(b))
    values = np.zeros(n, dtype=complex)
    for j in range(n):
        if not neigh[j]:
            continue
        d = tiled[list(neigh[j])] - tiled[centre_offset + j]
        theta = np.arctan2(d[:, 1], d[:, 0])
        values[j] = np.exp(6j * theta).mean()
    return np.abs(values), values


def psi6_curve(frames: list[np.ndarray], box: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(mean |psi6_j| per frame, |mean psi6_j| per frame)."""
    local, glob = [], []
    for f in frames:
        mags, vals = psi6_per_particle(f, box)
        local.append(float(mags.mean()))
        glob.append(float(abs(vals.mean())))
    return np.asarray(local), np.asarray(glob)


def relaxation_time(times: np.ndarray, psi6: np.ndarray, fit_window: float, plateau_fraction: float) -> dict:
    """The declared reading rule, applied; returns the reading and its parts.

    plateau  = mean of psi6 over the last `fit_window` seconds of the record
    threshold = plateau_fraction * plateau
    tau      = first time psi6 reaches threshold, linearly interpolated
               between the two frames that bracket it

    `converged` is False when the crossing happens inside the plateau window
    (then the plateau was not yet a plateau) or never; the reading is then a
    lower bound and says so.
    """
    times = np.asarray(times, dtype=float); psi6 = np.asarray(psi6, dtype=float)
    if len(times) < 2:
        return {"relaxation_time_si": None, "converged": False, "reason": "fewer than two frames; no curve to read"}
    t_end = times[-1]
    in_window = times >= t_end - fit_window
    if in_window.sum() < 2:
        return {"relaxation_time_si": None, "converged": False,
                "reason": f"fewer than two frames inside the {fit_window:g} s fit window at the end of the record"}
    plateau = float(psi6[in_window].mean())
    plateau_sd = float(psi6[in_window].std(ddof=1)) if in_window.sum() > 1 else None
    threshold = plateau_fraction * plateau
    above = np.nonzero(psi6 >= threshold)[0]
    if len(above) == 0:
        return {"relaxation_time_si": None, "converged": False, "plateau": plateau, "plateau_sd": plateau_sd,
                "threshold": threshold, "reason": "psi6 never reached the threshold; the record is shorter than the relaxation"}
    k = int(above[0])
    if k == 0:
        tau = float(times[0])
    else:
        t0, t1, p0, p1 = times[k - 1], times[k], psi6[k - 1], psi6[k]
        tau = float(t0 + (threshold - p0) / (p1 - p0) * (t1 - t0)) if p1 != p0 else float(t1)
    converged = tau < t_end - fit_window
    return {"relaxation_time_si": tau, "converged": bool(converged), "plateau": plateau, "plateau_sd": plateau_sd,
            "threshold": threshold, "plateau_window_start_si": float(t_end - fit_window),
            "reason": None if converged else "the crossing lies inside the plateau window, so the plateau was still rising; the time is a lower bound"}
