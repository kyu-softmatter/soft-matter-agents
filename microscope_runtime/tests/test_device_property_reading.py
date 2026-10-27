"""Card 096: the device reading carries every property of each device, and an optional exposure step writes.

    python -m unittest microscope_runtime/tests/test_device_property_reading.py

`operator.run_device_reading` against a FAKE MMCore on a non-mock backend, as card 092's tests do it: the
loader is injected, every root is a temporary folder, and the fake core is wrapped in a spy that records
every attribute the run reaches for. Each test was watched failing before the code that passes it existed.

The values here are the test's own. Which property carries limits or allowed values on the real adapters
is not known until the bench, so the fake reports them for some properties and not for others, and the
tests hold only that the record says what the core said.
"""

from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

import test_device_reading_run as t92                              # noqa: E402  card 092's fake and base

op, orch = t92.op, t92.orch
cfg_text, sha = t92.cfg_text, t92.sha

#: label -> {property: (value, type, read_only, (lower, upper) or None, allowed values)}
DEVICES = {
    "Aura": ("TestLib_Aura", "TestAuraEngine", {
        "LineReport": ("5 lines (test)", "String", True, None, ()),
        "Line1_Intensity": ("10", "Integer", False, (0.0, 100.0), ()),
        "State": ("0", "Integer", False, None, ("0", "1")),
    }),
    "Kinetix_red": ("TestLib_Cam", "TestKinetix", {
        "SerialNumber": ("RED-0001", "String", True, None, ()),
        "Binning": ("1", "String", False, None, ("1", "2", "4")),
        "Exposure": ("10.0", "Float", False, (0.01, 10000.0), ()),
    }),
    "Kinetix_blue": ("TestLib_Cam", "TestKinetix", {
        "SerialNumber": ("BLUE-0002", "String", True, None, ()),
        "Exposure": ("10.0", "Float", False, (0.01, 10000.0), ()),
    }),
    "DiaLamp": ("TestLib_Lamp", "TestDiaLamp", {
        "Description": ("a test lamp", "String", True, None, ()),
        "State": ("0", "Integer", False, None, ("0", "1")),
        "Intensity": ("0", "Integer", False, (0.0, 255.0), ()),
    }),
    "Turret1Shutter": ("TestLib_Stand", "TestShutter1", {"State": ("0", "Integer", False, None, ("0", "1"))}),
    "Turret2Shutter": ("TestLib_Stand", "TestShutter2", {"State": ("0", "Integer", False, None, ("0", "1"))}),
}
READ_LABELS = ["Aura", "Kinetix_red", "DiaLamp", "Kinetix_blue"]       # allow-list but Core, then the blue camera

WRITE_CALLS = ("setProperty", "setExposure", "snapImage", "setAutoShutter", "setConfig", "startSequenceAcquisition")


