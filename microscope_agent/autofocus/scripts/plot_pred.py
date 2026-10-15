"""Figure from the out-of-fold predictions saved by eval_synthetic.py.

    uv run python scripts/plot_pred.py outputs/pred_k100x_dinov2_vits14_L1.npz

Three panels, one measure each: predicted vs true signed dz, absolute error by
|dz|, and sign accuracy by |dz|. The -10..10 band is the live-view score range.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK, INK2, GRID, SERIES = "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"


def binned(x, y, edges, fn):
    idx = np.digitize(x, edges) - 1
    return np.array([fn(y[idx == k]) if np.any(idx == k) else np.nan for k in range(len(edges) - 1)])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pred", type=Path)
    args = ap.parse_args()

    d = np.load(args.pred, allow_pickle=True)
    v = d["valid"].astype(bool)
    dz, p = d["dz_dof"][v], d["pred_dz_dof"][v]
    err = np.abs(p - dz)

    plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                         "xtick.color": INK2, "ytick.color": INK2})
    fig, ax = plt.subplots(1, 3, figsize=(13, 4.2), constrained_layout=True)

    a = ax[0]
    lim = 12.5
    a.axhspan(-10, 10, color=GRID, alpha=0.5, lw=0)
    a.plot([-lim, lim], [-lim, lim], color=INK2, lw=1, ls="--")
    a.scatter(dz, p, s=8, color=SERIES, alpha=0.35, lw=0)
    a.set(xlim=(-lim, lim), ylim=(-lim, lim), xlabel="true dz (DoF)",
          ylabel="predicted dz (DoF)", title="Predicted vs true (shaded: score range)")

    edges = np.arange(0, 13, 1.0)
    mid = 0.5 * (edges[:-1] + edges[1:])
    a = ax[1]
    a.plot(mid, binned(np.abs(dz), err, edges, np.median), color=SERIES, lw=2, marker="o", ms=5)
    a.set(xlabel="|true dz| (DoF)", ylabel="median |error| (DoF)", ylim=(0, None),
          title="Error by distance from focus")

    a = ax[2]
    ok = (np.sign(p) == np.sign(dz)).astype(float)
    a.axhline(0.5, color=INK2, lw=1, ls="--")
    a.text(12, 0.52, "chance", color=INK2, ha="right", va="bottom")
    a.plot(mid, binned(np.abs(dz), ok, edges, np.mean), color=SERIES, lw=2, marker="o", ms=5)
    a.set(xlabel="|true dz| (DoF)", ylabel="sign accuracy", ylim=(0.4, 1.02),
          title="Above/below-focus accuracy")

    for a in ax:
        a.grid(color=GRID, lw=0.8)
        a.set_axisbelow(True)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)

    fig.suptitle(f"{args.pred.stem}: {v.sum()} valid frames, "
                 f"MAE {err.mean():.2f} DoF, within 1 DoF {np.mean(err < 1):.0%}",
                 color=INK)
    out = args.pred.with_suffix(".png")
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
