"""Card 049 at c544e1f: software may set DiaLamp's State and Intensity, and nothing else of it.

    python -m unittest microscope_agent/tests/test_dialamp_allowlist.py

The allow-list gained one device with two properties. What matters as much as
the grant is its edge: every other DiaLamp property, and every other stand
device, is still refused, and the calls that move things stay refused on
DiaLamp too.

Watched failing: with `"DiaLamp": None` (every property) the edge test fails;
with the DiaLamp line removed the grant test fails.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

DEVICES = Path(__file__).resolve().parents[1] / "src" / "devices"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mm = _load("_mm_dialamp_under_test", DEVICES / "micromanager.py")

STAND = ("ZDrive", "Nosepiece", "XYStage", "PFS", "PFSOffset", "IntermediateMagnification",
         "FilterTurret1", "FilterTurret2", "LightPath", "CondenserTurret", "LappMainBranch1",
         "Turret1Shutter", "Turret2Shutter", "Ti2-E__0")


class DiaLampAllowList(unittest.TestCase):
    def test_state_and_intensity_are_allowed(self):
        self.assertIsNone(mm.refusal("DiaLamp", "State", "setProperty", 1))
        self.assertIsNone(mm.refusal("DiaLamp", "Intensity", "setProperty", 2100))

    def test_every_other_dialamp_property_is_refused(self):
        for prop in ("Label", "ComputerControl", "Description", "Name"):
            self.assertIsNotNone(mm.refusal("DiaLamp", prop, "setProperty", 1), prop)

    def test_moving_calls_stay_refused_on_dialamp(self):
        for call in ("setState", "setStateLabel", "setConfig", "setShutterOpen"):
            self.assertIsNotNone(mm.refusal("DiaLamp", "State", call, 1), call)

    def test_every_other_stand_device_is_still_refused(self):
        for device in STAND:
            self.assertIsNotNone(mm.refusal(device, "State", "setProperty", 1), device)

    def test_named_refusals_still_hold(self):
        self.assertEqual(mm.named_refusals_hold(), [])


if __name__ == "__main__":
    unittest.main()