class _Core096:
    """A fake core that reports property metadata, the light state, and takes an exposure and a snap."""

    def __init__(self, loaded=None, values=None, raises=None, autoshutter=False, camera="Kinetix_red",
                 exposure_ms=10.0, readback=None, tags=None):
        self.loaded = tuple(loaded if loaded is not None else ["Core", *DEVICES])
        self.values = dict(values or {})                        # (device, property) -> value override
        self.raises = dict(raises or {})                        # (device, property) -> exception
        self.autoshutter = autoshutter
        self.camera = camera
        self.exposure = exposure_ms
        self.readback = readback                                # callable(wanted) -> what getExposure then says
        self.tags = tags                                        # callable(exposure) -> the frame's tags
        self.on_loaded = None                                   # callable(), fired when the loaded devices are asked
        self.on_snap = None                                     # callable(), fired after each snap
        self.calls = []

    # -- identity and properties ------------------------------------------------------------------ #
    def getLoadedDevices(self):
        self.calls.append(("getLoadedDevices",))
        if self.on_loaded:
            self.on_loaded()
        return self.loaded

    def getDeviceLibrary(self, label):
        self.calls.append(("getDeviceLibrary", label))
        return DEVICES[label][0]

    def getDeviceName(self, label):
        self.calls.append(("getDeviceName", label))
        return DEVICES[label][1]

    def getDevicePropertyNames(self, label):
        self.calls.append(("getDevicePropertyNames", label))
        return tuple(DEVICES[label][2])

    def _row(self, label, prop):
        return DEVICES[label][2][prop]

    def isPropertyReadOnly(self, label, prop):
        self.calls.append(("isPropertyReadOnly", label, prop))
        return self._row(label, prop)[2]

    def getPropertyType(self, label, prop):
        self.calls.append(("getPropertyType", label, prop))
        return SimpleNamespace(name=self._row(label, prop)[1])

    def hasPropertyLimits(self, label, prop):
        self.calls.append(("hasPropertyLimits", label, prop))
        return self._row(label, prop)[3] is not None

    def getPropertyLowerLimit(self, label, prop):
        self.calls.append(("getPropertyLowerLimit", label, prop))
        return self._row(label, prop)[3][0]

    def getPropertyUpperLimit(self, label, prop):
        self.calls.append(("getPropertyUpperLimit", label, prop))
        return self._row(label, prop)[3][1]

    def getAllowedPropertyValues(self, label, prop):
        self.calls.append(("getAllowedPropertyValues", label, prop))
        return self._row(label, prop)[4]

    def getProperty(self, label, prop):
        self.calls.append(("getProperty", label, prop))
        if (label, prop) in self.raises:
            raise self.raises[(label, prop)]
        return self.values.get((label, prop), self._row(label, prop)[0])

    # -- the light, the camera ---------------------------------------------------------------------- #
    def getAutoShutter(self):
        self.calls.append(("getAutoShutter",))
        if isinstance(self.autoshutter, Exception):
            raise self.autoshutter
        return self.autoshutter

    def getCameraDevice(self):
        self.calls.append(("getCameraDevice",))
        return self.camera

    def getExposure(self):
        self.calls.append(("getExposure",))
        if (self.camera, "Exposure") in self.raises:
            raise self.raises[(self.camera, "Exposure")]
        return self.exposure

    def setExposure(self, ms):
        self.calls.append(("setExposure", ms))
        self.exposure = self.readback(ms) if self.readback else ms

    def waitForDevice(self, label):
        self.calls.append(("waitForDevice", label))

    def snapImage(self):
        self.calls.append(("snapImage",))
        if self.on_snap:
            self.on_snap()

    def getTaggedImage(self):
        self.calls.append(("getTaggedImage",))
        import numpy as np
        tags = self.tags(self.exposure) if self.tags else {"Camera": self.camera, "Exposure": str(self.exposure)}
        return SimpleNamespace(pix=np.zeros((4, 6), dtype=np.uint16), tags=tags)


class _Base096(t92._Base):
    def setUp(self):
        super().setUp()
        self.core = _Core096()
        self.saved_identity = None

    def step(self, values=(5.0, 20.0, 80.0), run_id="run-test-096", **kw):
        return self.read(run_id=run_id, exposure_step=tuple(values), **kw)

    def run_dir(self, run_id="run-test-096"):
        return self.runs / run_id

    def of(self, record, name):
        return [e for e in record["events"] if e["event"] == name]

    def written(self):
        return [c for c in self.core.calls if c[0] in WRITE_CALLS]


