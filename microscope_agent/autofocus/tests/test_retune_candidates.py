"""scripts/retune_candidates.py on synthetic 4x scans and mosaics built with engine/mosaic.py."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from dino_autofocus.engine import mosaic as mz

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("retune_candidates",
                                               REPO / "scripts" / "retune_candidates.py")
rc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = rc  # dataclasses look their module up while the script loads
_spec.loader.exec_module(rc)

BENCH = np.array(mz.BENCH_M_4X)
SHAPE = (240, 320)
# strong, medium and faint dark particles, ~4 px wide at 1.625 um/px
PARTICLES = [(7700.0, 250.0, -600.0), (8250.0, 650.0, -600.0), (8050.0, 150.0, -150.0),
             (7950.0, 520.0, -90.0), (8150.0, 330.0, -60.0)]


def render(tile_um, scene, shape=SHAPE, background=1000.0, noise=5.0, seed=0):
    """A camera frame of `scene` [(x_um, y_um, amplitude, sigma_um)] taken at `tile_um`."""
    h, w = shape
    rows, cols = np.mgrid[0:h, 0:w].astype(float)
    centre = np.array([(w - 1) / 2, (h - 1) / 2])
    d = np.stack([centre[0] - cols, centre[1] - rows], axis=-1)
    st = np.asarray(tile_um, float) + d @ np.linalg.inv(BENCH).T
    img = np.full(shape, background)
    for x, y, amp, sig in scene:
        img += amp * np.exp(-((st[..., 0] - x) ** 2 + (st[..., 1] - y) ** 2) / (2 * sig**2))
    return img + np.random.default_rng(seed).normal(0, noise, shape)


def tiles(scene=None):
    scene = scene or [(x, y, a, 3.0) for x, y, a in PARTICLES]
    fov = np.array([SHAPE[1], SHAPE[0]]) * mz.um_per_px(BENCH)
    out = []
    for i, dx in enumerate((-0.4, 0.4)):
        for j, dy in enumerate((-0.4, 0.4)):
            t = (8000.0 + dx * fov[0], 400.0 + dy * fov[1])
            out.append(mz.Tile(f"tile_r{j}c{i}", *t, render(t, scene, seed=i + 2 * j)))
    return out


def write_scan(folder: Path, ts) -> Path:
    """A scan_4x record folder inside a sample folder, as scripts/scan_4x.py leaves it."""
    scan = folder / "sample-x" / "scan4x_20261001-120000"
    scan.mkdir(parents=True)
    (scan.parent / "sample.json").write_text(json.dumps({"sample_id": "sample-x"}), "utf-8")
    for t in ts:
        np.save(scan / f"{t.name}.npy", t.image.astype(np.uint16))
    rec = {"objective": "4x", "tiles": [{"name": t.name, "x_um": t.x_um, "y_um": t.y_um}
                                        for t in ts]}
    (scan / "scan.json").write_text(json.dumps(rec), "utf-8")
    return scan


def snapshot(folder: Path) -> dict[str, str]:
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


@pytest.fixture
def scan(tmp_path) -> Path:
    return write_scan(tmp_path, tiles())


# ---------------------------------------------------------------- thresholds
@pytest.mark.parametrize("text, expect", [
    ("4,5,6", [4.0, 5.0, 6.0]),
    ("6,4,4", [4.0, 6.0]),
    ("3:6", [3.0, 4.0, 5.0, 6.0]),
    ("3:5:0.5", [3.0, 3.5, 4.0, 4.5, 5.0]),
    ("2:3:0.3", [2.0, 2.3, 2.6, 2.9]),
])
def test_parse_thresholds(text, expect) -> None:
    assert rc.parse_thresholds(text) == pytest.approx(expect)


@pytest.mark.parametrize("text", ["", "a,b", "5:3", "3:6:0", "1:2:3:4", "0,4", "-1"])
def test_parse_thresholds_rejects(text) -> None:
    with pytest.raises(Exception, match="thresholds"):
        rc.parse_thresholds(text)


# ---------------------------------------------------------------- detection
def test_counts_match_find_candidates_called_directly(scan) -> None:
    src = rc.load_source(scan)
    assert src.kind == "scan" and len(src.tiles) == 4
    thresholds = [3.0, 6.0, 10.0, 20.0, 40.0]
    found = rc.candidates_by_threshold(src, mz.DEFAULT_CANDIDATES, thresholds)
    for t in thresholds:
        direct = mz.find_candidates(src.tiles, src.M, mz.CandidateParams(min_snr=t))
        assert found[t] == direct, t
    counts = [len(found[t]) for t in thresholds]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] > counts[-1]  # the faint particles drop out as the threshold rises


def test_the_detection_runs_once_per_tile_and_is_put_back(scan, monkeypatch) -> None:
    src = rc.load_source(scan)
    calls = []
    original = mz.detect_blobs

    def counting(img, p=mz.DEFAULT_CANDIDATES):
        calls.append(p.min_snr)
        return original(img, p)

    monkeypatch.setattr(mz, "detect_blobs", counting)
    rc.candidates_by_threshold(src, mz.DEFAULT_CANDIDATES, [3.0, 6.0, 9.0, 12.0])
    assert calls == [3.0] * len(src.tiles)
    assert mz.detect_blobs is counting


def test_max_per_tile_is_applied_after_the_threshold(scan) -> None:
    src = rc.load_source(scan)
    p = mz.CandidateParams(max_per_tile=1)
    found = rc.candidates_by_threshold(src, p, [2.0, 6.0])
    for t in (2.0, 6.0):
        assert found[t] == mz.find_candidates(src.tiles, src.M, mz.CandidateParams(
            min_snr=t, max_per_tile=1))


def test_hole_filter_is_passed_through(scan) -> None:
    src = rc.load_source(scan)
    hole = {"centre_um": [8250.0, 650.0], "diameter_mm": 0.3}
    found = rc.candidates_by_threshold(src, mz.DEFAULT_CANDIDATES, [6.0], hole=hole,
                                       hole_margin_um=50)
    assert len(found[6.0]) == 1
    assert np.hypot(found[6.0][0]["x_um"] - 8250, found[6.0][0]["y_um"] - 650) < 2.0


def test_mosaic_input_detects_on_the_mosaic(tmp_path) -> None:
    big = [(x, y, a * 3, 12.0) for x, y, a in PARTICLES[:2]]  # visible after 2x binning
    m, meta = mz.build_mosaic(tiles(big), BENCH, bin=2)
    folder = tmp_path / "saved"
    folder.mkdir()
    npy, _ = mz.save_mosaic(folder, m, meta)
    for given in (npy, folder):
        src = rc.load_source(given)
        assert src.kind == "mosaic" and src.meta is not None
        found = rc.candidates_by_threshold(src, mz.CandidateParams(sigma_px=3.0), [4.0])
        assert len(found[4.0]) >= 2
        for x, y, _ in PARTICLES[:2]:
            best = min(found[4.0], key=lambda c: (c["x_um"] - x) ** 2 + (c["y_um"] - y) ** 2)
            assert np.hypot(best["x_um"] - x, best["y_um"] - y) < 2 * meta.um_per_px


def test_bad_input_is_refused(tmp_path) -> None:
    with pytest.raises(SystemExit, match="neither"):
        rc.load_source(tmp_path)
    np.save(tmp_path / "cube.npy", np.zeros((2, 3, 4)))
    with pytest.raises(SystemExit, match="not a 2D image"):
        rc.load_source(tmp_path / "cube.npy")


# ---------------------------------------------------------------- CLI and files
def test_cli_prints_counts_and_writes_outputs_outside_the_sample(scan, tmp_path, capsys) -> None:
    before = snapshot(scan.parent)
    out = tmp_path / "retune"
    assert rc.main([str(scan), "--thresholds", "3,6,12", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "min_snr" in text and "(default)" in text and "4 tiles" in text
    assert snapshot(scan.parent) == before  # the sample folder is untouched
    assert not (scan / "mosaic.npy").exists()

    with (out / "counts.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [float(r["min_snr"]) for r in rows] == [3.0, 6.0, 12.0]
    counts = {float(r["min_snr"]): int(r["candidates"]) for r in rows}
    src = rc.load_source(scan)
    assert counts[6.0] == len(mz.find_candidates(src.tiles, src.M))
    with (out / "candidates.csv").open(encoding="utf-8") as f:
        cands = list(csv.DictReader(f))
    assert sum(1 for c in cands if float(c["min_snr"]) == 6.0) == counts[6.0]
    png = (out / "contact_sheet.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 1000


@pytest.mark.parametrize("where", ["scan", "sample"])
def test_out_inside_the_input_or_sample_folder_is_refused(scan, where) -> None:
    before = snapshot(scan.parent)
    out = (scan if where == "scan" else scan.parent) / "retune"
    with pytest.raises(SystemExit, match="outside the sample"):
        rc.main([str(scan), "--out", str(out)])
    assert not out.exists()
    assert snapshot(scan.parent) == before
