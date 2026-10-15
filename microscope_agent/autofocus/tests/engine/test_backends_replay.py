"""Replay backend (T-034): saved z-stacks through the Backend protocol.

Stacks are built in memory here. The one real-data test skips when data/smoke (gitignored,
generated on the microscope PC) is absent.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from test_contract_backend_v2 import BackendContract

from dino_autofocus.engine import GuardError
from dino_autofocus.engine.backend import (
    GUARD_TOKEN,
    PropertyNotAllowed,
    StreamActive,
    UnguardedMotion,
)
from dino_autofocus.engine.backends.replay import CAMERA, VIRTUAL_SPACING_UM, ReplayBackend
from dino_autofocus.engine.backends.stacks import ZStack
from dino_autofocus.engine.guards import FocusAxis

T = GUARD_TOKEN  # tests stand in for engine.guards
SMOKE = Path(__file__).resolve().parents[2] / "data" / "smoke"


def stack(z0=2900.0, n=21, step=5.0, base=100, shape=(32, 32), **meta) -> ZStack:
    """Plane i is filled with base + i, so a frame tells which plane it came from."""
    z = z0 + step * np.arange(n)
    frames = np.stack([np.full(shape, base + i, np.uint16) for i in range(n)])
    return ZStack.from_arrays(frames, z, objective="1-Plan Apo LmbdD20 4x", pixel_um=1.625,
                              z_kind="ZDrive (um)", **meta)


def focus_stack(best=2950.0) -> ZStack:
    """Speckle whose contrast falls with |z - best|: its standard deviation peaks at `best`."""
    rng = np.random.default_rng(0)
    z = np.arange(2900.0, 3001.0, 5.0)
    speckle = rng.random((48, 48))
    frames = [1000 + 800 * np.exp(-((zi - best) / 15.0) ** 2) * speckle for zi in z]
    return ZStack.from_arrays(frames, z, best_focus_um=best, z_kind="ZDrive (um)",
                              objective="1-Plan Apo LmbdD20 4x")


@pytest.fixture
def replay():
    b = ReplayBackend([stack(x_um=0.0, y_um=0.0), stack(base=500, x_um=5000.0, y_um=0.0)])
    b.open()
    yield b
    b.close()


class TestReplayContract(BackendContract):
    @pytest.fixture
    def backend(self, replay):
        return replay


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s


def plane(b: ReplayBackend) -> int:
    return int(b.snap().image[0, 0])


def test_imports_nothing_heavy():
    code = ("import sys, dino_autofocus.engine.backends.replay; "
            "bad = {'torch', 'pymmcore', 'pymmcore_plus', 'tkinter'} & set(sys.modules); "
            "assert not bad, bad")
    subprocess.run([sys.executable, "-c", code], check=True)


def test_info_is_not_bench_and_says_what_z_is(replay):
    info = replay.info()
    assert not info.bench and info.kind == "replay" and info.camera == CAMERA
    assert info.notes["z_kind"] == "ZDrive (um)" and info.notes["stacks"] == "2"
    assert info.pixel_um == 1.625 and info.objective == "1-Plan Apo LmbdD20 4x"
    json.dumps(info.to_dict())


def test_snap_is_the_plane_nearest_the_virtual_z(replay):
    with pytest.raises(UnguardedMotion):
        replay.move_z(2950.0, token=None)
    assert replay.move_z(2951.0, token=T) == 2951.0 and replay.positions().z_um == 2951.0
    assert plane(replay) == 110 and replay.last_hit.z_um == 2950.0
    replay.move_z(2952.5, token=T)  # a tie goes to the lower plane
    assert plane(replay) == 110
    replay.move_z(3500.0, token=T)
    assert plane(replay) == 120 and replay.last_hit.clamped


def test_xy_picks_the_nearest_stack(replay):
    assert plane(replay) == 110  # the first stack's median plane
    replay.move_xy(4000.0, 0.0, token=T)
    assert plane(replay) == 510
    replay.move_xy_rel(-3000.0, 0.0, token=T)
    assert replay.positions().x_um == 1000.0 and plane(replay) == 110


def test_one_stack_stays_and_stacks_without_xy_get_a_virtual_row():
    one = ReplayBackend(stack())
    one.move_xy(9000.0, 9000.0, token=T)
    assert plane(one) == 110
    two = ReplayBackend([stack(), stack(base=500)])
    assert two.stack_xy == [(0.0, 0.0), (VIRTUAL_SPACING_UM, 0.0)]
    assert "virtual" in two.info().notes["xy"]


def test_lights_are_virtual_and_leave_the_frames_alone(replay):
    before = plane(replay)
    with pytest.raises(UnguardedMotion):
        replay.aura_line_on("GREEN", 1, token=None)
    rbs = replay.aura_line_on("green", 1, token=T)
    assert [(r.device, r.prop, r.read) for r in rbs] == [
        ("DiaLamp", "State", "0"), ("Aura", "GREEN_Intensity", "10"), ("Aura", "GREEN", "1"),
        ("Aura", "State", "1")]
    assert plane(replay) == before and replay.light_state() == {"DiaLamp": "0", "Aura": "1"}
    assert all(r.verified for r in replay.all_off())
    assert replay.set_property("DiaLamp", "Intensity", 300, token=T).verified
    with pytest.raises(PropertyNotAllowed):
        replay.set_property("White Light Shutter", "State", 0, token=T)


def test_roi_crops_the_recorded_frame(replay):
    assert replay.set_roi(16) == (8, 8, 16, 16) and replay.snap().image.shape == (16, 16)
    assert replay.set_roi(0) == (0, 0, 32, 32)


def test_stream_paces_and_blocks_snap():
    clock = FakeClock()
    b = ReplayBackend(stack(), clock=clock, sleep=clock.sleep)
    b.start_stream(interval_ms=100)
    try:
        assert b.next_frame() is not None and b.next_frame() is not None
        assert clock.t == pytest.approx(0.1)
        assert b.next_frame(timeout_s=0.01) is None
        with pytest.raises(StreamActive):
            b.snap()
    finally:
        b.close()
    assert not b.streaming()


def test_a_guarded_sweep_on_replay_finds_the_recorded_focus():
    b = ReplayBackend(focus_stack(), z_um=2905.0)
    b.open()
    axis = FocusAxis(b, b.nosepiece(), allow_motion=True, sleep=lambda s: None)
    res = axis.sweep(axis.plan(2950, 40, 5), b.snap, score=lambda f: float(f.image.std()))
    assert res.peak_interior and res.peak_z_um == 2950.0
    with pytest.raises(GuardError):  # the guards still own the window
        axis.move_to(3300.0, allow_ascent_um=500)
    b.close()


def test_real_smoke_data():
    if not SMOKE.exists():
        pytest.skip("data/smoke not present (gitignored, generated on the microscope PC)")
    b = ReplayBackend(SMOKE)
    b.open()
    f = b.snap()
    assert f.image.dtype == np.uint16 and f.image.ndim == 2
    b.close()
