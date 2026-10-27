"""Card 095: every action parameter of a plan run is a setting, a verb argument or refused.

    python -m unittest tests.test_parameters_classified        (from microscope_runtime/)

`derive_commands` keyed an action's `params` by the plan's number names while a backend writes only
`params.settings`, so every planned command logged verification `none`, and a selector went out as a
`select_<element>` command to a device software may not command. Now each parameter is written into
`settings[label][property]` from a binding in the registry (E1, under the approved configuration's
digest), or is a verb argument listed in code, or refuses the run naming it; a selector on a device
software may not command is a state the plan needs, read and compared and never written. Mock only:
every binding, state, calibration, grade and digest below is a TEST value from `mm_label_registry`.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
REPO = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))

import mm_label_registry as R                                   # noqa: E402
import test_console_signed_approval as t87                      # noqa: E402  (its _Base runs a plan)

op = t87.op
orch = op.orch

EXPOSURE = {"quantity": "exposure_time", "property": "Exposure", "unit": "ms"}
FUTURE = (date.today() + timedelta(days=365)).isoformat()
PAST = (date.today() - timedelta(days=365)).isoformat()


def number(name, value, unit, grade="E5"):
    return {"name": name, "value": value, "unit": unit, "source": "a test", "grade": grade}


def action(aid, device, verb, parameters=()):
    return {"id": aid, "tier": 0, "device": device, "action": verb, "reversible": True,
            "parameters": list(parameters)}


def plan_of(*, actions=(), numbers=(), selectors=(), pid="plan-test-095"):
    plan = {**t87.PLAN_OK, "id": pid, "actions": list(actions),
            "numbers": list(t87.PLAN_OK["numbers"]) + list(numbers)}
    if selectors:
        plan["system_configuration"] = {"selectors": [{"element": e, "value": v} for e, v in selectors]}
    return plan


def schema_validator():
    import jsonschema
    from referencing import Registry, Resource
    resources = {f.name: Resource.from_contents(json.loads(f.read_text(encoding="utf-8")))
                 for f in (REPO / "contracts/schemas").glob("*.json")}
    return jsonschema.Draft202012Validator({"$ref": "run_log.schema.json#/$defs/event"},
                                           registry=Registry().with_resources(resources.items()))


class _Run(t87._Base):
    """A plan run on the mock over a test registry; events are read from the run's events.jsonl."""

    serial = 0

    def go(self, plan, *, digest=R.CONFIG_A, hands=(), **registry):
        type(self).serial += 1
        run_id = f"run-20261027-{950 + type(self).serial:03d}"
        path = R.write(self.tmp.name, **registry)
        patched = mock.patch.object(orch, "REGISTRY_LOOKUP", [path])
        patched.start()
        self.addCleanup(patched.stop)
        runs = Path(self.tmp.name) / "runs"

        def prepare(o):
            if digest is not None:
                o.set_config_digest_by_hand(digest)
            for channel, element, value in hands:
                o.set_element_by_hand(channel, element, value)
        try:
            record = self.run_plan(plan, run_id, runs_root=runs, on_orchestrator=prepare)
        except (op.Refusal, orch.InterlockError, orch.GapError) as exc:
            record = {"ended": "refused", "error": f"{type(exc).__name__}: {exc}"}
        lines = (runs / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()
        return record, [json.loads(line) for line in lines]

    def eventsValidate(self, events):
        try:
            validator = schema_validator()
        except ImportError:
            self.skipTest("jsonschema and referencing are not importable")
        for event in events:
            if event.get("event") in ("run_started", "run_ended"):   # the stream's header and footer
                continue
            errors = [e.message for e in validator.iter_errors(event)]
            self.assertEqual(errors, [], f"{event.get('event')}: {errors}: {event}")

    @staticmethod
    def named(events, name):
        return [e for e in events if e.get("event") == name]

    def assertRefusedBeforeAnyCommand(self, record, events, *needles):
        self.assertEqual(record["ended"], "refused", record)
        self.assertEqual(self.named(events, "apply"), [], "a command went out before the refusal")
        text = json.dumps(record) + json.dumps(events)
        for needle in needles:
            self.assertIn(needle, text)


def exposure_plan(value=0.1, unit="s", grade="E5"):
    return plan_of(actions=[action("a_red", "camera_red", "acquire", ["exposure_time"])],
                   numbers=[number("exposure_time", value, unit, grade)])


class T1AParameterThatIsNeitherBoundNorAVerbArgumentRefusesTheRun(_Run):
    def test_the_run_is_refused_naming_the_parameter_and_nothing_goes_out(self):
        record, events = self.go(exposure_plan())
        self.assertRefusedBeforeAnyCommand(record, events, "exposure_time")
        derivation = self.named(events, "derivation")[0]["derivation"]
        row = derivation["parameters"][0]
        self.assertEqual((row["name"], row["class"], row["from"]),
                         ("exposure_time", "refused", "numbers[exposure_time]"))
        self.assertIn("no binding", row["why"])

    def test_every_unbound_parameter_is_listed_and_none_is_dropped(self):
        plan = plan_of(actions=[action("a_red", "camera_red", "acquire", ["exposure_time", "gain"])],
                       numbers=[number("exposure_time", 0.1, "s"), number("gain", 2, "1")])
        record, events = self.go(plan)
        rows = self.named(events, "derivation")[0]["derivation"]["parameters"]
        self.assertEqual([(r["name"], r["class"]) for r in rows],
                         [("exposure_time", "refused"), ("gain", "refused")])
        self.assertRefusedBeforeAnyCommand(record, events, "exposure_time", "gain")

    def test_the_derivation_event_validates_against_the_run_log_schema(self):
        record, events = self.go(exposure_plan())
        self.assertEqual(len(self.named(events, "derivation")), 1)
        self.eventsValidate(events)


class T2ASettingIsWrittenThroughItsBindingAndRead(_Run):
    def test_exposure_time_in_seconds_is_written_in_milliseconds_and_read_back(self):
        record, events = self.go(exposure_plan(0.1, "s"), bindings={"camera_red": [EXPOSURE]})
        self.assertEqual(record["ended"], "completed")
        apply = [e for e in self.named(events, "apply") if e["action"] == "acquire"][0]
        self.assertEqual(apply["settings_sent"], {"Kinetix_red": {"Exposure": 100}})
        self.assertEqual(apply["verification"], "readback")
        written = apply["written"][0]
        self.assertEqual((written["plan_value"], written["plan_unit"], written["from"]),
                         (0.1, "s", "numbers[exposure_time]"))
        self.assertEqual((written["written"], written["unit"]), (100, "ms"))
        self.assertIn("mm_binding_camera_red_exposure_time", written["binding"])
        self.assertEqual(apply["params"]["exposure_time"]["from"], "numbers[exposure_time]")
        self.eventsValidate(events)

    def test_the_derivation_names_the_class_and_the_binding(self):
        record, events = self.go(exposure_plan(), bindings={"camera_red": [EXPOSURE]})
        derivation = self.named(events, "derivation")[0]["derivation"]
        row = derivation["parameters"][0]
        self.assertEqual((row["class"], row["action"]), ("setting", "actions[a_red]"))
        self.assertIn("mm_binding_camera_red_exposure_time", row["binding"])
        self.assertEqual(derivation["plan_hash"], op._contracts_validate().plan_hash(exposure_plan()))

    def test_a_unit_that_already_matches_is_written_unchanged(self):
        record, events = self.go(exposure_plan(100, "ms"), bindings={"camera_red": [EXPOSURE]})
        apply = [e for e in self.named(events, "apply") if e["action"] == "acquire"][0]
        self.assertEqual(apply["settings_sent"], {"Kinetix_red": {"Exposure": 100}})
        self.assertIsNone(apply["written"][0]["calibration"])

    def test_the_written_value_carries_the_number_s_grade(self):
        record, events = self.go(exposure_plan(0.1, "s", "E4"), bindings={"camera_red": [EXPOSURE]})
        apply = [e for e in self.named(events, "apply") if e["action"] == "acquire"][0]
        self.assertEqual(apply["written"][0]["grade"], "E4")

    def test_the_software_motion_check_judges_the_written_label_and_property(self):
        record, events = self.go(exposure_plan(), bindings={"camera_red": [EXPOSURE]})
        checked = self.named(events, "software_motion_checked")[0]
        self.assertIn("Kinetix_red", json.dumps(checked))
        o = op.orch.Orchestrator(registry_path=R.write(self.tmp.name, filename="x.json"), backend="mock")
        o.set_config_digest_by_hand(R.CONFIG_A)
        command = orch.Command(channel="camera_red", action="acquire", params={},
                               from_field="actions[a_red]",
                               settings={"DiaLamp": {"Intensity": 5, "Colour": 3}})
        with self.assertRaises(orch.InterlockError) as caught:
            o.check_software_motion([command])
        self.assertIn("Colour", str(caught.exception))


class T3ABindingCommandsOnlyAtE1UnderTheApprovedDigest(_Run):
    def test_a_binding_graded_e3_refuses_naming_the_binding_and_the_grade(self):
        binding = {**EXPOSURE, "grade": "E3"}
        record, events = self.go(exposure_plan(), bindings={"camera_red": [binding]})
        self.assertRefusedBeforeAnyCommand(record, events, "mm_binding_camera_red_exposure_time", "E3")

    def test_every_grade_below_e1_refuses(self):
        for grade in ("E2", "E3", "E4", "E5"):
            with self.subTest(grade=grade):
                record, events = self.go(exposure_plan(),
                                         bindings={"camera_red": [{**EXPOSURE, "grade": grade}]})
                self.assertRefusedBeforeAnyCommand(record, events, f"graded {grade}")

    def test_a_binding_read_under_another_configuration_refuses_naming_both_digests(self):
        binding = {**EXPOSURE, "digest": R.CONFIG_B}
        record, events = self.go(exposure_plan(), bindings={"camera_red": [binding]})
        self.assertRefusedBeforeAnyCommand(record, events, R.CONFIG_B, R.CONFIG_A)

    def test_a_binding_naming_no_digest_refuses(self):
        binding = {**EXPOSURE, "digest": None}
        record, events = self.go(exposure_plan(), bindings={"camera_red": [binding]})
        self.assertRefusedBeforeAnyCommand(record, events, "mm_config_sha256")

    def test_a_run_with_no_loaded_configuration_refuses(self):
        record, events = self.go(exposure_plan(), digest=None, bindings={"camera_red": [EXPOSURE]})
        self.assertRefusedBeforeAnyCommand(record, events, "no approved configuration")
        row = self.named(events, "derivation")[0]["derivation"]["parameters"][0]
        self.assertEqual(row["class"], "refused")

    def test_a_binding_whose_entry_names_another_property_refuses(self):
        binding = {**EXPOSURE, "label": "Kinetix_blue"}
        record, events = self.go(exposure_plan(), bindings={"camera_red": [binding]})
        self.assertRefusedBeforeAnyCommand(record, events, "mm_label")


POWER = {"quantity": "lamp_power", "property": "Intensity", "unit": "1"}


def power_plan(value=5):
    return plan_of(actions=[action("a_lamp", "dia_lamp", "set_power", ["lamp_power"])],
                   numbers=[number("lamp_power", value, "W")])


def calibration(**over):
    return {"label": "DiaLamp", "property": "Intensity", "quantity": "lamp_power",
            "valid_until": {"date": FUTURE, "no_event": True},
            "validity": {"lamp_power": {"min": 1, "max": 10, "unit": "W"}}, **over}


class T4APhysicalQuantityIntoAControlValueNeedsACalibration(_Run):
    def test_no_calibration_refuses_naming_what_was_needed(self):
        record, events = self.go(power_plan(), bindings={"dia_lamp": [POWER]})
        self.assertRefusedBeforeAnyCommand(record, events, "calibration", "lamp_power")

    def test_an_expired_calibration_refuses_naming_it(self):
        cal = calibration(valid_until={"date": PAST, "no_event": True})
        record, events = self.go(power_plan(), bindings={"dia_lamp": [POWER]}, calibrations=[cal])
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "expired")

    def test_a_range_that_misses_the_value_refuses_naming_the_calibration(self):
        record, events = self.go(power_plan(50), bindings={"dia_lamp": [POWER]},
                                 calibrations=[calibration()])
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "does not cover")

    def test_a_calibration_graded_below_e2_refuses(self):
        record, events = self.go(power_plan(), bindings={"dia_lamp": [POWER]},
                                 calibrations=[calibration(grade="E3")])
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "E3")

    def test_a_calibration_valid_until_an_event_refuses_because_ambiguity_stops(self):
        cal = calibration(valid_until={"date": FUTURE, "event": "the lamp is replaced"})
        record, events = self.go(power_plan(), bindings={"dia_lamp": [POWER]}, calibrations=[cal])
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0",
                                           "valid only until an event")

    def test_a_calibration_that_passes_every_gate_still_carries_no_conversion_form(self):
        record, events = self.go(power_plan(), bindings={"dia_lamp": [POWER]},
                                 calibrations=[calibration()])
        self.assertRefusedBeforeAnyCommand(record, events, "mm_calibration_0", "no conversion form")

    def test_two_calibrations_for_one_quantity_are_refused_and_none_is_chosen(self):
        record, events = self.go(power_plan(), bindings={"dia_lamp": [POWER]},
                                 calibrations=[calibration(), calibration()])
        self.assertRefusedBeforeAnyCommand(record, events, "holds 2 calibrations")

    def test_no_formula_lives_in_the_runtime(self):
        text = (SRC / "orchestrator.py").read_text(encoding="utf-8")
        self.assertIn("contracts\" / \"units.json", text)


