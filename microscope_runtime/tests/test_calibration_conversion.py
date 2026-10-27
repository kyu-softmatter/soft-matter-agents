"""Card 098: a calibration converts by its points, and every written value takes its binding's step.

    python -m unittest tests.test_calibration_conversion        (from microscope_runtime/)

Card 095 left two gaps: a calibration that passed every gate still refused with "no conversion form",
and the routes wrote whatever they computed, so the exact-factor route could write a float to a
property that takes whole steps. Now an E2 calibration entry's `conversion` (direction
`physical_to_control`, rule `piecewise_linear_within_points`) is applied in exact fractions, and a
value on any of the three routes is rounded to its binding's `step`, ties to even, or the write is
refused. Mock only: every binding, step, calibration and point below is a TEST value from
`mm_label_registry`, and none of them is a measurement of any lamp.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SRC = TESTS.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))

import test_parameters_classified as t95                           # noqa: E402

POWER = {"quantity": "lamp_power", "property": "Intensity", "unit": "permille"}
SET_POWER = "set_power"


def point(physical, control, physical_unit="W", control_unit="permille"):
    return {"physical": {"value": physical, "unit": physical_unit},
            "control": {"value": control, "unit": control_unit}, "source": "measured:run-test-098"}


def form(**over):
    """The agreed conversion form with the three test points of the card; `over` replaces a key."""
    base = {"direction": "physical_to_control", "rule": "piecewise_linear_within_points",
            "physical": {"quantity": "lamp_power", "unit": "W"}, "control": {"unit": "permille"},
            "points": [point(0, 0), point(0.002, 400), point(0.005, 1000)]}
    base.update(copy.deepcopy(over))
    return base


def calibration(conversion=None, **over):
    base = {"conversion": form() if conversion is None else conversion,
            "validity": {"lamp_power": {"min": 0, "max": 0.01, "unit": "W"}}}
    base.update(over)
    return t95.calibration(**base)


def power_plan(value, unit="mW", grade="E5"):
    return t95.plan_of(actions=[t95.action("a_lamp", "dia_lamp", SET_POWER, ["lamp_power"])],
                       numbers=[t95.number("lamp_power", value, unit, grade)])


class _Convert(t95._Run):
    def applied(self, plan, **registry):
        """(record, events, the one set_power apply event or None)."""
        record, events = self.go(plan, **registry)
        found = [e for e in self.named(events, "apply") if e.get("action") == SET_POWER]
        return record, events, (found[0] if found else None)

    def writes(self, value, unit="mW", *, conversion=None, binding=None, grade="E5", **cal):
        """What a plan number of `value` `unit` writes through the calibration route."""
        record, events, apply = self.applied(
            power_plan(value, unit, grade),
            bindings={"dia_lamp": [binding or POWER]},
            calibrations=[calibration(conversion, **cal)])
        return record, events, apply

    def assertWrote(self, apply, value):
        self.assertIsNotNone(apply, "no command went out")
        self.assertEqual(apply["settings_sent"], {"DiaLamp": {"Intensity": value}})
        self.assertEqual(apply["written"][0]["written"], value)


class T1ThePointsConvertAMilliwattNumberToPermille(_Convert):
    def test_one_two_three_and_a_half_and_five_milliwatts(self):
        for milliwatts, permille in ((1, 200), (2, 400), (3.5, 700), (5, 1000)):
            with self.subTest(milliwatts=milliwatts):
                record, events, apply = self.writes(milliwatts)
                self.assertEqual(record["ended"], "completed", record)
                self.assertWrote(apply, permille)

    def test_zero_is_the_first_point(self):
        record, events, apply = self.writes(0)
        self.assertWrote(apply, 0)

    def test_5_1_milliwatts_is_outside_the_points_and_the_refusal_names_the_span(self):
        record, events, apply = self.writes(5.1)
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "0.005", "W", "points")

    def test_the_apply_event_records_both_values_and_the_calibration(self):
        record, events, apply = self.writes(1)
        row = apply["written"][0]
        self.assertEqual((row["plan_value"], row["plan_unit"]), (1, "mW"))
        self.assertEqual((row["physical_value"], row["physical_unit"]), (0.001, "W"))
        self.assertEqual((row["unrounded"], row["written"], row["unit"]), (200, 200, "permille"))
        self.assertEqual(row["calibration"], "mm_calibration_0")
        self.assertEqual(row["step"], {"value": 1, "unit": "permille"})
        self.eventsValidate(events)

    def test_decimal_strings_in_the_points_are_read_exactly(self):
        points = [point("0", "0"), point("0.002", "400"), point("0.005", "1000")]
        record, events, apply = self.writes(3.5, conversion=form(points=points))
        self.assertWrote(apply, 700)

    def test_a_decreasing_control_is_a_monotone_control(self):
        points = [point(0, 1000), point(0.002, 600), point(0.005, 0)]
        record, events, apply = self.writes(1, conversion=form(points=points))
        self.assertWrote(apply, 800)

    def test_every_segment_is_its_own_slope_and_a_value_on_an_inner_point_gives_that_point(self):
        points = [point(0, 0), point(0.002, 400), point(0.004, 500), point(0.008, 900)]
        for milliwatts, permille in ((1, 200), (3, 450), (4, 500), (6, 700), (8, 900)):
            with self.subTest(milliwatts=milliwatts):
                record, events, apply = self.writes(milliwatts, conversion=form(points=points))
                self.assertWrote(apply, permille)

    def test_the_validity_range_still_bounds_a_value_the_points_cover(self):
        cal = calibration(validity={"lamp_power": {"min": 0, "max": 0.003, "unit": "W"}})
        record, events, apply = self.applied(power_plan(4), bindings={"dia_lamp": [POWER]},
                                             calibrations=[cal])
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "does not cover")


class T2AnInterpolationOnTheHalfStepRoundsToTheEvenOne(_Convert):
    HALF = form(points=[point(0, 0), point(0.004, 10)])

    def test_two_and_a_half_goes_down_and_seven_and_a_half_goes_up(self):
        for milliwatts, permille, unrounded in ((1, 2, 2.5), (3, 8, 7.5)):
            with self.subTest(milliwatts=milliwatts):
                record, events, apply = self.writes(milliwatts, conversion=self.HALF)
                self.assertWrote(apply, permille)
                self.assertEqual(apply["written"][0]["unrounded"], unrounded)

    def test_no_floating_point_drift_before_the_rounding(self):
        # 0.0005 / 0.003 * 3 is 0.5000000000000001 in floating point, which would round up to 1.
        points = [point(0, 0), point(0.003, 3)]
        record, events, apply = self.writes(0.5, conversion=form(points=points))
        self.assertWrote(apply, 0)
        self.assertEqual(apply["written"][0]["unrounded"], 0.5)
        record, events, apply = self.writes(1.5, conversion=form(points=points))
        self.assertWrote(apply, 2)


class T3AMalformedFormRefusesNamingTheField(_Convert):
    def refuses(self, conversion, *needles, **kw):
        record, events, apply = self.writes(1, conversion=conversion, **kw)
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", *needles)

    def test_a_wrong_direction(self):
        self.refuses(form(direction="control_to_physical"), "conversion.direction")

    def test_an_unknown_rule(self):
        self.refuses(form(rule="least_squares"), "conversion.rule")

    def test_a_form_that_is_not_an_object(self):
        self.refuses("physical_to_control", "no conversion form")

    def test_a_control_unit_that_is_not_the_bindings(self):
        self.refuses(form(control={"unit": "1"}), "conversion.control.unit", "permille")

    def test_one_point(self):
        self.refuses(form(points=[point(0, 0)]), "conversion.points")

    def test_points_that_are_not_a_list(self):
        self.refuses(form(points="0 W is 0 permille"), "conversion.points")

    def test_a_repeated_physical_value(self):
        points = [point(0, 0), point(0.002, 400), point(0.002, 600)]
        self.refuses(form(points=points), "conversion.points[2].physical")

    def test_a_decreasing_physical_value(self):
        points = [point(0, 0), point(0.002, 400), point(0.001, 600)]
        self.refuses(form(points=points), "conversion.points[2].physical")

    def test_a_control_that_turns_back(self):
        points = [point(0, 0), point(0.002, 400), point(0.005, 300)]
        self.refuses(form(points=points), "conversion.points[2].control")

    def test_a_control_that_stands_still(self):
        points = [point(0, 0), point(0.002, 400), point(0.005, 400)]
        self.refuses(form(points=points), "conversion.points[2].control")

    def test_a_form_for_another_quantity(self):
        self.refuses(form(physical={"quantity": "exposure_time", "unit": "W"}),
                     "conversion.physical.quantity", "exposure_time")

    def test_a_point_in_another_physical_unit(self):
        points = [point(0, 0), point(2, 400, physical_unit="mW"), point(0.005, 1000)]
        self.refuses(form(points=points), "conversion.points[1].physical.unit")

    def test_a_point_in_another_control_unit(self):
        points = [point(0, 0), point(0.002, 400, control_unit="1"), point(0.005, 1000)]
        self.refuses(form(points=points), "conversion.points[1].control.unit")

    def test_a_point_value_that_is_not_a_number(self):
        points = [point(0, 0), point("two", 400), point(0.005, 1000)]
        self.refuses(form(points=points), "conversion.points[1].physical.value")

    def test_a_plan_unit_with_no_exact_factor_to_the_forms_physical_unit(self):
        # the validity is in mW, so the plan's mW passes it; the form's physical unit is seconds
        cal = calibration(form(physical={"quantity": "lamp_power", "unit": "s"},
                               points=[point(0, 0, "s"), point(5, 1000, "s")]),
                          validity={"lamp_power": {"min": 0, "max": 10, "unit": "mW"}})
        record, events, apply = self.applied(power_plan(1), bindings={"dia_lamp": [POWER]},
                                             calibrations=[cal])
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "'mW'", "'s'",
                                           "no exact factor")

    def test_a_plan_unit_with_no_exact_factor_to_the_validity_unit(self):
        record, events, apply = self.writes(1, "s")
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "'s'", "'W'",
                                           "no exact factor")


class T4EveryRouteRoundsToTheStepWithTiesToEven(_Convert):
    def run_with(self, value, unit):
        return self.applied(power_plan(value, unit), bindings={"dia_lamp": [POWER]})

    def test_the_unchanged_route_writes_12_for_12_5_permille(self):
        record, events, apply = self.run_with(12.5, "permille")
        self.assertWrote(apply, 12)
        row = apply["written"][0]
        self.assertEqual((row["unrounded"], row["calibration"]), (12.5, None))

    def test_the_unchanged_route_writes_14_for_13_5_permille(self):
        record, events, apply = self.run_with(13.5, "permille")
        self.assertWrote(apply, 14)

    def test_the_exact_factor_route_writes_14_for_0_0135_in_unit_1(self):
        record, events, apply = self.run_with(0.0135, "1")
        self.assertWrote(apply, 14)
        row = apply["written"][0]
        self.assertEqual((row["unrounded"], row["calibration"]), (13.5, None))

    def test_the_exact_factor_route_writes_12_for_0_0125_in_unit_1(self):
        record, events, apply = self.run_with(0.0125, "1")
        self.assertWrote(apply, 12)

    def test_a_step_of_a_half_keeps_a_half(self):
        binding = {**POWER, "step": {"value": 0.5, "unit": "permille"}}
        record, events, apply = self.applied(power_plan(12.3, "permille"),
                                             bindings={"dia_lamp": [binding]})
        self.assertWrote(apply, 12.5)

    def test_a_step_of_ten_rounds_to_a_multiple_of_ten(self):
        binding = {**POWER, "step": {"value": 10, "unit": "permille"}}
        for value, written in ((14, 10), (15, 20), (25, 20), (26, 30)):
            with self.subTest(value=value):
                record, events, apply = self.applied(power_plan(value, "permille"),
                                                     bindings={"dia_lamp": [binding]})
                self.assertWrote(apply, written)

    def test_the_calibration_route_rounds_too(self):
        binding = {**POWER, "step": {"value": 25, "unit": "permille"}}
        record, events, apply = self.writes(3.3, binding=binding)
        self.assertWrote(apply, 650)
        self.assertEqual(apply["written"][0]["unrounded"], 660)

    def test_the_existing_exposure_route_still_writes_100_for_a_tenth_of_a_second(self):
        record, events = self.go(t95.exposure_plan(0.1, "s"), bindings={"camera_red": [t95.EXPOSURE]})
        apply = [e for e in self.named(events, "apply") if e["action"] == "acquire"][0]
        self.assertEqual(apply["settings_sent"], {"Kinetix_red": {"Exposure": 100}})


class T5ABindingWithoutAUsableStepRefusesTheWrite(_Convert):
    ROUTES = (("unchanged", 12, "permille", False), ("exact factor", 0.012, "1", False),
              ("calibration", 1, "mW", True))

    def refused(self, binding, *needles):
        for name, value, unit, with_calibration in self.ROUTES:
            with self.subTest(route=name):
                record, events, apply = self.applied(
                    power_plan(value, unit), bindings={"dia_lamp": [binding]},
                    calibrations=[calibration()] if with_calibration else ())
                self.assertRefusedBeforeAnyCommand(record, events, "mm_binding_dia_lamp_lamp_power",
                                                   "step", *needles)

    def test_no_step_at_all(self):
        self.refused({**POWER, "step": None})

    def test_a_step_in_another_unit(self):
        self.refused({**POWER, "step": {"value": 1, "unit": "1"}}, "'1'", "'permille'")

    def test_a_step_that_is_not_an_object(self):
        self.refused({**POWER, "step": 1})

    def test_a_step_of_zero(self):
        self.refused({**POWER, "step": {"value": 0, "unit": "permille"}}, "positive")

    def test_a_negative_step(self):
        self.refused({**POWER, "step": {"value": -1, "unit": "permille"}}, "positive")

    def test_a_step_that_is_not_a_number(self):
        self.refused({**POWER, "step": {"value": "one", "unit": "permille"}}, "positive")

    def test_a_step_that_is_a_boolean(self):
        self.refused({**POWER, "step": {"value": True, "unit": "permille"}}, "positive")

    def test_a_step_with_no_value(self):
        self.refused({**POWER, "step": {"unit": "permille"}})

    def test_the_refusal_comes_before_the_calibration_is_asked(self):
        record, events, apply = self.applied(
            power_plan(1, "mW"), bindings={"dia_lamp": [{**POWER, "step": None}]})
        self.assertRefusedBeforeAnyCommand(record, events, "step")

    def test_the_step_is_judged_before_a_snapshot_with_two_calibrations_is_refused(self):
        record, events, apply = self.applied(
            power_plan(1, "mW"), bindings={"dia_lamp": [{**POWER, "step": None}]},
            calibrations=[calibration(), calibration()])
        self.assertRefusedBeforeAnyCommand(record, events, "step")
        self.assertNotIn("holds 2 calibrations", record["error"])


class T6TheWrittenValueIsGradedByTheWorseOfTheNumberAndE2(_Convert):
    def test_a_number_at_e1_is_written_at_e2(self):
        record, events, apply = self.writes(1, grade="E1")
        self.assertEqual(apply["written"][0]["grade"], "E2")

    def test_a_number_at_e3_is_written_at_e3(self):
        record, events, apply = self.writes(1, grade="E3")
        self.assertEqual(apply["written"][0]["grade"], "E3")

    def test_a_number_at_e2_is_written_at_e2(self):
        record, events, apply = self.writes(1, grade="E2")
        self.assertEqual(apply["written"][0]["grade"], "E2")

    def test_a_route_that_names_no_calibration_keeps_the_numbers_grade(self):
        record, events, apply = self.applied(power_plan(12.5, "permille", "E1"),
                                             bindings={"dia_lamp": [POWER]})
        self.assertEqual(apply["written"][0]["grade"], "E1")


class T7TheConversionFormIsAppliedAndNothingMoreIsReadFromIt(_Convert):
    def test_the_form_is_read_through_a_calibration_found_by_its_identifiers_only(self):
        record, events, apply = self.writes(1)
        self.assertEqual(apply["written"][0]["calibration"], "mm_calibration_0")

    def test_two_calibrations_are_still_refused_and_none_is_chosen(self):
        record, events, apply = self.applied(
            power_plan(1), bindings={"dia_lamp": [POWER]},
            calibrations=[calibration(), calibration()])
        self.assertRefusedBeforeAnyCommand(record, events, "holds 2 calibrations")

    def test_a_calibration_without_a_form_still_refuses_after_every_gate(self):
        cal = t95.calibration(validity={"lamp_power": {"min": 0, "max": 0.01, "unit": "W"}})
        record, events, apply = self.applied(power_plan(1), bindings={"dia_lamp": [POWER]},
                                             calibrations=[cal])
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "no conversion form")

    def test_the_gates_of_card_095_still_stand_before_the_form(self):
        for name, over, needle in (
                ("grade", {"grade": "E3"}, "E3"),
                ("expiry", {"valid_until": {"date": t95.PAST, "no_event": True}}, "expired"),
                ("event", {"valid_until": {"date": t95.FUTURE, "event": "the lamp is replaced"}},
                 "valid only until an event")):
            with self.subTest(gate=name):
                record, events, apply = self.applied(power_plan(1), bindings={"dia_lamp": [POWER]},
                                                     calibrations=[calibration(**over)])
                self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", needle)

    def test_the_form_is_not_fitted_or_extended(self):
        # a value outside the first and last point is never extrapolated, even by a hair
        record, events, apply = self.writes(5.0001)
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "points")
        wide = {"lamp_power": {"min": -1, "max": 1, "unit": "W"}}
        record, events, apply = self.writes(-0.0001, validity=wide)
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "points")


if __name__ == "__main__":
    unittest.main()
