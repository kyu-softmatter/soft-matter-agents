# origin: soft-matter-agents, the original since 2026-10-05; dino-autofocus mirrors it:
#   https://github.com/kyu-softmatter/soft-matter-agents/blob/f2c56dcfc018b23ff784dc2ac06e150db499f556/microscope_agent/tests/test_focus_core.py
# body-sha256: 401dc7ec20c99e857db5e4a8266f8cbc1c553d6023e9d6cc3e21f912797f4d11
"""The flat focus files in the soft-matter-agents style: loaded by path, stdlib + numpy only.

Runs with `python -m unittest` from this folder (as soft-matter-agents runs its tests) and
under pytest. The data are built inline; no fixture files (that repo's check 13). The run-log
event has its own file, test_focus_run_log.py, so these tests need no focus_run_log.py."""

import importlib.util
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


def _frame(sigma_px: float) -> np.ndarray:
    """A spot blurred by `sigma_px` on a flat background, same total light, as uint16."""
    yy, xx = np.mgrid[0:64, 0:64]
    spot = np.exp(-((yy - 32.0) ** 2 + (xx - 32.0) ** 2) / (2 * sigma_px ** 2))
    return (200 + 3000 * spot * (2.0 / sigma_px) ** 2).astype(np.uint16)


# This repository's provisional thresholds (dino-autofocus bench_values); the flat modules
# take them as arguments and hold no numbers of their own.
RULES = {"min_dynamic_range_adu": 20.0, "min_contrast": 0.05, "min_frames": 3,
         "dropout_tolerance": 0.02, "max_saturated": 0.001}


class FocusCore(unittest.TestCase):
    def test_sweep_through_focus_is_in_focus_at_a_real_frame(self):
        z = [100.0, 102.0, 104.0, 106.0, 108.0]
        frames = [_frame(s) for s in (6.0, 3.5, 2.0, 3.5, 6.0)]
        stats = [classical.frame_stats(f, "vollath4", ceiling=CEILING) for f in frames]
        v = verdict.from_sweep(z, stats, **RULES)
        self.assertEqual(v.verdict, verdict.Verdict.IN_FOCUS)
        self.assertIn(v.z_um, z)  # an encoder z of a frame, never an interpolated one

    def test_dark_sweep_has_no_sample(self):
        dark = [np.full((64, 64), 100, np.uint16) for _ in range(4)]
        stats = [classical.frame_stats(f, "vollath4", ceiling=CEILING) for f in dark]
        v = verdict.from_sweep([0.0, 1.0, 2.0, 3.0], stats, **RULES)
        self.assertEqual(v.verdict, verdict.Verdict.NO_SAMPLE_HERE)

    def test_double_peak_without_scipy(self):
        z = np.arange(0.0, 20.0)
        s = np.exp(-((z - 5) ** 2) / 4) + 0.8 * np.exp(-((z - 14) ** 2) / 4)
        self.assertTrue(classical.double_peak(z, s, 0.2))

    def test_one_module_object_per_file(self):
        self.assertIs(verdict.FrameStats, classical.FrameStats)


if __name__ == "__main__":
    unittest.main()
