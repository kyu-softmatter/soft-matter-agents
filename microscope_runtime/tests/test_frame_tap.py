"""Card 058: a frame tap that commands nothing.

    python -m unittest microscope_agent/tests/test_frame_tap.py

The tap keeps a copy of the latest frame a run's own acquisition produced and
serves it on a loopback socket. It calls nothing on the core, never snaps to
have something to show, and a slow reader never slows the run. Mock and a
fake MMCore core only; frames here are small byte strings, not sensor frames.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
import tempfile
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


orch = _load("_orch_frame_tap_under_test", SRC / "orchestrator.py")

REQUEST = b'{"get": "latest_frame"}\n'


def _ask(addr, payload=REQUEST, timeout=5):
    """One request; returns (header dict or None, body bytes)."""
    data = b""
    try:
        with socket.create_connection((addr["host"], addr["port"]), timeout=timeout) as s:
            s.sendall(payload)
            s.shutdown(socket.SHUT_WR)
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
    except ConnectionResetError:
        pass
    if not data:
        return None, b""
    head, _, body = data.partition(b"\n")
    return json.loads(head), body


class _Rig:
    def __init__(self, test):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        self.o = orch.Orchestrator(backend="mock")
        self.mock = self.o.module_for("camera_red")
        self.mock.reset()
        self.addrs = self.o.begin_run(Path(self.tmp.name) / "run-tap", run_id="run-tap",
                                      plan_id="p", revision=1)
        test.addCleanup(self.end)

    @property
    def tap(self):
        return self.o.frame_tap_address()

    def end(self):
        if self.o.stop_channel_address() is not None:
            self.o.end_run("completed")


class T1LatestEqualsTheSinksLast(unittest.TestCase):
    def test_after_a_mock_sequence(self):
        rig = _Rig(self)
        got = []
        rig.o.acquire_sequence("camera_red", 7, lambda i, img, md: got.append((img, dict(md))))
        head, body = _ask(rig.tap)
        self.assertEqual(len(got), 7)
        self.assertTrue(head["frame"])
        self.assertEqual(body, bytes(got[-1][0]))
        self.assertEqual(head["metadata"]["ImageNumber"], got[-1][1]["ImageNumber"])

    def test_a_snap_fills_it_too(self):
        rig = _Rig(self)
        image, meta = rig.o.acquire_snap("camera_red")
        head, body = _ask(rig.tap)
        self.assertEqual(body, bytes(image))


class _FakeCore:
    """Deterministic: a frame is always ready, so the call list depends on nothing but n."""

    def __init__(self, n):
        self.calls = []
        self.left = 0
        self.n = n
        self.count = 0

    def _log(self, name, *args):
        self.calls.append((name,) + args)

    def getLoadedDevices(self):
        return ("Core", "Kinetix_red")

    def getCameraDevice(self):
        self._log("getCameraDevice")
        return "Kinetix_red"

    def getAutoShutter(self):
        self._log("getAutoShutter")
        return False

    def getExposure(self):
        self._log("getExposure")
        return 10.0

    def startSequenceAcquisition(self, n, interval, stop_on_overflow):
        self._log("startSequenceAcquisition", n)
        self.left = n

    def getRemainingImageCount(self):
        self._log("getRemainingImageCount")
        return self.left

    def popNextImageAndMD(self):
        self._log("popNextImageAndMD")
        self.left -= 1
        self.count += 1
        return bytes([self.count]) * 16, {"ImageNumber": str(self.count - 1)}

    def isSequenceRunning(self):
        self._log("isSequenceRunning")
        return False

    def stopSequenceAcquisition(self):
        self._log("stopSequenceAcquisition")

    def isBufferOverflowed(self):
        self._log("isBufferOverflowed")
        return False


class T2TheTapCallsNothing(unittest.TestCase):
    def _sequence(self, polling):
        rig = _Rig(self)
        core = _FakeCore(30)
        mm = rig.o._device_module("micromanager", needed_by="test")
        mm.reset()
        mm._core = lambda: mm.GuardedCore(core)
        rig.o.module_for = lambda cid: mm if cid == "camera_red" else rig.mock
        stop = threading.Event()
        replies = []

        def poll():
            while not stop.is_set():
                replies.append(_ask(rig.tap)[0])
        reader = threading.Thread(target=poll) if polling else None
        if reader:
            reader.start()
        rig.o.acquire_sequence("camera_red", 30, lambda i, img, md: time.sleep(0.002))
        stop.set()
        if reader:
            reader.join(5)
        return core.calls, replies

    def test_identical_core_calls_with_and_without_a_reader(self):
        quiet, _ = self._sequence(polling=False)
        busy, replies = self._sequence(polling=True)
        self.assertEqual(quiet, busy)
        self.assertGreater(len(replies), 0)


class T3ABlockedReaderDoesNotSlowTheRun(unittest.TestCase):
    TOLERANCE = 0.25          # the sequence may take at most 25 % longer with a blocked reader

    def _timed(self, block):
        rig = _Rig(self)
        rig.mock.FRAME_DELAY_S = 0.01
        rig.mock.FRAME_BYTES = 8_000_000       # far more than a socket buffer holds
        held = []
        got = []

        def sink(i, img, md):
            got.append(i)
            if block and i == 3:
                # Mid-sequence, with a frame in the tap: one asks and never reads,
                # so serving it fills the socket and the server's send blocks.
                s = socket.create_connection((rig.tap["host"], rig.tap["port"]))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
                s.sendall(REQUEST)
                held.append(s)
            if block and i == 4:
                # And one connects and never sends. Opened after the stuck reader:
                # the tap serves one connection at a time, so opened first it would
                # hold the server in its read timeout past the end of the sequence
                # and the stuck reader would never be served at all.
                held.append(socket.create_connection((rig.tap["host"], rig.tap["port"])))
        t0 = time.monotonic()
        rig.o.acquire_sequence("camera_red", 40, sink)
        elapsed = time.monotonic() - t0
        for s in held:
            s.close()
        return elapsed, got

    def test_duration_within_tolerance_and_every_frame_reaches_the_sink(self):
        free, got_free = self._timed(block=False)
        blocked, got_blocked = self._timed(block=True)
        print(f"\n  sequence of 40: {free * 1000:.0f} ms free, {blocked * 1000:.0f} ms with a "
              f"blocked reader (tolerance {self.TOLERANCE:.0%})")
        self.assertEqual(got_blocked, list(range(40)))
        self.assertEqual(got_free, list(range(40)))
        self.assertLess(blocked, free * (1 + self.TOLERANCE) + 0.02)


class T4NoFrameYetAndClosedAfter(unittest.TestCase):
    def test_no_frame_yet_then_closed_after_the_run(self):
        rig = _Rig(self)
        head, body = _ask(rig.tap)
        self.assertEqual((head["frame"], body), (False, b""))
        self.assertIn("no frame yet", head["note"])
        addr = rig.tap
        rig.o.end_run("completed")
        self.assertIsNone(rig.o.frame_tap_address())
        with self.assertRaises(OSError):
            socket.create_connection((addr["host"], addr["port"]), timeout=1).close()


class T5AnyOtherRequestIsRefused(unittest.TestCase):
    def test_refused_and_nothing_changes(self):
        rig = _Rig(self)
        rig.o.acquire_sequence("camera_red", 3, lambda i, img, md: None)
        before = _ask(rig.tap)
        for payload in (b'{"get": "latest_frame", "exposure_ms": 5}\n', b'{"snap": true}\n',
                        b'{"get": "stream"}\n', b"latest\n", b'{"get": "latest_frame"}\n{}\n',
                        b"x" * 5000 + b"\n"):
            self.assertEqual(_ask(rig.tap, payload), (None, b""), payload[:40])
        self.assertEqual(_ask(rig.tap), before)
        names = [e["event"] for e in rig.o.log]
        self.assertEqual(names.count("frame_tap_refused"), 6)
        self.assertEqual(names.count("test_never"), 0)


class T6Loopback(unittest.TestCase):
    def test_bound_to_127_0_0_1_and_announced_in_run_started(self):
        rig = _Rig(self)
        self.assertEqual(rig.tap["host"], "127.0.0.1")
        first = json.loads((Path(rig.tmp.name) / "run-tap" / "events.jsonl")
                           .read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(first["frame_tap"], rig.tap)
        self.assertNotEqual(first["frame_tap"]["port"], first["stop_channel"]["port"])


if __name__ == "__main__":
    unittest.main()
