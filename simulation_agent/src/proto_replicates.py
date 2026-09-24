"""Independent-seed replicates of the fixed-separation stiffness sweep.

Prototype, like `proto_harmonic_pair`: no configuration declares the model, S3.0
cannot select it, nothing here writes a card or carries an evidence grade.

WHY REPLICATES AND NOT ONE LONGER RUN. Every error bar reported before this
module was inferred -- one over the square root of the crossing count, which is
what the error WOULD be if every crossing were independent and every walker's
record were long. Neither is true at the stiff end: at a stiffness ratio of 100
a walker sees one or two soft-well dwells in its record. Replicates with
distinct seeds give the scatter as a measurement instead of an assumption, and
they are the only honest input to the question left open in the report --
whether the simulation's occupancy is the milestoning value or the Boltzmann
basin weight. Those differ by 2 per cent at a ratio of 3, and "suggestive, not
settled" becomes a verdict only when the standard error is measured, not
supposed.

BURN-IN IS FIVE TWO-STATE RELAXATION TIMES, NOT THREE ROUND TRIPS. The earlier
sweep burned in for 3*(tau1 + tau2). The quantity that decides whether the
walkers have forgotten their shared starting point is the relaxation time of
the two-state process, 1/(1/tau1 + 1/tau2), and at a=100 that is 1.94 against
a round trip of 22.9 -- so the old burn-in was 35 relaxation times and cost
twice the sampling it preceded. Five relaxation times leaves e^-5 = 0.7 per
cent of the initial condition, which is inside every error bar below, and it
is a change of protocol that is recorded here and not hidden.

    python -m simulation_agent.src.proto_replicates /path/to/outdir [--smoke | --stage2] [--workers=N]
    python -m simulation_agent.src.proto_replicates /path/to/outdir --aggregate
"""

from __future__ import annotations

import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

from . import proto_double_well as P
from .proto_harmonic_pair import KT, FIXED_SEPARATION, HarmonicPair

WALKERS = 1024
WORKERS = 4          # four performance cores; the machine is shared with other seats

# (ratio, replicates, crossings per replicate). The occupancy window a=2..5 gets
# the most replicates because that is where a verdict is available and cheap.
CAMPAIGN = [
    (1, 16, 6000),
    (2, 32, 6000),
    (3, 32, 6000),
    (5, 32, 6000),
    (10, 16, 6000),
    (20, 12, 3000),
    (50, 8, 1500),
    (100, 8, 1500),
]
SMOKE = [(1, 2, 600), (3, 2, 600), (100, 1, 60)]

# STAGE 2, AND WHY THERE IS ONE. The campaign above was sized from a smoke
# run's own timing at 25 to 40 minutes. It ran four times slower than that:
# 40 minutes in, another seat started an operator run on the declared engine
# (sim-20260923-041, multithreaded HOOMD), the machine went to a load of 11 on
# four performance cores, and the second batch of a=100 replicates took 2870 s
# each against 690 s for the first. At that rate the campaign would have passed
# the 2 h ceiling in envelope/budget.json, and it was slowing an approved run of
# this agent's real pipeline for the sake of a prototype with no card.
#
# So it was stopped once the eight a=100 replicates had landed, and the rest
# is run here on two workers. The occupancy window a=2..5 keeps all 32
# replicates, because that is where the verdict is; the ratios with nothing to
# decide give up replicates instead. Seeds cannot collide with stage 1: stage 1
# completed only ratio 100, and the seed carries the ratio.
STAGE2 = [
    (1, 16, 6000),
    (2, 32, 6000),
    (3, 32, 6000),
    (5, 32, 6000),
    (10, 8, 6000),
    (20, 6, 3000),
    (50, 4, 1500),
]


def exact(ratio):
    m = HarmonicPair(KT, ratio, 0.0, FIXED_SEPARATION)
    lT = P.log_mfpt(m, n=800001)
    lp = P.log_occupancy(m, n=800001)
    t1, t2 = float(np.exp(lT[0])), float(np.exp(lT[1]))
    return dict(tau1=t1, tau2=t2, p1_boltzmann=float(np.exp(lp[0])),
                p1_milestoning=t1/(t1 + t2), barrier=float(m.barrier))


def seed_of(ratio, rep):
    """Distinct and reproducible. Recorded with every replicate."""
    return 1_000_000 + 1000*int(ratio) + rep


