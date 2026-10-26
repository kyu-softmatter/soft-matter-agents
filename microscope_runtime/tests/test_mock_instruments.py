"""Card 086 items 2, 3, 4 and 6: what the mock shows of the piezo, the trap, the confocal and the light path.

    python -m unittest tests.test_mock_instruments

The mock stands in for instruments the Instruments tab reads while a run is under way, so it has to
behave in the three ways that matter to a reader: a position read mid-move is somewhere between
start and end (never a jump, never `not read`); a tweezers read-back is empty, because the Tweez 300
interface has none; and an element nobody set reads as unset, never as a value the mock made up.
The mock holds no policy: what software may command is the allow-list, and these tests check that
the allow-list's refusals still reach the mock's callers whole, with the mock's state untouched.

Every constant the mock reads is synthetic, set here by name, and implies nothing about a stage.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_mock_instruments", SRC / "operator.py")
orch = op.orch
orch._OPERATOR = op


# --- fixtures, copied from test_operation_plan and test_trap_steps ----------- #

def step_plan(target_um=100, axis="x"):
    """One absolute step on the piezo: a single point, so the move is the stage's own motion."""
    moves = [{"id": "step_x", "axis": axis, "kind": "step", "target_um": target_um, "role": "approach"}]
    return {
        "card": "plan", "schema_version": "0.1", "id": "plan-mic-20261026-990-r1",
        "qid": "mic-20261026-990", "revision": 1, "status": "DRAFT", "numbers": [],
        "purpose": "verify", "intent": "confirm",
        "operation": {"device": "piezo_stage", "verifies": "test fixture, twenty characters long",
                      "falsified_by": "test fixture, twenty characters long",
                      "read_back": "before_and_after_each_move", "moves": moves},
        "actions": [{"id": m["id"], "device": "piezo_stage", "action": "move_absolute",
                     "reversible": True, "parameters": [], "tier": 1} for m in moves],
        "envelope_check": {"checked_against": ["piezo_x_position_min", "piezo_x_position_max"],
                           "status": "inside"},
        "targets": [{"metric": "position_readback_error", "kind": "uncertainty", "value": 1,
                     "unit": "um"}],
        "stop_criteria": [{"id": "sc_readback", "metric": "position_readback_error",
                           "comparator": ">", "target": "position_readback_error",
                           "on_met": "fault", "statement": "stop on a read-back outside tolerance"}],
        "success_criteria": [], "open_risks": [],
    }


def limit(value, unit, bounds):
    return {"value": value, "unit": unit, "bounds": bounds,
            "confirmation": {"kind": "carried_over", "from": "test", "on": "2026-09-25"}}


def trap_safety():
    limits = {
        "tweezers_trap_position_100x_min": limit(-40, "um", "min"),
        "tweezers_trap_position_100x_max": limit(40, "um", "max"),
        "tweezers_trap_strength_min": limit(0, "1", "min"),
        "tweezers_trap_strength_max": limit(1, "1", "max"),
        "tweezers_trap_step_max": limit(1, "um", "max"),
    }
    return {"policy_version": "test", "targets": [{"target": "bench", "limits": limits}]}


