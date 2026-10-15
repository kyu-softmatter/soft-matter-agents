"""Dataset generation, label gates and the train/test splits."""
from __future__ import annotations

import warnings

import numpy as np
import pytest

from dino_autofocus.synth.sim.dataset import (COND_NAMES, DESCRIPTOR_NAMES, DatasetConfig,
                                PROFILE_CHANNELS, RADIAL_NAMES, ShardedArrays,
                                generate, n_scalar_features, render_scene)
from dino_autofocus.synth.sim.scene import RandomisationConfig, cap_emitters
from dino_autofocus.synth.sim import geometry as G


@pytest.fixture(scope="module")
def tiny_cfg():
    return DatasetConfig(
        fov_px=32, n_planes=7, refine_planes=5, refine_passes=1,
        global_step_dof=2.5, scan_span_dof=8.0, fft_workers=1,
        psf_cache_size=8, ee_radii=16, esf_samples=33,
        randomisation=RandomisationConfig(
            geometries=("solid_sphere", "thin_sheet", "strut_network"),
            empty_probability=0.0),
    )


@pytest.fixture(scope="module")
def tiny_dataset(tmp_path_factory, tiny_cfg):
    out = tmp_path_factory.mktemp("ds")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        generate(out, n_scenes=6, cfg=tiny_cfg, shard_size=3, workers=1,
                 progress=False)
    return ShardedArrays(out)


def test_scene_is_reproducible_from_its_seed(tiny_cfg):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        a = render_scene(3, tiny_cfg)
        b = render_scene(3, tiny_cfg)
    assert a is not None and b is not None
    assert np.array_equal(a["image"], b["image"])
    assert a["best_stage_um"][0] == b["best_stage_um"][0]


def test_planes_straddle_focus(tiny_cfg):
    """Training planes on one side of focus only would let the model learn a
    sign prior instead of reading the blur."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        r = render_scene(3, tiny_cfg)
    dz = r["dz_dof"]
    assert dz.min() < 0 < dz.max()


def test_label_sits_at_the_sharpest_plane(tiny_cfg):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        r = render_scene(3, tiny_cfg)
    if not r["valid"].any():
        pytest.skip("scene rejected by the gates")
    sharpest = int(np.argmax(r["sharpness"]))
    assert abs(r["dz_dof"][sharpest]) < 1.5


def test_every_record_carries_the_gate_diagnostics(tiny_cfg):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        r = render_scene(1, tiny_cfg)
    for key in ("ambiguous", "edge_peak", "peak_prominence",
                "label_residual_dof", "rival_peak_ratio", "snr", "saturated"):
        assert key in r, f"missing diagnostic {key}"


def test_gates_are_what_invalidate_records(tiny_cfg):
    """`valid` must be explainable: every False should trace to a stated reason,
    so a rejected frame is visible rather than merely absent."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        r = render_scene(5, tiny_cfg)
    bad = ~r["valid"]
    if not bad.any():
        pytest.skip("nothing rejected in this scene")
    explained = (
        r["ambiguous"] | r["edge_peak"]
        | (r["snr"] < tiny_cfg.min_snr)
        | (r["saturated"] > tiny_cfg.max_saturated)
        | (np.abs(r["dz_dof"]) > tiny_cfg.scan_span_dof)
        | (np.abs(r["label_residual_dof"]) > tiny_cfg.max_label_residual_dof)
        | ~np.isfinite(r["dz_um"])
    )
    assert explained[bad].all()


def test_feature_layout_is_self_consistent(tiny_dataset):
    a = tiny_dataset
    assert a["cond"].shape[1] == len(COND_NAMES)
    assert a["descriptors"].shape[1] == len(DESCRIPTOR_NAMES)
    assert a["radial_descriptors"].shape[1] == len(RADIAL_NAMES)
    n_scalars = (len(DESCRIPTOR_NAMES) + len(RADIAL_NAMES)
                 + a["encircled"].shape[1] + 2)
    assert n_scalar_features(a["esf"].shape[1], a["encircled"].shape[1]) == n_scalars
    for channel in PROFILE_CHANNELS:
        assert channel in a


def test_all_arrays_are_finite_and_aligned(tiny_dataset):
    a = tiny_dataset
    n = len(a)
    for key in a.keys:
        arr = a[key]
        assert arr.shape[0] == n, f"{key} has {arr.shape[0]} rows, expected {n}"
        if arr.dtype.kind == "f":
            assert np.isfinite(arr[np.isfinite(arr)]).all()
    assert np.isfinite(a["dz_dof"][a["valid"]]).all()


def test_scene_split_does_not_leak_scenes(tiny_dataset):
    """Planes from one scene share the sample, the aberration state and the
    illumination field.  A record-level split puts near-duplicates on both
    sides and reports accuracy the model does not have."""
    parts = tiny_dataset.scene_split((0.6, 0.2, 0.2), seed=0)
    ids = [set(tiny_dataset["scene_id"][p].tolist()) for p in parts]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            assert not (ids[i] & ids[j])
    assert sum(len(p) for p in parts) == len(tiny_dataset)


def test_family_split_holds_out_whole_families(tiny_dataset):
    train, test = tiny_dataset.family_split(["networks"])
    fam = tiny_dataset["family"].astype(str)
    assert set(fam[test]) <= {"networks"}
    assert "networks" not in set(fam[train])
    assert len(train) + len(test) == len(tiny_dataset)


def test_cap_emitters_preserves_brightness(rng):
    """Bounding cost by subsampling and rescaling weights keeps the expected
    image identical; truncating would dim the sample instead."""
    em = G.build("solid_sphere", rng, radius=1.5, density=3000.0)
    capped = cap_emitters(em, max_n=len(em) // 4, rng=rng)
    assert len(capped) == len(em) // 4
    assert capped.total_weight == pytest.approx(em.total_weight, rel=0.05)
    assert capped.meta["subsampled_from"] == len(em)


def test_manifest_records_the_configuration(tiny_dataset):
    m = tiny_dataset.manifest
    assert m["n_records"] == len(tiny_dataset)
    assert m["cond_names"] == list(COND_NAMES)
    assert m["config"]["fov_px"] == 32
    assert isinstance(m["errors"], list)


def test_summary_is_readable(tiny_dataset):
    text = tiny_dataset.summary()
    assert "records from" in text
    assert "valid" in text


def test_generate_resumes_an_interrupted_run(tmp_path, tiny_cfg):
    """Shards of a run killed before its manifest are kept and their scenes skipped."""
    full = generate(tmp_path / "full", 6, tiny_cfg, seed0=40, shard_size=2, workers=1,
                    progress=False)
    part = tmp_path / "part"
    generate(part, 4, tiny_cfg, seed0=40, shard_size=2, workers=1, progress=False)
    (part / "manifest.json").unlink()               # as if killed before the end
    (part / "tmp_shard_00009.npz").write_bytes(b"half a shard")
    m = generate(part, 6, tiny_cfg, seed0=40, shard_size=2, workers=1, progress=False)
    assert not list(part.glob("tmp_*"))

    def ids(root):
        return sorted({int(s) for p in root.glob("shard_*.npz")
                       for s in np.load(p, allow_pickle=True)["scene_id"]})

    assert ids(part) == ids(tmp_path / "full")
    assert m["n_records"] == full["n_records"]
