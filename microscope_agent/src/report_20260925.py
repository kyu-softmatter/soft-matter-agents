"""Generate the person's report on the 2026-09-25 trap-strength measurements, from the analysis files.

    python src/report_20260925.py <rec_dir> <out_html>

The simulation side's report shape (its task 022): summary, purpose, what was
expected, variables, setup, criteria set in advance, results with figures,
interpretation, limits, decisions for the person. Every number is read from
the <label>_analysis.json files the analysis wrote; only the prose is written
here. Nothing is re-run.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import glob                                                      # noqa: E402
import html                                                      # noqa: E402
import json                                                      # noqa: E402
import re                                                        # noqa: E402
from pathlib import Path                                         # noqa: E402

import numpy as np                                               # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
RAMP = ["#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
        "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]


def load(rec: Path, prefix: str) -> list[dict]:
    rows = []
    for f in glob.glob(str(rec / f"{prefix}*_analysis.json")):
        m = re.search(rf"{re.escape(prefix)}([0-9.]+)_analysis", f)
        if not m:
            continue
        a = json.load(open(f))
        a["s"] = float(m.group(1))
        a["xy"] = np.load(str(rec / f"{a['label']}_xy_um.npy"))
        rows.append(a)
    return sorted(rows, key=lambda a: a["s"])


def axes(W, H, L, R, T, B, xlab, ylab, xt, yt, X, Y):
    pw, ph = W - L - R, H - T - B
    o = []
    for v in yt:
        o.append(f'<line x1="{L}" x2="{L+pw}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="g"/>'
                 f'<text x="{L-6}" y="{Y(v)+4:.1f}" class="a" text-anchor="end">{v:g}</text>')
    for v in xt:
        o.append(f'<text x="{X(v):.1f}" y="{T+ph+16}" class="a" text-anchor="middle">{v:g}</text>')
    o.append(f'<text x="{L+pw/2}" y="{H-8}" class="a" text-anchor="middle">{xlab}</text>'
             f'<text transform="translate(14,{T+ph/2}) rotate(-90)" class="a" text-anchor="middle">{ylab}</text>')
    return o


def line_chart(title, ylab, series, ymin, ymax, yt):
    W, H, L, R, T, B = 470, 300, 58, 130, 30, 44
    pw, ph = W - L - R, H - T - B
    X = lambda s: L + s * pw
    Y = lambda v: T + ph - (v - ymin) / (ymax - ymin) * ph
    o = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{html.escape(title)}">',
         f'<text x="{L}" y="18" class="t">{html.escape(title)}</text>']
    o += axes(W, H, L, R, T, B, "trap_2 strength (trap_1 = 1)", ylab, [0, .2, .4, .6, .8, 1], yt, X, Y)
    for name, pts, color in series:
        o.append(f'<polyline points="{" ".join(f"{X(s):.1f},{Y(v):.1f}" for s, v in pts)}" fill="none" '
                 f'stroke="{color}" stroke-width="2"/>')
        for s, v in pts:
            o.append(f'<circle cx="{X(s):.1f}" cy="{Y(v):.1f}" r="4.5" fill="{color}" stroke="var(--surface)" '
                     f'stroke-width="2"><title>{html.escape(name)}, 1/{s:g}: {v:.3g}</title></circle>')
        s, v = pts[-1]
        o.append(f'<text x="{X(s)+10:.1f}" y="{Y(v)+4:.1f}" class="lab">{html.escape(name)}</text>')
    o.append("</svg>")
    return "".join(o)


def overlay(title, rows, ref):
    W, H, L, R, T, B = 940, 380, 64, 170, 30, 44
    pw, ph = W - L - R, H - T - B
    lo, hi = -400, 1400
    X = lambda t: L + t / 180 * pw
    Y = lambda v: T + ph - (v - lo) / (hi - lo) * ph
    o = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{html.escape(title)}">',
         f'<text x="{L}" y="18" class="t">{html.escape(title)}</text>']
    o += axes(W, H, L, R, T, B, "time (s)", "x from the 1/0 mean (nm)", range(0, 181, 30),
              range(-400, 1401, 200), X, Y)
    for k, a in enumerate(rows):
        c = a.get("color") or RAMP[round(k * (len(RAMP) - 1) / max(len(rows) - 1, 1))]
        x = (a["xy"][0] - ref) * 1000
        t = np.arange(len(x)) * a["frame_interval_s"]
        pts = " ".join(f"{X(u):.1f},{Y(v):.1f}" for u, v in zip(t[::5], x[::5]) if np.isfinite(v))
        o.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="1"><title>'
                 f'{html.escape(a["name"])}: mean {np.nanmean(x):.0f} nm</title></polyline>')
        ly = T + 12 + k * 16
        o.append(f'<line x1="{L+pw+12}" x2="{L+pw+32}" y1="{ly-4}" y2="{ly-4}" stroke="{c}" stroke-width="3"/>'
                 f'<text x="{L+pw+38}" y="{ly}" class="lab">{html.escape(a["name"])} ({np.nanmean(x):.0f} nm)</text>')
    o.append("</svg>")
    return "".join(o)


def main(rec_dir: str, out_html: str) -> int:
    rec = Path(rec_dir)
    first, five = load(rec, "strength_1_"), load(rec, "sep5_strength_1_")
    final = load(rec, "final_hand_2p5um_1_")
    ref = next(a for a in first if a["s"] == 0.0)
    ref_x = float(np.nanmean(ref["xy"][0]))
    shift = lambda a: (float(np.nanmean(a["xy"][0])) - ref_x) * 1000
    exc = lambda a: float(np.nanmax(np.abs(a["xy"][0] - np.nanmean(a["xy"][0])))) * 1000

    fig1 = line_chart("Bead pulled toward trap_2", "shift from 1/0 (nm)",
                      [("first position", [(a["s"], shift(a)) for a in first], BLUE),
                       ("5 um", [(0.0, 0.0)] + [(a["s"], shift(a)) for a in five], ORANGE)],
                      -200, 1200, range(-200, 1201, 200))
    fig2 = line_chart("Stiffness along the trap axis (power spectrum)", "k (pN/um)",
                      [("first position", [(a["s"], a["psd_x"]["k_psd_pN_per_um"]) for a in first], BLUE),
                       ("5 um", [(0.0, ref["psd_x"]["k_psd_pN_per_um"])] +
                        [(a["s"], a["psd_x"]["k_psd_pN_per_um"]) for a in five], ORANGE)],
                      0, 8, range(0, 9, 2))
    for a in first:
        a["name"] = f"first, 1/{a['s']:g}"
    for a in five:
        a["name"] = f"5 um, 1/{a['s']:g}"
    fig3 = overlay("x(t), first position, trap_2 from 0 (light) to 1 (dark)", first, ref_x)
    fig4 = overlay("x(t), trap_2 at 5 um", [ref] + five, ref_x)
    finals = ""
    raw_final = rec / "final_hand_2p5um_1_0.5.raw"
    if not final and raw_final.exists():
        # Recorded and not analysable: no bead in the frame. Said with the numbers
        # that show it, rather than dropped.
        st = np.memmap(raw_final, dtype=np.uint16, mode="r")
        n = st.size // (256 * 256)
        st = st[: n * 256 * 256].reshape(n, 256, 256)
        samp = st[:: max(1, n // 50)].astype(float)
        med, top = float(np.median(samp)), float(samp.max())
        refst = np.memmap(rec / "strength_1_0.0.raw", dtype=np.uint16, mode="r").reshape(-1, 256, 256)
        rmed, rtop = float(np.median(refst[::120].astype(float))), float(refst[::120].max())
        finals = (f"<h3>Final setting, set by hand: trap_2 at 2.5 um, 1/0.5</h3>"
                  f"<p><b>No bead in the recording.</b> {n} frames (3 min) were taken as before, but no frame holds a "
                  f"bright spot: brightest pixel {top:.0f} counts over a background of {med:.0f}, against "
                  f"{rtop:.0f} over {rmed:.0f} with the bead at 1/0. The field is also about a quarter as bright, "
                  f"although the Aura was set and read back exactly as before, so something besides the traps "
                  f"changed when they were set by hand -- the light path, a filter, or the bead leaving. Nothing "
                  f"can be said about hopping at 2.5 um from this record.</p>")
    if final:
        f = final[0]
        f["name"], f["color"] = "2.5 um, 1/0.5 (set by hand)", AQUA
        ref["name"], ref["color"] = "1/0 reference", RAMP[1]
        fig5 = overlay("x(t), final setting set by hand: trap_2 at 2.5 um, 1/0.5", [ref, f], ref_x)
        ms = f["milestoning_x"]
        finals = (f"<h3>Final setting, set by hand in the tweezers software</h3>{fig5}"
                  f"<p>Shift from 1/0: <b>{shift(f):.0f} nm</b>; spread {f['std_um'][0]*1000:.0f} nm along x; "
                  f"farthest excursion {exc(f):.0f} nm; wells found: <b>{ms['basins']}</b>"
                  + (f"; occupancy {ms['occupancy_well_1']:.2f} / {ms['occupancy_well_2']:.2f}, "
                     f"{ms['transitions_1_to_2']} + {ms['transitions_2_to_1']} crossings" if ms["basins"] == 2 else "")
                  + ".</p>")

    def table(rows, label):
        return "".join(
            f"<tr><td>{label}</td><td>1/{a['s']:g}</td><td>{shift(a):.0f}</td><td>{a['std_um'][0]*1000:.0f}</td>"
            f"<td>{a['std_um'][1]*1000:.0f}</td><td>{exc(a):.0f}</td><td>{a['psd_x']['k_psd_pN_per_um']:.2f}</td>"
            f"<td>{a['psd_x']['k_equipartition_pN_per_um']:.2f}</td><td>{a['psd_x']['D_um2_per_s']:.3f}</td>"
            f"<td>{a['lost_frames']}</td><td>{a['milestoning_x']['basins']}</td></tr>" for a in rows)

    hops_any = any(a["milestoning_x"]["basins"] == 2 for a in first + five + final)
    body = f"""
