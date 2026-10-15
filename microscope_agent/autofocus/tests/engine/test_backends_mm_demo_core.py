"""Micro-Manager demo devices in bench terms (T-017).

`ZMap` and the import check run anywhere. The rest loads pymmcore-plus's demo config (simulated
devices, no hardware) and skips when the demo adapters are not installed. Each test gets its
own core, closed afterwards.
"""

import subprocess
import sys
import time

import numpy as np
import pytest

from dino_autofocus.engine.backends.mm_demo_core import (
    AURA_LINES,
    BENCH_OBJECTIVE_LABELS,
    DemoDevices,
    DemoReadback,
    DemoUnavailable,
    DemoZRangeError,
    ZMap,
)


def vollath4(img: np.ndarray) -> float:
    """Same as scripts/mm_grab.py vollath4 (the classical metric the bench runs used)."""
    a = img.astype(np.float32)
    a = a - np.median(a)
    a /= max(float(np.abs(a).mean()), 1e-6)
    f = (a[:, :-1] * a[:, 1:]).mean() - (a[:, :-2] * a[:, 2:]).mean()
    g = (a[:-1] * a[1:]).mean() - (a[:-2] * a[2:]).mean()
    return float(f + g)


@pytest.fixture
def demo():
    try:
        dev = DemoDevices.open(roi=512)
    except DemoUnavailable as e:
        pytest.skip(f"Micro-Manager demo adapters not available: {e}")
    try:
        yield dev
    finally:
        dev.close()


# -- no Micro-Manager needed


def test_import_does_not_load_pymmcore():
    code = ("import sys, dino_autofocus.engine.backends.mm_demo_core; "
            "sys.exit('pymmcore_plus' in sys.modules or 'pymmcore' in sys.modules)")
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_zmap_round_trip_and_range():
    zm = ZMap()
    assert zm.bench_range_um == (2700.0, 3300.0)
    assert zm.bench_focus_um == 3000.0
    for bench in (2700.0, 2800.0, 3000.0, 3123.456, 3200.0, 3300.0):
        assert zm.to_bench(zm.to_demo(bench)) == pytest.approx(bench)
    assert zm.to_demo(2800.0) == -200.0
    for bad in (0.0, 2699.9, 3300.1, float("nan"), float("inf")):
        with pytest.raises(DemoZRangeError):
            zm.to_demo(bad)


def test_zmap_custom_offset():
    zm = ZMap(offset_um=2900.0)
    assert zm.bench_range_um == (2600.0, 3200.0)
    assert zm.to_demo(2900.0) == 0.0


def test_readback_compares_as_text():
    assert DemoReadback.of("Objective", "State", 5, "5").verified
    assert not DemoReadback.of("LED", "Label", "550nm", "Closed").verified


# -- demo adapters


def test_open_leaves_everything_dark(demo):
    # the White Light Shutter loads open; open() switches it off and records the readback
    assert all(r.verified for r in demo.opened_with)
    assert demo.light_state() == {"DiaLamp": "0", "Aura": "0", "AuraLine": ""}
    assert demo.core.getAutoShutter() is False


def test_z_in_bench_coordinates(demo):
    assert demo.z_um() == pytest.approx(3000.0)  # demo 0
    assert demo.move_z(2812.5) == pytest.approx(2812.5)
    assert demo.core.getPosition("Z") == pytest.approx(-187.5)
    assert demo.move_z(3300.0) == pytest.approx(3300.0)  # demo +300, the edge


def test_z_out_of_range_refused_without_moving(demo):
    demo.move_z(3050.0)
    for bad in (0.0, 2699.0, 3301.0):
        with pytest.raises(DemoZRangeError):
            demo.move_z(bad)
        assert demo.z_um() == pytest.approx(3050.0)


def test_lamp_on_off_read_back(demo):
    recs = demo.lamp_on()
    assert [r.device for r in recs] == ["LED Shutter", "White Light Shutter"]
    assert all(r.verified for r in recs)
    assert demo.light_state()["DiaLamp"] == "1"
    assert all(r.verified for r in demo.lamp_off())
    assert demo.light_state()["DiaLamp"] == "0"


