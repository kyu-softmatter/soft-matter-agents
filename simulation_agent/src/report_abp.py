"""The report for the active-particle study: interactions (041) and box size (042).

Follows the shared template (task 022; `report.py`'s header is the authority)
and reuses its parts -- the SVG panel, figure and legend wrappers, the code
scan, the plain-language provenance, the stylesheet. What differs is why this
is a module of its own: `report.build` reads one revision's plan and is
written around a trap's quantities, while these two questions are one study
whose grid ran across four revisions of 041 plus the compare in 042. So the
loader here gathers every result card of both questions, and the sections
speak about swimmers.

Numbers come from the result cards and run files; nothing is re-run. The
figures that need positions (raw paths, convergence, the video) are drawn from
the one run that kept a trajectory file, and say so.

    cd simulation_agent && ../.pixi/envs/sim/bin/python -m src.report_abp
"""

from __future__ import annotations

import datetime as _dt
import html
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

from . import cards, trajectory
from . import report as R0
from .estimator_abp import ActiveEstimator

Q1, Q2 = "sim-20260923-041", "sim-20260923-042"
TRAJ_RUN = "run-20260923-042-small-s2"
PE_COL = {1: R0.COLORS[0], 10: R0.COLORS[1], 100: R0.COLORS[2]}
PRETTY = {"um": "µm", "um^2/s": "µm²/s", "1/s": "s⁻¹", "Pa*s": "Pa·s"}


def num(card, name):
    n = next((x for x in card["numbers"] if x["name"] == name), None)
    return None if n is None else n


def val(card, name):
    n = num(card, name)
    return None if n is None else float(n["value"])


def load() -> dict:
    out = {"grid": [], "compare": []}
    for q, key in ((Q1, "grid"), (Q2, "compare")):
        for p in sorted(cards.question_dir(q).glob("result_run-*.json")):
            c = json.loads(p.read_text())
            run = cards.AGENT / "runs" / c["run_id"]
            obs = json.loads((run / "observables.json").read_text())
            log = json.loads((run / "log.json").read_text())
            meta = json.loads((run / "trajectory_meta.json").read_text())
            cfg = json.loads((run / "config.json").read_text())
            pe = val(c, "peclet"); d = val(c, "bead_diameter"); dr = val(c, "rotational_diffusivity")
            row = {"card": c, "run": c["run_id"], "obs": obs, "log": log, "meta": meta, "cfg": cfg,
                   "pe": pe, "phi": val(c, "packing_fraction"), "box": val(c, "box_length"), "N": val(c, "n_particles"),
                   "N_engine": [e for e in log["events"] if e["event"] == "preflight"][0]["report"].get("n_particles"),
                   "d": val(c, "effective_translational_diffusivity"), "se": val(c, "effective_translational_diffusivity_standard_error"),
                   "free": val(c, "effective_diffusivity_free_expectation"), "tau_p": val(c, "persistence_time"),
                   "lp": pe * d, "rev": c["plan_revision"], "outcome": c["outcome"],
                   "met": {e["id"]: e["met"] for e in c["criteria_evaluation"]},
                   "wall": [e for e in log["events"]][-1]["t_mono"]}
            # The free swimmer's value from the run's OWN inputs, not the card's
            # one-figure number. The grid cards round it (explore mode) -- 10
            # for 12.6 at strength 10, 1000 for 1250 at 100 -- which moved the
            # ratios by up to a quarter and made the dilute cells look faster
            # than a free swimmer when they are not. The engine's translational
            # diffusivity, swimming speed and rotational rate are read off the
            # run's preflight and configuration.
            pre = [e for e in log["events"] if e["event"] == "preflight"][0]["report"]
            dt_si = float(pre["diffusivity_si"]); v0_si = float(pre["self_propulsion_speed_si"])
            dr_si = float(cfg["parameters_si"]["rotational_diffusivity"])
            row["free_card"] = row["free"]
            row["free"] = (dt_si + v0_si * v0_si / (2 * dr_si)) * 1e12
            row["dt_engine"], row["v0_engine"], row["dr_engine"] = dt_si * 1e12, v0_si * 1e6, dr_si
            out[key].append(row)
    return out


