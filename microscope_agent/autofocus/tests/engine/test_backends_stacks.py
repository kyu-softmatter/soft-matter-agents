"""Z-stack sources for replay: in-memory stacks, synth shards, sample-folder files (T-005).

Everything except `test_real_smoke_shard` runs on arrays built here or files written to
tmp_path; that one test skips when data/smoke (gitignored) is absent.
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from dino_autofocus.engine.backends.stacks import (
    FocusCurve,
    ZStack,
    load_curves,
    load_stacks,
)

SMOKE = Path(__file__).resolve().parents[2] / "data" / "smoke"


def blurred_spot_stack(z_um, best_um=3000.0, size=48, dof_um=2.0):
    """A Gaussian spot whose width grows with |z - best|: sharpest (tallest) at best focus."""
    yy, xx = np.mgrid[:size, :size] - size / 2
    frames = []
    for z in z_um:
        s = 1.5 * np.sqrt(1 + ((z - best_um) / dof_um) ** 2)
        frames.append(100 + 3000 * np.exp(-(xx**2 + yy**2) / (2 * s**2)) * (1.5 / s) ** 2)
    return np.stack(frames)


@pytest.fixture
def stack():
    z = np.arange(2990.0, 3011.0, 2.0)  # 2990, 2992, ..., 3010
    return ZStack.from_arrays(blurred_spot_stack(z), z, source="test", best_focus_um=3000.0)


# ---------------------------------------------------------------- (a) in memory


def test_from_arrays_sorts_copies_and_converts(stack):
    z = np.array([3.0, 1.0, 2.0])
    f = np.stack([np.full((4, 4), v, np.float32) for v in (30.4, 10.6, -5.0)])
    s = ZStack.from_arrays(f, z)
    assert s.frames.dtype == np.uint16
    assert s.z_um.tolist() == [1.0, 2.0, 3.0]
    assert [int(fr[0, 0]) for fr in s.frames] == [11, 0, 30]  # rounded, clipped, z order
    f[:] = 999  # the stack holds its own copy
    assert int(s.frames[0, 0, 0]) == 11
    with pytest.raises(ValueError):
        s.frames[0, 0, 0] = 1  # read-only
    assert s.meta["source"] == "arrays" and stack.meta["source"] == "test"
    assert len(stack) == 11 and stack.shape == (48, 48)
    assert stack.z_range_um == (2990.0, 3010.0) and stack.best_focus_um == 3000.0


def test_single_2d_frame_is_one_plane():
    s = ZStack.from_arrays(np.zeros((5, 6), np.uint16), [2900.0])
    assert len(s) == 1 and s.frame_at(0.0).clamped and s.frame_at(2900.0).index == 0


@pytest.mark.parametrize("frames, z, match", [
    (np.zeros((2, 4, 4)), [1.0], "2 frames but 1"),
    (np.zeros((0, 4, 4)), [], "at least one plane"),
    (np.zeros((2, 4, 4)), [1.0, np.nan], "non-finite"),
])
def test_from_arrays_refuses_bad_input(frames, z, match):
    with pytest.raises(ValueError, match=match):
        ZStack.from_arrays(frames, z)


def test_direct_construction_requires_sorted_uint16():
    with pytest.raises(ValueError, match="non-decreasing"):
        ZStack(np.zeros((2, 3, 3), np.uint16), np.array([2.0, 1.0]))
    with pytest.raises(ValueError, match="uint16"):
        ZStack(np.zeros((2, 3, 3), np.float32), np.array([1.0, 2.0]))


def test_nearest_plane_exact_and_between(stack):
    hit = stack.frame_at(3000.0)
    assert (hit.index, hit.z_um, hit.clamped, hit.offset_um) == (5, 3000.0, False, 0.0)
    assert stack.frame_at(3000.9).z_um == 3000.0
    assert stack.frame_at(3001.1).z_um == 3002.0
    assert stack.frame_at(2990.4).index == 0


def test_tie_goes_to_the_lower_plane(stack):
    assert stack.frame_at(3001.0).z_um == 3000.0
    assert stack.frame_at(2991.0).z_um == 2990.0


def test_out_of_range_returns_edge_plane_with_flag(stack):
    lo, hi = stack.frame_at(2800.0), stack.frame_at(3200.0)
    assert (lo.index, lo.z_um, lo.clamped) == (0, 2990.0, True)
    assert (hi.index, hi.z_um, hi.clamped) == (10, 3010.0, True)
    assert hi.offset_um == pytest.approx(190.0)
    assert not stack.frame_at(3010.0).clamped  # the edge plane itself is in range


def test_equal_z_planes_resolve_to_the_first():
    f = np.stack([np.full((2, 2), v, np.uint16) for v in (1, 2, 3, 4)])
    s = ZStack.from_arrays(f, [1.0, 2.0, 2.0, 3.0])
    assert s.frame_at(2.0).index == 1
    assert s.frame_at(1.6).index == 1
    assert s.frame_at(2.4).index == 1
    assert int(s.frame_at(2.0).frame[0, 0]) == 2


def test_non_finite_request_raises(stack):
    with pytest.raises(ValueError, match="finite"):
        stack.frame_at(float("nan"))


def test_best_focus_plane_is_the_sharpest(stack):
    peaks = [int(stack.frame_at(z).frame.max()) for z in stack.z_um]
    assert int(np.argmax(peaks)) == stack.frame_at(stack.best_focus_um).index


def test_load_stacks_passes_stacks_through(stack):
    assert load_stacks(stack) == [stack]
    assert load_stacks([stack, [stack]]) == [stack, stack]
    with pytest.raises(TypeError):
        load_stacks(3.0)


def test_import_pulls_in_no_heavy_modules():
    code = ("import sys, dino_autofocus.engine.backends.stacks; "
            "print(sorted({'torch', 'pymmcore', 'pymmcore_plus', 'tkinter'} & set(sys.modules)))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True).stdout.strip()
    assert out == "[]"


# ---------------------------------------------------------------- (b) synth shards


def write_shard(path, with_stage=True, manifest=True):
    """Two scenes of 5 planes, interleaved and unsorted, with the synth writer's keys."""
    rng = np.random.default_rng(0)
    sid = np.array([7, 3, 7, 3, 7, 3, 7, 3, 7, 3])
    dz = np.array([2.0, -1.0, -2.0, 1.0, 0.0, 0.0, 1.0, -2.0, -1.0, 2.0], np.float32)
    best = np.where(sid == 7, 10.0, -4.0).astype(np.float32)
    cond = np.where(sid[:, None] == 7, [[1.4, 0.6, 0.1, 0.5, 1.0]], [[0.9, 0.5, 0.2, 1.1, 2.0]])
    keys = {
        "image": rng.integers(100, 4000, (10, 8, 8)).astype(np.uint16),
        "dz_um": dz, "dz_dof": dz / 0.5, "valid": dz != 2.0,
        "cond": cond.astype(np.float32), "scene_id": sid,
        "family": np.where(sid == 7, "compact", "sparse"),
    }
    if with_stage:
        keys |= {"stage_um": dz + best, "best_stage_um": best}
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **keys)
    if manifest:
        (path.parent / "manifest.json").write_text(json.dumps(
            {"cond_names": ["na", "wavelength_um", "pixel_size_um", "dof_um", "log10_signal"]}))
    return keys


