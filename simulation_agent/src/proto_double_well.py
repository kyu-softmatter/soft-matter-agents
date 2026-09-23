"""Two optical traps, one particle, overdamped -- the double-well prototype.

**THIS IS NOT A DECLARED CONFIGURATION AND CANNOT BECOME ONE FROM HERE.**
`contracts/capabilities/simulation.json` declares exactly one configuration,
`bd_overdamped`, and it produces `tracer_diffusivity` only. S3.0 screens against
that table, so nothing in this file can be selected by a plan; the model is a
human decision and declaring one is a write to `contracts/` this session cannot
make (4.2, 6.2). What this file is: the arithmetic and the integrator for the
question the person asked on 2026-09-23, written so that the day the
configuration is declared the run is one command rather than a week.

Nothing here writes a card. A number produced by this module is the prototype's
and carries no evidence grade -- 5.3 has no source kind for a simulated
observable, which is the architecture seat's open question, and inventing one
here would be the E6 the grade exists to keep out.

THE MODEL
---------
The question specifies `U_i = 0.5 * k_i * dr_i^2` for each trap and asks where
to put them so the particle hops. Taken globally that has no answer: the sum of
two parabolas is one parabola, with one minimum and no barrier, at every
separation and every stiffness. The word carrying the physics is *locally* --
a real trap is harmonic near its focus and decays to zero beyond the beam, and
it is that decay, not the curvature, that makes a barrier. So each trap is a
localized well whose curvature at the bottom is the stated stiffness:

    U(x) = -eps_1 * exp(-(x+d/2)^2 / (2 w_1^2))
           -eps_2 * exp(-(x-d/2)^2 / (2 w_2^2))

    expanding about the bottom of trap i:  U ~ -eps_i + 0.5*(eps_i/w_i^2)*dr^2
    so                                     k_i = eps_i / w_i^2       exactly.

Reduced units throughout: length w_1, energy k_B*T, time w_1^2/D. Hence D = 1,
gamma = 1, beta = 1. Physical units are restored by `to_physical`, which is
where D7 is honoured -- the conversion is the boundary's first responsibility.

ONE DIMENSION. Hopping is along the line joining the traps and this module
integrates that coordinate only. The transverse directions are not separable
from it for a sum of Gaussians, so this is an approximation and not a
reduction; what it costs has not been measured here.
"""

from __future__ import annotations

import numpy as np

from . import physics


class DoubleWell:
    """A static two-trap potential in one dimension, in reduced units."""

    def __init__(self, eps1: float, eps2: float, d: float,
                 w1: float = 1.0, w2: float = 1.0):
        self.eps1, self.eps2, self.d, self.w1, self.w2 = eps1, eps2, d, w1, w2
        self.k1, self.k2 = eps1 / w1**2, eps2 / w2**2
        # Far enough out that the wall is never reached: the barrier to it is
        # the full trap depth, tens of k_B T, and e^-30 is not a rate.
        self.L = d / 2 + 6.0 * max(w1, w2)

    def U(self, x):
        return -(self.eps1 * np.exp(-(x + self.d/2)**2 / (2*self.w1**2))
               + self.eps2 * np.exp(-(x - self.d/2)**2 / (2*self.w2**2)))

    def dU(self, x):
        return (self.eps1 * (x + self.d/2)/self.w1**2 * np.exp(-(x + self.d/2)**2/(2*self.w1**2))
              + self.eps2 * (x - self.d/2)/self.w2**2 * np.exp(-(x - self.d/2)**2/(2*self.w2**2)))

    def ddU(self, x, h=1e-5):
        return (self.U(x + h) - 2*self.U(x) + self.U(x - h)) / h**2

    def stationary(self, n=800001):
        """Every root of U', by sign change then bisection.

        The grid is offset by 1e-9 on purpose. A symmetric configuration puts
        an exact zero of U' at x=0, and a sign-change test never fires on an
        exact zero -- which silently reported "single well" for half the
        separations in the first run of this code.
        """
        xs = np.linspace(-self.L, self.L, n) + 1e-9
        f = self.dU(xs)
        out = []
        for i in np.nonzero(f[:-1] * f[1:] < 0)[0]:
            a, b, fa = xs[i], xs[i+1], f[i]
            for _ in range(80):
                m = 0.5*(a + b)
                fm = self.dU(m)
                if fa*fm <= 0:
                    b = m
                else:
                    a, fa = m, fm
            out.append(0.5*(a + b))
        return np.array(out)

    def wells(self):
        """(x_min1, x_barrier, x_min2), or None when the wells have merged."""
        r = self.stationary()
        mins = [x for x in r if self.ddU(x) > 0]
        maxs = [x for x in r if self.ddU(x) < 0]
        if len(mins) == 2 and len(maxs) == 1 and mins[0] < maxs[0] < mins[1]:
            return mins[0], maxs[0], mins[1]
        return None

    def barriers(self):
        """(dU_1to2, dU_2to1, depth_1, depth_2) in k_B T, or None."""
        w = self.wells()
        if w is None:
            return None
        x1, xb, x2 = w
        return (self.U(xb) - self.U(x1), self.U(xb) - self.U(x2),
                -self.U(x1), -self.U(x2))


