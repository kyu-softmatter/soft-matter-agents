"""Engine contract: light imports, JSON-safe commands/events, the FakeBackend protocol."""

import json
import queue
import subprocess
import sys

import pytest

from dino_autofocus.engine import Command, Event, queue_sink
from dino_autofocus.engine.backend import GUARD_TOKEN, Backend, UnguardedMotion


def test_import_pulls_no_ui_torch_or_pymmcore():
    code = ("import sys, pkgutil, importlib, dino_autofocus.engine as e; "
            "[importlib.import_module('dino_autofocus.engine.' + m.name) "
            " for m in pkgutil.iter_modules(e.__path__) if not m.ispkg]; "
            "bad = {'torch', 'pymmcore', 'pymmcore_plus', 'tkinter', 'PySide6', 'PyQt5'}"
            " & set(sys.modules); assert not bad, bad")
    subprocess.run([sys.executable, "-c", code], check=True)


def test_commands_and_events_round_trip_through_json():
    ev = Event("progress", "scan_4x_1", {"tile": "r0c1", "z_um": [3052.9]})
    assert Event.from_json(ev.to_json()) == ev
    cmd = Command("confirm", op_id="scan_4x_1", args={"key": "oil_loaded", "ok": True},
                  origin="assistant", user_id="operator@example.test",
                  session_id="20261001_1540_1")
    assert Command.from_json(cmd.to_json()) == cmd
    assert json.loads(Command("abort").to_json())["user_id"] is None
    with pytest.raises(ValueError):
        Event("explode")
    with pytest.raises(ValueError):
        Command("start", origin="robot")
    q = queue.Queue()
    queue_sink(q)(ev)
    assert q.get_nowait() is ev


def test_fake_backend_meets_the_protocol_and_refuses_unguarded_motion(fake):
    assert isinstance(fake, Backend)
    json.dumps(fake.info().to_dict())
    assert fake.info().ceiling_adu == 4095
    with pytest.raises(UnguardedMotion):
        fake.move_z(3000.0, token=None)
    assert all(r.verified for r in fake.aura_line_on("GREEN", 1, token=GUARD_TOKEN))
    assert fake.props[("Aura", "GREEN_Intensity")] == "10"  # per-mille