def series_plan(frames=12, verb="acquire_series"):
    return plan_of(actions=[action("a_red", "camera_red", verb, ["frame_count"])],
                   numbers=[number("frame_count", frames, "count", "E2")])


class T5AFrameCountIsCheckedAgainstTheFramesReturned(_Run):
    def drop_one(self, repeat_first=False):
        original = orch.Orchestrator.acquire_sequence

        def short(o, channel_id, count, on_frame, *a, **k):
            got = original(o, channel_id, count, on_frame, *a, **k)
            numbers = list(got["image_numbers"])[:-1]
            return {**got, "image_numbers": numbers + ([numbers[0]] if repeat_first else [])}
        patched = mock.patch.object(orch.Orchestrator, "acquire_sequence", short)
        patched.start()
        self.addCleanup(patched.stop)

    def test_it_is_a_verb_argument_naming_what_it_is_verified_against(self):
        record, events = self.go(series_plan())
        row = self.named(events, "derivation")[0]["derivation"]["parameters"][0]
        self.assertEqual((row["name"], row["class"]), ("frame_count", "verb_argument"))
        self.assertIn("image number", row["verification"])
        self.assertEqual(self.named(events, "frame_count_verified")[0]["counted"], 12)
        self.assertEqual(self.named(events, "frame_count_disagreed"), [])

    def test_599_frames_for_600_is_a_logged_disagreement_and_not_a_refusal(self):
        self.drop_one()
        record, events = self.go(series_plan(600))
        self.assertEqual(record["ended"], "completed")
        said = self.named(events, "frame_count_disagreed")[0]
        self.assertEqual((said["wanted"], said["counted"]), (600, 599))
        self.assertEqual(said["plan_field"], "actions[a_red]")
        self.eventsValidate(events)

    def test_a_frame_delivered_twice_counts_once(self):
        self.drop_one(repeat_first=True)                     # twelve numbers came back, eleven of them different
        record, events = self.go(series_plan(12))
        said = self.named(events, "frame_count_disagreed")[0]
        self.assertEqual((said["wanted"], said["counted"]), (12, 11))

    def test_a_sequence_that_returns_no_image_numbers_is_a_disagreement_too(self):
        original = orch.Orchestrator.acquire_sequence
        patched = mock.patch.object(orch.Orchestrator, "acquire_sequence",
                                    lambda o, *a, **k: {**original(o, *a, **k), "image_numbers": None})
        patched.start()
        self.addCleanup(patched.stop)
        record, events = self.go(series_plan(12))
        said = self.named(events, "frame_count_disagreed")[0]
        self.assertIsNone(said["counted"])

    def test_frame_count_on_another_verb_is_refused(self):
        record, events = self.go(series_plan(12, "acquire"))
        self.assertRefusedBeforeAnyCommand(record, events, "frame_count", "acquire_series only")

    def test_a_frame_count_that_is_not_a_whole_number_is_refused(self):
        for bad in (0, -3, 2.5):
            with self.subTest(bad=bad):
                record, events = self.go(series_plan(bad))
                self.assertRefusedBeforeAnyCommand(record, events, "frame_count")

    def test_frame_count_is_never_a_binding(self):
        item = {"quantity": "frame_count", "property": "Frames", "unit": "count"}
        with self.assertRaises(orch.GapError):
            orch.Orchestrator(registry_path=R.write(self.tmp.name, bindings={"camera_red": [item]}),
                              backend="mock")


