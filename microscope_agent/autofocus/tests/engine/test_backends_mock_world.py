"""The mock microscope's virtual world (T-007): optics, focus behaviour, lights, faults, state.

Numbers checked against the 2026-09-30 bench run where it gave one
(docs/runs/2026-09-30_substrate-scan.md).
"""

import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from dino_autofocus.bench_values import PEAK_BIN_PX
from dino_autofocus.engine.backends.mock_world import (
    OBJECTIVES,
    MockWorld,
    SampleSpec,
    StageLimitError,
    objective_at,
)
from dino_autofocus.engine.guards import (
    OBJECTIVE_LIMITS,
    STRICTEST,
    limits_for,
    registry_key,
)
from dino_autofocus.focus.classical import peak_brightness as peak
from dino_autofocus.focus.classical import vollath4

CONFIGS = Path(__file__).resolve().parents[2] / "configs"


def particle_light(w, permille=10):
    w.set_dialamp(False)
    w.set_aura_line("GREEN", True, permille)
    w.set_aura(True)


def isolated_particle(w, clear_um=40.0, upper=False):
    """A particle with no neighbour within clear_um, away from the hole wall."""
    s = w.sample
    hx, hy = s.spec.hole_centre_um
    for i in range(len(s.px)):
        if bool(s.upper[i]) != upper:
            continue
        if np.hypot(s.px[i] - hx, s.py[i] - hy) > s.radius_um - 200:
            continue
        dist = np.hypot(s.px - s.px[i], s.py - s.py[i])
        if np.sort(dist)[1] > clear_um:
            return i
    raise AssertionError("no isolated particle in this sample")


@pytest.fixture
def world():
    w = MockWorld(seed=1)
    w.set_roi(512)
    return w


# ---------------------------------------------------------------- optics table


def test_objectives_match_the_ti2_configs():
    yaml = pytest.importorskip("yaml")  # the synth extra
    for o in OBJECTIVES:
        key = o.key.split("-")[0]
        text = (CONFIGS / f"ti2_{key}.yaml").read_text(encoding="utf-8")
        cfg = yaml.safe_load(text)["system"]["objective"]
        assert (o.na, o.magnification, o.n_immersion, o.working_distance_um) == (
            cfg["na"], cfg["magnification"], cfg["n_immersion"], cfg["working_distance"])
        assert int(re.search(r"nosepiece position (\d)", text).group(1)) == o.position
    assert objective_at(0).label == "1-Plan Apo LmbdD20 4x"
    assert objective_at(5).label == "6-Plan Apo LmbdD0.13 100x Oil"
    assert objective_at(0).pixel_um == pytest.approx(1.625)
    assert objective_at(0).dof_um == pytest.approx(15.1, abs=0.1)  # n lambda / NA^2
    with pytest.raises(ValueError):
        objective_at(6)


def test_every_mock_lens_key_has_its_own_guards_row():
    """Each mock key is a guards row, so no mock lens falls back to the strictest limits."""
    for o in OBJECTIVES:
        row, row_name = limits_for(o.key)
        assert row_name == o.key and row is OBJECTIVE_LIMITS[o.key], (o.key, row_name)
        assert "strictest" not in row_name and row != STRICTEST
    assert {o.key for o in OBJECTIVES} == set(OBJECTIVE_LIMITS)


@pytest.mark.parametrize("o", [pytest.param(o, id=o.key) for o in OBJECTIVES])
def test_every_mock_lens_label_reads_back_to_its_key(o):
    """What the mock nosepiece reports maps to the same guards row as the key."""
    assert registry_key(o.label) == o.key
    assert limits_for(o.label)[1] == o.key


def test_parfocal_offset_100x_is_60_um_below_4x(world):
    z4 = world.in_focus_z(objective=objective_at(0))
    assert z4 == pytest.approx(3048.7)  # hole centre, 2026-09-30 plane fit
    assert world.in_focus_z(objective=objective_at(5)) == pytest.approx(z4 - 60.0)
    offs = [o.parfocal_um for o in OBJECTIVES]
    assert offs == sorted(offs, reverse=True)  # estimates between 4x and 100x are monotone


