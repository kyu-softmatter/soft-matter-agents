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
from test_backends_mm_real import open_on_demo

from dino_autofocus.engine.backend import GUARD_TOKEN, CommandPathRetired
from dino_autofocus.engine.backends import mm_real
from dino_autofocus.engine.backends.mm_real import MmRealBackend
from dino_autofocus.engine.backends.mock import MockBackend

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
def real():
    b = open_on_demo(roi=64)
    try:
        yield b
    finally:
        b.close()


def test_mock_is_unaffected():
    b = MockBackend(seed=1)
    assert b.move_z(3000.0, token=T) == 3000.0
    assert b.set_nosepiece(5, token=T).verified


def test_motion_is_retired_rather_than_locked():
    """Card 077 removed the motion the lock guarded: each motion method now refuses with
    CommandPathRetired, before any core, whatever the lock says. The lock stays LOCKED."""
    b = MmRealBackend("absent.cfg")
    for call in (lambda: b.move_z(2950.0, token=GUARD_TOKEN),
                 lambda: b.move_xy(1.0, 2.0, token=GUARD_TOKEN),
                 lambda: b.move_xy_rel(1.0, 2.0, token=GUARD_TOKEN),
                 lambda: b.set_nosepiece(0, token=GUARD_TOKEN)):
        with pytest.raises(CommandPathRetired):
            call()
    assert mm_real.BENCH_MOTION == "LOCKED" and b.core is None