# ----------------------------------------------------------------- exact ----
# Both of these are exact for one-dimensional overdamped dynamics. They are not
# Kramers approximations and carry no high-barrier assumption. They are also
# the reason a run of this configuration would have to declare
# output_independent_of_input: false in 1D -- a quadrature already knows the
# answer. In three dimensions there is no such closed form and the run would
# carry information the inputs do not.

def _grid(dw, n=600001):
    x = np.linspace(-dw.L, dw.L, n)
    return x, x[1] - x[0]


def _lse(a):
    if a.size == 0:
        return -np.inf
    m = a.max()
    return m + np.log(np.exp(a - m).sum())


def log_occupancy(dw, n=600001):
    """(log p1, log p2): Boltzmann basin weight, split at the barrier.

    Logs, not probabilities. At a stiffness ratio of 100 with depth coupled to
    stiffness this ratio reaches 1e1288, which is not a float.
    """
    x, dx = _grid(dw, n)
    w = dw.wells()
    if w is None:
        return None
    lw = -dw.U(x) + np.log(dx)
    left = x <= w[1]
    l1, l2 = _lse(lw[left]), _lse(lw[~left])
    tot = np.logaddexp(l1, l2)
    return float(l1 - tot), float(l2 - tot)


def log_mfpt(dw, n=600001):
    """(log T_1to2, log T_2to1): mean first passage between the two minima.

        T(a->b) = (1/D) int_a^b dy e^{U(y)} int_reflecting^y dz e^{-U(z)}

    Evaluated in log space with a cumulative logaddexp. The direct form
    overflows: e^{-U} at the bottom of the stiff well passes 1e308 by a
    stiffness ratio of about 25, and the two halves of the product overflow and
    underflow separately while the product itself is perfectly finite.

    Checked against free diffusion between a reflecting and an absorbing wall,
    where the answer is ((b-a)^2 - (x0-a)^2)/2D: agreement to 6 parts per
    million. Checked against Brownian dynamics in the symmetric double well
    below: 1 per cent.
    """
    x, dx = _grid(dw, n)
    w = dw.wells()
    if w is None:
        return None
    x1, xb, x2 = w
    Ux = dw.U(x)
    logw = -Ux + np.log(dx)
    sel = (x >= x1) & (x <= x2)
    lG = np.logaddexp.accumulate(logw)                 # log int_{-L}^{y}
    lGr = np.logaddexp.accumulate(logw[::-1])[::-1]    # log int_{y}^{+L}
    return (float(_lse(Ux[sel] + lG[sel] + np.log(dx))),
            float(_lse(Ux[sel] + lGr[sel] + np.log(dx))))


