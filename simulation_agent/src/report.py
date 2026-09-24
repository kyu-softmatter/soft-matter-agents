"""A report for the person, generated from the records (task 022).

`python -m src.report <qid>` reads the question folder, the result cards of its
latest revision and the runs they name, and writes one HTML file to
`~/Desktop/report/`. It re-runs nothing: every figure is drawn from files on
disk, and a trajectory that is gone is named with what regenerating it would
take instead of being regenerated.

Numbers come from the cards and run files. The seat writes by hand only what no
card holds -- purpose in plain words, interpretation, limits, decisions -- in
`~/Desktop/report/notes/<qid>.md`, under `## ` headings of those names. A
missing notes file leaves those sections saying they are empty.

Figures are SVG written here rather than drawn with a plotting library, which
this environment does not have. That keeps the report one self-contained file
and costs nothing a later plotting library would have to undo.

The body is refused, exit 2, when it carries an internal code: the person reads
this without plan.md beside it. Only the footer may carry references.
"""

from __future__ import annotations

import datetime as _dt
import html
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from . import cards, trajectory

REPORT_DIR = Path.home() / "Desktop" / "report"
NOTES_DIR = REPORT_DIR / "notes"
HAND = ("Purpose", "Criteria", "Interpretation", "Limits", "Decisions")


class Refused(Exception):
    pass


# -- plain language ------------------------------------------------------------