def trap_plan():
    steps = [
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
        "trap_steps": {"device": "optical_tweezers", "objective": "100x", "read_back": "none",
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


HANDOVER = {"objective": "100x",
            "tweezers_calibration": {"objective": "100x", "stated_by": "test",
                                     "pixel_to_um": "test scaffolding"}}


def approve(p):
    h = op._contracts_validate().plan_hash(p)
    return [{"card": "plan_approval", "id": "appr-test", "plan_id": p["id"],
             "plan_revision": p["revision"], "plan_hash": h, "__path": "test"}]


#: python_serial._run_trajectory's result, key by key. The mock's answer must not carry a key a
#: reader of the real one would not find, or a screen written against the mock reads a field the
#: instrument never sends.
SERIAL_KEYS = {"move", "axis", "channel", "before_um", "after_um", "points_sent", "points_planned",
               "late_points", "dt_s", "samples", "settle", "settle_wait_s", "verified", "disagreed",
               "security_level_after", "backend"}
SERIAL_SAMPLE_KEYS = {"i", "t_planned_s", "t_sent_s", "target_um", "measured_um", "late"}


class Base(unittest.TestCase):
    def setUp(self):
        self._approvals, self._safety = op.approvals_on_disk, op.load_safety
        self.o = orch.Orchestrator(backend="mock")
        self.o.handover = dict(HANDOVER)
        self.m = self.o.module_for("piezo_stage")       # the one mock module every channel shares
        self.m.reset()

    def tearDown(self):
        op.approvals_on_disk, op.load_safety = self._approvals, self._safety

    def rows(self, out):
        return [r for batch in out for rows in batch["results"].values() for r in rows]

    def events(self, name, **match):
        return [e for e in self.o.log if e.get("event") == name
                and all(e.get(k) == v for k, v in match.items())]


# --- item 2: the piezo moves in time, and a read mid-move is between ---------- #

class PiezoMidMove(Base):
    def dispatch(self, p):
        op.approvals_on_disk = lambda: approve(p)
        return self.o.dispatch(op.derive_commands(p), plan=p)

    def poll_while(self, run):
        """Take a watcher snapshot every few ms while `run()` goes; return the piezo readings."""
        self.o._preflight_state["piezo_stage"] = {}
        readings, stop, started = [], threading.Event(), threading.Event()

        def poll():
            while not stop.is_set():
                readings.append(self.o.watcher_snapshot()["piezo_stage"])
                started.set()
                time.sleep(0.004)

        t = threading.Thread(target=poll, daemon=True)
        t.start()
        self.assertTrue(started.wait(5))
        try:
            result = run()
        finally:
            time.sleep(0.03)
            stop.set()
            t.join(5)
        return result, readings

    def test_a_read_during_the_move_is_between_start_and_end_and_never_a_jump(self):
        self.m.PIEZO_RATE_UM_PER_S = 500.0              # 100 um takes 0.2 s
        out, readings = self.poll_while(lambda: self.dispatch(step_plan(100)))
        self.assertTrue(all(not r.get("not_read") for r in readings),
                        f"a read during the move was not taken: {[r for r in readings if r.get('not_read')][:1]}")
        xs = [r["position_um"]["x"] for r in readings]
        self.assertTrue(all(-1e-9 <= x <= 100 + 1e-9 for x in xs), xs)
        self.assertEqual(xs, sorted(xs), "the position went backwards during a one-way move")
        self.assertTrue(any(5 < x < 95 for x in xs), f"no read caught the stage in motion: {xs}")
        self.assertTrue(any(r.get("moving") for r in readings))
        self.assertAlmostEqual(xs[-1], 100, delta=1)
        self.assertFalse(readings[-1]["moving"])

    def test_the_move_is_judged_by_a_read_back_and_says_so(self):
        self.m.PIEZO_RATE_UM_PER_S = 2000.0
        out = self.dispatch(step_plan(100))
        row = self.rows(out)[0]
        self.assertEqual(row["verification"], "readback")
        self.assertTrue(row["returned"]["verified"])
        self.assertFalse(row["returned"]["disagreed"])
        self.assertEqual(row["returned"]["backend"], "mock")
        self.assertEqual(row["returned"]["before_um"], 0.0)

    def test_a_stage_too_slow_to_arrive_disagrees_and_is_not_a_read_back(self):
        self.m.PIEZO_RATE_UM_PER_S = 10.0
        self.m.PIEZO_SETTLE_WAIT_S = 0.05
        out = self.dispatch(step_plan(100))
        row = self.rows(out)[0]
        self.assertTrue(row["returned"]["disagreed"])
        self.assertNotEqual(row["verification"], "readback")
        self.assertIs(row["ok"], False)

    def test_the_result_has_the_real_ones_keys_and_no_others(self):
        self.m.PIEZO_RATE_UM_PER_S = 2000.0
        returned = self.rows(self.dispatch(step_plan(50)))[0]["returned"]
        self.assertLessEqual(set(returned), SERIAL_KEYS)
        for sample in returned["samples"]:
            self.assertLessEqual(set(sample), SERIAL_SAMPLE_KEYS)
        self.assertEqual(returned["points_sent"], returned["points_planned"])

    def test_the_applied_move_does_not_land_in_the_generic_state(self):
        """Not `_STATE.update(params)`: a trajectory is not a state the stage holds."""
        self.m.PIEZO_RATE_UM_PER_S = 2000.0
        self.dispatch(step_plan(50))
        self.assertEqual(self.m._STATE, {})

    def test_the_lock_is_not_held_across_the_move(self):
        self.m.PIEZO_RATE_UM_PER_S = 200.0
        self.o._preflight_state["piezo_stage"] = {}
        box = {}
        t = threading.Thread(target=lambda: box.update(out=self.dispatch(step_plan(60))), daemon=True)
        t.start()
        deadline = time.monotonic() + 5.0
        while not self.m._piezo_read()["moving"] and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertTrue(self.m._piezo_read()["moving"], "the move never began, so the lock was not tested")
        self.assertTrue(self.m._LOCK.acquire(blocking=False), "a move holds the mock's lock")
        self.m._LOCK.release()
        t.join(10)


# --- item 3: the trap has no read-back, and the mock does not invent one ------ #

class TrapIsBlind(Base):
    def run_trap(self):
        p = trap_plan()
        op.approvals_on_disk = lambda: approve(p)
        op.load_safety = lambda: trap_safety()
        cmds = op.derive_trap_steps(p)
        return cmds, self.o.dispatch(cmds, plan=p)

    def test_every_trap_step_is_unverified_and_echoes_what_was_sent(self):
        cmds, out = self.run_trap()
        rows = [r for r in self.rows(out)]
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r["verification"] == "none" for r in rows))
        # The dispatcher ranks a power-lowering command first, so rows are not in the plan's order.
        self.assertEqual(sorted(json.dumps(r["returned"]["commands_sent"]) for r in rows),
                         sorted(json.dumps(c.params["commands"]) for c in cmds))
        for row in rows:
            self.assertNotIn("verified", row["returned"])
            self.assertNotIn("disagreed", row["returned"])
        applies = self.events("apply", channel="optical_tweezers")
        self.assertEqual(len(applies), 5)
        self.assertTrue(all(e["verification"] == "none" for e in applies))

    def test_a_read_of_the_trap_offers_no_position_and_no_state(self):
        self.run_trap()
        got = self.m.read_for("optical_tweezers")
        self.assertIs(got["read_back"], False)
        self.assertEqual(got["verification"], "none")
        self.assertNotIn("position_um", got)
        self.assertNotIn("state", got)
        self.assertNotIn("commands_sent", got)

    def test_the_watcher_gets_the_same_empty_read(self):
        self.run_trap()
        self.o._preflight_state["optical_tweezers"] = {}
        got = self.o.watcher_snapshot()["optical_tweezers"]
        self.assertNotIn("state", got)
        self.assertNotIn("position_um", got)
        self.assertEqual(got["verification"], "none")