class T1EveryPropertyOfEveryDevice(_Base096):
    def test_one_record_per_property_per_device_each_with_its_calls(self):
        record = self.read()
        self.assertEqual(record["ended"], "completed")
        by_label = {e["label"]: e for e in self.reports(record)}
        self.assertEqual(list(by_label), READ_LABELS)
        for label in READ_LABELS:
            event, props = by_label[label], DEVICES[label][2]
            self.assertEqual([p["property"] for p in event["properties"]], list(props))
            for p in event["properties"]:
                value, kind, read_only, limits, allowed = props[p["property"]]
                where = f"({label!r}, {p['property']!r})"
                self.assertEqual(p["value"], value)
                self.assertEqual(p["read_by"], f"getProperty{where}")
                self.assertEqual(p["property_type"], {"value": kind, "read_by": f"getPropertyType{where}"})
                self.assertEqual(p["read_only"], {"value": read_only, "read_by": f"isPropertyReadOnly{where}"})
                self.assertEqual(p["has_limits"], {"value": limits is not None, "read_by": f"hasPropertyLimits{where}"})

    def test_limits_are_present_exactly_where_the_core_reported_them(self):
        record = self.read()
        seen = {"with": 0, "without": 0}
        for event in self.reports(record):
            for p in event["properties"]:
                limits = DEVICES[event["label"]][2][p["property"]][3]
                if limits is None:
                    seen["without"] += 1
                    self.assertNotIn("lower_limit", p)
                    self.assertNotIn("upper_limit", p)
                else:
                    seen["with"] += 1
                    where = f"({event['label']!r}, {p['property']!r})"
                    self.assertEqual(p["lower_limit"], {"value": limits[0], "read_by": f"getPropertyLowerLimit{where}"})
                    self.assertEqual(p["upper_limit"], {"value": limits[1], "read_by": f"getPropertyUpperLimit{where}"})
        self.assertGreater(seen["with"], 0)
        self.assertGreater(seen["without"], 0)

    def test_allowed_values_are_present_exactly_where_the_core_reported_them(self):
        record = self.read()
        seen = {"with": 0, "without": 0}
        for event in self.reports(record):
            for p in event["properties"]:
                allowed = DEVICES[event["label"]][2][p["property"]][4]
                if not allowed:
                    seen["without"] += 1
                    self.assertNotIn("allowed_values", p)
                else:
                    seen["with"] += 1
                    where = f"({event['label']!r}, {p['property']!r})"
                    self.assertEqual(p["allowed_values"], {"value": list(allowed),
                                                           "read_by": f"getAllowedPropertyValues{where}"})
        self.assertGreater(seen["with"], 0)
        self.assertGreater(seen["without"], 0)

    def test_a_writable_property_is_read_now_and_the_old_unread_list_is_gone(self):
        record = self.read()
        red = {e["label"]: e for e in self.reports(record)}["Kinetix_red"]
        exposure = [p for p in red["properties"] if p["property"] == "Exposure"][0]
        self.assertEqual(exposure["value"], "10.0")
        self.assertEqual(exposure["read_only"]["value"], False)
        self.assertNotIn("writable_not_read", red)

    def test_the_streamed_log_carries_the_same_records(self):
        self.read(run_id="run-test-096")
        lines = (self.runs / "run-test-096" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        reports = [json.loads(l) for l in lines if json.loads(l)["event"] == "device_report"]
        self.assertEqual(len(reports), 4)
        self.assertTrue(all("has_limits" in p for r in reports for p in r["properties"]))


class T2WithoutTheStepNothingIsWritten(_Base096):
    def test_no_write_of_any_kind_reaches_or_is_reached_for(self):
        self.read()
        self.assertTrue(self.core.calls, "the fake core was never read: the test proves nothing")
        self.assertEqual(self.written(), [])
        self.assertEqual([n for n in self.reached if not n.startswith(("get", "is", "has"))], [])
        sent = {c[0] for c in self.core.calls}
        self.assertNotIn("getTaggedImage", sent)
        self.assertNotIn("getExposure", sent)

    def test_no_exposure_step_section_is_logged_when_it_was_not_asked_for(self):
        record = self.read()
        self.assertEqual([e["event"] for e in record["events"] if e["event"].startswith("exposure_step")], [])
        self.assertFalse((self.run_dir("run-test-096") / "frames").exists())

    def test_only_the_configuration_load_touches_the_stand(self):
        self.read()
        self.assertEqual(len(self.loaded), 1)


class T3TheExposureStep(_Base096):
    def test_the_only_writes_are_three_sets_one_restore_and_three_snaps_on_the_red_camera(self):
        record = self.step((5.0, 20.0, 80.0))
        self.assertEqual(record["ended"], "completed")
        self.assertEqual(self.written(), [
            ("setExposure", 5.0), ("snapImage",), ("setExposure", 20.0), ("snapImage",),
            ("setExposure", 80.0), ("snapImage",), ("setExposure", 10.0)])
        self.assertEqual(self.core.exposure, 10.0, "the exposure read before the step is back")
        self.assertEqual([c for c in self.core.calls if c[0] == "getCameraDevice"] != [], True)

    def test_the_values_are_the_run_arguments_and_none_is_in_the_code(self):
        self.step((7.5, 33.0, 123.0), run_id="run-test-096b")
        self.assertEqual([c[1] for c in self.written() if c[0] == "setExposure"], [7.5, 33.0, 123.0, 10.0])

    def test_each_value_is_logged_with_the_value_set_the_value_read_back_and_the_frames_own_exposure(self):
        record = self.step((5.0, 20.0, 80.0))
        rows = self.of(record, "exposure_step_value")
        self.assertEqual([r["value_set_ms"] for r in rows], [5.0, 20.0, 80.0])
        for r in rows:
            self.assertEqual(r["value_read_back_ms"], r["value_set_ms"])
            self.assertTrue(r["verified"])
            self.assertEqual(r["frame_exposure_tags"], {"Exposure": str(r["value_set_ms"])})
            self.assertEqual(r["set_by"], f"set_exposure({r['value_set_ms']!r})")
            self.assertEqual(r["section"], "exposure_step")
        self.assertEqual([r["index"] for r in rows], [0, 1, 2])

    def test_the_frames_tags_are_kept_whole_beside_the_dark_frame(self):
        record = self.step((5.0, 20.0, 80.0))
        for r in self.of(record, "exposure_step_value"):
            frame = self.run_dir() / r["frame_file"]
            tags = self.run_dir() / r["frame_tags_file"]
            self.assertTrue(frame.is_file(), frame)
            self.assertEqual(json.loads(tags.read_text(encoding="utf-8")),
                             {"Camera": "Kinetix_red", "Exposure": str(r["value_set_ms"])})
            self.assertEqual(r["frame_shape"], [4, 6])
            self.assertNotIn("\\", r["frame_file"])
        import numpy as np
        self.assertEqual(np.load(str(self.run_dir() / "frames" / "exposure_step_0.npy")).shape, (4, 6))

    def test_a_frame_that_reports_no_exposure_says_so_and_does_not_invent_one(self):
        self.core = _Core096(tags=lambda ms: {"Camera": "Kinetix_red", "Width": "6"})
        record = self.step()
        for r in self.of(record, "exposure_step_value"):
            self.assertEqual(r["frame_exposure_tags"], {})
            self.assertEqual(r["frame_tag_count"], 2)

    def test_the_restore_is_read_back_and_logged(self):
        record = self.step()
        restored = self.of(record, "exposure_step_restored")
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["wanted_ms"], 10.0)
        self.assertEqual(restored[0]["value_read_back_ms"], 10.0)
        self.assertTrue(restored[0]["verified"])
        self.assertEqual(restored[0]["read_before_step_by"], "getExposure()")

    def test_the_step_names_the_configuration_as_the_reading_does(self):
        record = self.step()
        for name in ("exposure_step_started", "exposure_step_value", "exposure_step_restored"):
            for e in self.of(record, name):
                self.assertEqual(e["configuration_sha256"], sha(cfg_text()), name)
        started = self.of(record, "exposure_step_started")[0]
        self.assertEqual(started["approval_file"], (self.approvals / "appr-cfg.json").resolve().as_posix())
        self.assertEqual(started["exposure_ms_arguments"], [5.0, 20.0, 80.0])

    def test_the_motion_check_ran_over_every_write_before_the_first_one(self):
        record = self.step()
        names = [e["event"] for e in record["events"]]
        self.assertIn("software_motion_checked", names)
        self.assertLess(names.index("software_motion_checked"), names.index("exposure_step_value"))
        checked = self.of(record, "software_motion_checked")[0]
        self.assertEqual(checked["commands"], 7)

    def test_the_section_follows_the_reading_in_the_log(self):
        record = self.step()
        names = [e["event"] for e in record["events"]]
        self.assertLess(max(i for i, n in enumerate(names) if n == "device_report"), names.index("exposure_step_started"))
        self.assertEqual(names[-1], "exposure_step_finished")
        self.assertTrue(self.of(record, "exposure_step_finished")[0]["ok"])

    def test_a_property_is_never_set(self):
        self.step()
        self.assertEqual([c for c in self.core.calls if c[0] in ("setProperty", "setAutoShutter", "setConfig")], [])


