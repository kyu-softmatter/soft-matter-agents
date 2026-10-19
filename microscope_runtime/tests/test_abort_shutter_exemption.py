"""Card 056 part 2: an abort, and only an abort, closes the two filter-turret shutters.

    python -m unittest microscope_agent/tests/test_abort_shutter_exemption.py

The person allowed it on 2026-10-04 (plan.md 4.6.8 interlock 1, 10561c8):
close only, never open, only from orchestrator.abort, read back on every
close, and every one of them still in NAMED_REFUSALS for any other path. The
closed value, State 0 for both turret shutters, is the person's statement in
this seat's window on 2026-10-04. CSUW1-Shutter is approved too and is NOT
built: no closed value for it is recorded anywhere this seat can read.

Fake MMCore core and mock only. No device is opened.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

TURRETS = ("Turret1Shutter", "Turret2Shutter")
APPROVED = TURRETS + ("CSUW1-Shutter",)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


orch = _load("_orch_shutter_exemption_under_test", SRC / "orchestrator.py")


class _FakeCore:
    """Just enough of CMMCorePlus: set, wait, get. `stuck` pairs read back what they were."""

    def __init__(self, stuck=None):
        self.props = {("Aura", "State"): "1", ("DiaLamp", "State"): "1",
                      ("Turret1Shutter", "State"): "1", ("Turret2Shutter", "State"): "1",
                      ("CSUW1-Shutter", "State"): "Open"}
        self.stuck = dict(stuck or {})
        self.writes = []

    def getLoadedDevices(self):
        return ("Core", "Aura", "DiaLamp", "Turret1Shutter", "Turret2Shutter", "CSUW1-Shutter")

    def setProperty(self, device, prop, value):
        self.writes.append((device, prop, value))
        if (device, prop) not in self.stuck:
            self.props[(device, prop)] = str(value)

    def getProperty(self, device, prop):
        return self.stuck.get((device, prop), self.props[(device, prop)])

    def waitForSystem(self):
        return None


class _Rig:
    """An orchestrator on mock, with the Micro-Manager channels routed to micromanager."""

    def __init__(self, core=None):
        self.o = orch.Orchestrator(backend="mock")
        self.mock = self.o.module_for(next(iter(self.o.channels)))
        self.mock.reset()
        self.core = core or _FakeCore()
        self.mm = self.o._device_module("micromanager", needed_by="test")
        self.mm.reset()
        self.mm._core = lambda: self.mm.GuardedCore(self.core)
        routed = {"confocal_csuw1": self.mm, "widefield_source_a": self.mm, "stand_ti2e": self.mm}
        self.o.module_for = lambda cid: routed.get(cid, self.mock)

    def abort(self):
        try:
            return self.o.abort("test")
        finally:
            self.mm.reset()


def _declared(report):
    return {r["device"]: r for r in report["shutters"] if r.get("device")}


class NoPlanPathReachesTheExemption(unittest.TestCase):
    """Test 1: a plan, an operation plan and a direct apply() are refused; the abort closes."""

    def _command(self, device):
        return orch.Command(channel="stand_ti2e", action="set", from_field="plan.test",
                            params={"settings": {device: {"State": "0"}}})

    # The refusal must name THE SHUTTER. The command also names stand_ti2e,
    # which is refused on its own, so a bare assertRaises passed even with
    # the shutter lifted onto the allow-list -- watched, before this line.
    def _refused_for(self, o, plan, device):
        with self.assertRaises(orch.InterlockError, msg=device) as caught:
            o.check_software_motion_for(plan, [self._command(device)])
        self.assertIn(f"settings {device}.State", str(caught.exception), device)

    def test_a_plan_naming_each_device_is_refused(self):
        o = orch.Orchestrator(backend="mock")
        for device in APPROVED:
            self._refused_for(o, {}, device)

    def test_an_operation_plan_naming_each_device_is_refused(self):
        o = orch.Orchestrator(backend="mock")
        for device in APPROVED:
            plan = {"operation": {"device": device, "moves": [{"id": "m1", "axis": "x"}]}}
            self._refused_for(o, plan, device)

    def test_a_direct_apply_is_refused_and_writes_nothing(self):
        rig = _Rig()
        for device in APPROVED:
            with self.assertRaises(rig.mm.SoftwareMotionRefused, msg=device):
                rig.mm.apply({"settings": {device: {"State": "0"}}})
        self.assertEqual(rig.core.writes, [])

    def test_the_abort_closes_both_turret_shutters(self):
        rig = _Rig()
        rows = _declared(rig.abort())
        for device in TURRETS:
            row = rows[device]
            self.assertEqual((row["commanded"], row["read_back"], row["closed"]), ("0", "0", True),
                             device)
            self.assertEqual(row["channel"], "stand_ti2e")
            self.assertIn((device, "State", "0"), rig.core.writes)
        self.assertFalse([w for w in rig.core.writes if w[0] == "CSUW1-Shutter"])

    def test_close_for_abort_is_called_from_one_place_only(self):
        sites = []
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(fn):
                    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                            and node.func.attr == "close_for_abort"):
                        sites.append((path.name, fn.name))
        self.assertEqual(sorted(set(sites)), [("orchestrator.py", "_close_shutter")])


class AnOpenValueIsRefused(unittest.TestCase):
    """Test 2: the exemption closes and never opens, on the abort path too."""

    def test_each_device_at_an_open_value_is_refused_without_writing(self):
        rig = _Rig()
        for device, value in (("Turret1Shutter", "1"), ("Turret2Shutter", "1"),
                              ("CSUW1-Shutter", "Open")):
            self.assertIsNotNone(rig.mm.abort_close_refusal(device, "State", value), device)
            with self.assertRaises(rig.mm.SoftwareMotionRefused, msg=device):
                rig.mm.close_for_abort(device, "State", value)
        self.assertEqual(rig.core.writes, [])

    def test_another_property_is_refused(self):
        rig = _Rig()
        with self.assertRaises(rig.mm.SoftwareMotionRefused):
            rig.mm.close_for_abort("Turret1Shutter", "Label", "0")
        self.assertEqual(rig.core.writes, [])


class NamedRefusalsStillHold(unittest.TestCase):
    """Test 3."""

    def test_named_refusals_hold_is_empty_and_all_three_are_named(self):
        mm = orch.Orchestrator(backend="mock")._device_module("micromanager", needed_by="test")
        self.assertEqual(mm.named_refusals_hold(), [])
        for device in APPROVED:
            self.assertIn(device, mm.NAMED_REFUSALS)
            self.assertNotIn(device, mm.SOFTWARE_MAY_COMMAND)


class ADisagreeingReadBack(unittest.TestCase):
    """Test 4: closed false, and the abort still reaches the light sources and the fan-out."""

    def test_closed_false_and_the_abort_goes_on(self):
        rig = _Rig(_FakeCore(stuck={("Turret1Shutter", "State"): "1"}))
        report = rig.abort()
        rows = _declared(report)
        t1 = rows["Turret1Shutter"]
        self.assertEqual((t1["commanded"], t1["read_back"], t1["closed"]), ("0", "1", False))
        self.assertIs(rows["Turret2Shutter"]["closed"], True)
        self.assertEqual(len(report["light_sources"]), 5)
        self.assertEqual(sorted(r["channel"] for r in report["channels"]),
                         sorted(rig.o.channels))


if __name__ == "__main__":
    unittest.main()
