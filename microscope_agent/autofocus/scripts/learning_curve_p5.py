"""Learning curve of the frozen-DINO dz head on the 5 um particle dataset (farm_p5.py).

    uv run python scripts/learning_curve_p5.py

Reads every finished chunk (manifest.json present) of data/p5_<obj>/, caches DINO
features next to each chunk, and re-applies the validity gates with a looser
focus-peak prominence (--min-prominence; the gate inputs are stored per frame, so
this needs no regeneration). 20% of scenes per objective are held out; the dz MLP
of eval_synthetic.py is trained on growing, objective-balanced subsets of the rest.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from dino_autofocus.synth.models.preprocess import normalise_cond

sys.path.insert(0, str(Path(__file__).parent))
from eval_synthetic import mlp  # noqa: E402

OBJECTIVES = ("4x", "10x", "20x", "40x", "60x", "100x")
KEYS = ("image", "dz_dof", "cond", "scene_id", "snr", "saturated", "label_residual_dof",
        "rival_peak_ratio", "edge_peak", "peak_prominence")


def stable_shards(root: Path, age_s: float = 60.0) -> list[Path]:
    """All shards of a finished chunk; of an unfinished one, those not written lately."""
    shards = sorted(root.glob("shard_*.npz"))
    if (root / "manifest.json").exists():
        return shards
    return [p for p in shards if time.time() - p.stat().st_mtime > age_s]


def load_chunk(shards: list[Path]) -> dict:
    parts = [np.load(p, allow_pickle=True) for p in shards]
    return {k: np.concatenate([p[k] for p in parts]) for k in KEYS}


def gate(d: dict, min_prominence: float, span: float = 15.0) -> np.ndarray:
    """dataset.render_scene's validity mask, with the prominence threshold as given."""
    dz = d["dz_dof"]
    return (np.isfinite(dz) & (d["snr"] >= 3.0) & (d["saturated"] <= 0.2)
            & (np.abs(np.nan_to_num(dz, nan=1e9)) <= span)
            & (np.abs(d["label_residual_dof"]) <= 0.6) & (d["rival_peak_ratio"] < 0.5)
            & ~d["edge_peak"].astype(bool) & (d["peak_prominence"] >= min_prominence))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--model", default="dinov2_vits14")
    ap.add_argument("--min-prominence", type=float, default=1.5)
    ap.add_argument("--sizes", type=int, nargs="+", default=[10, 25, 50, 100, 200, 400])
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--out", type=Path, default=Path("outputs"))
    args = ap.parse_args()

    extractor = None
    X, dz, valid, sid, obj = [], [], [], [], []
    for k, o in enumerate(OBJECTIVES):
        for root in sorted(p for p in (args.data / f"p5_{o}").glob("chunk_*") if p.is_dir()):
            shards = stable_shards(root)
            if not shards:
                continue
            d = load_chunk(shards)
            # cache keyed by the shard count, so a chunk that grows is re-extracted
            fpath = root / f"feat_{args.model}_L1_{len(shards)}shards.npz"
            if fpath.exists():
                f = np.load(fpath)["x"]
            else:
                if extractor is None:
                    from dino_autofocus.backbone import DinoExtractor
                    extractor = DinoExtractor(args.model, 1)
                t = time.perf_counter()
                f = extractor(d["image"], batch=64)
                np.savez_compressed(fpath, x=f)
                print(f"  features {root} {f.shape} in {time.perf_counter() - t:.0f}s", flush=True)
            X.append(np.hstack([f, normalise_cond(d["cond"])]))
            dz.append(d["dz_dof"]); valid.append(gate(d, args.min_prominence))
            sid.append(d["scene_id"]); obj.append(np.full(len(f), k))
    X, dz, valid = np.vstack(X), np.concatenate(dz), np.concatenate(valid)
    sid, obj = np.concatenate(sid), np.concatenate(obj)

    rng = np.random.default_rng(0)
    test_mask = np.zeros(len(sid), bool)
    pools = {}
    print(f"\n{'obj':5s} scenes  frames  valid(prom>={args.min_prominence})")
    for k, o in enumerate(OBJECTIVES):
        sc = np.unique(sid[obj == k])
        if len(sc) == 0:
            continue
        test = rng.choice(sc, size=max(1, len(sc) // 5), replace=False)
        test_mask |= np.isin(sid, test)
        pools[k] = np.setdiff1d(sc, test)
        m = obj == k
        print(f"{o:5s} {len(sc):6d}  {m.sum():6d}  {valid[m].mean():6.1%}")
    te = test_mask & valid

    rows = []
    for n in args.sizes:                                  # scenes per objective
        if all(n > len(p) for p in pools.values()):
            break
        for rep in range(args.repeats):
            r2 = np.random.default_rng(100 + rep)
            pick = np.concatenate([r2.choice(p, size=min(n, len(p)), replace=False)
                                   for p in pools.values()])
            tr = np.isin(sid, pick) & valid & ~test_mask
            t = time.perf_counter()
            p = mlp(rep).fit(X[tr], dz[tr]).predict(X[te])
            e = np.abs(p - dz[te])
            # distance from focus regardless of side: learnable even where the sign is not
            pa = mlp(rep).fit(X[tr], np.abs(dz[tr])).predict(X[te])
            ea = np.abs(pa - np.abs(dz[te]))
            row = {"scenes_per_obj": n, "train_frames": int(tr.sum()), "rep": rep,
                   "mae_dof": float(e.mean()), "median_ae_dof": float(np.median(e)),
                   "within_1dof": float((e < 1).mean()), "abs_mae_dof": float(ea.mean()),
                   "per_obj": {}, "per_obj_abs": {}}
            big = np.abs(dz[te]) >= 1
            row["sign_acc"] = float((np.sign(p[big]) == np.sign(dz[te][big])).mean())
            for k in pools:
                m = obj[te] == k
                row["per_obj"][OBJECTIVES[k]] = float(e[m].mean())
                row["per_obj_abs"][OBJECTIVES[k]] = float(ea[m].mean())
                big_k = m & big
                row.setdefault("per_obj_sign", {})[OBJECTIVES[k]] = float(
                    (np.sign(p[big_k]) == np.sign(dz[te][big_k])).mean())
            rows.append(row)
            print(f"  {n:4d} scenes/obj ({tr.sum():6d} frames) rep {rep}: MAE {row['mae_dof']:.2f} "
                  f"median {row['median_ae_dof']:.2f}  <1DoF {row['within_1dof']:.2f}  "
                  f"sign {row['sign_acc']:.2f}  |dz| MAE {row['abs_mae_dof']:.2f}  [{time.perf_counter() - t:.0f}s]", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "learning_curve_p5.json"
    out.write_text(json.dumps(rows, indent=1))
    plot(rows, [OBJECTIVES[k] for k in pools], args.out / "learning_curve_p5.png")
    print(f"wrote {out}")


def plot(rows, objs, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sizes = sorted({r["scenes_per_obj"] for r in rows})
    mean = lambda f: [np.mean([f(r) for r in rows if r["scenes_per_obj"] == n]) for n in sizes]
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    ax[0].plot(sizes, mean(lambda r: r["mae_dof"]), "o-", color="k", lw=2, label="all")
    for o in objs:
        ax[0].plot(sizes, mean(lambda r, o=o: r["per_obj"][o]), "o-", lw=1, label=o)
    ax[0].set(xscale="log", xlabel="training scenes per objective", ylabel="test MAE (DoF)",
              title="signed dz error, held-out scenes")
    ax[1].plot(sizes, mean(lambda r: r["abs_mae_dof"]), "o-", color="k", lw=2, label="all")
    for o in objs:
        ax[1].plot(sizes, mean(lambda r, o=o: r["per_obj_abs"][o]), "o-", lw=1, label=o)
    ax[1].set(xscale="log", xlabel="training scenes per objective", ylabel="test MAE (DoF)",
              title="|dz| error (distance only)")
    ax[1].legend(fontsize=8)
    ax[0].legend(fontsize=8)
    for o in objs:
        ax[2].plot(sizes, mean(lambda r, o=o: r["per_obj_sign"][o]), "o-", lw=1, label=o)
    ax[2].axhline(0.5, color="gray", ls=":")
    ax[2].set(xscale="log", xlabel="training scenes per objective", ylim=(0.4, 1),
              title="sign correct, |dz| >= 1 DoF")
    ax[2].legend(fontsize=8)
    fig.suptitle("Frozen DINOv2-S + MLP head, 5 um particles, 6 objectives (+-15 DoF)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)


if __name__ == "__main__":
    main()