def test_focus_plane_is_tilted_as_measured(world):
    hx, hy = world.spec.hole_centre_um
    z = world.in_focus_z
    assert z(hx + 1000, hy) - z(hx, hy) == pytest.approx(-1.66)
    assert z(hx, hy + 1000) - z(hx, hy) == pytest.approx(-3.62)


# ---------------------------------------------------------------- determinism


def test_same_seed_same_frame_and_new_noise_per_snap():
    a, b = MockWorld(seed=3), MockWorld(seed=3)
    for w in (a, b):
        w.set_roi(256)
        particle_light(w)
        w.set_exposure(994)
        w.move_z(w.in_focus_z())
    fa, fb = a.snap(), b.snap()
    assert np.array_equal(fa, fb)
    assert not np.array_equal(a.snap(), fa)  # next frame: same scene, new noise
    assert not np.array_equal(MockWorld(seed=4).sample.px[:5], a.sample.px[:5])
    args = (a.x_um, a.y_um, a.z_um, a.objective, a.light, a.exposure_ms, a.roi, 1, 0)
    assert np.array_equal(a.render(*args), fa)  # render is pure


# ---------------------------------------------------------------- focus behaviour


def test_4x_vollath_peaks_at_focus_and_falls_with_defocus(world):
    particle_light(world)
    world.set_exposure(994)
    z0 = world.in_focus_z()
    score = {}
    for dz in (-60, -30, -15, -5, 0, 5, 15, 30, 60):
        world.move_z(z0 + dz)
        score[dz] = vollath4(world.snap())
    assert max(score, key=score.get) == 0
    for side in (1, -1):
        seq = [score[side * d] for d in (0, 5, 15, 30, 60)]
        assert all(x > y for x, y in zip(seq, seq[1:], strict=False)), seq


def test_100x_peak_metric_finds_a_sparse_particle_where_vollath_does_not(world):
    world.set_nosepiece(5)
    i = isolated_particle(world)
    s = world.sample
    world.move_xy(s.px[i], s.py[i])
    particle_light(world)
    world.set_exposure(20)
    zt = float(s.particle_z(i)) + world.objective.parfocal_um
    zs = zt + np.arange(-10.0, 10.5, 1.0)
    pk, vo = [], []
    for z in zs:
        world.move_z(z)
        f = world.snap()
        pk.append(peak(f, PEAK_BIN_PX))
        vo.append(vollath4(f))
    assert abs(zs[int(np.argmax(pk))] - zt) <= 1.0
    assert max(abs(v) for v in vo) < 0.5  # vs ~17 at 4x: Vollath sees nothing (2026-09-30)


def test_upper_particles_focus_15_to_25_um_above_the_layer(world):
    s = world.sample
    up = np.flatnonzero(s.upper)
    assert len(up) > 0
    h = s.particle_z(up) - s.focus_z(s.px[up], s.py[up])
    assert np.all((h >= 15) & (h <= 25))


def test_flipped_sample_puts_the_layer_on_the_far_wall():
    w = MockWorld(SampleSpec(seed=1, flipped=True, chamber_um=120.0))
    assert w.in_focus_z() == pytest.approx(3048.7 + 120.0)
    up = np.flatnonzero(w.sample.upper)
    assert np.all(w.sample.height[up] < 0)


# ---------------------------------------------------------------- light and camera


def test_brightfield_level_matches_the_bench(world):
    world.move_z(world.in_focus_z())
    world.set_dialamp(True, 608)
    world.set_exposure(10)
    med = float(np.median(world.snap()))
    assert med == pytest.approx(2766, rel=0.03)  # 4x, 10 ms, 2026-09-30


def test_100x_in_focus_particle_level_matches_the_bench(world):
    world.set_nosepiece(5)
    i = isolated_particle(world)
    s = world.sample
    world.move_xy(s.px[i], s.py[i])
    world.move_z(float(s.particle_z(i)) + world.objective.parfocal_um)
    particle_light(world)
    world.set_exposure(20)
    assert int(world.snap().max()) == pytest.approx(3435, rel=0.1)  # Aura GREEN 1 %, 20 ms


