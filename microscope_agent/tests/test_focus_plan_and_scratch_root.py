"""Card 063 Part A: a focus-search plan through operator.run, the copied core deciding, and a
scratch root that only mock may use.

    python -m unittest microscope_agent/tests/test_focus_plan_and_scratch_root.py

Mock only. Every envelope, approval and plan here is a TEST value in a
temporary folder. `verdict_thresholds` is a PROVISIONAL field name: the plan
schema has no field for focus_verdict.from_sweep's five thresholds yet, and
until it does the decider refuses (test 2b).
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
sys.path.insert(0, str(SRC))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_focus_plan_under_test", SRC / "operator.py")
fd = _load("_focus_decider_under_test", SRC / "focus_decider.py")

try:
    import numpy
except ImportError:                                             # pragma: no cover
    numpy = None

THRESHOLDS = {"min_dynamic_range_adu": 50, "min_contrast": 0.05, "min_frames": 3,
              "dropout_tolerance": 0.5, "max_saturated": 0.01}
PLAN = {
    "card": "plan", "id": "plan-mic-test-063-focus", "revision": 1,
    "actions": [{"id": "focus", "device": "stand_ti2e", "action": "focus_search",
                 "reversible": True, "tier": 1}],
    "numbers": [{"name": "camera_full_scale", "value": 65535, "unit": "ADU",
                 "source": "kb:TEST_mock_camera_full_scale", "grade": "E3"}],
    "targets": [{"metric": "position_readback_error", "value": 0.5, "unit": "um"}],
    "stop_criteria": [{"id": "readback", "target": "position_readback_error",
                       "metric": "position_readback_error", "comparator": "<="}],
    "focus_search": {
        "channel": "stand_ti2e", "element": "z_drive", "action": "focus", "objective": "40x",
        "read_back": "encoder", "pfs": "off", "approach_from": "retract",
        "range_um": {"min": 100.0, "max": 110.0}, "step_um": 5.0, "max_moves": 10,
        "max_extensions": 0, "metric_arguments": {"bin_px": 4, "blocks_per_side": 2},
        "camera_ceiling": {"number": "camera_full_scale"},
        "branches": ["in_focus", "step_up", "step_down", "no_sample_here", "unsure"],
        "decided_by": "metric_maximum", "metric": {"name": "vollath4", "computed": "deterministic"},
        "illumination": "as_set_by_plan",
        "verdict_thresholds": THRESHOLDS,
    },
}


def _scratch(tmp: Path, approved: bool = True) -> Path:
    agent = tmp / "microscope_agent"
    (agent / "envelope").mkdir(parents=True)
    (agent / "approvals").mkdir()
    (agent / "envelope" / "safety.json").write_text(json.dumps({
        "policy_version": "TEST", "targets": [{"target": "bench", "limits": {
            "focus_z_40x_min": {"value": 90, "unit": "um", "bounds": "min",
                                "note": "TEST VALUE, card 063 on mock"},
            "focus_z_40x_max": {"value": 110, "unit": "um", "bounds": "max",
                                "note": "TEST VALUE, card 063 on mock"}}}]}))
    return tmp


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _scratch(Path(self.tmp.name))
        self._saved = op.RUN_LOCK_PATH, op.authorise
        op.RUN_LOCK_PATH = Path(self.tmp.name) / "run.lock"
        self.addCleanup(self._restore)
        self.plan = copy.deepcopy(PLAN)

    def _restore(self):
        op.RUN_LOCK_PATH, op.authorise = self._saved

    def approve(self):
        real = self._saved[1]
        op.authorise = lambda plan, approvals=None: op.Authorisation(
            True, ["test: approved"], "appr-test", "plan_approval", max_tier=2) \
            if plan.get("id") == self.plan["id"] else real(plan, approvals)

    def run_plan(self, **kw):
        path = Path(self.tmp.name) / "plan.json"
        path.write_text(json.dumps(self.plan))
        return op.run(path, "run-test-063", backend=kw.pop("backend", "mock"),
                      handover={"objective": "40x"}, root=self.root, **kw)


class T1AGapCeilingRefusesWithNoZWrite(_Base):
    def test_gap(self):
        self.approve()
        self.plan["focus_search"]["camera_ceiling"] = {"gap": "camera_full_scale_per_readout"}
        writes = []
        real = op.orch.Orchestrator._focus_move
        op.orch.Orchestrator._focus_move = lambda s, *a, **k: writes.append(a) or real(s, *a, **k)
        self.addCleanup(setattr, op.orch.Orchestrator, "_focus_move", real)
        with self.assertRaises(op.Refusal) as caught:
            self.run_plan()
        self.assertIn("gap", str(caught.exception))
        self.assertEqual(writes, [])

    def test_unapproved_focus_plan_refuses_at_the_gate(self):
        with self.assertRaises(op.Refusal) as caught:
            self.run_plan()
        self.assertIn("not approved", str(caught.exception))


@unittest.skipIf(numpy is None, "numpy is not installed")
class T2ASourcedCeilingLetsTheCorePick(unittest.TestCase):
    def test_the_core_picks_a_branch_from_mock_frames(self):
        plan = copy.deepcopy(PLAN)
        frames = iter(numpy.random.default_rng(0).integers(0, 4000, (8, 32, 32), dtype=numpy.uint16))
        decide = fd.MetricMaximumDecider(plan, grab=lambda: (next(frames), {}))
        self.assertEqual(decide.ceiling, 65535)
        seen = [decide(100.0 + 5 * k)["branch"] for k in range(4)]
        self.assertTrue(all(b in plan["focus_search"]["branches"] for b in seen), seen)
        self.assertTrue(decide.records and "verdict" in decide.records[-1])

    def test_in_focus_only_where_the_cores_frame_is(self):
        # Found by card 063's mock walk: the core said in_focus with its frame
        # at 105 while Z stood at 110, and the search recorded 110 as found.
        # The core's in_focus names a frame; the decider steps toward it and
        # says in_focus only when that frame is where Z is now.
        plan = copy.deepcopy(PLAN)
        decide = fd.MetricMaximumDecider(plan, grab=lambda: (None, {}))

        class V:                                        # a verdict that names frame 105
            def __init__(self, verdict, z):
                self.r = {"verdict": verdict, "reason": "test", "z_um": z}

            def as_record(self):
                return self.r
        decide.classical = type("C", (), {"frame_stats": staticmethod(
            lambda *a, **k: type("S", (), {"score": 1.0})())})
        decide.verdict = type("F", (), {"from_sweep": staticmethod(lambda *a, **k: V("in_focus", 105.0))})
        self.assertEqual(decide(110.0)["branch"], "step_down")
        self.assertEqual(decide(100.0)["branch"], "step_up")
        self.assertEqual(decide(105.0)["branch"], "in_focus")

    def test_no_thresholds_refuses(self):
        plan = copy.deepcopy(PLAN)
        del plan["focus_search"]["verdict_thresholds"]
        with self.assertRaises(fd.DeciderRefused) as caught:
            fd.MetricMaximumDecider(plan, grab=lambda: None)
        self.assertIn("thresholds", str(caught.exception))

    def test_thresholds_out_of_their_ranges_refuse(self):
        # The committed field (0e3eff1): min_frames a whole number >= 3, the
        # dynamic range a whole number >= 0, and three fractions in [0, 1].
        for key, bad in (("min_frames", 2), ("min_frames", 3.5), ("min_contrast", 1.5),
                         ("dropout_tolerance", -0.1), ("max_saturated", 2),
                         ("min_dynamic_range_adu", -1), ("min_dynamic_range_adu", 1.5)):
            plan = copy.deepcopy(PLAN)
            plan["focus_search"]["verdict_thresholds"][key] = bad
            with self.assertRaises(fd.DeciderRefused, msg=(key, bad)):
                fd.MetricMaximumDecider(plan, grab=lambda: None)

    def test_a_ceiling_without_a_kb_source_refuses(self):
        plan = copy.deepcopy(PLAN)
        plan["numbers"][0]["source"] = "operator_recall:test"
        with self.assertRaises(fd.DeciderRefused):
            fd.MetricMaximumDecider(plan, grab=lambda: None)


class T3AScratchRootRefusesWithAnyOtherBackend(_Base):
    def test_micromanager_with_a_scratch_root_refuses_before_anything_loads(self):
        built = []
        real = op.orch.Orchestrator.__init__
        op.orch.Orchestrator.__init__ = lambda s, *a, **k: built.append(1) or real(s, *a, **k)
        self.addCleanup(setattr, op.orch.Orchestrator, "__init__", real)
        read = []
        real_safety = op.load_safety
        op.load_safety = lambda *a, **k: read.append(1) or real_safety(*a, **k)
        self.addCleanup(setattr, op, "load_safety", real_safety)
        for backend in ("micromanager", "hardware"):
            with self.assertRaises(op.Refusal) as caught:
                self.run_plan(backend=backend)
            self.assertIn("mock", str(caught.exception))
        self.assertEqual((built, read), ([], []))


class T4TheDefaultRootIsUnchanged(unittest.TestCase):
    def test_no_root_reads_this_tree(self):
        calls = []
        saved = op.load_safety, op.approvals_on_disk
        op.load_safety = lambda *a, **k: calls.append(("safety", a, k)) or {"targets": []}
        op.approvals_on_disk = lambda *a, **k: calls.append(("approvals", a, k)) or []
        self.addCleanup(lambda: (setattr(op, "load_safety", saved[0]),
                                 setattr(op, "approvals_on_disk", saved[1])))
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        saved_lock = op.RUN_LOCK_PATH
        op.RUN_LOCK_PATH = Path(tmp.name) / "run.lock"
        self.addCleanup(setattr, op, "RUN_LOCK_PATH", saved_lock)
        plan = {"card": "plan", "id": "plan-test-063-default", "revision": 1, "actions": [],
                "numbers": [{"name": "n", "value": 1, "unit": "1", "source": "test", "grade": "E5"}],
                "stop_criteria": [{"id": "n", "number": "n", "metric": "n", "comparator": ">="}]}
        path = Path(tmp.name) / "plan.json"
        path.write_text(json.dumps(plan))
        op.run(path, "run-test-063-default", backend="mock")
        self.assertIn(("safety", (), {}), calls)
        self.assertIn(("approvals", (), {}), calls)
        self.assertEqual(op.agent_root(None), op.AGENT)


if __name__ == "__main__":
    unittest.main()
