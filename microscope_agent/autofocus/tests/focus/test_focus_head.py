"""focus.head: the pickle-free head reproduces the scikit-learn pipelines it came from, the
shipped head opens without pickle, and FocusScorer refuses a joblib file."""

import json
from pathlib import Path

import numpy as np
import pytest

from dino_autofocus.focus.head import FORMAT, NpzHead, from_pipelines, save

SHIPPED = Path(__file__).resolve().parents[2] / "models" / "heads"


def _pipelines(rng, n_features=12):
    pytest.importorskip("sklearn")  # the ml extra
    from sklearn.linear_model import LogisticRegression, RidgeCV
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    X = rng.normal(size=(200, n_features)) * rng.uniform(0.5, 3, n_features) + 1.0
    y = X[:, 0] - 0.5 * X[:, 1] ** 2
    dz = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(16, 8), max_iter=300,
                                                     random_state=0))
    err = make_pipeline(StandardScaler(), RidgeCV())
    valid = make_pipeline(StandardScaler(), LogisticRegression())
    dz.fit(X, y)
    err.fit(X, np.log(np.abs(y) + 0.05))
    valid.fit(X, y > 0)
    return X, {"backbone": "dinov2_vits14", "n_layers": 1, "tile_px": 224, "uses_signal": False,
               "dz": dz, "err": err, "err_offset": 0.05, "sigma_scale": 1.7, "valid": valid,
               "trained_on": "synthetic", "report": {"chosen": "dino"}}


def test_numpy_head_matches_the_pipelines(tmp_path):
    rng = np.random.default_rng(0)
    X, h = _pipelines(rng)
    head = NpzHead.load(save(tmp_path / "h.npz", *from_pipelines(h)))
    Xt = rng.normal(size=(50, X.shape[1])) * 2
    np.testing.assert_allclose(head.dz(Xt), h["dz"].predict(Xt), rtol=0, atol=1e-12)
    np.testing.assert_allclose(head.log_err(Xt), h["err"].predict(Xt), rtol=0, atol=1e-12)
    np.testing.assert_allclose(head.p_valid(Xt), h["valid"].predict_proba(Xt)[:, 1],
                               rtol=0, atol=1e-12)
    assert head["tile_px"] == 224 and head["sigma_scale"] == 1.7


def test_shipped_head_opens_without_pickle():
    files = sorted(SHIPPED.glob("*.npz"))
    assert files, "no head in models/heads"
    assert not list(SHIPPED.glob("*.joblib")), "pickled heads must not be shipped"
    for f in files:
        with np.load(f, allow_pickle=False) as z:
            assert all(z[k].dtype != object for k in z.files)
            meta = json.loads(str(z["meta"]))
        assert meta["format"] == FORMAT
        head = NpzHead.load(f)
        X = np.zeros((2, head.arrays["dz_mean"].shape[0]))
        assert head.dz(X).shape == head.log_err(X).shape == head.p_valid(X).shape == (2,)


def test_a_file_that_is_not_a_head_is_refused(tmp_path):
    np.savez(tmp_path / "x.npz", meta=np.array(json.dumps({"format": "other"})))
    with pytest.raises(ValueError, match="not a"):
        NpzHead.load(tmp_path / "x.npz")


def test_focus_scorer_refuses_joblib(tmp_path):
    pytest.importorskip("torch")  # live imports the backbone
    from dino_autofocus.live import FocusScorer

    (tmp_path / "head.joblib").write_bytes(b"not opened")
    with pytest.raises(ValueError, match=".npz only"):
        FocusScorer(tmp_path / "head.joblib")
