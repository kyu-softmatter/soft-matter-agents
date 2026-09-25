"""Card 049 items 2 and 3: an approved plan's trap steps reach the tweezers, and nothing else does.

    python -m unittest microscope_agent/tests/test_trap_steps.py
    python microscope_agent/tests/trap_steps_mutations.py   each behaviour off: its tests must fail

The tweezers are the real devices/python_tcp.py, reached through the real
router with a non-mock backend, talking to a scripted fake GUI on one end of a
socketpair -- no port, no Tweez300 process. Approvals and the envelope are
injected, because the person's envelope/safety.json is theirs and may be
mid-edit; the injected limits are test scaffolding, not the person's numbers.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_traps_under_test", SRC / "operator.py")
orch = op.orch
orch._OPERATOR = op


def limit(value, unit, bounds):
    return {"value": value, "unit": unit, "bounds": bounds,
            "confirmation": {"kind": "carried_over", "from": "test", "on": "2026-09-25"}}


def safety(objective="100x", **drop):
    """The person's names (policy 8) with test values; `objective` is the one the range is for."""
    limits = {
        f"tweezers_trap_position_{objective}_min": limit(-40, "um", "min"),
        f"tweezers_trap_position_{objective}_max": limit(40, "um", "max"),
        "tweezers_trap_strength_min": limit(0, "1", "min"),
        "tweezers_trap_strength_max": limit(1, "1", "max"),
        "tweezers_trap_step_max": limit(1, "um", "max"),
    }
    for name in drop:
        limits.pop(name)
    return {"policy_version": "test", "targets": [{"target": "bench", "limits": limits}]}


def plan(steps=None, objective="100x"):
    steps = steps if steps is not None else [
        {"id": "make", "kind": "create", "trap": "t1", "x_um": -2, "y_um": 0, "strength": 0.2},
        {"id": "hold_bead", "kind": "hold_for_person", "statement": "the bead is under trap t1"},
        {"id": "light", "kind": "on", "trap": "t1"},
        {"id": "walk1", "kind": "position", "trap": "t1", "x_um": -1, "y_um": 0},
        {"id": "walk2", "kind": "position", "trap": "t1", "x_um": 0, "y_um": 0},
        {"id": "dark", "kind": "off", "trap": "t1"},
    ]
    return {
        "card": "plan", "schema_version": "0.1", "id": "plan-mic-20260925-990-r1",
        "qid": "mic-20260925-990", "revision": 1, "status": "DRAFT", "numbers": [],
        "purpose": "verify", "intent": "confirm",
        "trap_steps": {"device": "optical_tweezers", "objective": objective, "read_back": "none",
                       "verifies": "test fixture, twenty characters long",
                       "falsified_by": "test fixture, twenty characters long", "steps": steps},
        "actions": [{"id": s["id"], "device": "optical_tweezers", "action": f"trap_{s['kind']}",
                     "reversible": True, "parameters": [], "tier": 1}
                    for s in steps if s["kind"] != "hold_for_person"],
        "targets": [{"metric": "trap_step_count", "kind": "count", "value": len(steps), "unit": "1"}],
        "stop_criteria": [{"id": "sc_person", "metric": "trap_step_count", "comparator": ">",
                           "target": "trap_step_count", "on_met": "fault",
                           "statement": "stop when the person does not confirm a hold"}],
        "success_criteria": [], "open_risks": [],
    }


def approve(p):
    h = op._contracts_validate().plan_hash(p)
    return [{"card": "plan_approval", "id": "appr-test", "plan_id": p["id"],
             "plan_revision": p["revision"], "plan_hash": h, "__path": "test"}]


class FakeGUI:
    """Answers every line with the next scripted reply (default 0); None is silence."""

    def __init__(self, replies=()):
        self.replies = list(replies)
        self.received: list[str] = []
        self.ours, self._theirs = socket.socketpair()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        buf = b""
        try:
            while True:
                chunk = self._theirs.recv(1024)
                if not chunk:
                    return
                buf += chunk
                while b"\r\n" in buf:
                    line, buf = buf.split(b"\r\n", 1)
                    self.received.append(line.decode())
                    reply = self.replies.pop(0) if self.replies else 0
                    if reply is not None:
                        self._theirs.sendall(f"{reply}\r\n".encode())
        except OSError:
            return


HANDOVER = {"objective": "100x",
            "tweezers_calibration": {"objective": "100x", "stated_by": "test",
                                     "pixel_to_um": "test scaffolding"}}


