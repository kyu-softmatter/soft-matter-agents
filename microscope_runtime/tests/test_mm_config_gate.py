"""Card 069: the configuration gate -- what a hardware run may load, and what it may not.

    python -m unittest microscope_runtime/tests/test_mm_config_gate.py

Pure and on temporary files: the gate reads a configuration's bytes, the
person's approval of their sha256, and the FocusDirection lines, and loads
nothing itself. Every test here was watched failing before the code that
passes it existed. Nothing touches an instrument.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


gate = _load("_mm_config_gate_under_test", SRC / "mm_config_gate.py")

STARTUP = ("ConfigGroup,System,Startup,Core,Shutter,LightEngine\n"
           "ConfigGroup,System,Startup,Core,AutoShutter,1\n")


def cfg_text(zdrive="FocusDirection,ZDrive,1\n", pfs="FocusDirection,PFSOffset,-1\n",
             startup=STARTUP, extra=""):
    return ("# a test configuration\n"
            "Device,Core,Core,Initialize\n"
            "Device,ZDrive,NikonTi2,ZDrive\n"
            f"{zdrive}{pfs}{extra}"
            "Property,Core,Camera,Kinetix_red\n"
            f"{startup}"
            "Property,Core,AutoShutter,1\n")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.approvals = self.root / "approvals"
        self.approvals.mkdir()

    def write_cfg(self, text, name="test.cfg"):
        path = self.root / name
        path.write_bytes(text.encode("utf-8"))
        return path

    def approve(self, text, name="appr-cfg.json", **over):
        doc = {"artifact": "mm_config_approval", "schema_version": "0.1",
               "written_by": "tester", "written_at": "2026-10-19",
               "label": "TEST approval",
               "configuration": {"file": "test.cfg", "sha256": sha(text)}}
        doc.update(over)
        (self.approvals / name).write_text(json.dumps(doc), encoding="utf-8")

    def check(self, text):
        path = self.write_cfg(text)
        return gate.check(path, self.approvals)

    def approved_check(self, text):
        self.approve(text)
        return self.check(text)


class T1ApprovalByHash(_Tmp):
    def test_a_file_with_no_approval_at_all_is_refused(self):
        with self.assertRaisesRegex(gate.ConfigRefused, "approved list"):
            self.check(cfg_text())

    def test_no_approvals_folder_is_refused_too(self):
        path = self.write_cfg(cfg_text())
        with self.assertRaisesRegex(gate.ConfigRefused, "approved list"):
            gate.check(path, self.root / "no-such-folder")

    def test_an_approval_of_other_bytes_is_refused(self):
        self.approve(cfg_text() + "# one more line\n")
        with self.assertRaisesRegex(gate.ConfigRefused, "approved list"):
            self.check(cfg_text())

    def test_a_missing_file_is_refused(self):
        with self.assertRaisesRegex(gate.ConfigRefused, "does not exist"):
            gate.check(self.root / "nope.cfg", self.approvals)

    def test_an_unreadable_approval_is_not_an_approval(self):
        (self.approvals / "broken.json").write_text("{not json", encoding="utf-8")
        with self.assertRaisesRegex(gate.ConfigRefused, "not readable JSON"):
            self.check(cfg_text())

    def test_an_approval_of_another_artifact_kind_does_not_count(self):
        text = cfg_text()
        self.approve(text, artifact="plan_approval")
        with self.assertRaisesRegex(gate.ConfigRefused, "approved list"):
            self.check(text)

    def test_the_approved_file_passes_and_names_its_approval(self):
        text = cfg_text()
        res = self.approved_check(text)
        self.assertEqual(res["sha256"], sha(text))
        self.assertEqual(res["approval"]["id"], "appr-cfg.json")
        self.assertEqual(res["approval"]["written_by"], "tester")

    def test_a_powershell_bom_in_the_approval_is_accepted(self):
        text = cfg_text()
        doc = {"artifact": "mm_config_approval", "configuration": {"sha256": sha(text)}}
        (self.approvals / "bom.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(doc).encode("utf-8"))
        self.assertEqual(self.check(text)["approval"]["id"], "bom.json")


class T2ZDriveDirection(_Tmp):
    """The rule: a ZDrive FocusDirection line is present, and its value is a positive integer.

    kb:micromanager_focus_direction_encoding_mmcore_12_5_0 (only the sign counts, positive means
    increasing position brings objective and sample closer) with z_retract_direction_is_measured
    (smaller Z is retracted) make an agreeing ZDrive value positive.
    """

    def refused(self, zdrive, pattern):
        with self.assertRaisesRegex(gate.ConfigRefused, pattern):
            self.approved_check(cfg_text(zdrive=zdrive))

    def test_a_positive_value_passes(self):
        res = self.approved_check(cfg_text(zdrive="FocusDirection,ZDrive,1\n"))
        self.assertEqual(res["focus_direction"]["ZDrive"]["sign"], "positive")

    def test_only_the_sign_counts_so_two_passes_as_well(self):
        res = self.approved_check(cfg_text(zdrive="FocusDirection,ZDrive,2\n"))
        self.assertEqual(res["focus_direction"]["ZDrive"]["raw"], "2")

    def test_zero_is_refused_as_unknown(self):
        self.refused("FocusDirection,ZDrive,0\n", "zero")

    def test_a_negative_value_is_refused(self):
        self.refused("FocusDirection,ZDrive,-1\n", "negative")

    def test_a_non_integer_is_refused(self):
        self.refused("FocusDirection,ZDrive,1.0\n", "not an integer")

    def test_a_word_is_refused(self):
        self.refused("FocusDirection,ZDrive,up\n", "not an integer")

    def test_an_empty_value_is_refused(self):
        self.refused("FocusDirection,ZDrive,\n", "not an integer")

    def test_a_line_of_two_tokens_is_refused(self):
        self.refused("FocusDirection,ZDrive\n", "three")

    def test_a_line_of_four_tokens_is_refused(self):
        self.refused("FocusDirection,ZDrive,1,extra\n", "three")

    def test_no_zdrive_line_at_all_is_refused(self):
        self.refused("", "no FocusDirection line for ZDrive")

    def test_two_zdrive_lines_are_refused_as_ambiguous(self):
        self.refused("FocusDirection,ZDrive,1\nFocusDirection,ZDrive,1\n", "more than one")

    def test_a_label_that_is_not_the_focus_stage_is_refused(self):
        with self.assertRaisesRegex(gate.ConfigRefused, "ZDrve"):
            self.approved_check(cfg_text(extra="FocusDirection,ZDrve,1\n"))

    def test_a_typo_cannot_stand_in_for_the_missing_zdrive_line(self):
        self.refused("FocusDirection,ZDrve,1\n", "ZDrve")

    def test_a_commented_out_line_is_not_a_line(self):
        res = self.approved_check(cfg_text(
            zdrive="# FocusDirection,ZDrive,-1\nFocusDirection,ZDrive,1\n"))
        self.assertEqual(res["focus_direction"]["ZDrive"]["sign"], "positive")

    def test_a_refusal_cites_the_entry_it_stands_on(self):
        with self.assertRaises(gate.ConfigRefused) as ctx:
            self.approved_check(cfg_text(zdrive="FocusDirection,ZDrive,-1\n"))
        text = str(ctx.exception)
        self.assertIn("micromanager_focus_direction_encoding_mmcore_12_5_0", text)
        self.assertIn("z_retract_direction_is_measured", text)


class T3PfsOffsetIsRecordedNotJudged(_Tmp):
    def test_a_pfsoffset_line_is_recorded_beside_the_hashes(self):
        res = self.approved_check(cfg_text(pfs="FocusDirection,PFSOffset,-1\n"))
        self.assertEqual(res["focus_direction"]["PFSOffset"]["raw"], "-1")
        self.assertIn("refused by name to software", res["focus_direction"]["PFSOffset"]["note"])

    def test_no_pfsoffset_line_is_recorded_as_none(self):
        res = self.approved_check(cfg_text(pfs=""))
        self.assertIsNone(res["focus_direction"]["PFSOffset"])

    def test_a_pfsoffset_value_nobody_can_read_is_recorded_as_read_by_nobody(self):
        res = self.approved_check(cfg_text(pfs="FocusDirection,PFSOffset,sideways\n"))
        self.assertEqual(res["focus_direction"]["PFSOffset"]["sign"], "unread")


class T4StartupPreset(_Tmp):
    def test_the_startup_lines_are_found(self):
        res = self.approved_check(cfg_text())
        self.assertEqual(len(res["startup_lines"]), 2)

    def test_a_file_without_a_startup_preset_says_so(self):
        res = self.approved_check(cfg_text(startup=""))
        self.assertEqual(res["startup_lines"], [])

    def test_derive_removes_the_startup_lines_and_nothing_else(self):
        text = cfg_text()
        derived, removed = gate.derive(text, "test.cfg", sha(text))
        self.assertEqual(len(removed), 2)
        body = derived.split("Nothing else changed.\n", 1)[1]
        self.assertNotIn("ConfigGroup,System,Startup", body)
        kept = [l for l in text.splitlines(True) if not l.startswith("ConfigGroup,System,Startup")]
        self.assertEqual(body, "".join(kept))
        self.assertIn(sha(text), derived.split("Nothing else changed")[0])

    def test_derive_keeps_the_original_line_endings(self):
        text = cfg_text().replace("\n", "\r\n")
        derived, _ = gate.derive(text, "test.cfg", sha(text))
        self.assertIn("Device,Core,Core,Initialize\r\n", derived)


class T5LoadInTheRunFolder(_Tmp):
    def setUp(self):
        super().setUp()
        self.folder = self.root / "runs" / "run-test-069"
        self.folder.mkdir(parents=True)
        self.calls = []
        self.seen = {}

    def loader(self, verified=True):
        def load(path):
            p = Path(path)
            self.calls.append(p)
            self.seen["text"] = p.read_text(encoding="utf-8")        # the file must exist now
            return {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    "changed_during_load": False, "loaded_devices": ["Core", "ZDrive"],
                    "autoshutter": {"wanted": "0", "read_getAutoShutter": not verified,
                                    "read_property": "0" if verified else "1",
                                    "verified": verified}}
        return load

    def test_with_a_startup_preset_the_derived_copy_is_what_is_loaded(self):
        text = cfg_text()
        res = self.approved_check(text)
        event = gate.load(res, self.folder, self.loader())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0].parent, self.folder)
        loaded_body = self.seen["text"].split("Nothing else changed.\n", 1)[1]
        self.assertNotIn("ConfigGroup,System,Startup", loaded_body)
        self.assertEqual(event["original"]["sha256"], sha(text))
        self.assertEqual(event["derived"]["sha256"], sha(self.seen["text"]))
        self.assertEqual(len(event["derived"]["removed"]), 2)
        self.assertEqual(event["startup_preset"], "removed")

    def test_without_a_startup_preset_the_original_is_loaded_and_nothing_is_derived(self):
        text = cfg_text(startup="")
        res = self.approved_check(text)
        event = gate.load(res, self.folder, self.loader())
        self.assertEqual(self.calls, [self.root / "test.cfg"])
        self.assertIsNone(event["derived"])
        self.assertIn("nothing derived", event["startup_preset"])
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), [])

    def test_the_event_carries_what_the_card_lists(self):
        res = self.approved_check(cfg_text())
        event = gate.load(res, self.folder, self.loader())
        self.assertEqual(event["event"], "mm_config_loaded")
        for key in ("original", "approval", "derived", "startup_preset", "focus_direction",
                    "loaded_devices", "autoshutter"):
            self.assertIn(key, event)
        self.assertEqual(event["original"]["path"], str(self.root / "test.cfg"))
        self.assertEqual(event["loaded_devices"], ["Core", "ZDrive"])
        self.assertTrue(event["autoshutter"]["verified"])

    def test_with_no_run_folder_nothing_is_loaded(self):
        res = self.approved_check(cfg_text())
        with self.assertRaisesRegex(gate.ConfigRefused, "--write"):
            gate.load(res, None, self.loader())
        self.assertEqual(self.calls, [])

    def test_an_autoshutter_that_did_not_verify_stops_the_run_and_keeps_the_event(self):
        res = self.approved_check(cfg_text())
        with self.assertRaises(gate.AutoShutterNotVerified) as ctx:
            gate.load(res, self.folder, self.loader(verified=False))
        self.assertEqual(ctx.exception.event["event"], "mm_config_loaded")
        self.assertFalse(ctx.exception.event["autoshutter"]["verified"])
        self.assertIn("AutoShutter", str(ctx.exception))

    def test_a_loader_that_says_nothing_about_autoshutter_is_not_verified(self):
        res = self.approved_check(cfg_text())
        with self.assertRaises(gate.AutoShutterNotVerified):
            gate.load(res, self.folder, lambda path: {"loaded_devices": ["Core"]})


if __name__ == "__main__":
    unittest.main()