<h1>Two optical traps, one bead: strength scans, 2026-09-25</h1>
<p class="meta">Microscope agent, session microscope-20260924-6. Preparatory record: the tweezers commands ran
through approved plans, but the recordings and this analysis are not a planned measurement, so no number here goes
to the knowledge store or the simulation as a result yet.</p>

<h2>1. Summary</h2>
<p>One 5 um bead was held in trap_1 (strength 1) while trap_2's strength was raised from 0 to 1 at two positions,
3 minutes of video per setting. <b>{"The bead hopped in at least one setting." if hops_any else "The bead never hopped between the traps in any setting."}</b>
At the first position trap_2 pulled the bead steadily toward itself, about {shift(first[-1]):.0f} nm at 1/1;
at 5 um it pulled nothing measurable. Trap_1 alone holds the bead at about
{ref['psd_x']['k_psd_pN_per_um']:.1f} pN/um along the trap axis.</p>
{fig1}

<h2>2. Purpose</h2>
<p>The first experimental side of the simulation comparison: one bead in two traps, asking whether and where it
hops as the second trap is strengthened. Today's question was narrower: how far does trap_2 reach the bead at a given
separation and strength, and is there a setting where hopping starts.</p>

<h2>3. What was expected</h2>
<p>The simulation (its ask of 2026-09-24) predicted wells hundreds of k_BT deep for a 5 um bead, so that hops need
nearly equal strengths and a separation close to where the two wells merge; at a strength ratio of 0.5 or below it
expected no hops at any separation. Tens of hops per hour need a barrier of 1 to 4 k_BT.</p>

