"""Run an approved operation plan on the piezo stage through the dispatcher, and draw it.

    python src/run_operation_plan.py --plan <plan.json> --run-id run-YYYYMMDD-NNN \
        --bench "<the person's words handing over the bench>"
    python src/run_operation_plan.py --graph runs/<run_id>/log.json

Not a stand-in script. The commands come out of operator.derive_commands and go
through operator.run, which refuses a plan no approval covers and checks every
derived point against envelope/safety.json before the first is sent. What this
file does is the part the dispatcher cannot: open the controller's port once,
before the run, and close it after, whatever happened.

  1. open COM4 writable, with the bench hand-over recorded -- a record, not a
     verification
  2. re-read the calibrated range: positions are written only if it still says
     picometres
  3. learn what the locked and User levels read as and put the found level
     back (live checklist 2a), so an unlock can be undone
  4. operator.run(backend="hardware"), then operator.write_run
  5. close the port in `finally`, and draw planned against measured from the
     log -- the log, not memory, so the graph shows only what was recorded

Nothing here chooses a position, a speed or a time. The plan and the dispatcher
do; this opens and closes a port and plots a file.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import argparse                                                  # noqa: E402
import importlib.util                                            # noqa: E402
import json                                                      # noqa: E402
from pathlib import Path                                         # noqa: E402

AGENT = Path(_HERE).parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)                                 # type: ignore[union-attr]
    return mod


def run(plan_path: Path, run_id: str, bench: str, address: str = "COM4") -> Path:
    op = _load("_op_runner", Path(_HERE) / "operator.py")
    serial = _load("_serial_runner", Path(_HERE) / "devices" / "python_serial.py")
    link = serial.open_link("dll", address=address, bench=bench, read_only=False)
    try:
        unit = link.confirm_position_unit()
        if not unit["picometres"]:
            raise op.Refusal(f"the calibrated range no longer reads as picometres: {unit}")
        levels = link.learn_levels()
        if not levels["restored"]:
            raise op.Refusal(f"the found security level was not restored: {levels}")
        record = op.run(plan_path, run_id, backend="hardware")
        record["events"][0:0] = [
            {"t_mono": 0.0, "time_base": "software", "event": "link_opened", "address": address,
             "bench": bench, "position_unit": unit, "security_levels": levels}]
    finally:
        serial.close_link()
    return op.write_run(record)


# --------------------------------------------------------------------------- #
# the graph: planned against measured, from the log
# --------------------------------------------------------------------------- #

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9"
PLANNED, MEASURED = "#2a78d6", "#eb6834"


def series(log: dict):
    """(t, planned, measured) for every point of every move, on one run clock."""
    out, offset = [], 0.0
    for e in log["events"]:
        if e.get("event") != "apply" or not str(e.get("from", "")).startswith("operation.moves["):
            continue
        m = e.get("measured") or {}
        samples = m.get("samples") or []
        for s in samples:
            out.append((offset + s["t_sent_s"], s["target_um"], s["measured_um"], e["from"]))
        if samples:
            offset += samples[-1]["t_sent_s"] + (m.get("dt_s") or 0)
    return out


def svg(log: dict, title: str) -> str:
    pts = series(log)
    if not pts:
        raise SystemExit("the log carries no measured samples; nothing to draw")
    W, H1, H2, ml, mr, mt, gap = 900, 360, 170, 70, 110, 56, 44
    H = mt + H1 + gap + H2 + 44
    tmax = max(p[0] for p in pts) or 1
    X = lambda t: ml + (W - ml - mr) * t / tmax
    lo = min(min(p[1], p[2]) for p in pts)
    hi = max(max(p[1], p[2]) for p in pts)
    Y1 = lambda v: mt + H1 * (1 - (v - lo) / ((hi - lo) or 1))
    errs = [p[2] - p[1] for p in pts]
    emax = max(abs(e) for e in errs) or 1
    top2 = mt + H1 + gap
    Y2 = lambda v: top2 + H2 * (0.5 - v / (2 * emax))

    def path(ys, yf):
        return "M" + " L".join(f"{X(t):.1f},{yf(y):.1f}" for t, y in ys)

    g = []
    for k in range(6):
        v = lo + (hi - lo) * k / 5
        g.append(f'<line x1="{ml}" x2="{W-mr}" y1="{Y1(v):.1f}" y2="{Y1(v):.1f}" stroke="{GRID}"/>'
                 f'<text x="{ml-8}" y="{Y1(v)+4:.1f}" text-anchor="end" font-size="12" fill="{INK2}">{v:.0f}</text>')
    for v in (-emax, 0, emax):
        g.append(f'<line x1="{ml}" x2="{W-mr}" y1="{Y2(v):.1f}" y2="{Y2(v):.1f}" stroke="{GRID}"/>'
                 f'<text x="{ml-8}" y="{Y2(v)+4:.1f}" text-anchor="end" font-size="12" fill="{INK2}">{v:+.1f}</text>')
    for t in range(0, int(tmax) + 1):
        g.append(f'<text x="{X(t):.1f}" y="{H-24}" text-anchor="middle" font-size="12" fill="{INK2}">{t}</text>')
    planned = path([(p[0], p[1]) for p in pts], Y1)
    measured = path([(p[0], p[2]) for p in pts], Y1)
    error = path([(p[0], p[2] - p[1]) for p in pts], Y2)
    late = sum(1 for e in log["events"] for s in ((e.get("measured") or {}).get("samples") or [])
               if s.get("late"))
    rms = (sum(e * e for e in errs) / len(errs)) ** 0.5
    last = pts[-1]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Segoe UI, Arial, sans-serif">
<rect width="{W}" height="{H}" fill="{SURFACE}"/>
<text x="{ml}" y="22" font-size="15" font-weight="600" fill="{INK}">{title}</text>
<text x="{ml}" y="40" font-size="12" fill="{INK2}">{len(pts)} points; measured minus planned: RMS {rms:.2f} um, largest {max(errs, key=abs):+.2f} um; {late} late point(s)</text>
{''.join(g)}
<path d="{planned}" fill="none" stroke="{PLANNED}" stroke-width="2"/>
<path d="{measured}" fill="none" stroke="{MEASURED}" stroke-width="2"/>
<text x="{W-mr+8}" y="{Y1(last[1])-6:.1f}" font-size="12" fill="{INK}">planned</text>
<text x="{W-mr+8}" y="{Y1(last[2])+14:.1f}" font-size="12" fill="{INK}">measured</text>
<rect x="{W-mr-150}" y="{mt-18}" width="10" height="10" fill="{PLANNED}"/><text x="{W-mr-136}" y="{mt-9}" font-size="12" fill="{INK2}">planned (commanded)</text>
<rect x="{W-mr-150}" y="{mt-4}" width="10" height="10" fill="{MEASURED}"/><text x="{W-mr-136}" y="{mt+5}" font-size="12" fill="{INK2}">measured (read back)</text>
<text x="18" y="{mt+H1/2}" font-size="12" fill="{INK2}" transform="rotate(-90 18 {mt+H1/2})" text-anchor="middle">X position (um)</text>
<text x="{ml}" y="{top2-10}" font-size="13" font-weight="600" fill="{INK}">Tracking error: measured minus planned (um)</text>
<path d="{error}" fill="none" stroke="{MEASURED}" stroke-width="2"/>
<text x="{(ml+W-mr)/2}" y="{H-6}" text-anchor="middle" font-size="12" fill="{INK2}">time since the first point (s)</text>
</svg>'''


def graph(log_path: Path) -> Path:
    log = json.loads(log_path.read_text(encoding="utf-8"))
    out = log_path.parent / "position_vs_time.svg"
    out.write_text(svg(log, f"Piezo X, {log.get('run_id')}: planned against measured"),
                   encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--run-id")
    ap.add_argument("--bench", help="the person's words handing over the bench")
    ap.add_argument("--graph", type=Path, help="draw an existing run log")
    args = ap.parse_args(argv)
    if args.graph:
        print(graph(args.graph))
        return 0
    if not (args.plan and args.run_id and args.bench):
        ap.error("--plan, --run-id and --bench are all required to run")
    folder = run(args.plan, args.run_id, args.bench)
    print(folder, graph(folder / "log.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
