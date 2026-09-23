"""The person's model as written, 2026-09-23:

    U1 = 1/2 kt (dr - a1)^2        U2 = 1/2 a kt (dr - a2)^2

with the stiffness ratio `a` swept from 1 to 100. Prototype, like
`proto_double_well`: no configuration declares it, S3.0 cannot select it, and
nothing here writes a card or carries an evidence grade.

TWO WELLS HAVE TO BE COMBINED AND THE RULE IS NOT IN THE FORMULAE.

`U = U1 + U2` is what two optical tweezers physically make, because intensities
add and so do the gradient forces. It has no barrier. The sum of two parabolas
is a parabola: the curvature is kt(1+a) EVERYWHERE, the separation cancels out
of it entirely, and there is exactly one minimum at

    x* = (a1 + a*a2)/(1 + a)

for every stiffness ratio and every separation. Checked numerically over nine
combinations spanning separations 0.5 to 50 and ratios 1 to 100: one minimum,
zero maxima, every time. So no choice of a2 - a1 rescues it -- not a/2, not
anything.

`U = min(U1, U2)` is a double well, and it is the reading under which the
question has an answer. It is a modelling convention rather than optics: it
says each trap acts alone where it is the stronger one, which is what a
saturating trap approaches when the two barely overlap. Everything below is
closed form.

    crossing     x_c  = (a1 + sqrt(a) a2) / (1 + sqrt(a))
    barrier      dU   = 1/2 kt (a2-a1)^2 * a / (1 + sqrt(a))^2

and the barrier is THE SAME FROM BOTH SIDES, because both parabolas bottom out
at zero, so the two wells are equally deep no matter how their stiffnesses
differ. That is what makes this model the clean experiment: the stiffness ratio
is varied with the depth held fixed by construction, not by tuning.

Inverting the barrier for the separation gives the scaling the question needs:

    a2 - a1 = (1 + 1/sqrt(a)) * sqrt(2 dU / kt)

which DECREASES as the ratio grows, by a factor approaching 2 over 1 to 100.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from . import proto_double_well as P


class HarmonicPair:
    """U = min(U1, U2): two parabolas, the lower one wins, cusp at the crossing."""

    def __init__(self, kt: float, ratio: float, a1: float, a2: float):
        self.kt, self.ratio, self.a1, self.a2 = kt, ratio, a1, a2
        self.k1, self.k2 = kt, ratio*kt
        s = np.sqrt(ratio)
        self.xc = (a1 + s*a2)/(1.0 + s)
        self.barrier = 0.5*kt*(a2 - a1)**2 * ratio/(1.0 + s)**2
        # The parabolas confine on their own, so there is no escape to infinity
        # and no depth to trade against the barrier -- unlike a saturating trap.
        self.L = max(abs(a1), abs(a2)) + np.sqrt(2*45.0/kt)

    def U(self, x):
        return np.minimum(0.5*self.kt*(x - self.a1)**2,
                          0.5*self.ratio*self.kt*(x - self.a2)**2)

    def dU(self, x):
        return np.where(x < self.xc, self.kt*(x - self.a1),
                        self.ratio*self.kt*(x - self.a2))

    def ddU(self, x, h=1e-5):
        return np.where(x < self.xc, self.kt, self.ratio*self.kt)

    def wells(self):
        return self.a1, self.xc, self.a2

    def barriers(self):
        return (self.U(self.xc) - self.U(self.a1),
                self.U(self.xc) - self.U(self.a2),
                -self.U(self.a1), -self.U(self.a2))


def separation_for_barrier(kt, ratio, barrier):
    """The inverse of the barrier formula. Exact, no search."""
    return (1.0 + 1.0/np.sqrt(ratio))*np.sqrt(2.0*barrier/kt)


KT = 30.0
BARRIER = 4.0
RATIOS = [1, 2, 3, 5, 10, 20, 50, 100]

# THE SEPARATION IS HELD FIXED ACROSS THE WHOLE SWEEP, which is the person's
# instruction of 2026-09-23 and is also the only way the sweep isolates the
# stiffness. It works here and would not work in a saturating trap, because of
# one bounded factor: the barrier is
#
#     dU = 1/2 kt d^2 * a/(1 + sqrt(a))^2
#
# and a/(1+sqrt(a))^2 climbs from 0.25 at a=1 only to 1 as a goes to infinity.
# So ONE separation covers every stiffness ratio: the barrier rises by 3.31x
# over 1 to 100 and by at most 4x ever. The saturating counterpart at a fixed
# separation runs 4 kT to 27 kT over the same range, an exponential in which
# nothing hops at the top.
#
# d is chosen so the barrier starts at 2 kT, which leaves 6.6 kT at a=100 --
# both ends crossable in a run, which is what makes every row comparable.
FIXED_SEPARATION = 0.7303        # barrier 2.00 kT at a=1, 6.61 kT at a=100


def sum_model_has_no_barrier():
    """The claim in the docstring, counted rather than asserted."""
    out = []
    for ratio in (1.0, 10.0, 100.0):
        for d in (0.5, 2.0, 50.0):
            xs = np.linspace(-3*d - 5, 3*d + 5, 200001)
            U = 0.5*KT*xs**2 + 0.5*ratio*KT*(xs - d)**2
            turn = np.diff(np.sign(np.diff(U)))
            out.append(dict(ratio=ratio, separation=d,
                            minima=int((turn > 0).sum()),
                            maxima=int((turn < 0).sum()),
                            curvature_everywhere=KT*(1 + ratio)))
    return out


def crossings_wanted(ratio):
    """Fewer crossings where a crossing is dear, and say so rather than hiding
    it: the timestep falls as 1/a while the dwell in the soft well grows, so
    a=100 costs 1500 times what a=1 costs per crossing. 1500 crossings is a
    2.6 per cent standard error, which is inside explore's tie band."""
    return int(min(6000, max(1500, 60000/ratio)))


