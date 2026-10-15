"""How many synthetic scenes does the frozen-DINO focus head need?

    uv run python scripts/learning_curve.py --data ../psf-autofocus/data/k100x

Uses the cached features from eval_synthetic.py. A fixed 20% of scenes is held out;
the dz MLP of eval_synthetic.py is trained on growing subsets of the rest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from dino_autofocus.synth.models.preprocess import normalise_cond

import sys
sys.path.insert(0, str(Path(__file__).parent))
from eval_synthetic import load, mlp  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--feat", default="feat_dinov2_vits14_L1.npz")
    ap.add_argument("--sizes", type=int, nargs="+", default=[25, 50, 100, 200, 400, 700, 960])
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    args = ap.parse_args()

    d = load(args.data)
    X = np.hstack([np.load(args.data / args.feat)["x"], normalise_cond(d["cond"])])
    dz, valid, sid = d["dz_dof"], d["valid"], d["scene_id"]
    scenes = np.unique(sid)
    rng = np.random.default_rng(0)
    test = rng.choice(scenes, size=len(scenes) // 5, replace=False)
    pool = np.setdiff1d(scenes, test)
    te = np.isin(sid, test) & valid
    rows = []
    for n in args.sizes:
        for rep in range(args.repeats):
            pick = np.random.default_rng(100 + rep).choice(pool, size=min(n, len(pool)), replace=False)
            tr = np.isin(sid, pick) & valid
            p = mlp(rep).fit(X[tr], dz[tr]).predict(X[te])
            e = np.abs(p - dz[te])
            big = np.abs(dz[te]) >= 1
            rows.append({"scenes": int(len(pick)), "frames": int(tr.sum()), "rep": rep,
                         "mae_dof": float(e.mean()), "median_ae_dof": float(np.median(e)),
                         "within_1dof": float((e < 1).mean()),
                         "sign_acc": float((np.sign(p[big]) == np.sign(dz[te][big])).mean())})
            print(json.dumps(rows[-1]), flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"learning_curve_{args.data.name}.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
