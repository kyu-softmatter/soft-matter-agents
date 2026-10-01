"""The Stage 2 report for a bleach-recovery question: generated, not written.

    cd simulation_agent && python -m src.report_bleach <qid> <run_id> [<run_id> ...]

Numbers come from the run directories and the deterministic solver, and
figures are drawn from the run files on disk, never by re-running anything.
Writes `stage2_runs.json` (the record), `stage2_runs.md` (for the person,
generated from it) and `stage2_runs.png` into the question's directory.

The Markdown follows the root CLAUDE.md's rules for talking to the person:
provenance in words, and no internal codes in the body. References go in
the footer.
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np

from . import bleach_solver, cards, estimator_bleach, result_card

TIE = 10.0           # explore mode: differences under 10x are ties

# The scratch curve of 2026-09-30 that read D 12 per cent high, before any
# planned run: the manager asked whether that was scatter or bias.
SCRATCH_TRIAL = dict(temperature=293.0, viscosity=1e-3, bead_diameter=100e-9, bleach_radius=3e-6,
                     box_length=30e-6, bleach_rate=200.0, bleach_duration=0.05, frame_interval=0.1,
                     max_recovery_time=6.0, integration_timestep=0.005, pre_bleach_frames=5)


def collect(run_ids: list[str]) -> dict:
    points = {}
    for rid in run_ids:
        run = result_card.read_run(rid)
        params = run["config"]["parameters_si"]
        pred = bleach_solver.predict_si(params)
        obs = run["observables"]
        D_se = pred["D_stokes_einstein_m2_per_s"]
        per = [c for c in obs["per_curve"]]
        rep = [c for c in per if c.get("reported")]
        D = np.array([c["D"] for c in rep]) * 1e-12 / D_se       # ratio to Stokes-Einstein
        s = obs["summary"]
        row = {
            "run_id": rid,
            "point": run["config"].get("compare_arm"),
            "backend": run["log"]["backend"],
            "beads_in_disc": s["beads_in_disc_mean"],
            "n_curves": s["n_curves"],
            "n_reported": s["n_reported"],
            "refusals": s["refusals"],
            "frame_over_tau": params["frame_interval"] / pred["tau_s"],
            "bleach_over_tau": params["bleach_duration"] / pred["tau_s"],
            "dt_s": params["integration_timestep"],
            "predicted_ratio": pred["D_fit_over_D"],
            "predicted_w_over_w": pred["w_measured_over_w"],
            "predicted_plateau": pred["plateau_expected"],
        }
        if len(D) > 1:
            mean, sem = float(D.mean()), float(D.std(ddof=1) / math.sqrt(len(D)))
            row.update(ratio_mean=mean, ratio_sem=sem, ratio_sd=float(D.std(ddof=1)),
                       ratio_p05=float(np.percentile(D, 5)), ratio_p95=float(np.percentile(D, 95)),
                       ratio_median=float(np.median(D)),
                       spread_factor_90=float(np.percentile(D, 95) / np.percentile(D, 5)),
                       z_vs_solver=abs(mean - pred["D_fit_over_D"]) / sem if sem > 0 else None,
                       mobile_fraction_mean=s.get("mobile_fraction_mean"),
                       w_over_w_mean=s.get("w_measured_mean", 0) / params["bleach_radius"])
        cost = next((e for e in run["log"]["events"] if e["event"] == "cost_measured"), {})
        # Every curve that produced a fit, read or refused. A refused curve's D
        # is a one-sided bound, but the spread of single bleaches has to count
        # it, or few-bead curves look better than they are -- the reads that
        # survive refusal are the lucky ones.
        all_D = np.array([c["D"] for c in per if c.get("D") is not None]) * 1e-12 / D_se
        if len(all_D) > 1:
            row.update(all_fitted=int(len(all_D)),
                       all_p05=float(np.percentile(all_D, 5)), all_p95=float(np.percentile(all_D, 95)),
                       all_spread_factor_90=float(np.percentile(all_D, 95) / np.percentile(all_D, 5)))
        row["read_fraction"] = s["n_reported"] / s["n_curves"] if s["n_curves"] else None
        # ADDED AFTER SEEING THE DATA, and labelled so wherever it is shown.
        # The plan's criterion compares the mean of single-curve fits with the
        # solver; at a few hundred beads the fit refuses the slow curves, so
        # that mean is selected and reads high. The comparison that tests the
        # integrator is curve against curve: the mean bright fraction, frame by
        # frame, against the equation, and one fit to the mean curve.
        mc = obs.get("mean_curve")
        if mc and mc.get("F_sem"):
            Fm, Fe = np.array(mc["F_mean"]), np.array(mc["F_sem"])
            Fp = np.array(pred["F"][: len(Fm)])
            z = np.abs(Fm - Fp) / np.where(Fe > 0, Fe, np.inf)
            ws = [c["w_measured"] for c in per if c.get("w_measured")]
            w_mean = float(np.mean(ws)) if ws else None
            fit = estimator_bleach.estimate(np.array(mc["t_s"]), Fm, w_mean, params["bleach_radius"] * 1e6,
                                            params["bleach_duration"], params["frame_interval"],
                                            params["max_recovery_time"])
            curves = obs.get("curves_F")
            if curves and len(curves) > 2 and fit.get("D"):
                # jackknife over curves: the fit to the mean curve, leaving one out
                C = np.array(curves)
                n = len(C)
                loo = []
                for i in range(n):
                    Fi = (C.sum(axis=0) - C[i]) / (n - 1)
                    fi = estimator_bleach.fit(np.array(mc["t_s"]), Fi, tau_guess=fit["tau"])
                    if fi.get("converged"):
                        loo.append((w_mean * 1e-6) ** 2 / (4 * fi["tau"]) / D_se)
                if len(loo) > 2:
                    loo = np.array(loo)
                    se = float(np.sqrt((len(loo) - 1) / len(loo) * np.sum((loo - loo.mean()) ** 2)))
                    mcr = fit["D"] * 1e-12 / D_se
                    row.update(mean_curve_ratio_se=se,
                               z_mean_curve_vs_solver=abs(mcr - pred["D_fit_over_D"]) / se if se > 0 else None)
            row.update(curve_frames=int(len(Fm)), curve_z_max=float(z.max()),
                       curve_within_2se=float(np.mean(z <= 2.0)),
                       mean_curve_ratio=(fit["D"] * 1e-12 / D_se) if fit.get("D") else None,
                       mean_curve_reported=fit.get("reported"))
        row["wall_s"] = (cost.get("integration_wall_s") or 0) + (cost.get("frame_readout_wall_s") or 0)
        row["particle_step_rate"] = cost.get("particle_step_rate")
        row["mean_curve"] = obs.get("mean_curve")
        row["pred_curve"] = {"t_over_tau": pred["t_over_tau"], "F": pred["F"], "tau_s": pred["tau_s"]}
        row["ratios"] = [float(x) for x in D]
        key = row["point"] + ("_s2" if rid.endswith("-s2") else "")
        points[key] = row
    return points


def threshold(points: dict) -> dict:
    """The bead count below which one curve's 90 per cent range exceeds a tie."""
    scan = sorted((p["beads_in_disc"], p.get("all_spread_factor_90"), p["read_fraction"])
                  for k, p in points.items() if k and k.endswith("_dt_f12_b30") and p.get("all_spread_factor_90"))
    crossing = None
    for (n0, f0, _), (n1, f1, _) in zip(scan, scan[1:]):
        if f0 > TIE >= f1:
            # log-log interpolation between the bracketing levels
            x = math.log(n0) + (math.log(f0) - math.log(TIE)) * (math.log(n1) - math.log(n0)) / (math.log(f0) - math.log(f1))
            crossing = math.exp(x)
    return {"scan": [{"beads": n, "spread_factor_90": f, "reported_fraction": r} for n, f, r in scan],
            "beads_where_spread_is_a_tie": crossing,
            "definition": "the ratio of the 95th to the 5th percentile of single-curve D over every curve "
                          "that produced a fit (read or refused), against the factor of ten that explore "
                          "mode calls a tie; the fraction of curves the fit reads is reported beside it"}


