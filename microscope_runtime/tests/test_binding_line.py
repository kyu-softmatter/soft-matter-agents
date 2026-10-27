"""Card 098 part 5: a plan action may name the light line it drives, and the binding is picked by it.

    python -m unittest tests.test_binding_line        (from microscope_runtime/)

A device such as a multi-line light engine binds one quantity once per line, each to its own property.
The plan's action carries `line` (plan.schema.json, `f37a56b9d`): every parameter of the action applies
to that line and two lines take two actions. The runtime picks the binding whose line equals the
action's, compared exactly and never case-folded or trimmed. A quantity whose bindings carry lines
refuses an action that names none or a line no binding carries, naming the row, the quantity and the
lines it does carry; and it never falls back to a binding that has no line. Where no binding carries a
line, nothing changes. Mock only: every line, property and number is a TEST value.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SRC = TESTS.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))

import mm_label_registry as R                                          # noqa: E402
import orchestrator as orch                                            # noqa: E402
import test_parameters_classified as t95                               # noqa: E402

GREEN = {"quantity": "lamp_power", "property": "GreenIntensity", "unit": "permille", "line": "GREEN"}
NIR = {"quantity": "lamp_power", "property": "NirIntensity", "unit": "permille", "line": "NIR"}
PLAIN = {"quantity": "lamp_power", "property": "Intensity", "unit": "permille"}
SET_POWER = "set_power"
DEVICE = "widefield_source_a"      # labelled Aura here: the one lamp software may write any property of


def lit(line, value=300, name="lamp_power", device=DEVICE, aid="a_lamp"):
    """One action driving `line` (None leaves the field out) and the number it points at."""
    act = t95.action(aid, device, SET_POWER, [name])
    if line is not None:
        act["line"] = line
    return act, t95.number(name, value, "permille", "E5")


def plan_for(*pairs):
    return t95.plan_of(actions=[a for a, _ in pairs], numbers=[n for _, n in pairs])


class _Line(t95._Run):
    def applied(self, plan, bindings):
        record, events = self.go(plan, bindings={DEVICE: bindings}, labels={DEVICE: "Aura"})
        return record, events, [e for e in self.named(events, "apply") if e.get("action") == SET_POWER]

    def drives(self, line, bindings=(GREEN, NIR), value=300):
        return self.applied(plan_for(lit(line, value)), list(bindings))

    def refused(self, line, *needles, bindings=(GREEN, NIR)):
        record, events, _ = self.drives(line, bindings)
        self.assertRefusedBeforeAnyCommand(record, events, *needles)
        return record


class T1TheBindingOfTheNamedLineIsWritten(_Line):
    def test_green_writes_the_green_property_and_nothing_else(self):
        record, events, apply = self.drives("GREEN", value=300)
        self.assertEqual(record["ended"], "completed", record)
        self.assertEqual(len(apply), 1)
        self.assertEqual(apply[0]["settings_sent"], {"Aura": {"GreenIntensity": 300}})

    def test_nir_writes_the_nir_property_whichever_binding_comes_first(self):
        for bindings in ((GREEN, NIR), (NIR, GREEN)):
            with self.subTest(first=bindings[0]["line"]):
                record, events, apply = self.drives("NIR", bindings, value=120)
                self.assertEqual(apply[0]["settings_sent"], {"Aura": {"NirIntensity": 120}})

    def test_two_actions_take_two_lines(self):
        # The parameter's name is the quantity, so both actions point at the one number.
        green, number = lit("GREEN", 300, aid="a_green")
        nir, _ = lit("NIR", 300, aid="a_nir")
        record, events, apply = self.applied(t95.plan_of(actions=[green, nir], numbers=[number]), [GREEN, NIR])
        self.assertEqual(record["ended"], "completed", record)
        sent = sorted((p, v) for e in apply for props in e["settings_sent"].values() for p, v in props.items())
        self.assertEqual(sent, [("GreenIntensity", 300), ("NirIntensity", 300)])

    def test_the_apply_event_and_the_derivation_name_the_line(self):
        record, events, apply = self.drives("GREEN")
        self.assertEqual(apply[0]["written"][0]["line"], "GREEN")
        self.assertIn("lamp_power[GREEN] ->", apply[0]["written"][0]["binding"])
        self.eventsValidate(events)


class T2ALineThatPicksNoBindingRefusesBeforeAnyCommand(_Line):
    def test_no_line_where_the_bindings_carry_lines_names_the_row_the_quantity_and_both_lines(self):
        self.refused(None, DEVICE, "lamp_power", "GREEN", "NIR", "names no line")

    def test_a_line_no_binding_carries_names_it_and_the_lines_there_are(self):
        self.refused("RED", "RED", DEVICE, "lamp_power", "GREEN", "NIR")

    def test_the_comparison_is_exact_not_case_folded(self):
        self.refused("green", "green", "GREEN")

    def test_the_comparison_does_not_trim(self):
        self.refused("GREEN ", "GREEN ")

    def test_a_refused_line_writes_nothing_even_when_the_plan_also_has_a_good_action(self):
        green, number = lit("GREEN", 300, aid="a_green")
        red, _ = lit("RED", 300, aid="a_red")
        record, events, apply = self.applied(t95.plan_of(actions=[green, red], numbers=[number]), [GREEN, NIR])
        self.assertRefusedBeforeAnyCommand(record, events, "RED")
        self.assertEqual(apply, [])

    def test_a_line_on_a_quantity_none_of_whose_bindings_has_a_line_refuses(self):
        self.refused("GREEN", "GREEN", "on no line", bindings=(PLAIN,))

    def test_a_line_on_an_action_with_no_setting_is_not_silently_dropped(self):
        act = t95.action("a_lamp", DEVICE, SET_POWER, [])
        act["line"] = "GREEN"
        record, events, apply = self.applied(t95.plan_of(actions=[act]), [GREEN, NIR])
        self.assertRefusedBeforeAnyCommand(record, events, "GREEN", "no parameter")


class T3WhereNoBindingCarriesALineNothingChanges(_Line):
    def test_an_action_with_no_line_writes_the_plain_binding(self):
        record, events, apply = self.drives(None, bindings=(PLAIN,))
        self.assertEqual(record["ended"], "completed", record)
        self.assertEqual(apply[0]["settings_sent"], {"Aura": {"Intensity": 300}})
        self.assertNotIn("line", apply[0]["written"][0])


class T4ARegistryThatCannotPickIsRefusedAtLoad(unittest.TestCase):
    def load(self, items):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = R.write(tmp, bindings={DEVICE: items}, labels={DEVICE: "Aura"})
            return orch.Orchestrator(registry_path=path, backend="mock")

    def test_the_two_lines_load(self):
        self.assertIsNotNone(self.load([GREEN, NIR]))

    def test_one_quantity_on_one_line_twice(self):
        again = {**GREEN, "property": "OtherIntensity"}
        with self.assertRaises(orch.GapError) as caught:
            self.load([GREEN, again])
        self.assertIn("GREEN", str(caught.exception))

    def test_two_lines_on_one_property(self):
        same = {**NIR, "property": GREEN["property"]}
        with self.assertRaises(orch.GapError):
            self.load([GREEN, same])

    def test_a_quantity_with_a_line_and_the_same_quantity_without_one(self):
        other = {**PLAIN, "property": "Intensity"}
        with self.assertRaises(orch.GapError) as caught:
            self.load([GREEN, other])
        self.assertIn("lamp_power", str(caught.exception))

    def test_a_line_that_is_empty_or_not_a_string(self):
        for bad in ("", 7, None, ["GREEN"]):
            with self.subTest(line=bad):
                with self.assertRaises(orch.GapError):
                    self.load([{**GREEN, "line": bad}])


if __name__ == "__main__":
    unittest.main()
