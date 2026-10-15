"""mosaic: stage <-> tile pixel mapping (PLAN v1.2 mirror), the stage-oriented mosaic, and
classical candidates, on tiles rendered from a known stage-fixed scene."""

from __future__ import annotations

import json

import numpy as np
import pytest

from dino_autofocus.engine import mosaic as mz

BENCH = np.array(mz.BENCH_M_4X)  # mirrored in y, ~0.1 degree
SHAPE = (240, 320)  # rows, cols: not square, so a swapped axis shows


def render(M, tile_um, scene, shape=SHAPE, background=1000.0, noise=5.0, seed=0):
    """A frame of `scene` (list of (x_um, y_um, amplitude, sigma_um)) seen from `tile_um`."""
    h, w = shape
    rows, cols = np.mgrid[0:h, 0:w].astype(float)
    centre = np.array([(w - 1) / 2, (h - 1) / 2])
    Minv = np.linalg.inv(M)
    d = np.stack([centre[0] - cols, centre[1] - rows], axis=-1)
    st = np.asarray(tile_um, float) + d @ Minv.T  # stage of every pixel
    img = np.full(shape, background)
    for x, y, amp, sig in scene:
        img += amp * np.exp(-((st[..., 0] - x) ** 2 + (st[..., 1] - y) ** 2) / (2 * sig**2))
    img += np.random.default_rng(seed).normal(0, noise, shape)
    return img


# ---------------------------------------------------------------- mapping
def test_pixel_stage_round_trip_and_mirror() -> None:
    t = (8000.0, 500.0)
    x, y = mz.tile_pixel_to_stage(BENCH, t, 10.0, 20.0, SHAPE)
    assert mz.stage_to_tile_pixel(BENCH, t, x, y, SHAPE) == pytest.approx((10.0, 20.0))
    cx, cy = (SHAPE[1] - 1) / 2, (SHAPE[0] - 1) / 2
    assert mz.tile_pixel_to_stage(BENCH, t, cx, cy, SHAPE) == pytest.approx(t)
    # mirrored bench: a pixel to the right of centre is at smaller stage x, one below at larger y
    xr, _ = mz.tile_pixel_to_stage(BENCH, t, cx + 100, cy, SHAPE)
    _, yd = mz.tile_pixel_to_stage(BENCH, t, cx, cy + 100, SHAPE)
    assert xr < t[0] and yd > t[1]
    assert mz.um_per_px(BENCH) == pytest.approx(1.6252, abs=1e-3)


@pytest.mark.parametrize("M, expect", [
    (BENCH, (False, True, False)),  # plot_scan: flip_lr, rows already run toward +y
    (np.array([[0.6, 0.0], [0.0, 0.6]]), (False, True, True)),
    (np.array([[-0.6, 0.0], [0.0, -0.6]]), (False, False, False)),
    (np.array([[0.0, 0.6], [0.6, 0.0]]), (True, True, True)),  # camera turned 90 degrees
])
def test_orientation(M, expect) -> None:
    o = mz.Orientation.of(M)
    assert (o.transpose, o.flip_cols, o.flip_rows) == expect
    assert abs(o.rotation_ignored_deg) < 1.0


# ---------------------------------------------------------------- mosaic
# inside the area the 2 x 2 grid covers for every M below
SCENE = [(7750.0, 300.0, 3000.0, 30.0), (8250.0, 550.0, 3000.0, 30.0),
         (8000.0, 250.0, 3000.0, 30.0)]


def _grid(M, scene=SCENE, shape=SHAPE):
    fov = np.array([shape[1], shape[0]]) * mz.um_per_px(M)  # stage x, y extent of a frame
    if mz.Orientation.of(M).transpose:
        fov = fov[::-1]
    tiles = []
    for i, dx in enumerate((-0.4, 0.4)):
        for j, dy in enumerate((-0.4, 0.4)):
            t = (8000.0 + dx * fov[0], 400.0 + dy * fov[1])
            tiles.append(mz.Tile(f"tile_r{j}c{i}", *t, render(M, t, scene, shape, seed=i + 2 * j)))
    return tiles


@pytest.mark.parametrize("M", [BENCH, np.array([[0.0, 0.62], [0.62, 0.0]]),
                               np.array([[-0.62, 0.0], [0.0, 0.62]])])
def test_features_land_at_their_stage_position(M) -> None:
    mosaic, meta = mz.build_mosaic(_grid(M), M, bin=4)
    assert meta.orientation == "stage" and meta.n_tiles == 4 and meta.bin == 4
    assert meta.um_per_px == pytest.approx(4 * mz.um_per_px(M))
    assert list(mosaic.shape) == meta.shape
    for x, y, *_ in SCENE:
        c, r = mz.stage_to_mosaic(meta, x, y)
        win = mosaic[int(r) - 6:int(r) + 7, int(c) - 6:int(c) + 7]
        pr, pc = np.unravel_index(np.argmax(win), win.shape)
        bx, by = mz.mosaic_to_stage(meta, int(c) - 6 + pc, int(r) - 6 + pr)
        assert abs(bx - x) <= 1.5 * meta.um_per_px and abs(by - y) <= 1.5 * meta.um_per_px
    assert mz.mosaic_to_stage(meta, *mz.stage_to_mosaic(meta, 8123.0, 456.0)) == \
        pytest.approx((8123.0, 456.0))


