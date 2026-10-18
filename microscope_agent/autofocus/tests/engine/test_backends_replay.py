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

from dino_autofocus.engine.backend import (
    GUARD_TOKEN,
    CommandPathRetired,
    StreamActive,
)
from dino_autofocus.engine.backends.replay import CAMERA, ReplayBackend
from dino_autofocus.engine.backends.stacks import ZStack

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
    """The contract's reads hold on replay. Its write tests are overridden below: card 077
    retired replay's command path, so each write refuses and nothing changes."""

    @pytest.fixture
    def backend(self, replay):
        return replay

    def _refuses(self, call) -> None:
        before = (self._state(), self._snap_plane())
        with pytest.raises(CommandPathRetired, match="plan.md 15, bc0f4848"):
            call()
        assert (self._state(), self._snap_plane()) == before

    def _state(self):
        b = self.b
        return (b.positions().z_um, b.positions().x_um, b.positions().y_um, b.light_state(),
                b.nosepiece())

    def _snap_plane(self):
        return int(self.b.snap().image[0, 0])

    @pytest.fixture(autouse=True)
    def _bind(self, backend):
        self.b = backend

    def test_info_and_readbacks_carry_json_safe_notes(self, backend):
        json.dumps(backend.info().to_dict())
        self._refuses(lambda: backend.lamp_on(token=T))

    def test_light_on_needs_the_token_and_off_never_does(self, backend):
        for call in (lambda: backend.lamp_on(token=T), backend.lamp_off,
                     lambda: backend.aura_line_on("GREEN", 5.0, token=T), backend.aura_off,
                     backend.all_off):
            self._refuses(call)

    def test_light_property_needs_the_token(self, backend):
        self._refuses(lambda: backend.set_property("DiaLamp", "State", 1, token=T))

    def test_listed_camera_property_needs_no_token(self, backend):
        self._refuses(lambda: backend.set_property(CAMERA, "Binning", "1"))

    def test_move_xy_rel_needs_the_token_and_moves_by_the_step(self, backend):
        for call in (lambda: backend.move_xy_rel(10.0, 0.0, token=T),
                     lambda: backend.move_xy(10.0, 0.0, token=T),
                     lambda: backend.move_z(2950.0, token=T),
                     lambda: backend.set_nosepiece(0, token=T),
                     lambda: backend.pfs_off(token=T)):
            self._refuses(call)

    def test_set_property_refuses_motion_devices_even_with_the_token(self, backend):
        self._refuses(lambda: backend.set_property("ZDrive", "Position", 1.0, token=T))

    def test_unlisted_property_is_refused_with_the_allow_list(self, backend):
        self._refuses(lambda: backend.set_property("Nope", "Nope", 1, token=T))


def test_snap_reads_the_plane_nearest_the_z_it_was_built_with():
    """Reading a recorded stack stays (card 077): the plane nearest the z given at build time,
    the lower one on a tie, the edge plane (clamped) outside the stack."""
    for z, want, clamped in ((2951.0, 110, False), (2952.5, 110, False), (3500.0, 120, True)):
        b = ReplayBackend([stack(x_um=0.0, y_um=0.0)], z_um=z)
        b.open()
        try:
            assert int(b.snap().image[0, 0]) == want and b.last_hit.clamped is clamped, z
            assert b.positions().z_um == z
        finally:
            b.close()


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


def test_real_smoke_data():
    if not SMOKE.exists():
        pytest.skip("data/smoke not present (gitignored, generated on the microscope PC)")
    b = ReplayBackend(SMOKE)
    b.open()
    f = b.snap()
    assert f.image.dtype == np.uint16 and f.image.ndim == 2
    b.close()
