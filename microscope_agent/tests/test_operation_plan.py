"""Card 040: the dispatcher runs an operation plan. Nothing here touches hardware.

    python -m unittest microscope_agent/tests/test_operation_plan.py
    python microscope_agent/tests/operation_plan_mutations.py   each behaviour off: its tests must fail

The piezo is the in-process MockLink behind devices/python_serial.py, reached
through the real router with a non-mock backend, so the path under test is the
path a run takes. Approvals are injected rather than read from approvals/, and
the envelope is the person's real envelope/safety.json (piezo X and Y 0 to 600).
"""

from __future__ import annotations

import copy
import importlib.util
import math
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_under_test", SRC / "operator.py")
orch = op.orch
orch._OPERATOR = op                      # one copy: the gate uses the operator under test
serial = _load("_serial_under_test", SRC / "devices" / "python_serial.py")


def plan(moves=None, ppp=8, period=0.08, cycles=1, device="piezo_stage", status="inside"):
    """A small operation plan in the committed shape, fast enough to run in a test."""
    moves = moves if moves is not None else [
        {"id": "approach_x", "axis": "x", "kind": "step", "target_um": 10, "role": "approach"},
        {"id": "sine_x", "axis": "x", "kind": "sine", "centre_um": 300, "amplitude_um": 290,
         "period_s": period, "cycles": cycles, "points_per_period": ppp, "host_timed": True,
         "start": "minimum"},
        {"id": "return_x", "axis": "x", "kind": "step", "target_um": 0.5, "role": "return"},
    ]
    return {
        "card": "plan", "schema_version": "0.1", "id": "plan-mic-20260924-990-r1",
        "qid": "mic-20260924-990", "revision": 1, "status": "DRAFT", "numbers": [],
        "purpose": "verify", "intent": "confirm",
        "operation": {"device": device, "verifies": "test fixture, twenty characters long",
                      "falsified_by": "test fixture, twenty characters long",
                      "read_back": "before_and_after_each_move", "moves": moves},
        "actions": [{"id": m["id"], "device": device, "action": "move_absolute",
                     "reversible": True, "parameters": [], "tier": 1} for m in moves],
        "envelope_check": {"checked_against": ["piezo_x_position_min", "piezo_x_position_max"],
                           "status": status},
        "targets": [{"metric": "position_readback_error", "kind": "uncertainty", "value": 1,
                     "unit": "um"}],
        "stop_criteria": [{"id": "sc_readback", "metric": "position_readback_error",
                           "comparator": ">", "target": "position_readback_error",
                           "on_met": "fault", "statement": "stop on a read-back outside tolerance"}],
        "success_criteria": [], "open_risks": [],
    }


def approve(p):
    """A plan_approval matching this plan's id, revision and hash."""
    h = op._contracts_validate().plan_hash(p)
    return [{"card": "plan_approval", "id": "appr-test", "plan_id": p["id"],
             "plan_revision": p["revision"], "plan_hash": h, "__path": "test"}]


class Lagging(serial.MockLink):
    """Reports a position `lag` short of where it was told to go."""
    lag = 5.0

    def read_position(self, channel):
        return self.position[channel] - (self.lag if self.commands else 0.0)


class Base(unittest.TestCase):
    def setUp(self):
        self._approvals = op.approvals_on_disk
        self.link = serial.MockLink()
        serial._HOLDER.link = self.link

    def tearDown(self):
        op.approvals_on_disk = self._approvals
        serial._HOLDER.link = None

    def orchestrator(self):
        return orch.Orchestrator(backend="hardware")


# --- 1. derivation, and every derived point against the envelope ------------ #

class Derivation(Base):
    def test_sine_points_from_the_integer_index(self):
        p = plan(ppp=200, period=1.0, cycles=5)
        sine = [c for c in op.derive_commands(p) if c.from_field == "operation.moves[sine_x]"][0]
        pts = sine.params["trajectory"]["points"]
        self.assertEqual(len(pts), 1000)
        self.assertEqual(sine.params["trajectory"]["dt_s"], 0.005)
        for i, x in (pts[0], pts[99], pts[999]):
            self.assertAlmostEqual(x, 300 - 290 * math.cos(2 * math.pi * i / 200), places=9)
        self.assertEqual(pts[0][0], 1)

    def test_sine_must_start_where_the_step_before_it_ends(self):
        p = plan()
        p["operation"]["moves"][0]["target_um"] = 12
        with self.assertRaises(op.Refusal):
            op.derive_commands(p)

    def test_a_point_outside_the_envelope_refuses_and_names_the_disagreement(self):
        p = plan()
        p["operation"]["moves"][1]["amplitude_um"] = 350        # reaches -50 and 650
        p["operation"]["moves"][0]["target_um"] = -50
        cmds = op.derive_commands(p)
        with self.assertRaises(op.Refusal) as ctx:
            op.check_operation_points(p, cmds, op.load_safety())
        self.assertIn("disagrees", str(ctx.exception))

    def test_a_missing_limit_refuses(self):
        p = plan()
        with self.assertRaises(op.Refusal):
            op.check_operation_points(p, op.derive_commands(p), {"targets": []})