def test_mosaic_from_scan_folder_saves_metadata(tmp_path) -> None:
    sample = tmp_path / "20261001_1200_1"
    scan = sample / "scan4x_20261001-120000"
    scan.mkdir(parents=True)
    tiles = _grid(BENCH)
    rec = {"objective": "1-Plan Apo LmbdD20 4x", "tiles": []}
    for t in tiles:
        np.save(scan / f"{t.name}.npy", t.image.astype(np.uint16))
        rec["tiles"].append({"name": t.name, "x_um": t.x_um, "y_um": t.y_um})
    (scan / "scan.json").write_text(json.dumps(rec), encoding="utf-8")

    mosaic, meta = mz.mosaic_from_scan(scan)  # no sample.json: the bench M
    assert meta.calibration_source.startswith("2026-09-30")
    assert meta.objective == "4x" and meta.bin == mz.BIN
    saved = json.loads((scan / "mosaic.json").read_text(encoding="utf-8"))
    for key in ("orientation", "M_px_per_um", "objective", "n_tiles", "x0", "x1", "y0", "y1",
                "um_per_px", "bin"):
        assert key in saved
    assert saved["orientation"] == "stage" and saved["n_tiles"] == 4
    m2, meta2 = mz.load_mosaic(scan)
    assert np.array_equal(m2, mosaic) and meta2 == meta

    own = [[0.0, 0.62], [0.62, 0.0]]
    (sample / "sample.json").write_text(json.dumps(
        {"stage_camera_calibration": {"objective": "4x", "M_px_per_um": own}}), encoding="utf-8")
    _, meta3 = mz.mosaic_from_scan(scan, save=False)
    assert meta3.M_px_per_um == own and meta3.transpose


def test_empty_and_mismatched_tiles_are_refused() -> None:
    with pytest.raises(ValueError, match="no tiles"):
        mz.build_mosaic([], BENCH)
    tiles = _grid(BENCH)
    tiles[1] = mz.Tile("odd", 0.0, 0.0, np.zeros((100, 100)))
    with pytest.raises(ValueError, match="shape"):
        mz.build_mosaic(tiles, BENCH)


# ---------------------------------------------------------------- candidates
PARTICLES = [(7700.0, 250.0), (8250.0, 650.0), (8050.0, 150.0), (7950.0, 520.0)]


def _particle_tiles(polarity: str, extra=()):
    amp = -400.0 if polarity == "dark" else 400.0
    scene = [(x, y, amp, 3.0) for x, y in PARTICLES] + list(extra)  # ~4 px wide at 1.625 um/px
    return _grid(BENCH, scene=scene)


@pytest.mark.parametrize("polarity", ["dark", "bright"])
def test_candidates_found_at_their_stage_position(polarity) -> None:
    cands = mz.find_candidates(_particle_tiles(polarity), BENCH,
                               mz.CandidateParams(polarity=polarity))
    assert len(cands) == len(PARTICLES)  # each once, though tiles overlap
    for x, y in PARTICLES:
        best = min(cands, key=lambda c: (c["x_um"] - x) ** 2 + (c["y_um"] - y) ** 2)
        assert np.hypot(best["x_um"] - x, best["y_um"] - y) < 2.0
    c = cands[0]
    assert c["source"] == "classical_candidate" and c["grade"] == "computed"
    assert c["method"]["polarity"] == polarity


def test_wrong_polarity_finds_nothing() -> None:
    assert mz.find_candidates(_particle_tiles("dark"), BENCH,
                              mz.CandidateParams(polarity="bright")) == []


def test_a_line_is_not_a_candidate() -> None:
    # a dark line running past every tile, like the hole edge (no ends in view)
    line = [(7000.0 + k * 4.0, 400.0, -400.0, 3.0) for k in range(500)]
    tiles = _grid(BENCH, scene=line)
    assert mz.find_candidates(tiles, BENCH) == []


def test_hole_filter_keeps_only_points_inside() -> None:
    hole = {"centre_um": [8250.0, 650.0], "diameter_mm": 0.5}  # r 250 um around one particle
    cands = mz.find_candidates(_particle_tiles("dark"), BENCH, hole=hole, hole_margin_um=50)
    assert len(cands) == 1
    assert np.hypot(cands[0]["x_um"] - 8250, cands[0]["y_um"] - 650) < 2.0


def test_bad_polarity() -> None:
    with pytest.raises(ValueError, match="polarity"):
        mz.detect_blobs(np.zeros((50, 50)), mz.CandidateParams(polarity="grey"))
