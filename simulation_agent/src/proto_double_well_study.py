"""Driver for the 2026-09-23 double-well question.

Not a plan and not an operator run: no configuration declares this model, so
there is no plan card to preflight against, nothing here is approved, and it
produces a results file and no cards.

**THE OUTPUT DIRECTORY IS AN ARGUMENT AND HAS NO DEFAULT, ON PURPOSE.**
The obvious place, `simulation_agent/runs/<id>/`, is wrong and the validator
says so within one run: check 15 treats every directory under `runs/` as an
operator run standing on a plan, and fails one holding neither `config.json`
nor `log.json`. Satisfying it would mean writing a log naming a `plan_id` that
does not exist, which is forging a run record to quiet a check that is right.
The other two places section 7 allows this agent to write -- `questions/<qid>/`
and `envelope/` -- are the card path and the budget, and this is neither.

So a prototype with no declared configuration has no home in the repository's
data tree, and that is the boundary working rather than a gap in it. Pass a
path outside the tree until `contracts/capabilities/simulation.json` declares
the model; after that this becomes a real run and the run directory is right.

    python -m simulation_agent.src.proto_double_well_study /path/to/outdir
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from . import proto_double_well as P

EPS = 30.0                      # reduced trap depth of the reference trap
TARGET_BARRIER = 4.0            # k_B T out of well 1 -- the observability band
RS = [1, 2, 3, 5, 10, 20, 50, 100]
BD_RS = [1, 2, 3, 5, 10]        # beyond this the return leg is not simulable

FAMILIES = {
    "A_depth_follows_stiffness": dict(
        gloss="one beam waist, the stiffer trap is the more powerful one, so "
              "depth and stiffness rise together: eps2 = R*eps1, w2 = w1",
        make=lambda R, d: P.DoubleWell(EPS, R*EPS, d)),
    "B_depth_held_fixed": dict(
        gloss="equal power into a tighter focus, so the stiffer trap is the "
              "narrower one at the same depth: eps2 = eps1, w2 = w1/sqrt(R)",
        make=lambda R, d: P.DoubleWell(EPS, EPS, d, 1.0, 1.0/np.sqrt(R))),
}


def symmetric_scan():
    rows = []
    for s in [2.0, 2.05, 2.1, 2.2, 2.3, 2.5, 2.75, 3.0, 3.5, 4.0, 5.0]:
        o = P.DoubleWell(1.0, 1.0, s)
        b = o.barriers()
        rows.append(dict(separation_over_sigma=s,
                         double_well=b is not None,
                         barrier_per_eps=None if b is None else b[0],
                         depth_per_eps=None if b is None else b[2],
                         barrier_over_depth=None if b is None else b[0]/b[2]))
    return rows


def merge_ratio(make, d, hi=1e7):
    """Stiffness ratio at which the shallow well is swallowed, at fixed d."""
    lo = 1.0
    for _ in range(80):
        m = np.sqrt(lo*hi)
        if make(m, d).wells() is None:
            hi = m
        else:
            lo = m
    return lo


def sweep(name, fam):
    rows = []
    for R in RS:
        d = P.solve_separation(lambda dd: fam["make"](R, dd), TARGET_BARRIER)
        o = fam["make"](R, d)
        w = o.wells()
        if w is None:
            rows.append(dict(ratio=R, separation_over_sigma=d, double_well=False))
            continue
        b = o.barriers()
        lT = P.log_mfpt(o)
        lp = P.log_occupancy(o)
        rows.append(dict(
            ratio=R, separation_over_sigma=d, double_well=True,
            x_min1=w[0], x_barrier=w[1], x_min2=w[2],
            barrier_1to2_kT=b[0], barrier_2to1_kT=b[1],
            depth_1_kT=b[2], depth_2_kT=b[3],
            curvature_min1=float(abs(o.ddU(w[0]))),
            curvature_barrier=float(abs(o.ddU(w[1]))),
            curvature_min2=float(abs(o.ddU(w[2]))),
            log10_residence_1=lT[0]/np.log(10), log10_residence_2=lT[1]/np.log(10),
            log10_rate_1to2=-lT[0]/np.log(10), log10_rate_2to1=-lT[1]/np.log(10),
            log10_occupancy_1=lp[0]/np.log(10), log10_occupancy_2=lp[1]/np.log(10),
            log10_occupancy_ratio_2_over_1=(lp[1]-lp[0])/np.log(10)))
    return rows


def bd_points(name, fam, walkers=3000, seed0=20260923):
    out = []
    for R in BD_RS:
        d = P.solve_separation(lambda dd: fam["make"](R, dd), TARGET_BARRIER)
        o = fam["make"](R, d)
        dt = P.suggest_dt(o)
        t0 = time.time()
        fp = P.first_passage(o, dt, walkers, seed=seed0 + R)
        exact = float(np.exp(P.log_mfpt(o)[0]))
        out.append(dict(ratio=R, separation_over_sigma=d, dt=dt, walkers=walkers,
                        bd_residence_1=fp["mean"], bd_sem=fp["sem"],
                        n_absorbed=fp["n"], n_censored=fp["n_censored"],
                        exact_residence_1=exact,
                        bd_over_exact=fp["mean"]/exact, seconds=time.time()-t0))
        print(f"  {name} R={R:<4} d={d:.4f} dt={dt:.2e} "
              f"BD={fp['mean']:.4f}+-{fp['sem']:.4f} exact={exact:.4f} "
              f"ratio={fp['mean']/exact:.4f} [{time.time()-t0:.0f}s]", flush=True)
    return out


def symmetric_equilibrium(t_sim=3000.0, walkers=96, seed=20260923):
    """The one point where both legs and the occupancy are measurable."""
    d = P.solve_separation(lambda dd: P.DoubleWell(EPS, EPS, dd), TARGET_BARRIER)
    o = P.DoubleWell(EPS, EPS, d)
    dt = P.suggest_dt(o)
    t0 = time.time()
    r = P.bd(o, dt, int(t_sim/dt), walkers, seed)
    lT = P.log_mfpt(o)
    lp = P.log_occupancy(o)
    cv = float(r["res1"].std()/r["res1"].mean())
    return dict(separation_over_sigma=d, dt=dt, walkers=walkers, t_sim=t_sim,
                exits=r["n_exit"].tolist(),
                renewal_residence_1=r["tau"][0], renewal_residence_2=r["tau"][1],
                naive_mean_residence_1=float(r["res1"].mean()),
                naive_mean_residence_2=float(r["res2"].mean()),
                bd_occupancy_1=r["p_occ"][0],
                exact_residence_1=float(np.exp(lT[0])),
                exact_residence_2=float(np.exp(lT[1])),
                exact_occupancy_1=float(np.exp(lp[0])),
                dwell_coefficient_of_variation=cv,
                seconds=time.time()-t0)


def free_diffusion_check():
    """The quadrature against the one case with a closed form."""
    a, b, x0 = -3.0, 1.0, -1.0
    exact = ((b - a)**2 - (x0 - a)**2)/2.0
    n = 600001
    x = np.linspace(a, b, n)
    dx = x[1] - x[0]
    lG = np.logaddexp.accumulate(np.full(n, np.log(dx)))
    sel = (x >= x0) & (x <= b)
    got = float(np.exp(P._lse(lG[sel] + np.log(dx))))
    return dict(analytic=exact, quadrature=got, ratio=got/exact)


def physical(temperature=293.0, viscosity=1.0e-3):
    rows = []
    for diameter, w1 in ((5.0e-6, 1.5e-6), (1.0e-6, 0.5e-6)):
        s = P.to_physical(temperature, viscosity, diameter, w1)
        d = P.solve_separation(lambda dd: P.DoubleWell(EPS, EPS, dd), TARGET_BARRIER)
        rows.append(dict(
            bead_diameter_um=diameter*1e6, trap_width_um=w1*1e6,
            drag_kg_per_s=s["gamma"], diffusivity_m2_per_s=s["D"],
            time_unit_s=s["tau"], separation_um=d*w1*1e6,
            stiffness_1_N_per_m=EPS*s["stiffness"],
            stiffness_1_pN_per_um=EPS*s["stiffness"]*1e6,
            trap_depth_kT=EPS,
            residence_symmetric_s=float(np.exp(P.log_mfpt(
                P.DoubleWell(EPS, EPS, d))[0]))*s["tau"],
            trap_relaxation_ms=s["tau"]/EPS*1e3))
    return rows


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out_dir = Path(sys.argv[1]).expanduser().resolve()
    if "_agent/runs/" in out_dir.as_posix():
        print("refusing: see this module's docstring -- runs/ is for operator "
              "runs standing on a plan, and this stands on none")
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    res = dict(
        generated="2026-09-23", seat="simulation-7",
        question="two optical traps, one particle, thermally activated hopping; "
                 "stiffness ratio 1 to 100",
        not_a_card="No configuration declares this model, so nothing here is a "
                   "graded number and nothing here is a plan (4.2, 5.3).",
        reduced_units="length w1, energy kT, time w1^2/D",
        reference_depth_kT=EPS, target_barrier_kT=TARGET_BARRIER,
        splitting_threshold=dict(
            separation_over_sigma=2.0,
            statement="Two wells exist if and only if the separation exceeds "
                      "twice the trap width, for equal traps. U''(0) changes "
                      "sign there exactly."),
        free_diffusion_check=free_diffusion_check(),
        symmetric_scan=symmetric_scan(),
        merge_ratio_at_fixed_separation={
            str(d): merge_ratio(FAMILIES["A_depth_follows_stiffness"]["make"], d)
            for d in (2.2, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)},
        families={}, physical_instantiation=physical())
    res["symmetric_equilibrium_bd"] = symmetric_equilibrium()
    print("symmetric equilibrium done", flush=True)
    for name, fam in FAMILIES.items():
        print("sweep", name, flush=True)
        res["families"][name] = dict(gloss=fam["gloss"], exact=sweep(name, fam),
                                     bd=bd_points(name, fam))
    (out_dir / "results.json").write_text(json.dumps(res, indent=1, default=float))
    print("wrote", out_dir / "results.json")


if __name__ == "__main__":
    sys.exit(main())