def test_synth_shard_dir_gives_one_sorted_stack_per_scene(tmp_path):
    keys = write_shard(tmp_path / "shards" / "shard_00000.npz")
    stacks = load_stacks(tmp_path / "shards")
    assert [s.meta["scene_id"] for s in stacks] == [3, 7]
    s3 = stacks[0]
    assert len(s3) == 5 and s3.shape == (8, 8)
    assert s3.z_um.tolist() == [-6.0, -5.0, -4.0, -3.0, -2.0]  # stage = dz + best (-4)
    assert s3.best_focus_um == -4.0 and s3.frame_at(-4.0).index == 2
    assert s3.meta["pixel_um"] == pytest.approx(0.2) and s3.meta["family"] == "sparse"
    assert s3.meta["valid"] == [True, True, True, True, False]  # dz 2.0 marked invalid
    i_best = np.flatnonzero((keys["scene_id"] == 3) & (keys["dz_um"] == 0.0))[0]
    assert np.array_equal(s3.frame_at(-4.0).frame, keys["image"][i_best])
    json.dumps(s3.meta)  # metadata stays serialisable for records


def test_synth_shard_without_stage_uses_dz(tmp_path):
    write_shard(tmp_path / "shard_00000.npz", with_stage=False, manifest=False)
    stacks = load_stacks(tmp_path / "shard_00000.npz")  # one file works too
    s = stacks[1]
    assert s.meta["scene_id"] == 7 and s.best_focus_um == 0.0
    assert s.z_um.tolist() == [-2.0, -1.0, 0.0, 1.0, 2.0]
    assert s.meta["z_kind"].startswith("dz_um")
    assert s.meta["pixel_um"] == pytest.approx(0.1)  # default cond order