PORT_STATE = {"word": "empty", "state_label": "Empty"}


def port_plan(value="empty"):
    return plan_of(selectors=[("csuw1_port", value)])


PORT = dict(labels={"csuw1_port": "CSUW1-Port"}, states={"csuw1_port": [PORT_STATE]})


class T6ASelectorOnADeviceSoftwareMayNotCommandIsARequiredState(_Run):
    def test_a_matching_read_proceeds_and_nothing_is_written_to_that_device(self):
        record, events = self.go(port_plan(), hands=[("confocal_csuw1", "csuw1_port", "Empty")], **PORT)
        self.assertEqual(record["ended"], "completed")
        checked = self.named(events, "required_states_checked")[0]["states"][0]
        self.assertEqual((checked["element"], checked["state"], checked["read"], checked["matched"]),
                         ("csuw1_port", "Empty", "Empty", True))
        self.assertEqual(self.named(events, "apply"), [])
        self.assertEqual([e for e in self.named(events, "dispatch")
                          if "csuw1" in json.dumps(e)], [])
        derivation = self.named(events, "derivation")[0]["derivation"]
        self.assertEqual(derivation["selectors"],
                         [{"element": "csuw1_port", "from": "system_configuration.selectors[csuw1_port]",
                           "class": "required_state", "state": "Empty"}])
        self.eventsValidate(events)

    def test_a_mismatch_refuses_naming_the_element(self):
        record, events = self.go(port_plan(), hands=[("confocal_csuw1", "csuw1_port", "Other")], **PORT)
        self.assertRefusedBeforeAnyCommand(record, events, "csuw1_port", "Other", "Empty")
        self.assertFalse(self.named(events, "required_states_refused")[0]["states"][0]["matched"])

    def test_an_element_that_was_not_read_refuses_naming_it(self):
        record, events = self.go(port_plan(), **PORT)
        self.assertRefusedBeforeAnyCommand(record, events, "csuw1_port", "was not read")

    def test_a_value_the_registry_cannot_resolve_refuses_naming_the_element(self):
        record, events = self.go(port_plan("full"), hands=[("confocal_csuw1", "csuw1_port", "Empty")],
                                 **PORT)
        self.assertRefusedBeforeAnyCommand(record, events, "csuw1_port", "'full'")

    def test_a_state_graded_below_e1_resolves_nothing(self):
        states = {"csuw1_port": [{**PORT_STATE, "grade": "E3"}]}
        record, events = self.go(port_plan(), hands=[("confocal_csuw1", "csuw1_port", "Empty")],
                                 labels=PORT["labels"], states=states)
        self.assertRefusedBeforeAnyCommand(record, events, "E3")

    def test_a_state_whose_entry_names_another_label_resolves_nothing(self):
        states = {"csuw1_port": [{**PORT_STATE, "label": "CSUW1-Shutter"}]}
        record, events = self.go(port_plan(), hands=[("confocal_csuw1", "csuw1_port", "Empty")],
                                 labels=PORT["labels"], states=states)
        self.assertRefusedBeforeAnyCommand(record, events, "mm_label")

    def test_a_state_read_under_another_configuration_resolves_nothing(self):
        states = {"csuw1_port": [{**PORT_STATE, "digest": R.CONFIG_B}]}
        record, events = self.go(port_plan(), hands=[("confocal_csuw1", "csuw1_port", "Empty")],
                                 labels=PORT["labels"], states=states)
        self.assertRefusedBeforeAnyCommand(record, events, R.CONFIG_B)

    def test_the_required_state_is_read_after_preflight_and_before_the_first_action(self):
        plan = plan_of(selectors=[("csuw1_port", "empty")],
                       actions=[action("a_red", "camera_red", "acquire")])
        record, events = self.go(plan, hands=[("confocal_csuw1", "csuw1_port", "Empty")], **PORT)
        names = [e["event"] for e in events]
        self.assertLess(names.index("preflight"), names.index("required_states_checked"))
        self.assertLess(names.index("required_states_checked"), names.index("apply"))


