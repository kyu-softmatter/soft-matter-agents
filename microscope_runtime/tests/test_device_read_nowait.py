"""Card 076 part E: a device read that refuses rather than waits when its device's lock is held.

    python -m unittest microscope_runtime/tests/test_device_read_nowait.py

The watcher's sampling is `read()` and nothing else, and a read never waits (plan.md 13.4 item 2):
a channel whose read cannot start at once, because a command, a sequence or another read holds its
device, is recorded as not read at that tick and is never given its last value. This is the one
change to devices/, and what that "never waits" stands on. `read()` with no argument is unchanged.
Fake cores and links only; nothing touches an instrument.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
import time
import types
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


types_namespace = types.SimpleNamespace
mock = _load("_dev_mock_nowait", SRC / "devices" / "mock.py")
manual = _load("_dev_manual_nowait", SRC / "devices" / "manual.py")
lunf = _load("_dev_lunf_nowait", SRC / "devices" / "lunf.py")
micromanager = _load("_dev_micromanager_nowait", SRC / "devices" / "micromanager.py")
python_serial = _load("_dev_python_serial_nowait", SRC / "devices" / "python_serial.py")
python_tcp = _load("_dev_python_tcp_nowait", SRC / "devices" / "python_tcp.py")


class _FakeCore:
    def __init__(self):
        self.reads = 0

    def getLoadedDevices(self):
        return ("Core", "ZDrive")

    def getDevicePropertyNames(self, device):
        return ("State",) if device == "ZDrive" else ()

    def getProperty(self, device, prop):
        self.reads += 1
        return "0"


class _FakeLink:
    def __init__(self):
        self.reads = 0

    def read_position(self, channel):
        self.reads += 1
        return 1.5

    def security_level(self):
        return 3


def set_up(mod):
    """Make `mod.read()` work with nothing real behind it."""
    core, link = _FakeCore(), _FakeLink()
    if mod is micromanager:
        mod._core = lambda: mod.GuardedCore(core)
    if mod is python_serial:
        mod._link = lambda: link
    return core, link


LOCKED = (mock, manual, lunf, micromanager, python_serial)


def within(seconds, fn):
    """Run fn on a thread; (True, result or exception) if it finished in time, (False, None) if not.

    A read that waits when it should refuse would otherwise hang the whole suite, so a regression
    shows as a failed assertion and not as a stuck run.
    """
    box = {}

    def run():
        try:
            box["value"] = fn()
        except BaseException as exc:                              # noqa: BLE001 - handed back
            box["value"] = exc
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(seconds)
    return (not thread.is_alive()), box.get("value")


class _Locks(unittest.TestCase):
    def tearDown(self):
        for mod in LOCKED:
            if mod._LOCK.locked():
                mod._LOCK.release()                              # one bad read must not wedge the rest


class T1ABusyDeviceIsRefusedNotWaited(_Locks):
    def test_every_locked_device_refuses_at_once_when_its_lock_is_held(self):
        for mod in LOCKED:
            with self.subTest(device=mod.__name__):
                core, link = set_up(mod)
                with mod._LOCK:
                    finished, outcome = within(1.0, lambda: mod.read(wait=False))
                self.assertTrue(finished, "the read waited for a held lock instead of refusing")
                self.assertIsInstance(outcome, mod.ReadWouldWait)
                caught = types_namespace(exception=outcome)
                self.assertTrue(caught.exception.would_wait)
                self.assertIn("not to wait", str(caught.exception))
                self.assertEqual((core.reads, link.reads), (0, 0), "a refused read still touched the device")

    def test_the_refusal_is_a_runtime_error_so_a_generic_caller_still_catches_it(self):
        for mod in LOCKED:
            self.assertTrue(issubclass(mod.ReadWouldWait, RuntimeError))

    def test_a_free_lock_reads_as_usual_and_leaves_the_lock_free(self):
        for mod in LOCKED:
            with self.subTest(device=mod.__name__):
                set_up(mod)
                out = mod.read(wait=False)
                self.assertIsInstance(out, dict)
                self.assertTrue(mod._LOCK.acquire(blocking=False), "the read kept the lock")
                mod._LOCK.release()

    def test_an_aborted_read_does_not_keep_the_lock_either(self):
        core, _ = set_up(micromanager)
        core.getLoadedDevices = lambda: (_ for _ in ()).throw(RuntimeError("the core went away"))
        with self.assertRaises(RuntimeError):
            micromanager.read(wait=False)
        self.assertTrue(micromanager._LOCK.acquire(blocking=False))
        micromanager._LOCK.release()


class T2TheDefaultReadIsUnchanged(_Locks):
    def test_read_with_no_argument_still_waits_for_a_held_lock(self):
        for mod in (mock, manual, lunf):
            with self.subTest(device=mod.__name__):
                set_up(mod)
                done = threading.Event()
                mod._LOCK.acquire()
                try:
                    thread = threading.Thread(target=lambda: (mod.read(), done.set()), daemon=True)
                    thread.start()
                    self.assertFalse(done.wait(0.2), "a default read did not wait for the lock")
                finally:
                    mod._LOCK.release()
                self.assertTrue(done.wait(2.0), "a default read never finished once the lock was free")

    def test_read_with_wait_true_is_the_same_as_no_argument(self):
        for mod in LOCKED:
            with self.subTest(device=mod.__name__):
                set_up(mod)
                done_a, first = within(2.0, mod.read)
                done_b, second = within(2.0, lambda: mod.read(wait=True))
                self.assertTrue(done_a and done_b, "a plain read did not finish: it kept the lock")
                self.assertEqual(sorted(first), sorted(second))

    def test_the_tweezers_module_has_no_lock_to_wait_on_and_takes_the_argument(self):
        self.assertEqual(sorted(python_tcp.read(wait=False)), sorted(python_tcp.read()))
        self.assertTrue(issubclass(python_tcp.ReadWouldWait, RuntimeError))


class T3AReadHoldsTheLockWhileItReads(_Locks):
    """The bound the card measures: a read in progress can delay a command by one read, no more."""

    def test_a_command_waits_for_a_read_in_progress_and_then_goes(self):
        core, _ = set_up(micromanager)
        inside, release = threading.Event(), threading.Event()
        real = core.getProperty

        def slow(device, prop):
            inside.set()
            release.wait(2.0)
            return real(device, prop)
        core.getProperty = slow
        reader = threading.Thread(target=lambda: micromanager.read(wait=False), daemon=True)
        reader.start()
        self.assertTrue(inside.wait(2.0))
        got = []
        command = threading.Thread(target=lambda: (micromanager._LOCK.acquire(), got.append(1),
                                                   micromanager._LOCK.release()), daemon=True)
        command.start()
        time.sleep(0.15)
        self.assertEqual(got, [], "a command got through while a read was in progress")
        release.set()
        command.join(2.0)
        reader.join(2.0)
        self.assertEqual(got, [1])


if __name__ == "__main__":
    unittest.main()