def run(out_dir, walkers=1024, seed0=20260923):
    res = dict(generated="2026-09-23", seat="simulation-7",
               model="U = min(U1, U2), U1 = 0.5 kt (x-a1)^2, U2 = 0.5 a kt (x-a2)^2",
               kt_in_kT_per_length_squared=KT, barrier_held_at_kT=BARRIER,
               not_a_card="no configuration declares this model (4.2, 5.3)",
               sum_model=sum_model_has_no_barrier(),
               proposed_separation_a_over_2=[], rows=[])

    for a in RATIOS:
        m = HarmonicPair(KT, a, 0.0, a/2.0)
        res["proposed_separation_a_over_2"].append(
            dict(ratio=a, separation=a/2.0, barrier_kT=float(m.barrier)))

    res["fixed_separation"] = FIXED_SEPARATION
    res["barrier_factor"] = [dict(ratio=a, factor=float(a/(1+np.sqrt(a))**2))
                             for a in (1, 2, 5, 10, 20, 50, 100, 1000)]
    for a in RATIOS:
        d = FIXED_SEPARATION
        target_crossings = crossings_wanted(a)
        m = HarmonicPair(KT, a, 0.0, d)
        lT = P.log_mfpt(m, n=800001)
        lp = P.log_occupancy(m, n=800001)
        t1x, t2x = float(np.exp(lT[0])), float(np.exp(lT[1]))
        p1x = float(np.exp(lp[0]))
        # Timestep off the stiffest curvature present, which for a cusp barrier
        # is the stiffer parabola and not the barrier: the cusp has no finite
        # second derivative to bound anything with.
        dt = 1.0/(max(m.k1, m.k2)*200)
        t_sim = target_crossings*(t1x + t2x)/walkers
        n_steps = int(t_sim/dt)
        t0 = time.time()
        r = P.bd(m, dt, n_steps, walkers, seed0 + int(a), x0=0.0,
                 burn_in=int(3*(t1x + t2x)/dt))
        row = dict(
            ratio=a, separation=float(d), barrier_kT=float(m.barrier),
            dt=dt, walkers=walkers, t_sim=float(t_sim), n_steps=n_steps,
            target_crossings=target_crossings,
            crossings_1to2=float(r["n_exit"][0]), crossings_2to1=float(r["n_exit"][1]),
            bd_residence_1=float(r["tau"][0]), bd_residence_2=float(r["tau"][1]),
            bd_naive_residence_1=float(r["res1"].mean()) if r["res1"].size else None,
            bd_occupancy_1=float(r["p_occ"][0]), bd_occupancy_2=float(r["p_occ"][1]),
            bd_rate_1to2=float(1.0/r["tau"][0]), bd_rate_2to1=float(1.0/r["tau"][1]),
            bd_dwell_cv_1=float(r["res1"].std()/r["res1"].mean()) if r["res1"].size else None,
            bd_dwell_cv_2=float(r["res2"].std()/r["res2"].mean()) if r["res2"].size else None,
            exact_residence_1=t1x, exact_residence_2=t2x,
            exact_occupancy_1=p1x, exact_occupancy_2=1.0 - p1x,
            boltzmann_ratio_p1_over_p2=p1x/(1.0 - p1x), sqrt_ratio=float(np.sqrt(a)),
            # The two definitions of occupancy the vocabulary entry separates.
            # Boltzmann weighs the basin; milestoning weighs the record. The
            # simulation measures the second by construction.
            exact_milestoning_occupancy_1=t1x/(t1x + t2x),
            bd_over_exact_1=float(r["tau"][0]/t1x), bd_over_exact_2=float(r["tau"][1]/t2x),
            detailed_balance_bd=float((r["tau"][0]/r["tau"][1])),
            seconds=time.time() - t0)
        res["rows"].append(row)
        print(f"  a={a:<4} d={d:.5f} dt={dt:.2e} steps={n_steps:>9} "
              f"cross={int(r['n_exit'][0])}/{int(r['n_exit'][1])} "
              f"tau={r['tau'][0]:.4f}/{r['tau'][1]:.4f} exact={t1x:.4f}/{t2x:.4f} "
              f"p1={r['p_occ'][0]:.4f} exact={p1x:.4f} [{time.time()-t0:.0f}s]", flush=True)

    (out_dir / "harmonic_pair_results.json").write_text(json.dumps(res, indent=1, default=float))
    print("wrote", out_dir / "harmonic_pair_results.json")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out_dir = Path(sys.argv[1]).expanduser().resolve()
    if "_agent/runs/" in out_dir.as_posix():
        print("refusing: runs/ is for operator runs standing on a plan, and "
              "this stands on none -- see proto_double_well_study")
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    run(out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