def test_real_smoke_shard():
    if not (SMOKE / "shard_00000.npz").exists():
        pytest.skip("data/smoke not present (gitignored, generated on the microscope PC)")
    stacks = load_stacks(SMOKE)
    assert stacks and all(len(s) > 1 and s.frames.dtype == np.uint16 for s in stacks)
    for s in stacks:
        assert np.all(np.diff(s.z_um) >= 0)
        lo, hi = s.z_range_um
        if s.best_focus_um is not None and lo <= s.best_focus_um <= hi:
            assert not s.frame_at(s.best_focus_um).clamped


# ---------------------------------------------------------------- (c) sample folders


def make_sample_folder(root):
    """A small imitation of D:\\AutoFocus\\samples\\<id> with every file kind T-005 reads."""
    d = root / "20260930_1849_1"
    scan = d / "scan4x_20260930-200241"
    scan.mkdir(parents=True)
    tiles = []
    for k, (name, zf) in enumerate([("tile_r0c0", 3057.93), ("tile_r0c1", None)]):
        np.save(scan / f"{name}.npy", np.full((6, 6), 1000 + k, np.uint16))
        tiles.append({"name": name, "row": 0, "col": k, "x_um": 6368.3 + 3315 * k,
                      "y_um": -1086.0, "z_focus_um": zf, "focus_note": "fine parabola",
                      "z_image_um": 3058.0 if zf else 3050.0,
                      "curve": [{"z": 3060.0, "sharp": 0.2, "mean": 900.0, "sat": 0.0},
                                {"z": 3050.0, "sharp": 0.5, "mean": 905.0, "sat": 0.0}]})
    (scan / "scan.json").write_text(json.dumps(
        {"sample": d.name, "objective": "1-Plan Apo LmbdD20 4x", "um_per_px": 1.6252,
         "exposure_ms": 994.0, "tiles": tiles}))

    (d / "focus100x_20260930-202813.json").write_text(json.dumps(
        {"coarse": [[2970.0, 50.0, 110.0, 400], [2968.0, 40.0, 109.0, 380]],
         "fine": [[2989.0, 900.0, 115.0, 3435]], "z_focus_um": 2989.42, "why": "fine parabola",
         "z_parked_um": 2989.4}))

    zs = np.array([2984.0, 2985.0, 2986.0])
    binned = np.stack([np.full((3, 3), v, np.float32) for v in (101.4, 250.6, 99.0)])
    np.savez_compressed(d / "find_particle_20260930-204000_field00.npz",
                        stack=binned, z_um=zs, xy_um=np.array([7239.9, 710.0]), bin=8)
    (d / "find_particle_20260930-204000.json").write_text(json.dumps({"pixel_um": 0.065}))

    np.save(d / "stack_20260930-205000.npy",
            np.stack([np.full((4, 4), v, np.uint16) for v in (1, 2, 3)]))
    (d / "stack_20260930-205000.json").write_text(json.dumps(
        {"pixel_um": 0.065, "objective": "6-Plan Apo LmbdD0.13 100x Oil", "exposure_ms": 20.0,
         "frames": [{"z_um": 3012.0}, {"z_error": "timeout"}, {"z_um": 3010.0}]}))
    return d