<h2>4. Variables</h2>
<table><tr><th>varied</th><td>trap_2 strength: 0 to 1 in 0.1 at the first position; 0.2 to 1 in 0.2 at 5 um; a final hand-set 0.5 at 2.5 um</td></tr>
<tr><th>held fixed</th><td>trap_1 at the image centre, strength 1; laser dial 0.02 (your setting, not read by software); 100x oil, 1x;
Aura green 5%; 30 ms exposure and frame interval; 256 x 256 px crop</td></tr>
<tr><th>measured</th><td>bead position every frame (6000 frames = 3 min per setting)</td></tr></table>

<h2>5. Setup</h2>
<p>Traps commanded over the network to the tweezers software from approved plans, every command logged; the software
confirms receipt only, never position. Camera driven through Micro-Manager. Positions from an intensity-weighted
centroid; scale 0.065 um per pixel (measured). Temperature taken as the room's 20 C (a reading, not the sample's).
The first position was commanded as +6 um from trap_1; see section 9 on whether it was there.</p>

<h2>6. Criteria set in advance</h2>
<p>The analysis method was committed before any data existed (this morning): stiffness by power spectrum with the
variance method beside it, never averaged, and reported as undetermined if they differ by more than 2x; wells by the
simulation's milestone rule (cores 0.2 of the peak spacing). Accuracy wanted: within a decade (your choice).</p>