MODE = {"quantity": "camera_red", "property": "Mode", "unit": "1"}
MODE_STATE = {"word": "DynamicRange", "state_label": "Dynamic Range"}


class T7TheRedCameraSModeSelectorIsASettingThroughItsBinding(_Run):
    def test_it_goes_out_as_a_setting_and_is_read_back(self):
        plan = plan_of(selectors=[("camera_red", "DynamicRange")])
        record, events = self.go(plan, bindings={"camera_red": [MODE]},
                                 states={"camera_red": [MODE_STATE]})
        self.assertEqual(record["ended"], "completed")
        apply = self.named(events, "apply")[0]
        self.assertEqual(apply["settings_sent"], {"Kinetix_red": {"Mode": "Dynamic Range"}})
        self.assertEqual(apply["verification"], "readback")
        derivation = self.named(events, "derivation")[0]["derivation"]
        self.assertEqual(derivation["selectors"][0]["class"], "setting")
        self.assertIn("mm_binding_camera_red_camera_red", derivation["selectors"][0]["binding"])
        self.eventsValidate(events)

    def test_without_a_binding_it_refuses_and_is_not_written(self):
        plan = plan_of(selectors=[("camera_red", "DynamicRange")])
        record, events = self.go(plan, states={"camera_red": [MODE_STATE]})
        self.assertRefusedBeforeAnyCommand(record, events, "camera_red", "binding")