class Base(unittest.TestCase):
    def setUp(self):
        self._approvals, self._safety = op.approvals_on_disk, op.load_safety
        op.load_safety = lambda: safety()
        self.dir = tempfile.TemporaryDirectory()
        self.gui = FakeGUI()

    def tearDown(self):
        op.approvals_on_disk, op.load_safety = self._approvals, self._safety
        self.dir.cleanup()

    def link(self):
        return {"host": "fake", "port": 0, "connect_timeout_s": 1, "reply_timeout_s": 0.3,
                "min_gap_s": 0, "busy_retries": 0, "busy_backoff_s": 0,
                "log_path": Path(self.dir.name) / "tweez.jsonl",
                "numbers_from": "test scaffolding, not a measurement", "sock": self.gui.ours}

    def run_plan(self, p, answers=("yes",), handover=None, approved=True):
        if approved:
            op.approvals_on_disk = lambda: approve(p)
        else:
            op.approvals_on_disk = lambda: []
        path = Path(self.dir.name) / "plan.json"
        path.write_text(json.dumps(p))
        answers = list(answers)
        return op.run(path, "run-test", backend="hardware",
                      handover=HANDOVER if handover is None else handover,
                      ask_person=lambda s: answers.pop(0) if answers else None,
                      tweezers_link=self.link())


# --- the derivation --------------------------------------------------------- #

class Derivation(Base):
    def test_positions_are_absolute_never_relative(self):
        lines = [l for c in op.derive_trap_steps(plan()) for l in c.params["commands"]]
        self.assertNotIn("TRAP_POSITION_REL", {l[0] for l in lines})
        self.assertIn(["TRAP_POSITION", "t1", -1.0, 0.0], lines)

    def test_create_sets_position_and_strength_before_anything_turns_it_on(self):
        make = op.derive_trap_steps(plan())[0]
        self.assertEqual([l[0] for l in make.params["commands"]],
                         ["SIMPLE_TRAP_CREATE", "TRAP_POSITION", "TRAP_STRENGTH"])


# --- the envelope checks ------------------------------------------------------ #

class Envelope(Base):
    def check(self, p, objective="100x", env=None):
        return op.check_trap_steps(p, op.derive_trap_steps(p), env or safety(), objective)

    def test_inside_passes(self):
        self.assertTrue(self.check(plan()))

    def test_position_outside_refuses(self):
        # A create alone, so no step size can refuse it: only the range can.
        # With the create inside the default plan, a trap at -41 was also a
        # 40 um step to the next position, and the test passed with the range
        # check switched off -- the mutation harness caught it.
        p = plan(steps=[{"id": "make", "kind": "create", "trap": "t1", "x_um": 0, "y_um": 41,
                         "strength": 0.2}])
        with self.assertRaises(op.Refusal):
            self.check(p)

    def test_missing_limit_refuses(self):
        with self.assertRaises(op.Refusal):
            self.check(plan(), env=safety(tweezers_trap_strength_max=None))

    def test_limit_for_another_objective_refuses(self):
        with self.assertRaises(op.Refusal):
            self.check(plan(), env=safety(objective="60x"))

    def test_no_objective_at_handover_refuses(self):
        with self.assertRaises(op.Refusal):
            self.check(plan(), objective=None)

    def test_plan_for_another_objective_refuses(self):
        with self.assertRaises(op.Refusal):
            self.check(plan(objective="60x"))

    def test_step_larger_than_the_limit_refuses(self):
        p = plan()
        p["trap_steps"]["steps"][3]["x_um"] = 0.5            # -2 -> 0.5 is 2.5 um
        with self.assertRaises(op.Refusal):
            self.check(p)

    def test_a_move_before_the_trap_is_placed_refuses(self):
        p = plan(steps=[{"id": "walk", "kind": "position", "trap": "t1", "x_um": 0, "y_um": 0}])
        with self.assertRaises(op.Refusal):
            self.check(p)

    def test_strength_above_the_limit_refuses(self):
        p = plan()
        p["trap_steps"]["steps"][0]["strength"] = 1.5
        with self.assertRaises(op.Refusal):
            self.check(p)


# --- the exemption ------------------------------------------------------------ #