class T4NoLightNoWrite(_Base096):
    def refused(self, device, core):
        self.core = core
        record = self.step()
        self.assertEqual(self.written(), [], "a write reached the core after a refusal")
        self.assertEqual(len(self.reports(record)), 4, "the reading part must still complete")
        refusal = self.of(record, "exposure_step_refused")
        self.assertEqual(len(refusal), 1)
        self.assertIn(device, refusal[0]["device"])
        self.assertIn(device, refusal[0]["why"])
        self.assertEqual(self.of(record, "exposure_step_value"), [])
        self.assertEqual(self.of(record, "exposure_step_restored"), [])
        self.assertEqual(record["ended"], "failed")
        self.assertTrue((self.run_dir() / "log.json").exists())
        return record

    def test_a_light_source_that_reads_on_refuses(self):
        self.refused("Aura", _Core096(values={("Aura", "State"): "1"}))

    def test_the_transmitted_lamp_that_reads_on_refuses(self):
        self.refused("DiaLamp", _Core096(values={("DiaLamp", "State"): "1"}))

    def test_a_shutter_that_reads_open_refuses(self):
        self.refused("Turret1Shutter", _Core096(values={("Turret1Shutter", "State"): "1"}))

    def test_the_other_shutter_that_reads_open_refuses(self):
        self.refused("Turret2Shutter", _Core096(values={("Turret2Shutter", "State"): "1"}))

    def test_a_source_that_could_not_be_read_refuses(self):
        self.refused("Aura", _Core096(raises={("Aura", "State"): RuntimeError("no such property (test)")}))

    def test_a_shutter_that_is_not_loaded_is_not_read_and_refuses(self):
        loaded = ["Core", "Aura", "Kinetix_red", "Kinetix_blue", "DiaLamp", "Turret1Shutter"]
        record = self.refused("Turret2Shutter", _Core096(loaded=loaded))
        self.assertIn("not read", self.of(record, "exposure_step_refused")[0]["why"])

    def test_autoshutter_on_refuses_naming_it(self):
        self.refused("AutoShutter", _Core096(autoshutter=True))

    def test_autoshutter_that_could_not_be_read_refuses_naming_it(self):
        self.refused("AutoShutter", _Core096(autoshutter=RuntimeError("no autoshutter (test)")))

    def test_a_core_camera_that_is_not_the_red_one_refuses_naming_it(self):
        self.refused("Kinetix_blue", _Core096(camera="Kinetix_blue"))

    def test_an_exposure_that_cannot_be_read_first_refuses_since_it_could_not_be_restored(self):
        self.refused("exposure", _Core096(raises={("Kinetix_red", "Exposure"): RuntimeError("no exposure (test)")}))

    def test_every_refusal_is_listed_not_just_the_first(self):
        self.core = _Core096(values={("Aura", "State"): "1", ("DiaLamp", "State"): "1"})
        record = self.step()
        refusal = self.of(record, "exposure_step_refused")[0]
        self.assertEqual(sorted(r["device"] for r in refusal["refusals"]), ["Aura", "DiaLamp"])

    def test_the_sources_software_cannot_read_are_named_so_the_person_can_see_them(self):
        record = self.step()
        started = self.of(record, "exposure_step_started")[0]
        unreadable = {row["source"] for row in started["not_readable_by_software"]}
        self.assertIn("optical tweezers", unreadable)
        self.assertIn("Spectra III (LightEngine)", unreadable)
        self.assertIn("laser_shutter", unreadable)
        self.assertEqual(started["lights_read_off"][0]["read_by"], "getProperty('Aura', 'State')")


