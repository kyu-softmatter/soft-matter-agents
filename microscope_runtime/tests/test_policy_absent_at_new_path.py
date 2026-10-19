"""Card 080: the moved operator refuses when the policy is absent at the new path.

    python -m unittest microscope_runtime/tests/test_policy_absent_at_new_path.py

The person's policy and approvals are read from microscope_runtime/ with no
fallback to the old folder (plan.md 15). A policy that still sits under
microscope_agent/ -- as the real one does until the person moves it -- must
not satisfy the run. The knowledge snapshot is the one file read from
microscope_agent/, by an explicit path. Mock only: every root here is a
temporary scratch copy and nothing touches an instrument.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_card080_under_test", SRC / "operator.py")
orch = op.orch
lunf = _load("_lunf_card080_under_test", SRC / "devices" / "lunf.py")
serial = _load("_serial_card080_under_test", SRC / "devices" / "python_serial.py")
live_view = _load("_live_view_card080_under_test", SRC / "live_view.py")

POLICY = {"policy_version": "TEST", "targets": [{"target": "bench", "limits": {}}]}


def _old_path_only(tmp: Path) -> Path:
    """A scratch root whose policy and an approval sit ONLY under microscope_agent/."""
    old = tmp / "microscope_agent"
    (old / "envelope").mkdir(parents=True)
    (old / "approvals").mkdir()
    (old / "envelope" / "safety.json").write_text(json.dumps(POLICY))
    (old / "approvals" / "appr-test.json").write_text(json.dumps({"approval": "TEST"}))
    (tmp / "microscope_runtime").mkdir()                 # the runtime's folder exists and is empty
    return tmp


class _Scratch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _old_path_only(Path(self.tmp.name))
        self._agent = op.AGENT
        self.addCleanup(setattr, op, "AGENT", self._agent)


class T1AbsentPolicyRefuses(_Scratch):
    def test_run_refuses_while_the_old_path_holds_a_policy(self):
        plan = Path(self.tmp.name) / "plan.json"
        plan.write_text(json.dumps({"card": "plan", "id": "plan-test-080"}))
        with self.assertRaisesRegex(op.Refusal, "Nothing executes without a safety policy"):
            op.run(plan, "run-test-080", backend="mock", root=self.root)
        self.assertFalse((self.root / "microscope_runtime" / "runs").exists(),
                         "a refused run wrote a run folder")

    def test_load_safety_reads_the_runtime_folder_and_no_other(self):
        op.AGENT = self.root / "microscope_runtime"
        with self.assertRaisesRegex(op.Refusal, "Nothing executes without a safety policy"):
            op.load_safety()

    def test_approvals_are_read_from_the_runtime_folder_and_no_other(self):
        op.AGENT = self.root / "microscope_runtime"
        self.assertEqual(op.approvals_on_disk(), [])
        self.assertEqual(op.approvals_on_disk(self.root / "microscope_runtime"), [])

    def test_the_policy_is_read_once_it_is_in_the_runtime_folder(self):
        folder = self.root / "microscope_runtime" / "envelope"
        folder.mkdir()
        (folder / "safety.json").write_text(json.dumps(POLICY))
        self.assertEqual(op.load_safety(self.root / "microscope_runtime")["policy_version"], "TEST")


class T2Anchors(unittest.TestCase):
    def test_operator_resolves_from_the_runtime_folder(self):
        self.assertEqual(op.AGENT, REPO / "microscope_runtime")
        self.assertEqual(op.agent_root(None), REPO / "microscope_runtime")

    def test_the_snapshot_alone_is_read_from_the_design_folder(self):
        want = REPO / "microscope_agent" / "envelope" / "snapshot.json"
        self.assertEqual(op.SNAPSHOT_PATH, want)
        self.assertEqual(op.snapshot_path(None), want)
        self.assertEqual(orch.SNAPSHOT_PATH, want)
        self.assertEqual(orch.REGISTRY_LOOKUP[0], want)

    def test_a_scratch_root_keeps_the_same_split(self):
        root = Path("scratch")
        self.assertEqual(op.agent_root(root), root / "microscope_runtime")
        self.assertEqual(op.snapshot_path(op.agent_root(root)),
                         root / "microscope_agent" / "envelope" / "snapshot.json")

    def test_device_wrappers_find_the_policy_in_the_runtime_folder(self):
        want = REPO / "microscope_runtime" / "envelope" / "safety.json"
        self.assertEqual(lunf.ENVELOPE_PATH, want)
        self.assertEqual(serial._ENVELOPE, want)

    def test_live_view_defaults_follow_the_runtime_folder(self):
        self.assertEqual(live_view.AGENT, REPO / "microscope_runtime")


if __name__ == "__main__":
    unittest.main()