def test_lights_off_is_the_dark_offset(world):
    world.all_off()
    f = world.snap()
    assert float(np.median(f)) == pytest.approx(102, abs=1)
    assert 0.5 < float(f.std()) < 3.0 and int(f.max()) < 120


def test_saturation_clips_at_the_12_bit_ceiling(world):
    world.move_z(world.in_focus_z())
    world.set_dialamp(True)
    world.set_exposure(30)  # ">= 30 ms saturated" on 2026-09-30
    f = world.snap()
    assert f.dtype == np.uint16 and int(f.max()) == 4095
    assert float(np.mean(f == 4095)) > 0.9


def test_aura_master_and_line_both_gate_the_light(world):
    world.set_aura_line("GREEN", True, 10)
    assert world.light.fluor_permille == 0  # master State still off
    world.set_aura(True)
    assert world.light.fluor_permille == 10
    world.set_aura_line("GREEN", False)
    assert world.light.fluor_permille == 0
    with pytest.raises(ValueError, match="per-mille"):
        world.set_aura_line("GREEN", True, 1001)


def test_hole_edge_is_mirrored_against_the_stage(world):
    """Stage on the edge's +x point: sample +x (outside the hole, darker spacer) is on the
    image's left, because columns run toward -x."""
    hx, hy = world.spec.hole_centre_um
    world.move_xy(hx + world.sample.radius_um, hy)
    world.move_z(world.in_focus_z())
    world.set_dialamp(True)
    world.set_exposure(10)
    cols = world.snap().mean(axis=0)
    left, right, mid = cols[:150].mean(), cols[-150:].mean(), cols[236:276].min()
    assert left < 0.75 * right
    assert mid < left  # the dark edge line sits at the field centre


def test_pixel_mapping_follows_the_plan_convention(world):
    """PLAN v1.2: stage of pixel p = stage + inv(M) @ (centre - p), 9/30 4x M."""
    m = np.array([[0.61602, 0.00236], [0.00126, -0.61456]])
    st = np.array([world.x_um, world.y_um])
    centre = np.array([1199.5, 1199.5])
    for p in ([0.0, 0.0], [2399.0, 100.0], [1199.5, 1199.5]):
        want = st + np.linalg.solve(m, centre - np.array(p))
        assert world.stage_of_pixel(*p) == pytest.approx(tuple(want))
        assert world.pixel_of_stage(*want) == pytest.approx(tuple(p))
    assert np.allclose(world.pixel_matrix(objective_at(5)), m * 25)


def test_particle_is_drawn_where_the_matrix_puts_it(world):
    world.set_nosepiece(5)
    i = isolated_particle(world, clear_um=80.0)  # alone in a 1024-px (67 um) field
    s = world.sample
    world.move_xy(s.px[i] + 10.0, s.py[i] - 6.0)  # particle off-centre in the field
    world.move_z(float(s.particle_z(i)) + world.objective.parfocal_um)
    particle_light(world)
    world.set_exposure(10)
    world.set_roi(1024)
    world.binning = 2
    f = world.snap().astype(float) - 102
    f[f < 0.3 * f.max()] = 0
    rr, cc = np.indices(f.shape)
    got = (float((cc * f).sum() / f.sum()), float((rr * f).sum() / f.sum()))
    col, row = world.pixel_of_stage(s.px[i], s.py[i])
    x0 = y0 = (2400 - 1024) // 2  # ROI origin in sensor px
    want = ((col - x0 + 0.5) / 2 - 0.5, (row - y0 + 0.5) / 2 - 0.5)
    assert got == pytest.approx(want, abs=1.0)
    assert want[0] > 256 + 50  # particle at -x of the stage sits right of centre: the mirror


def test_zdrive_up_is_toward_the_sample_and_zero_is_retract(world):
    world.move_z(0.0)  # full retract is inside the travel
    with pytest.raises(StageLimitError):
        world.move_z(-0.1)
    s = world.sample
    up = np.flatnonzero(s.upper)
    assert np.all(s.particle_z(up) > s.focus_z(s.px[up], s.py[up]))  # deeper = higher z