def test_aura_line_order_and_read_back(demo):
    demo.lamp_on()
    recs = demo.aura_line_on("green", 1.0)
    assert [(r.device, r.prop) for r in recs] == [
        ("White Light Shutter", "open"),
        ("LED", "GREEN_Intensity (emulated)"),
        ("LED", "Label"),
        ("LED Shutter", "open"),
    ]
    assert all(r.verified for r in recs)
    assert recs[1].wanted == "10"  # 1 % -> per-mille 10, as GREEN_Intensity on the bench
    assert recs[2].read == AURA_LINES["GREEN"]
    assert demo.light_state() == {"DiaLamp": "0", "Aura": "1", "AuraLine": "GREEN"}
    assert all(r.verified for r in demo.all_off())
    assert demo.light_state()["Aura"] == "0"


def test_aura_rejects_unknown_line_and_bad_percent(demo):
    with pytest.raises(ValueError, match="unknown Aura line"):
        demo.aura_line_on("ULTRAVIOLET", 1.0)
    with pytest.raises(ValueError, match="0-100"):
        demo.aura_line_on("GREEN", 120.0)
    assert demo.light_state()["Aura"] == "0"


def test_close_switches_off(demo):
    demo.aura_line_on("GREEN", 5.0)
    recs = demo.close()
    assert [r.device for r in recs] == ["LED Shutter", "White Light Shutter"]
    assert all(r.verified and r.read == "0" for r in recs)
    assert demo.close() == []  # the fixture's close after this is a no-op too


def test_camera_shape_and_dtype(demo):
    img = demo.snap()
    assert img.shape == (512, 512) and img.dtype == np.uint16
    demo.set_roi(0)
    assert demo.snap().shape == (2400, 2400)


def test_beads_focus_curve_peaks_at_bench_focus(demo):
    dz = [0.0, 2.0, 5.0, 10.0, 20.0]
    score = {}
    for d in sorted({s * x for x in dz for s in (1, -1)}):
        demo.move_z(demo.zmap.bench_focus_um + d)
        score[d] = vollath4(demo.snap())
    above = [score[d] for d in dz]
    below = [score[-d] for d in dz]
    assert above == sorted(above, reverse=True) and len(set(above)) == len(above)
    assert below == pytest.approx(above)  # symmetric about the focus
    assert score[20.0] < 0.01 * score[0.0]
    demo.move_z(3005.0)
    assert vollath4(demo.snap()) == score[5.0]  # same z, same frame


def test_xy_large_move_ends_in_time(demo):
    t = time.perf_counter()
    x, y = demo.move_xy(50_000.0, -20_000.0)  # 54 mm: 5.4 s at the demo's default 10 mm/s
    assert time.perf_counter() - t < 4.0
    assert (x, y) == (pytest.approx(50_000.0, abs=0.1), pytest.approx(-20_000.0, abs=0.1))


def test_xy_own_deadline(demo):
    demo.core.setProperty("XY", "Velocity", 10.0)
    with pytest.raises(TimeoutError):
        demo.move_xy(20_000.0, 0.0, timeout_s=0.3)  # needs 2 s
    assert not demo.core.deviceBusy("XY")


def test_objective_labels(demo):
    objs = demo.objectives()
    assert len(objs) == 6  # like the Ti2 nosepiece
    assert [o.bench_label for o in objs if o.bench_label] == list(BENCH_OBJECTIVE_LABELS.values())
    rb = demo.set_objective(5)
    assert rb.verified and rb.read == "5"
    now = demo.objective()
    assert now.state == 5 and now.bench_label == "6-Plan Apo LmbdD0.13 100x Oil"
    with pytest.raises(ValueError):
        demo.set_objective(6)


def test_public_set_and_read_goes_through_the_allow_list(demo):
    from dino_autofocus.engine.backend import GUARD_TOKEN, PropertyNotAllowed, UnguardedMotion

    with pytest.raises(UnguardedMotion):
        demo.set_and_read("Z", "Position", 10, token=GUARD_TOKEN)  # motion: never
    with pytest.raises(UnguardedMotion):
        demo.set_and_read("White Light Shutter", "State", 1)  # light: token required
    with pytest.raises(PropertyNotAllowed):
        demo.set_and_read("Dichroic", "State", 1, token=GUARD_TOKEN)
    assert demo.light_state()["DiaLamp"] == "0"
    assert demo.set_and_read("Camera", "Binning", 2).verified
    assert demo.set_and_read("White Light Shutter", "State", 0, token=GUARD_TOKEN).verified