class T5AReadThatRaisesIsUnreadAndCalledOnce(_Base096):
    def test_a_property_that_raises_is_unread_and_asked_once_and_the_rest_of_it_is_still_read(self):
        self.core = _Core096(raises={("Kinetix_red", "SerialNumber"): RuntimeError("no such property (test)")})
        record = self.read()
        self.assertEqual(record["ended"], "completed")
        red = {e["label"]: e for e in self.reports(record)}["Kinetix_red"]
        serial = [p for p in red["properties"] if p["property"] == "SerialNumber"][0]
        self.assertNotIn("value", serial)
        self.assertEqual(serial["unread"], "RuntimeError: no such property (test)")
        self.assertEqual(serial["read_by"], "getProperty('Kinetix_red', 'SerialNumber')")
        self.assertEqual(self.core.calls.count(("getProperty", "Kinetix_red", "SerialNumber")), 1)
        self.assertEqual(serial["property_type"]["value"], "String")
        self.assertTrue(serial["read_only"]["value"])
        binning = [p for p in red["properties"] if p["property"] == "Binning"][0]
        self.assertEqual(binning["value"], "1")

    def test_a_metadata_read_that_raises_is_unread_in_its_own_field_and_asked_once(self):
        def boom(label, prop):
            raise RuntimeError("no limits (test)")
        self.core.hasPropertyLimits = boom
        record = self.read()
        self.assertEqual(record["ended"], "completed")
        red = {e["label"]: e for e in self.reports(record)}["Kinetix_red"]
        p = [p for p in red["properties"] if p["property"] == "Exposure"][0]
        self.assertEqual(p["has_limits"]["unread"], "RuntimeError: no limits (test)")
        self.assertNotIn("lower_limit", p)
        self.assertEqual(p["value"], "10.0")

    def test_a_device_not_loaded_is_still_logged_not_loaded_and_nothing_is_asked_of_it(self):
        self.core = _Core096(loaded=["Core", "Aura", "Kinetix_red", "DiaLamp"])
        record = self.read()
        blue = {e["label"]: e for e in self.reports(record)}["Kinetix_blue"]
        self.assertFalse(blue["loaded"])
        self.assertNotIn("properties", blue)
        self.assertNotIn(("getPropertyType", "Kinetix_blue", "SerialNumber"), self.core.calls)


