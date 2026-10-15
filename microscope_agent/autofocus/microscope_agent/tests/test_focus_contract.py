# origin: soft-matter-agents, the original since 2026-10-05; dino-autofocus mirrors it:
#   https://github.com/kyu-softmatter/soft-matter-agents/blob/f2c56dcfc018b23ff784dc2ac06e150db499f556/microscope_agent/tests/test_focus_contract.py
# body-sha256: d863c62cee1f1894ee92a7e395ac53408bd7e0aeae4902a861f48b9b5407c3d4
"""The verdict contract (D-07): what goes in, what comes out, in JSON.

Pins the "Contract" section of focus_verdict.py's docstring so a change to the shape is a
failing test here before it is a surprise in soft-matter-agents. The run-log event's contract
is pinned in test_focus_run_log.py, so this file needs no focus_run_log.py.
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
# This repository's camera clip level (bench_values.CEILING_16BIT); the flat modules hold
# no clip level of their own (D-03c).
CEILING = 65535

# This repository's provisional thresholds; the modules hold none of their own (D-02).
RULES = {"min_dynamic_range_adu": 20.0, "min_contrast": 0.05, "min_frames": 3,
         "dropout_tolerance": 0.02, "max_saturated": 0.001}
SMA_BRANCHES = ("in_focus", "step_up", "step_down", "no_sample_here", "unsure")


def _frame(sigma_px):
    yy, xx = np.mgrid[0:64, 0:64]
    spot = np.exp(-((yy - 32.0) ** 2 + (xx - 32.0) ** 2) / (2 * sigma_px ** 2))
    return (200 + 3000 * spot * (2.0 / sigma_px) ** 2).astype(np.uint16)


def _sweep(blurs=(6.0, 3.5, 2.0, 3.5, 6.0)):
    z = [100.0 + 2.0 * i for i in range(len(blurs))]
    stats = [classical.frame_stats(_frame(s), "vollath4", ceiling=CEILING) for s in blurs]
    return z, stats


class Vocabulary(unittest.TestCase):
    def test_the_vocabulary_is_the_soft_matter_agents_focus_branches(self):
        self.assertEqual(verdict.VERDICTS, SMA_BRANCHES)
        self.assertEqual(verdict.SOURCES, ("sweep",))
        self.assertEqual(verdict.GRADES, ("measured", "computed"))  # origin kinds, not grades


class SweepRecord(unittest.TestCase):
    def test_record_has_exactly_the_contract_keys_and_is_json(self):
        z, stats = _sweep()
        rec = verdict.from_sweep(z, stats, **RULES).as_record()
        self.assertEqual(tuple(rec), verdict.RECORD_KEYS)
        self.assertEqual(json.loads(json.dumps(rec, allow_nan=False)), rec)
        self.assertIn(rec["verdict"], verdict.VERDICTS)
        self.assertEqual(rec["source"], "sweep")
        self.assertTrue(rec["reason"])
        for e in rec["evidence"]:
            self.assertEqual(set(e), {"name", "value", "grade", "unit"})
            self.assertIn(e["grade"], verdict.GRADES)

    def test_z_is_the_readback_of_the_frame_the_verdict_points_at(self):
        z, stats = _sweep()
        v = verdict.from_sweep(z, stats, **RULES)
        self.assertEqual(v.verdict, verdict.Verdict.IN_FOCUS)
        self.assertIsNotNone(v.frame_index)
        self.assertEqual(v.z_um, z[v.frame_index])
        self.assertEqual(v.as_record()["z_grade"], "measured")

    def test_a_refusing_verdict_carries_no_z_and_no_frame(self):
        z, stats = _sweep()
        dark = [classical.frame_stats(np.full((64, 64), 100, np.uint16), "vollath4",
                                       ceiling=CEILING)
                for _ in z]
        v = verdict.from_sweep(z, dark, **RULES)
        self.assertEqual(v.verdict, verdict.Verdict.NO_SAMPLE_HERE)
        rec = v.as_record()
        self.assertIsNone(rec["z_um"])
        self.assertIsNone(rec["frame_index"])
        self.assertIsNone(rec["z_grade"])

    def test_thresholds_are_required_and_lengths_must_match(self):
        z, stats = _sweep()
        with self.assertRaises(TypeError):
            verdict.from_sweep(z, stats)  # no defaults: the caller names every threshold
        with self.assertRaises(ValueError):
            verdict.from_sweep(z[:-1], stats, **RULES)


if __name__ == "__main__":
    unittest.main()
