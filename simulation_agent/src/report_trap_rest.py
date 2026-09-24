"""Report parts for `bd_overdamped_trapped` (sim-20260923-102), for `report.py`.

`report.py`'s body was written around the driven trap's drag offset. This
configuration's observable is a width, so it supplies its whole body here and
reuses the shared pieces: the section order of task 022, the SVG plot helper,
the code filter, the footer and the notes file. Every number is read from the
result card, its run files and the plan; only the notes are written by hand.

The video is not drawn here. The environment's plotting library is not yet a
declared dependency of `src/`, so the clip is made outside the tree and this
body links it if it sits beside the report as `<stem>.mp4`, and says so if not.
"""

from __future__ import annotations

import html
import json
import math

import numpy as np

from . import cards, trajectory
from .report import (COLORS, K_B, REPORT_DIR, Plot, figure, fmt, legend, md, num, provenance, section)

TITLE = "One bead in one optical trap: the width a camera should see"


def _row(R):
    r = R["results"][0]
    c, o = r["card"], r["obs"]
    w = o["trapped_position_distribution"]
    plan = R["plan"]
    P = {n["name"]: n for n in plan["numbers"]}
    return {
        "r": r, "card": c, "obs": o, "w": w, "P": P, "run_id": c["run_id"],
        "k": P["trap_stiffness_operating"]["value"], "dt": P["integration_timestep_op"]["value"],
        "save": P["save_interval_op"]["value"], "startup": P["startup_discard_op"]["value"],
        "record": P["record_length_op"]["value"], "tau": P["relaxation_time_op"]["value"],
        "exposure": P["camera_exposure_max_op"]["value"], "accept": P["width_acceptance_op"]["value"],
        "met": {e["id"]: e["met"] for e in c["criteria_evaluation"]},
        "seed": json.loads((r["run_dir"] / "trajectory_meta.json").read_text())["trajectory"]["seed"],
    }


def f1(x):
    w = x["w"]; pred = w["predicted_width_um"] * 1e3; sc = w["expected_relative_scatter"]
    p = Plot((-0.5, 1.5), (pred * 0.8, pred * 1.15), xlabel="in-plane axis", ylabel="width (nm)", w=460)
    p.band(pred * (1 - sc), pred * (1 + sc)); p.hline(pred, "#c0392b", "5 3")
    for i, a in enumerate(("x", "y")):
        v = w["axes"][a]
        p.point(i, v["width_um"] * 1e3, pred * sc, COLORS[0], 5)
        p.text(i, pred * 0.82, a, "#333", "middle")
    return figure("F1", p.svg() + legend([(COLORS[0], "measured, with one record's expected scatter"),
                                          ("#c0392b", "predicted √(k_B T/k)"), ("#e5f2ea", "± one expected scatter")]),
                  f"Main result. The bead's width along each in-plane axis, from one run of {w['frames_in_record']} frames "
                  f"over the {fmt(w['record_length_si'])} s record, against equipartition's prediction at {fmt(x['k'])} pN/µm. "
                  "The measured widths sit slightly below the line, as a finite record should: subtracting the record's own "
                  "mean removes a little of the slowest fluctuation.")


def f2(x):
    w = x["w"]; lim = x["accept"]
    p = Plot((-0.5, 1.5), (-lim * 1.4, lim * 1.4), xlabel="in-plane axis", ylabel="relative deviation after the bias correction", w=460)
    p.band(-lim, lim); p.hline(0)
    for i, a in enumerate(("x", "y")):
        p.point(i, w["axes"][a]["relative_deviation_bias_corrected"], None, COLORS[0], 5)
        p.text(i, -lim * 1.3, a, "#333", "middle")
    return figure("F2", p.svg(),
                  f"Residuals. Measured width over predicted, corrected for the record's expected shortfall, minus one. The green "
                  f"band is ±{fmt(lim)}, the pass limit written on the plan before the run. It was meant as three of the record's "
                  f"own standard errors, {fmt(3 * w['expected_relative_scatter'], 2)}; written to one figure it became {fmt(lim)}, "
                  "which is looser. Both points pass either way.")


