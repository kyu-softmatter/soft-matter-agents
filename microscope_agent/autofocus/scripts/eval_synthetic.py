"""Frozen-DINOv2 vs classical focus features on synthetic z-stacks (scripts/make_dataset.py).

    uv run python scripts/eval_synthetic.py --data data/synth320 --model dinov2_vits14

Per frame: signed dz (DoF units, dz = stage - best focus) and |dz| from one image.
Per stack: pick the plane with the smallest predicted |dz| and compare with the
classical z-scan (argmax of a sharpness metric + parabola).
Splits are 5-fold grouped by scene, so no scene is in both train and test.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from dino_autofocus.backbone import DinoExtractor
from dino_autofocus.synth.models.preprocess import normalise_cond
from dino_autofocus.synth.sim.metrics import RELIABLE, argmax_parabolic, focus_score

KEYS = (
    "image",
    "dz_dof",
    "stage_um",
    "best_stage_um",
    "dof_um",
    "valid",
    "cond",
    "descriptors",
    "scene_id",
    "family",
)


def load(root: Path) -> dict[str, np.ndarray]:
    parts = [np.load(p, allow_pickle=True) for p in sorted(root.glob("shard_*.npz"))]
    return {k: np.concatenate([p[k] for p in parts]) for k in KEYS}


def cached(path: Path, fn):
    if path.exists():
        return np.load(path)["x"]
    t = time.perf_counter()
    x = fn()
    print(f"  computed {path.name} {x.shape} in {time.perf_counter() - t:.0f}s")
    np.savez_compressed(path, x=x)
    return x


def classical_metrics(d) -> np.ndarray:
    rows = []
    for im in d["image"]:
        im = im.astype(np.float64)
        rows.append([focus_score(im, k) for k in RELIABLE])
    return np.array(rows)


def signed_log(m: np.ndarray, floor: float = 1e-3) -> np.ndarray:
    """Monotonic and sign-preserving (vollath4 goes negative out of focus)."""
    return np.sign(m) * np.log10(1 + np.abs(m) / floor)


def ridge():
    return make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 4, 13)))


def mlp(seed=0):
    return make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=(256, 128),
            alpha=1e-3,
            early_stopping=True,
            max_iter=400,
            random_state=seed,
        ),
    )


def crossval(X, y, groups, make, mask):
    """Out-of-fold predictions for every row; models fit on rows where mask is True."""
    pred = np.full(len(y), np.nan)
    for tr, te in GroupKFold(5).split(X, y, groups):
        tr = tr[mask[tr]]
        model = make().fit(X[tr], y[tr])
        pred[te] = model.predict(X[te])
    return pred


def frame_metrics(dz, pred_dz, pred_abs, valid):
    e = pred_dz[valid] - dz[valid]
    big = valid & (np.abs(dz) >= 1)
    return {
        "mae_dof": float(np.mean(np.abs(e))),
        "median_ae_dof": float(np.median(np.abs(e))),
        "within_1dof": float(np.mean(np.abs(e) < 1)),
        "sign_acc_|dz|>=1": float(np.mean(np.sign(pred_dz[big]) == np.sign(dz[big]))),
        "abs_mae_dof": float(np.mean(np.abs(pred_abs[valid] - np.abs(dz[valid])))),
    }


def stack_pick(d, score, higher_is_focus):
    """Per scene: best-plane estimate from a per-frame score, error in DoF."""
    errs = []
    for s in np.unique(d["scene_id"]):
        i = np.where(d["scene_id"] == s)[0]
        if not d["valid"][i].all():
            continue
        i = i[np.argsort(d["stage_um"][i])]
        sc = score[i] if higher_is_focus else -score[i]
        z = argmax_parabolic(d["stage_um"][i], sc)
        errs.append(abs(z - d["best_stage_um"][i[0]]) / d["dof_um"][i[0]])
    errs = np.array(errs)
    return {
        "n_stacks": len(errs),
        "median_err_dof": float(np.median(errs)),
        "p90_err_dof": float(np.percentile(errs, 90)),
        "within_0.25dof": float(np.mean(errs < 0.25)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--model", default="dinov2_vits14")
    ap.add_argument("--n-layers", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    ap.add_argument(
        "--fp16",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="autocast fp16 feature extraction (default, as on the microscope PC); "
        "--no-fp16 on GPUs without tensor cores. fp32 features are cached as *_fp32.npz "
        "so train_head.py, which reads feat_<model>_L<n>.npz, never mixes the two",
    )
    args = ap.parse_args()

    d = load(args.data)
    valid = d["valid"]
    print(f"{len(valid)} frames, {len(np.unique(d['scene_id']))} scenes, {valid.mean():.0%} valid")

    tag = f"{args.model}_L{args.n_layers}" + ("" if args.fp16 else "_fp32")
    dino = cached(
        args.data / f"feat_{tag}.npz",
        lambda: DinoExtractor(args.model, args.n_layers, fp16=args.fp16)(d["image"]),
    )
    raw = cached(args.data / "feat_classical_raw.npz", lambda: classical_metrics(d))
    clas = signed_log(raw)
    cond = normalise_cond(d["cond"])
    desc = np.nan_to_num(d["descriptors"])

    feature_sets = {
        "classical(metrics+desc+cond)": np.hstack([clas, desc, cond]),
        f"dino[{tag}]+cond": np.hstack([dino, cond]),
        f"dino[{tag}]+classical": np.hstack([dino, clas, desc, cond]),
    }
    dz, groups = d["dz_dof"], d["scene_id"]
    results = {
        "data": str(args.data),
        "n_frames": int(len(dz)),
        "fp16": args.fp16,
        "frame": {},
        "stack": {},
    }

    for fname, X in feature_sets.items():
        for hname, make in (("ridge", ridge), ("mlp", mlp)):
            t = time.perf_counter()
            p_dz = crossval(X, dz, groups, make, valid)
            p_abs = crossval(X, np.abs(dz), groups, make, valid)
            key = f"{fname} / {hname}"
            results["frame"][key] = frame_metrics(dz, p_dz, p_abs, valid)
            results["stack"][key] = stack_pick(d, p_abs, higher_is_focus=False)
            print(f"  {key}: {time.perf_counter() - t:.0f}s")

    for k, name in enumerate(RELIABLE):
        # log scale: the parabola through the peak fits a log-sharpness curve better
        results["stack"][f"z-scan argmax {name}"] = stack_pick(d, clas[:, k], True)

    per_family = {}
    X = feature_sets[f"dino[{tag}]+cond"]
    p = crossval(X, dz, groups, mlp, valid)
    for fam in np.unique(d["family"]):
        m = valid & (d["family"] == fam)
        per_family[fam] = {"n": int(m.sum()), "mae_dof": float(np.mean(np.abs(p[m] - dz[m])))}
    results["per_family_dino_mlp"] = per_family

    args.out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.out / f"pred_{args.data.name}_{tag}.npz",
        dz_dof=dz,
        pred_dz_dof=p,
        valid=valid,
        family=d["family"],
        scene_id=groups,
    )
    out = args.out / f"eval_{args.data.name}_{tag}.json"
    out.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
