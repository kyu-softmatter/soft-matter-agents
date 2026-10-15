"""Plot a piezo z sweep (live_focus 'w'): DINO score, Vollath F4 and Brenner against z.

    uv run python scripts/plot_zsweep.py D:/AutoFocus/samples/<id>/zsweep_<time>.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK, INK2, GRID, SERIES, MARK = "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6", "#eb6834"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep", type=Path)
    args = ap.parse_args()
    d = json.loads(args.sweep.read_text())
    rows = d["rows"]
    z = np.array([r["z_um"] for r in rows])
    res = d.get("result") or {}

    plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                         "xtick.color": INK2, "ytick.color": INK2})
    fig, ax = plt.subplots(3, 1, figsize=(7.5, 8.5), sharex=True, constrained_layout=True)
    panels = [("dino", "DINO score (DoF, offset applied)", res.get("dino_min_abs_um")),
              ("vollath", "Vollath F4 (centre 518 px)", res.get("vollath_peak_um")),
              ("brenner", "Brenner (centre 518 px)", None)]
    for a, (key, title, mark) in zip(ax, panels):
        v = np.array([r[key] for r in rows])
        if key == "dino":
            for zi, r in zip(z, rows):  # every reading behind the median
                a.scatter([zi] * len(r["dino_all"]), r["dino_all"], s=6, color=SERIES,
                          alpha=0.25, lw=0)
            a.axhline(0, color=INK2, lw=1, ls="--")
        a.plot(z, v, color=SERIES, lw=2, marker="o", ms=4)
        if mark is not None:
            a.axvline(mark, color=MARK, lw=1.5)
            a.text(mark, 0.97, f" {mark:.2f} um", color=INK, va="top",
                   transform=a.get_xaxis_transform())
        a.set_title(title, loc="left", color=INK)
        a.grid(color=GRID, lw=0.8)
        a.set_axisbelow(True)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    ax[-1].set_xlabel("piezo z (um)")
    fig.suptitle(f"{args.sweep.parent.name} / {args.sweep.stem}: {len(rows)} planes "
                 f"(5 frames each)", color=INK)
    out = args.sweep.with_suffix(".png")
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")
    for r in rows:
        print(f"  z {r['z_um']:6.2f}  dino {r['dino']:+6.2f}  vollath {r['vollath']:.4f}  "
              f"brenner {r['brenner']:.4f}  box_max {r['box_max']:.0f}")


if __name__ == "__main__":
    main()
