"""MockBackend (T-021): the backend contract, and the T-002 guards and scopes on the mock.

The T-002 contract tests themselves drive FakeBackend internals (`fake.z`, `fake.calls`,
patched methods), so they are not re-run verbatim. Here the shared `BackendContract`
(T-015) runs against MockBackend, and the T-002 guard and scope rules are exercised on it
through their public API: Z/XY readback stops, sweeps that find the world's focus, lights
off on every exit path.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict

import numpy as np
import pytest
from test_contract_backend_v2 import BackendContract

from dino_autofocus.engine import GuardError
from dino_autofocus.engine.backend import (
    GUARD_TOKEN,
    PROVISIONAL,
    Backend,
    PropertyNotAllowed,
    StreamActive,
    UnguardedMotion,
)
from dino_autofocus.engine.backends.mock import CAMERA, MockBackend
from dino_autofocus.engine.backends.mock_world import StageLimitError
from dino_autofocus.engine.guards import FocusAxis, XYAxis, XYBox, operation
from dino_autofocus.focus.classical import vollath4

ROI = 128  # px; small frames keep the suite fast


@pytest.fixture
def mock():
    b = MockBackend(seed=1)
    b.open()
    b.set_roi(ROI)
    yield b
    b.all_off()
    b.close()


class TestMockBackendContract(BackendContract):
    @pytest.fixture
    def backend(self, mock):
        return mock


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s


def at_sample(b: MockBackend, z_um: float | None = None) -> float:
    """Put the stage at the sample: hole centre, Z at the 4x focus (test set-up, like
    `fake.z = ...`)."""
    w = b.world
    w.move_z(w.in_focus_z() if z_um is None else z_um)
    return w.z_um


# -- protocol and import


def test_meets_the_protocol_and_imports_nothing_heavy(mock):
    assert isinstance(mock, Backend)
    code = ("import sys, dino_autofocus.engine.backends.mock; "
            "bad = {'torch', 'pymmcore', 'pymmcore_plus', 'tkinter', 'PySide6', 'PyQt5'}"
            " & set(sys.modules); assert not bad, bad")
    subprocess.run([sys.executable, "-c", code], check=True)


def test_info_is_the_bench_shape_with_provisional_notes(mock):
    info = mock.info()
    assert info.kind == "mock" and info.camera == CAMERA and info.ceiling_adu == 4095
    assert info.objective == "1-Plan Apo LmbdD20 4x" and info.pixel_um == pytest.approx(1.625)
    assert [o.state for o in info.objectives] == [0, 1, 2, 3, 4, 5]
    assert info.roi == (1136, 1136, ROI, ROI)
    assert info.notes["aura.CYAN"] == PROVISIONAL and "aura.GREEN" not in info.notes
    assert info.notes["stage_limits"] == PROVISIONAL
    json.dumps(info.to_dict())


# -- motion goes through the token, z is bench coordinates


def test_motion_needs_the_token_and_z_is_bench(mock):
    for call in (lambda: mock.move_z(3000.0, token=None),
                 lambda: mock.move_xy(0.0, 0.0, token=None),
                 lambda: mock.set_nosepiece(5, token=None),
                 lambda: mock.pfs_off(token=None)):
        with pytest.raises(UnguardedMotion):
            call()
    assert mock.move_z(3000.0, token=GUARD_TOKEN) == 3000.0
    assert mock.positions().z_um == 3000.0 and mock.world.z_um == 3000.0
    with pytest.raises(StageLimitError):  # the stage's own travel, not a guard
        mock.move_z(-5.0, token=GUARD_TOKEN)
    rb = mock.set_nosepiece(5, token=GUARD_TOKEN)
    assert rb.verified and mock.nosepiece() == "6-Plan Apo LmbdD0.13 100x Oil"


def test_xy_timeout_raises_after_the_stage_moved(mock):
    x0, y0 = mock.world.x_um, mock.world.y_um
    with pytest.raises(TimeoutError):
        mock.move_xy(x0 + 30000.0, y0, token=GUARD_TOKEN, timeout_s=5.0)
    assert mock.positions().x_um == pytest.approx(x0 + 30000.0)


def test_relative_move_starts_from_the_read_and_time_scale_sleeps():
    clock = FakeClock()
    b = MockBackend(seed=1, move_time_scale=1.0, clock=clock, sleep=clock.sleep)
    b.inject_faults(xy_readback_error_um=(2.0, 0.0))
    x_read = b.positions().x_um
    x, _ = b.move_xy_rel(100.0, 0.0, token=GUARD_TOKEN)
    assert x == pytest.approx(x_read + 100.0 + 2.0)  # target = read + d; read adds the error
    assert clock.t == pytest.approx(102.0 / b.world.limits.xy_speed_um_s  # true travel
                                    + b.world.limits.settle_s)


# -- lights


def test_lights_follow_the_bench_order_and_render(mock):
    at_sample(mock)
    dark = mock.snap().image.mean()
    rbs = mock.aura_line_on("green", 1, token=GUARD_TOKEN)
    assert [(r.device, r.prop, r.wanted) for r in rbs] == [
        ("DiaLamp", "State", "0"), ("Aura", "GREEN_Intensity", "10"), ("Aura", "GREEN", "1"),
        ("Aura", "State", "1")]
    assert all(r.verified and not r.notes for r in rbs)
    assert mock.read_property("Aura", "GREEN_Intensity") == "10"
    assert mock.lamp_on(token=GUARD_TOKEN)[-1].verified
    assert mock.light_state() == {"DiaLamp": "1", "Aura": "0"}
    bright = mock.snap().image.mean()
    assert all(r.verified for r in mock.all_off())
    assert dark == pytest.approx(102, abs=3) and bright > 1000
    assert mock.snap().image.mean() == pytest.approx(102, abs=3)


def test_unmeasured_aura_lines_are_marked(mock):
    rbs = mock.aura_line_on("CYAN", 2, token=GUARD_TOKEN)
    assert {r.prop: r.notes for r in rbs}["CYAN"] == {"aura_line": PROVISIONAL}
    rb = mock.set_property("Aura", "RED_Intensity", 5, token=GUARD_TOKEN)
    assert rb.verified and rb.notes == {"aura_line": PROVISIONAL}
    with pytest.raises(ValueError):
        mock.aura_line_on("ULTRAVIOLET", 1, token=GUARD_TOKEN)


def test_set_property_applies_allowed_writes_and_refuses_the_rest(mock):
    assert mock.set_property("DiaLamp", "Intensity", 300, token=GUARD_TOKEN).verified
    assert mock.world.light.dia_intensity == 300
    assert mock.set_property(CAMERA, "Exposure", 25).verified and mock.info().exposure_ms == 25
    mock.set_property(CAMERA, "Binning", 2)
    assert mock.snap().image.shape == (ROI // 2, ROI // 2)
    with pytest.raises(ValueError, match="no device"):  # demo names pass the list, not the mock
        mock.set_property("White Light Shutter", "State", 0, token=GUARD_TOKEN)
    with pytest.raises(PropertyNotAllowed):
        mock.set_property("LightPath", "State", "4-L100")


# -- discovery


def test_describe_devices_has_the_hardware_profile_shape(mock):
    devs = {d.label: d for d in mock.describe_devices()}
    assert set(devs) >= {CAMERA, "ZDrive", "XYStage", "Nosepiece", "PFS", "DiaLamp", "Aura"}
    assert devs["Nosepiece"].properties["Label"].allowed[5] == "6-Plan Apo LmbdD0.13 100x Oil"
    assert devs["DiaLamp"].properties["Intensity"].limits == (0.0, 2100.0)
    assert devs["XYStage"].type == "XYStageDevice" and devs["PFS"].properties[
        "PFS in Range"].read_only
    json.dumps([asdict(d) for d in devs.values()])
    assert mock.config_record().sha256 and not mock.config_record().changed_during_load
    assert [n.pixel_um for n in mock.nosepiece_labels()][::5] == pytest.approx([1.625, 0.065])
    assert mock.piezo_read("COM4").z_um == 9.94
    assert mock.piezo_read("COM9").error and not mock.piezo_read("COM9").connected


# -- stream


def test_stream_paces_frames_drops_late_ones_and_times_out():
    clock = FakeClock()
    b = MockBackend(seed=1, clock=clock, sleep=clock.sleep)
    b.set_roi(64)
    b.start_stream(interval_ms=100)
    try:
        f0 = b.next_frame()
        assert f0 is not None and clock.t == 0.0
        f1 = b.next_frame()  # waits for the next due frame
        assert f1 is not None and clock.t == pytest.approx(0.1)
        n = b.world.frame_index
        clock.t += 0.55  # consumer late: frames 2-6 due, only the newest is returned
        assert b.next_frame() is not None and b.world.frame_index == n + 1
        assert b.next_frame(timeout_s=0.01) is None  # next one due at 0.7 s
        with pytest.raises(StreamActive):
            b.snap()
    finally:
        b.close()
    assert not b.streaming()


def test_stream_frames_see_motion_and_dropout(mock):
    at_sample(mock)
    mock.lamp_on(token=GUARD_TOKEN)
    k = mock.world.frame_index
    mock.inject_faults(dropout_frames=(k + 1,))
    mock.start_stream(interval_ms=1)
    try:
        a = mock.next_frame(timeout_s=5)
        b = mock.next_frame(timeout_s=5)
        mock.move_z(3000.0, token=GUARD_TOKEN)
        c = mock.next_frame(timeout_s=5)
    finally:
        mock.stop_stream()
    assert b.image.mean() < 0.85 * a.image.mean()  # the -23 % frame
    assert c.z_um == 3000.0 and a.z_um != 3000.0


# -- T-002 guards and scopes on the mock


def test_focus_sweep_on_the_mock_finds_the_world_focus(mock, tmp_path):
    focus = mock.world.in_focus_z()
    at_sample(mock, round(focus) - 40)
    with operation(mock, tmp_path, "sweep") as op:
        op.lamp_on()
        axis = FocusAxis(mock, mock.nosepiece(), allow_motion=True, sleep=lambda s: None)
        coarse = axis.sweep(axis.plan(round(focus), 40, 10), mock.snap,
                            score=lambda f: vollath4(f.image))
        fine = axis.sweep(axis.plan(coarse.peak_z_um, 10, 2), mock.snap,
                          score=lambda f: vollath4(f.image))
    assert coarse.peak_interior
    assert fine.peak_z_um == pytest.approx(focus, abs=2 * mock.world.objective.dof_um + 2)
    assert mock.light_state() == {"DiaLamp": "0", "Aura": "0"}


def test_injected_z_readback_error_stops_the_guard(mock):
    at_sample(mock, 3036.0)
    mock.inject_faults(z_readback_error_um=-1.0)  # 3037 commanded, 3036 read (2026-09-30)
    with pytest.raises(GuardError, match="read 3036"):
        FocusAxis(mock, mock.nosepiece(), allow_motion=True).move_to(3037,
                                                                     allow_ascent_um=2)


def test_injected_xy_readback_error_stops_the_guard(mock):
    x, y = mock.world.x_um, mock.world.y_um
    xy = XYAxis(mock, XYBox.around((x, y), 5000), allow_motion=True)
    xy.goto(x + 50, y)
    mock.inject_faults(xy_readback_error_um=(20.0, 0.0))  # a hand on the joystick
    with pytest.raises(GuardError, match="XY commanded"):
        xy.goto(x + 100, y)


def test_long_xy_move_needs_z_retracted_on_the_mock(mock):
    at_sample(mock, 3000.0)
    mock.set_nosepiece(5, token=GUARD_TOKEN)  # 100x Oil: long move > 156 um
    x, y = mock.world.x_um, mock.world.y_um
    xy = XYAxis(mock, XYBox.around((x, y), 5000), allow_motion=True)
    with pytest.raises(GuardError, match="needs Z retracted"):
        xy.goto(x + 500, y)
    mock.world.move_z(0.0)
    assert xy.goto(x + 500, y)[0] == pytest.approx(x + 500)


@pytest.mark.parametrize("exc, status", [(RuntimeError("boom"), "error"),
                                         (KeyboardInterrupt(), "aborted")])
def test_lights_go_off_on_every_exit_path_on_the_mock(mock, tmp_path, exc, status):
    with pytest.raises(type(exc)), operation(mock, tmp_path, "op") as op:
        op.aura_line_on("GREEN", 1)
        assert mock.world.light.any_on
        raise exc
    s = json.loads((tmp_path / op.op_id / "summary.json").read_text())
    assert s["status"] == status and s["lights_off"]["verified"]
    assert not mock.world.light.any_on


def test_same_seed_same_frames():
    a, b = MockBackend(seed=3), MockBackend(seed=3)
    for m in (a, b):
        m.set_roi(64)
        at_sample(m)
        m.lamp_on(token=GUARD_TOKEN)
    assert np.array_equal(a.snap().image, b.snap().image)