class T8NumbersNothingUsesAreListedAndNotRefused(_Run):
    NAMES = ("illumination_line_intensity_permille", "record_length", "brightness_window",
             "bleach_window")

    def test_the_four_numbers_of_the_first_question_are_listed_and_the_run_goes_on(self):
        plan = plan_of(numbers=[number("illumination_line_intensity_permille", 100, "permille"),
                                number("record_length", 60, "s"), number("brightness_window", 6, "s"),
                                number("bleach_window", 60, "s")])
        record, events = self.go(plan)
        self.assertEqual(record["ended"], "completed")
        listed = self.named(events, "derivation")[0]["derivation"]["unused_numbers"]
        self.assertEqual([u["name"] for u in listed], list(self.NAMES))
        self.assertEqual(listed[0], {"name": self.NAMES[0], "value": 100, "unit": "permille",
                                     "from": "numbers[1]"})
        self.assertEqual(listed, op._contracts_validate().unused_numbers(plan))
        self.eventsValidate(events)

    def test_the_real_plan_s_unused_list_holds_them_by_the_validator_s_own_rule(self):
        path = REPO / "microscope_agent/questions/mic-20260920-001/plan_microscope_mic-20260920-001.json"
        if not path.exists():
            self.skipTest("the first question's plan is not in this working copy")
        plan = json.loads(path.read_text(encoding="utf-8"))
        listed = [u["name"] for u in op._contracts_validate().unused_numbers(plan)]
        for name in self.NAMES:
            self.assertIn(name, listed)


