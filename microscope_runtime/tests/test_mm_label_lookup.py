"""Card 091: the software-motion check finds each registry name's Micro-Manager label in the registry.

    python -m unittest tests.test_mm_label_lookup        (from microscope_runtime/)

A registry name (`camera_red`, `dia_lamp`) is a name and never a label. The check asks the registry
which label a name carries (`mm_label` on its row, citing one entry of the same snapshot), and a label
commands a device only when that entry is graded E1 AND names the configuration this run loaded
(plan.md 15.1 item 9). The policy stays the allow-list's: the lookup says which device a name is, never
whether it may move. Mock only; every label, grade and digest below is a TEST value from
`mm_label_registry`, never a fact about the instrument.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
REPO = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))

import mm_label_registry as R                                   # noqa: E402
import test_console_signed_approval as t87                      # noqa: E402  (its _Base runs a plan)
import test_mm_config_in_run as t69                             # noqa: E402  (its _Base loads a file)

op = t87.op
orch = op.orch
REAL_SOURCE = "microscope_agent/envelope/snapshot.json"


def red(action="acquire"):
    return orch.Command(channel="camera_red", action=action, params={}, from_field="actions[a_red]")


def lamp():
    return orch.Command(channel="stand_ti2e", element="dia_lamp", action="set_lamp",
                        params={"settings": {"DiaLamp": {"State": 1}}}, from_field="actions[a_lamp]")


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def build(self, digest=R.CONFIG_A, **registry) -> "orch.Orchestrator":
        """An orchestrator on a test registry; `digest` is the configuration the mock stands for."""
        path = R.write(self.tmp.name, **registry)
        o = orch.Orchestrator(registry_path=path, backend="mock")
        o.registry_path_for_test = path
        if digest is not None:
            o.set_config_digest_by_hand(digest)
        return o

    def mm(self, o):
        return o._device_module("micromanager", needed_by="test")

    def events(self, o, name):
        return [e for e in o.log if e.get("event") == name]

    def refused(self, o, commands) -> str:
        with self.assertRaises(orch.InterlockError) as ctx:
            o.dispatch(commands, plan=None)
        self.assertEqual(self.events(o, "apply"), [], "a command went out before the refusal")
        return str(ctx.exception)


class T1ARegistryNameIsFoundInTheRegistry(_Base):
    def test_a_plan_on_the_two_labelled_names_passes_the_check_and_dispatches(self):
        o = self.build()
        out = o.dispatch([red(), lamp()], plan=None)
        results = {cid: rows for batch in out for cid, rows in batch["results"].items()}
        self.assertTrue(all(r["ok"] for rows in results.values() for r in rows), results)
        self.assertEqual(sorted(results), ["camera_red", "stand_ti2e"])
        self.assertEqual(len(self.events(o, "software_motion_checked")), 1)
        self.assertEqual(self.events(o, "software_motion_refused"), [])

    def test_the_same_plan_without_the_lookup_is_refused(self):
        # the real registry carries no label yet, and that is the "without" the card asks for
        o = orch.Orchestrator(backend="mock")
        text = self.refused(o, [red(), lamp()])
        self.assertIn("'camera_red' has no Micro-Manager label", text)
        self.assertIn("'dia_lamp' has no Micro-Manager label", text)
        self.assertIn("2 refusal(s)", text)

    def test_the_container_of_a_labelled_element_needs_no_label_of_its_own(self):
        o = self.build()
        self.assertNotIn("stand_ti2e", o.mm_labels)
        o.check_software_motion([lamp()])

    def test_a_label_found_in_the_registry_is_the_one_the_check_judges(self):
        o = self.build(labels={"camera_red": "Aura"})                # a test's own label for the name
        o.check_software_motion([red()])
        self.assertEqual(self.events(o, "software_motion_checked")[0]["resolved"][0]["label"], "Aura")


class T2ANameWithNoLabelIsRefusedBeforeAnyCommand(_Base):
    def test_the_refusal_names_the_name_the_missing_label_and_the_registry_file(self):
        o = self.build(labels={"camera_red": None})
        text = self.refused(o, [red(), lamp()])
        self.assertIn("'camera_red' has no Micro-Manager label in the registry", text)
        self.assertIn(Path(o.registry_path_for_test).as_posix(), text)
        self.assertNotIn("dia_lamp", text)                          # the labelled one is not refused
        self.assertEqual(len(self.events(o, "software_motion_refused")), 1)

    def test_every_refusal_is_collected_and_the_whole_plan_is_refused(self):
        o = self.build(labels={"camera_red": None, "dia_lamp": None})
        text = self.refused(o, [red(), lamp()])
        self.assertIn("2 refusal(s)", text)
        self.assertIn("actions[a_red]", text)
        self.assertIn("actions[a_lamp]", text)

    def test_a_row_whose_entry_the_file_does_not_carry_refuses_naming_the_grade_it_lacks(self):
        o = self.build(drop_entries=("mm_label_camera_red",))
        text = self.refused(o, [red()])
        self.assertIn("mm_label_camera_red", text)
        self.assertIn("unknown", text)
        self.assertIn("carries no entry", text)


class T3ALabelWrittenDirectlyIsRefusedAsToday(_Base):
    def test_a_plan_on_zdrive_is_refused_with_the_allow_lists_own_text(self):
        for o in (self.build(), orch.Orchestrator(backend="mock")):  # the same text with or without labels
            mm = self.mm(o)
            why = mm.refusal("ZDrive", None, "setProperty")
            self.assertTrue(why)
            as_channel = orch.Command(channel="ZDrive", action="set", params={}, from_field="actions[a1]")
            self.assertIn(why, self.refused(o, [as_channel]))
            as_setting = orch.Command(channel="confocal_csuw1", action="set", from_field="actions[a2]",
                                      params={"settings": {"ZDrive": {"State": 1}}})
            text = self.refused(o, [as_setting])
            self.assertIn(mm.refusal("ZDrive", "State", "setProperty", 1), text)

    def test_the_text_is_the_same_under_a_labelled_registry_and_the_real_one(self):
        texts = []
        for o in (self.build(), orch.Orchestrator(backend="mock")):
            texts.append(self.refused(o, [orch.Command(channel="ZDrive", action="set", params={},
                                                       from_field="actions[a1]")]))
        self.assertEqual(texts[0], texts[1])

    def test_every_named_refusal_written_directly_is_refused_whole(self):
        o = self.build()
        mm = self.mm(o)
        for device in mm.NAMED_REFUSALS:
            command = orch.Command(channel="confocal_csuw1", action="set", from_field="actions[a1]",
                                   params={"settings": {device: {"State": 1}}})
            self.assertIn(mm.refusal(device, "State", "setProperty", 1), self.refused(o, [command]), device)


class T4ALabelOfARefusedDeviceIsRefusedWithThatDevicesRefusal(_Base):
    def test_a_name_whose_label_is_zdrive_or_a_named_refusal_is_refused_with_its_text(self):
        mm = self.mm(self.build())
        for device in ["ZDrive", *mm.NAMED_REFUSALS]:
            with self.subTest(device=device):
                o = self.build(labels={"camera_red": device})
                why = self.mm(o).refusal(device, None, "setProperty")
                self.assertTrue(why)
                text = self.refused(o, [red()])
                self.assertIn(why, text)
                self.assertIn(f"is the label {device!r}", text)

    def test_the_lookup_opens_nothing_the_allow_list_closes(self):
        o = self.build(labels={"camera_blue": "Kinetix_blue"})      # a device not on the allow-list
        blue = orch.Command(channel="camera_blue", action="acquire", params={}, from_field="actions[a_blue]")
        self.assertIn("is not a device software may command today", self.refused(o, [blue]))


class T5TheRealRegistryGivesTheAuraNoLabel(_Base):
    def test_a_plan_on_widefield_source_a_is_refused_naming_the_missing_label(self):
        o = orch.Orchestrator(backend="mock")
        aura = orch.Command(channel="widefield_source_a", action="set", from_field="actions[a_aura]",
                            params={"settings": {"Aura": {"State": 1}}})
        text = self.refused(o, [aura])
        self.assertIn("'widefield_source_a' has no Micro-Manager label in the registry", text)
        self.assertIn(REAL_SOURCE, text)

    def test_a_test_registry_that_gives_it_one_is_the_tests_own(self):
        o = self.build(labels={"widefield_source_a": "Aura"})
        aura = orch.Command(channel="widefield_source_a", action="set", from_field="actions[a_aura]",
                            params={"settings": {"Aura": {"State": 1}}})
        o.check_software_motion([aura])


class T6NothingUnderSrcHoldsALabelForARegistryName(unittest.TestCase):
    """The labels are the allow-list's and the registry's, and no other file writes one.

    Card 091 asks for none outside micromanager.py and the LIGHT_SOURCES abort pairing. Today the
    tree holds the places below that the card did not name, each a string literal equal to one of the
    allow-list's keys. They are PINNED here, file by file, so none is added and each can be removed by
    the card that owns it; the orchestrator, where the lookup is, holds none outside LIGHT_SOURCES.
    """

    #: file -> {key: number of string literals equal to it}; never raised without a card that says why
    PINNED = {
        "devices/mock.py": {"Kinetix_red": 1},
        "live_view.py": {"Kinetix_red": 1},
        "live_view_20260925.py": {"DiaLamp": 2, "Aura": 1},
        "operator.py": {"Kinetix_red": 9, "DiaLamp": 6},
        "record_20260925.py": {"DiaLamp": 1, "Aura": 1},
        "session_033.py": {"Aura": 1, "Kinetix_red": 1, "Core": 2},
        "session_036_blink.py": {"DiaLamp": 2, "Core": 2},
        "session_036_laser.py": {"Kinetix_red": 1, "Core": 1, "Aura": 1, "DiaLamp": 1},
        "session_036_readonly.py": {"DiaLamp": 1, "Aura": 1, "Core": 1},
        "session_038.py": {"Core": 1},
        "shutdown_20260925.py": {"Aura": 2, "DiaLamp": 1},
    }

    def keys(self):
        mm = orch.Orchestrator(backend="mock")._device_module("micromanager", needed_by="test")
        return set(mm.SOFTWARE_MAY_COMMAND)

    def literals(self, path: Path, keys: set, lines: range | None = None) -> dict:
        found: dict = {}
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in keys
                    and (lines is None or node.lineno not in lines)):
                found[node.value] = found.get(node.value, 0) + 1
        return found

    def test_the_orchestrator_holds_none_outside_the_light_sources_table(self):
        path = SRC / "orchestrator.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        table = next(n for n in tree.body if isinstance(n, ast.AnnAssign)
                     and getattr(n.target, "id", "") == "LIGHT_SOURCES")
        inside = range(table.lineno, table.end_lineno + 1)
        self.assertEqual(self.literals(path, self.keys(), lines=inside), {})
        self.assertGreater(len(self.literals(path, self.keys())), 0)   # the pairing is still there to exclude

    def test_no_file_outside_the_pinned_ones_holds_one_and_no_pinned_file_holds_more(self):
        keys = self.keys()
        seen = {}
        for path in sorted(SRC.rglob("*.py")):
            rel = path.relative_to(SRC).as_posix()
            if rel in ("devices/micromanager.py", "orchestrator.py"):
                continue
            found = self.literals(path, keys)
            if found:
                seen[rel] = found
        self.assertEqual(sorted(seen), sorted(self.PINNED), "a file gained or lost its labels")
        for rel, found in seen.items():
            for key, count in found.items():
                self.assertLessEqual(count, self.PINNED[rel].get(key, 0), f"{rel} gained a {key!r} literal")


class T8TheRegistrySourceIsWrittenWithForwardSlashes(_Base):
    def test_the_real_registry_is_named_repo_relative_with_no_backslash(self):
        o = orch.Orchestrator(backend="mock")
        self.assertEqual(o.registry_source, REAL_SOURCE)
        self.assertNotIn("\\", o.registry_source)

    def test_the_source_a_missing_label_refusal_names_has_no_backslash(self):
        o = orch.Orchestrator(backend="mock")
        text = self.refused(o, [red()])
        self.assertIn(f"({REAL_SOURCE})", text)
        self.assertNotIn("\\", text.split("(")[1].split(")")[0])

    def test_load_registry_gives_the_same_posix_source(self):
        self.assertEqual(orch.load_registry()[1], REAL_SOURCE)


class T8bARunRecordCarriesTheSameSource(t87._Base):
    def test_the_run_record_and_log_say_registry_source_with_forward_slashes(self):
        record = self.run_plan(t87.PLAN_OK, "run-20261027-911")
        self.assertEqual(record["registry_source"], REAL_SOURCE)
        self.assertNotIn("\\", record["registry_source"])


class T9TheTapNamesTheMissingLabel(_Base):
    def rig(self, **registry):
        o = self.build(**registry)
        o.begin_run(Path(self.tmp.name) / "run-20261027-001", run_id="run-20261027-001", plan_id="p",
                    revision=1, tap_cameras=[c for c in [o.camera_label("camera_red"),
                                                         o.camera_label("camera_blue")] if c])
        self.addCleanup(lambda: o.stop_channel_address() is not None and o.end_run("completed"))
        return o

    def test_the_label_removed_from_one_row_leaves_that_camera_with_no_frame_and_names_it(self):
        from test_frame_tap_per_camera import ask                   # the one socket client the tap tests use
        o = self.rig(labels={"camera_blue": None})
        o.acquire_snap("camera_red")
        o.acquire_snap("camera_blue")
        head, body = ask(o.frame_tap_address(), {"get": "latest_frame", "camera": "Kinetix_blue"})
        self.assertEqual((head["frame"], body), (False, b""))
        self.assertIn("camera_blue", head["note"])
        self.assertIn("no Micro-Manager label", head["note"])
        head, body = ask(o.frame_tap_address(), {"get": "latest_frame", "camera": "Kinetix_red"})
        self.assertTrue(head["frame"])
        self.assertEqual(len(self.events(o, "frame_tap_unlabelled")), 1)   # said once, not once per frame
        self.assertEqual(self.events(o, "frame_tap_unlabelled")[0]["channel"], "camera_blue")

    def test_the_bare_request_with_no_labelled_camera_names_the_missing_labels(self):
        from test_frame_tap_per_camera import ask
        o = self.rig(labels={"camera_red": None, "camera_blue": None})
        o.acquire_snap("camera_red")
        head, body = ask(o.frame_tap_address(), {"get": "latest_frame"})
        self.assertEqual((head["frame"], body), (False, b""))
        self.assertIn("camera_red", head["note"])
        self.assertIn("no Micro-Manager label", head["note"])

    def test_a_plan_names_a_camera_by_its_channel_and_the_tap_lists_its_label(self):
        o = self.build()
        plan = {"actions": [{"id": "a", "device": "camera_red", "action": "acquire"},
                            {"id": "b", "device": "camera_blue", "action": "acquire_series"}]}
        self.assertEqual(op.derive_tap_cameras(plan, o), ["Kinetix_red", "Kinetix_blue"])
        o = self.build(labels={"camera_blue": None})
        self.assertEqual(op.derive_tap_cameras(plan, o), ["Kinetix_red"])


class T10WhatWasResolvedIsInTheRunsEvents(_Base):
    def test_each_resolved_names_entry_grade_and_digest_are_in_the_checked_event_with_the_loaded_one(self):
        o = self.build()
        o.check_software_motion([red(), lamp()])
        event = self.events(o, "software_motion_checked")[0]
        self.assertEqual(event["loaded_config_sha256"], R.CONFIG_A)
        rows = {r["name"]: r for r in event["resolved"]}
        self.assertEqual(sorted(rows), ["camera_red", "dia_lamp"])
        for name, label in (("camera_red", "Kinetix_red"), ("dia_lamp", "DiaLamp")):
            self.assertEqual(rows[name]["label"], label)
            self.assertEqual(rows[name]["entry_ref"], R.entry_ref(name))
            self.assertEqual(rows[name]["grade"], "E1")
            self.assertEqual(rows[name]["config_sha256"], R.CONFIG_A)
            self.assertEqual(rows[name]["loaded_config_sha256"], R.CONFIG_A)

    def test_a_refused_check_keeps_the_same_facts(self):
        o = self.build(grade={"camera_red": "E3"})
        self.refused(o, [red()])
        event = self.events(o, "software_motion_refused")[0]
        self.assertEqual(event["resolved"][0]["grade"], "E3")
        self.assertEqual(event["resolved"][0]["entry_ref"], "mm_label_camera_red")
        self.assertEqual(event["loaded_config_sha256"], R.CONFIG_A)

    def test_a_run_writes_them_into_events_jsonl_and_the_digest_set_by_hand_is_an_event_too(self):
        class Run(t87._Base):
            def runTest(self):                                      # never collected, built by hand below
                pass
        base = Run()
        base.setUp()
        self.addCleanup(base.doCleanups)
        registry = R.write(self.tmp.name)
        patched = mock.patch.object(orch, "REGISTRY_LOOKUP", [registry])
        patched.start()
        self.addCleanup(patched.stop)
        plan = {**t87.PLAN_OK, "id": "plan-test-091-run",
                "actions": [{"id": "a_red", "tier": 0, "device": "camera_red", "action": "acquire",
                             "reversible": True}]}
        runs = Path(self.tmp.name) / "runs"
        base.run_plan(plan, "run-20261027-912", runs_root=runs,
                      on_orchestrator=lambda o: o.set_config_digest_by_hand(R.CONFIG_A))
        events = [json.loads(l) for l in
                  (runs / "run-20261027-912" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        names = [e["event"] for e in events]
        self.assertIn("config_digest_set_by_hand", names)
        checked = [e for e in events if e["event"] == "software_motion_checked"][0]
        self.assertEqual(checked["resolved"][0]["entry_ref"], "mm_label_camera_red")
        self.assertEqual(checked["resolved"][0]["config_sha256"], R.CONFIG_A)
        self.assertEqual(checked["loaded_config_sha256"], R.CONFIG_A)


class T11TheEntrysGradeDecides(_Base):
    def test_an_e3_entry_refuses_its_name_naming_the_grade(self):
        for grade in ("E2", "E3", "E4", "E5"):
            with self.subTest(grade=grade):
                o = self.build(grade={"camera_red": grade})
                text = self.refused(o, [red()])
                self.assertIn(f"graded {grade}", text)
                self.assertIn("mm_label_camera_red", text)

    def test_the_same_row_cited_to_an_e1_entry_passes(self):
        self.build(grade={"camera_red": "E3"})
        o = self.build(grade={"camera_red": "E1"})
        o.check_software_motion([red()])

    def test_the_grade_is_the_entrys_and_a_row_cannot_raise_it(self):
        path = R.write(self.tmp.name, grade={"camera_red": "E3"})
        data = json.loads(path.read_text(encoding="utf-8"))
        table = json.loads(data["tables"]["devices"]["text"])
        row = next(c for c in table["channels"] if c["id"] == "camera_red")
        row["mm_label"]["grade"] = "E1"                              # not a key of the field
        data["tables"]["devices"]["text"] = json.dumps(table)
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(orch.GapError) as ctx:
            orch.Orchestrator(registry_path=path, backend="mock")
        self.assertIn("camera_red", str(ctx.exception))


class T12TheEntrysDigestIsTheLoadedFilesDigest(_Base):
    def test_a_different_digest_refuses_naming_both(self):
        o = self.build(digest=R.CONFIG_B)
        text = self.refused(o, [red()])
        self.assertIn(R.CONFIG_A, text)
        self.assertIn(R.CONFIG_B, text)
        self.assertIn("A label read under another configuration commands nothing", text)

    def test_an_e1_entry_with_no_digest_refuses_naming_the_missing_digest(self):
        o = self.build(entry_digest={"camera_red": None})
        text = self.refused(o, [red()])
        self.assertIn("mm_config_sha256", text)
        self.assertIn("only in prose", text)

    def test_a_mock_given_no_digest_refuses_every_label_resolved_name(self):
        o = self.build(digest=None)
        self.assertIsNone(o.loaded_config_sha256)
        text = self.refused(o, [red(), lamp()])
        self.assertIn("2 refusal(s)", text)
        self.assertIn("no approved configuration is loaded in this run", text)

    def test_the_digest_cannot_be_set_by_hand_off_the_mock(self):
        o = self.build(digest=None)
        o.backend = "hardware"
        with self.assertRaises(orch.InterlockError):
            o.set_config_digest_by_hand(R.CONFIG_A)
        self.assertIsNone(o.loaded_config_sha256)

    def test_a_copy_of_the_digest_on_the_row_that_differs_from_the_entrys_stops_the_load(self):
        with self.assertRaises(orch.GapError) as ctx:
            self.build(row_digest={"camera_red": R.CONFIG_B})
        self.assertIn(R.CONFIG_A, str(ctx.exception))
        self.assertIn(R.CONFIG_B, str(ctx.exception))

    def test_a_copy_that_agrees_loads(self):
        self.build(row_digest={"camera_red": R.CONFIG_A})

    def test_a_row_digest_that_is_not_hex_stops_the_load(self):
        with self.assertRaises(orch.GapError):
            self.build(entry_digest={"camera_red": None}, row_digest={"camera_red": "not-a-digest"})


class T13ADigestIsOfBytesAndNotOfAFileName(_Base):
    def digest_of(self, folder, body: bytes) -> str:
        path = Path(self.tmp.name) / folder / "DMD_dualcam_LUNF.cfg"   # the same file name in both
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_two_configurations_with_one_name_and_different_bytes_are_two_digests(self):
        first = self.digest_of("one", b"Device,Core,Core,Initialize\n")
        second = self.digest_of("two", b"Device,Core,Core,Initialize\n# one more line\n")
        self.assertNotEqual(first, second)
        read_under_first = self.build(digest=first, entry_digest={"camera_red": first})
        read_under_first.check_software_motion([red()])
        loaded_second = self.build(digest=second, entry_digest={"camera_red": first})
        text = self.refused(loaded_second, [red()])
        self.assertIn(first, text)
        self.assertIn(second, text)

    def test_the_same_bytes_under_another_name_are_the_same_digest(self):
        first = self.digest_of("one", b"Device,Core,Core,Initialize\n")
        second = self.digest_of("two", b"Device,Core,Core,Initialize\n")
        self.assertEqual(first, second)


class T14TheOperatorGivesTheOrchestratorTheApprovedOriginalsDigest(t69._Base):
    """On the instrument the one digest is the approved ORIGINAL's, read by the load (card 069's gate),
    and never the derived copy that was loaded: the copy has the startup preset removed, so its bytes
    differ from the file the entry was read under whatever that file was."""

    def test_after_the_load_the_run_holds_the_originals_sha256_not_the_derived_copys(self):
        text = t69.cfg_text()
        self.approve(text)
        held = []
        with self.assertRaises((t69.op.Refusal, t69.orch.InterlockError)):     # refused at the gate, after the load
            self.run_hw(handover={"objective": "20x"}, mm_config=self.write_cfg(text),
                        config_loader=self.loader(), on_orchestrator=held.append)
        event = [e for e in self.events() if e["event"] == "mm_config_loaded"][0]
        self.assertEqual(held[0].loaded_config_sha256, t69.sha(text))
        self.assertEqual(event["original"]["sha256"], t69.sha(text))
        self.assertNotEqual(held[0].loaded_config_sha256, event["loaded_sha256"])

    def test_before_any_load_the_run_holds_no_digest(self):
        held = []
        with self.assertRaises((t69.op.Refusal, t69.orch.InterlockError)):
            self.run_hw(on_orchestrator=held.append)                  # no --mm-config, no approval
        self.assertTrue(all(o.loaded_config_sha256 is None for o in held))


class T15AMalformedOrDoubledLabelStopsTheLoad(_Base):
    """The registry is not resolved by picking one: a row whose field is not the form, or a label that
    sits on two rows, stops the load with the rows named (2.1 rule 2)."""

    def edited(self, change):
        path = R.write(self.tmp.name)
        data = json.loads(path.read_text(encoding="utf-8"))
        table = json.loads(data["tables"]["devices"]["text"])
        change({c["id"]: c for c in table["channels"]})
        data["tables"]["devices"]["text"] = json.dumps(table)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_a_label_on_two_rows_stops_the_load_naming_both(self):
        def change(rows):
            rows["camera_blue"]["mm_label"]["label"] = rows["camera_red"]["mm_label"]["label"]
        path = self.edited(change)
        with self.assertRaises(orch.GapError) as ctx:
            orch.Orchestrator(registry_path=path, backend="mock")
        self.assertIn("camera_red", str(ctx.exception))
        self.assertIn("camera_blue", str(ctx.exception))

    def test_a_field_that_is_not_the_form_stops_the_load(self):
        for bad in ("Kinetix_red", {"label": "Kinetix_red"}, {"label": "", "entry_ref": "x"},
                    {"label": "Kinetix_red", "entry_ref": "x", "grade": "E1"}):
            with self.subTest(bad=bad):
                path = self.edited(lambda rows: rows["camera_red"].__setitem__("mm_label", bad))
                with self.assertRaises(orch.GapError) as ctx:
                    orch.Orchestrator(registry_path=path, backend="mock")
                self.assertIn("camera_red", str(ctx.exception))

    def test_a_row_with_no_field_is_simply_without_a_label(self):
        o = self.build(labels={"camera_blue": None})
        self.assertNotIn("camera_blue", o.mm_labels)
        self.assertIn("camera_red", o.mm_labels)


if __name__ == "__main__":
    unittest.main()