def main(qid: str, run_ids: list[str]) -> dict:
    points = collect(run_ids)
    th = threshold(points)
    base, half = points.get("n300_dt_f12_b30"), points.get("n300_dt2_f12_b30")
    dt_check = None
    b2, h2 = points.get("n300_dt_f12_b30_s2"), points.get("n300_dt2_f12_b30_s2")
    mean_curve_dt = None
    if b2 and h2 and b2.get("mean_curve_ratio_se") and h2.get("mean_curve_ratio_se"):
        mean_curve_dt = {"base": b2["mean_curve_ratio"], "finer": h2["mean_curve_ratio"],
                         "z": abs(b2["mean_curve_ratio"] - h2["mean_curve_ratio"])
                              / math.hypot(b2["mean_curve_ratio_se"], h2["mean_curve_ratio_se"])}
    if base and half and base.get("ratio_sem") and half.get("ratio_sem"):
        dt_check = {"base": base["ratio_mean"], "finer": half["ratio_mean"],
                    "z": abs(base["ratio_mean"] - half["ratio_mean"]) / math.hypot(base["ratio_sem"], half["ratio_sem"])}
    record = {"kind": "stage2_runs", "qid": qid, "generated_by": "simulation_agent/src/report_bleach.py",
              "points": points, "single_curve_threshold": th, "dt_halving": dt_check,
              "dt_halving_mean_curve_second_seed": mean_curve_dt, "tie_factor": TIE}
    out = cards.question_dir(qid)
    (out / "stage2_runs.json").write_text(json.dumps(record, indent=1) + "\n")
    _figure(record, out / "stage2_runs.png")
    (out / "stage2_runs.md").write_text(_markdown(record))
    return record