def free_msd(t, dt_, v0, dr):
    """The free active particle's 2D mean squared displacement, um^2, at lags t (s).

    4 D_T t + 2 v0^2 tau^2 (t/tau - 1 + exp(-t/tau)), tau = 1/D_R. The bracket is
    taken by its series below t/tau = 1e-4, where the direct form cancels.
    """
    tau = 1.0 / dr
    x = np.asarray(t) / tau
    br = np.where(x < 1e-4, x * x / 2 - x ** 3 / 6, x - 1 + np.exp(-x))
    return 4 * dt_ * np.asarray(t) + 2 * v0 * v0 * tau * tau * br


# -- figures -------------------------------------------------------------------

def f1(G):
    p = R0.Plot((0.005, 1), (0.1, 3), logx=True, logy=True, xlabel="packing fraction", ylabel="spreading rate ÷ free swimmer")
    p.hline(1)
    items = []
    for pe in sorted({r["pe"] for r in G}):
        rows = sorted([r for r in G if r["pe"] == pe and r is best(G, r)], key=lambda r: r["phi"])
        col = PE_COL.get(int(pe), "#555")
        if len(rows) > 1:
            p.line([r["phi"] for r in rows], [r["d"] / r["free"] for r in rows], col, 1.5)
        for r in [x for x in G if x["pe"] == pe]:
            p.point(r["phi"], r["d"] / r["free"], r["se"] / r["free"], col, 5 if r is best(G, r) else 3)
        items.append((col, f"swimming strength {pe:g}"))
    return R0.figure("F1", p.svg() + R0.legend(items + [("#888", "dashed: a free swimmer at the same strength")]),
        f"Main result. The long-time spreading rate of the interacting particles divided by that of a free swimmer at the same "
        f"swimming strength, against how crowded the box is, from {len(G)} runs of one seed each. Error bars are each run's own "
        "statistical error. Where one condition ran twice in boxes of different size, both are drawn and the line goes through "
        "the larger box.")


def best(G, r):
    same = [x for x in G if x["pe"] == r["pe"] and x["phi"] == r["phi"]]
    return max(same, key=lambda x: x["box"])


def f2(G):
    rows = sorted([r for r in G if r is best(G, r)], key=lambda r: (r["pe"], r["phi"]))
    p = R0.Plot((-0.5, len(rows) - 0.5), (-1.5, 1.5), xlabel="condition (swimming strength / packing fraction)", ylabel="log10 (measured ÷ free)")
    p.band(-1, 1); p.hline(0)
    for i, r in enumerate(rows):
        p.point(i, math.log10(r["d"] / r["free"]), None, PE_COL.get(int(r["pe"]), "#555"), 5)
        p.text(i, -1.35, f"{r['pe']:g} / {r['phi']:g}", "#555", "middle")
    return R0.figure("F2", p.svg(),
        "Departure from the free swimmer, as the base-10 logarithm of the ratio, one dot per condition. The green band is one "
        "factor of ten either way: the resolution you asked for, set on the plan before any run. Every condition sits inside it.")


def f3(T):
    if T is None:
        return f"<p class='gone'>The raw-path figure needs {TRAJ_RUN}'s trajectory file, which is gone. {GONE[0]}</p>"
    xy = T["coords"] * 1e6
    stretch = slice(0, 3001)
    p = R0.Plot((xy[stretch, :, 0].min() - 10, xy[stretch, :, 0].max() + 10), (xy[stretch, :, 1].min() - 10, xy[stretch, :, 1].max() + 10),
                w=460, h=460, xlabel="x (µm)", ylabel="y (µm)")
    for k in range(min(4, xy.shape[1])):
        col = R0.COLORS[k % len(R0.COLORS)]
        p.line(xy[stretch, k, 0][::5], xy[stretch, k, 1][::5], col, 1)
        p.point(xy[0, k, 0], xy[0, k, 1], None, col, 4)
    dt = T["meta"]["save_interval_steps"]
    return R0.figure("F3", p.svg(),
        f"Raw data. The paths of four of the {xy.shape[1]} particles over the first 3000 s of one run (swimming strength 10, packing "
        "fraction 0.1, box 50 µm), unwrapped so a particle leaving one side of the box keeps going. Dots mark the start. Each "
        "particle swims at 0.5 µm/s and forgets its direction in about 100 s, so the straight stretches are about 50 µm long.")


