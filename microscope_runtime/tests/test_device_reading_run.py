"""Card 092: a run reads each device's report of itself under the approved configuration.

    python -m unittest microscope_runtime/tests/test_device_reading_run.py

`operator.run_device_reading` against a FAKE MMCore on a non-mock backend: the loader is injected, so
no instrument and no Micro-Manager install is involved, and every root is a temporary scratch folder.
The fake core is wrapped in a spy that records EVERY attribute the run reaches for on the core handle
it was given, so a write attempted and refused by the guard still shows. Each test was watched
failing before the code that passes it existed.
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
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_card092_under_test", SRC / "operator.py")
orch = op.orch
in_run = _load("_in_run_tests_for_092", TESTS / "test_mm_config_in_run.py")
cfg_text, sha = in_run.cfg_text, in_run.sha

#: What the fake instrument reports of itself: (library, device name, {read-only property: value},
#: [writable properties]). The values are the test's own and say nothing about the instrument.
IDENTITY = {
    "Aura": ("TestLib_Aura", "TestAuraEngine", {"LineReport": "5 lines (test)"}, ["Line1_Intensity"]),
    "Kinetix_red": ("TestLib_Cam", "TestKinetix", {"SerialNumber": "RED-0001", "ChipName": "TestChip",
                                                   "FirmwareVersion": "9.9"}, ["Exposure", "Binning"]),
    "Kinetix_blue": ("TestLib_Cam", "TestKinetix", {"SerialNumber": "BLUE-0002", "ChipName": "TestChip",
                                                    "FirmwareVersion": "9.9"}, ["Exposure"]),
    "DiaLamp": ("TestLib_Lamp", "TestDiaLamp", {"Description": "a test lamp"}, ["State", "Intensity"]),
}

#: Every call name that would change the stand, whatever the guard says of it.
WRITES = ("setProperty", "setConfig", "snapImage", "snap", "startSequenceAcquisition",
          "startContinuousSequenceAcquisition", "setPosition", "setXYPosition", "setRelativePosition",
          "setAutoShutter", "setExposure", "loadSystemConfiguration")


class _FakeCore:
    def __init__(self, loaded=None, raises=None):
        self.loaded = tuple(loaded if loaded is not None else ["Core", *IDENTITY])
        self.raises = dict(raises or {})                       # (device, property) -> exception
        self.calls = []                                        # what reached the fake

    def getLoadedDevices(self):
        self.calls.append(("getLoadedDevices",))
        return self.loaded

    def getDeviceLibrary(self, label):
        self.calls.append(("getDeviceLibrary", label))
        return IDENTITY[label][0]

    def getDeviceName(self, label):
        self.calls.append(("getDeviceName", label))
        return IDENTITY[label][1]

    def getDevicePropertyNames(self, label):
        self.calls.append(("getDevicePropertyNames", label))
        return tuple([*IDENTITY[label][2], *IDENTITY[label][3]])

    def isPropertyReadOnly(self, label, prop):
        self.calls.append(("isPropertyReadOnly", label, prop))
        return prop in IDENTITY[label][2]

    def getProperty(self, label, prop):
        self.calls.append(("getProperty", label, prop))
        if (label, prop) in self.raises:
            raise self.raises[(label, prop)]
        return IDENTITY[label][2].get(prop, "writable value")


class _Spy:
    """Whatever the run reaches for on the core, by name, before the guard sees it."""

    def __init__(self, inner, seen):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_seen", seen)

    def __getattr__(self, name):
        self._seen.append(name)
        return getattr(self._inner, name)


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.approvals = self.root / "approvals"
        self.approvals.mkdir()
        self.runs = self.root / "runs"
        saved_lock = op.RUN_LOCK_PATH
        op.RUN_LOCK_PATH = self.root / "run.lock"
        self.addCleanup(setattr, op, "RUN_LOCK_PATH", saved_lock)
        self.lock_taken = []
        real_take = op._take_run_lock

        def take(holder):
            self.lock_taken.append(holder)
            return real_take(holder)
        op._take_run_lock = take
        self.addCleanup(setattr, op, "_take_run_lock", real_take)
        self.core = _FakeCore()
        self.reached = []                                      # every name the run asked the core for
        self.loaded = []

    def write_cfg(self, text, name="single.cfg"):
        path = self.root / name
        path.write_bytes(text.encode("utf-8"))
        return path

    def approve(self, text, name="appr-cfg.json"):
        (self.approvals / name).write_text(json.dumps(
            {"artifact": "mm_config_approval", "schema_version": "0.1", "written_by": "tester",
             "written_at": "2026-10-19", "configuration": {"file": "single.cfg", "sha256": sha(text)}}),
            encoding="utf-8")

    def loader(self, verified=True):
        def load(mm, path):
            self.loaded.append(Path(path))
            mm._core = lambda: _Spy(mm.GuardedCore(self.core), self.reached)
            return {"path": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    "changed_during_load": False, "loaded_devices": list(self.core.getLoadedDevices()),
                    "autoshutter": {"wanted": "0", "read_getAutoShutter": not verified,
                                    "read_property": "0" if verified else "1", "verified": verified}}
        return load

    def read(self, run_id="run-test-092", text=None, **kw):
        text = cfg_text() if text is None else text
        self.approve(text)
        kw.setdefault("mm_config", self.write_cfg(text))
        kw.setdefault("config_loader", self.loader())
        kw.setdefault("runs_root", self.runs)
        kw.setdefault("mm_approvals", self.approvals)
        kw.setdefault("backend", "hardware")
        return op.run_device_reading(run_id, **kw)

    def reports(self, record):
        return [e for e in record["events"] if e["event"] == "device_report"]


class T1OneEventPerDevice(_Base):
    def test_one_report_per_allow_listed_device_but_core_plus_the_blue_camera(self):
        record = self.read()
        self.assertEqual(record["ended"], "completed")
        mm = orch.Orchestrator(backend="hardware")._device_module("micromanager", needed_by="the test")
        expected = [d for d in mm.SOFTWARE_MAY_COMMAND if d != "Core"] + ["Kinetix_blue"]
        self.assertEqual([e["label"] for e in self.reports(record)], expected)
        self.assertNotIn("Core", expected)

    def test_each_report_has_library_device_name_and_read_only_properties_each_with_its_call(self):
        record = self.read()
        by_label = {e["label"]: e for e in self.reports(record)}
        for label, (library, name, read_only, writable) in IDENTITY.items():
            event = by_label[label]
            self.assertTrue(event["loaded"])
            self.assertEqual(event["library"], {"value": library, "read_by": f"getDeviceLibrary({label!r})"})
            self.assertEqual(event["device_name"], {"value": name, "read_by": f"getDeviceName({label!r})"})
            self.assertEqual({p["property"]: p["value"] for p in event["properties"] if p["read_only"]["value"]},
                             read_only)
            for p in event["properties"]:
                self.assertEqual(p["read_by"], f"getProperty({label!r}, {p['property']!r})")
            self.assertEqual([p["property"] for p in event["properties"] if not p["read_only"]["value"]], writable)

    def test_the_reports_are_in_the_streamed_log_too(self):
        self.read()
        lines = (self.runs / "run-test-092" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sum(json.loads(l)["event"] == "device_report" for l in lines), 4)

    def test_the_run_is_a_preparatory_run_with_no_plan(self):
        record = self.read()
        self.assertIsNone(record["plan_id"])
        self.assertIsNone(record["revision"])
        self.assertTrue(record["no_plan_because"])
        self.assertTrue(record["not_dispatched"])
        self.assertTrue((self.runs / "run-test-092" / "log.json").exists())


class T2NothingIsWritten(_Base):
    def test_no_write_call_of_any_kind_reaches_the_core(self):
        self.read()
        self.assertTrue(self.core.calls, "the fake core was never read: the test proves nothing")
        sent = {c[0] for c in self.core.calls}
        for name in WRITES:
            self.assertNotIn(name, sent)
        self.assertEqual(sent - {"getLoadedDevices", "getDeviceLibrary", "getDeviceName",
                                 "getDevicePropertyNames", "isPropertyReadOnly", "getProperty"}, set())

    def test_the_run_does_not_even_reach_for_one(self):
        self.read()
        self.assertTrue(self.reached)
        self.assertEqual([n for n in self.reached if n in WRITES or not n.startswith(("get", "is", "has"))], [])

    def test_only_the_configuration_load_touches_the_stand(self):
        self.read()
        self.assertEqual(len(self.loaded), 1)
        self.assertEqual(self.loaded[0].parent, self.runs / "run-test-092")


class T3TheConfigurationIsNamedAsTheCheckWillCompareIt(_Base):
    def test_the_log_carries_the_originals_sha256_not_the_derived_copys(self):
        text = cfg_text()
        record = self.read(text=text)
        self.assertEqual(record["approved_commands"]["sha256"], sha(text))
        loaded = [e for e in record["events"] if e["event"] == "mm_config_loaded"][0]
        self.assertNotEqual(loaded["loaded_sha256"], sha(text), "the test's configuration has no startup preset")
        for event in self.reports(record):
            self.assertEqual(event["configuration_sha256"], sha(text))
            self.assertNotEqual(event["configuration_sha256"], loaded["loaded_sha256"])

    def test_the_approval_file_is_named_with_forward_slashes(self):
        record = self.read()
        started = [e for e in record["events"] if e["event"] == "device_reading_started"]
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0]["approval_file"], (self.approvals / "appr-cfg.json").resolve().as_posix())
        self.assertNotIn("\\", started[0]["approval_file"])
        self.assertEqual(started[0]["configuration"]["sha256"], sha(cfg_text()))
        names = [e["event"] for e in record["events"]]
        self.assertLess(names.index("mm_config_loaded"), names.index("device_reading_started"))
        self.assertLess(names.index("device_reading_started"), names.index("device_report"))


class T4WhatCannotBeReadIsSaidSo(_Base):
    def test_a_device_the_configuration_did_not_load_is_logged_as_not_loaded_and_the_run_completes(self):
        self.core = _FakeCore(loaded=["Core", "Aura", "Kinetix_red", "DiaLamp"])      # no Kinetix_blue
        record = self.read()
        self.assertEqual(record["ended"], "completed")
        by_label = {e["label"]: e for e in self.reports(record)}
        self.assertFalse(by_label["Kinetix_blue"]["loaded"])
        self.assertIn("not loaded", by_label["Kinetix_blue"]["why"])
        self.assertNotIn("properties", by_label["Kinetix_blue"])
        self.assertNotIn(("getDeviceName", "Kinetix_blue"), self.core.calls)
        self.assertTrue(by_label["Kinetix_red"]["loaded"])

    def test_a_property_read_that_raises_is_logged_as_unread_and_called_once(self):
        self.core = _FakeCore(raises={("Kinetix_red", "SerialNumber"): RuntimeError("no such property (test)")})
        record = self.read()
        self.assertEqual(record["ended"], "completed")
        red = {e["label"]: e for e in self.reports(record)}["Kinetix_red"]
        serial = [p for p in red["properties"] if p["property"] == "SerialNumber"][0]
        self.assertNotIn("value", serial)
        self.assertEqual(serial["unread"], "RuntimeError: no such property (test)")
        self.assertEqual(serial["read_by"], "getProperty('Kinetix_red', 'SerialNumber')")
        self.assertEqual(self.core.calls.count(("getProperty", "Kinetix_red", "SerialNumber")), 1)
        chip = [p for p in red["properties"] if p["property"] == "ChipName"][0]
        self.assertEqual(chip["value"], "TestChip")                 # the next property was still read

    def test_a_device_name_read_that_fails_is_unread_not_invented(self):
        def boom(label):
            raise RuntimeError("no name (test)")
        self.core.getDeviceName = boom
        record = self.read()
        red = {e["label"]: e for e in self.reports(record)}["Kinetix_red"]
        self.assertEqual(red["device_name"]["unread"], "RuntimeError: no name (test)")
        self.assertNotIn("value", red["device_name"])
        self.assertEqual(red["library"]["value"], "TestLib_Cam")

    def test_a_load_that_did_not_verify_autoshutter_reads_nothing(self):
        record = self.read(config_loader=self.loader(verified=False))
        self.assertEqual(record["ended"], "failed")
        self.assertEqual(self.reports(record), [])
        names = [e["event"] for e in record["events"]]
        self.assertIn("mm_config_loaded", names)
        self.assertIn("device_reading_failed", names)
        self.assertEqual([c for c in self.core.calls if c[0] != "getLoadedDevices"], [])


class T5RefusedBeforeTheLock(_Base):
    def refused(self, pattern, **kw):
        kw.setdefault("runs_root", self.runs)
        kw.setdefault("backend", "hardware")
        with self.assertRaisesRegex(op.Refusal, pattern):
            op.run_device_reading("run-test-092", config_loader=self.loader(), **kw)
        self.assertEqual(self.lock_taken, [], "a refused run took the run lock")
        self.assertFalse((self.root / "run.lock").exists())
        self.assertFalse((self.runs / "run-test-092").exists())
        self.assertEqual(self.loaded, [])

    def test_no_configuration_named_is_refused(self):
        self.refused("configuration", mm_approvals=self.approvals)

    def test_a_configuration_the_person_did_not_approve_is_refused(self):
        self.refused("approved list", mm_config=self.write_cfg(cfg_text()), mm_approvals=self.approvals)

    def test_an_approval_of_other_bytes_is_refused(self):
        self.approve(cfg_text() + "# changed after approval\n")
        self.refused("approved list", mm_config=self.write_cfg(cfg_text()), mm_approvals=self.approvals)

    def test_the_mock_backend_is_refused_not_ignored(self):
        text = cfg_text()
        self.approve(text)
        self.refused("mock", mm_config=self.write_cfg(text), mm_approvals=self.approvals, backend="mock")

    def test_without_write_there_is_nowhere_to_keep_the_derived_copy(self):
        text = cfg_text()
        self.approve(text)
        self.refused("--write", mm_config=self.write_cfg(text), mm_approvals=self.approvals, runs_root=None)
        self.assertFalse(self.runs.exists())

    def test_a_negative_focus_direction_is_refused(self):
        text = cfg_text(zdrive="FocusDirection,ZDrive,-1\n")
        self.approve(text)
        self.refused("negative", mm_config=self.write_cfg(text), mm_approvals=self.approvals)

    def test_a_run_id_is_not_reused_and_the_lock_is_released(self):
        self.read()
        with self.assertRaisesRegex(op.Refusal, "already exists"):
            self.read()
        op._take_run_lock({"kind": "test", "run_id": "after"}).release()      # raises if the run kept it


class T6TheListIsTheModulesNotACopy(_Base):
    def test_a_device_added_to_the_allow_list_is_read_with_no_other_change(self):
        text = cfg_text()
        self.approve(text)
        IDENTITY["TestExtra"] = ("TestLib_X", "TestExtraDevice", {"SerialNumber": "X-1"}, [])
        self.addCleanup(IDENTITY.pop, "TestExtra", None)
        self.core = _FakeCore(loaded=["Core", *IDENTITY])

        def add(o):
            o._device_module("micromanager", needed_by="the test").SOFTWARE_MAY_COMMAND["TestExtra"] = None
        record = self.read(on_orchestrator=add)
        labels = [e["label"] for e in self.reports(record)]
        self.assertIn("TestExtra", labels)
        self.assertEqual(len(labels), 5)

    def test_a_device_taken_off_the_allow_list_is_no_longer_read(self):
        def drop(o):
            del o._device_module("micromanager", needed_by="the test").SOFTWARE_MAY_COMMAND["DiaLamp"]
        record = self.read(on_orchestrator=drop)
        self.assertNotIn("DiaLamp", [e["label"] for e in self.reports(record)])

    def test_the_blue_camera_is_read_without_being_on_the_allow_list(self):
        mm = orch.Orchestrator(backend="hardware")._device_module("micromanager", needed_by="the test")
        self.assertNotIn("Kinetix_blue", mm.SOFTWARE_MAY_COMMAND)
        record = self.read()
        self.assertIn("Kinetix_blue", [e["label"] for e in self.reports(record)])
        self.assertNotIn("Kinetix_blue", mm.SOFTWARE_MAY_COMMAND)


if __name__ == "__main__":
    unittest.main()
