"""Card 068 step 3: a round's number enters the bleach-recovery design only through the store.

Round 1 of thr-bleach-recovery-diffusivity-001 found a bead count one bleach
needs before its D lands inside the tie. plan.md 11-26 (8c57691): that number
reaches an axis only as a store entry, after a query. Until the librarian
enters it (librarian task 049), A2 abstains on it and names that remedy, and no
number is taken from the payload. A goal that stands on no round is left
exactly as it was.

Run: PYTHONUTF8=1 python -m unittest tests/test_design_bleach_recovery_round.py
"""
from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dbr = _load("_t068_design_bleach_recovery", SRC / "design_bleach_recovery.py")

PIN = "kbv-TEST068"
CID = "mic-TEST068:v5:widefield_inline:a2"
FLOOR = "recovery_curve_tie_particle_count"
ROUND = "thr-bleach-recovery-diffusivity-001:r1"


def goal(with_round: bool) -> dict:
    g = {"card": "goal", "qid": "mic-TEST068", "revision": 5,
         "observable": {"name": "bleach_recovery_diffusivity"},
         "numbers": [{"name": "tracer_diameter", "value": 0.1, "unit": "um",
                      "source": "assumed:a_bead_identity", "grade": "E5",
                      "precision": "order_of_magnitude"}],
         "assumptions": []}
    if with_round:
        g["from_round"] = ROUND
    return g


def responses(floor_entry: bool) -> dict:
    """What build_responses returns, built by hand: no store is read here."""
    answered = {"kb_version": PIN, "commit": "TEST"}
    r = {"pin": PIN, "caller_id": CID, "entries": {}, "gaps": []}
    if floor_entry:
        r["entries"]["TEST_recovery_curve_tie_particle_count"] = {
            "grade": "E5", "claim": "TEST ENTRY, card 068: not a fact about anything",
            "answered_from": answered,
            "numbers": [{"name": FLOOR, "value": 300, "unit": "count",
                         "source": "simulated:TEST", "grade": "E5"}]}
    else:
        r["gaps"].append({"observable": FLOOR, "kind": "absent", "tool": "kb_query",
                          "searched": ["kb/entries", "kb/exports"], "asked_at": "TEST",
                          "answered_from": answered, "near_names": []})
    return r


def outcome(run, id_):
    return next((o for o in run.outcomes if o.inequality_id == id_), None)


class BeadCountFloorThroughTheStore(unittest.TestCase):

    def test_no_entry_abstains_naming_the_remedy(self):
        run = dbr.run_axis("a2", goal(True), CID, PIN, responses(floor_entry=False))
        o = outcome(run, "beads_in_disc_reach_tie")
        self.assertIsNotNone(o, "a goal on the round must speak about the bead-count floor")
        self.assertEqual(o.state, "abstained")
        self.assertEqual(o.missing, [FLOOR])
        self.assertIn("049", o.reason)
        self.assertEqual(run.silent(), [])

    def test_no_entry_carries_no_payload_number(self):
        run = dbr.run_axis("a2", goal(True), CID, PIN, responses(floor_entry=False))
        o = outcome(run, "beads_in_disc_reach_tie")
        self.assertIsNone(o.precondition)
        self.assertIsNone(o.interval)
        self.assertNotIn("300", o.reason, "the payload's number must not ride in on the reason")

    def test_entry_present_bounds_on_it_by_reference(self):
        run = dbr.run_axis("a2", goal(True), CID, PIN, responses(floor_entry=True))
        o = outcome(run, "beads_in_disc_reach_tie")
        self.assertEqual(o.state, "returned")
        self.assertEqual(o.precondition["basis"], ["kb:TEST_recovery_curve_tie_particle_count"])
        self.assertEqual(o.precondition["parameter"], "bead_count_in_bleached_column")
        self.assertIn("effective", o.precondition["requires"])
        self.assertNotIn("300", o.precondition["requires"], "cited by reference, not restated")
        self.assertIn("TEST_recovery_curve_tie_particle_count", {r["entry_id"] for r in run.kb_refs})

    def test_goal_without_the_round_is_unchanged(self):
        r = responses(floor_entry=False)
        r["gaps"] = []
        run = dbr.run_axis("a2", goal(False), CID, PIN, r)
        self.assertIsNone(outcome(run, "beads_in_disc_reach_tie"))
        self.assertEqual([i.id for i in run.owned], [i.id for i in dbr.AXIS_BOUNDS["a2"]])
        self.assertEqual(run.silent(), [])

    def test_the_round_does_not_widen_other_axes(self):
        for axis in ("a3", "a5"):
            run = dbr.run_axis(axis, goal(True), CID.replace("a2", axis), PIN,
                               {"pin": PIN, "caller_id": CID, "entries": {}, "gaps": []})
            self.assertIsNone(outcome(run, "beads_in_disc_reach_tie"))


AVERAGE_THEN_FIT = {"name": "average_then_fit",
                    "statement": "TEST: average the curves first, then fit the mean curve once",
                    "from_round": ROUND, "round_revision": 2}


class TheRoundsFitMethodIsADesignInput(unittest.TestCase):
    """Card 068 steps 1-2: the method enters directly, copied exactly, with no source or grade."""

    def goal_with_method(self):
        g = goal(True)
        g["design_inputs"] = [copy.deepcopy(AVERAGE_THEN_FIT)]
        return g

    def card(self, g, axis="a2"):
        run = dbr.run_axis(axis, g, CID.replace("a2", axis), PIN, responses(floor_entry=False))
        return dbr.card_for(run, g, "mic-TEST068", "2026-10-12T00:00:00Z", 5)

    def test_the_fitting_axis_copies_the_item_exactly(self):
        self.assertEqual(self.card(self.goal_with_method())["design_inputs"], [AVERAGE_THEN_FIT])

    def test_the_item_carries_no_source_grade_or_value(self):
        item = self.card(self.goal_with_method())["design_inputs"][0]
        self.assertEqual(set(item), {"name", "statement", "from_round", "round_revision"})

    def test_a_goal_without_design_inputs_gives_an_axis_without_them(self):
        self.assertNotIn("design_inputs", self.card(goal(True)))
        self.assertNotIn("design_inputs", self.card(goal(False)))

    def test_axes_that_do_not_fit_take_nothing(self):
        for axis in ("a3", "a5"):
            self.assertNotIn("design_inputs", self.card(self.goal_with_method(), axis))


if __name__ == "__main__":
    unittest.main()