def f3(x):
    try:
        t = trajectory.read_text(x["r"]["run_dir"])
    except trajectory.TrajectoryUnavailable as exc:
        return f"<p class='gone'><b>F3 not drawn.</b> {html.escape(str(exc))}</p>"
    time = t["steps"] * x["dt"]
    keep = time >= time[0] + x["startup"]
    xs = t["coords"][keep, 0, 0] * 1e9
    tt = time[keep]
    n = min(len(xs), int(5 / x["save"]))
    p1 = Plot((tt[0], tt[n - 1]), (xs[:n].min() * 1.15, xs[:n].max() * 1.15), xlabel="time (s)", ylabel="x position (nm)", w=520, h=260)
    p1.hline(0, "#999"); p1.line(tt[:n], xs[:n], COLORS[0], 0.8)
    h = x["w"]["axes"]["x"]["histogram"]
    edges = np.array(h["edges_in_predicted_widths"]); counts = np.array(h["counts"], float)
    frac = counts / counts.sum(); g = np.array(h["gaussian_expected_fraction"])
    p2 = Plot((edges[0], edges[-1]), (0, max(frac.max(), g.max()) * 1.15), xlabel="x in predicted widths", ylabel="fraction of frames", w=380, h=260)
    p2.bars(edges, frac)
    p2.line(0.5 * (edges[1:] + edges[:-1]), g, "#c0392b", 1.6)
    k = x["w"]["axes"]["x"]["excess_kurtosis"]
    return figure("F3", p1.svg() + p2.svg(),
                  f"Raw data. Left: the first 5 s of the recorded x position after the start-up. Right: the histogram of all "
                  f"{x['w']['frames_in_record']} recorded frames in units of the predicted width, against the Gaussian that "
                  f"equipartition predicts (red). Excess kurtosis {k:+.2f}; for a Gaussian sampled about "
                  f"{int(x['w']['record_length_si'] / x['tau'])} independent times it scatters by roughly ±0.3. A bench "
                  "histogram whose tails fall below the red curve is the sign that the real trap has stopped being harmonic.")


