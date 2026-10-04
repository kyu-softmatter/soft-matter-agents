"""Card 054: an abort turns off every light source software can turn off, and says which it cannot.

    python -m unittest microscope_agent/tests/test_abort_lights_off.py

Before this card `abort()` closed the shutters it recognised and then told
every channel module to stop, and no step in between lowered any power: the
Aura and the DiaLamp stayed lit behind closed shutters and the record did not
say so. These tests hold the power-down step to the card:

- exactly the five declared sources, each with one row;
- the two commandable lamps written off AND read back, `matched` judged from
  the backend's own read-back and never from the call returning;
- the three sources software may not command claim nothing;
- the step sits after the shutter coverage and before any channel's abort(),
  because a module's abort() makes its apply() refuse;
- one source raising stops nothing.

The last class runs the same step through `micromanager.apply` against a fake
core, so the `settings` shape and the getProperty read are exercised on the
backend the instrument uses. No device is opened anywhere here.
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


orch = _load("_orch_abort_lights_under_test", SRC / "orchestrator.py")

SOURCES = ["Aura III", "DiaLamp", "optical tweezers", "Spectra III (LightEngine)",
           "confocal laser lines"]
NOT_COMMANDABLE = ["optical tweezers", "Spectra III (LightEngine)", "confocal laser lines"]


def _rows(report):
    return {r["source"]: r for r in report["light_sources"]}


def _watch_channel_aborts(o, module):
    """Record an event each time a channel module's abort() runs, so order is in the log."""
    original = module.abort

    def watched():
        o.record(event="test_channel_abort_ran")
        return original()
    module.abort = watched


class AbortTurnsTheLightsOffOnMock(unittest.TestCase):
    def setUp(self):
        self.o = orch.Orchestrator(backend="mock")
        self.mock = self.o.module_for(next(iter(self.o.channels)))
        self.mock.reset()
        _watch_channel_aborts(self.o, self.mock)

    def test_exactly_the_five_declared_sources(self):
        report = self.o.abort("test")
        self.assertIn("light_sources", report)
        self.assertEqual([r["source"] for r in report["light_sources"]], SOURCES)

    def test_dialamp_and_aura_written_off_and_read_back(self):
        rows = _rows(self.o.abort("test"))
        dia = rows["DiaLamp"]
        self.assertEqual((dia["commanded"], dia["read_back"], dia["matched"]), ("0", "0", True))
        self.assertEqual(dia["channel"], "stand_ti2e")
        aura = rows["Aura III"]
        self.assertIs(aura["matched"], True)
        self.assertEqual(aura["channel"], "widefield_source_a")

    def test_sources_software_may_not_command_claim_nothing(self):
        rows = _rows(self.o.abort("test"))
        for source in NOT_COMMANDABLE:
            row = rows[source]
            self.assertIsNone(row["commanded"], source)
            self.assertIsNone(row["read_back"], source)
            self.assertIsNone(row["matched"], source)
            self.assertIn("not software-controllable", row["note"], source)

    def test_power_down_after_shutter_coverage_and_before_any_channel_abort(self):
        self.o.abort("test")
        events = [e["event"] for e in self.o.log]
        self.assertIn("abort_light_sources", events)
        lights = events.index("abort_light_sources")
        self.assertLess(events.index("abort_shutter_coverage"), lights)
        self.assertLess(lights, events.index("test_channel_abort_ran"))

    def test_a_source_that_raises_is_recorded_and_stops_nothing(self):
        original = self.mock.apply

        def apply(params):
            if "Aura" in (params.get("settings") or {}):
                raise RuntimeError("the Aura refused")
            return original(params)
        self.mock.apply = apply
        report = self.o.abort("test")
        rows = _rows(report)
        self.assertIn("the Aura refused", rows["Aura III"]["error"])
        self.assertIsNone(rows["Aura III"]["matched"])
        self.assertIs(rows["DiaLamp"]["matched"], True)
        self.assertEqual(sorted(r["channel"] for r in report["channels"]),
                         sorted(self.o.channels))


class _FakeCore:
    """Just enough of CMMCorePlus for micromanager.apply: set, wait, get."""

    def __init__(self, stuck=None):
        self.props = {("Aura", "State"): "1", ("DiaLamp", "State"): "1"}
        self.stuck = stuck or {}            # (device, prop) -> what it reads whatever was set
        self.writes = []

    def getLoadedDevices(self):
        return ("Core", "Aura", "DiaLamp")

    def setProperty(self, device, prop, value):
        self.writes.append((device, prop, value))
        self.props[(device, prop)] = str(value)

    def getProperty(self, device, prop):
        return self.stuck.get((device, prop), self.props[(device, prop)])

    def waitForSystem(self):
        return None


class AbortTurnsTheLightsOffThroughMicroManager(unittest.TestCase):
    def _run(self, core):
        o = orch.Orchestrator(backend="mock")
        mock = o.module_for(next(iter(o.channels)))
        mock.reset()
        mm = o._device_module("micromanager", needed_by="test")
        mm.reset()
        mm._core = lambda: mm.GuardedCore(core)
        routed = {"widefield_source_a": mm, "stand_ti2e": mm}
        o.module_for = lambda cid: routed.get(cid, mock)
        try:
            return _rows(o.abort("test"))
        finally:
            mm.reset()

    def test_settings_shape_and_verified_read(self):
        core = _FakeCore()
        rows = self._run(core)
        self.assertIn(("Aura", "State", "0"), core.writes)
        self.assertIn(("DiaLamp", "State", "0"), core.writes)
        for source in ("Aura III", "DiaLamp"):
            row = rows[source]
            self.assertEqual((row["commanded"], row["read_back"], row["matched"]), ("0", "0", True),
                             source)

    def test_a_lamp_that_reads_back_on_is_not_matched(self):
        rows = self._run(_FakeCore(stuck={("DiaLamp", "State"): "1"}))
        dia = rows["DiaLamp"]
        self.assertEqual((dia["commanded"], dia["read_back"], dia["matched"]), ("0", "1", False))
        self.assertIs(rows["Aura III"]["matched"], True)


if __name__ == "__main__":
    unittest.main()
