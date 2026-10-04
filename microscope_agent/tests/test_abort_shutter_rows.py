"""Card 056 part 1: an abort's shutter rows say what happened, never `closed: true` unread.

    python -m unittest microscope_agent/tests/test_abort_shutter_rows.py

Before this card the shutter loop sent every recognised shutter
`{"element": e, "state": "closed"}` and wrote `closed: True` because the call
returned. Through micromanager that call writes nothing (`_settings()` reads
only `settings`), so the spinning-disk shutter's row claimed closed with
nothing sent; through lunf it raised, and the laser lines were never blanked.

These tests run on mock, on a fake MMCore core, and on lunf's MockTransport.
No device is opened. The lunf wiring below is SYNTHETIC -- line ids and
levels are made up and are not this instrument's.
"""

from __future__ import annotations

import importlib.util
import sys
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


orch = _load("_orch_shutter_rows_under_test", SRC / "orchestrator.py")

LUNF_ROW = {"id": "laser_combiner", "automatable": "partial", "read_back": False,
            "elements": [{"id": "laser_shutter"},
                         {"id": "line_select", "lines": {"a": "dl0", "b": "dl1"},
                          "open_level": "OPEN", "closed_level": "SHUT"}]}


class _FakeCore:
    """Just enough of CMMCorePlus for micromanager.apply: set, wait, get."""

    def __init__(self):
        self.props = {("Aura", "State"): "1", ("DiaLamp", "State"): "1"}
        self.writes = []

    def getLoadedDevices(self):
        return ("Core", "Aura", "DiaLamp", "CSUW1-Shutter")

    def setProperty(self, device, prop, value):
        self.writes.append((device, prop, value))
        self.props[(device, prop)] = str(value)

    def getProperty(self, device, prop):
        return self.props[(device, prop)]

    def waitForSystem(self):
        return None


def _shutters(report):
    return {r["element"]: r for r in report["shutters"] if r["identified"]}


class _Rig:
    """An orchestrator on mock, with chosen channels routed to real backend modules."""

    def __init__(self, lunf_row=LUNF_ROW, transport=None):
        self.o = orch.Orchestrator(backend="mock")
        self.mock = self.o.module_for(next(iter(self.o.channels)))
        self.mock.reset()
        self.core = _FakeCore()
        self.mm = self.o._device_module("micromanager", needed_by="test")
        self.mm.reset()
        self.mm._core = lambda: self.mm.GuardedCore(self.core)
        self.lunf = self.o._device_module("lunf", needed_by="test")
        self.lunf.reset()
        self.transport = transport if transport is not None else self.lunf.MockTransport()
        self.lunf.use_transport(self.transport)
        self.lunf.preflight(lunf_row)
        routed = {"confocal_csuw1": self.mm, "widefield_source_a": self.mm,
                  "stand_ti2e": self.mm, "laser_combiner": self.lunf}
        self.o.module_for = lambda cid: routed.get(cid, self.mock)

    def abort(self):
        try:
            return self.o.abort("test")
        finally:
            self.mm.reset()


class SpinningDiskShutterThroughMicroManager(unittest.TestCase):
    def test_csuw1_is_not_claimed_closed(self):
        rig = _Rig()
        row = _shutters(rig.abort())["csuw1_shutter"]
        self.assertIsNot(row["closed"], True, row)
        self.assertIsNone(row["closed"])
        self.assertIsNone(row["commanded"])
        self.assertIn("not commanded", row["note"])
        self.assertFalse([w for w in rig.core.writes if w[0] == "CSUW1-Shutter"])


class LaserShutterThroughLunf(unittest.TestCase):
    def test_close_all_is_sent_and_not_confirmed(self):
        rig = _Rig()
        row = _shutters(rig.abort())["laser_shutter"]
        self.assertEqual(row["commanded"], {"enable": []})
        self.assertIsNone(row["closed"])
        self.assertIsNone(row["read_back"])
        self.assertIn("not confirmed", row["note"])
        self.assertIn(("dl0", "SHUT"), rig.transport.writes)
        self.assertIn(("dl1", "SHUT"), rig.transport.writes)

    def test_a_transport_that_raises_is_recorded_and_stops_nothing(self):
        rig = _Rig(transport=None)
        rig.lunf.use_transport(rig.lunf.MockTransport(fail_on={"dl0"}))
        report = rig.abort()
        row = _shutters(report)["laser_shutter"]
        self.assertIn("dl0", row["error"])
        self.assertIsNone(row["closed"])
        self.assertIn("light_sources", report)
        self.assertEqual(sorted(r["channel"] for r in report["channels"]),
                         sorted(rig.o.channels))

    def test_a_refusal_over_missing_wiring_is_recorded(self):
        rig = _Rig(lunf_row={"id": "laser_combiner", "elements": [{"id": "laser_shutter"},
                                                                  {"id": "line_select"}]})
        row = _shutters(rig.abort())["laser_shutter"]
        self.assertIn("line_select", row["error"])
        self.assertIsNone(row["closed"])


class NoShutterRowIsTrueUnread(unittest.TestCase):
    def test_on_mock(self):
        o = orch.Orchestrator(backend="mock")
        o.module_for(next(iter(o.channels))).reset()
        for row in o.abort("test")["shutters"]:
            self.assertIsNot(row["closed"], True, row)

    def test_through_the_real_backends(self):
        for row in _Rig().abort()["shutters"]:
            self.assertIsNot(row["closed"], True, row)
            for key in ("commanded", "read_back", "closed"):
                self.assertIn(key, row, row)


if __name__ == "__main__":
    unittest.main()