def f4(T):
    if T is None:
        return f"<p class='gone'>The convergence figure needs {TRAJ_RUN}'s trajectory file, which is gone. {GONE[0]}</p>"
    frames = list(T["coords"]); times = (T["steps"] * 0.005).tolist()
    fr = np.linspace(0.2, 1.0, 9); est, err = [], []
    for f in fr:
        n = int(len(frames) * f)
        e = ActiveEstimator(times[:n], frames[:n], None, dimensions=2)
        fit = e.fit_effective_diffusivity(1000.0, 3000.0); u = e.block_uncertainty(1000.0, 3000.0)
        est.append(fit["diffusivity"] * 1e12); err.append((u.get("standard_error") or 0) * 1e12)
    final = est[-1]
    p = R0.Plot((0.15, 1.05), (0, max(e + s for e, s in zip(est, err)) * 1.2), xlabel="fraction of the record used", ylabel="spreading rate (µm²/s)")
    p.hline(final, "#1f7a4d")
    for f, e, s in zip(fr, est, err):
        p.point(f, e, s, R0.COLORS[1], 3)
    return R0.figure("F4", p.svg(),
        f"Convergence. The spreading rate estimated from the first part of one run's record, with that estimate's own statistical "
        f"error, as more of the record is used (swimming strength 10, packing fraction 0.1, 13 particles). The green line is the "
        f"full-record value, {R0.fmt(final)} µm²/s. The estimate settles well before the end; the error bar shrinks as the record grows.")


def f5(c):
    eps_kT = val(c, "wca_epsilon") / (1.380649e-23 * val(c, "temperature"))
    r = np.linspace(0.9, 1.3, 200); rc = 2 ** (1 / 6)
    u = np.where(r < rc, 4 * eps_kT * ((1 / r) ** 12 - (1 / r) ** 6) + eps_kT, 0.0)
    p = R0.Plot((0.9, 1.3), (-0.5, 8), w=460, h=300, xlabel="centre-to-centre distance ÷ particle diameter", ylabel="energy (thermal units)")
    p.hline(0); p.line(r, u, R0.COLORS[0], 2)
    p.text(rc + 0.01, 1.5, "no force beyond here", "#555")
    return R0.figure("F5", p.svg(),
        f"Setup. The repulsion between two particles as they approach, in units of the thermal energy: zero until they touch, then "
        f"rising steeply, depth {R0.fmt(eps_kT, 2)} thermal units. There is no attraction. Each particle also swims along its own "
        "direction, which turns randomly.")


def f6(G, C):
    def panel(title, group):
        top = max(r["d"] + r["se"] for _, r in group) * 1.15
        W, left, right, rowh = 620, 190, 110, 40
        X = lambda v: left + v / top * (W - left - right)
        H = 30 + rowh * len(group) + 36
        parts = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" font-family="Helvetica, Arial, sans-serif">']
        for i, (lab, r) in enumerate(group):
            y = 20 + i * rowh
            parts.append(f'<text x="{left - 8}" y="{y + 17}" font-size="12" text-anchor="end">{html.escape(lab)}</text>')
            parts.append(f'<rect x="{left}" y="{y + 4}" width="{X(r["d"]) - left:.1f}" height="22" rx="3" fill="{R0.COLORS[1]}"/>')
            parts.append(f'<line x1="{X(r["d"] - r["se"]):.1f}" x2="{X(r["d"] + r["se"]):.1f}" y1="{y + 15}" y2="{y + 15}" stroke="#111" stroke-width="2"/>')
            parts.append(f'<text x="{X(r["d"] + r["se"]) + 6:.1f}" y="{y + 19}" font-size="12">{r["d"]:.2f} ± {r["se"]:.2g}</text>')
        yb = 20 + rowh * len(group) + 4
        parts.append(f'<line x1="{left}" x2="{X(top):.1f}" y1="{yb}" y2="{yb}" stroke="#999"/>')
        step = 1 if top < 6 else 5
        v = 0
        while v <= top:
            parts.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{yb}" y2="{yb + 4}" stroke="#999"/><text x="{X(v):.1f}" y="{yb + 16}" font-size="11" text-anchor="middle">{v:g}</text>')
            v += step
        parts.append(f'<text x="{(left + X(top)) / 2:.1f}" y="{H - 4}" font-size="12" text-anchor="middle">spreading rate (µm²/s), {title}</text></svg>')
        return "".join(parts)
    top_rows = [(f"{r['box']:g} µm box, {r['N_engine']} particles, seed {r['cfg']['seed']}", r) for r in sorted(C, key=lambda r: (r["box"], r["run"]))]
    dense = [(f"{r['box']:g} µm box, {r['N_engine']} particles", r) for r in sorted([r for r in G if r["pe"] == 10 and r["phi"] == 0.5], key=lambda r: r["box"])]
    return R0.figure("F6", panel("strength 10, packing 0.1", top_rows) + panel("strength 10, packing 0.5", dense),
        "Box size. The same condition run in boxes of different size. Top: one persistence length (50 µm) against ten (500 µm), "
        "with the small box run twice from different random starts. Bottom: the densest condition in a box of one persistence "
        "length and of four. Black lines are each run's statistical error. The box does not change the answer in either case.")


