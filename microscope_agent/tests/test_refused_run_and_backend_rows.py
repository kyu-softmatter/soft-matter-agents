"""Card 065: a run refused inside operator.run leaves a log, and every abort row names its backend.

    python -m unittest microscope_agent/tests/test_refused_run_and_backend_rows.py

Mock and a fake MMCore core only. The envelope, approval and plan are TEST
values in a temporary scratch root.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
REPO = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_card065_under_test", SRC / "operator.py")
orch = op.orch
validate = _load("_validate_card065", REPO / "contracts" / "validate.py")
focus_plan_tests = _load("_focus_plan_tests_for_065", TESTS / "test_focus_plan_and_scratch_root.py")
PLAN = focus_plan_tests.PLAN


class _Run(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = focus_plan_tests._scratch(Path(self.tmp.name))
        self._saved = op.RUN_LOCK_PATH, op.authorise
        op.RUN_LOCK_PATH = Path(self.tmp.name) / "run.lock"
        self.addCleanup(self._restore)
        op.authorise = lambda plan, approvals=None: op.Authorisation(
            True, ["test: approved"], "appr-test", "plan_approval", max_tier=2)

    def _restore(self):
        op.RUN_LOCK_PATH, op.authorise = self._saved

    def folder(self, run_id):
        return self.root / "microscope_agent" / "runs" / run_id

    def refused_at_20x(self, run_id="run-test-065-refused"):
        plan = copy.deepcopy(PLAN)
        plan["focus_search"]["objective"] = "20x"           # the TEST envelope has no 20x limit
        path = Path(self.tmp.name) / "plan.json"
        path.write_text(json.dumps(plan))
        with self.assertRaises((op.Refusal, orch.InterlockError)) as caught:
            op.run(path, run_id, backend="mock", handover={"objective": "20x"}, root=self.root)
        return caught.exception


class T1ARefusedRunLeavesALog(_Run):
    def test_log_says_refused_with_the_reason(self):
        exc = self.refused_at_20x()
        log_path = self.folder("run-test-065-refused") / "log.json"
        self.assertTrue(log_path.exists(), "no log.json for a refused run")
        log = json.loads(log_path.read_text(encoding="utf-8"))
        self.assertEqual(log["ended"], "refused")
        self.assertIn("focus_z_20x_min", log["refusal"])
        self.assertIn("focus_z_20x_min", str(exc))
        schema = json.loads((REPO / "contracts/schemas/run_log.schema.json").read_text(encoding="utf-8"))
        import jsonschema
        jsonschema.validate(log, schema)

    def test_the_stream_ends_refused(self):
        self.refused_at_20x()
        lines = (self.folder("run-test-065-refused") / "events.jsonl").read_text(
            encoding="utf-8").splitlines()
        last = json.loads(lines[-1])
        self.assertEqual((last["event"], last["how"]), ("run_ended", "refused"))

    def test_no_dispatch_and_check_15_passes(self):
        self.refused_at_20x()
        log = json.loads((self.folder("run-test-065-refused") / "log.json").read_text(encoding="utf-8"))
        self.assertEqual([e for e in log["events"] if e.get("event") in validate._DISPATCH_EVENTS], [])
        self.assertEqual([e for e in log["events"] if e.get("event") == "focus_search_readback"], [])
        saved = validate.REPO
        validate.REPO = self.root
        self.addCleanup(setattr, validate, "REPO", saved)

        class Bundle:
            def of_kind(self, kind):
                return []
        found = [f for f in validate.check_15_approval_precedes_run(Bundle())
                 if "run-test-065-refused" in str(f.path)]
        self.assertEqual([f.status for f in found], ["PASS"], [vars(f) for f in found])

    @unittest.skipIf(importlib.util.find_spec("numpy") is None, "numpy is not installed")
    def test_a_refusal_after_z_moved_is_failed_not_refused(self):
        # The walk steps 95..110 and is refused at 115, above the TEST limit:
        # Z had moved, so the run did something, and calling it refused would
        # be a refused log with motion in it.
        env = self.root / "microscope_agent" / "envelope" / "safety.json"
        doc = json.loads(env.read_text())
        doc["targets"][0]["limits"]["pfs_not_engaged"] = {
            "device": "PFS", "property": "State", "values": ["Off"],
            "confirmation": {"kind": "carried_over", "from": "TEST", "on": "2026-10-08"}}
        env.write_text(json.dumps(doc))
        init = orch.Orchestrator.__init__

        def configured(s, *a, **k):
            init(s, *a, **k)
            m = s.module_for("stand_ti2e")
            m.reset()
            m.FRAME_SHAPE, m.FOCUS_Z_UM = (64, 64), 112.0
            m.apply({"settings": {"PFS": {"State": "Off"}}})
        orch.Orchestrator.__init__ = configured
        self.addCleanup(setattr, orch.Orchestrator, "__init__", init)
        plan = copy.deepcopy(PLAN)
        plan["focus_search"]["range_um"] = {"min": 95.0, "max": 110.0}
        path = Path(self.tmp.name) / "plan-above.json"
        path.write_text(json.dumps(plan))
        with self.assertRaises(orch.InterlockError):
            op.run(path, "run-test-065-above", backend="mock", handover={"objective": "40x"},
                   root=self.root)
        folder = self.folder("run-test-065-above")
        last = json.loads((folder / "events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(last["how"], "failed")
        self.assertFalse((folder / "log.json").exists())

    def test_every_log_says_how_it_ended(self):
        plan = {"card": "plan", "id": "plan-test-065-ok", "revision": 1, "actions": [],
                "numbers": [{"name": "n", "value": 1, "unit": "1", "source": "test", "grade": "E5"}],
                "stop_criteria": [{"id": "n", "number": "n", "metric": "n", "comparator": ">="}]}
        path = Path(self.tmp.name) / "plan-ok.json"
        path.write_text(json.dumps(plan))
        record = op.run(path, "run-test-065-ok", backend="mock", root=self.root, observe=lambda m: 5)
        self.assertEqual(record["ended"], "completed")


class _FakeCore:
    def __init__(self):
        self.props = {("Aura", "State"): "1", ("DiaLamp", "State"): "1",
                      ("Turret1Shutter", "State"): "1", ("Turret2Shutter", "State"): "1"}

    def getLoadedDevices(self):
        return ("Core", "Aura", "DiaLamp", "Turret1Shutter", "Turret2Shutter")

    def setProperty(self, device, prop, value):
        self.props[(device, prop)] = str(value)

    def getProperty(self, device, prop):
        return self.props[(device, prop)]

    def waitForSystem(self):
        return None


def _rows(report):
    return report["light_sources"] + report["shutters"]


class T2EveryAbortRowNamesItsBackend(unittest.TestCase):
    def test_on_mock(self):
        o = orch.Orchestrator(backend="mock")
        o.module_for("stand_ti2e").reset()
        report = o.abort("test")
        for row in _rows(report):
            self.assertIn("backend", row, row)
            if row.get("commanded") is not None:
                self.assertEqual(row["backend"], "mock", row)
            else:
                self.assertIsNone(row["backend"], row)       # nothing answered, nothing assumed
        trues = [r for r in _rows(report) if r.get("matched") is True or r.get("closed") is True]
        self.assertTrue(trues)
        self.assertTrue(all(r["backend"] == "mock" for r in trues))

    def test_through_the_fake_core(self):
        o = orch.Orchestrator(backend="mock")
        mock = o.module_for("stand_ti2e")
        mock.reset()
        mm = o._device_module("micromanager", needed_by="test")
        mm.reset()
        self.addCleanup(mm.reset)
        core = _FakeCore()
        mm._core = lambda: mm.GuardedCore(core)
        routed = {"stand_ti2e": mm, "widefield_source_a": mm}
        o.module_for = lambda cid: routed.get(cid, mock)
        report = o.abort("test")
        by = {r.get("source") or r.get("device") or r.get("element"): r for r in _rows(report)}
        for name in ("Aura III", "DiaLamp", "Turret1Shutter", "Turret2Shutter"):
            self.assertEqual(by[name]["backend"], "micromanager", by[name])
        self.assertEqual(by["laser_shutter"]["backend"], "mock")


if __name__ == "__main__":
    unittest.main()