# --- items 4 and 6: elements nobody set read as unset; refused devices stay refused --- #

class ElementsAreReadable(Base):
    CHANNELS = ("confocal_csuw1", "stand_ti2e")

    def test_every_registry_element_is_reported_and_none_is_invented(self):
        for cid in self.CHANNELS:
            ids = self.o.channels[cid].element_ids()
            got = self.m.read_for(cid, elements=ids)
            self.assertEqual(sorted(got["elements"]), sorted(ids), cid)
            self.assertTrue(all(v is None for v in got["elements"].values()), (cid, got["elements"]))

    def test_the_watcher_passes_the_registry_ids(self):
        self.o._preflight_state["confocal_csuw1"] = {}
        got = self.o.watcher_snapshot()["confocal_csuw1"]
        self.assertEqual(sorted(got["elements"]), sorted(self.o.channels["confocal_csuw1"].element_ids()))
        self.assertIn("note", got)

    def test_a_hand_set_element_reads_back_and_only_that_one(self):
        self.o.set_element_by_hand("confocal_csuw1", "csuw1_dichroic", "position 2")
        ids = self.o.channels["confocal_csuw1"].element_ids()
        got = self.m.read_for("confocal_csuw1", elements=ids)["elements"]
        self.assertEqual(got["csuw1_dichroic"], "position 2")
        self.assertTrue(all(v is None for k, v in got.items() if k != "csuw1_dichroic"))
        self.assertEqual(len(self.events("element_set_by_hand")), 1)

    def test_a_hand_setting_is_not_a_command_and_is_not_in_the_apply_log(self):
        self.o.set_element_by_hand("stand_ti2e", "nosepiece", "2")
        self.assertEqual(self.events("apply"), [])

    def test_set_by_hand_is_refused_for_what_the_registry_does_not_hold(self):
        with self.assertRaises(orch.GapError):
            self.o.set_element_by_hand("confocal_csuw1", "no_such_element", "x")
        with self.assertRaises(orch.GapError):
            self.o.set_element_by_hand("confocal_csuw1", "nosepiece", "2")     # another channel's
        with self.assertRaises(orch.GapError):
            self.o.set_element_by_hand("no_such_channel", "nosepiece", "2")

    def test_it_is_refused_on_a_real_backend(self):
        real = orch.Orchestrator(backend="hardware")
        with self.assertRaises(orch.InterlockError):
            real.set_element_by_hand("confocal_csuw1", "csuw1_dichroic", "x")

    def test_apply_never_sets_an_element(self):
        self.m.apply_for("confocal_csuw1", {"csuw1_dichroic": {"value": "x", "from": "t"}})
        self.m.apply({"nosepiece": {"value": "2", "from": "t"}})
        for cid in self.CHANNELS:
            got = self.m.read_for(cid, elements=self.o.channels[cid].element_ids())["elements"]
            self.assertTrue(all(v is None for v in got.values()), (cid, got))

    def test_reset_forgets_what_a_hand_set(self):
        self.o.set_element_by_hand("confocal_csuw1", "csuw1_dichroic", "x")
        self.m.reset()
        got = self.m.read_for("confocal_csuw1", elements=["csuw1_dichroic"])["elements"]
        self.assertEqual(got, {"csuw1_dichroic": None})

    def test_a_channel_with_nothing_special_reads_as_it_always_did(self):
        got = self.m.read_for("dmd")
        self.assertEqual(sorted(got), ["aborted", "backend", "state"])


