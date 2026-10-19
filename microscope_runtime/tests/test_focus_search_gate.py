"""Card 055: the focus search is refused at dispatch, and opened only for an approved plan.

    python -m unittest microscope_agent/tests/test_focus_search_gate.py

Mock and a fake MMCore core only; no device is opened. The limits, the PFS
reading and the plan below are SYNTHETIC test values, not this instrument's:
no focus_z_* key exists in envelope/safety.json, and which PFS reading means
"not engaged" is recorded nowhere, so on the real envelope every search
refuses -- which test 1 and the PFS test show.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import sys
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


orch = _load("_orch_focus_search_under_test", SRC / "orchestrator.py")

PFS_DECLARED = ("PFS", "State", "Off")         # SYNTHETIC: the real reading is the person's

PLAN = {
    "id": "plan-mic-test-focus", "revision": 1,
    "actions": [{"id": "focus", "device": "stand_ti2e", "reversible": True}],
    "targets": [{"metric": "position_readback_error", "value": 0.5, "unit": "um"}],
    "stop_criteria": [{"id": "readback", "target": "position_readback_error",
                       "metric": "position_readback_error", "comparator": "<="}],
    "focus_search": {
        "channel": "stand_ti2e", "element": "z_drive", "action": "focus", "objective": "40x",
        "read_back": "encoder", "pfs": "off", "approach_from": "retract",
        "range_um": {"min": 100.0, "max": 110.0}, "step_um": 5.0, "max_moves": 10,
        "branches": ["in_focus", "step_up", "step_down", "no_sample_here", "unsure"],
        "decided_by": "metric_maximum",
    },
}


def _safety(lo=90.0, hi=110.0, objective="40x", pfs=PFS_DECLARED):
    limits = {}
    if pfs:
        # The envelope's pfs_not_engaged (0e3eff1): SYNTHETIC test values.
        limits["pfs_not_engaged"] = {"device": pfs[0], "property": pfs[1], "values": [pfs[2]],
                                     "confirmation": {"kind": "carried_over", "from": "TEST",
                                                      "on": "2026-10-07"}}
    if lo is not None:
        limits[f"focus_z_{objective}_min"] = {"value": lo, "unit": "um", "bounds": "min"}
    if hi is not None:
        limits[f"focus_z_{objective}_max"] = {"value": hi, "unit": "um", "bounds": "max"}
    return {"targets": [{"target": "bench", "limits": limits}]}


class _Approved:
    permitted, reasons = True, ["test: approved"]


class _NotApproved:
    permitted, reasons = False, ["test: no approval covers this revision"]


def _decider(*branches, then=None):
    """Return the given branches in order, then `then` (default in_focus) forever."""
    queue = list(branches)
    seen = []

    def decide(last_read_um):
        seen.append(last_read_um)
        b = queue.pop(0) if queue else (then or "in_focus")
        return b if isinstance(b, dict) else {"branch": b, "confidence": 0.9}
    decide.seen = seen
    return decide


class _Base(unittest.TestCase):
    approved = True
    pfs = PFS_DECLARED

    def setUp(self):
        self.o = orch.Orchestrator(backend="mock")
        self.mock = self.o.module_for("stand_ti2e")
        self.mock.reset()
        self.o.handover["objective"] = "40x"
        op = orch._operator()
        self._saved = (op.authorise,)
        op.authorise = (lambda plan, approvals=None: _Approved()) if self.approved else \
                       (lambda plan, approvals=None: _NotApproved())
        if self.pfs:
            self.mock.apply({"settings": {self.pfs[0]: {self.pfs[1]: self.pfs[2]}}})
        self.plan = copy.deepcopy(PLAN)
        self.writes = []
        original = self.mock.focus_z_move

        def counted(target_um):
            self.writes.append(target_um)
            return original(target_um)
        self.mock.focus_z_move = counted

    def tearDown(self):
        op = orch._operator()
        op.authorise, = self._saved

    def run_search(self, decide, safety=None):
        safety = _safety(pfs=self.pfs) if safety is None else safety
        return self.o.run_focus_search(self.plan, decide, load_safety=lambda: safety)

    def events(self, name):
        return [e for e in self.o.log if e.get("event") == name]


class T01NoLimitsRefuses(_Base):
    def test_no_focus_z_keys_refuses_before_any_z_command(self):
        with self.assertRaises(orch.InterlockError) as caught:
            self.run_search(_decider(), safety={"targets": [{"target": "bench", "limits": {}}]})
        self.assertIn("focus_z_40x_min", str(caught.exception))
        self.assertEqual(self.writes, [])

    def test_only_the_max_key_present_still_refuses(self):
        with self.assertRaises(orch.InterlockError) as caught:
            self.run_search(_decider(), safety=_safety(lo=None))
        self.assertIn("focus_z_40x_min", str(caught.exception))
        self.assertEqual(self.writes, [])


class T02ObjectiveMustMatch(_Base):
    def test_a_different_objective_refuses(self):
        self.o.handover["objective"] = "60x"
        with self.assertRaises(orch.InterlockError) as caught:
            self.run_search(_decider())
        self.assertIn("60x", str(caught.exception))
        self.assertEqual(self.writes, [])

    def test_a_missing_objective_refuses(self):
        self.o.handover.pop("objective")
        with self.assertRaises(orch.InterlockError):
            self.run_search(_decider())
        self.assertEqual(self.writes, [])


class T03PfsEngagedRefuses(_Base):
    def test_pfs_reading_engaged_refuses_with_no_z_write(self):
        self.mock.apply({"settings": {"PFS": {"State": "On"}}})
        with self.assertRaises(orch.InterlockError) as caught:
            self.run_search(_decider())
        self.assertIn("PFS", str(caught.exception))
        self.assertEqual(self.writes, [])


class T03bPfsReadingUndeclaredRefuses(_Base):
    pfs = None

    def test_an_undeclared_pfs_reading_refuses(self):
        with self.assertRaises(orch.InterlockError) as caught:
            self.run_search(_decider())
        self.assertIn("pfs_not_engaged", str(caught.exception))
        self.assertEqual(self.writes, [])

    def test_an_unreadable_pfs_reading_refuses(self):
        # Declared in the envelope, and the mock has never been told any PFS
        # state, so the read comes back None: unreadable refuses (0e3eff1).
        with self.assertRaises(orch.InterlockError) as caught:
            self.run_search(_decider(), safety=_safety(pfs=PFS_DECLARED))
        self.assertIn("PFS", str(caught.exception))
        self.assertEqual(self.writes, [])


class T04NoApprovalNoExemption(_Base):
    approved = False

    def test_the_allow_list_refuses_zdrive(self):
        # Since card 066 the approval is the gate's FIRST check, so an
        # unapproved plan is refused there, before any exemption is asked.
        with self.assertRaises(orch.InterlockError) as caught:
            self.run_search(_decider())
        self.assertIn("not approved", str(caught.exception))
        self.assertEqual(self.writes, [])
        self.assertFalse(self.events("software_motion_exempt"))
        # and the allow-list still refuses a ZDrive command on its own
        bad = orch.Command(channel="stand_ti2e", element="z_drive", action="focus_z_move",
                           params={"target_um": 100.0}, from_field="focus_search.range_um.min")
        with self.assertRaises(orch.InterlockError):
            self.o.check_software_motion_for(self.plan, [bad])
        self.assertTrue(self.events("software_motion_refused"))


class T05OnlyTheDerivation(_Base):
    def test_a_hand_built_z_command_is_refused(self):
        bad = orch.Command(channel="stand_ti2e", element="z_drive", action="focus_z_move",
                           params={"target_um": 105.0}, from_field="focus_search.step_up")
        with self.assertRaises(orch.InterlockError):
            self.o.check_software_motion_for(self.plan, [bad])
        self.assertEqual(self.writes, [])

    def test_a_number_from_the_decider_is_refused(self):
        decide = _decider({"branch": "step_up", "confidence": 0.9, "target_um": 108.0})
        with self.assertRaises(orch.InterlockError):
            self.run_search(decide)
        self.assertEqual(self.writes, [100.0])         # the retract, and nothing after

    def test_a_branch_not_in_branches_is_refused(self):
        self.plan["focus_search"]["branches"] = ["in_focus", "step_up", "unsure"]
        with self.assertRaises(orch.InterlockError):
            self.run_search(_decider("step_down"))
        self.assertEqual(self.writes, [100.0])


class T06OutsideRangeOrLimits(_Base):
    def test_a_target_outside_range_refuses_at_that_step(self):
        self.plan["focus_search"]["range_um"] = {"min": 100.0, "max": 108.0}
        with self.assertRaises(orch.InterlockError):
            self.run_search(_decider("step_up", "step_up"))
        self.assertEqual(self.writes, [100.0, 105.0])

    def test_a_target_outside_the_limits_refuses_at_that_step(self):
        safety = _safety()

        def decide(last):
            if last == 100.0:
                safety["targets"][0]["limits"]["focus_z_40x_min"]["value"] = 100.0
                return {"branch": "step_down", "confidence": 0.9}
            return {"branch": "in_focus", "confidence": 0.9}
        with self.assertRaises(orch.InterlockError):
            self.run_search(decide, safety=safety)
        self.assertEqual(self.writes, [100.0])


class T07LiveClearance(_Base):
    def test_one_step_above_the_max_is_refused_and_recorded(self):
        # range_um ends AT the limit, as preflight requires; the third step_up
        # lands one step_um above both, and the clearance comparison -- made
        # first -- is what refuses it.
        with self.assertRaises(orch.InterlockError) as caught:
            self.run_search(_decider("step_up", "step_up", "step_up"),
                            safety=_safety(hi=110.0))
        self.assertEqual(self.writes, [100.0, 105.0, 110.0])       # exactly at the limit: allowed
        self.assertIn("focus_z_40x_max", str(caught.exception))
        last = self.events("focus_clearance_compared")[-1]
        self.assertEqual((last["target"], last["limit"], last["compared"], last["within"]),
                         (115.0, 110.0, True, False))

    def test_the_max_key_removed_after_preflight_refuses_the_next_step(self):
        safety = _safety()

        def decide(last):
            safety["targets"][0]["limits"].pop("focus_z_40x_max", None)
            return {"branch": "step_up", "confidence": 0.9}
        with self.assertRaises(orch.InterlockError) as caught:
            self.run_search(decide, safety=safety)
        self.assertIn("focus_z_40x_max", str(caught.exception))
        self.assertEqual(self.writes, [100.0])
        self.assertIs(self.events("focus_clearance_compared")[-1]["compared"], False)


class T08MaxMovesIsNotFound(_Base):
    def test_reaching_the_ceiling_ends_as_not_found(self):
        self.plan["focus_search"]["max_moves"] = 2
        result = self.run_search(_decider(then="step_up"))
        self.assertEqual(result["outcome"], "not_found")
        self.assertEqual(self.writes, [100.0, 105.0, 110.0])     # retract + 2 moves

    def test_in_focus_is_the_encoder_read(self):
        result = self.run_search(_decider("step_up", "in_focus"))
        self.assertEqual((result["outcome"], result["z_um"]), ("found", 105.0))

    def test_unsure_is_an_abstention_not_a_miss(self):
        result = self.run_search(_decider("unsure"))
        self.assertEqual(result["outcome"], "unsure")
        self.assertTrue(self.events("focus_search_decision")[-1]["abstention"])


class T09ReadBackOutOfTolerance(_Base):
    def test_a_bad_read_back_stops_before_the_next_move(self):
        original = self.mock.focus_z_move

        def drifting(target_um):
            out = original(target_um)
            if target_um == 105.0:
                out = dict(out, read_um=107.0)
            return out
        self.mock.focus_z_move = drifting
        with self.assertRaises(orch.InterlockError):
            self.run_search(_decider("step_up", "step_up"))
        self.assertTrue(self.events("stop_criterion_violated"))
        self.assertEqual(len(self.events("focus_search_command")), 2)   # retract, one step


class T10RefusalsStillHold(unittest.TestCase):
    def test_named_refusals(self):
        mm = orch.Orchestrator(backend="mock")._device_module("micromanager", needed_by="test")
        self.assertEqual(mm.named_refusals_hold(), [])
        for device in ("ZDrive", "PFS"):
            self.assertIn(device, mm.NAMED_REFUSALS)
            self.assertNotIn(device, mm.SOFTWARE_MAY_COMMAND)

    def test_focus_z_move_is_called_from_one_place_only(self):
        sites = set()
        for path in sorted(SRC.rglob("*.py")):
            for fn in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(fn, ast.FunctionDef):
                    for node in ast.walk(fn):
                        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                                and node.func.attr == "focus_z_move"):
                            sites.add((path.name, fn.name))
        self.assertEqual(sorted(sites), [("orchestrator.py", "_focus_move")])


class _FakeCore:
    def __init__(self):
        self.z = 50.0
        self.writes = []
        self.props = {("PFS", "State"): "Off"}

    def getLoadedDevices(self):
        return ("Core", "ZDrive", "PFS")

    def setPosition(self, device, z):
        self.writes.append((device, z))
        self.z = float(z)

    def getPosition(self, device):
        return self.z

    def getProperty(self, device, prop):
        return self.props[(device, prop)]

    def waitForDevice(self, device):
        return None

    def waitForSystem(self):
        return None


class ThroughMicroManager(_Base):
    def test_the_search_through_a_fake_core(self):
        core = _FakeCore()
        mm = self.o._device_module("micromanager", needed_by="test")
        mm.reset()
        mm._core = lambda: mm.GuardedCore(core)
        self.o.module_for = lambda cid: mm if cid == "stand_ti2e" else self.mock
        result = self.run_search(_decider("step_up", "in_focus"))
        self.assertEqual(core.writes, [("ZDrive", 100.0), ("ZDrive", 105.0)])
        self.assertEqual((result["outcome"], result["z_um"]), ("found", 105.0))
        with self.assertRaises(mm.SoftwareMotionRefused):        # every other path still refused
            mm.GuardedCore(core).setPosition("ZDrive", 1.0)
        self.assertEqual(len(core.writes), 2)


if __name__ == "__main__":
    unittest.main()
