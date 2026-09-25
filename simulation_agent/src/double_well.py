"""The Gaussian double well in two dimensions: the potential, a NumPy integrator, the estimator.

For `bd_overdamped_gaussian_double_well_2d`. Three things live here and nowhere
else, so the NumPy reference and the HOOMD engine share them:

1. **The potential and what follows from it in closed form** -- the saddle,
   the barrier, the exact Boltzmann basin weight. No simulation is needed for
   any of these, and the map computes them over its whole grid first.

       U(r) = -eps_1 exp(-|r - r_1|^2 / 2 w_1^2) - eps_2 exp(-|r - r_2|^2 / 2 w_2^2)

   with r_1 = (-d/2, 0), r_2 = (+d/2, 0). At the bottom of trap i alone,
   k_i = eps_i / w_i^2 exactly. By symmetry the saddle lies on the joining line.

2. **A NumPy Euler-Maruyama integrator** over an ensemble of independent
   walkers, used as the reference the engine is validated against.

3. **The estimator**, applied to the trajectory PROJECTED ON THE JOINING LINE
   with one milestone definition, so the experiment's projected trajectory goes
   through it unchanged (plan.md 11-23 condition 1). It takes x(t) in any
   length unit and the trap centres in the same unit, and returns occupancy,
   residence times, the transition rate and the projected free-energy barrier.

Reduced units in this module: length w_1, energy k_B*T, time w_1^2/D with D the
free-particle diffusivity. `si_scales` converts; nothing else here knows SI.
"""

from __future__ import annotations

import math

import numpy as np

K_B = 1.380649e-23   # J/K, exact by the SI definition


# ---------------------------------------------------------------------------
# 1. the potential
# ---------------------------------------------------------------------------

class Wells:
    """Two Gaussian wells in reduced units (length w_1, energy kT)."""

    def __init__(self, eps1: float, eps2: float, d: float, w1: float = 1.0, w2: float = 1.0) -> None:
        self.eps1, self.eps2, self.d, self.w1, self.w2 = float(eps1), float(eps2), float(d), float(w1), float(w2)
        self.c1, self.c2 = -self.d / 2.0, self.d / 2.0

    def energy(self, x, y):
        g1 = np.exp(-((x - self.c1) ** 2 + y ** 2) / (2 * self.w1 ** 2))
        g2 = np.exp(-((x - self.c2) ** 2 + y ** 2) / (2 * self.w2 ** 2))
        return -self.eps1 * g1 - self.eps2 * g2

    def force(self, x, y):
        """-grad U, as (fx, fy)."""
        g1 = self.eps1 * np.exp(-((x - self.c1) ** 2 + y ** 2) / (2 * self.w1 ** 2)) / self.w1 ** 2
        g2 = self.eps2 * np.exp(-((x - self.c2) ** 2 + y ** 2) / (2 * self.w2 ** 2)) / self.w2 ** 2
        return -(g1 * (x - self.c1) + g2 * (x - self.c2)), -(g1 + g2) * y

    def line(self, n: int = 20001):
        lo = self.c1 - 6 * self.w1
        hi = self.c2 + 6 * self.w2
        x = np.linspace(lo, hi, n)
        return x, self.energy(x, 0.0)

    def landscape(self) -> dict:
        """Minima and saddle on the joining line, and the barrier from each well.

        Returns `merged: True` when the line carries one minimum only -- then there
        is no barrier and nothing to hop over.
        """
        x, u = self.line()
        du = np.diff(u)
        # a local minimum where the slope turns from negative to positive, a maximum the reverse
        idx_min = [i + 1 for i in range(len(du) - 1) if du[i] < 0 <= du[i + 1]]
        idx_max = [i + 1 for i in range(len(du) - 1) if du[i] > 0 >= du[i + 1]]
        if len(idx_min) < 2 or not idx_max:
            i = int(np.argmin(u))
            return {"merged": True, "x_min": float(x[i]), "u_min": float(u[i])}
        i1, i2 = idx_min[0], idx_min[-1]
        inner = [j for j in idx_max if i1 < j < i2]
        js = inner[int(np.argmax(u[inner]))]
        refine = lambda j: _refine_extremum(self, x[j - 1], x[j + 1])  # noqa: E731
        x1, x2, xs = refine(i1), refine(i2), refine(js)
        u1, u2, us = (float(self.energy(v, 0.0)) for v in (x1, x2, xs))
        return {"merged": False, "x1": x1, "x2": x2, "x_saddle": xs, "u1": u1, "u2": u2, "u_saddle": us,
                "barrier_from_1": us - u1, "barrier_from_2": us - u2,
                "barrier_from_deeper": us - min(u1, u2)}

    def boltzmann_weight_1(self, x_split: float, n: int = 1201) -> float:
        """Exact basin weight of well 1: the fraction of exp(-U) with x < x_split, in 2-D."""
        span = 8 * max(self.w1, self.w2)
        x = np.linspace(self.c1 - span, self.c2 + span, n)
        y = np.linspace(-span, span, n)
        X, Y = np.meshgrid(x, y, indexing="ij")
        U = self.energy(X, Y)
        b = np.exp(-(U - U.min()))
        return float(b[x < x_split].sum() / b.sum())