class RefusedDevicesStayRefused(Base):
    """The mock does not widen the allow-list: a command reaching any of these is refused whole."""

    def mm(self):
        return self.o._device_module("micromanager", needed_by="test")

    def test_every_named_refusal_stops_the_plan_with_the_instruments_own_words(self):
        mm = self.mm()
        for device in mm.NAMED_REFUSALS:
            cmd = orch.Command(channel="confocal_csuw1", action="set_x",
                               params={"settings": {device: {"State": 1}}}, from_field="actions[a1]")
            with self.assertRaises(orch.InterlockError) as ctx:
                self.o.dispatch([cmd], plan=None)
            why = mm.refusal(device, "State", "setProperty", 1)
            self.assertTrue(why, device)
            self.assertIn(why, str(ctx.exception), device)
        self.assertEqual(self.m._STATE, {})
        self.assertEqual(self.events("apply"), [])

    def test_a_registry_element_is_not_a_device_software_may_command(self):
        for cid in ("confocal_csuw1", "stand_ti2e"):
            for element in self.o.channels[cid].element_ids():
                cmd = orch.Command(channel=cid, element=element, action=f"select_{element}",
                                   params={element: {"value": "1", "from": "t"}},
                                   from_field=f"system_configuration.selectors[{element}]")
                with self.assertRaises(orch.InterlockError, msg=f"{cid}.{element}"):
                    self.o.dispatch([cmd], plan=None)
        self.assertEqual(self.events("apply"), [])


