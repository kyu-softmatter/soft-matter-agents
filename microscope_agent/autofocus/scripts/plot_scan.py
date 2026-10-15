"""Overview mosaic + z map of a scan_4x.py run (uv env: needs matplotlib).

    uv run python scripts/plot_scan.py D:/AutoFocus/samples/<id>/scan4x_<stamp>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

BIN = 8


def main() -> None:
    d = Path(sys.argv[1])
    rec = json.loads((d / "scan.json").read_text())
    um_px = rec["um_per_px"] * BIN
    tiles = rec["tiles"]
    # Image -> stage orientation from the sample's stage_camera_calibration M
    # (d_pixels = M @ d_stage, as edge_track measures it). A feature moves WITH the stage,
    # so the sample point at pixel p sits at stage + Minv @ (centre - p): on this stand
    # columns run toward -x and rows toward +y. Only the signs are used here (|angle| ~0.1 deg).
    cal = json.loads((d.parent / "sample.json").read_text()).get("stage_camera_calibration")
    M = np.array(cal["M_px_per_um"]) if cal else np.array([[0.616, 0.0], [0.0, -0.616]])
    flip_lr = M[0, 0] > 0   # +stage x moves features right -> image columns run toward -x
    rows_up = M[1, 1] < 0   # +stage y moves features up -> image rows run toward +y
    xs = [t["x_um"] for t in tiles]
    ys = [t["y_um"] for t in tiles]
    half = rec["fov_um"] / 2
    x0, x1 = min(xs) - half, max(xs) + half
    y0, y1 = min(ys) - half, max(ys) + half
    W, H = int((x1 - x0) / um_px) + 1, int((y1 - y0) / um_px) + 1
    mosaic = np.zeros((H, W), np.float32)
    for t in tiles:
        img = np.load(d / f"{t['name']}.npy").astype(np.float32)
        n = img.shape[0] // BIN
        small = img[:n * BIN, :n * BIN].reshape(n, BIN, n, BIN).mean(axis=(1, 3))
        if flip_lr:
            small = small[:, ::-1]
        if not rows_up:
            small = small[::-1]
        # mosaic row 0 = y0 (drawn with origin="lower")
        c = int((t["x_um"] - half - x0) / um_px)
        r = int((t["y_um"] - half - y0) / um_px)
        mosaic[r:r + n, c:c + n] = small[: H - r, : W - c]
    lo, hi = np.percentile(mosaic[mosaic > 0], (0.5, 99.8))

    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 6.5))
    a.imshow(mosaic, cmap="gray", vmin=lo, vmax=hi, extent=(x0, x1, y0, y1), origin="lower")
    h = rec["hole"]
    a.add_patch(plt.Circle(h["centre_um"], h["diameter_mm"] * 500, fill=False, ec="#eb6834"))
    for t in tiles:
        z = t["z_focus_um"]
        a.text(t["x_um"], t["y_um"], f"{t['name'][5:]}\nz {z if z is None else f'{z:.1f}'}",
               color="#2a78d6", ha="center", va="center", fontsize=9)
    a.set(title=f"{rec['sample']} 4x mosaic", xlabel="stage x (um)", ylabel="stage y (um)")

    # local z map from per-tile sub-blocks
    pts = []
    for t in tiles:
        nb = t["blocks_per_side"]
        step = rec["fov_um"] / nb
        for k, z in enumerate(t["block_z_um"]):
            if z is not None:
                i, j = divmod(k, nb)  # i = image row block, j = column block
                fx = (j + 0.5) * step - half  # offset from the tile centre along the image
                fy = (i + 0.5) * step - half
                pts.append((t["x_um"] + (-fx if flip_lr else fx),
                            t["y_um"] + (fy if rows_up else -fy), z))
    if pts:
        p = np.array(pts)
        sc = b.scatter(p[:, 0], p[:, 1], c=p[:, 2], s=120, marker="s", cmap="viridis")
        fig.colorbar(sc, ax=b, label="best-focus ZDrive (um)")
        A = np.c_[p[:, 0], p[:, 1], np.ones(len(p))]
        coef, *_ = np.linalg.lstsq(A, p[:, 2], rcond=None)
        rms = float(np.sqrt(np.mean((A @ coef - p[:, 2]) ** 2)))
        b.set_title(f"focus z map: tilt {coef[0] * 1000:.2f} / {coef[1] * 1000:.2f} um/mm "
                    f"(x/y), plane rms {rms:.1f} um")
    b.set(xlim=(x0, x1), ylim=(y0, y1), aspect="equal", xlabel="stage x (um)")
    fig.tight_layout()
    fig.savefig(d / "scan_overview.png", dpi=130)
    print(d / "scan_overview.png")


if __name__ == "__main__":
    main()
