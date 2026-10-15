#!/usr/bin/env python3
"""Look at a generated dataset: focal series, per-geometry frames, distributions.

Three figures:

``dataset_series.png``
    One focal series per row, planes ordered by their defocus label. The label
    is printed on each frame, so a mislabelled scene is visible as a sharpest
    frame that is not the one marked 0.0 -- which is the check worth doing by
    eye before training on anything.
``dataset_geometries.png``
    Near-focus frames grouped by geometry, at the objective each was drawn with.
``dataset_stats.png``
    Label balance, SNR, per-family counts, feature coverage, and the rejection
    breakdown.
"""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


from dino_autofocus.synth.sim.dataset import ShardedArrays

warnings.filterwarnings("ignore")


def show(ax, img, vmax=None):
    a = np.asarray(img, dtype=np.float64)
    lo = np.percentile(a, 1)
    hi = vmax if vmax is not None else np.percentile(a, 99.7)
    ax.imshow(a, cmap="magma", vmin=lo, vmax=max(hi, lo + 1))
    ax.set_xticks([]); ax.set_yticks([])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/train")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--series", type=int, default=6, help="scenes to show as focal series")
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    a = ShardedArrays(args.data)
    print(a.summary())

    sid = a["scene_id"]; dz = a["dz_dof"]; valid = a["valid"].astype(bool)
    geom = a["geometry"].astype(str); fam = a["family"].astype(str)
    system = a["system"].astype(str)
    rng = np.random.default_rng(args.seed)

    # ---------------- figure 1: focal series ----------------
    # pick scenes that are usable and whose sample is not empty
    good = np.unique(sid[valid & (geom != "empty")])
    pick = rng.choice(good, size=min(args.series, len(good)), replace=False)
    n_col = int(np.median([np.sum(sid == s) for s in pick]))
    fig, axes = plt.subplots(len(pick), n_col, figsize=(1.35 * n_col, 1.55 * len(pick)),
                             squeeze=False)
    for i, s in enumerate(pick):
        rows = np.flatnonzero(sid == s)
        rows = rows[np.argsort(dz[rows])][:n_col]
        vmax = np.percentile(a["image"][rows[len(rows) // 2]], 99.7)
        for j in range(n_col):
            ax = axes[i][j]
            if j >= len(rows):
                ax.axis("off"); continue
            r = rows[j]
            show(ax, a["image"][r], vmax=vmax)
            sharp = a["sharpness"][r]
            ax.set_title(f"{dz[r]:+.1f}", fontsize=6.5,
                         color=("crimson" if abs(dz[r]) < 1.0 else "black"),
                         fontweight=("bold" if sharp > 0.9 else "normal"), pad=1.5)
            if not valid[r]:
                ax.set_xlabel("invalid", fontsize=5.5, color="grey", labelpad=1)
        axes[i][0].set_ylabel(f"{geom[rows[0]]}\n{system[rows[0]]}", fontsize=6,
                              rotation=0, ha="right", va="center")
    fig.suptitle("Focal series from the dataset — title = defocus label (DoF), "
                 "bold = sharpest plane, red = within 1 DoF", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    fig.savefig(out / "dataset_series.png", dpi=140)
    print(f"wrote {out / 'dataset_series.png'}")

    # ---------------- figure 2: geometries near focus ----------------
    kinds = [g for g in sorted(set(geom)) if g != "empty"]
    near = valid & (np.abs(dz) < 1.0)
    per = 4
    fig, axes = plt.subplots(len(kinds), per, figsize=(1.5 * per, 1.5 * len(kinds)),
                             squeeze=False)
    for i, g in enumerate(kinds):
        rows = np.flatnonzero(near & (geom == g))
        if rows.size == 0:
            rows = np.flatnonzero(valid & (geom == g))
        sel = rng.choice(rows, size=min(per, rows.size), replace=False) if rows.size else []
        for j in range(per):
            ax = axes[i][j]
            if j >= len(sel):
                ax.axis("off"); continue
            show(ax, a["image"][sel[j]])
            ax.set_title(f"{system[sel[j]]}  dz={dz[sel[j]]:+.2f}", fontsize=5.5, pad=1.5)
        axes[i][0].set_ylabel(g.replace("_", "\n"), fontsize=6.5, rotation=0,
                              ha="right", va="center")
    fig.suptitle("Near-focus frames by geometry (|defocus| < 1 DoF)", fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.975])
    fig.savefig(out / "dataset_geometries.png", dpi=140)
    print(f"wrote {out / 'dataset_geometries.png'}")

    # ---------------- figure 3: distributions ----------------
    fig, ax = plt.subplots(2, 3, figsize=(13, 6.6))

    ax[0, 0].hist(dz[valid], bins=60, color="#4C72B0")
    ax[0, 0].axvline(0, color="k", ls=":", lw=0.9)
    neg, pos = int((dz[valid] < 0).sum()), int((dz[valid] > 0).sum())
    ax[0, 0].set_title(f"defocus label, valid records\n{neg} negative / {pos} positive",
                       fontsize=9)
    ax[0, 0].set_xlabel("defocus (DoF)", fontsize=8)

    snr = a["snr"]
    ax[0, 1].hist(np.log10(np.clip(snr, 1e-2, None)), bins=60, color="#DD8452")
    ax[0, 1].axvline(np.log10(3.0), color="crimson", ls="--", lw=1,
                     label="SNR floor = 3")
    ax[0, 1].set_title(f"peak SNR (median {np.median(snr[valid]):.0f} on valid)", fontsize=9)
    ax[0, 1].set_xlabel("log10 SNR", fontsize=8); ax[0, 1].legend(fontsize=7)

    fams, counts = np.unique(fam, return_counts=True)
    vcounts = [int(valid[fam == f].sum()) for f in fams]
    y = np.arange(len(fams))
    ax[0, 2].barh(y, counts, color="#CCCCCC", label="all")
    ax[0, 2].barh(y, vcounts, color="#55A868", label="valid")
    ax[0, 2].set_yticks(y); ax[0, 2].set_yticklabels(fams, fontsize=7.5)
    ax[0, 2].set_title("records per geometry family", fontsize=9)
    ax[0, 2].legend(fontsize=7)

    ev = a["edge_valid"].astype(bool); xv = a["encircled_valid"].astype(bool)
    bins_dz = np.linspace(-14, 14, 15)
    cen = 0.5 * (bins_dz[1:] + bins_dz[:-1])
    for mask, lab, c in ((ev, "edge profile", "#4C72B0"),
                         (xv, "encircled energy", "#DD8452"),
                         (ev | xv, "either", "#55A868")):
        frac = [mask[(dz >= lo) & (dz < hi)].mean() if ((dz >= lo) & (dz < hi)).any() else np.nan
                for lo, hi in zip(bins_dz[:-1], bins_dz[1:])]
        ax[1, 0].plot(cen, frac, "o-", ms=3, lw=1.2, label=lab, color=c)
    ax[1, 0].set_title("physics-feature availability vs defocus", fontsize=9)
    ax[1, 0].set_xlabel("defocus (DoF)", fontsize=8)
    ax[1, 0].set_ylabel("fraction of frames", fontsize=8)
    ax[1, 0].legend(fontsize=7); ax[1, 0].set_ylim(0, 1)

    # sharpness vs label: the shape of the focus response the model must invert
    for f in fams:
        m = valid & (fam == f)
        o = np.argsort(dz[m])
        d, sh = dz[m][o], a["sharpness"][m][o]
        k = max(len(d) // 40, 1)
        db = np.array([d[i:i + k].mean() for i in range(0, len(d) - k, k)])
        sb = np.array([sh[i:i + k].mean() for i in range(0, len(sh) - k, k)])
        ax[1, 1].plot(db, sb, lw=1.2, label=f)
    ax[1, 1].axvline(0, color="k", ls=":", lw=0.9)
    ax[1, 1].set_title("normalised sharpness vs label, by family", fontsize=9)
    ax[1, 1].set_xlabel("defocus (DoF)", fontsize=8); ax[1, 1].legend(fontsize=7)

    reasons = {
        "ambiguous peak": float(a["ambiguous"].mean()),
        "peak on window edge": float(a["edge_peak"].mean()),
        "SNR below floor": float((snr < 3.0).mean()),
        "label residual too big": float((np.abs(a["label_residual_dof"]) > 0.6).mean()),
    }
    names = list(reasons); vals = [100 * reasons[n] for n in names]
    ax[1, 2].barh(np.arange(len(names)), vals, color="#C44E52")
    ax[1, 2].set_yticks(np.arange(len(names)))
    ax[1, 2].set_yticklabels(names, fontsize=7.5)
    ax[1, 2].set_xlabel("% of all records (reasons overlap)", fontsize=8)
    ax[1, 2].set_title(f"rejection reasons — {100 * valid.mean():.1f}% kept", fontsize=9)

    for a_ in ax.ravel():
        a_.tick_params(labelsize=7)
    fig.suptitle(f"{len(a)} records from {len(np.unique(sid))} scenes", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out / "dataset_stats.png", dpi=140)
    print(f"wrote {out / 'dataset_stats.png'}")


if __name__ == "__main__":
    main()