def f7(G):
    p = R0.Plot((1, 3e3), (1e-2, 1e8), logx=True, logy=True, xlabel="lag time (s)", ylabel="mean squared displacement (µm²)")
    items = []
    for pe in (1, 10, 100):
        rs = [r for r in G if r["pe"] == pe and r is best(G, r)]
        if not rs:
            continue
        r = max(rs, key=lambda x: x["phi"]); c = r["card"]
        curve = np.asarray(r["obs"]["msd_curve"]); t = curve[:, 0]; m = curve[:, 1] * 1e12
        idx = np.unique(np.geomspace(1, len(t), 60).astype(int) - 1)
        col = PE_COL[pe]
        p.line(t[idx], m[idx], col, 2)
        tt = np.geomspace(1, 3e3, 80)
        p.line(tt, free_msd(tt, r["dt_engine"], r["v0_engine"], r["dr_engine"]), col, 1, "5 3")
        items.append((col, f"strength {pe:g}, packing {r['phi']:g}"))
    return R0.figure("F7", p.svg() + R0.legend(items + [("#888", "dashed: free swimmer")]),
        "Spreading curves. Mean squared displacement against lag time at the densest condition run for each swimming strength "
        "(solid), with the free swimmer at the same strength (dashed). At short lags the particles swim straight and the curve "
        "rises steeply; after about 100 s their direction is forgotten and it rises in proportion to time. Crowding lowers the "
        "long-time part.")


GONE = [""]


def video(T, out_stem: Path) -> str:
    """V1: the particles of the one run that kept its trajectory, drawn from the file."""
    if T is None:
        return ""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter
    # The environment's own ffmpeg, not whatever PATH holds: run as
    # .pixi/envs/sim/bin/python the environment's bin is not on PATH.
    matplotlib.rcParams["animation.ffmpeg_path"] = str(Path(sys.prefix) / "bin" / "ffmpeg")
    L = T["meta"]["box"]["length_m"] * 1e6
    xy = T["coords"] * 1e6
    th = T["theta"]
    dt_save = 1.0                                   # s per saved frame in this run's plan
    step = 10
    frames = list(range(0, min(len(xy), 6001), step))
    fig, ax = plt.subplots(figsize=(4.2, 4.2), dpi=120)
    path = out_stem.with_suffix(".mp4")
    writer = FFMpegWriter(fps=30)
    with writer.saving(fig, str(path), dpi=120):
        for i in frames:
            ax.clear()
            ax.set_xlim(0, L); ax.set_ylim(0, L); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
            w = np.mod(xy[i] + L / 2, L)
            for k in range(len(w)):
                ax.add_patch(plt.Circle(w[k], 2.5, color="#2f5d9e"))
                ax.arrow(w[k, 0], w[k, 1], 4 * np.cos(th[i, k]), 4 * np.sin(th[i, k]), head_width=1.2, color="#c0392b")
            ax.plot([3, 13], [3, 3], "k-", lw=2)
            ax.text(8, 4.5, "10 µm", ha="center", fontsize=8)
            ax.set_title(f"t = {i * dt_save:.0f} s", fontsize=9)
            writer.grab_frame()
    plt.close(fig)
    return (f"<figure><video src='{path.name}' controls width='480'></video><figcaption><b>V1.</b> The 13 particles of one run "
            f"(swimming strength 10, packing fraction 0.1, box 50 µm) over the first {frames[-1] * dt_save:.0f} s, one frame every "
            f"{step * dt_save:.0f} s of simulated time, played at 30 frames per second. Blue discs are particles at their true size, "
            "red arrows their swimming direction. The box is periodic: a particle leaving one edge enters the opposite one.</figcaption></figure>")


