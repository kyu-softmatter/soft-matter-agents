# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/tests/test_focus_step_rules.py
# body-sha256: 848d48ea2e5f3d750c7a5e6413610962318c92ae3abc191977833ca7229f4d20
"""focus_step_rules.py: the guards' comparisons as pure functions, loaded by path, stdlib only.

Runs with `python -m unittest` from this folder and under pytest. The numbers below are this
repository's provisional bench values (the engine's guards); the module holds none."""

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


rules = _load("_mic_focus_step_rules", SRC / "focus_step_rules.py")

WINDOW = (2800.0, 3200.0)
TOP = WINDOW[1]
RETRACT, RETURN = 0.0, 2800.0
TOL = 0.25
WD_FRACTION = 0.4
FREE_WD = {"4x": 20000.0, "10x": 4000.0, "20x": 800.0, "40x-WI": 170.0, "60x-Oil": 150.0,
           "100x-Oil": 130.0}
ROWS = {"4x": (10000.0, 10.0), "10x": (1000.0, 10.0), "20x": (777.0, 10.0),
        "40x-WI": (390.0, 10.0), "60x-Oil": (260.0, 10.0), "100x-Oil": (156.0, 10.0)}
RETRACTED_MAX = RETRACT + 1.0


class Values(unittest.TestCase):
    def test_a_model_number_drives_no_motion(self):
        self.assertIsNone(rules.refuse_model_graded("measured", "z"))
        self.assertIsNone(rules.refuse_model_graded(None, "z"))
        self.assertIn("model output", rules.refuse_model_graded("model", "z", "dino head"))

    def test_strictest_row_for_an_unknown_lens(self):
        self.assertEqual(rules.strictest_for_unknown_lens(ROWS), (0.0, 10.0))
        with self.assertRaises(ValueError):
            rules.strictest_for_unknown_lens({})

    def test_bad_numbers_are_refused_not_coerced(self):
        for bad in (float("nan"), float("inf"), "x", None):
            with self.assertRaises(ValueError):
                rules.inside_window(bad, WINDOW)


class Z(unittest.TestCase):
    def test_window_and_readback(self):
        self.assertIsNone(rules.inside_window(2930.0, WINDOW))
        self.assertIn("outside the window", rules.inside_window(2799.9, WINDOW))
        self.assertIsNone(rules.readback_ok(3037.0, 3037.2, TOL))
        # 2026-09-30: commanded 3037.0, read 3036.0 -> stopped
        self.assertIn("read 3036.000", rules.readback_ok(3037.0, 3036.0, TOL))

    def test_move_up_needs_permission_and_descents_are_free(self):
        self.assertIsNone(rules.may_move_up(2950.0, 2900.0, 0.0, TOL))
        self.assertIsNone(rules.may_move_up(2950.0, 2950.2, 0.0, TOL))  # flat within tol
        self.assertIn("only 0.00 um allowed", rules.may_move_up(2950.0, 2952.0, 0.0, TOL))
        self.assertIsNone(rules.may_move_up(2950.0, 2952.0, 2.0, TOL))

    def test_park_only_descends_and_stays_between_retract_and_window_top(self):
        park = rules.park_only_descends
        self.assertIsNone(park(2950.0, 0.0, TOL, RETRACT, TOP))
        self.assertIn("only descends", park(2950.0, 2960.0, TOL, RETRACT, TOP))
        self.assertIn("outside", park(2950.0, -5.0, TOL, RETRACT, TOP))

    def test_plans_ascend_one_step_at_a_time_inside_the_ceiling(self):
        plan = [2890.0 + 2.0 * k for k in range(41)]
        self.assertIsNone(rules.ascending(plan, 2.0))
        self.assertIn("not ascending", rules.ascending([2890.0, 2894.1], 2.0))
        self.assertIn("not ascending", rules.ascending([2890.0, 2890.0], 2.0))
        self.assertEqual(rules.ascending([], 2.0), "empty sweep plan")
        self.assertIsNone(rules.plan_inside(plan, WINDOW[0], 2982.0))
        self.assertIn("leaves", rules.plan_inside(plan, WINDOW[0], 2960.0))

    def test_sweep_ceiling_per_lens(self):
        ceiling = rules.sweep_ceiling
        # 100x Oil at the 2026-09-30 centre: 2930 + 0.4 x 130 = 2982, under the window top
        self.assertEqual(ceiling(2930.0, TOP, FREE_WD["100x-Oil"], WD_FRACTION), 2982.0)
        self.assertEqual(ceiling(2930.0, TOP, FREE_WD["4x"], WD_FRACTION), 3200.0)
        self.assertIsNone(ceiling(2930.0, TOP, None, WD_FRACTION, released=True))
        with self.assertRaises(ValueError):  # no working distance: no plan, never a guess
            ceiling(2930.0, TOP, None, WD_FRACTION)

    def test_approach_ceiling_is_the_window_top_only_when_the_wd_covers_it(self):
        for lens in ("4x", "10x", "20x"):
            self.assertEqual(rules.approach_ceiling(RETURN, TOP, FREE_WD[lens]), 3200.0, lens)
        for lens in ("40x-WI", "60x-Oil", "100x-Oil"):
            self.assertEqual(rules.approach_ceiling(RETURN, TOP, FREE_WD[lens]), 2800.0, lens)
        self.assertEqual(rules.approach_ceiling(RETURN, TOP, None), 2800.0)

    def test_approach_step_is_the_row_step_or_smaller_and_above_the_tolerance(self):
        step = rules.approach_step_allowed
        self.assertEqual(step(None, 10.0, TOL), 10.0)
        self.assertEqual(step(5.0, 10.0, TOL), 5.0)
        self.assertIn("larger than", step(20.0, 10.0, TOL, "100x-Oil"))
        self.assertIn("exceed the readback tolerance", step(0.2, 10.0, TOL))

    def test_approach_steps_follow_the_bench_procedure(self):
        # from the retract: one move to the window bottom, then 10 um steps, the last one short
        steps = rules.approach_steps(0.0, 2935.0, 10.0, RETURN, TOL)
        self.assertEqual(steps[:3], [2800.0, 2810.0, 2820.0])
        self.assertEqual(steps[-2:], [2930.0, 2935.0])
        self.assertEqual(len(steps), 1 + 14)
        self.assertEqual(rules.approach_steps(2900.0, 2915.0, 10.0, RETURN, TOL),
                         [2910.0, 2915.0])
        # above the target: straight down in one move; already there: nothing
        self.assertEqual(rules.approach_steps(2950.0, 2900.0, 10.0, RETURN, TOL), [2900.0])
        self.assertEqual(rules.approach_steps(2900.1, 2900.0, 10.0, RETURN, TOL), [])
        with self.assertRaises(ValueError):
            rules.approach_steps(0.0, 2900.0, 0.0, RETURN, TOL)

    def test_every_approach_step_must_rise(self):
        self.assertIsNone(rules.rise_ok(2810.0, 2819.9))
        self.assertIn("did not rise", rules.rise_ok(2810.0, 2810.0))

    def test_retracted(self):
        self.assertTrue(rules.retracted(0.3, RETRACTED_MAX))
        self.assertFalse(rules.retracted(2.0, RETRACTED_MAX))


