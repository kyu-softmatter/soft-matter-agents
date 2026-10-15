"""S2 (docs/integration-sma.md section 9): the pure map and focus-search cores live in
`microscope_agent/src/` as flat files. Here, with scipy and the engine at hand: the numpy
ports give scipy's results bit for bit, `sweep_z` gives the guards' plan, the constants the
flat files copy match the engine's, and the old modules hand out the same objects."""

import sys

import numpy as np
import pytest
from scipy import ndimage

from dino_autofocus.engine import mosaic, records, sample
from dino_autofocus.engine.backend import PROVISIONAL
from dino_autofocus.engine.guards import FREE_WD_UM, FocusAxis, GuardError
from dino_autofocus.engine.operations import edge_trace, focus_100x, scan_4x


def _flat(stem):
    return sys.modules[f"_mic_{stem}"]


def test_old_modules_hand_out_the_flat_objects():
    assert mosaic.build_mosaic is _flat("map_mosaic").build_mosaic
    assert mosaic.tile_pixel_to_stage is _flat("map_geometry").tile_pixel_to_stage
    assert sample.SampleGeometry is _flat("map_geometry").SampleGeometry
    assert sample.GeometryError is _flat("map_geometry").GeometryError
    assert scan_4x.grid is _flat("map_tiles").grid
    assert edge_trace.find_edge is _flat("map_edge").find_edge
    assert edge_trace.calibration_of is _flat("map_geometry").calibration_of
    # the engine adds only the light it switches on itself (D-03f)
    assert issubclass(focus_100x.FocusArgs, _flat("focus_search").FocusArgs)
    assert set(focus_100x.FocusArgs.__dataclass_fields__) - set(
        _flat("focus_search").FocusArgs.__dataclass_fields__) == {"aura_line", "aura_percent"}
    assert sys.modules["dino_autofocus.engine._map_mosaic"] is _flat("map_mosaic")


def test_copied_constants_match_the_engine():
    for stem in ("map_mosaic", "map_tiles", "focus_search"):
        assert _flat(stem).GRADE_COMPUTED == records.GRADE_COMPUTED
    assert _flat("map_geometry").GRADE_MODEL == records.GRADE_MODEL
    assert _flat("focus_search").PROVISIONAL == PROVISIONAL


def test_graded_model_value_is_refused_as_geometry():
    with pytest.raises(sample.GeometryError, match="model output"):
        sample.validate_geometry({"sample_thickness_um": records.model_value(120.0, "x")})
    assert sample.validate_geometry(
        {"sample_thickness_um": records.Graded(120.0, records.GRADE_COMPUTED)}) == {
        "sample_thickness_um": 120.0}


@pytest.mark.parametrize("shape", [(5, 7), (40, 33), (97, 128)])
@pytest.mark.parametrize("sigma", [0.7, 1.5, 3.3, 25.0])
def test_numpy_filters_are_scipy_bit_for_bit(shape, sigma):
    rng = np.random.default_rng(int(sigma * 10) + shape[0])
    a = rng.normal(1000, 100, shape)
    a[1:3, 2:4] = 7.0  # a flat patch: ties
    m = _flat("map_mosaic")
    assert np.array_equal(m.gaussian_filter(a, sigma), ndimage.gaussian_filter(a, sigma))
    assert np.array_equal(m.gaussian_laplace(a, sigma), ndimage.gaussian_laplace(a, sigma))
    for size in (3, 7):
        assert np.array_equal(m.maximum_filter(a, size), ndimage.maximum_filter(a, size=size))