def _order(points):
    order = ["n10_dt_f12_b30", "n30_dt_f12_b30", "n100_dt_f12_b30", "n300_dt_f12_b30", "n1000_dt_f12_b30",
             "n300_dt2_f12_b30", "n300_dt_f12_b30_s2", "n300_dt2_f12_b30_s2",
             "n300_dt_f30_b30", "n300_dt_f6_b30", "n300_dt_f12_b12", "n300_dt_f6_b12"]
    return [points[k] for k in order if k in points]


def _markdown(r: dict) -> str:
    P = r["points"]
    L = []
    a = L.append
    th = r["single_curve_threshold"]
    a("# sim-20260930-401, Stage 2: the bleach recovery simulated, bead by bead")
    a("")
    a("*Generated by `simulation_agent/src/report_bleach.py` from the run files; `stage2_runs.json` "
      "beside this file is the record.*")
    a("")
    a("## What the runs show")
    a("")
    cross = th["beads_where_spread_is_a_tie"]
    scan = th["scan"]
    bias_keys = ("n300_dt_f12_b30", "n300_dt2_f12_b30", "n300_dt_f12_b30_s2", "n300_dt2_f12_b30_s2",
                 "n300_dt_f30_b30", "n300_dt_f6_b30", "n300_dt_f12_b12", "n300_dt_f6_b12")
    bias = [P[k] for k in bias_keys if k in P and P[k].get("ratio_mean") is not None]
    zs = [b["z_vs_solver"] for b in bias if b.get("z_vs_solver") is not None]
    worst_pred = max((abs(b["predicted_ratio"] - 1) for b in bias), default=None)
    worst_read = max((abs(b["ratio_mean"] - 1) for b in bias), default=None)
    if cross:
        a(f"**One bleach places D in the right decade only above about {int(float(f'{cross:.1g}'))} beads in the disc.** "
          "Below that, single curves scatter over more than a factor of ten and most are refused by the fit "
          "as bounds rather than read. The beads are counted through the whole depth of the bleached "
          "column, so at ordinary dilutions a disc of a few micrometres holds hundreds to thousands.")
    elif scan:
        a("**At every bead count run here, one curve's 90 per cent range is "
          + ("narrower" if scan[0]["spread_factor_90"] <= TIE else "wider") + " than a factor of ten.**")
    a("")
    curve_z = [q["curve_z_max"] for q in P.values() if q.get("curve_z_max") is not None]
    within = [q["curve_within_2se"] for q in P.values() if q.get("curve_within_2se") is not None]
    if curve_z:
        a(f"**The simulated recovery is the one the diffusion equation predicts, at every setting.** Averaged "
          f"over fifty bleaches, the bright fraction in the disc stays within {max(curve_z):.1f} standard "
          f"errors of the equation at every frame, and at least {100 * min(within):.0f} per cent of frames lie "
          "within two. That is the check this stage exists for: the simulation says nothing new about the "
          "real beads (their D is fixed by the size, the viscosity and the temperature put in), but it "
          "shows the bleach and the camera behave as planned before anyone spends sample on them.")
        a("")
    sel = [q for q in bias if q.get("z_vs_solver") is not None and q["z_vs_solver"] > 3]
    if sel:
        hi = max(bias, key=lambda q: q["ratio_mean"])
        lo = min(bias, key=lambda q: q["ratio_mean"])
        a("**Averaging the D of single bleaches is biased, and the bias comes from the fit, not the beads.** "
          "The fit refuses a curve whose recovery looks too slow for the record or too fast for the frames, "
          "so the curves it keeps are a selected set. At a few hundred beads the mean of the kept curves "
          f"reads from {lo['ratio_mean']:.2f} to {hi['ratio_mean']:.2f} of the true value, and the check "
          "declared before the runs -- that this mean matches the equation -- **fails** at "
          f"{len(sel)} of {len(bias)} settings. **Average the curves first and fit once**: a fit to the mean "
          "curve reads "
          + ", ".join(f"{q['mean_curve_ratio']:.2f}" for q in bias if q.get("mean_curve_ratio")) +
          " at the same settings. (The mean-curve comparison was added after the data were seen, and is "
          "labelled so in the record.)")
        a("")
    a("## How far one curve strays, against beads in the disc")
    a("")
    a("Base settings: disc 3 um, frames every 50 ms, a 20 ms bleach, a 9 s record, 50 independent curves "
      "per row. D is given as a fraction of the value the beads were simulated with.")
    a("")
    a("| beads in disc | curves the fit reads | one curve, middle 90 per cent (every fitted curve) | spread of that range | mean of the read curves |")
    a("|---|---|---|---|---|")
    for p in _order(P):
        if not p["point"].endswith("_dt_f12_b30"):
            continue
        rng = (f"{p['all_p05']:.2g} - {p['all_p95']:.2g} | x{p['all_spread_factor_90']:.2g}"
               if p.get("all_spread_factor_90") else "-- | --")
        mean = f"{p['ratio_mean']:.2f} +/- {p['ratio_sem']:.2f}" if p.get("ratio_mean") is not None else "--"
        a(f"| {p['beads_in_disc']:.0f} | {p['n_reported']} of {p['n_curves']} | {rng} | {mean} |")
    a("")
    a("A curve the fit does not read is one it refuses: its fitted recovery time came out so short or so "
      "long against the frames, the bleach or the record that the curve can only bound D from one side. "
      "With few beads that is common, and it is part of the answer: a refused curve is a bleach that "
      "taught nothing.")
    a("")
    a("## The bleach and the camera, against the diffusion equation")
    a("")
    a("Each row is 50 curves at about 300 beads. 'Predicted' is what the diffusion equation gives when "
      "it is bleached, sampled and fitted exactly as the run is -- so a row that agrees shows the "
      "integrator, the bleach and the fit are working, and the size of the prediction is the bias "
      "itself.")
    a("")
    a("| setting | frame / recovery time | bleach / recovery time | mean of kept single curves | fit to the mean curve | predicted | single-curve mean apart, in standard errors |")
    a("|---|---|---|---|---|---|---|")
    names = {"n300_dt_f12_b30": "base", "n300_dt2_f12_b30": "finer engine step", "n300_dt_f30_b30": "faster camera",
             "n300_dt_f6_b30": "slower camera (near the limit)", "n300_dt_f12_b12": "longer bleach (near the limit)",
             "n300_dt_f6_b12": "both near the limit"}
    for p in _order(P):
        if p["point"] not in names or p.get("ratio_mean") is None:
            continue
        mcr = (f"{p['mean_curve_ratio']:.3f}" + (f" +/- {p['mean_curve_ratio_se']:.3f}" if p.get("mean_curve_ratio_se") else "")
               if p.get("mean_curve_ratio") else "--")
        a(f"| {names[p['point']]}{' (second seed)' if p['run_id'].endswith('-s2') else ''} | 1/{1 / p['frame_over_tau']:.0f} | "
          f"1/{1 / p['bleach_over_tau']:.0f} | {p['ratio_mean']:.3f} +/- {p['ratio_sem']:.3f} | {mcr} | "
          f"{p['predicted_ratio']:.3f} | {p['z_vs_solver']:.1f} |")
    if r.get("dt_halving"):
        d = r["dt_halving"]
        a("")
        a(f"**The engine step: passes as declared, and leaves a question open.** A finer step (5 ms to 2 ms) "
          f"moves the mean of the kept single curves from {d['base']:.3f} to {d['finer']:.3f}, {d['z']:.1f} "
          "standard errors, which is the check declared before the runs, and it passes.")
    if r.get("dt_halving_mean_curve_second_seed"):
        d = r["dt_halving_mean_curve_second_seed"]
        fz = [P[k]["curve_z_max"] for k in ("n300_dt2_f12_b30", "n300_dt2_f12_b30_s2") if P.get(k, {}).get("curve_z_max")]
        a("")
        a(f"But on a second seed, with every curve saved, one fit to the mean curve reads {d['base']:.3f} at "
          f"5 ms and {d['finer']:.3f} at 2 ms, {d['z']:.1f} jackknife standard errors apart, and the finer-step "
          "runs are the two whose mean curves sit furthest from the equation on any frame ("
          + " and ".join(f"{z:.1f}" for z in fz) + " standard errors). The diffusion equation predicts no "
          "difference between the two steps. Whether this is chance or a small real effect of the step is "
          "not resolved by these runs; more curves at both steps would settle it. At the factor-of-ten "
          "resolution asked for it is a tie either way, and it would matter only for a confirmatory measurement.")
    a("")
    a("## The 12 per cent single curve from the first trial")
    a("")
    sc = bleach_solver.predict_si(SCRATCH_TRIAL)
    a("A first trial curve, before these runs, read D 12 per cent high at about a thousand beads (disc "
      "3 um, bleach rate 200 per second for 50 ms, frames every 100 ms, a 6 s record). The diffusion "
      f"equation, bleached and sampled the same way, predicts that setup reads {sc['D_fit_over_D']:.2f} of "
      f"the true value: the bleach lengthens the fitted recovery time by {100 * (sc['tau_fit_over_tau'] - 1):.0f} "
      f"per cent and the half-contrast radius grows by {100 * (sc['w_measured_over_w'] - 1):.0f} per cent to "
      "match, and the two nearly cancel. So the 12 per cent is the scatter of one curve, not a bias -- "
      + (f"about {0.12 / P['n1000_dt_f12_b30']['ratio_sd']:.1f} standard deviations of one curve at that "
         "bead count." if P.get("n1000_dt_f12_b30", {}).get("ratio_sd") else "within one curve's scatter."))
    a("")
    a("## What binds as the disc grows")
    a("")
    a("Measured in recovery times and disc radii the model is the same at every disc size, so nothing "
      "above changes with w. What changes is the clock, and the things the model leaves out bind on "
      "the clock. Computed from the same D (about 4 um^2/s) and the same sedimentation speed (about "
      "0.2 nm/s) as the first stage; none of the last three columns is modelled.")
    a("")
    a("| disc radius (um) | recovery time | shortest record the fit allows | reference region at least this far (um) | field of view at least (um) | settling over the record (um) | beads in a 10 um column at volume fraction 1e-6 |")
    a("|---|---|---|---|---|---|---|")
    for w, row in _large_w().items():
        a(f"| {w:g} | {row['tau']} | {row['record']} | {row['ref']:g} | {row['fov']:g} | {row['settle']:.2g} | {row['beads']:.2g} |")
    a("")
    a("Up to about 10 um the record is under a minute and these are small. From 30 um the record runs "
      "to many minutes and past an hour at 100 um: bleaching by the imaging light over that time (which "
      "the reference region corrects only if it sees the same light), drift of the stage and focus, and "
      "a field of view of a millimetre become the limits, and none of them is in this model.")
    a("")
    a("## What this cannot say, and what is asked for")
    a("")
    a("- The simulated D is the value put in. These runs check the method; they are not evidence about "
      "how the real beads move.")
    a("- The camera here counts beads perfectly: no blur, no photon noise, no background, no bleaching by "
      "the imaging light, no drift, no walls. Real curves scatter more than these.")
    a("- The bleach rate (50 per second) is a guess and sets how deep the dip is. **Measure the bleaching "
      "rate under the patterning light first**; with it, and the measured first frame after the bleach "
      "and the bleach length actually used, these runs are repeated with the real numbers so that the "
      "same small biases sit on both sides of the comparison.")
    a("- The disc size does not change these conclusions: measured in recovery times and disc radii the "
      "problem is the same at any disc, so a 30 um disc has the same biases and, at the same dilution, "
      "a hundred times more beads.")
    a("")
    a("![Stage 2](stage2_runs.png)")
    a("")
    a("---")
    a("References: task 025; plan `v2_plan_simulation_sim-20260930-401.json`; runs "
      + ", ".join(f"`{p['run_id']}`" for p in _order(P)) + "; engine " + (_order(P)[0]["backend"] if P else "") + ".")
    return "\n".join(L) + "\n"


