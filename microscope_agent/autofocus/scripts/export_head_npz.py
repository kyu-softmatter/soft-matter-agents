"""Convert a trained focus head (joblib of scikit-learn pipelines) to the pickle-free `.npz`.

    uv run python scripts/export_head_npz.py outputs/heads/head_k100x_dinov2_vits14_L1.joblib

Writes `<same name>.npz` next to it and checks on random features that the numpy head gives
the pipelines' outputs. Only open joblib files you trained yourself: loading one runs code.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np

from dino_autofocus.focus.head import NpzHead, from_pipelines, save


def max_differences(h: dict, head: NpzHead, n: int = 512, seed: int = 0) -> dict[str, float]:
    X = np.random.default_rng(seed).normal(size=(n, len(head.arrays["dz_mean"])))
    return {"dz": float(np.max(np.abs(h["dz"].predict(X) - head.dz(X)))),
            "log_err": float(np.max(np.abs(h["err"].predict(X) - head.log_err(X)))),
            "p_valid": float(np.max(np.abs(h["valid"].predict_proba(X)[:, 1] - head.p_valid(X))))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("head", type=Path, help="head_*.joblib written by scripts/train_head.py")
    ap.add_argument("--out", type=Path, default=None, help="default: same name, .npz")
    args = ap.parse_args()
    h = joblib.load(args.head)
    meta, arrays = from_pipelines(h)
    out = save(args.out or args.head.with_suffix(".npz"), meta, arrays)
    diff = max_differences(h, NpzHead.load(out))
    print(f"wrote {out}; max |numpy - sklearn| on random features: {diff}")
    if max(diff.values()) > 1e-9:
        raise SystemExit("numpy head does not reproduce the pipelines")


if __name__ == "__main__":
    main()