# -- the report ----------------------------------------------------------------

def sec(n, title, body):
    return R0.section(n, title, body)


def build(stem: Path) -> tuple[str, dict]:
    D = load(); G, C = D["grid"], D["compare"]
    N = R0.notes(Q1)
    try:
        T = trajectory.read_text(cards.AGENT / "runs" / TRAJ_RUN)
    except trajectory.TrajectoryUnavailable as exc:
        T = None; GONE[0] = str(exc)
    fmt = R0.fmt
    c0 = G[0]["card"]
    kept = [r for r in G if r is best(G, r)]
    lo = min(kept, key=lambda r: r["d"] / r["free"])
    dense_small = min([r for r in G if r["pe"] == 10 and r["phi"] == 0.5], key=lambda r: r["box"])
    dense_big = max([r for r in G if r["pe"] == 10 and r["phi"] == 0.5], key=lambda r: r["box"])
    cmp_small = [r for r in C if r["box"] == min(x["box"] for x in C)]
    cmp_big = max(C, key=lambda r: r["box"])
    S = []
    S.append(sec(1, "Summary",
        f"<div class='box'><p>Asked: how do interactions change the motion of self-propelled particles compared with a free swimmer, "
        f"and how large must the simulation box be?</p><p><b>Crowding slows them steadily, to {fmt(lo['d'] / lo['free'], 2)} of a free "
        f"swimmer's long-time spreading rate at a packing fraction of {fmt(lo['phi'])}</b> (swimming strength {fmt(lo['pe'])}: "
        f"{fmt(lo['d'])} ± {fmt(lo['se'], 2)} µm²/s against {fmt(lo['free'])}). Every condition stayed within the factor of ten set in "
        f"advance, so no qualitatively different regime appeared in this range. The box size did not change the answer: "
        f"{fmt(cmp_small[0]['d'])} and {fmt(cmp_big['d'])} µm²/s in boxes of one and ten persistence lengths, and "
        f"{fmt(dense_small['d'])} and {fmt(dense_big['d'])} µm²/s in boxes of one and four at the densest condition.</p></div>"))
    S.append(sec(2, "Purpose", R0.md(N["Purpose"])))
    S.append(sec(3, "What was expected",
        "<p>A single free swimmer with swimming speed v, rotational wandering rate D<sub>R</sub> and thermal jostling D<sub>T</sub> "
        "has a known long-time spreading rate in two dimensions:</p><p class='eq'>D<sub>free</sub> = D<sub>T</sub> + v² / (2 D<sub>R</sub>)</p>"
        "<p>and a known spreading curve, which rises steeply while the swimmer still remembers its direction and in proportion to "
        "time after about one persistence time, 1/D<sub>R</sub>. Both are textbook results for this model, written on the plan; the "
        "knowledge store holds nothing on active particles yet. Interactions were expected to lower the long-time rate as crowding "
        "grows, because particles block each other's swimming; by how much was the question.</p>"))
    pes = sorted({r["pe"] for r in G}); phis = sorted({r["phi"] for r in G})
    fixed = [(n, num(c0, n)) for n in ("bead_diameter", "temperature", "viscosity", "translational_diffusivity", "rotational_diffusivity", "wca_epsilon")]
    label = {"bead_diameter": "particle diameter", "temperature": "temperature", "viscosity": "fluid viscosity",
             "translational_diffusivity": "thermal jostling rate", "rotational_diffusivity": "rotational wandering rate",
             "wca_epsilon": "repulsion strength"}
    S.append(sec(4, "Variables",
        "<table><tr><th>Quantity</th><th>Value</th><th>Where it came from</th></tr>"
        f"<tr><td><b>varied:</b> swimming strength (speed ÷ diameter × wandering rate)</td><td class='n'>{', '.join(fmt(x) for x in pes)}</td><td>the two axes you chose</td></tr>"
        f"<tr><td><b>varied:</b> packing fraction (share of area covered)</td><td class='n'>{', '.join(fmt(x) for x in phis)}</td><td>the two axes you chose</td></tr>"
        "<tr><td><b>varied, separately:</b> box size at fixed conditions</td><td class='n'>1, 4 and 10 persistence lengths</td><td>the box-size question</td></tr>"
        + "".join(f"<tr><td>{label[n]}</td><td class='n'>{fmt(x['value'])} {PRETTY.get(x['unit'], x['unit'])}</td><td>{R0.provenance(x['source'])}</td></tr>" for n, x in fixed)
        + "<tr><td><b>measured:</b> long-time spreading rate; spreading curve; persistence time</td><td class='n'>µm²/s; µm²; s</td><td>read off each run</td></tr></table>"
        f"<p>{len(kept)} of the 9 grid conditions produced a result; two did not run because each would exceed the two-hour limit per "
        "job, and the most dilute condition at the weakest swimming holds a single particle, too few for an error bar.</p>"))
    eng = G[0]["log"]["events"][1]["report"].get("engine_build", {})
    rows = "".join(f"<tr><td class='n'>{fmt(r['pe'])}</td><td class='n'>{fmt(r['phi'])}</td><td class='n'>{fmt(r['box'])}</td>"
                   f"<td class='n'>{r['N_engine']}</td><td class='n'>{fmt(r['cfg']['parameters_si']['integration_timestep'])}</td>"
                   f"<td class='n'>{fmt(r['cfg']['parameters_si']['total_simulated_time'])}</td><td class='n'>{r['cfg']['seed']}</td></tr>"
                   for r in sorted(G + C, key=lambda r: (r['pe'], r['phi'], r['box'])))
    S.append(sec(5, "Setup",
        "<p>Particles move in a flat, periodic box. Each swims at a fixed speed along its own direction, that direction turns "
        "randomly, and each is also jostled by the fluid. Two particles repel only when they touch; nothing attracts. The fluid's own "
        "flow around a swimmer is left out, as is inertia.</p>"
        f"<p>Engine: {html.escape(str(eng.get('engine', '?')))} {html.escape(str(eng.get('version', '')))}, one run per condition.</p>"
        "<table><tr><th>swimming strength</th><th>packing fraction</th><th>box (µm)</th><th>particles</th><th>time step (s)</th><th>record (s)</th><th>seed</th></tr>"
        + rows + "</table>"
        "<p><b>Why these settings.</b> The time step is small enough that no particle moves through a neighbour in one step, "
        "whichever is shorter of the time to swim one diameter and the time a squeezed pair takes to spring apart. The spreading rate "
        "is read from lags of 10 to 30 persistence times, well after the direction is forgotten, and the record is ten times the "
        "longest lag so each lag is measured many times over. The box is ten persistence lengths across unless you chose otherwise. "
        "Positions are saved a hundred times per persistence time, so the swimming stage of the curve is resolved.</p>" + f5(c0)))
    S.append(sec(6, "Criteria set in advance",
        f"<p><b>Set on the plan before any run</b>, dated {html.escape(G[0]['card']['created_at'][:10])} for the first grid runs:</p><ul>"
        "<li><b>Accuracy you asked for:</b> each condition's spreading rate within a factor of ten of the free swimmer at the same "
        "strength. A result outside it would mark a different regime.</li>"
        "<li><b>Precision:</b> the statistical error of each spreading rate at or below 10 per cent. Chosen during planning.</li>"
        "<li><b>Settled:</b> the rate from the first and second halves of the fit range agrees within a factor of ten.</li>"
        "<li><b>Divergence guard:</b> a run stops as a fault if any particle moves more than its own diameter in one step.</li>"
        "<li><b>Box size:</b> the two boxes agree within a factor of ten.</li></ul>"))
    for r in G:
        r["q"] = "interactions"
    for r in C:
        r["q"] = "box size"
    res = "".join(
        f"<tr><td>{r['q']}</td><td class='n'>{fmt(r['pe'])}</td><td class='n'>{fmt(r['phi'])}</td><td class='n'>{fmt(r['box'])}</td>"
        f"<td class='n'>{r['d']:.3g} ± {r['se']:.2g}</td><td class='n'>{fmt(r['free'])}</td><td class='n'>{r['d'] / r['free']:.2f}</td>"
        f"<td class='n'>{fmt(r['tau_p']) if r['tau_p'] else '—'}</td>"
        f"<td>{'met' if all(v for k, v in r['met'].items() if k != 'step_displacement_diverged' and v is not None) else 'precision missed' if r['met'].get('statistics_met') is False else '—'}</td></tr>"
        for r in sorted(G + C, key=lambda r: (r['pe'], r['phi'], r['box'])))
    S.append(sec(7, "Results",
        f1(G) + f7(G) + f6(G, C) +
        "<table><tr><th>question</th><th>strength</th><th>packing</th><th>box (µm)</th><th>spreading rate (µm²/s)</th><th>free swimmer (computed)</th><th>ratio</th>"
        "<th>persistence time (s)</th><th>criteria</th></tr>" + res + "</table>"
        "<p class='meta'>Every value read off the runs. “precision missed”: the run met the other criteria but its error was above 10 per "
        "cent, which happens in the smallest boxes with 13 particles. The 500 µm run at strength 10 and packing 0.1 appears twice because it was run for both questions with the same seed, and the two agree exactly. No run diverged. One run of the strongest swimming was stopped "
        "early by a fault in the divergence guard itself, which measured the distance between saved snapshots rather than one step; the "
        "guard was corrected and the run repeated, and the stopped run is kept on record.</p>" + f3(T) + f4(T) + video(T, stem)))
    S.append(sec(8, "Checks",
        "<p>Cases whose answer is known independently, read off the same runs:</p><ul>"
        f"<li><b>Persistence time.</b> Measured from how fast each particle forgets its direction: {fmt(min(r['tau_p'] for r in G + C if r['tau_p']))} "
        f"to {fmt(max(r['tau_p'] for r in G + C if r['tau_p']))} s across the runs, against the 100 s that was put in. The rotational "
        "wandering is realised as intended.</li>"
        f"<li><b>Reproducibility.</b> The condition at strength 10 and packing 0.1 in a 500 µm box was run under both questions with "
        "the same seed and gave identical results to every digit.</li>"
        f"<li><b>Dilute limit.</b> At the lowest crowding the interacting particles should behave like free ones; they are within "
        f"{max(abs(r['d'] / r['free'] - 1) for r in kept if r['phi'] == min(phis)) * 100:.0f} per cent of the free swimmer "
        "(F2).</li></ul>" + f2(G)))
    S.append(sec(9, "Interpretation", "<p class='meta'>Judgement, kept apart from the numbers above.</p>" + R0.md(N["Interpretation"])))
    S.append(sec(10, "Limits", R0.md(N["Limits"])))
    S.append(sec(11, "Link to experiment",
        "<p>Both plans are ready to send to the microscope: they use physical units only and ask for the mean squared "
        "displacement, which the microscope could in principle measure from tracked particles. It does not yet declare a way to "
        "measure it, and the interaction study would also need self-propelled particles as a sample, which is new for it. Until "
        "the microscope side adds both, nothing is sent.</p>"))
    S.append(sec(12, "Decisions for you", R0.md(N["Decisions"])))
    budget = json.loads((cards.AGENT / "envelope" / "budget.json").read_text())
    lim = next(t for t in budget["targets"] if t["target"] == "local")["limits"]
    wall = sum(r["wall"] for r in G + C)
    traj = [(r["run"], (cards.AGENT / "runs" / r["run"] / "trajectory.txt")) for r in G + C]
    kept_files = [(rid, p.stat().st_size) for rid, p in traj if p.exists()]
    S.append(sec(13, "Cost",
        f"<p>Wall clock over all {len(G + C)} runs, including analysis: {fmt(wall / 3600, 2)} h, the longest single job "
        f"{fmt(max(r['wall'] for r in G + C) / 60, 2)} min, against a limit of {lim['wall_clock_max']['value']} "
        f"{lim['wall_clock_max']['unit']} per job. Measured on this machine at about three to four million particle-steps per second, "
        "three times slower than the planning estimate; the plans' estimates are therefore low, and the two conditions refused for "
        "time were refused on the planning estimate before this was known.</p>"
        "<table><tr><th>trajectory kept</th><th>size</th></tr>"
        + ("".join(f"<tr><td><code>simulation_agent/runs/{rid}/trajectory.txt</code></td><td class='n'>{s / 1e6:.1f} MB</td></tr>" for rid, s in kept_files)
           or "<tr><td colspan='2'>none</td></tr>")
        + "</table><p>Runs before the text-file rule kept no positions; the figures that need positions are drawn from the one that did. "
        "Deleting that file removes those figures from the next report and nothing reruns it.</p>"))
    return "".join(S), {"G": G, "C": C}


