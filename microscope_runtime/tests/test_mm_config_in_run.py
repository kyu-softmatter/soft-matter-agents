"""Card 069: a hardware run loads a configuration the person approved, through the operator.

    python -m unittest microscope_runtime/tests/test_mm_config_in_run.py

The operator's `--mm-config` and `--handover-objective`, against a FAKE MMCore
on a non-mock backend: the loader is injected, so no instrument and no
Micro-Manager install is involved. Every root here is a temporary scratch
folder. Each test was watched failing before the code that passes it existed.
"""

from __future__ import annotations

import copy
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


op = _load("_op_card069_under_test", SRC / "operator.py")
orch = op.orch
orch._OPERATOR = op                      # one copy: the focus gate uses the operator under test
focus_plan_tests = _load("_focus_plan_tests_for_069", TESTS / "test_focus_plan_and_scratch_root.py")
PLAN = focus_plan_tests.PLAN

STARTUP = ("ConfigGroup,System,Startup,Core,Shutter,LightEngine\n"
           "ConfigGroup,System,Startup,Core,AutoShutter,1\n")


def cfg_text(zdrive="FocusDirection,ZDrive,1\n", startup=STARTUP):
    return ("# a test configuration\n"
            "Device,Core,Core,Initialize\n"
            "Device,ZDrive,NikonTi2,ZDrive\n"
            f"{zdrive}"
            "FocusDirection,PFSOffset,-1\n"
            f"{startup}"
            "Property,Core,AutoShutter,1\n")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _FakeCore:
    """Only the stand and the camera are loaded, as with the single-camera configuration."""

    def __init__(self):
        self.z = 100.0
        self.writes = []
        self.props = {("PFS", "State"): "Off", ("Core", "AutoShutter"): "0"}

    def getLoadedDevices(self):
        return ("Core", "ZDrive", "PFS", "Kinetix_red")

    def getPosition(self, device):
        return self.z

    def setPosition(self, device, z):
        self.writes.append((device, z))
        self.z = float(z)

    def getProperty(self, device, prop):
        return self.props[(device, prop)]

    def getAutoShutter(self):
        return False

    def waitForDevice(self, device):
        return None

    def waitForSystem(self):
        return None


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        focus_plan_tests._scratch(self.root)                     # <root>/microscope_runtime/...
        self.agent = self.root / "microscope_runtime"
        self.runs = self.agent / "runs"
        self.approvals = self.agent / "approvals"
        saved = op.AGENT, op.RUN_LOCK_PATH, op.authorise
        op.AGENT = self.agent
        op.RUN_LOCK_PATH = self.root / "run.lock"
        op.authorise = lambda plan, approvals=None: op.Authorisation(
            True, ["test: approved"], "appr-test", "plan_approval", max_tier=2)
        self.addCleanup(lambda: [setattr(op, "AGENT", saved[0]),
                                 setattr(op, "RUN_LOCK_PATH", saved[1]),
                                 setattr(op, "authorise", saved[2])])
        real_module_for = orch.Orchestrator.module_for

        def module_for(s, cid):
            kind = "micromanager" if cid == "stand_ti2e" else "mock"
            return s._device_module(kind, needed_by="card 069 test")
        orch.Orchestrator.module_for = module_for
        self.addCleanup(setattr, orch.Orchestrator, "module_for", real_module_for)
        self.core = _FakeCore()
        self.loaded = []                                         # every path the loader was asked for
        self.plan = copy.deepcopy(PLAN)
        self.plan_path = self.root / "plan.json"

    # -- helpers --------------------------------------------------------------
    def write_cfg(self, text, name="single.cfg"):
        path = self.root / name
        path.write_bytes(text.encode("utf-8"))
        return path

    def approve(self, text):
        (self.approvals).mkdir(exist_ok=True)
        (self.approvals / "appr-cfg.json").write_text(json.dumps(
            {"artifact": "mm_config_approval", "schema_version": "0.1", "written_by": "tester",
             "written_at": "2026-10-19", "configuration": {"file": "single.cfg", "sha256": sha(text)}}),
            encoding="utf-8")

    def loader(self, verified=True):
        def load(mm, path):
            self.loaded.append(Path(path))
            mm._core = lambda: mm.GuardedCore(self.core)         # the module this run's orchestrator holds
            return {"path": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    "changed_during_load": False,
                    "loaded_devices": list(self.core.getLoadedDevices()),
                    "autoshutter": {"wanted": "0", "read_getAutoShutter": not verified,
                                    "read_property": "0" if verified else "1", "verified": verified}}
        return load

    def run_hw(self, run_id="run-test-069", **kw):
        self.plan_path.write_text(json.dumps(self.plan))
        kw.setdefault("runs_root", self.runs)
        kw.setdefault("handover", {"objective": "40x"})
        return op.run(self.plan_path, run_id, backend="hardware", **kw)

    def events(self, run_id="run-test-069"):
        lines = (self.runs / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(l) for l in lines]

    def names(self, run_id="run-test-069"):
        return [e["event"] for e in self.events(run_id)]


