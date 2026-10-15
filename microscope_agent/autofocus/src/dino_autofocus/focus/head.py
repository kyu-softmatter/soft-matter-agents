"""The DINO focus head as plain arrays in an `.npz` file, scored with numpy.

A head used to be a joblib pickle of three scikit-learn pipelines; loading a pickle runs
code, so a head file from a public repository must not be one.
The `.npz` holds only arrays and is opened with `allow_pickle=False`.

    dz     StandardScaler -> MLPRegressor (relu hidden layers, identity output)
    err    StandardScaler -> RidgeCV          log of the expected |dz error|
    valid  StandardScaler -> LogisticRegression (binary)  P(frame is readable)

Keys: `meta` (a JSON string: backbone, n_layers, tile_px, uses_signal, sigma_scale, ...),
`{dz,err,valid}_mean` / `_scale` (the scalers), `dz_W<i>` / `dz_b<i>` (MLP layers),
`err_coef`, `err_intercept`, `valid_coef`, `valid_intercept`.
`scripts/export_head_npz.py` writes one from a trained pipeline set.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

FORMAT = "dino-autofocus-head"
VERSION = 1


@dataclass(frozen=True)
class NpzHead:
    meta: dict[str, Any]
    arrays: dict[str, np.ndarray]

    @classmethod
    def load(cls, path: str | Path) -> NpzHead:
        with np.load(path, allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        meta = json.loads(str(arrays.pop("meta")))
        if meta.get("format") != FORMAT or meta.get("version") != VERSION:
            raise ValueError(f"{path}: not a {FORMAT} v{VERSION} file "
                             f"(format {meta.get('format')!r}, version {meta.get('version')!r})")
        return cls(meta, arrays)

    def __getitem__(self, key: str) -> Any:
        return self.meta[key]

    def _scaled(self, name: str, X: np.ndarray) -> np.ndarray:
        a = self.arrays
        return (np.asarray(X, dtype=np.float64) - a[f"{name}_mean"]) / a[f"{name}_scale"]

    def dz(self, X: np.ndarray) -> np.ndarray:
        """Signed defocus in DoF, one per row of `X`."""
        h = self._scaled("dz", X)
        n = int(self.meta["dz_layers"])
        for i in range(n):
            h = h @ self.arrays[f"dz_W{i}"] + self.arrays[f"dz_b{i}"]
            if i < n - 1:
                h = np.maximum(h, 0.0)
        return h[:, 0]

    def log_err(self, X: np.ndarray) -> np.ndarray:
        return self._scaled("err", X) @ self.arrays["err_coef"] + self.arrays["err_intercept"]

    def p_valid(self, X: np.ndarray) -> np.ndarray:
        t = self._scaled("valid", X) @ self.arrays["valid_coef"] + self.arrays["valid_intercept"]
        return 1.0 / (1.0 + np.exp(-t))


META_KEYS = ("backbone", "n_layers", "tile_px", "uses_signal", "err_offset", "sigma_scale",
             "trained_on", "report")


def from_pipelines(h: dict) -> tuple[dict, dict]:
    """(meta, arrays) of a head dict of fitted scikit-learn pipelines, as
    scripts/train_head.py builds it. Reads attributes only; imports no scikit-learn."""
    (dz_sc, mlp), (err_sc, ridge), (val_sc, logit) = (
        [s for _, s in h[k].steps] for k in ("dz", "err", "valid"))
    if mlp.activation != "relu" or mlp.out_activation_ != "identity":
        raise ValueError(f"MLP {mlp.activation}/{mlp.out_activation_}: only relu/identity")
    if list(logit.classes_) != [False, True]:
        raise ValueError(f"valid head classes {logit.classes_}: expected [False, True]")
    arrays = {"dz_mean": dz_sc.mean_, "dz_scale": dz_sc.scale_,
              "err_mean": err_sc.mean_, "err_scale": err_sc.scale_,
              "err_coef": ridge.coef_, "err_intercept": np.atleast_1d(ridge.intercept_),
              "valid_mean": val_sc.mean_, "valid_scale": val_sc.scale_,
              "valid_coef": logit.coef_[0], "valid_intercept": logit.intercept_}
    for i, (W, b) in enumerate(zip(mlp.coefs_, mlp.intercepts_, strict=True)):
        arrays[f"dz_W{i}"], arrays[f"dz_b{i}"] = W, b
    meta = {k: h[k] for k in META_KEYS if k in h}
    meta["dz_layers"] = len(mlp.coefs_)
    return meta, arrays


def save(path: str | Path, meta: dict[str, Any], arrays: dict[str, np.ndarray]) -> Path:
    """Write a head; `meta` must be JSON-serialisable (no objects)."""
    meta = {**meta, "format": FORMAT, "version": VERSION}
    out = {k: np.asarray(v, dtype=np.float64) for k, v in arrays.items()}
    np.savez_compressed(path, meta=np.array(json.dumps(meta, sort_keys=True)), **out)
    return Path(path)