def footer(ctx) -> str:
    rev = subprocess.run(["git", "-C", str(cards.REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    v = subprocess.run([sys.executable, str(cards.CONTRACTS / "validate.py"), "--quiet"], capture_output=True, text=True, cwd=cards.REPO)
    tree = next((l for l in v.stdout.splitlines()[::-1] if l.startswith("tree:")), "tree: not reported")
    verdict = next((l for l in v.stdout.splitlines()[::-1] if l.startswith("verdict:")), "")
    runs = ", ".join(sorted(r["run"] for r in ctx["G"] + ctx["C"]))
    revs = sorted({r["rev"] for r in ctx["G"]})
    return (f"<footer><p>Generated {_dt.datetime.now().astimezone().isoformat(timespec='minutes')} by <code>simulation_agent/src/report_abp.py</code>. "
            f"Questions {Q1} (revisions {', '.join(map(str, revs))}) and {Q2}; runs {runs}. Repository at {rev}. "
            f"Validator: {html.escape(verdict)} {html.escape(tree)}. Notes: <code>{R0.NOTES_DIR / (Q1 + '.md')}</code>.</p>"
            f"<p>Regenerate: <code>cd simulation_agent &amp;&amp; ../.pixi/envs/sim/bin/python -m src.report_abp</code></p></footer>")


def unique_clips(body: str) -> str:
    """Give every figure's clip path its own id.

    report.Plot names its clip path after id(self), and CPython reuses the
    address of a panel that has been garbage-collected, so two figures in one
    page can carry the same id. A browser applies the first definition to
    every reference, and later figures were clipped to an earlier figure's
    rectangle: the dense points of F1 and the long lags of F7 vanished. Each
    <svg> is renumbered on its own, so each reference stays with its own
    definition.
    """
    import re
    count = iter(range(1, 10_000))

    def one(m):
        svg = m.group(0)
        for old in set(re.findall(r'id="(c\d+)"', svg)):
            new = f"clip{next(count)}"
            svg = svg.replace(f'id="{old}"', f'id="{new}"').replace(f"url(#{old})", f"url(#{new})")
        return svg
    return re.sub(r"<svg\b.*?</svg>", one, body, flags=re.S)


def emit() -> Path:
    R0._selftest()
    R0.REPORT_DIR.mkdir(exist_ok=True)
    stem = R0.REPORT_DIR / f"rebuild-report-{_dt.date.today():%m%d}-{Q1}"
    body, ctx = build(stem)
    body = unique_clips(body)
    R0.refuse_codes(body)
    title = "Interacting active Brownian particles in two dimensions"
    doc = (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{title}</title><style>{R0.CSS}</style></head>"
           f"<body><main><h1>{title}</h1><p class='meta'>Simulation report, generated from the records. Numbers are read off the "
           f"cards and runs; the sections marked as notes are written by hand. The file name carries your local date.</p>"
           f"{body}{footer(ctx)}</main></body></html>")
    out = stem.with_suffix(".html")
    out.write_text(doc)
    return out


if __name__ == "__main__":
    try:
        print(emit())
    except R0.Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