class T1RefusedBeforeAnythingIsLoaded(_Base):
    def test_the_option_is_refused_on_the_mock_backend_not_ignored(self):
        text = cfg_text()
        self.approve(text)
        self.plan_path.write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(op.Refusal, "mock"):
            op.run(self.plan_path, "run-test-069", backend="mock", runs_root=self.runs,
                   mm_config=self.write_cfg(text), config_loader=self.loader())
        self.assertEqual(self.loaded, [])
        self.assertFalse((self.runs / "run-test-069").exists())

    def test_a_hardware_load_without_write_is_refused(self):
        text = cfg_text()
        self.approve(text)
        with self.assertRaisesRegex(op.Refusal, "--write"):
            self.run_hw(runs_root=None, mm_config=self.write_cfg(text), config_loader=self.loader())
        self.assertEqual(self.loaded, [])
        self.assertFalse((self.root / "run.lock").exists(), "a refused file took the run lock")

    def test_a_file_the_person_did_not_approve_is_refused_and_nothing_is_loaded(self):
        with self.assertRaisesRegex(op.Refusal, "approved list"):
            self.run_hw(mm_config=self.write_cfg(cfg_text()), config_loader=self.loader())
        self.assertEqual(self.loaded, [])
        self.assertFalse((self.runs / "run-test-069").exists())
        self.assertFalse((self.root / "run.lock").exists(), "a refused file took the run lock")

    def test_an_approval_of_other_bytes_is_refused(self):
        self.approve(cfg_text() + "# changed after approval\n")
        with self.assertRaisesRegex(op.Refusal, "approved list"):
            self.run_hw(mm_config=self.write_cfg(cfg_text()), config_loader=self.loader())
        self.assertEqual(self.loaded, [])

    def test_a_negative_zdrive_direction_is_refused_before_the_load(self):
        text = cfg_text(zdrive="FocusDirection,ZDrive,-1\n")
        self.approve(text)
        with self.assertRaisesRegex(op.Refusal, "negative"):
            self.run_hw(mm_config=self.write_cfg(text), config_loader=self.loader())
        self.assertEqual(self.loaded, [])
        self.assertFalse((self.runs / "run-test-069").exists())

    def test_a_configuration_with_no_zdrive_direction_is_refused_before_the_load(self):
        text = cfg_text(zdrive="")
        self.approve(text)
        with self.assertRaisesRegex(op.Refusal, "no FocusDirection line for ZDrive"):
            self.run_hw(mm_config=self.write_cfg(text), config_loader=self.loader())
        self.assertEqual(self.loaded, [])


class T2TheLoadAndItsEvent(_Base):
    def refused_at_the_gate(self, **kw):
        """A 20x lens stated against a 40x plan: the gate refuses after the load, as the card shows."""
        text = kw.pop("text", cfg_text())
        self.approve(text)
        with self.assertRaises((op.Refusal, orch.InterlockError)) as caught:
            self.run_hw(handover={"objective": "20x"}, mm_config=self.write_cfg(text),
                        config_loader=self.loader(**kw))
        return caught.exception

    def test_the_derived_copy_is_loaded_and_the_startup_preset_is_not_in_it(self):
        self.refused_at_the_gate()
        self.assertEqual(len(self.loaded), 1)
        self.assertEqual(self.loaded[0].parent, self.runs / "run-test-069")
        body = self.loaded[0].read_text(encoding="utf-8").split("Nothing else changed.\n", 1)[1]
        self.assertNotIn("ConfigGroup,System,Startup", body)

    def test_the_load_event_names_both_hashes_and_what_was_removed(self):
        text = cfg_text()
        self.refused_at_the_gate(text=text)
        event = [e for e in self.events() if e["event"] == "mm_config_loaded"][0]
        self.assertEqual(event["original"]["sha256"], sha(text))
        self.assertEqual(event["derived"]["sha256"], event["loaded_sha256"])
        self.assertEqual(len(event["derived"]["removed"]), 2)
        self.assertEqual(event["focus_direction"]["ZDrive"]["sign"], "positive")
        self.assertEqual(event["focus_direction"]["PFSOffset"]["raw"], "-1")
        self.assertEqual(event["loaded_devices"], ["Core", "ZDrive", "PFS", "Kinetix_red"])
        self.assertTrue(event["autoshutter"]["verified"])

    def test_the_load_comes_before_the_focus_gate_and_the_handover(self):
        self.refused_at_the_gate()
        names = self.names()
        self.assertIn("mm_config_loaded", names)
        self.assertLess(names.index("mm_config_loaded"), names.index("handover"))
        for later in ("focus_search_z_before", "focus_search_command", "focus_search_readback"):
            if later in names:
                self.assertLess(names.index("mm_config_loaded"), names.index(later))

    def test_a_refused_run_still_keeps_the_load_in_its_log(self):
        self.refused_at_the_gate()
        log = json.loads((self.runs / "run-test-069" / "log.json").read_text(encoding="utf-8"))
        self.assertEqual(log["ended"], "refused")
        self.assertIn("mm_config_loaded", [e["event"] for e in log["events"]])

    def test_the_gate_is_reached_with_only_the_stand_and_the_camera_loaded(self):
        exc = self.refused_at_the_gate()
        self.assertIn("20x", str(exc))
        self.assertIn("40x", str(exc))

    def test_an_autoshutter_that_did_not_verify_stops_before_the_gate(self):
        text = cfg_text()
        self.approve(text)
        with self.assertRaisesRegex(op.Refusal, "AutoShutter"):
            self.run_hw(mm_config=self.write_cfg(text), config_loader=self.loader(verified=False))
        names = self.names()
        self.assertIn("mm_config_loaded", names)
        self.assertNotIn("handover", names)
        self.assertFalse([n for n in names if n.startswith("focus_search")])
        self.assertEqual(self.core.writes, [])

    def test_without_the_option_nothing_is_loaded_and_behaviour_is_unchanged(self):
        with self.assertRaises((op.Refusal, orch.InterlockError)):
            self.run_hw()                                       # no core: refused, as before this card
        self.assertEqual(self.loaded, [])
        self.assertNotIn("mm_config_loaded", self.names())