class T7AStopFromOutsideEndsTheStepBeforeAnotherWrite(_Base096):
    def test_a_stop_before_the_step_begins_writes_nothing_and_says_so(self):
        holder = {}
        self.core = _Core096()

        def stop():
            holder["o"]._aborted.set()
            holder["o"].stopped_from_outside = True

        self.core.on_loaded = stop
        record = self.step(on_orchestrator=lambda o: holder.update(o=o))
        self.assertEqual(self.written(), [])
        self.assertEqual(len(self.of(record, "exposure_step_skipped")), 1)
        self.assertEqual(self.of(record, "exposure_step_started"), [])
        self.assertEqual(record["ended"], "stopped_from_outside")

    def test_a_stop_during_the_step_ends_it_after_the_frame_in_hand_and_puts_the_exposure_back(self):
        holder = {}
        self.core = _Core096()
        self.core.on_snap = lambda: holder["o"]._aborted.set()
        record = self.step(on_orchestrator=lambda o: holder.update(o=o))
        self.assertEqual(len(self.of(record, "exposure_step_value")), 1)
        self.assertEqual([c[1] for c in self.core.calls if c[0] == "setExposure"], [5.0, 10.0])
        self.assertEqual(len([c for c in self.core.calls if c[0] == "snapImage"]), 1)
        self.assertIn("stopped from outside", self.of(record, "exposure_step_failed")[0]["error"])
        self.assertEqual(self.of(record, "exposure_step_restored")[0]["verified"], True)
        self.assertEqual(record["ended"], "failed")