def _detect_blobs_scipy(img, p):
    """engine.mosaic.detect_blobs before S2 (scipy.ndimage), for the comparison."""
    a = np.asarray(img, np.float64)
    a = a - ndimage.gaussian_filter(a, p.background_sigma_px, mode="reflect")
    if p.polarity == "dark":
        a = -a
    sm = ndimage.gaussian_filter(a, p.sigma_px, mode="reflect")
    resp = -ndimage.gaussian_laplace(a, p.sigma_px, mode="reflect") * p.sigma_px**2
    noise = 1.4826 * float(np.median(np.abs(resp - np.median(resp))))
    if noise <= 0:
        return []
    size = max(3, int(2 * round(2 * p.sigma_px) + 1))
    peaks = (resp == ndimage.maximum_filter(resp, size=size)) & (resp > p.min_snr * noise)
    b = p.border_px
    peaks[:b], peaks[-b:], peaks[:, :b], peaks[:, -b:] = False, False, False, False
    rows, cols = np.nonzero(peaks)
    gy, gx = np.gradient(sm)
    hyy, hyx = np.gradient(gy)
    hxy, hxx = np.gradient(gx)
    out = []
    for r, c in zip(rows, cols, strict=True):
        H = np.array([[hxx[r, c], hxy[r, c]], [hyx[r, c], hyy[r, c]]])
        ev = np.linalg.eigvalsh(0.5 * (H + H.T))
        big = max(abs(ev[0]), abs(ev[1]))
        ratio = 0.0 if big == 0 else min(abs(ev[0]), abs(ev[1])) / big
        if ratio < p.min_blob_ratio or not (ev < 0).all():
            continue
        out.append({"col": float(c), "row": float(r), "snr": float(resp[r, c] / noise),
                    "response": float(resp[r, c]), "blob_ratio": float(ratio)})
    out.sort(key=lambda d: -d["snr"])
    return out[:p.max_per_tile]


@pytest.mark.parametrize("polarity", ["dark", "bright"])
def test_detect_blobs_matches_the_scipy_version(polarity):
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:160, 0:200]
    img = np.full((160, 200), 2700.0) + rng.normal(0, 20, (160, 200))
    for r, c in rng.uniform(15, 145, (12, 2)):
        img -= 600 * np.exp(-((yy - r) ** 2 + (xx - c) ** 2) / (2 * 2.0 ** 2))
    img[:, 150] -= 500  # a line: not a blob
    img[40:44, 60:64] = 2000.0  # a flat-bottomed blob: tied maxima
    p = mosaic.CandidateParams(polarity=polarity)
    found = mosaic.detect_blobs(img, p)
    assert found == _detect_blobs_scipy(img, p)
    if polarity == "dark":
        assert len(found) >= 10


def _remove_small_regions_scipy(mask, min_area):
    out = mask.copy()
    for value in (True, False):
        labels, n = ndimage.label(mask == value)
        if n == 0:
            continue
        sizes = np.bincount(labels.ravel())
        small = np.nonzero(sizes < min_area)[0]
        small = small[small != 0]
        if small.size:
            out[np.isin(labels, small)] = not value
    return out


@pytest.mark.parametrize("seed", range(40))
def test_remove_small_regions_matches_scipy_label(seed):
    rng = np.random.default_rng(seed)
    shape = tuple(rng.integers(1, 60, 2))
    smooth = ndimage.gaussian_filter(rng.normal(size=shape), rng.uniform(0.5, 4))
    mask = smooth > rng.uniform(-0.1, 0.1)
    for min_area in (0, 1, 3, 20, 400):
        assert np.array_equal(edge_trace.remove_small_regions(mask, min_area),
                              _remove_small_regions_scipy(mask, min_area))


@pytest.mark.parametrize("key", ["100x-Oil", "4x", "40x-WI"])
def test_sweep_z_is_the_guards_plan(key):
    fs = _flat("focus_search")
    axis = FocusAxis(None, key)
    rng = np.random.default_rng(len(key))
    n_ok = 0
    for _ in range(300):
        c = float(rng.uniform(2700, 3300))
        h = float(rng.choice([0.0, 0.6, 3.0, 12.0, 40.0, 160.0]))
        s = float(rng.choice([0.2, 1.0, 2.0, 6.0, 10.0]))
        try:
            want = axis.plan(c, h, s)
        except GuardError:
            with pytest.raises(ValueError):
                fs.sweep_z(c, h, s, floor_um=axis.window[0], ceiling_um=axis.ceiling_um(c))
            continue
        assert fs.sweep_z(c, h, s, floor_um=axis.window[0], ceiling_um=want.ceiling_um) == \
            want.z_um
        n_ok += 1
    assert n_ok > 100
    assert key in FREE_WD_UM


def test_focus_100x_plan_uses_the_spans():
    a = focus_100x.parse({})
    pl = focus_100x.plan(a, focus_100x.default_centre(None, None, None))
    fs = _flat("focus_search")
    axis = FocusAxis(None, focus_100x.OBJECTIVE_KEY)
    z = fs.sweep_z(*fs.coarse_span(pl["centre_um"], a), floor_um=axis.window[0],
                   ceiling_um=pl["ceiling_um"])
    assert pl["coarse"] == axis.plan(*fs.coarse_span(pl["centre_um"], a)).describe()
    assert z == axis.plan(pl["centre_um"], a.half_um, a.step_um).z_um