class T4ZIsReadOnBothSidesOfARefusal(_Base):
    """What card 066 could only show on mock: the encoder read before and after a refusal, equal."""

    def test_the_load_precedes_the_z_read_and_z_is_the_same_after_the_refusal(self):
        text = cfg_text()
        self.approve(text)
        env = self.agent / "envelope" / "safety.json"
        doc = json.loads(env.read_text())
        doc["targets"][0]["limits"]["pfs_not_engaged"] = {
            "device": "PFS", "property": "State", "values": ["Off"],
            "confirmation": {"kind": "carried_over", "from": "TEST", "on": "2026-10-08"}}
        env.write_text(json.dumps(doc))
        self.plan["focus_search"]["camera_ceiling"] = {"gap": "camera_full_scale_per_readout"}
        with self.assertRaisesRegex(orch.InterlockError, "gap"):
            self.run_hw(mm_config=self.write_cfg(text), config_loader=self.loader())
        names = self.names()
        self.assertLess(names.index("mm_config_loaded"), names.index("focus_search_z_before"))
        before = [e for e in self.events() if e["event"] == "focus_search_z_before"][0]
        refused = [e for e in self.events() if e["event"] == "focus_search_refused"][0]
        self.assertEqual(before["z_um"], 100.0)
        self.assertIsNone(before["z_read_failed"])
        self.assertEqual(refused["z_before_um"], refused["z_at_refusal_um"])
        self.assertEqual(refused["z_at_refusal_um"], 100.0)
        self.assertEqual(self.core.writes, [])                  # a refusal moved nothing


class T3Main(_Base):
    def run_main(self, argv):
        calls = {}

        def fake_run(plan, **kw):
            calls.update(kw)
            raise op.Refusal("stopped by the test after the options were read")
        real = op.run
        op.run = fake_run
        self.addCleanup(setattr, op, "run", real)
        self.plan_path.write_text(json.dumps(self.plan))
        code = op.main(["--plan", str(self.plan_path), "--run-id", "run-test-069", *argv])
        return code, calls

    def test_handover_objective_passes_exactly_what_the_person_states(self):
        code, calls = self.run_main(["--backend", "hardware", "--handover-objective", "20x"])
        self.assertEqual(code, 2)
        self.assertEqual(calls["handover"]["objective"], "20x")
        self.assertIn("--handover-objective", calls["handover"]["stated_by"])

    def test_without_handover_objective_nothing_is_passed_and_nothing_is_inferred(self):
        _, calls = self.run_main(["--backend", "hardware"])
        self.assertIsNone(calls["handover"])

    def test_mm_config_is_passed_through_to_run(self):
        _, calls = self.run_main(["--backend", "hardware", "--mm-config", str(self.root / "x.cfg"),
                                  "--write"])
        self.assertEqual(Path(calls["mm_config"]), self.root / "x.cfg")

    def test_no_mm_config_means_none_is_passed(self):
        _, calls = self.run_main(["--backend", "hardware"])
        self.assertIsNone(calls["mm_config"])


if __name__ == "__main__":
    unittest.main()