# What the body may not carry. Each pattern was tried against physics notation
# (2D, D_R, 1E6, P = 0.5, k_B, E_b) before it went in; see `_selftest`.
CODE_PATTERNS = [
    (r"§\s*\d", "a section sign"),
    (r"\b(?:check|rule|principle|decision|section|tier|milestone)s?\s+\d+", "a numbered rule or check"),
    (r"\b[PD]\d{1,2}\b", "a principle or decision code"),
    (r"\bA[1-7]\b", "an axis code"),
    (r"\bS[2-6](?:\.\d)?\b", "a stage code"),
    (r"\bE[1-6]\b", "a grade code"),
    (r"\bM[0-5]\b", "a milestone code"),
    (r"\bkb:", "a store entry id"),
    (r"\bseat:|\b(?:simulation|microscope|librarian|bridge|manager|architecture)-\d+\b", "a seat name"),
    (r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b", "a commit hash"),
]


def refuse_codes(body_html: str) -> None:
    body_html = re.sub(r"<footer\b.*?</footer>", " ", body_html, flags=re.S)
    body_html = re.sub(r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+", " ", body_html)
    body_html = re.sub(r"<(svg|style|script)\b.*?</\1>", " ", body_html, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body_html))
    for pat, what in CODE_PATTERNS:
        m = re.search(pat, text, flags=re.I if "check" in pat else 0)
        if m:
            ctx = text[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
            raise Refused(f"the body carries {what}: {m.group(0)!r} in ...{ctx}...")


def _selftest() -> None:
    for ok in ("a 2D box", "rotational D_R", "1E6 steps", "P = 0.5", "k_B T", "E_b over k_B T",
               '<img src="data:image/png;base64,iVBORA5E4xx==">', "<footer>commit c2431d4, check 45</footer>"):
        refuse_codes(ok)
    for bad in ("check 45", "§4.3", "grade E3", "axis A5", "kb:water", "seat:simulation-8", "commit c2431d4"):
        try:
            refuse_codes(bad)
        except Refused:
            continue
        raise AssertionError(f"{bad!r} passed the code filter")


def provenance(source: str) -> str:
    kind, _, rest = source.partition(":")
    return {
        "simulated": "read off the run",
        "measured": "measured on this machine",
        "computed": "computed from the other inputs",
        "assumed": "assumed",
        "kb": "from the knowledge store",
        "spec": "from a specification",
        "operator_read": "read by the operator",
    }.get(kind, "source not stated")


UNWORDED: list[str] = []  # reasons that carried a code, sent to the footer verbatim


def worded(text: str, what: str = "This text") -> str:
    """Card prose shown verbatim when it is written for the person, else a placeholder; the original goes to the footer."""
    try:
        refuse_codes(text)
        return html.escape(text)
    except Refused:
        UNWORDED.append(text)
        return f"<i>{what} is not worded for you yet; the original is in the footer.</i>"


def plain_skip(reason: str) -> str:
    """A skip reason as written, if it is written for the person; otherwise a placeholder that says so.

    The rule is the writer's: a reason meant for the person carries no code. The generator does not
    paraphrase a reason it cannot read -- it says the reason is not worded yet and puts the original
    in the footer, so the gap is visible rather than smoothed into "not run".
    """
    try:
        refuse_codes(reason)
        return "not run: " + reason
    except Refused:
        UNWORDED.append(reason)
        return "not run — the reason is not worded for you yet"


def fmt(x: float, sig: int = 3) -> str:
    if x == 0 or not math.isfinite(x):
        return str(x)
    s = f"{x:.{sig}g}"
    if "e" in s:
        m, e = s.split("e")
        return f"{m}×10<sup>{int(e)}</sup>"
    return s


# -- figures (SVG) -------------------------------------------------------------

COLORS = ["#2f5d9e", "#c0392b", "#1f7a4d", "#9a5b00", "#6c3483"]


class Plot:
    """A minimal x-y panel: log or linear axes, points with error bars, lines, bands."""

    def __init__(self, xr, yr, *, logx=False, logy=False, w=560, h=320, xlabel="", ylabel=""):
        self.logx, self.logy, self.w, self.h = logx, logy, w, h
        self.m = (62, 16, 20, 46)  # left, right, top, bottom
        self.xr = [math.log10(v) for v in xr] if logx else list(xr)
        self.yr = [math.log10(v) for v in yr] if logy else list(yr)
        self.xlabel, self.ylabel, self.parts = xlabel, ylabel, []

    def X(self, x):
        x = math.log10(x) if self.logx else x
        l, r = self.m[0], self.w - self.m[1]
        return l + (x - self.xr[0]) / (self.xr[1] - self.xr[0]) * (r - l)

    def Y(self, y):
        y = math.log10(y) if self.logy else y
        t, b = self.m[2], self.h - self.m[3]
        return b - (y - self.yr[0]) / (self.yr[1] - self.yr[0]) * (b - t)

    def band(self, y0, y1, color="#e5f2ea"):
        x0, x1 = self.m[0], self.w - self.m[1]
        self.parts.append(f'<rect x="{x0}" y="{self.Y(y1):.1f}" width="{x1 - x0}" height="{self.Y(y0) - self.Y(y1):.1f}" fill="{color}"/>')

    def hline(self, y, color="#888", dash="4 3"):
        self.parts.append(f'<line x1="{self.m[0]}" x2="{self.w - self.m[1]}" y1="{self.Y(y):.1f}" y2="{self.Y(y):.1f}" stroke="{color}" stroke-dasharray="{dash}"/>')

    def line(self, xs, ys, color="#333", width=1.2, dash=None):
        pts = " ".join(f"{self.X(x):.1f},{self.Y(y):.1f}" for x, y in zip(xs, ys))
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"{d}/>')

    def point(self, x, y, err=None, color="#333", r=4):
        if err:
            self.parts.append(f'<line x1="{self.X(x):.1f}" x2="{self.X(x):.1f}" y1="{self.Y(y - err):.1f}" y2="{self.Y(y + err):.1f}" stroke="{color}"/>')
        self.parts.append(f'<circle cx="{self.X(x):.1f}" cy="{self.Y(y):.1f}" r="{r}" fill="{color}"/>')

    def bars(self, edges, counts, color="#9fb6d8"):
        for a, b, c in zip(edges[:-1], edges[1:], counts):
            self.parts.append(f'<rect x="{self.X(a):.1f}" y="{self.Y(c):.1f}" width="{max(self.X(b) - self.X(a) - 0.5, 0.5):.1f}" height="{self.Y(0) - self.Y(c):.1f}" fill="{color}"/>')

    def text(self, x, y, s, color="#333", anchor="start"):
        self.parts.append(f'<text x="{self.X(x):.1f}" y="{self.Y(y):.1f}" font-size="11" fill="{color}" text-anchor="{anchor}">{s}</text>')

    def _ticks(self, lo, hi, log):
        if log:
            return [(v, f"10<tspan dy='-5' font-size='8'>{v}</tspan>") for v in range(math.ceil(lo), math.floor(hi) + 1)]
        step = 10 ** math.floor(math.log10((hi - lo) / 4))
        for m in (1, 2, 5, 10):
            if (hi - lo) / (step * m) <= 6:
                step *= m
                break
        v, out = math.ceil(lo / step) * step, []
        while v <= hi + 1e-12:
            out.append((v, f"{v:.6g}"))
            v += step
        return out

    def svg(self) -> str:
        l, r, t, b = self.m[0], self.w - self.m[1], self.m[2], self.h - self.m[3]
        ax = [f'<rect x="{l}" y="{t}" width="{r - l}" height="{b - t}" fill="none" stroke="#999"/>']
        for v, lab in self._ticks(*self.xr, self.logx):
            x = self.X(10 ** v if self.logx else v)
            ax.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{b}" y2="{b + 4}" stroke="#999"/><text x="{x:.1f}" y="{b + 16}" font-size="11" text-anchor="middle">{lab}</text>')
        for v, lab in self._ticks(*self.yr, self.logy):
            y = self.Y(10 ** v if self.logy else v)
            ax.append(f'<line x1="{l - 4}" x2="{l}" y1="{y:.1f}" y2="{y:.1f}" stroke="#999"/><text x="{l - 7}" y="{y + 4:.1f}" font-size="11" text-anchor="end">{lab}</text>')
        ax.append(f'<text x="{(l + r) / 2}" y="{self.h - 8}" font-size="12" text-anchor="middle">{self.xlabel}</text>')
        ax.append(f'<text x="14" y="{(t + b) / 2}" font-size="12" text-anchor="middle" transform="rotate(-90 14 {(t + b) / 2})">{self.ylabel}</text>')
        clip = f'<clipPath id="c{id(self)}"><rect x="{l}" y="{t}" width="{r - l}" height="{b - t}"/></clipPath>'
        body = f'<g clip-path="url(#c{id(self)})">' + "".join(self.parts) + "</g>"
        return (f'<svg viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" xmlns="http://www.w3.org/2000/svg" '
                f'font-family="Helvetica, Arial, sans-serif">{clip}' + body + "".join(ax) + "</svg>")


def legend(items) -> str:
    return "<p class='legend'>" + " ".join(
        f"<span><i style='background:{c}'></i>{html.escape(s)}</span>" for c, s in items) + "</p>"


def figure(tag: str, svg: str, caption: str) -> str:
    return f"<figure><div class='fig'>{svg}</div><figcaption><b>{tag}.</b> {caption}</figcaption></figure>"


# -- records -------------------------------------------------------------------

def load(qid: str) -> dict:
    qdir = cards.question_dir(qid)
    rev = cards.question_revision(qid)
    goal = cards.load_goal(qid, rev)
    plan_path = qdir / cards.artifact_name(f"plan_simulation_{qid}.json", rev)
    if not plan_path.exists():
        raise Refused(f"revision {rev} has no plan yet; there is nothing to report")
    plan = json.loads(plan_path.read_text())
    syn_path = qdir / cards.artifact_name("synthesis.json", rev)
    syn = json.loads(syn_path.read_text()) if syn_path.exists() else {}
    results = []
    for p in sorted(qdir.glob("result_run-*.json")):
        c = json.loads(p.read_text())
        if c.get("plan_id") == plan["id"]:
            run_dir = cards.AGENT / "runs" / c["run_id"]
            obs = json.loads((run_dir / "observables.json").read_text())
            log = json.loads((run_dir / "log.json").read_text())
            results.append({"card": c, "path": p, "run_dir": run_dir, "obs": obs, "log": log})
    if not results:
        raise Refused(f"revision {rev} has a plan and no result cards; nothing ran to report on")
    return {"qid": qid, "rev": rev, "goal": goal, "plan": plan, "plan_path": plan_path, "syn": syn,
            "results": results}


def num(card: dict, name: str) -> dict | None:
    return next((n for n in card.get("numbers", []) if n["name"] == name), None)


def notes(qid: str) -> dict[str, str]:
    path = NOTES_DIR / f"{qid}.md"
    out = {h: "" for h in HAND}
    if not path.exists():
        return out
    cur = None
    for line in path.read_text().splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            cur = m.group(1).strip() if m.group(1).strip() in out else None
            continue
        if cur:
            out[cur] += line + "\n"
    return out


def md(text: str) -> str:
    """Enough Markdown for notes: paragraphs, '- ' bullets, **bold**, *italic*."""
    if not text.strip():
        return "<p class='empty'>Not written yet: the notes file has nothing under this heading.</p>"
    out, items = [], []
    def inline(s):
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        return re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.splitlines()
        if all(l.startswith("- ") for l in lines):
            out.append("<ul>" + "".join(f"<li>{inline(l[2:])}</li>" for l in lines) + "</ul>")
        else:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "".join(out)


# -- per-configuration parts ---------------------------------------------------

K_B = 1.380649e-23


def trap_cells(R: dict) -> list[dict]:
    """One row per kept grid cell, every value read from its result card and run files."""
    rows = []
    for r in R["results"]:
        c, o = r["card"], r["obs"]
        cell = next(n["name"] for n in c["numbers"] if n["name"].startswith("flow_speed_")).removeprefix("flow_speed_")
        k = cell.split("_")[0]
        d = o["drag_offset"]; s = o["recovered_stiffness"]
        rows.append({
            "cell": cell, "run_id": c["run_id"], "r": r,
            "k": num(c, f"trap_stiffness_{k}")["value"], "v": num(c, f"flow_speed_{cell}")["value"],
            "offset": d["value_um"], "offset_se": d["standard_error_block_si"] * 1e6,
            "offset_pred": d["predicted_si"] * 1e6, "dev_se": d["deviation_in_block_standard_errors"],
            "ratio": s["from_drag_ratio"], "rel_se": s["from_drag_relative_standard_error"],
            "rel_se_pred": s["from_drag_relative_standard_error_ou_predicted"],
            "widths": o["recovered_stiffness"]["offset_in_thermal_widths"],
            "eq_ratio": s["from_equipartition_ratio"], "tau_ratio": o["relaxation_time"]["ratio"],
            "var_y": o["transverse"]["y"]["variance_ratio_to_equipartition"],
            "var_z": o["transverse"]["z"]["variance_ratio_to_equipartition"],
            "wall": o["cost"]["integration_wall_s"], "steps": o["cost"]["steps"],
            "met": {e["id"]: e["met"] for e in c["criteria_evaluation"]}, "outcome": c.get("outcome"),
            "record": num(c, f"record_length_{cell}")["value"], "dt": num(c, f"integration_timestep_{cell}")["value"],
            "save": num(c, f"save_interval_{k}")["value"], "startup": num(c, f"startup_discard_{k}")["value"],
            "seed": json.loads((r["run_dir"] / "trajectory_meta.json").read_text())["trajectory"]["seed"],
        })
    return sorted(rows, key=lambda x: (x["k"], x["v"]))


def trap_f3(R: dict, rows: list[dict]) -> str:
    row = rows[0]
    try:
        t = trajectory.read_text(row["r"]["run_dir"])
    except trajectory.TrajectoryUnavailable as exc:
        return f"<p class='gone'><b>F3 not drawn.</b> {html.escape(str(exc))}</p>"
    x = t["coords"][:, 0, 0] * 1e6
    time = t["steps"] * row["dt"]
    keep = time >= time[0] + row["startup"]
    n = min(int(40 * row["k"] and 400), keep.sum())
    tt, xx = time[keep][:n], x[keep][:n]
    p1 = Plot((tt[0], tt[-1]), (min(xx.min(), 0) - 0.2, xx.max() + 0.2), xlabel="time (s)", ylabel="along-flow position (µm)")
    p1.hline(0, "#999"); p1.hline(row["offset_pred"], "#c0392b")
    p1.line(tt, xx, "#2f5d9e", 0.8)
    sigma = math.sqrt(K_B * num(row["r"]["card"], "temperature")["value"] / (row["k"] * 1e-6)) * 1e6
    xs = x[keep]
    edges = np.linspace(row["offset_pred"] - 4 * sigma, row["offset_pred"] + 4 * sigma, 41)
    cnt, _ = np.histogram(xs, edges, density=True)
    gx = np.linspace(edges[0], edges[-1], 200)
    gy = np.exp(-(gx - row["offset_pred"]) ** 2 / (2 * sigma ** 2)) / (sigma * math.sqrt(2 * math.pi))
    p2 = Plot((edges[0], edges[-1]), (0, max(cnt.max(), gy.max()) * 1.1), w=360, xlabel="along-flow position (µm)", ylabel="probability density (1/µm)")
    p2.bars(edges, cnt); p2.line(gx, gy, "#c0392b", 1.5)
    return figure("F3", p1.svg() + p2.svg(),
                  f"Raw data from one run: stiffness {fmt(row['k'])} pN/µm, flow {fmt(row['v'])} µm/s, seed {row['seed']}. "
                  f"Left, the first {n} saved frames after start-up, with the trap centre (grey) and the predicted mean offset (red). "
                  f"Right, all {int(keep.sum())} frames after start-up as a histogram, against the Gaussian the model predicts: "
                  f"centred on the offset, with thermal width {fmt(sigma)} µm.")


def trap_f5(R: dict, rows: list[dict]) -> str:
    row = next(r for r in rows if r["cell"].endswith("o2"))
    sigma = math.sqrt(K_B * num(row["r"]["card"], "temperature")["value"] / (row["k"] * 1e-6)) * 1e6
    off = row["offset_pred"]
    span = off + 4 * sigma
    xs = np.linspace(-span * 0.6, span, 300)
    u = 0.5 * row["k"] * 1e-6 * (xs * 1e-6) ** 2 / (K_B * 293)
    tilt = u - (row["k"] * 1e-6 * off * 1e-6) * (xs * 1e-6) / (K_B * 293)
    p = Plot((xs[0], xs[-1]), (tilt.min() - 5, u.max()), xlabel="position along the flow (µm)", ylabel="energy (k_B T)")
    p.line(xs, u, "#999", 1.2, "4 3")
    p.line(xs, tilt, "#2f5d9e", 2)
    p.parts.append(f'<line x1="{p.X(0):.1f}" x2="{p.X(off):.1f}" y1="{p.Y(tilt.min() - 2):.1f}" y2="{p.Y(tilt.min() - 2):.1f}" stroke="#c0392b" stroke-width="2" marker-end="url(#ar)"/>')
    p.parts.insert(0, '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#c0392b"/></marker></defs>')
    p.text(off / 2, tilt.min() - 1, "offset γv/k", "#c0392b", "middle")
    return figure("F5", p.svg(),
                  f"The setup, drawn from the plan's parameters at stiffness {fmt(row['k'])} pN/µm and flow {fmt(row['v'])} µm/s. "
                  "Grey dashed: the trap alone, a harmonic well centred on zero. Blue: the trap plus the steady drag of the flow, "
                  "which tilts the well so its bottom moves downstream by γv/k. The sphere jiggles about that new bottom.")


def trap_expected(R, rows) -> str:
    return ("<p>With inertia negligible, the sphere obeys <code>γ(ṙ − v) = −k r + noise</code>, with drag <code>γ = 3πηd</code>. "
            "Its mean offset from the trap centre is therefore</p><p class='eq'><code>Δx = γ v / k</code></p>"
            "<p>and a drag calibration reads the stiffness back as <code>k = γv / Δx</code>. The bead jiggles with thermal width "
            "<code>σ = √(k<sub>B</sub>T/k)</code> and relaxes over <code>τ = γ/k</code>, so over a record of length T the relative "
            "error of the recovered stiffness should be</p><p class='eq'><code>√(2τ/T) ÷ (Δx/σ)</code></p>"
            "<p>The stiffness cancels from this: the error should depend on how far the flow pushes the bead in units of its "
            "jiggle, and on the record length in units of the relaxation time, and on nothing else. That is the prediction "
            "these runs test. It follows from the Langevin equation for an overdamped sphere, a textbook result.</p>")


def trap_setup_words(R, rows) -> str:
    return ("<p>One sphere in water, held by a perfectly harmonic trap, with the fluid flowing past at constant speed. "
            "Inertia is left out, which is exact for a micrometre bead in water on these timescales. In this limit a steady "
            "flow and a steady push of <code>γv</code> are the same thing, so no fluid is simulated. <b>Left out:</b> the trap "
            "never lets go and never softens far from its centre; walls, other particles and heating by the laser are absent.</p>")


# Configurations whose report body is written in their own module (task 022: each
# window adds its own configuration's parts). The module exposes PARTS with a
# `build(R, notes) -> (body, ctx)` and a `title`.
EXTERNAL_PARTS = {"bd_overdamped_trapped": "report_trap_rest"}

CONFIG_PARTS = {
    "bd_overdamped_trapped_uniform_flow": {
        "cells": trap_cells, "f3": trap_f3, "f5": trap_f5, "expected": trap_expected, "setup": trap_setup_words,
        "observable": "recovered stiffness ÷ stiffness put in",
    },
}


# -- the shared figures ----------------------------------------------------------

def f1(rows) -> str:
    ks = sorted({r["k"] for r in rows})
    vs = [r["v"] for r in rows]
    offs = [r["offset"] for r in rows]
    p = Plot((min(vs) / 2, max(vs) * 2), (min(offs) / 3, max(offs) * 3), logx=True, logy=True,
             xlabel="flow speed (µm/s)", ylabel="mean offset from trap centre (µm)")
    items = []
    for i, k in enumerate(ks):
        col = COLORS[i % len(COLORS)]
        mine = [r for r in rows if r["k"] == k]
        slope = mine[0]["offset_pred"] / mine[0]["v"]
        gx = [min(vs) / 2, max(vs) * 2]
        p.line(gx, [slope * x for x in gx], col, 1, "5 3")
        for r in mine:
            p.point(r["v"], r["offset"], r["offset_se"], col)
        items.append((col, f"{fmt(k)} pN/µm"))
    return figure("F1", p.svg() + legend(items + [("#666", "dashed: prediction γv/k")]),
                  f"Main result. Mean offset against flow speed, one colour per stiffness, from {len(rows)} runs of one seed each. "
                  "Error bars are each run's own standard error; most are smaller than the dots. The dashed lines are the prediction, "
                  "drawn before any run.")


def f2(rows, limit) -> str:
    p = Plot((-0.5, len(rows) - 0.5), (-limit - 1, limit + 1), xlabel="condition", ylabel="deviation (standard errors)")
    p.band(-limit, limit); p.hline(0)
    for i, r in enumerate(rows):
        p.point(i, r["dev_se"], None, COLORS[sorted({x["k"] for x in rows}).index(r["k"]) % len(COLORS)], 5)
        p.text(i, -limit - 0.6, f"{r['k']:g} / {r['v']:g}", "#555", "middle")
    return figure("F2", p.svg(),
                  f"Residuals. (measured − predicted offset) ÷ that run's own standard error, one dot per condition, labelled "
                  f"stiffness (pN/µm) / speed (µm/s). The green band is the ±{fmt(limit)} standard errors you set as the pass limit "
                  "before the runs.")


def f4(R, rows, limit) -> str:
    """Running deviation in units of the standard error AT THAT RECORD LENGTH, so the band is the declared limit throughout.

    The standard error of a mean over a fraction f of the record is the final one over sqrt(f): the record is
    many relaxation times long, so blocks are independent and the error shrinks as one over the root of their count.
    """
    p = Plot((0, 1), (-limit - 2, limit + 2), xlabel="fraction of the record used", ylabel="deviation (standard errors at that length)")
    p.band(-limit, limit); p.hline(0)
    drawn, gone, items = [], [], []
    for i, r in enumerate(rows):
        try:
            t = trajectory.read_text(r["r"]["run_dir"])
        except trajectory.TrajectoryUnavailable:
            gone.append(r["run_id"]); continue
        x = t["coords"][:, 0, 0] * 1e6
        time = t["steps"] * r["dt"]
        x = x[time >= time[0] + r["startup"]]
        f = np.arange(1, len(x) + 1) / len(x)
        dev = (np.cumsum(x) / np.arange(1, len(x) + 1) - r["offset_pred"]) / (r["offset_se"] / np.sqrt(f))
        idx = np.unique(np.linspace(len(x) // 10, len(x) - 1, 120).astype(int))
        col = COLORS[i % len(COLORS)] if i < len(COLORS) else "#555"
        p.line(f[idx], dev[idx], col, 1.2)
        items.append((col, f"{r['k']:g} pN/µm, {r['v']:g} µm/s"))
        drawn.append(r)
    note = f" Not drawn, trajectory gone: {', '.join(gone)}." if gone else ""
    return figure("F4", p.svg() + legend(items),
                  f"Convergence. How far the running mean offset sits from the prediction as more of each record is used, in units "
                  f"of the standard error a record of that length has, for {len(drawn)} runs, from the first tenth on. The green band "
                  f"is your ±{fmt(limit)} standard-error limit, fixed before the runs; each curve's right end is the value judged.{note}")


# -- sections ------------------------------------------------------------------

def section(n, title, body) -> str:
    return f"<h2>{n}. {title}</h2>{body}"


def build(qid: str) -> tuple[str, dict]:
    R = load(qid)
    plan, goal = R["plan"], R["goal"]
    cfg = plan["system_configuration"]["config"]
    parts = CONFIG_PARTS.get(cfg)
    if parts is None and cfg in EXTERNAL_PARTS:
        # A configuration whose whole body differs lives in its own module, imported
        # only when asked, so this file needs no knowledge of it beyond its name.
        import importlib  # noqa: PLC0415
        parts = importlib.import_module(f"{__package__}.{EXTERNAL_PARTS[cfg]}").PARTS
    if parts is None:
        raise Refused(f"no report parts are written for configuration {cfg!r}; its window adds them to CONFIG_PARTS")
    if "build" in parts:
        return parts["build"](R, notes(qid))
    rows = parts["cells"](R)
    N = notes(qid)
    c0 = rows[0]["r"]["card"]
    target = next(t["value"] for t in goal["targets"] if t["kind"] == "uncertainty")
    limit_n = num(c0, "deviation_limit_in_standard_errors")
    limit = limit_n["value"] if limit_n else None
    n_pass = sum(all(v for k, v in r["met"].items() if k != "step_displacement_diverged") for r in rows)
    worst = max(rows, key=lambda r: r["rel_se"])

    S = []
    S.append(section(1, "Summary",
        f"<div class='box'><p>Asked: can a known trap stiffness be recovered from a simulated drag calibration, to "
        f"{fmt(target * 100)}% relative uncertainty, across stiffnesses from {fmt(min(r['k'] for r in rows))} to "
        f"{fmt(max(r['k'] for r in rows))} pN/µm?</p><p><b>{n_pass} of {len(rows)} conditions met every criterion set in advance.</b> "
        f"The largest relative error was {fmt(worst['rel_se'] * 100, 2)}%, at {fmt(worst['k'])} pN/µm and {fmt(worst['v'])} µm/s; "
        f"the recovered stiffness ranged from {fmt(min(r['ratio'] for r in rows), 4)} to {fmt(max(r['ratio'] for r in rows), 4)} "
        f"of the value put in.</p></div>"))
    S.append(section(2, "Purpose", md(N["Purpose"])))
    S.append(section(3, "What was expected", parts["expected"](R, rows)))

    kept = {r["cell"] for r in rows}
    skipped = [p for p in plan["sweep"]["points"] if p.get("skipped")]
    fixed = [(n, num(c0, n)) for n in ("temperature", "viscosity", "bead_diameter")]
    var_rows = "".join(f"<tr><td>{n.replace('_', ' ')}</td><td class='n'>{fmt(x['value'])} {x['unit']}</td><td>{provenance(x['source'])}</td></tr>" for n, x in fixed)
    S.append(section(4, "Variables",
        "<table><tr><th>Quantity</th><th>Value</th><th>Where it came from</th></tr>"
        f"<tr><td><b>varied:</b> trap stiffness</td><td class='n'>{', '.join(fmt(k) for k in sorted({r['k'] for r in rows}))} pN/µm</td><td>the range you gave</td></tr>"
        f"<tr><td><b>varied:</b> flow speed</td><td class='n'>{', '.join(fmt(v) for v in sorted({r['v'] for r in rows}))} µm/s</td><td>computed per stiffness so the push is about 10 or about 100 thermal widths</td></tr>"
        + var_rows +
        f"<tr><td><b>measured:</b> mean offset, and the stiffness recovered from it</td><td class='n'>µm; ratio to the input</td><td>read off each run</td></tr></table>"
        f"<p>{len(kept)} of {len(plan['sweep']['points'])} planned conditions ran; the other {len(skipped)} were "
        f"{plain_skip(skipped[0]['skipped']) if skipped else ''}.</p>"))

    engine = rows[0]["r"]["log"]["events"][1]["report"].get("engine_build", {})
    setup_rows = "".join(
        f"<tr><td class='n'>{fmt(r['k'])}</td><td class='n'>{fmt(r['v'])}</td><td class='n'>{fmt(r['dt'])}</td><td class='n'>{fmt(r['save'])}</td>"
        f"<td class='n'>{fmt(r['startup'])}</td><td class='n'>{fmt(r['record'])}</td><td class='n'>{r['seed']}</td></tr>" for r in rows)
    S.append(section(5, "Setup",
        parts["setup"](R, rows) +
        f"<p>Engine: {html.escape(str(engine.get('engine', '?')))} {html.escape(str(engine.get('version', '')))}, one run per condition.</p>"
        "<table><tr><th>stiffness (pN/µm)</th><th>flow (µm/s)</th><th>time step (s)</th><th>save every (s)</th><th>start-up discarded (s)</th><th>record (s)</th><th>seed</th></tr>"
        + setup_rows + "</table>"
        "<p><b>Why these settings.</b> The time step is kept well below the bead's relaxation time and small enough that neither "
        "the random kick nor the flow moves it far in one step. The record is long enough that the predicted error meets your "
        "target with a margin. Positions are saved several times per relaxation time. The start-up discarded covers the time the "
        "bead takes to settle at its new offset. Every setting scales with that condition's relaxation time, so the number of steps "
        "does not grow with stiffness.</p>" + parts["f5"](R, rows)))

    crit = [f"<li><b>Precision:</b> the relative error of the recovered stiffness at or below {fmt(target * 100)}% in every condition. Chosen by you.</li>"]
    if limit is not None:
        crit.append(f"<li><b>Accuracy:</b> the recovered stiffness within {fmt(limit)} of that condition's own standard errors "
                    "of the value put in. Chosen by you.</li>")
    crit.append("<li><b>Divergence guard:</b> the run stops as a fault if the sphere moves more than its own diameter in one step.</li>")
    # Three states (task 022, amended): on a card, before the data in prose only, or none.
    if plan.get("success_criteria"):
        crit_body = ("<p><b>Set on the plan before any run</b>, dated "
                     f"{html.escape(plan['created_at'][:10])}, and applied as written:</p><ul>" + "".join(crit) + "</ul>")
    elif N["Criteria"].strip():
        crit_body = ("<p><b>Stated before the data, but only in prose</b> and not on any card. Quoted from the notes, with "
                     "its source and time as written there, and judged separately:</p>" + md(N["Criteria"]))
    else:
        crit_body = "<p><b>No criterion was set in advance.</b> Any band drawn below is for reading, not a criterion.</p>"
    S.append(section(6, "Criteria set in advance", crit_body))

    res_rows = "".join(
        f"<tr><td class='n'>{fmt(r['k'])}</td><td class='n'>{fmt(r['v'])}</td><td class='n'>{fmt(r['widths'], 3)}</td>"
        f"<td class='n'>{r['offset']:.4f} ± {r['offset_se']:.4f}</td><td class='n'>{r['offset_pred']:.4f}</td>"
        f"<td class='n'>{r['ratio']:.4f}</td><td class='n'>{r['rel_se'] * 100:.2f}%</td><td class='n'>{r['dev_se']:+.2f}</td>"
        f"<td>{'pass' if all(v for k, v in r['met'].items() if k != 'step_displacement_diverged') else '<b>fail</b>'}"
        f"{'' if r['outcome'] == 'DONE' else ' (' + html.escape(str(r['outcome'])) + ')'}</td></tr>" for r in rows)
    S.append(section(7, "Results",
        f1(rows) + "<table><tr><th>stiffness (pN/µm)</th><th>flow (µm/s)</th><th>push (thermal widths)</th><th>offset (µm)</th>"
        "<th>predicted (µm)</th><th>recovered ÷ input</th><th>relative error</th><th>deviation (SE)</th><th>verdict</th></tr>"
        + res_rows + "</table><p class='meta'>Every value read off the runs. No run diverged or was dropped.</p>"
        + parts["f3"](R, rows) + (f4(R, rows, limit) if limit is not None else "")))

    chk_rows = "".join(
        f"<tr><td class='n'>{fmt(r['k'])} / {fmt(r['v'])}</td><td class='n'>{r['rel_se'] / r['rel_se_pred']:.2f}</td>"
        f"<td class='n'>{r['tau_ratio']:.2f}</td><td class='n'>{r['eq_ratio']:.3f}</td><td class='n'>{r['var_y']:.2f} / {r['var_z']:.2f}</td></tr>" for r in rows)
    S.append(section(8, "Checks",
        "<p>Cases whose answer is known independently of the drag calibration, read off the same runs:</p>"
        "<table><tr><th>stiffness / flow</th><th>measured ÷ predicted error</th><th>relaxation time, fitted ÷ declared</th>"
        "<th>stiffness from jiggle width ÷ input</th><th>cross-flow jiggle ÷ expected (y / z)</th></tr>" + chk_rows + "</table>"
        + (f2(rows, limit) if limit is not None else "")))
    S.append(section(9, "Interpretation", "<p class='meta'>Judgement, kept apart from the numbers above.</p>" + md(N["Interpretation"])))
    S.append(section(10, "Limits", md(N["Limits"])))

    caps = json.loads((cards.CONTRACTS / "capabilities" / "microscope.json").read_text())
    obs_name = plan["observable"]["name"]
    can = [c["config"] for c in caps["configurations"] for p in (c.get("produces") or [])
           if (p if isinstance(p, str) else p.get("id")) == obs_name]
    S.append(section(11, "Link to experiment",
        f"<p>{'The microscope can measure this in: ' + ', '.join(can) + '.' if can else 'The microscope does not yet declare a way to measure the mean drag offset, so this plan cannot be sent to the experiment side yet.'} "
        + ("It already measures the position distribution of a trapped bead, and the offset is the mean of that same trajectory, so adding it is likely one declaration on the microscope side." if not can else "")
        + "</p><p>On the bench, the viscosity would not cancel as it does here: its uncertainty goes straight into the recovered stiffness, "
        "and nothing reads the temperature at the sample.</p>"))
    S.append(section(12, "Decisions for you", md(N["Decisions"])))

    budget = json.loads((cards.AGENT / "envelope" / "budget.json").read_text())
    lim = next(t for t in budget["targets"] if t["target"] == "local")["limits"]
    wall = sum(r["wall"] for r in rows)
    sizes = [(r["run_id"], (r["r"]["run_dir"] / "trajectory.txt").stat().st_size if (r["r"]["run_dir"] / "trajectory.txt").exists() else 0) for r in rows]
    S.append(section(13, "Cost",
        f"<p>Integration time over all runs: {fmt(wall, 2)} s, against a ceiling of {lim['wall_clock_max']['value']} {lim['wall_clock_max']['unit']} "
        f"per job. Measured, {fmt(wall / sum(r['steps'] for r in rows) * 1e6, 2)} µs per step.</p>"
        "<table><tr><th>trajectory kept</th><th>size</th></tr>" +
        "".join(f"<tr><td><code>simulation_agent/runs/{rid}/trajectory.txt</code></td><td class='n'>{s / 1e6:.2f} MB</td></tr>" for rid, s in sizes)
        + f"<tr><td>total</td><td class='n'>{sum(s for _, s in sizes) / 1e6:.2f} MB of {lim['storage_max']['value']} {lim['storage_max']['unit']}</td></tr></table>"
        "<p>These files are what the figures are drawn from; deleting one removes its figures from the next report and nothing reruns it.</p>"))
    return "".join(S), {"R": R, "rows": rows}


# -- a revision that ended in a refusal (task 022, 2026-09-24) ----------------

def load_refusal(qid: str) -> dict | None:
    """The latest revision whose record ends in a refusal and that produced no results, or None.

    A revision with results is reported the ordinary way even if it also holds a
    refusal card (a sweep's skipped cells leave one). One without results but with
    a refusal is reported as the refusal. A later revision that has a plan and has
    not run yet is named in the summary, not reported on.
    """
    qdir = cards.question_dir(qid)
    latest = cards.question_revision(qid)
    results = [json.loads(p.read_text()) for p in qdir.glob("result_run-*.json")]
    for rev in range(latest, 0, -1):
        plan_path = qdir / cards.artifact_name(f"plan_simulation_{qid}.json", rev)
        if plan_path.exists():
            pid = json.loads(plan_path.read_text())["id"]
            if any(r.get("plan_id") == pid for r in results):
                return None
        path = qdir / cards.artifact_name(f"refusal_s4_{qid}.json", rev)
        if path.exists():
            return {"qid": qid, "rev": rev, "latest": latest, "refusal": json.loads(path.read_text()),
                    "plan_path": path, "goal": cards.load_goal(qid, rev), "results": []}
    return None


def _ratio(a: dict, b: dict) -> float:
    return float(a["value"]) / float(b["value"]) if a["unit"] == b["unit"] else float("nan")


def build_refusal(R: dict) -> str:
    c, goal = R["refusal"], R["goal"]
    nums = {n["name"]: n for n in c["numbers"]}
    N = notes(R["qid"])

    def show(n):
        return fmt(float(n["value"])) + ("" if n["unit"] == "1" else f" {n['unit']}")

    ce = [x for x in c.get("counterexample") or [] if x.get("required_number") in nums and x.get("limit_number") in nums]
    later = (f" A later revision, {R['latest']}, has a plan that has not run yet; this report is on the revision that ended."
             if R["latest"] > R["rev"] else "")
    S = [section(1, "Summary",
        "<div class='box'><p><b>Nothing was run. The plan was refused before any computing, because the question as "
        "asked does not fit inside the budget.</b> "
        + " ".join(f"It needs {show(nums[x['required_number']])} {x['parameter'].replace('_', ' ')} against "
                   f"{show(nums[x['limit_number']])} allowed, about {fmt(_ratio(nums[x['required_number']], nums[x['limit_number']]), 2)} times over."
                   for x in ce)
        + later + "</p></div>")]
    S.append(section(2, "Purpose", md(N["Purpose"])))
    S.append(section(3, "What was expected", "<p class='empty'>No prediction to compare against: nothing ran.</p>"))
    chosen = [n for n in c["numbers"] if n["source"].startswith("assumed:")]
    S.append(section(4, "Variables",
        f"<p>Quantity asked for: {html.escape(goal['observable']['name'].replace('_', ' '))}. Settings the refusal was computed at:</p>"
        "<table><tr><th>Setting</th><th>Value</th><th>Where it came from</th></tr>"
        + "".join(f"<tr><td>{html.escape(n['name'].replace('_', ' '))}</td><td class='n'>{show(n)}</td><td>{provenance(n['source'])}</td></tr>" for n in chosen)
        + "</table>"))
    S.append(section(5, "Setup", "<p>Not run, so no engine, time step or seed was used.</p>"))
    tg = goal.get("targets") or []
    S.append(section(6, "Criteria set in advance",
        ("<p><b>Set on the goal before any planning:</b></p><ul>"
         + "".join(f"<li>{html.escape(t['metric'].replace('_', ' '))}: {html.escape(t['kind'])} {fmt(float(t['value']))} {html.escape(t.get('unit', ''))}</li>" for t in tg)
         + "</ul>") if tg else
        "<p><b>No accuracy criterion was set in advance.</b> The only fixed limit was the computing budget.</p>"))
    rows = "".join(
        f"<tr><td>{html.escape(x['parameter'].replace('_', ' '))}</td><td class='n'>{show(nums[x['required_number']])}</td>"
        f"<td class='n'>{show(nums[x['limit_number']])}</td><td>{worded(x.get('statement', ''), 'The explanation')}</td></tr>"
        for x in ce)
    S.append(section(7, "Results",
        f"<p><b>Refused.</b> What was asked: {worded(c.get('refused_what', ''), 'The description')}</p>"
        "<table><tr><th>What collided</th><th>Needed</th><th>Allowed</th><th>Why</th></tr>" + rows + "</table>"))
    chain = [n for n in c["numbers"] if n.get("formula")]
    S.append(section(8, "Checks",
        "<p>How the needed resources were computed; each line uses the ones above it or the settings in the table before:</p>"
        "<table><tr><th>Quantity</th><th>Value</th><th>Computed as</th></tr>"
        + "".join(f"<tr><td>{html.escape(n['name'].replace('_', ' '))}</td><td class='n'>{show(n)}</td><td><code>{html.escape(n['formula'])}</code></td></tr>" for n in chain)
        + "</table>"))
    S.append(section(9, "Interpretation", "<p class='meta'>Judgement, kept apart from the numbers above.</p>" + md(N["Interpretation"])))
    S.append(section(10, "Limits", md(N["Limits"])))
    S.append(section(11, "Link to experiment", "<p>Nothing to send to the experiment side: no plan was accepted.</p>"))
    alts = "".join(f"<li>{worded(a.get('what', ''), 'This option')}"
                   + (f"<br><span class='meta'>Needs: {worded(a['requires'], 'What it needs')}</span>" if a.get("requires") else "")
                   + "</li>" for a in c.get("alternatives") or [])
    S.append(section(12, "Decisions for you",
        ("<p>The options the refusal offers:</p><ul>" + alts + "</ul>" if alts else "") + md(N["Decisions"])))
    S.append(section(13, "Cost", "<p>No computing was spent and no trajectory was kept.</p>"))
    return "".join(S)


def footer(qid: str, R: dict) -> str:
    rev = subprocess.run(["git", "-C", str(cards.REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    v = subprocess.run([sys.executable, str(cards.CONTRACTS / "validate.py"), "--quiet"], capture_output=True, text=True, cwd=cards.REPO)
    tree = next((l for l in v.stdout.splitlines()[::-1] if l.startswith("tree:")), "tree: not reported")
    verdict = next((l for l in v.stdout.splitlines()[::-1] if l.startswith("verdict:")), "")
    runs = ", ".join(r["card"]["run_id"] for r in R["results"])
    return (f"<footer><p>Generated {_dt.datetime.now().astimezone().isoformat(timespec='minutes')} by <code>simulation_agent/src/report.py</code>. "
            f"Question {qid}, revision {R['rev']}; record <code>{R['plan_path'].relative_to(cards.REPO)}</code>; runs {runs}. "
            f"Repository at {rev}. Validator: {html.escape(verdict)} {html.escape(tree)}. "
            f"Notes: <code>{NOTES_DIR / (qid + '.md')}</code>.</p>"
            + "".join(f"<p>As recorded, not yet worded for you: {html.escape(r)}</p>" for r in dict.fromkeys(UNWORDED))
            + f"<p>Regenerate: <code>cd simulation_agent &amp;&amp; ../.pixi/envs/sim/bin/python -m src.report {qid}</code></p></footer>")


CSS = """
:root{--ink:#1d2330;--muted:#5b6475;--line:#dde2ea;--accent:#2f5d9e}
body{font:15px/1.55 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif;color:var(--ink);background:#fafbfc;margin:0}
main{max-width:940px;margin:0 auto;padding:40px 28px 60px;background:#fff}
h1{font-size:24px;margin:0 0 6px}h2{font-size:18px;margin:34px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line);color:var(--accent)}
table{border-collapse:collapse;width:100%;margin:10px 0 14px;font-size:13.5px}th,td{border:1px solid var(--line);padding:5px 8px;text-align:left}
th{background:#f2f4f8}td.n{font-variant-numeric:tabular-nums;white-space:nowrap}
code{font:12.5px Menlo,Consolas,monospace;background:#f2f4f8;padding:1px 4px;border-radius:3px}
.box{border-left:3px solid var(--accent);background:#f5f8fc;padding:8px 14px}.eq{text-align:center}
figure{margin:16px 0}.fig{display:flex;flex-wrap:wrap;gap:8px}figcaption{font-size:13px;color:var(--muted)}
.legend span{margin-right:14px;font-size:12.5px}.legend i{display:inline-block;width:12px;height:12px;margin-right:4px;vertical-align:-1px}
.meta,.empty{color:var(--muted);font-size:13px}.empty{font-style:italic}.gone{background:#fdf7ec;padding:8px 12px}
footer{margin-top:40px;padding-top:10px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
"""


def emit(qid: str) -> Path:
    _selftest()
    refused = load_refusal(qid)
    if refused:
        body, ctx = build_refusal(refused), {"R": refused, "title": f"{qid}: refused before running"}
    else:
        body, ctx = build(qid)
    refuse_codes(body)
    title = ctx.get("title") or ("Drag calibration of a harmonic trap"
                                 if "trap" in ctx["R"]["plan"]["system_configuration"]["config"] else qid)
    doc = (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head>"
           f"<body><main><h1>{title}</h1><p class='meta'>Simulation report, generated from the records. Numbers are read off the "
           f"cards and runs; the sections marked as notes are written by hand.</p>{body}{footer(qid, ctx['R'])}</main></body></html>")
    REPORT_DIR.mkdir(exist_ok=True)
    out = REPORT_DIR / f"rebuild-report-{_dt.date.today():%m%d}-{qid}.html"
    out.write_text(doc)
    return out


if __name__ == "__main__":
    try:
        print(emit(sys.argv[1]))
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