def separation_for_barrier(eps1: float, eps2: float, barrier: float, w2: float = 1.0) -> float:
    """The d/w_1 at which the barrier from the deeper well equals `barrier` kT.

    The barrier rises with separation from the merge point, so bisection on d
    finds it. Raises when no separation gives it -- which is the normal answer
    for unequal wells hundreds of kT deep, where the shallow well vanishes while
    the barrier from the deeper one is still far above the target.
    """
    def b(d):
        L = Wells(eps1, eps2, d, 1.0, w2).landscape()
        return 0.0 if L["merged"] else L["barrier_from_deeper"]
    lo, hi = 0.5, 12.0 * max(1.0, w2)
    if b(hi) < barrier:
        raise ValueError(f"no separation up to {hi} w_1 gives a {barrier} kT barrier")
    for _ in range(80):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if b(m) < barrier else (lo, m)
    if abs(b(hi) - barrier) > 0.05 * barrier:
        raise ValueError(f"the barrier jumps past {barrier} kT at d = {hi:.6f} w_1 (to {b(hi):.2f} kT): "
                         "the shallower well vanishes before the barrier from the deeper one reaches it")
    return hi


def _refine_extremum(w: Wells, a: float, b: float) -> float:
    """Where dU/dx = 0 on y = 0 between a and b, by bisection on the force."""
    fa = w.force(a, 0.0)[0]
    for _ in range(80):
        m = 0.5 * (a + b)
        fm = w.force(m, 0.0)[0]
        if (fm > 0) == (fa > 0):
            a, fa = m, fm
        else:
            b = m
    return 0.5 * (a + b)


def si_scales(temperature: float, viscosity: float, bead_diameter: float, w1: float) -> dict:
    """The reduced units in SI: length w_1, energy kT, time w_1^2 / D, D = kT / (3 pi eta d)."""
    kT = K_B * temperature
    D = kT / (3 * math.pi * viscosity * bead_diameter)
    return {"length_m": w1, "energy_J": kT, "time_s": w1 ** 2 / D, "D_m2_s": D}


class DiskTracker:
    """Every-step 2-D disk milestoning, kept online: the manager's reference definition.

    Not the comparison's definition -- the experiment applies the projected one at its
    frame interval (`estimate`) -- and kept only to close the question of whether two
    engines agree when both use the same, finer definition.
    """

    def __init__(self, w: Wells, walkers: int, radius: float) -> None:
        self.w, self.r2 = w, radius ** 2
        self.state = np.zeros(walkers, dtype=np.int8)
        self.changes = np.zeros(walkers, dtype=np.int64)
        self.in1 = np.zeros(walkers, dtype=np.int64)
        self.assigned = np.zeros(walkers, dtype=np.int64)

    def update(self, x, y) -> None:
        core = np.where((x - self.w.c1) ** 2 + y ** 2 < self.r2, 1,
                        np.where((x - self.w.c2) ** 2 + y ** 2 < self.r2, 2, 0)).astype(np.int8)
        new = np.where(core == 0, self.state, core)
        self.changes += (self.state > 0) & (new != self.state)
        self.state = new
        self.assigned += new > 0
        self.in1 += new == 1

    def result(self, dt: float) -> dict:
        return {"occupancy_1_per_walker": self.in1 / np.maximum(self.assigned, 1),
                "rate_per_walker": self.changes / np.maximum(self.assigned * dt, dt)}


# ---------------------------------------------------------------------------
# 2. the NumPy reference integrator
# ---------------------------------------------------------------------------