def solve_separation(make, target_barrier, lo=0.2, hi=14.0, key=0, iters=90):
    """Smallest separation whose barrier out of well `key` is `target_barrier`.

    `make(d)` returns a DoubleWell. The barrier grows monotonically with
    separation, from zero at the merge to the full trap depth, so bisection is
    safe and "no double well yet" sorts to the same side as "barrier too low".
    """
    for _ in range(iters):
        m = 0.5*(lo + hi)
        b = make(m).barriers()
        if b is None or b[key] - target_barrier < 0:
            lo = m
        else:
            hi = m
    return 0.5*(lo + hi)


# ------------------------------------------------------------ dynamics ------

def bd(dw, dt, n_steps, n_walkers, seed, x0=None, burn_in=0):
    """Euler-Maruyama in reduced units, with milestoning states.

    dx = -U'(x) dt + sqrt(2 dt) * N(0,1)

    The state is the minimum most recently touched: it becomes 2 on reaching
    x2 and 1 on reaching x1, and the barrier belongs to neither. Nearest-minimum
    assignment would flicker every timestep a walker sits near the saddle and
    would count each flicker as a transition.

    Time is `(i+1)*dt` off an integer step count and never a running sum of dt.
    Ten thousand additions of 0.002 land at 19.999999999999794, and a
    comparison at a boundary is a decision rather than a measurement.
    """
    w = dw.wells()
    if w is None:
        raise ValueError("no double well: nothing to be in or out of")
    x1, xb, x2 = w
    rng = np.random.default_rng(seed)
    x = np.full(n_walkers, x1 if x0 is None else x0, dtype=float)
    state = np.where(x >= x2, 2, 1)
    last_t = np.zeros(n_walkers)
    res1, res2 = [], []
    occ = np.zeros(2)
    n_exit = np.zeros(2)
    amp = np.sqrt(2.0*dt)
    # Every walker starts at the same minimum, so the first dwell is a first
    # passage from a prepared state and the occupancy of the other well is zero
    # until one arrives. Burn-in runs the dynamics without accumulating, then
    # the state and the clock are reset to whatever the walkers had reached.
    for i in range(burn_in):
        x += -dw.dU(x)*dt + amp*rng.standard_normal(n_walkers)
        np.clip(x, -dw.L, dw.L, out=x)
        state = np.where(x >= x2, 2, np.where(x <= x1, 1, state))
    for i in range(n_steps):
        x += -dw.dU(x)*dt + amp*rng.standard_normal(n_walkers)
        np.clip(x, -dw.L, dw.L, out=x)
        t = (i + 1)*dt
        occ[0] += dt*np.count_nonzero(state == 1)
        occ[1] += dt*np.count_nonzero(state == 2)
        hit2 = (x >= x2) & (state == 1)
        if hit2.any():
            res1.extend((t - last_t[hit2]).tolist())
            last_t[hit2] = t
            state[hit2] = 2
            n_exit[0] += hit2.sum()
        hit1 = (x <= x1) & (state == 2)
        if hit1.any():
            res2.extend((t - last_t[hit1]).tolist())
            last_t[hit1] = t
            state[hit1] = 1
            n_exit[1] += hit1.sum()
    # THE ESTIMATOR IS PART OF THE IDENTITY, and these two differ by more than
    # the error bar. The mean of completed dwells is biased LOW by roughly
    # mu/T_record, because the longest dwell in a record is the one most likely
    # to straddle its end and be thrown away: measured 5.7 per cent low over a
    # 600-tau record where the renewal form was 1 per cent. Total time in the
    # state over exits from it keeps the censored tail in the numerator.
    tau = np.where(n_exit > 0, occ/np.maximum(n_exit, 1), np.nan)
    return dict(res1=np.array(res1), res2=np.array(res2),
                occ=occ, n_exit=n_exit, tau=tau, p_occ=occ/occ.sum(),
                t_total=n_steps*dt, x_end=x, state=state)