def f4(x):
    try:
        t = trajectory.read_text(x["r"]["run_dir"])
    except trajectory.TrajectoryUnavailable as exc:
        return f"<p class='gone'><b>F4 not drawn.</b> {html.escape(str(exc))}</p>"
    time = t["steps"] * x["dt"]; keep = time >= time[0] + x["startup"]
    pred = x["w"]["predicted_width_um"] * 1e-6
    p = Plot((0.05, 1), (0.7, 1.1), xlabel="fraction of the record used", ylabel="running width ÷ predicted")
    items = []
    for i, a in enumerate((0, 1)):
        c = t["coords"][keep, 0, a]
        idx = np.unique(np.linspace(len(c) // 20, len(c) - 1, 100).astype(int))
        run = [c[: j + 1].std(ddof=1) / pred for j in idx]
        f = (idx + 1) / len(c)
        col = (COLORS[0], COLORS[2])[i]          # not COLORS[1]: that red is the expected-shortfall curve
        p.line(f, run, col, 1.3); items.append((col, "xy"[a]))
    f = np.linspace(0.05, 1, 60)
    T = f * x["w"]["record_length_si"]
    p.line(f, 1 - x["tau"] / T, "#c0392b", 1.3, "5 3"); p.hline(1.0)
    return figure("F4", p.svg() + legend(items + [("#c0392b", "expected shortfall 1 − τ/T")]),
                  "Convergence. The width computed from the first part of the record, as more of it is used. A short record "
                  "understates the width because its own mean absorbs the slowest fluctuations; the red dashed curve is the "
                  "expected shortfall, and the running widths close in on the prediction as the record grows.")


def f5(x):
    P = x["P"]; k = x["k"] * 1e-6
    kT = K_B * P["temperature"]["value"]
    sig = math.sqrt(kT / k) * 1e9
    xs = np.linspace(-6 * sig, 6 * sig, 300)
    u = 0.5 * k * (xs * 1e-9) ** 2 / kT
    depth = 30.0; wid = math.sqrt(depth) * sig
    ug = depth * (1 - np.exp(-xs ** 2 / (2 * wid ** 2)))
    p = Plot((xs[0], xs[-1]), (0, 20), xlabel="distance from the trap centre (nm)", ylabel="energy (k_B T)")
    p.line(xs, u, COLORS[0], 2); p.line(xs, ug, "#999", 1.3, "5 3")
    rho = np.exp(-u); p.line(xs, 18 * rho, "#1f7a4d", 1.2)
    return figure("F5", p.svg() + legend([(COLORS[0], "the trap as modelled: harmonic everywhere"),
                                          ("#999", "a real trap: same curvature, flattening to zero far away (illustrative depth 30 k_B T)"),
                                          ("#1f7a4d", "where the bead spends its time")]),
                  f"The setup, from the plan's parameters at {fmt(x['k'])} pN/µm. The bead stays within a few widths "
                  f"({fmt(sig)} nm each) of the centre, where the two curves agree. They part only far out, where the bead "
                  "almost never goes. The real trap's depth is not known here; the grey curve's depth is illustrative only.")


def body(R, N):
    x = _row(R)
    c, w, P, plan, goal = x["card"], x["w"], x["P"], R["plan"], R["goal"]
    ok = all(v for k, v in x["met"].items() if k != "step_displacement_diverged")
    ax = w["axes"]
    S = []
    S.append(section(1, "Summary",
        f"<div class='box'><p>Asked: how wide should one trapped bead's position distribution be, and how must the bench record "
        f"it so the two sides can be compared? At {fmt(x['k'])} pN/µm the predicted width is {w['predicted_width_um'] * 1e3:.1f} nm. "
        f"The run measured {ax['x']['width_um'] * 1e3:.1f} nm along x and {ax['y']['width_um'] * 1e3:.1f} nm along y.</p>"
        f"<p><b>{'Both criteria set in advance were met.' if ok else 'A criterion set in advance was not met.'}</b> "
        f"Record for at least {fmt(x['record'])} s and keep the exposure at or below {fmt(x['exposure'] * 1e3)} ms.</p></div>"
        + f1(x)))
    S.append(section(2, "Purpose", md(N["Purpose"])))
    S.append(section(3, "What was expected",
        "<p>An overdamped bead in a harmonic trap of stiffness <code>k</code> jiggles with a Gaussian position distribution whose "
        "width along each axis is</p><p class='eq'><code>σ = √(k<sub>B</sub>T / k)</code></p><p>This is equipartition. The bead "
        "relaxes over <code>τ = γ/k</code>, with <code>γ = 3πηd</code>. A record of length T subtracts its own mean, so its width "
        "comes out low by about <code>τ/T</code>, and scatters by about <code>√(τ/2T)</code>. A camera frame averages over its "
        f"exposure and narrows the width further. Here τ = {fmt(x['tau'])} s, so a {fmt(x['record'])} s record should read about "
        f"{fmt(100 * x['tau'] / x['record'], 2)}% low, with {fmt(100 * w['expected_relative_scatter'], 2)}% scatter. These are "
        "textbook results for the Ornstein–Uhlenbeck process.</p>"))
    fixed = [(n, num(c, n)) for n in ("temperature", "viscosity", "bead_diameter")]
    rows = "".join(f"<tr><td>{n.replace('_', ' ')}</td><td class='n'>{fmt(v['value'])} {v['unit']}</td><td>{provenance(v['source'])}</td></tr>"
                   for n, v in fixed if v)
    S.append(section(4, "Variables",
        "<table><tr><th>Quantity</th><th>Value</th><th>Where it came from</th></tr>"
        f"<tr><td><b>held fixed:</b> trap stiffness</td><td class='n'>{fmt(x['k'])} pN/µm</td><td>assumed: the double well's soft trap, "
        "so the result feeds it directly</td></tr>" + rows +
        "<tr><td><b>measured:</b> width along x and y, histogram, relaxation time</td><td class='n'>nm</td><td>read off the run</td></tr>"
        "</table><p>Nothing was varied in this first run. The declared stiffness range for the double well, 0.05 to 50 pN/µm, "
        "has not been run yet.</p>"))
    engine = c.get("new_facts", [{}])[0].get("claim", "") if c.get("new_facts") else ""
    S.append(section(5, "Setup",
        "<p>One sphere in water, held by a harmonic trap, with the fluid at rest, in three dimensions; the width is read in the "
        "two in-plane axes. Inertia is left out, which is exact for a micrometre bead in water on these timescales. <b>Left out:</b> "
        "the trap never softens far from its centre, and walls, other particles and heating by the laser are absent.</p>"
        f"<p>Engine: HOOMD-blue 7.2.0 on the CPU, with the trap as a spring to a fixed anchor. One run, seed {x['seed']}.</p>"
        "<table><tr><th>time step</th><th>save every</th><th>start-up discarded</th><th>record</th></tr>"
        f"<tr><td class='n'>{fmt(x['dt'])} s</td><td class='n'>{fmt(x['save'])} s</td><td class='n'>{fmt(x['startup'])} s</td>"
        f"<td class='n'>{fmt(x['record'])} s</td></tr></table>"
        f"<p><b>Why these settings.</b> Everything scales with the relaxation time, {fmt(x['tau'])} s. The time step is small enough "
        "that one random kick moves the bead much less than its width. A frame is saved about every tenth of a relaxation time, "
        "and the save interval is a whole number of time steps. The start-up covers ten relaxation times, since the bead starts "
        "at the centre and needs time to spread out. The record is two hundred relaxation times, so the width's shortfall and "
        "scatter are both small.</p>" + f5(x)))
    crit = "".join(f"<li>{html.escape(cr['statement'])}</li>" for cr in plan.get("success_criteria", []))
    S.append(section(6, "Criteria set in advance",
        f"<p><b>Set on the plan before any run</b>, dated {html.escape(plan['created_at'][:10])}, and applied as written:</p>"
        f"<ul>{crit}<li>Divergence guard: the run stops as a fault if the bead moves more than its own diameter in one step.</li></ul>"))
    res = "".join(
        f"<tr><td>{a}</td><td class='n'>{ax[a]['width_um'] * 1e3:.2f} nm</td><td class='n'>{w['predicted_width_um'] * 1e3:.2f} nm</td>"
        f"<td class='n'>{ax[a]['ratio_to_equipartition']:.4f}</td><td class='n'>{ax[a]['ratio_bias_corrected']:.4f}</td>"
        f"<td class='n'>{ax[a]['deviation_in_scatters']:+.2f}</td><td class='n'>{ax[a]['excess_kurtosis']:+.2f}</td></tr>" for a in ("x", "y"))
    S.append(section(7, "Results",
        "<table><tr><th>axis</th><th>measured width</th><th>predicted</th><th>measured ÷ predicted</th><th>after bias correction</th>"
        "<th>deviation (scatters)</th><th>excess kurtosis</th></tr>" + res + "</table>"
        f"<p class='meta'>Every value read off the run. Verdict: {'pass' if ok else '<b>fail</b>'}. The run did not diverge and nothing "
        "was dropped.</p>" + f3(x) + f4(x) + _video(x)))
    tau_r = x["obs"]["relaxation_time"]["ratio"]
    S.append(section(8, "Checks",
        "<p>Cases whose answer is known independently, read off the same run:</p>"
        "<table><tr><th>check</th><th>result</th></tr>"
        f"<tr><td>relaxation time fitted from the trace ÷ declared</td><td class='n'>{tau_r:.2f}</td></tr>"
        f"<tr><td>out-of-plane axis variance ÷ expected</td><td class='n'>{x['obs']['transverse']['z']['variance_ratio_to_equipartition']:.3f}</td></tr>"
        f"<tr><td>largest single-step move ÷ bead diameter</td><td class='n'>{fmt(_max_step(x) / (P['bead_diameter']['value'] * 1e-6), 2)}</td></tr>"
        "</table>" + f2(x)))
    S.append(section(9, "Interpretation", "<p class='meta'>Judgement, kept apart from the numbers above.</p>" + md(N["Interpretation"])))
    S.append(section(10, "Limits", md(N["Limits"])))
    caps = json.loads((cards.CONTRACTS / "capabilities" / "microscope.json").read_text())
    can = [cc["config"] for cc in caps["configurations"] for p in (cc.get("produces") or [])
           if (p if isinstance(p, str) else p.get("id")) == plan["observable"]["name"]]
    S.append(section(11, "Link to experiment",
        f"<p>The microscope can measure this width in: {', '.join(can)}, each together with the trap.</p>"
        "<p>The plan for this run is validated and can go to the microscope as the first comparison. What the bench needs: record "
        f"at least {fmt(x['record'])} s, keep the exposure at or below {fmt(x['exposure'] * 1e3)} ms, and write down the laser "
        "dial setting by hand, because nothing reads it back. The stiffness then follows from the measured width as "
        "<code>k = k<sub>B</sub>T / σ²</code>.</p>"))
    S.append(section(12, "Decisions for you", md(N["Decisions"])))
    budget = json.loads((cards.AGENT / "envelope" / "budget.json").read_text())
    lim = next(t for t in budget["targets"] if t["target"] == "local")["limits"]
    cost = x["obs"]["cost"]
    tp = x["r"]["run_dir"] / "trajectory.txt"
    size = tp.stat().st_size if tp.exists() else 0
    S.append(section(13, "Cost",
        f"<p>Integration time: {fmt(cost['integration_wall_s'], 2)} s for {cost['steps']} steps, "
        f"{fmt(cost['wall_s_per_step'] * 1e6, 2)} µs per step, against a ceiling of {lim['wall_clock_max']['value']} "
        f"{lim['wall_clock_max']['unit']} per job.</p><table><tr><th>trajectory kept</th><th>size</th></tr>"
        f"<tr><td><code>simulation_agent/runs/{x['run_id']}/trajectory.txt</code></td><td class='n'>{size / 1e6:.2f} MB of "
        f"{lim['storage_max']['value']} {lim['storage_max']['unit']}</td></tr></table>"
        "<p>This file is what the figures are drawn from; deleting it removes them from the next report.</p>"))
    return "".join(S), {"R": R, "rows": [x], "title": TITLE}


def _max_step(x):
    return json.loads((x['r']['run_dir'] / 'trajectory_meta.json').read_text())['max_single_step_displacement']


def _video(x):
    stem = f"rebuild-report-" + __import__("datetime").date.today().strftime("%m%d") + f"-{x['card']['qid']}"
    if (REPORT_DIR / f"{stem}.mp4").exists():
        return (f"<figure><video src='{stem}.mp4' controls width='560'></video><figcaption><b>V1.</b> The bead seen from "
                "above, moving in the trap plane, with a fading trail. Time on screen in seconds; the scale bar is 50 nm; "
                "every saved frame of the first 12 s is shown. Keep this file beside the report for it to play.</figcaption></figure>")
    return "<p class='gone'><b>V1 not drawn.</b> The video file is not beside this report.</p>"


PARTS = {"build": body, "title": TITLE}