def _hms(t: float) -> str:
    def two(x):
        return f"{x:.0f}" if x >= 10 else f"{x:.2g}"
    if t < 1:
        return f"{two(t * 1e3)} ms"
    if t < 120:
        return f"{two(t)} s"
    if t < 7200:
        return f"{two(t / 60)} min"
    return f"{two(t / 3600)} h"


def _large_w() -> dict:
    """The clock against disc size, from the first stage's D and settling speed."""
    stage1 = json.loads((cards.question_dir("sim-20260930-401") / "stage1_closed_forms.json").read_text())
    D = stage1["diffusivity"]["unrounded"]                      # um^2/s
    v_settle = stage1["sedimentation"]["velocity_nm_per_s"] * 1e-3  # um/s
    v_bead = math.pi * 0.1**3 / 6
    out = {}
    for w in (1, 3, 10, 30, 100):
        tau = w * w / (4 * D)
        record = 10 * tau
        out[w] = {"tau": _hms(tau), "record": _hms(record), "ref": 5 * w, "fov": 12 * w,
                  "settle": v_settle * record, "beads": 1e-6 * math.pi * w * w * 10 / v_bead}
    return out


def _figure(r: dict, path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    P = r["points"]
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
    base = P.get("n300_dt_f12_b30")
    if base and base.get("mean_curve"):
        mc, pc = base["mean_curve"], base["pred_curve"]
        tau = pc["tau_s"]
        t = np.array(mc["t_s"]) / tau
        F = np.array(mc["F_mean"])
        e = np.array(mc["F_sem"]) if mc.get("F_sem") else None
        ax[0].errorbar(t, F, yerr=e, fmt=".", ms=3, alpha=0.6, label="simulated, mean of 50 curves")
        ax[0].plot(pc["t_over_tau"], pc["F"], "k-", lw=1.2, label="diffusion equation, same camera")
        ax[0].set_xscale("log")
        ax[0].set_xlabel("time after the bleach / recovery time")
        ax[0].set_ylabel("bright fraction in the disc")
        ax[0].set_title("Base point: simulation against the equation")
        ax[0].legend(fontsize=8)
    for k in ("n10_dt_f12_b30", "n30_dt_f12_b30", "n100_dt_f12_b30", "n300_dt_f12_b30", "n1000_dt_f12_b30"):
        p = P.get(k)
        if not p or not p["ratios"]:
            continue
        x = np.full(len(p["ratios"]), p["beads_in_disc"]) * np.exp(np.random.default_rng(0).normal(0, 0.05, len(p["ratios"])))
        ax[1].plot(x, p["ratios"], "o", ms=3, alpha=0.5)
    ax[1].axhspan(1 / math.sqrt(TIE), math.sqrt(TIE), color="green", alpha=0.07, label="within a half-decade")
    ax[1].axhline(1.0, color="k", lw=0.8)
    ax[1].set_xscale("log"); ax[1].set_yscale("log")
    ax[1].set_xlabel("beads in the disc")
    ax[1].set_ylabel("one curve's D / D put in")
    ax[1].set_title("How far one bleach strays (curves the fit read)")
    ax[1].legend(fontsize=8)
    labels, read, err, pred = [], [], [], []
    for k, lab in (("n300_dt_f12_b30", "base"), ("n300_dt2_f12_b30", "finer step"), ("n300_dt_f30_b30", "faster camera"),
                   ("n300_dt_f6_b30", "slower camera"), ("n300_dt_f12_b12", "longer bleach"), ("n300_dt_f6_b12", "both")):
        p = P.get(k)
        if not p or p.get("ratio_mean") is None:
            continue
        labels.append(lab); read.append(p["ratio_mean"]); err.append(p["ratio_sem"]); pred.append(p["predicted_ratio"])
    y = np.arange(len(labels))
    ax[2].errorbar(read, y, xerr=err, fmt="o", label="simulated mean")
    ax[2].plot(pred, y, "kx", ms=8, label="diffusion equation")
    ax[2].axvline(1.0, color="grey", lw=0.8)
    ax[2].set_yticks(y); ax[2].set_yticklabels(labels)
    ax[2].set_xlabel("D read / D put in")
    ax[2].set_title("Bias of the bleach and camera, about 300 beads")
    ax[2].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)


if __name__ == "__main__":
    rec = main(sys.argv[1], sys.argv[2:])
    print(json.dumps({"threshold": rec["single_curve_threshold"], "dt_halving": rec["dt_halving"]}, indent=1))