class Exemption(Base):
    def test_approved_steps_are_exempt_and_logged_blind(self):
        p = plan()
        op.approvals_on_disk = lambda: approve(p)
        o = orch.Orchestrator(backend="mock")
        o.handover = dict(HANDOVER)
        o.check_software_motion_for(p, op.derive_trap_steps(p))
        exempt = [e for e in o.log if e.get("event") == "software_motion_exempt"]
        self.assertEqual(len(exempt), 5)
        self.assertTrue(all(e.get("verification") == "none" for e in exempt))

    def test_without_approval_the_allow_list_refuses_the_tweezers(self):
        p = plan()
        op.approvals_on_disk = lambda: []
        o = orch.Orchestrator(backend="mock")
        o.handover = dict(HANDOVER)
        with self.assertRaises(orch.InterlockError):
            o.check_software_motion_for(p, op.derive_trap_steps(p))

    def test_a_hand_built_command_cannot_ride_the_approved_plan(self):
        p = plan()
        op.approvals_on_disk = lambda: approve(p)
        cmds = op.derive_trap_steps(p)
        cmds[3] = orch.Command(channel="optical_tweezers", action="trap_position",
                               params={"commands": [["TRAP_POSITION", "t1", 30.0, 0.0]],
                                       "step": cmds[3].params["step"]},
                               from_field=cmds[3].from_field)
        o = orch.Orchestrator(backend="mock")
        o.handover = dict(HANDOVER)
        with self.assertRaises(orch.InterlockError):
            o.check_software_motion_for(p, cmds)

    def test_the_run_refuses_an_unapproved_trap_plan(self):
        with self.assertRaises(op.Refusal):
            self.run_plan(plan(), approved=False)


# --- the run, through the real wrapper -------------------------------------- #

class Run(Base):
    def test_steps_go_out_in_the_plans_order(self):
        self.run_plan(plan())
        self.assertEqual(self.gui.received, [
            "TRAP_DELETE __readiness_probe__",
            "SIMPLE_TRAP_CREATE t1", "TRAP_POSITION t1 -2.0 0.0", "TRAP_STRENGTH t1 0.2",
            "TRAP_ON t1", "TRAP_POSITION t1 -1.0 0.0", "TRAP_POSITION t1 0.0 0.0",
            "TRAP_OFF t1",
            # the abort's safe direction is not part of a run that finished
        ][:len(self.gui.received)])
        self.assertEqual(self.gui.received[-1], "TRAP_OFF t1")

    def test_a_hold_without_a_yes_stops_every_later_step(self):
        self.run_plan(plan(), answers=("no",))
        self.assertNotIn("TRAP_ON t1", self.gui.received)
        self.assertNotIn("TRAP_POSITION t1 -1.0 0.0", self.gui.received)

    def test_a_declined_hold_does_not_abort_or_switch_the_laser_off(self):
        # run-20260925-008: a no at a hold aborted, and the abort sent LASER_OFF
        # while the plan said the traps stay on.
        record = self.run_plan(plan(), answers=("no",))
        self.assertNotIn("LASER_OFF", self.gui.received)
        self.assertNotIn("TRAP_OFF t1", self.gui.received)
        events = [e.get("event") for e in record["events"]]
        self.assertNotIn("abort_begin", events)
        self.assertIn("hold_declined", events)

    def test_an_explicit_abort_at_a_hold_aborts(self):
        record = self.run_plan(plan(), answers=("abort",))
        events = [e.get("event") for e in record["events"]]
        self.assertIn("hold_aborted_by_person", events)
        self.assertIn("abort_begin", events)

    def test_no_position_goes_out_without_the_persons_calibration(self):
        with self.assertRaises(orch.InterlockError):
            self.run_plan(plan(), handover={"objective": "100x"})
        self.assertNotIn("SIMPLE_TRAP_CREATE t1", self.gui.received)

    def test_a_calibration_for_another_objective_is_refused(self):
        h = {"objective": "100x", "tweezers_calibration": {"objective": "60x", "stated_by": "t",
                                                           "pixel_to_um": "x"}}
        with self.assertRaises(orch.InterlockError):
            self.run_plan(plan(), handover=h)

    def test_a_rejected_step_still_aborts(self):
        self.gui.replies = [0, 0, 0, -27]
        record = self.run_plan(plan())
        self.assertIn("abort_begin", [e.get("event") for e in record["events"]])

    def test_a_rejected_step_stops_the_plan(self):
        # probe, create, position -> then the strength line is rejected
        self.gui.replies = [0, 0, 0, -27]
        self.run_plan(plan())
        self.assertNotIn("TRAP_ON t1", self.gui.received)

    def test_every_tweezers_dispatch_is_recorded_as_unverified(self):
        record = self.run_plan(plan())
        applies = [e for e in record["events"] if e.get("event") == "apply"
                   and e.get("channel") == "optical_tweezers"]
        self.assertTrue(applies)
        self.assertTrue(all(e.get("verification") == "none" for e in applies))


if __name__ == "__main__":
    unittest.main()