class LightPath(Base):
    SELECTORS = ["filter_turret_1", "filter_turret_2", "light_path_port", "filter_wheel_em1",
                 "filter_wheel_em2", "csuw1_dichroic", "csuw1_port"]

    def test_a_selector_plan_is_refused_whole_and_nothing_moves(self):
        p = {"system_configuration": {"selectors": [{"element": e, "value": "1"} for e in self.SELECTORS]}}
        cmds = op.derive_commands(p)
        self.assertEqual(len(cmds), len(self.SELECTORS))
        with self.assertRaises(orch.InterlockError) as ctx:
            self.o.dispatch(cmds, plan=p)
        self.assertIn(f"{len(self.SELECTORS)} refusal(s)", str(ctx.exception))
        self.assertEqual(self.events("apply"), [])
        self.assertEqual(self.m._STATE, {})
        for cid in ("confocal_csuw1", "stand_ti2e"):
            got = self.m.read_for(cid, elements=self.o.channels[cid].element_ids())["elements"]
            self.assertTrue(all(v is None for v in got.values()))

    def test_the_names_software_may_command_pass_the_check(self):
        cmds = [
            orch.Command(channel="Aura", action="set", params={"settings": {"Aura": {"State": 1}}},
                         from_field="actions[a1]"),
            orch.Command(channel="Kinetix_red", action="set", params={"settings": {}},
                         from_field="actions[a2]"),
            orch.Command(channel="DiaLamp", action="set",
                         params={"settings": {"DiaLamp": {"State": 1, "Intensity": 5}}},
                         from_field="actions[a3]"),
            orch.Command(channel="Core", action="set",
                         params={"settings": {"Core": {"AutoShutter": "0", "Camera": "Kinetix_red",
                                                       "Shutter": "LightEngine"}}},
                         from_field="actions[a4]"),
        ]
        self.o.check_software_motion(cmds)
        self.assertEqual(len(self.events("software_motion_checked")), 1)
        self.assertEqual(self.events("software_motion_refused"), [])


class NosepieceInterlock(Base):
    """Called directly: no plan can reach this check, because the nosepiece, the PFS and the Z drive
    are each refused by the allow-list first. These are the check's own cases."""

    def command(self, value="2"):
        return orch.Command(channel="stand_ti2e", element="nosepiece", action="select_nosepiece",
                            params={"nosepiece": {"value": value, "from": "test"}},
                            from_field="system_configuration.selectors[nosepiece]")

    def refused(self, completed):
        self.o._completed = set(completed)
        with self.assertRaises(orch.InterlockError) as ctx:
            self.o.check_turret_rotation_allowed(self.command())
        return str(ctx.exception)

    def test_nothing_done_names_both_the_stabiliser_and_the_retract(self):
        text = self.refused([])
        self.assertIn("is not disabled", text)
        self.assertIn("not retracted", text)

    def test_the_stabiliser_alone_is_not_enough_and_the_retract_is_named(self):
        text = self.refused([self.o.STABILISER])
        self.assertNotIn("is not disabled", text)
        self.assertIn("not retracted", text)

    def test_the_retract_alone_is_not_enough_and_the_stabiliser_is_named(self):
        text = self.refused(["z_drive"])
        self.assertIn("is not disabled", text)
        self.assertNotIn("not retracted", text)

    def test_both_verified_lets_it_through(self):
        self.o._completed = {self.o.STABILISER, "z_drive"}
        self.o.check_turret_rotation_allowed(self.command())

    def test_the_mock_gives_no_seated_position_so_the_default_is_to_refuse(self):
        self.assertIsNone(self.o._preflight_state.get("stand_ti2e", {}).get("nosepiece"))
        self.refused([])

    def test_a_seated_position_equal_to_the_commanded_one_is_no_rotation(self):
        self.o._preflight_state["stand_ti2e"] = {"nosepiece": "2"}
        self.o._completed = set()
        self.o.check_turret_rotation_allowed(self.command("2"))
        self.assertEqual(len(self.events("turret_no_rotation")), 1)

    def test_a_different_commanded_position_still_refuses(self):
        self.o._preflight_state["stand_ti2e"] = {"nosepiece": "2"}
        self.o._completed = set()
        with self.assertRaises(orch.InterlockError):
            self.o.check_turret_rotation_allowed(self.command("3"))


if __name__ == "__main__":
    unittest.main()
