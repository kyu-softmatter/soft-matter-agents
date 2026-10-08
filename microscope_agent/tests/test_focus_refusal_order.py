"""Card 066: each focus refusal shows its own reason, with the encoder read around it.

    python -m unittest microscope_agent/tests/test_focus_refusal_order.py

The gate checks, in order: approval, the hand-over lens, the limits and the
range, focus hold, and only then the method's readiness (the ceiling, the
thresholds, the decider), then the first Z. A gap ceiling -- which stays a
gap until the bench count is in the store -- must not mask the refusal the
plan actually fails. Mock only; every value is a TEST value in a temporary
scratch root.
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
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_card066_under_test", SRC / "operator.py")
orch = op.orch
base = _load("_focus_plan_tests_for_066", TESTS / "test_focus_plan_and_scratch_root.py")

PFS = {"device": "PFS", "property": "State", "values": ["Off"],
       "confirmation": {"kind": "carried_over", "from": "TEST", "on": "2026-10-08"}}
Z_PARKED = 150.0          # TEST: where the mock encoder reads before the gate


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = base._scratch(Path(self.tmp.name))
        self._saved = op.RUN_LOCK_PATH, op.authorise, orch.Orchestrator.__init__
        op.RUN_LOCK_PATH = Path(self.tmp.name) / "run.lock"
        self.addCleanup(self._restore)
        self.approved = True
        self.pfs_reading = "Off"
        real = self._saved[1]
        op.authorise = lambda plan, approvals=None: (op.Authorisation(
            True, ["test: approved"], "appr-test", "plan_approval", max_tier=2)
            if self.approved else op.Authorisation(False, ["test: no approval for this revision"]))
        init = self._saved[2]
        test = self

        def configured(s, *a, **k):
            init(s, *a, **k)
            m = s.module_for("stand_ti2e")
            m.reset()
            m.FRAME_SHAPE, m.FOCUS_Z_UM = (64, 64), 105.0
            m.apply({"settings": {"PFS": {"State": test.pfs_reading}}})
            m.focus_z_move(Z_PARKED)            # TEST scaffolding: give the mock encoder a reading
            s.plan_authoriser = op.authorise
        orch.Orchestrator.__init__ = configured
        self.plan = copy.deepcopy(base.PLAN)
        self.plan["focus_search"]["camera_ceiling"] = {"gap": "camera_full_scale_per_readout"}
        self.plan["kb_gaps"] = [{"gap_id": "camera_full_scale_per_readout", "looked_for": "TEST",
                                 "where": "TEST"}]
        self.lens = "40x"
        self.n = 0

    def _restore(self):
        op.RUN_LOCK_PATH, op.authorise, orch.Orchestrator.__init__ = self._saved

    def envelope(self, limits=True, pfs=True):
        env = self.root / "microscope_agent" / "envelope" / "safety.json"
        doc = json.loads(env.read_text())
        lim = doc["targets"][0]["limits"]
        if not limits:
            lim.pop("focus_z_40x_min", None)
            lim.pop("focus_z_40x_max", None)
        else:
            lim["focus_z_40x_min"] = {"value": 90, "unit": "um", "bounds": "min", "note": "TEST"}
            lim["focus_z_40x_max"] = {"value": 110, "unit": "um", "bounds": "max", "note": "TEST"}
        if pfs:
            lim["pfs_not_engaged"] = PFS
        else:
            lim.pop("pfs_not_engaged", None)
        env.write_text(json.dumps(doc))

    def refusal(self):
        """Run the plan; return (reason, the refusal event)."""
        self.n += 1
        run_id = f"run-test-066-{self.n}"
        path = Path(self.tmp.name) / f"plan-{self.n}.json"
        path.write_text(json.dumps(self.plan))
        try:
            op.run(path, run_id, backend="mock", handover={"objective": self.lens}, root=self.root)
        except (op.Refusal, orch.InterlockError) as exc:
            reason = str(exc)
        else:
            return None, None
        ev = self.root / "microscope_agent" / "runs" / run_id / "events.jsonl"
        lines = [json.loads(l) for l in ev.read_text(encoding="utf-8").splitlines()] if ev.exists() else []
        refused = [e for e in lines if e.get("event") == "focus_search_refused"]
        self.assertFalse([e for e in lines if e.get("event") == "focus_search_command"],
                         "a refusal sent a Z command")
        return reason, (refused[-1] if refused else None)


class TheRefusalNamesItsOwnReason(_Base):
    def test_no_limit_is_named_not_the_ceiling(self):
        self.envelope(limits=False)
        reason, _ = self.refusal()
        self.assertIn("focus_z_40x_min", reason)

    def test_no_focus_hold_reading_is_named(self):
        self.envelope(pfs=False)
        reason, _ = self.refusal()
        self.assertIn("pfs_not_engaged", reason)

    def test_focus_hold_engaged_is_named(self):
        self.envelope()
        self.pfs_reading = "On"
        reason, _ = self.refusal()
        self.assertIn("PFS reads PFS.State = 'On'", reason)

    def test_the_ceiling_only_when_every_safety_check_passes(self):
        self.envelope()
        reason, _ = self.refusal()
        self.assertIn("camera_ceiling is the gap", reason)


class TheEncoderIsReadAroundEveryRefusal(_Base):
    def test_z_before_and_at_refusal(self):
        for setup in (lambda: self.envelope(limits=False), lambda: self.envelope(pfs=False),
                      lambda: self.envelope()):
            setup()
            _, event = self.refusal()
            self.assertIsNotNone(event)
            self.assertEqual((event["z_before_um"], event["z_at_refusal_um"]), (Z_PARKED, Z_PARKED))

    def test_a_failed_read_is_recorded_and_still_refuses(self):
        self.envelope(limits=False)
        init = orch.Orchestrator.__init__

        def broken(s, *a, **k):
            init(s, *a, **k)
            s.module_for("stand_ti2e").read_z = lambda: (_ for _ in ()).throw(OSError("no encoder"))
        orch.Orchestrator.__init__ = broken
        reason, event = self.refusal()
        self.assertIn("focus_z_40x_min", reason)
        self.assertIsNone(event["z_before_um"])
        self.assertIn("no encoder", event["z_read_failed"])


class TheOrderIsFixed(_Base):
    def test_walk_the_six_checks(self):
        # Start failing everything, fix one check at a time, and the refusal
        # moves to the next check in the card's order.
        self.approved = False
        self.lens = "60x"
        self.envelope(limits=False, pfs=False)
        self.pfs_reading = "On"
        seen = []
        reason, _ = self.refusal(); seen.append(reason)                      # 1 approval
        self.approved = True
        reason, _ = self.refusal(); seen.append(reason)                      # 2 lens
        self.lens = "40x"
        reason, _ = self.refusal(); seen.append(reason)                      # 3 limits
        self.envelope(limits=True, pfs=False)
        reason, _ = self.refusal(); seen.append(reason)                      # 4a focus hold declared
        self.envelope(limits=True, pfs=True)
        reason, _ = self.refusal(); seen.append(reason)                      # 4b focus hold reading
        self.pfs_reading = "Off"
        reason, _ = self.refusal(); seen.append(reason)                      # 5 method: the ceiling
        for got, want in zip(seen, ("approval", "60x", "focus_z_40x_min", "pfs_not_engaged",
                                    "'On'", "camera_ceiling is the gap")):
            self.assertIn(want, got)
        # 6: with a sourced ceiling the gate reaches the first Z command, and a
        # depth of field that is a gap does not refuse the run.
        self.plan["focus_search"]["camera_ceiling"] = {"number": "camera_full_scale"}
        self.plan["focus_search"]["success"] = {"depth_of_field": {"gap": "dof_test"}}
        path = Path(self.tmp.name) / "plan-go.json"
        path.write_text(json.dumps(self.plan))
        op.run(path, "run-test-066-go", backend="mock", handover={"objective": "40x"}, root=self.root)
        ev = self.root / "microscope_agent" / "runs" / "run-test-066-go" / "events.jsonl"
        lines = [json.loads(l) for l in ev.read_text(encoding="utf-8").splitlines()]
        self.assertTrue([e for e in lines if e.get("event") == "focus_search_command"])
        dof = [e for e in lines if e.get("event") == "focus_success_not_judgeable"]
        self.assertTrue(dof and "dof_test" in dof[0]["gap"])


if __name__ == "__main__":
    unittest.main()