def test_roi_and_binning(world):
    world.set_roi(518)
    assert world.roi == (941, 941, 518, 518)
    assert world.snap().shape == (518, 518)
    world.set_roi((0, 0, 400, 200))
    world.binning = 2
    assert world.snap().shape == (100, 200)
    world.set_roi(None)
    world.binning = 8
    assert world.snap().shape == (300, 300)
    for bad in (0, 2401, (2300, 0, 200, 10)):
        with pytest.raises(ValueError):
            world.set_roi(bad)


# ---------------------------------------------------------------- stage, PFS, faults


def test_stage_moves_report_time_and_refuse_outside_travel(world):
    t = world.move_xy(world.x_um + 5000, world.y_um)
    assert t == pytest.approx(5000 / world.limits.xy_speed_um_s + world.limits.settle_s)
    with pytest.raises(StageLimitError):
        world.move_xy(1e6, 0)
    with pytest.raises(StageLimitError):
        world.move_z(-1.0)
    with pytest.raises(ValueError):
        world.set_nosepiece(7)


def test_pfs_is_off_and_out_of_range_and_never_switched_on(world):
    assert (world.pfs_enabled, world.pfs_in_range) == (False, "Out of Range")
    world.pfs_disable()
    assert not world.pfs_enabled
    methods = [n for n in dir(world) if callable(getattr(world, n)) and "pfs" in n.lower()]
    assert methods == ["pfs_disable"]


def test_readback_error_injection(world):
    w = world.with_faults(z_readback_error_um=-1.0, xy_readback_error_um=(0.5, 0.0))
    w.move_z(3037.0)
    assert w.z_um == 3037.0 and w.read_z() == 3036.0  # 2026-09-30 guard stop
    assert w.read_xy() == (w.x_um + 0.5, w.y_um)
    assert world.read_z() == world.z_um  # the original world has no fault


def test_light_dropout_injection(world):
    w = world.with_faults(dropout_frames=(1,))
    particle_light(w)
    w.set_exposure(994)
    w.move_z(w.in_focus_z())
    means = [float(w.snap().mean()) - 102 for _ in range(3)]
    assert means[1] == pytest.approx(0.77 * means[0], rel=0.03)
    assert means[2] == pytest.approx(means[0], rel=0.03)


# ---------------------------------------------------------------- state


def test_state_round_trip_through_json(world):
    particle_light(world)
    world.set_nosepiece(5)
    world.move_z(2989.4)
    world.snap()
    d = json.loads(json.dumps(world.to_dict()))
    w2 = MockWorld.from_dict(d)
    assert w2.state_dict() == world.state_dict()
    assert np.array_equal(w2.snap(), world.snap())  # same frame_index, same frame
    assert d["state"]["objective"] == "6-Plan Apo LmbdD0.13 100x Oil"


# ---------------------------------------------------------------- cost and imports


PERF = os.environ.get("DINOAF_PERF") == "1"


def _snap_times(world, n=5):
    world.move_xy(world.spec.hole_centre_um[0] + world.sample.radius_um, world.y_um)
    world.move_z(world.in_focus_z())
    world.set_dialamp(True)
    particle_light(world)
    world.set_dialamp(True)  # both lights: the most work per frame
    world.snap()
    return [_timed(world.snap) for _ in range(n)]


@pytest.mark.skipif(not PERF, reason="strict timing bound; set DINOAF_PERF=1 on an idle machine")
def test_512_frame_renders_under_50_ms(world):
    best = min(_snap_times(world))  # min: robust to a busy machine
    assert best < 0.05, f"{best * 1e3:.0f} ms"


def test_512_frame_renders_in_reasonable_time(world):
    """Always on: loose enough for a machine loaded by other test runs, tight enough that a
    real regression (a frame ten times over the 50 ms target) still fails."""
    median = statistics.median(_snap_times(world))
    assert median < 0.5, f"{median * 1e3:.0f} ms"


def _timed(fn):
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t


def test_import_pulls_in_no_heavy_modules():
    code = ("import sys, dino_autofocus.engine.backends.mock_world; "
            "print(sorted({'torch', 'pymmcore', 'pymmcore_plus', 'tkinter'} & set(sys.modules)))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         check=True).stdout.strip()
    assert out == "[]"