class PFS(unittest.TestCase):
    def test_pfs_must_be_known_and_off(self):
        self.assertIsNone(rules.pfs_quiet(False))
        self.assertIn("enabled", rules.pfs_quiet(True))
        self.assertIn("unknown", rules.pfs_quiet(None))
        self.assertTrue(rules.pfs_out_of_range("Out of Range"))
        self.assertFalse(rules.pfs_out_of_range("In Range"))
        self.assertFalse(rules.pfs_out_of_range(None))

    def test_nosepiece_turns_only_retracted_with_pfs_off_and_out_of_range(self):
        turn = rules.nosepiece_turn_allowed
        self.assertIsNone(turn(0.2, RETRACTED_MAX, False, "Out of Range"))
        self.assertIn("not retracted", turn(2800.0, RETRACTED_MAX, False, "Out of Range"))
        self.assertIn("enabled", turn(0.2, RETRACTED_MAX, True, "Out of Range"))
        self.assertIn("refusing to rotate", turn(0.2, RETRACTED_MAX, False, "In Range"))


class XY(unittest.TestCase):
    BOX = (-1000.0, 1000.0, -1000.0, 1000.0)

    def test_box_and_readback(self):
        self.assertIsNone(rules.inside_box(100.0, -100.0, self.BOX))
        self.assertIn("outside the box", rules.inside_box(1001.0, 0.0, self.BOX))
        self.assertIsNone(rules.xy_readback_ok((100.0, 0.0), (103.0, 2.0), 5.0))
        self.assertIn("read (106.0, 0.0)", rules.xy_readback_ok((100.0, 0.0), (106.0, 0.0), 5.0))

    def test_long_moves_need_z_retracted_on_immersion_or_unknown_lenses(self):
        need = rules.needs_retract_before_xy
        long_100x = ROWS["100x-Oil"][0]
        self.assertIsNone(need(100.0, long_100x, 2950.0, RETRACTED_MAX, immersion=True))
        self.assertIn("immersion lens",
                      need(500.0, long_100x, 2950.0, RETRACTED_MAX, immersion=True))
        self.assertIsNone(need(500.0, long_100x, 0.5, RETRACTED_MAX, immersion=True))
        # Q4: a dry lens released from the rule moves at sample height
        self.assertIsNone(need(3300.0, ROWS["4x"][0], 2950.0, RETRACTED_MAX, immersion=False))
        # an unknown lens: the strictest row (threshold 0) and ambiguity refuses
        long_unknown, _ = rules.strictest_for_unknown_lens(ROWS)
        self.assertIn("unknown kind",
                      need(1.0, long_unknown, 2950.0, RETRACTED_MAX, immersion=None))


if __name__ == "__main__":
    unittest.main()
