"""End-to-end check of FocusScorer on synthetic frames with known defocus, no hardware.

    uv run python scripts/check_scorer.py --head outputs/heads/head_k100x_dinov2_vits14_L1.npz

Pastes four 224-px frames of one synthetic focal plane into a dark 2400 x 2400 sensor
(their own camera noise included), scores the full frame as the live view does, and
compares with the label. Uses scenes the head was trained on, so it checks the plumbing
(tiling, preprocessing, fusion, timing), not generalisation -- that is train_head's CV.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from dino_autofocus.live import FocusScorer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", type=Path, required=True)
    ap.add_argument("--data", type=Path, default=Path("data/k100x"))
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()

    shard = np.load(sorted(args.data.glob("shard_*.npz"))[0], allow_pickle=True)
    img, dz, valid, scene = shard["image"], shard["dz_dof"], shard["valid"], shard["scene_id"]
    rng = np.random.default_rng(0)
    scorer = FocusScorer(args.head)
    scorer(np.full((2400, 2400), 100, np.uint16))  # warm-up (CUDA init)

    rows, times = [], []
    for i in rng.choice(np.where(valid)[0], size=args.n, replace=False):
        same = np.where((scene == scene[i]) & (np.abs(dz - dz[i]) < 1e-6))[0]
        bg = int(np.median(img[i]))
        frame = rng.normal(bg, 2, (2400, 2400)).clip(0, 65535).astype(np.uint16)
        # on the 112-px tile grid, so each scored tile is exactly one synthetic frame
        for j, (y, x) in enumerate([(224, 336), (896, 1568), (1568, 560), (1680, 1904)]):
            frame[y : y + 224, x : x + 224] = img[same[j % len(same)]]
        t = time.perf_counter()
        r = scorer(frame)
        times.append(time.perf_counter() - t)
        rows.append((dz[i], r.score, r.sigma, r.n_used))

    rows = np.array([(a, np.nan if b is None else b, np.nan if c is None else c, d)
                     for a, b, c, d in rows], dtype=float)
    ok = np.isfinite(rows[:, 1])
    err = np.abs(rows[ok, 1] - rows[ok, 0])
    print(f"{ok.sum()}/{len(rows)} frames read; |error| median {np.median(err):.2f} DoF, "
          f"mean {err.mean():.2f}; |err| <= sigma {np.mean(err <= rows[ok, 2]):.0%}")
    print(f"tiles used per frame {rows[:, 3].mean():.1f}; "
          f"score time median {1e3 * np.median(times):.0f} ms, p90 {1e3 * np.percentile(times, 90):.0f} ms")
    for a, b, c, d in rows[:8]:
        print(f"  true {a:+6.2f}  score {b:+6.2f} +- {c:4.2f}  ({int(d)} tiles)")


if __name__ == "__main__":
    main()