def first_passage(dw, dt, n_walkers, seed, max_steps=40_000_000, chunk=20000):
    """Mean first passage x1 -> x2 from an absorbed ensemble.

    Cheaper than waiting for round trips whenever the return is slow, which is
    the whole asymmetric half of this question: at a stiffness ratio of 100 the
    forward hop takes 4 reduced times and the return takes 1e8 of them.
    """
    w = dw.wells()
    x1, xb, x2 = w
    rng = np.random.default_rng(seed)
    x = np.full(n_walkers, x1, dtype=float)
    alive = np.ones(n_walkers, bool)
    t_hit = np.zeros(n_walkers)
    amp = np.sqrt(2.0*dt)
    done = 0
    for i in range(max_steps):
        n = int(alive.sum())
        if n == 0:
            break
        x[alive] += -dw.dU(x[alive])*dt + amp*rng.standard_normal(n)
        np.clip(x, -dw.L, dw.L, out=x)
        hit = alive & (x >= x2)
        if hit.any():
            t_hit[hit] = (i + 1)*dt
            alive[hit] = False
        if i % chunk == 0 and i and not alive.any():
            break
    done = ~alive
    return dict(mean=float(t_hit[done].mean()) if done.any() else np.nan,
                sem=float(t_hit[done].std()/np.sqrt(max(done.sum(), 1))),
                n=int(done.sum()), n_censored=int(alive.sum()))


def matched_depth_pair(eps1, ratio, target_barrier, w1=1.0, iters=45):
    """Two wells of EQUAL DEPTH whose stiffnesses differ by `ratio`.

    This is the only one of the three families in which the question "what does
    stiffness asymmetry alone do" has an answer, because it is the only one that
    holds everything else. Depth and stiffness are not independent in one trap:
    k = eps/w^2, so a stiffness ratio has to be paid for in depth, in width, or
    in both. Raising the power pays in depth and the shallower well stops
    existing by a ratio near 1.6; narrowing the waist pays in width and the
    overlap tilts the pair anyway. Here the second trap's depth AND width both
    move, chosen so that the two TOTAL depths come out equal.

    Returned wells have equal depth and, as a consequence rather than a
    constraint, equal barriers. What is left over is the curvature, which is
    what the question was about.

    Solved as two nested bisections: the inner one puts the barrier at
    `target_barrier`, the outer one drives the depth difference to zero. The
    hand-rolled bisection in `solve_separation` was checked against
    scipy.optimize.brentq on this landscape and the two agreed to every digit
    printed, so neither is standing in for the other.
    """
    def build(w2):
        return lambda d: DoubleWell(eps1, ratio*eps1*w2**2, d, w1, w2)

    def tilt_of(w2):
        make = build(w2)
        d = solve_separation(make, target_barrier)
        b = make(d).barriers()
        return (None if b is None else b[3] - b[2]), d

    lo, hi = 0.03*w1, 1.6*w1/np.sqrt(ratio)
    for _ in range(iters):
        m = 0.5*(lo + hi)
        t, _ = tilt_of(m)
        if t is None or t < 0:
            lo = m
        else:
            hi = m
    w2 = 0.5*(lo + hi)
    _, d = tilt_of(w2)
    return build(w2)(d)


def suggest_dt(dw, per_relaxation=200):
    """Timestep from the stiffest curvature anywhere on the path (A1).

    The bound is the shortest characteristic time, and in a two-trap landscape
    that is the largest |U''| among the two minima and the saddle -- not the
    softer trap's, and not the barrier's alone.
    """
    w = dw.wells()
    kmax = max(abs(dw.ddU(v)) for v in w)
    return 1.0/(kmax*per_relaxation)


# ------------------------------------------------------------- units --------

def to_physical(temperature, viscosity, diameter, w1):
    """Reduced -> SI. The conversion lives at the boundary, not in the physics.

    Returns the scales: drag, diffusivity, the time unit w1^2/D, the energy
    unit k_B T, and the stiffness that one reduced unit of eps/w^2 means.
    """
    gamma = 3.0*np.pi*viscosity*diameter
    D = physics.stokes_einstein(temperature, viscosity, diameter)
    return dict(gamma=gamma, D=D, tau=w1**2/D,
                energy=physics.K_B*temperature,
                stiffness=physics.K_B*temperature/w1**2, length=w1)
