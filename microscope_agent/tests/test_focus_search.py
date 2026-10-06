# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/tests/test_focus_search.py
# body-sha256: 317b654a3c42dab90fef5e79fa312ef2eaa5dff48e78394577122c8afe766c20
"""focus_search.py, the 100x search as steps: loaded by path, stdlib + numpy only.

Runs with `python -m unittest` from this folder and under pytest."""

import importlib.util
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


fs = _load("_mic_focus_search", SRC / "focus_search.py")


# The caller's numbers (dino-autofocus bench_values.FOCUS_ARG_DEFAULTS and the 2026-09-30
# bench values); the flat module holds none of its own.
DEFAULTS = {"half_um": 40.0, "step_um": 2.0, "fine_half_um": 3.0, "fine_step_um": 0.2,
            "exposure_ms": 20.0, "max_extensions": 3}
CENTRE = {"default_centre_um": 2930.0, "parfocal_offset_um": -60.0}
DARK = {"dark_offset_adu": 102.0, "signal_min_adu": 50.0}


class FocusSearch(unittest.TestCase):
    def test_parse(self):
        a = fs.parse({"sample_id": "s", "half_um": 30}, DEFAULTS)
        self.assertEqual((a.half_um, a.step_um, a.metric), (30, 2.0, "peak"))
        for bad in ({"metric": "dino"}, {"step_um": 0}, {"fine_half_um": float("nan")},
                    {"nope": 1}, {"max_extensions": -1}, {"max_extensions": 1.5},
                    {"aura_line": "GREEN"}):  # the search takes no light
            with self.assertRaises(ValueError):
                fs.parse(bad, DEFAULTS)
        with self.assertRaises(ValueError):  # no number and no default: refused, not guessed
            fs.parse({}, {k: v for k, v in DEFAULTS.items() if k != "exposure_ms"})
        with self.assertRaises(ValueError):  # the extension count is the caller's too
            fs.parse({}, {k: v for k, v in DEFAULTS.items() if k != "max_extensions"})
        self.assertFalse(hasattr(fs, "MAX_EXTENSIONS"))
        self.assertNotIn("aura_line", fs.FocusArgs.__dataclass_fields__)

    def test_sweep_z_ascends_and_stays_inside_the_limits(self):
        z = fs.sweep_z(2930.0, 40.0, 2.0, floor_um=2800.0, ceiling_um=2982.0)
        self.assertEqual((z[0], z[-1], len(z)), (2890.0, 2970.0, 41))
        self.assertEqual(z, sorted(z))
        z = fs.sweep_z(2960.0, 40.0, 2.0, floor_um=2800.0, ceiling_um=2982.0)
        self.assertEqual(z[-1], 2982.0)  # clipped at the ceiling, never above
        z = fs.sweep_z(2810.0, 40.0, 3.0, floor_um=2800.0, ceiling_um=3200.0)
        self.assertEqual((z[0], z[-1]), (2800.0, 2848.0))
        self.assertEqual(fs.sweep_z(2900.0, 0.6, 0.2, floor_um=0, ceiling_um=3200),
                         [2899.4, 2899.6, 2899.8, 2900.0, 2900.2, 2900.4, 2900.6])
        for args in ((2930.0, 40.0, 0.0), (2930.0, -1.0, 2.0), (3300.0, 10.0, 2.0),
                     (float("inf"), 1.0, 1.0)):
            with self.assertRaises(ValueError):
                fs.sweep_z(*args, floor_um=2800.0, ceiling_um=3200.0)

    def test_spans(self):
        a = fs.FocusArgs(**DEFAULTS)
        self.assertEqual(fs.coarse_span(2930.0, a), (2930.0, 40.0, 2.0))
        self.assertEqual(fs.fine_span(2911.3, a), (2911.3, 3.0, 0.2))
        # one span higher, swept up from the old low end: centre at the old top
        self.assertEqual(fs.extension_span(2890.0, 2970.0, 2.0), (2970.0, 80.0, 2.0))
        self.assertTrue(fs.room_above(2982.0, 2970.0))
        self.assertFalse(fs.room_above(2970.0 + 1e-7, 2970.0))

    def test_reading_the_coarse_peak(self):
        self.assertEqual(fs.peak_at(True, 40), fs.TOP_END)
        self.assertEqual(fs.peak_at(False, 0), fs.LOW_END)
        self.assertEqual(fs.peak_at(False, 12), fs.INTERIOR)
        self.assertEqual(fs.peak_at(True, 0), fs.TOP_END)

    def test_centre(self):
        c = fs.centre_from_plane({"z_um": 2990.0, "scan": "scan4x_x"}, **CENTRE)
        self.assertEqual((c["centre_um"], c["z_4x_um"], c["grade"]), (2930.0, 2990.0, "computed"))
        self.assertIn("unmeasured provisional", c["source"])
        d = fs.centre_from_plane(None, **CENTRE)
        self.assertEqual((d["centre_um"], d["grade"]), (2930.0, None))
        self.assertEqual(fs.centre_grade(c), "computed")
        self.assertIsNone(fs.centre_grade(d))

    def test_warnings(self):
        self.assertTrue(fs.at_dark_level(152.0, **DARK))
        self.assertFalse(fs.at_dark_level(153.0, **DARK))
        self.assertTrue(fs.too_bright([0.0, None, 0.5], 0.001))
        self.assertFalse(fs.too_bright([None, 0.0], 0.001))


if __name__ == "__main__":
    unittest.main()