class T9OperationAndTrapStepPlansAreNotRead(_Run):
    def test_classify_leaves_an_operation_plan_alone(self):
        o = orch.Orchestrator(backend="mock")
        commands = [orch.Command(channel="piezo_stage", action="move", params={}, from_field="operation")]
        kept, required = op.classify_parameters(o, {"operation": {}}, commands)
        self.assertEqual((kept, required), (commands, []))
        self.assertEqual([e for e in o.log if e.get("event") == "derivation"], [])


class T10TheValidatorIsLoadedOncePerFileVersion(unittest.TestCase):
    """Loading validate.py takes close to a second. A run asks for it at its approval and again at
    its derivation; a second load falls between the watcher's start and the run's first step and
    gives the watcher a tick no earlier run had (test_watcher_in_run failed on it)."""

    def test_two_asks_get_the_same_module_and_a_changed_file_gets_a_new_one(self):
        first, second = op._contracts_validate(), op._contracts_validate()
        self.assertIs(first, second)
        saved = dict(op._VALIDATE_CACHE)
        self.addCleanup(lambda: [op._VALIDATE_CACHE.clear(), op._VALIDATE_CACHE.update(saved)])
        op._VALIDATE_CACHE["key"] = (0, 0)               # as if the file had changed since
        self.assertIsNot(op._contracts_validate(), first)


if __name__ == "__main__":
    unittest.main()
