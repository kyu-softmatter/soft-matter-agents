# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/tests/test_focus_verdict_model.py
# body-sha256: d3005378309b408bc27a9ba9a2c851b25fb136ce3f8b4eb89745283bd1968faa
"""focus_verdict_model.py, the model-reading verdict: loaded by path, stdlib only.

Kept apart from test_focus_contract.py so that the classical verdict and its tests can be
copied without this file (D-03c). Runs with `python -m unittest` and under pytest."""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


verdict = _load("_mic_focus_verdict", SRC / "focus_verdict.py")
model = _load("_mic_focus_verdict_model", SRC / "focus_verdict_model.py")

# This repository's provisional DoF thresholds; the module holds none of its own.
DOF = {"in_focus_dof": 1.0, "max_sigma_dof": 3.0}


class Reading:
    """What the live module's ``FocusReading`` provides, with model numbers."""

    def __init__(self, score, sigma, tiles=(0, 1, 2), n_used=3, sign_known=True):
        self.score, self.sigma, self.n_used = score, sigma, n_used
        self.tiles, self.sign_known = list(tiles), sign_known


class ReadingRecord(unittest.TestCase):
    def test_model_numbers_are_evidence_graded_model_and_z_stays_the_readback(self):
        v = model.from_reading(Reading(score=2.5, sigma=0.5), 3010.0, 7, **DOF)
        self.assertEqual(v.verdict, verdict.Verdict.STEP_DOWN)
        self.assertEqual((v.source, v.frame_index, v.z_um), ("dino", 7, 3010.0))
        self.assertTrue(model.has_model_numbers(v))
        self.assertEqual((model.SOURCE, model.MODEL), ("dino", "model"))
        grades = {e.name: e.grade for e in v.evidence}
        self.assertEqual((grades["dz"], grades["sigma"]), ("model", "model"))
        rec = v.as_record()
        self.assertEqual(tuple(rec), verdict.RECORD_KEYS)
        self.assertEqual(json.loads(json.dumps(rec, allow_nan=False)), rec)

    def test_dof_thresholds_are_required(self):
        with self.assertRaises(TypeError):
            model.from_reading(Reading(score=0.1, sigma=0.5), 3000.0, 0)

    def test_each_branch_is_reachable(self):
        v = model.from_reading
        self.assertEqual(v(Reading(0.1, 0.5), 3000.0, 0, **DOF).verdict, verdict.Verdict.IN_FOCUS)
        self.assertEqual(v(Reading(-2.0, 0.5), 3000.0, 0, **DOF).verdict, verdict.Verdict.STEP_UP)
        self.assertEqual(v(Reading(2.0, 0.5), 3000.0, 0, **DOF).verdict, verdict.Verdict.STEP_DOWN)
        self.assertEqual(v(Reading(2.0, 0.5, tiles=()), 3000.0, 0, **DOF).verdict,
                         verdict.Verdict.NO_SAMPLE_HERE)
        self.assertEqual(v(Reading(2.0, 9.0), 3000.0, 0, **DOF).verdict, verdict.Verdict.UNSURE)


class Module(unittest.TestCase):
    def test_the_verdict_types_are_the_sibling_s(self):
        v = model.from_reading(Reading(0.1, 0.5), 3000.0, 0, **DOF)
        self.assertIsInstance(v, verdict.FocusVerdict)
        self.assertIs(v.verdict, verdict.Verdict.IN_FOCUS)


if __name__ == "__main__":
    unittest.main()