<h2>7. Results</h2>
{fig2}
{fig3}
{fig4}
{finals}
<table><tr><th>set</th><th>trap_1/trap_2</th><th>shift (nm)</th><th>std x (nm)</th><th>std y (nm)</th>
<th>max excursion (nm)</th><th>k spectrum</th><th>k variance</th><th>D (um2/s)</th><th>lost frames</th><th>wells</th></tr>
{table(first, "first position")}{table(five, "5 um")}{table(final, "2.5 um, hand")}</table>
<p class="meta">k in pN/um along the trap axis. Every recording: 6000 frames, 30.0 ms apart by the camera's clock,
no gaps.</p>

<h2>8. Interpretation</h2>
<p>With trap_2 at 5 um the bead does not feel it: its position, spread and stiffness match trap_1 alone at every
strength. At the first position trap_2 reaches the bead: the bead moves toward it and is held more stiffly along the
axis as trap_2 grows, which is what a second well overlapping the first does. But no strength reached a second well
the bead could sit in, so the barrier between them stayed far above a few k_BT.</p>

<h2>9. Limits</h2>
<ul>
<li><b>The separations are uncertain.</b> A trap commanded to +6 um pulled strongly and one commanded to +5 um did
not pull at all, which is backwards. The first trap_2 was most likely much closer than +6 um. Nothing here can see the
traps themselves; the tweezers report nothing back.</li>
<li>Stiffness is at the frame rate's limit: the bead relaxes in about 30 ms, one frame. The two methods differ by up
to {max(a['psd_x']['k_equipartition_pN_per_um']/a['psd_x']['k_psd_pN_per_um'] for a in first+five):.1f}x.
Faster frames (a smaller crop, shorter exposure) would settle it.</li>
<li>The power delivered at dial 0.02, and how the software splits it between two traps, are not measured.</li>
<li>Preparatory: recordings were not part of an approved measurement plan.</li></ul>

<h2>10. Decisions for you</h2>
<ul>
<li>Where the traps really are: an image of both traps (e.g. brightfield, or the laser spot on the camera) at the
positions used, so separations become measured numbers.</li>
<li>Whether to go closer than the first position, where hopping, if any, must lie.</li>
<li>Whether to record faster (e.g. 5 ms frames on a smaller crop) to pin the stiffness.</li>
<li>Whether these numbers go to the simulation as a first ask, once the separation is known.</li></ul>
<p class="meta">Files: videos and per-recording analysis in {html.escape(str(rec))}.</p>
"""
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Two traps, one bead, 2026-09-25</title>
<style>:root{{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e6e5e0}}
@media (prefers-color-scheme:dark){{:root{{--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#34332f}}}}
body{{background:var(--surface);color:var(--ink);font:14px/1.5 system-ui,sans-serif;margin:24px auto;max-width:980px}}
.t{{font-weight:600;fill:var(--ink);font-size:13px}} .a{{fill:var(--ink2);font-size:11px}}
.lab{{fill:var(--ink);font-size:11px}} .g{{stroke:var(--grid)}} .meta{{color:var(--ink2)}}
table{{border-collapse:collapse;margin:12px 0}} td,th{{padding:4px 8px;border-bottom:1px solid var(--grid);text-align:right}}
th{{text-align:left}} svg{{margin:6px 8px 6px 0}}</style></head><body>{body}</body></html>"""
    Path(out_html).write_text(page, encoding="utf-8")
    print(out_html)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
