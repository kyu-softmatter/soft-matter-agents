"""Photostability curves and drift from today's preparatory runs, reproducibly.

The numbers in findings/microscope-20260924-1-20260924.json for runs -002,
-006 and -007 were first computed by hand after each run, and a store reader
could not check them: the frames sit outside the repository and nothing on
disk said how the figures came out of them. This script is the how. It
reads each run's frames from the path its committed log names, checks each
file's sha256 against the log, and writes the curves and drift to
microscope_agent/runs/<run_id>/photostability_analysis.json, beside
each run log, which it does not touch.

METHOD (microscope_agent/CLAUDE.md at b48c9b3). No mask fixed at frame 0: on
this sample particles drift, and a frame-0 mask reads drift as fading, which
is how the first -002 curve came out at 80.7% when the total barely moved.
Instead the whole frame is summed over pixels more than THRESH_ADU above that
frame's median, dark subtracted. The curve is normalised to the settled level
(the mean of the samples at 5 and 10 s), because the first frame after
State=1 sits a few percent low while the light settles. Drift is reported
beside the curve: nearest-neighbour displacement of detected particles from
frame 0.

Numbers here are observable values from preparatory runs. They are not for
the store until a plan cites these runs.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]

import hashlib                                                   # noqa: E402
import json                                                      # noqa: E402
from pathlib import Path                                         # noqa: E402

import numpy as np                                               # noqa: E402

AGENT = Path(__file__).resolve().parent.parent
THRESH_ADU = 300           # above the frame median: particle signal, not background
BLOB_ADU = 1500            # above the frame median: a particle core, for drift
SETTLED_S = (5, 10)        # the level a curve is normalised to

RUNS = {
    "run-20260924-002": {"label": "particles_series", "period_s": 0.1, "step": 10},
    "run-20260924-006": {"label": "particles_paced", "period_s": 1.0, "step": 5},
    "run-20260924-007": {"label": "particles_paced", "period_s": 1.0, "step": 5},
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def frames_of(run_id: str, label: str) -> dict:
    log = json.loads((AGENT / "runs" / run_id / "log.json").read_text(encoding="utf-8"))
    listed = log["events"][-1]["frames"]
    return {f["label"]: f for f in listed}, log


def blobs(frame: np.ndarray) -> np.ndarray:
    """Particle centres on a 4-px grid: enough for displacements of several px."""
    h, w = frame.shape
    core = (frame - np.median(frame[::8, ::8])) > BLOB_ADU
    c = core[: h - h % 4, : w - w % 4].reshape(h // 4, 4, w // 4, 4).any(axis=(1, 3))
    seen = np.zeros_like(c)
    centres = []
    for y0, x0 in zip(*np.nonzero(c)):
        if seen[y0, x0]:
            continue
        stack, members = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            a, b = stack.pop()
            members.append((a, b))
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    u, v = a + da, b + db
                    if 0 <= u < c.shape[0] and 0 <= v < c.shape[1] and c[u, v] and not seen[u, v]:
                        seen[u, v] = True
                        stack.append((u, v))
        centres.append(np.mean(members, axis=0) * 4)
    return np.array(centres)


def analyse(run_id: str, spec: dict) -> dict:
    listed, _ = frames_of(run_id, spec["label"])
    series, dark_entry = listed[spec["label"]], listed["dark_a1"]
    for entry in (series, dark_entry):
        got = sha(Path(entry["path"]))
        if got != entry["sha256"]:
            raise SystemExit(f"{entry['path']} hashes {got}, not the {entry['sha256']} its log names")
    stack = np.load(series["path"], mmap_mode="r")
    dark = np.load(dark_entry["path"]).astype(np.float32)
    n = stack.shape[0]
    idx = list(range(0, n, spec["step"]))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    totals, medians = [], []
    for i in idx:
        f = stack[i].astype(np.float32) - dark
        med = float(np.median(f[::8, ::8]))
        g = f - med
        totals.append(float(g[g > THRESH_ADU].sum()))
        medians.append(med)
    t = [round(i * spec["period_s"], 3) for i in idx]
    settled = [tot for ti, tot in zip(t, totals) if SETTLED_S[0] <= ti <= SETTLED_S[1]]
    ref = float(np.mean(settled))
    curve = [round(v / ref * 100, 3) for v in totals]

    marks = sorted({0, int(round(60 / spec["period_s"])), n - 1} & set(range(n)))
    centres = {i: blobs(stack[i].astype(np.float32) - dark) for i in marks}
    drift = {}
    for i in marks[1:]:
        d = np.sqrt(((centres[0][:, None, :] - centres[i][None, :, :]) ** 2).sum(-1)).min(1)
        drift[f"{round(i * spec['period_s'])}s"] = {
            "median_px": round(float(np.median(d)), 1), "max_px": round(float(d.max()), 1),
            "share_over_10px": round(float((d > 10).mean()), 2)}
    return {
        "frames": {"path": series["path"], "sha256": series["sha256"], "n": n},
        "dark": {"path": dark_entry["path"], "sha256": dark_entry["sha256"]},
        "t_s": t, "total_pct_of_settled": curve,
        "first_frame_pct_of_settled": curve[0], "last_pct_of_settled": curve[-1],
        "background_median_adu": {"first": round(medians[0], 1), "last": round(medians[-1], 1)},
        "particles_detected": {f"{round(i * spec['period_s'])}s": len(c) for i, c in centres.items()},
        "drift_from_frame0": drift,
    }


def main() -> int:
    # No `artifact` key: this is not a registered artefact kind, and the
    # collector reads only files that carry one. It is a derived file beside
    # the run log, which it does not touch.
    common = {
        "what": "photostability curve and drift, preparatory run",
        "script": "microscope_agent/src/analyse_photostability.py",
        "method": {"threshold_adu_above_frame_median": THRESH_ADU, "settled_window_s": list(SETTLED_S),
                   "blob_adu_above_frame_median": BLOB_ADU,
                   "note": "whole-frame total, no frame-0 mask, normalised to the settled level; "
                           "drift is nearest-neighbour displacement of particle centres from frame 0"},
        "for_store": False,
    }
    for run, spec in RUNS.items():
        r = analyse(run, spec)
        path = AGENT / "runs" / run / "photostability_analysis.json"
        path.write_bytes((json.dumps({"run_id": run, **common, **r}, indent=2) + "\n").encode("utf-8"))
        print(f"{run}: first {r['first_frame_pct_of_settled']}%, last {r['last_pct_of_settled']}% of "
              f"settled; drift {r['drift_from_frame0']}; wrote {path.relative_to(AGENT.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