# --- 2. read back before and after each move, and stop outside tolerance ---- #

class ReadBack(Base):
    def run_dispatch(self, p):
        op.approvals_on_disk = lambda: approve(p)
        o = self.orchestrator()
        return o, o.dispatch(op.derive_commands(p), plan=p)

    def rows(self, out):
        return [r for batch in out for rows in batch["results"].values() for r in rows]

    def test_within_tolerance_is_readback_and_every_move_runs(self):
        o, out = self.run_dispatch(plan())
        rows = self.rows(out)
        self.assertEqual([r.get("verification") for r in rows], ["readback"] * 3)
        sine = rows[1]["returned"]
        self.assertEqual(sine["points_sent"], 8)
        self.assertIn("measured_um", sine["samples"][0])

    def test_outside_tolerance_stops_before_the_next_move(self):
        serial._HOLDER.link = Lagging()
        o, out = self.run_dispatch(plan())
        rows = self.rows(out)
        self.assertIs(rows[0].get("ok"), False)
        self.assertTrue(all(r.get("skipped") == "aborted" for r in rows[1:]),
                        "a move after a failed read-back still went out")


# --- 3. the router reaches the person's two named blind channels only ------- #

class Router(Base):
    def test_tweezers_reach_their_wrapper_not_the_manual_sheet(self):
        o = self.orchestrator()
        self.assertNotEqual(o.module_for("optical_tweezers").__name__, "_dev_manual")

    def test_any_other_blind_channel_still_goes_to_the_manual_sheet(self):
        o = self.orchestrator()
        o.channels["dmd"] = copy.copy(o.channels["dmd"])
        o.channels["dmd"].read_back = False
        self.assertEqual(o.module_for("dmd").__name__, "_dev_manual")


# --- 4. the allow-list, and exactly where it does not bind ------------------ #

class Exemption(Base):
    def check(self, p, cmds):
        o = self.orchestrator()
        o.check_software_motion_for(p, cmds)
        return o

    def test_approved_piezo_x_moves_are_exempt_and_logged(self):
        p = plan()
        op.approvals_on_disk = lambda: approve(p)
        o = self.check(p, op.derive_commands(p))
        self.assertEqual(sum(e.get("event") == "software_motion_exempt" for e in o.log), 3)

    def test_piezo_z_operation_move_is_refused(self):
        p = plan(moves=[{"id": "z_find", "axis": "z", "kind": "step", "target_um": 1,
                         "role": "direction_finding"}])
        op.approvals_on_disk = lambda: approve(p)
        with self.assertRaises(orch.InterlockError):
            self.check(p, op.derive_commands(p))

    def test_piezo_x_from_a_plan_without_operation_is_refused(self):
        p = plan()
        cmds = op.derive_commands(p)
        del p["operation"]
        # Approved, so the plan's STRUCTURE is the only thing refusing it.
        op.approvals_on_disk = lambda: approve(p)
        with self.assertRaises(orch.InterlockError):
            self.check(p, cmds)

    def test_a_micromanager_command_inside_an_operation_plan_meets_the_allow_list(self):
        p = plan()
        op.approvals_on_disk = lambda: approve(p)
        cmds = op.derive_commands(p) + [orch.Command(channel="Nosepiece", action="setState",
                                                     from_field="operation.moves[approach_x]")]
        with self.assertRaises(orch.InterlockError):
            self.check(p, cmds)

    def test_a_hand_built_piezo_command_with_no_approved_plan_is_refused(self):
        p = plan()
        op.approvals_on_disk = lambda: []
        with self.assertRaises(orch.InterlockError):
            self.check(p, op.derive_commands(p))


if __name__ == "__main__":
    unittest.main()