class T6TheStepIsAskedForByNameAndCheckedFirst(_Base096):
    def refused(self, pattern, values):
        text = cfg_text()
        self.approve(text)
        with self.assertRaisesRegex(op.Refusal, pattern):
            op.run_device_reading("run-test-096", runs_root=self.runs, backend="hardware",
                                  exposure_step=values, mm_config=self.write_cfg(text),
                                  mm_approvals=self.approvals, config_loader=self.loader())
        self.assertEqual(self.lock_taken, [])
        self.assertFalse((self.runs / "run-test-096").exists())
        self.assertEqual(self.loaded, [])

    def test_two_values_are_refused(self):
        self.refused("three", (5.0, 20.0))

    def test_four_values_are_refused(self):
        self.refused("three", (5.0, 20.0, 80.0, 90.0))

    def test_a_value_that_is_not_a_positive_number_is_refused(self):
        for bad in (0.0, -1.0, math.inf, math.nan, True, "5"):
            with self.subTest(bad=bad):
                self.refused("positive", (5.0, bad, 80.0))

    def test_the_mock_backend_is_still_refused_with_the_step(self):
        text = cfg_text()
        self.approve(text)
        with self.assertRaisesRegex(op.Refusal, "mock"):
            op.run_device_reading("run-test-096", runs_root=self.runs, backend="mock",
                                  exposure_step=(1.0, 2.0, 3.0), mm_config=self.write_cfg(text),
                                  mm_approvals=self.approvals)

    def test_a_readback_that_disagrees_stops_the_step_restores_and_ends_failed(self):
        self.core = _Core096(readback=lambda ms: ms * 2 if ms == 20.0 else ms)
        record = self.step((5.0, 20.0, 80.0))
        self.assertEqual(record["ended"], "failed")
        rows = self.of(record, "exposure_step_value")
        self.assertEqual([r["value_set_ms"] for r in rows], [5.0, 20.0])
        self.assertFalse(rows[1]["verified"])
        self.assertEqual(rows[1]["value_read_back_ms"], 40.0)
        self.assertEqual([c for c in self.written() if c[0] == "setExposure"][-1], ("setExposure", 10.0))
        self.assertEqual(self.core.exposure, 10.0)
        self.assertEqual(len(self.of(record, "exposure_step_restored")), 1)
        self.assertEqual(len(self.of(record, "exposure_step_failed")), 1)

    def test_a_snap_that_raises_still_restores(self):
        def boom():
            raise RuntimeError("snap failed (test)")
        self.core = _Core096()
        self.core.snapImage = boom
        record = self.step()
        self.assertEqual(record["ended"], "failed")
        self.assertEqual(self.core.exposure, 10.0)
        failed = self.of(record, "exposure_step_failed")[0]
        self.assertIn("snap failed (test)", failed["error"])
        self.assertEqual(self.of(record, "exposure_step_value")[0]["value_set_ms"], 5.0)

    def test_a_restore_that_is_not_read_back_as_the_original_says_so(self):
        self.core = _Core096(readback=lambda ms: 3.0 if ms == 10.0 else ms)
        record = self.step()
        restored = self.of(record, "exposure_step_restored")[0]
        self.assertFalse(restored["verified"])
        self.assertEqual(restored["value_read_back_ms"], 3.0)
        self.assertEqual(record["ended"], "failed")


if __name__ == "__main__":
    unittest.main()