def test_scan_tiles_are_one_plane_stacks(tmp_path):
    d = make_sample_folder(tmp_path)
    stacks = load_stacks(d / "scan4x_20260930-200241")
    assert [s.meta["tile"] for s in stacks] == ["tile_r0c0", "tile_r0c1"]
    s0, s1 = stacks
    assert len(s0) == 1 and s0.z_um.tolist() == [3058.0] and s0.best_focus_um == 3057.93
    assert s1.best_focus_um is None and s0.meta["pixel_um"] == 1.6252
    assert s0.frame_at(3000.0).clamped and int(s0.frame_at(3058.0).frame[0, 0]) == 1000
    assert load_stacks(d / "scan4x_20260930-200241" / "scan.json")[1].meta["x_um"] == 9683.3


def test_missing_tile_frame_is_skipped_with_warning(tmp_path):
    d = make_sample_folder(tmp_path)
    (d / "scan4x_20260930-200241" / "tile_r0c1.npy").unlink()
    with pytest.warns(UserWarning, match="tile_r0c1"):
        stacks = load_stacks(d / "scan4x_20260930-200241")
    assert [s.meta["tile"] for s in stacks] == ["tile_r0c0"]


def test_particle_field_and_mm_grab_stacks(tmp_path):
    d = make_sample_folder(tmp_path)
    fld = load_stacks(d / "find_particle_20260930-204000_field00.npz")[0]
    assert fld.z_um.tolist() == [2984.0, 2985.0, 2986.0] and fld.frames.dtype == np.uint16
    assert [int(f[0, 0]) for f in fld.frames] == [101, 251, 99]
    assert fld.meta["pixel_um"] == pytest.approx(0.52) and fld.meta["xy_um"] == [7239.9, 710.0]

    grab = load_stacks(d / "stack_20260930-205000.npy")[0]
    assert grab.z_um.tolist() == [3010.0, 3012.0]  # the frame without a z is dropped, sorted
    assert [int(f[0, 0]) for f in grab.frames] == [3, 1]
    assert grab.meta["dropped_no_z"] == 1


def test_sample_folder_collects_every_stack(tmp_path):
    d = make_sample_folder(tmp_path)
    kinds = [s.meta["source"] for s in load_stacks(d)]
    assert kinds == ["scan4x_tile", "scan4x_tile", "find_particle_field", "mm_grab_stack"]


def test_focus100x_is_a_curve_not_a_stack(tmp_path):
    d = make_sample_folder(tmp_path)
    f = d / "focus100x_20260930-202813.json"
    with pytest.raises(ValueError, match="load_curves"):
        load_stacks(f)
    coarse, fine = load_curves(f)
    assert isinstance(coarse, FocusCurve) and coarse.meta["stage"] == "coarse"
    assert coarse.z_um.tolist() == [2968.0, 2970.0]  # sorted by z
    assert coarse.columns["score"].tolist() == [40.0, 50.0]
    assert fine.columns["max"].tolist() == [3435.0] and fine.meta["z_focus_um"] == 2989.42


def test_curves_from_a_sample_folder(tmp_path):
    d = make_sample_folder(tmp_path)
    curves = load_curves(d)
    assert [c.meta["source"] for c in curves] == ["focus100x"] * 2 + ["scan4x_tile"] * 2
    tile = curves[2]
    assert tile.z_um.tolist() == [3050.0, 3060.0] and tile.columns["sharp"].tolist() == [0.5, 0.2]


def test_missing_and_empty_paths(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_stacks(tmp_path / "nope")
    with pytest.raises(FileNotFoundError, match="no z-stack sources"):
        load_stacks(tmp_path)
    (tmp_path / "other.npz").write_bytes(b"")
    np.savez(tmp_path / "other.npz", a=np.zeros(2))
    with pytest.raises(ValueError, match="not a known z-stack"):
        load_stacks(tmp_path / "other.npz")
    with pytest.raises(FileNotFoundError):
        load_curves(tmp_path / "nope")