def one(job):
    ratio, rep, crossings = job
    m = HarmonicPair(KT, ratio, 0.0, FIXED_SEPARATION)
    ex = exact(ratio)
    t1, t2 = ex["tau1"], ex["tau2"]
    dt = 1.0/(max(m.k1, m.k2)*200)
    t_relax = 1.0/(1.0/t1 + 1.0/t2)
    t_sim = crossings*(t1 + t2)/WALKERS
    n_steps = int(t_sim/dt)
    burn = int(5*t_relax/dt)
    seed = seed_of(ratio, rep)
    t0 = time.time()
    r = P.bd(m, dt, n_steps, WALKERS, seed, x0=0.0, burn_in=burn)
    return dict(ratio=ratio, rep=rep, seed=seed, walkers=WALKERS, dt=dt,
                n_steps=n_steps, burn_in_steps=burn, t_sim=t_sim,
                crossings_1to2=float(r["n_exit"][0]),
                crossings_2to1=float(r["n_exit"][1]),
                tau1=float(r["tau"][0]), tau2=float(r["tau"][1]),
                p1=float(r["p_occ"][0]),
                seconds=time.time() - t0)


def aggregate(rows):
    out = []
    for ratio in sorted({r["ratio"] for r in rows}):
        rs = [r for r in rows if r["ratio"] == ratio]
        ex = exact(ratio)
        agg = dict(ratio=ratio, replicates=len(rs),
                   crossings=sum(r["crossings_1to2"] + r["crossings_2to1"] for r in rs),
                   barrier_kT=ex["barrier"], exact=ex,
                   cpu_seconds=sum(r["seconds"] for r in rs))
        for key in ("tau1", "tau2", "p1"):
            v = np.array([r[key] for r in rs])
            sd = float(v.std(ddof=1)) if len(v) > 1 else float("nan")
            agg[key] = dict(mean=float(v.mean()), sd=sd, se=sd/np.sqrt(len(v)))
        for key, ek in (("tau1", "tau1"), ("tau2", "tau2")):
            a = agg[key]
            a["exact"] = ex[ek]
            a["z_vs_exact"] = (a["mean"] - ex[ek])/a["se"] if a["se"] > 0 else float("nan")
        p = agg["p1"]
        p["milestoning"] = ex["p1_milestoning"]
        p["boltzmann"] = ex["p1_boltzmann"]
        p["z_vs_milestoning"] = (p["mean"] - ex["p1_milestoning"])/p["se"] if p["se"] > 0 else float("nan")
        p["z_vs_boltzmann"] = (p["mean"] - ex["p1_boltzmann"])/p["se"] if p["se"] > 0 else float("nan")
        out.append(agg)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    out_dir = Path(args[0]).expanduser().resolve()
    if "_agent/runs/" in out_dir.as_posix():
        print("refusing: runs/ is for operator runs standing on a plan")
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    if "--aggregate" in sys.argv:
        rows = [json.loads(line) for f in sorted(out_dir.glob("replicates_campaign*.jsonl"))
                for line in f.read_text().splitlines() if line.strip()]
        agg = aggregate(rows)
        (out_dir / "replicates_summary.json").write_text(
            json.dumps(dict(generated="2026-09-23", seat="simulation-7",
                            separation=FIXED_SEPARATION, kt1=KT, walkers=WALKERS,
                            sources=[f.name for f in sorted(out_dir.glob("replicates_campaign*.jsonl"))],
                            rows=agg), indent=1))
        print(f"aggregated {len(rows)} replicates")
        return 0
    workers = WORKERS
    for a in sys.argv:
        if a.startswith("--workers="):
            workers = int(a.split("=", 1)[1])
    if "--smoke" in sys.argv:
        campaign, tag = SMOKE, "smoke"
    elif "--stage2" in sys.argv:
        campaign, tag = STAGE2, "campaign_stage2"
    else:
        campaign, tag = CAMPAIGN, "campaign"

    # Longest jobs first, so the stiff-end replicates do not end up alone at
    # the tail of the queue with three idle workers beside them.
    jobs = [(a, rep, c) for a, n, c in campaign for rep in range(n)]
    jobs.sort(key=lambda j: -j[0]*j[2])

    log = out_dir / f"replicates_{tag}.jsonl"
    rows = []
    t0 = time.time()
    with mp.get_context("spawn").Pool(workers) as pool, open(log, "w") as f:
        for i, row in enumerate(pool.imap_unordered(one, jobs), 1):
            rows.append(row)
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i:3d}/{len(jobs)}] a={row['ratio']:<4} rep={row['rep']:<3} "
                  f"tau={row['tau1']:.4f}/{row['tau2']:.4f} p1={row['p1']:.4f} "
                  f"{row['seconds']:6.0f}s  wall {time.time()-t0:6.0f}s", flush=True)

    agg = aggregate(rows)
    (out_dir / f"replicates_{tag}_summary.json").write_text(
        json.dumps(dict(generated="2026-09-23", seat="simulation-7",
                        separation=FIXED_SEPARATION, kt1=KT, walkers=WALKERS,
                        workers=workers, wall_seconds=time.time() - t0,
                        campaign=campaign, rows=agg), indent=1))
    print(f"done in {time.time()-t0:.0f}s wall")
    return 0


if __name__ == "__main__":
    sys.exit(main())
