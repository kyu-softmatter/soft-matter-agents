"""Train the live focus-score head on cached frozen-DINO features (eval_synthetic.py makes them).

    uv run python scripts/train_head.py --data data/k100x

Heads, all on [CLS | mean patch] of dinov2_vits14 (optionally + the log10 signal scalar):
  dz     MLP regressor, signed defocus in DoF (dz = stage - best focus)
  err    ridge on the dz head's out-of-fold |error|  -> per-frame sigma
  valid  logistic: can this frame be read at all (blank, low SNR, ambiguous scene)
Out-of-fold metrics are 5-fold grouped by scene; the saved heads are refit on everything.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from dino_autofocus.focus.head import from_pipelines
from dino_autofocus.focus.head import save as save_head
from dino_autofocus.synth.models.preprocess import COND_SCALE

KEYS = ("dz_dof", "valid", "cond", "scene_id", "family")


def load(root: Path) -> dict[str, np.ndarray]:
    parts = [np.load(p, allow_pickle=True) for p in sorted(root.glob("shard_*.npz"))]
    return {k: np.concatenate([p[k] for p in parts]) for k in KEYS}


def signal_feature(cond: np.ndarray) -> np.ndarray:
    """log10 detected photons per pixel, scaled exactly as synth normalise_cond does."""
    mu, sd = COND_SCALE["log10_signal"]
    return ((cond[:, 4] - mu) / sd)[:, None].astype(np.float32)


def mlp(seed: int = 0):
    return make_pipeline(StandardScaler(), MLPRegressor(
        hidden_layer_sizes=(256, 128), alpha=1e-3, early_stopping=True, max_iter=400,
        random_state=seed))


def oof(X, y, groups, mask, make) -> np.ndarray:
    pred = np.full(len(y), np.nan)
    for tr, te in GroupKFold(5).split(X, y, groups):
        tr = tr[mask[tr]]
        pred[te] = make().fit(X[tr], y[tr]).predict(X[te])
    return pred


def metrics(dz, p, v) -> dict:
    e = np.abs(p[v] - dz[v])
    big = v & (np.abs(dz) >= 1)
    near = v & (np.abs(dz) < 1)
    return {"mae_dof": float(e.mean()), "median_ae_dof": float(np.median(e)),
            "within_1dof": float(np.mean(e < 1)),
            "sign_acc_|dz|>=1": float(np.mean(np.sign(p[big]) == np.sign(dz[big]))),
            "near_focus_mae_dof": float(np.mean(np.abs(p[near] - dz[near])))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--model", default="dinov2_vits14")
    ap.add_argument("--n-layers", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("outputs/heads"))
    args = ap.parse_args()

    tag = f"{args.model}_L{args.n_layers}"
    d = load(args.data)
    feats = np.load(args.data / f"feat_{tag}.npz")["x"].astype(np.float32)
    dz, v, g = d["dz_dof"].astype(np.float64), d["valid"].astype(bool), d["scene_id"]
    print(f"{len(dz)} frames, {v.sum()} valid, features {feats.shape}")

    variants = {"dino": feats, "dino+signal": np.hstack([feats, signal_feature(d["cond"])])}
    report = {"data": str(args.data), "backbone": tag, "variants": {}}
    for name, X in variants.items():
        t = time.perf_counter()
        p = oof(X, dz, g, v, mlp)
        report["variants"][name] = metrics(dz, p, v)
        print(f"  {name:12s} {report['variants'][name]}  ({time.perf_counter() - t:.0f}s)")
        variants[name] = (X, p)

    # Deploy without the signal scalar unless it clearly helps: it needs the camera gain in
    # e-/ADU, which has not been measured on this Kinetix, and a wrong gain would shift it.
    gain = (report["variants"]["dino"]["mae_dof"]
            - report["variants"]["dino+signal"]["mae_dof"])
    chosen = "dino+signal" if gain > 0.25 else "dino"
    X, p_oof = variants[chosen]
    report["chosen"] = chosen
    print(f"chosen: {chosen} (signal scalar improves MAE by {gain:.2f} DoF)")

    # Uncertainty: predict the dz head's own out-of-fold |error| from the features.
    err = np.abs(p_oof - dz)
    err_head = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-1, 4, 11)))
    log_err = np.log(err[v] + 0.05)
    err_oof = np.full(len(dz), np.nan)
    for tr, te in GroupKFold(5).split(X[v], log_err, g[v]):
        m = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-1, 4, 11)))
        err_oof[np.where(v)[0][te]] = np.exp(m.fit(X[v][tr], log_err[tr]).predict(X[v][te]))
    # sigma such that |err| <= sigma about 68% of the time (Gaussian 1-sigma coverage)
    k = float(np.quantile(err[v] / err_oof[v], 0.68))
    report["sigma_scale"] = k
    cover = float(np.mean(err[v] <= k * err_oof[v]))
    rho = float(np.corrcoef(np.log(err[v] + 0.05), np.log(err_oof[v]))[0, 1])
    report["sigma"] = {"coverage_1sigma": cover, "corr_log_err": rho}
    print(f"sigma: scale {k:.2f}, 1-sigma coverage {cover:.0%}, corr(log err) {rho:.2f}")

    # Validity: blank / low-SNR / ambiguous frames should say so instead of a confident 0.
    val_head = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
    pv = np.full(len(dz), np.nan)
    for tr, te in GroupKFold(5).split(X, v, g):
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
        pv[te] = m.fit(X[tr], v[tr]).predict_proba(X[te])[:, 1]
    acc = float(np.mean((pv > 0.5) == v))
    report["valid_head"] = {"accuracy": acc, "base_rate": float(v.mean())}
    print(f"valid head: accuracy {acc:.1%} (base rate {v.mean():.1%})")

    t = time.perf_counter()
    dz_head = mlp().fit(X[v], dz[v])
    err_head.fit(X[v], log_err)
    val_head.fit(X, v)
    print(f"refit on all data in {time.perf_counter() - t:.0f}s")

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"head_{args.data.name}_{tag}.joblib"
    head = {"backbone": args.model, "n_layers": args.n_layers, "tile_px": 224,
            "uses_signal": chosen == "dino+signal", "dz": dz_head, "err": err_head,
            "err_offset": 0.05, "sigma_scale": k, "valid": val_head,
            "trained_on": str(args.data), "report": report}
    joblib.dump(head, path)  # the pipelines, for further training; never shipped
    npz = save_head(path.with_suffix(".npz"), *from_pipelines(head))  # what FocusScorer loads
    (args.out / f"head_{args.data.name}_{tag}.json").write_text(json.dumps(report, indent=2))
    print(f"wrote {path} and {npz}")


if __name__ == "__main__":
    main()