def integrate_numpy(w: Wells, walkers: int, t_total: float, dt: float, save_every: int,
                    burn_in: float, seed: int, start: str = "split",
                    tracker: DiskTracker | None = None) -> np.ndarray:
    """Euler-Maruyama in reduced units (D = gamma = kT = 1). Returns x(t) as (frames, walkers).

    `start='split'` puts half the walkers at each centre, which is the no-burn-in
    reference's start; the burn-in is discarded before the first saved frame.
    """
    rng = np.random.default_rng(seed)
    x = np.where(np.arange(walkers) % 2 == 0, w.c1, w.c2).astype(float)
    y = np.zeros(walkers)
    amp = math.sqrt(2 * dt)
    for _ in range(int(round(burn_in / dt))):
        fx, fy = w.force(x, y)
        x += fx * dt + amp * rng.standard_normal(walkers)
        y += fy * dt + amp * rng.standard_normal(walkers)
    n_steps = int(round(t_total / dt))
    frames = n_steps // save_every + 1
    out = np.empty((frames, walkers))
    out[0] = x
    for s in range(1, n_steps + 1):
        fx, fy = w.force(x, y)
        x += fx * dt + amp * rng.standard_normal(walkers)
        y += fy * dt + amp * rng.standard_normal(walkers)
        if tracker is not None:
            tracker.update(x, y)
        if s % save_every == 0:
            out[s // save_every] = x
    return out


# ---------------------------------------------------------------------------
# 3. the estimator, on the projected trajectory
# ---------------------------------------------------------------------------

def milestone_states(x: np.ndarray, c1: float, c2: float, radius: float) -> np.ndarray:
    """Core-set milestoning on the projection: +1 in well 1's core, 2 in well 2's, and
    otherwise the last core visited. Frames before the first core visit are 0 (unassigned).

    x is (frames,) or (frames, records); c1 < c2 are the projected trap centres.
    """
    x = np.asarray(x, dtype=float)
    core = np.where(np.abs(x - c1) < radius, 1, np.where(np.abs(x - c2) < radius, 2, 0))
    state = core.copy()
    for t in range(1, len(state)):
        state[t] = np.where(core[t] == 0, state[t - 1], core[t])
    return state


def estimate(x: np.ndarray, frame_interval: float, c1: float, c2: float, radius: float,
             bins: int = 120) -> dict:
    """The four estimators for ONE record x(t) (frames,), or per record for (frames, records).

    - occupancy_1: fraction of assigned frames whose milestone state is well 1
    - residence_1, residence_2: mean completed dwell in each state (time units of frame_interval)
    - transitions: count of state changes; rate = transitions / assigned time
      (the hop frequency, both directions counted -- NOT the registered observable)
    - rate_12, rate_21: the registered `interwell_transition_rate`, transitions out of
      the origin well over the time assigned to that well
    - barrier_from_deeper: -ln of the projected histogram, saddle region maximum minus the
      deeper well's minimum -- a FREE-energy barrier on the projection, not the potential's
    """
    x = np.asarray(x, dtype=float)
    single = x.ndim == 1
    if single:
        x = x[:, None]
    st = milestone_states(x, c1, c2, radius)
    res = []
    for r in range(x.shape[1]):
        s = st[:, r]
        s = s[s > 0]
        n = len(s)
        if n < 2:
            res.append(None)
            continue
        change = np.flatnonzero(s[1:] != s[:-1]) + 1
        edges = np.concatenate(([0], change, [n]))
        dw = [(int(s[a]), (b - a) * frame_interval) for a, b in zip(edges[:-1], edges[1:])]
        complete = dw[1:-1]           # the first and last dwell are cut by the record
        r1 = [t for k, t in complete if k == 1]
        r2 = [t for k, t in complete if k == 2]
        T = (n - 1) * frame_interval
        t1 = float(np.sum(s[:-1] == 1)) * frame_interval       # time assigned to each ORIGIN well
        t2 = float(np.sum(s[:-1] == 2)) * frame_interval
        n12 = int(np.sum((s[:-1] == 1) & (s[1:] == 2)))
        n21 = int(np.sum((s[:-1] == 2) & (s[1:] == 1)))
        res.append({
            "occupancy_1": float(np.mean(s == 1)),
            "transitions": int(len(change)),
            # the hop frequency, both directions over the record: what "hops per hour" counts
            "rate": float(len(change) / T) if T > 0 else float("nan"),
            # the registered interwell_transition_rate, per ordered pair, over time in the origin well
            "rate_12": n12 / t1 if t1 > 0 else float("nan"),
            "rate_21": n21 / t2 if t2 > 0 else float("nan"),
            "transitions_12": n12, "transitions_21": n21,
            "residence_1": float(np.mean(r1)) if r1 else float("nan"),
            "residence_2": float(np.mean(r2)) if r2 else float("nan"),
            "barrier_from_deeper": _hist_barrier(x[:, r], c1, c2, bins),
        })
    return res[0] if single else res


def _hist_barrier(x: np.ndarray, c1: float, c2: float, bins: int) -> float:
    h, e = np.histogram(x, bins=bins, range=(c1 - 1.5 * (c2 - c1) / 2, c2 + 1.5 * (c2 - c1) / 2))
    mid = 0.5 * (e[1:] + e[:-1])
    with np.errstate(divide="ignore"):
        f = -np.log(h / h.sum())
    inner = (mid > c1) & (mid < c2)
    if not np.isfinite(f[inner]).all():
        return float("inf")
    wells = min(np.min(f[mid < 0.5 * (c1 + c2)]), np.min(f[mid >= 0.5 * (c1 + c2)]))
    return float(np.max(f[inner]) - wells)
