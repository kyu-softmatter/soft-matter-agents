"""An abort stops a sequence that is running, on mock and through micromanager.

    python -m unittest microscope_agent/tests/test_sequence_stops_on_abort.py

Found by card 061 before its run: `sequence()` checked `_ABORTED` once, at
the start, and then delivered every frame it was asked for. So an abort --
from a monitor, a refusal, or the stop channel -- turned the light off and
left the camera streaming until n frames had arrived, and on mock a ten-
minute sequence held the run open ten minutes past its own stop. A stop
that waits for the acquisition it is meant to end is not a stop.

Mock and a fake MMCore core only.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
import time
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


orch = _load("_orch_seq_abort_under_test", SRC / "orchestrator.py")


class OnMock(unittest.TestCase):
    def test_an_abort_mid_sequence_ends_it(self):
        o = orch.Orchestrator(backend="mock")
        mock = o.module_for("camera_red")
        mock.reset()
        mock.FRAME_DELAY_S = 0.01
        got = []
        threading.Timer(0.1, lambda: o.abort("test: abort mid-sequence")).start()
        t0 = time.monotonic()
        out = o.acquire_sequence("camera_red", 1000, lambda i, img, md: got.append(i))
        elapsed = time.monotonic() - t0
        self.assertLess(len(got), 1000)
        self.assertLess(elapsed, 2.0)                  # 1000 frames would take 10 s
        self.assertEqual((out["received"], out["aborted"]), (len(got), True))


class _FakeCore:
    """A camera that always has a frame ready, until it is stopped."""

    def __init__(self):
        self.running = False
        self.stopped = 0
        self.count = 0

    def getLoadedDevices(self):
        return ("Core", "Kinetix_red")

    def getCameraDevice(self):
        return "Kinetix_red"

    def getAutoShutter(self):
        return False

    def getExposure(self):
        return 10.0

    def startSequenceAcquisition(self, n, interval, stop_on_overflow):
        self.running = True

    def getRemainingImageCount(self):
        return 1 if self.running else 0

    def popNextImageAndMD(self):
        time.sleep(0.005)
        self.count += 1
        return bytes(16), {"ImageNumber": str(self.count - 1)}

    def isSequenceRunning(self):
        return self.running

    def stopSequenceAcquisition(self):
        self.stopped += 1
        self.running = False

    def isBufferOverflowed(self):
        return False


class ThroughMicroManager(unittest.TestCase):
    def test_an_abort_mid_sequence_stops_the_camera(self):
        o = orch.Orchestrator(backend="mock")
        mock = o.module_for("camera_red")
        mock.reset()
        mm = o._device_module("micromanager", needed_by="test")
        mm.reset()
        self.addCleanup(mm.reset)
        core = _FakeCore()
        mm._core = lambda: mm.GuardedCore(core)
        o.module_for = lambda cid: mm if cid == "camera_red" else mock
        got = []
        threading.Timer(0.1, lambda: o.abort("test: abort mid-sequence")).start()
        out = o.acquire_sequence("camera_red", 5000, lambda i, img, md: got.append(i))
        self.assertLess(len(got), 5000)
        self.assertTrue(out["aborted"])
        self.assertGreaterEqual(core.stopped, 1)
        self.assertFalse(core.running)


if __name__ == "__main__":
    unittest.main()
