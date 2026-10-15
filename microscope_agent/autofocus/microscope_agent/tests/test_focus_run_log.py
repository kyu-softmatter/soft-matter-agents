# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/tests/test_focus_run_log.py
# body-sha256: 7c347f28e8debcda42a910a9356317df455c2cd293772c031af93ddf1565c5aa
"""The run-log event contract (D-07): a verdict as one soft-matter-agents run-log event.

Pins the "Contract" section of focus_run_log.py's docstring. Kept apart from
test_focus_core.py and test_focus_contract.py so that focus_classical, focus_verdict and
focus_search can be copied with their tests and without focus_run_log.py.
Loaded by path, stdlib + numpy only; runs with `python -m unittest` and under pytest."""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


classical = _load("_mic_focus_classical", SRC / "focus_classical.py")
verdict = _load("_mic_focus_verdict", SRC / "focus_verdict.py")
model = _load("_mic_focus_verdict_model", SRC / "focus_verdict_model.py")
# This repository's camera clip level (bench_values.CEILING_16BIT); the flat modules hold
# no clip level of their own (D-03c).
CEILING = 65535
run_log = _load("_mic_focus_run_log", SRC / "focus_run_log.py")

# This repository's provisional thresholds; the modules hold none of their own (D-02).
RULES = {"min_dynamic_range_adu": 20.0, "min_contrast": 0.05, "min_frames": 3,
         "dropout_tolerance": 0.02, "max_saturated": 0.001}
DOF = {"in_focus_dof": 1.0, "max_sigma_dof": 3.0}
SMA_BRANCHES = ("in_focus", "step_up", "step_down", "no_sample_here", "unsure")


def _frame(sigma_px):
    yy, xx = np.mgrid[0:64, 0:64]
    spot = np.exp(-((yy - 32.0) ** 2 + (xx - 32.0) ** 2) / (2 * sigma_px ** 2))
    return (200 + 3000 * spot * (2.0 / sigma_px) ** 2).astype(np.uint16)


def _sweep(blurs=(6.0, 3.5, 2.0, 3.5, 6.0)):
    z = [100.0 + 2.0 * i for i in range(len(blurs))]
    stats = [classical.frame_stats(_frame(s), "vollath4", ceiling=CEILING) for s in blurs]
    return z, stats


class Reading:
    """What the live module's ``FocusReading`` provides, with model numbers."""

    def __init__(self, score, sigma, tiles=(0, 1, 2), n_used=3, sign_known=True):
        self.score, self.sigma, self.n_used = score, sigma, n_used
        self.tiles, self.sign_known = list(tiles), sign_known


class RunLogModule(unittest.TestCase):
    def test_one_module_object_per_file(self):
        self.assertIs(run_log.FocusVerdict, verdict.FocusVerdict)

    def test_event_is_json_and_has_no_e6(self):
        z, stats = _sweep()
        ev = run_log.to_run_log_event(verdict.from_sweep(z, stats, **RULES), 1.5)
        self.assertNotIn("E6", json.dumps(ev, allow_nan=False))
        self.assertEqual(ev["event"], "focus_verdict")
        self.assertEqual(ev["z"]["grade"], "E1")


class RunLogEvent(unittest.TestCase):
    def test_event_has_exactly_the_contract_keys_and_no_command_fields(self):
        z, stats = _sweep()
        ev = run_log.to_run_log_event(verdict.from_sweep(z, stats, **RULES), 12.5)
        self.assertEqual(tuple(ev), run_log.EVENT_KEYS)
        self.assertFalse(set(run_log.COMMAND_KEYS) & set(ev))
        self.assertEqual(json.loads(json.dumps(ev, allow_nan=False)), ev)
        self.assertEqual((ev["event"], ev["time_base"], ev["t_mono"]),
                         (run_log.EVENT, "software", 12.5))
        self.assertIn(ev["choice"], SMA_BRANCHES)
        self.assertEqual(set(ev["z"]), {"value", "unit", "grade", "read_from"})
        self.assertEqual((ev["z"]["unit"], ev["z"]["grade"], ev["z"]["read_from"]),
                         ("um", "E1", "z_drive"))
        self.assertEqual(ev["z"]["value"], z[ev["frame_index"]])
        for e in ev["evidence"]:
            self.assertIn(e["grade"], ("E1", "E4"))
            self.assertTrue({"name", "value"} <= set(e) <= {"name", "value", "unit", "grade"})
        self.assertEqual(ev["signals"], [])

    def test_model_numbers_become_signals_without_a_grade_and_no_e6_anywhere(self):
        ev = run_log.to_run_log_event(
            model.from_reading(Reading(2.5, 0.5), 3010.0, 7, **DOF), 3.0, time_base="device")
        self.assertEqual(ev["time_base"], "device")
        self.assertEqual({s["name"] for s in ev["signals"]}, {"dz", "sigma", "n_used"})
        for s in ev["signals"]:
            self.assertNotIn("grade", s)
        self.assertNotIn("E6", json.dumps(ev))
        self.assertEqual(ev["z"]["value"], 3010.0)

    def test_refused_inputs(self):
        z, stats = _sweep()
        v = verdict.from_sweep(z, stats, **RULES)
        with self.assertRaises(ValueError):
            run_log.to_run_log_event(v, float("nan"))
        with self.assertRaises(ValueError):
            run_log.to_run_log_event(v, 1.0, time_base="wall")

    def test_non_finite_evidence_becomes_none(self):
        v = model.from_reading(Reading(float("nan"), 0.5), None, None, **DOF)
        ev = run_log.to_run_log_event(v, 0.0)
        self.assertIsNone(ev["z"])
        dz = next(s for s in ev["signals"] if s["name"] == "dz")
        self.assertIsNone(dz["value"])
        json.dumps(ev, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
