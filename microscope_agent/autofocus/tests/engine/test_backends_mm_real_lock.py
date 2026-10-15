"""SAFETY (T-036): bench motion on mm-real ships locked.

- The constant is "LOCKED" and nothing in src/ or scripts/ reads or writes it except the one
  definition and the one read in mm_real (so no argument, environment variable or setting
  can lift it).
- Every motion method refuses on mm-real, with or without the guard token, before touching
  the core; so do the guards' paths that reach them. Reads, frames, streams, light on/off
  and PFS off still work.
- mock and mm-demo are unaffected.

Demo-config cases skip without the Micro-Manager demo adapters.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from test_backends_mm_real import StubCore, open_on_demo

from dino_autofocus.engine.backend import GUARD_TOKEN, PfsState
from dino_autofocus.engine.backends import mm_real
from dino_autofocus.engine.backends.mm_real import BenchMotionLocked, MmRealBackend
from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.guards import FocusAxis, GuardError, XYAxis, XYBox, rotate_nosepiece

T = GUARD_TOKEN
ROOT = Path(__file__).resolve().parents[2]
REASON = "bench motion locked until clearance guards land (T-027, T-011)"
MOTION = {
    "move_z": lambda b: b.move_z(10.0, token=T),
    "move_xy": lambda b: b.move_xy(10.0, 10.0, token=T),
    "move_xy_rel": lambda b: b.move_xy_rel(10.0, 0.0, token=T),
    "set_nosepiece": lambda b: b.set_nosepiece(1, token=T),
}


def test_ships_locked():
    assert mm_real.BENCH_MOTION == "LOCKED"
    assert mm_real.MOTION_LOCK_REASON == REASON


def test_the_constant_is_read_nowhere_else():
    hits = [p for d in ("src", "scripts") for p in (ROOT / d).rglob("*.py")
            if "BENCH_MOTION" in p.read_text(encoding="utf-8") and p.name != "mm_real.py"]
    assert hits == []
    tree = ast.parse((ROOT / "src/dino_autofocus/engine/backends/mm_real.py")
                     .read_text(encoding="utf-8"))
    stores = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "BENCH_MOTION"
              and isinstance(n.ctx, ast.Store)]
    assert len(stores) == 1 and stores[0].col_offset == 0  # the one module-level definition
    readers = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
               for n in ast.walk(f) if isinstance(n, ast.Name) and n.id == "BENCH_MOTION"}
    assert readers == {"_motion_state"}
    assert not any(isinstance(n, ast.Global) for n in ast.walk(tree))
    src = ast.get_source_segment((ROOT / "src/dino_autofocus/engine/backends/mm_real.py")
                                 .read_text(encoding="utf-8"),
                                 next(f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
                                      and f.name == "_motion_state"))
    assert "environ" not in src and "getenv" not in src and "settings" not in src


@pytest.fixture
def stub(tmp_path):
    b = MmRealBackend(tmp_path / "bench.cfg")
    b.core = StubCore()
    yield b
    b.core = None


@pytest.mark.parametrize("name", sorted(MOTION))
def test_every_motion_method_refuses_before_the_core(stub, name):
    with pytest.raises(BenchMotionLocked, match=r"T-027, T-011"):
        MOTION[name](stub)
    assert stub.core.writes == []  # the stub has no motion calls: reaching the core would fail


@pytest.fixture
def real():
    b = open_on_demo(roi=64)
    try:
        yield b
    finally:
        b.close()


@pytest.mark.parametrize("name", sorted(MOTION))
def test_every_motion_method_refuses_on_the_demo_config(real, name):
    before = (real.positions().x_um, real.positions().y_um, real.positions().z_um,
              real.nosepiece())
    with pytest.raises(BenchMotionLocked):
        MOTION[name](real)
    after = (real.positions().x_um, real.positions().y_um, real.positions().z_um,
             real.nosepiece())
    assert after == before


def test_guard_paths_reach_the_lock(real):
    # the demo has no PFS; read it as off and out of range so rotate_nosepiece reaches the
    # nosepiece call (the bench PFS would answer that after a retract)
    real.pfs = lambda: PfsState(False, False, "Out of Range")
    z = real.positions().z_um
    axis = FocusAxis(real, "4x", allow_motion=True, sleep=lambda s: None,
                     window=(z - 50.0, z + 50.0))
    # upward paths: the T-029d bench-approach refusal in guards stops them first (an earlier,
    # independent layer); the down move and the nosepiece turn reach the T-036 lock
    for call in (lambda: axis.move_to(z + 1.0, allow_ascent_um=2.0),
                 lambda: axis.sweep(axis.plan(z + 10.0, 5.0, 5.0), real.snap),
                 lambda: axis.approach(z + 20.0, clearance=lambda read: True)):
        with pytest.raises((GuardError, BenchMotionLocked), match="T-029d|T-027, T-011"):
            call()
    for call in (lambda: axis.park_at(z),
                 lambda: rotate_nosepiece(real, axis, 1)):
        with pytest.raises(BenchMotionLocked):
            call()
    x, y = real.positions().x_um, real.positions().y_um
    xy = XYAxis(real, XYBox.around((x, y), 5000.0), allow_motion=True)
    for call in (lambda: xy.goto(x + 10.0, y), lambda: xy.goto_rel(10.0, 0.0)):
        with pytest.raises(BenchMotionLocked):
            call()
    assert real.positions().z_um == z and real.positions().x_um == x


def test_reads_frames_streams_lights_and_pfs_off_still_work(real):
    real.positions()
    real.describe_devices(include_properties=False)
    real.config_record()
    assert real.snap().image.ndim == 2
    real.start_stream()
    try:
        assert real.next_frame(timeout_s=5.0) is not None
    finally:
        real.stop_stream()
    assert real.lamp_on(token=T)[-1].read == "1"
    assert all(r.verified for r in real.all_off())
    assert real.pfs_off(token=T).read == "Off"
    assert real.info().notes["bench_motion"] == f"LOCKED: {REASON}"


def test_mock_is_unaffected():
    b = MockBackend(seed=1)
    assert b.move_z(3000.0, token=T) == 3000.0
    assert b.set_nosepiece(5, token=T).verified


def test_mm_demo_is_unaffected():
    from dino_autofocus.engine.backends.mm_demo import MmDemoBackend
    from dino_autofocus.engine.backends.mm_demo_core import DemoUnavailable

    b = MmDemoBackend(roi=64)
    try:
        b.open()
    except DemoUnavailable as e:
        pytest.skip(f"Micro-Manager demo adapters not available: {e}")
    try:
        assert b.move_z(3010.0, token=T) == pytest.approx(3010.0, abs=0.01)
        assert b.move_xy_rel(5.0, 0.0, token=T)
    finally:
        b.close()
