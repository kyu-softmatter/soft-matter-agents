"""Micro-Manager demo devices in bench terms (T-017).

`ZMap` and the import check run anywhere. The rest loads pymmcore-plus's demo config (simulated
devices, no hardware) and skips when the demo adapters are not installed. Each test gets its
own core, closed afterwards.
"""

import subprocess
import sys

import numpy as np
import pytest

from dino_autofocus.engine.backend import CommandPathRetired
from dino_autofocus.engine.backends.mm_demo_core import (
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


def test_the_demo_core_does_not_open_and_its_writes_are_gone():
    """Card 077: no second Micro-Manager core, and no core-level write left to call."""
    with pytest.raises(CommandPathRetired, match="plan.md 15, bc0f4848"):
        DemoDevices.open()
    gone = ("set_exposure", "set_roi", "move_z", "move_xy", "set_objective", "lamp_on",
            "lamp_off", "aura_line_on", "aura_off", "all_off", "set_and_read",
            "_set_and_read", "_shutter")
    assert not [name for name in gone if hasattr(DemoDevices, name)]
