"""Card 086 item 7: the mock's connection states.

    python -m unittest tests.test_mock_connection_states

Each mock channel can be set, by a test only and never from the console, to answer, to be absent or
to be busy; a plan run, a live view and a check-now run then write card 085's status file with each
state as it is, so the connection-state page reads only that file.

Mock only. Every list is a TEST FIXTURE in a temporary approvals/ folder and the status file is
written into a temporary folder; nothing here writes microscope_runtime/.runtime_status/ or the
person's real check-now list. The states are synthetic and imply nothing about how a real device
looks when it is unplugged or in use.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_idle_status_and_check_now as t85                    # noqa: E402  (its _Base builds the host)

op = t85.op
orch = t85.orch
CHECK_NOW_LIST = t85.CHECK_NOW_LIST
_with_channels = t85._with_channels


class _States(t85._Base):
    """The host of card 085, with the mock's connection states set on every orchestrator it builds."""
    states: dict = {}

    def _hook(self, o):
        super()._hook(o)
        for cid, state in self.states.items():
            o.set_mock_connection(cid, state)

    def events(self, log, name):
        return [e for e in log["events"] if e.get("event") == name]


# --------------------------------------------------------------------------- #
# 7a. what the mock does in each state
# --------------------------------------------------------------------------- #

class T7aTheMockInEachState(unittest.TestCase):
    def setUp(self):
        self.o = orch.Orchestrator(backend="mock")
        self.m = self.o.module_for("camera_red")

    def test_every_channel_answers_until_something_sets_it(self):
        for cid in self.o.channels:
            self.assertEqual(self.m.connection_of(cid), "answering", cid)
        self.assertEqual(self.m.preflight({"id": "camera_red"})["ready"], True)

    def test_a_state_word_the_mock_does_not_know_is_refused(self):
        for bad in ("unplugged", "", None, 3, "ABSENT"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.m.set_connection("camera_red", bad)
        self.assertEqual(self.m.connection_of("camera_red"), "answering")

    def test_answering_sets_it_back(self):
        self.m.set_connection("camera_red", "absent")
        self.m.set_connection("camera_red", "answering")
        self.assertEqual(self.m.connection_of("camera_red"), "answering")
        self.assertEqual(self.m.read_for("camera_red")["backend"], "mock")

    def test_absent_answers_its_preflight_as_not_ready_and_everything_else_fails(self):
        self.m.set_connection("camera_red", "absent")
        pre = self.m.preflight({"id": "camera_red"})
        self.assertIs(pre["ready"], False)
        self.assertIs(pre["absent"], True)
        self.assertIn("reason", pre)
        for wait in (True, False):
            with self.assertRaises(self.m.DeviceAbsent) as caught:
                self.m.read_for("camera_red", wait=wait)
            self.assertFalse(getattr(caught.exception, "would_wait", False), "absent is not busy")
        with self.assertRaises(self.m.DeviceAbsent):
            self.m.open_for("camera_red")
        self.assertEqual(self.m.open_channels(), [])
        with self.assertRaises(self.m.DeviceAbsent):
            self.m.apply_for("camera_red", {"x": 1})
        self.assertEqual(self.m.read_for("dmd")["backend"], "mock", "another channel is unaffected")

    def test_an_absent_camera_gives_no_frame_and_a_busy_one_still_streams(self):
        self.m.set_connection("camera_red", "absent")
        with self.assertRaises(self.m.DeviceAbsent):
            self.m.snap_for("camera_red")
        with self.assertRaises(self.m.DeviceAbsent):
            self.m.sequence_for("camera_red", 2, lambda i, image, meta: None)
        self.m.snap_for("camera_blue")                          # another camera is unaffected
        self.m.set_connection("camera_red", "busy")             # busy is a read's refusal only
        image, meta = self.m.snap_for("camera_red")
        self.assertEqual(meta["camera"], self.m._camera("camera_red")[0])

    def test_busy_answers_its_preflight_and_a_read_that_would_wait_raises_for_both_asks(self):
        self.m.set_connection("camera_red", "busy")
        self.assertIs(self.m.preflight({"id": "camera_red"})["ready"], True)
        for wait in (False, True):
            with self.assertRaises(self.m.ReadWouldWait) as caught:
                self.m.read_for("camera_red", wait=wait)
            self.assertTrue(caught.exception.would_wait)
        self.m.open_for("camera_red")                           # an open takes no device lock
        self.assertEqual(self.m.open_channels(), ["camera_red"])
        self.assertEqual(self.m.read_for("camera_blue")["backend"], "mock")

    def test_a_piezo_and_the_tweezers_follow_the_same_states(self):
        for cid in ("piezo_stage", "optical_tweezers"):
            self.m.set_connection(cid, "busy")
            with self.assertRaises(self.m.ReadWouldWait, msg=cid):
                self.m.read_for(cid, wait=False)
            self.m.set_connection(cid, "absent")
            with self.assertRaises(self.m.DeviceAbsent, msg=cid):
                self.m.read_for(cid)

    def test_reset_returns_every_channel_to_answering(self):
        self.m.set_connection("camera_red", "absent")
        self.m.set_connection("dmd", "busy")
        self.m.reset()
        self.assertEqual({self.m.connection_of(c) for c in ("camera_red", "dmd")}, {"answering"})

    def test_the_generic_calls_that_name_no_channel_are_as_they_were(self):
        self.m.set_connection("camera_red", "absent")
        self.assertEqual(self.m.read()["backend"], "mock")
        self.assertIs(self.m.preflight()["ready"], True)


class T7bTheOrchestratorSetsThemForTestsOnly(unittest.TestCase):
    def setUp(self):
        self.o = orch.Orchestrator(backend="mock")

    def test_it_sets_a_registry_channel_and_says_so_in_the_log(self):
        self.o.set_mock_connection("camera_red", "absent")
        self.assertEqual(self.o.module_for("camera_red").connection_of("camera_red"), "absent")
        events = [e for e in self.o.log if e.get("event") == "mock_connection_set"]
        self.assertEqual([(e["channel"], e["state"]) for e in events], [("camera_red", "absent")])
        self.assertIn("mock", events[0]["note"])
        self.assertEqual([e for e in self.o.log if e.get("event") in ("apply", "dispatch")], [])

    def test_a_channel_the_registry_does_not_hold_is_not_made_up(self):
        with self.assertRaises(orch.GapError):
            self.o.set_mock_connection("no_such_channel", "absent")
        self.assertEqual([e for e in self.o.log if e.get("event") == "mock_connection_set"], [])

    def test_a_state_it_does_not_know_is_refused(self):
        with self.assertRaises(ValueError):
            self.o.set_mock_connection("camera_red", "unplugged")

    def test_it_is_refused_on_a_real_backend(self):
        real = orch.Orchestrator(backend="hardware")
        with self.assertRaises(orch.InterlockError):
            real.set_mock_connection("camera_red", "absent")

    def test_the_console_has_no_way_to_set_one(self):
        # the host answers only live_on, stop, check_now and the like: a message naming a state is not one
        src = (Path(t85.SRC) / "live_view.py").read_text(encoding="utf-8")
        self.assertNotIn("set_mock_connection", src)
        self.assertNotIn("set_connection", src)


# --------------------------------------------------------------------------- #
# 7c. each kind of run writes the status file with each state as it is
# --------------------------------------------------------------------------- #

ANSWERING, ABSENT, BUSY = "camera_red", "widefield_source_a", "camera_blue"


class _Three(_States):
    states = {ANSWERING: "answering", ABSENT: "absent", BUSY: "busy"}

    def assert_no_value(self, row):
        self.assertEqual((row["how"], row["t_wall"], row["value"]), ("not_read", None, None), row)


class T7cCheckNowShowsEachState(_Three):
    def test_answering_absent_and_busy(self):
        self.host.start()
        reply = self.check_now(self.write_list(_with_channels(ANSWERING, ABSENT, BUSY)))
        self.assertEqual(reply["check_now"], "started", reply)
        log = self.wait_run(reply["run_id"])
        self.assertEqual(log["ended"], "completed")
        doc = self.status()
        self.assert_status_valid(doc)
        rows = {r["channel"]: r for r in doc["check_now"]["channels"]}
        self.assertEqual(list(rows), [ANSWERING, ABSENT, BUSY])
        answering, absent, busy = rows[ANSWERING], rows[ABSENT], rows[BUSY]
        self.assertEqual((answering["how"], answering["opened"], answering["closed"]), ("read_back", True, True))
        self.assertIsInstance(answering["value"], dict)
        self.assertIsNotNone(answering["t_wall"])
        self.assertNotIn("error", answering)
        # absent: its preflight said not ready, the open failed, it was never read and never closed
        self.assert_no_value(absent)
        self.assertEqual((absent["opened"], absent["closed"]), (False, None))
        self.assertIn("open failed", absent["error"])
        # busy: opened, a read that would have waited was not taken, and it was closed
        self.assert_no_value(busy)
        self.assertEqual((busy["opened"], busy["closed"]), (True, True))
        self.assertNotIn("open failed", busy["error"])
        self.assertIn("mock", busy["error"])
        # the two states are told apart by the file alone
        self.assertNotEqual(absent["error"], busy["error"])
        pre = {r["channel"]: r for r in doc["last_run"]["preflight"]["rows"]}
        self.assertIs(pre[ABSENT]["state"]["ready"], False)
        self.assertIs(pre[BUSY]["state"]["ready"], True)
        self.assertIs(pre[ANSWERING]["state"]["ready"], True)
        self.assertEqual(self.orchestrators[0].module_for(ANSWERING).open_channels(), [])

    def test_no_absent_or_busy_channel_carries_a_value_anywhere_in_the_file(self):
        self.host.start()
        reply = self.check_now(self.write_list(_with_channels(ANSWERING, ABSENT, BUSY)))
        self.wait_run(reply["run_id"])
        doc = self.status()
        for row in doc["last_run"]["last_snapshot"]["channels"]:
            if row["channel"] in (ABSENT, BUSY):
                self.assert_no_value(row)
            else:
                self.assertEqual(row["how"], "read_back")


class T7dPlanRunShowsEachState(_Three):
    PLAN = {"card": "plan", "id": "plan-test-086-states", "revision": 1,
            "numbers": [{"name": "n", "value": 1, "unit": "1", "source": "test", "grade": "E5"}],
            "actions": [
                {"id": "a_red", "tier": 0, "device": ANSWERING, "action": "acquire", "reversible": True},
                {"id": "a_blue", "tier": 0, "device": BUSY, "action": "acquire_series", "reversible": True},
                {"id": "a_src", "tier": 0, "device": ABSENT, "action": "set_exposure", "reversible": True}],
            "stop_criteria": [{"id": "n", "number": "n", "metric": "n", "comparator": ">="}]}

    def setUp(self):
        super().setUp()
        # Until the software-motion check resolves a registry name to its Micro-Manager label (card
        # 091) it refuses a plan naming a camera, as test_frame_tap_per_camera notes. This lets that one
        # check pass for these runs and changes nothing else in them.
        real = orch.Orchestrator.check_software_motion_for
        orch.Orchestrator.check_software_motion_for = lambda o, plan, commands: None
        self.addCleanup(setattr, orch.Orchestrator, "check_software_motion_for", real)

    def run_plan(self, run_id="run-20261026-701"):
        path = Path(self.tmp.name) / "plan.json"
        path.write_text(json.dumps(self.PLAN))
        return op.run(path, run_id, backend="mock", observe=lambda m: 9.0, runs_root=self.runs,
                      status_dir=self.status_dir, on_orchestrator=self.on_orchestrator)

    def test_the_status_file_validates_and_shows_each_state(self):
        record = self.run_plan()
        doc = self.status()
        self.assert_status_valid(doc)
        self.assertEqual((doc["last_run"]["run_id"], doc["last_run"]["kind"]), ("run-20261026-701", "plan"))
        self.assertEqual(doc["last_run"]["outcome"], record["ended"])
        pre = {r["channel"]: r for r in doc["last_run"]["preflight"]["rows"]}
        self.assertEqual(set(pre), {ANSWERING, ABSENT, BUSY})
        self.assertIs(pre[ANSWERING]["state"]["ready"], True)
        self.assertIs(pre[ABSENT]["state"]["ready"], False)
        self.assertIs(pre[BUSY]["state"]["ready"], True)
        snap = {r["channel"]: r for r in doc["last_run"]["last_snapshot"]["channels"]}
        self.assertEqual(set(snap), {ANSWERING, ABSENT, BUSY})
        self.assertEqual(snap[ANSWERING]["how"], "read_back")
        self.assertIsNotNone(snap[ANSWERING]["t_wall"])
        self.assertIsInstance(snap[ANSWERING]["value"], dict)
        self.assert_no_value(snap[ABSENT])
        self.assert_no_value(snap[BUSY])
        self.assertIsNone(doc["check_now"])

    def test_the_mock_states_are_in_the_run_log_so_the_run_is_not_read_as_a_real_one(self):
        record = self.run_plan("run-20261026-702")
        events = [(e["channel"], e["state"]) for e in record["events"] if e.get("event") == "mock_connection_set"]
        self.assertEqual(sorted(events), sorted(self.states.items()))


class T7eLiveViewShowsEachState(_States):
    """A live view reads nothing: it streams one camera. The file it writes shows how it ended, and
    carries no reading for any channel whatever state the camera was in."""

    def live(self, states):
        self.states = states
        self.host.start()
        reply = self.live_on(self.write_list(t85.LIVE_LIST, "live.json"))
        self.assertEqual(reply["live_on"], "started", reply)
        log = self.wait_run(reply["run_id"])
        doc = self.status()
        self.assert_status_valid(doc)
        self.assertEqual((doc["last_run"]["run_id"], doc["last_run"]["kind"]), (reply["run_id"], "live_view"))
        return log, doc

    def test_an_answering_camera_streams_and_the_run_completes(self):
        log, doc = self.live({"camera_red": "answering"})
        self.assertEqual((log["ended"], doc["last_run"]["outcome"]), ("completed", "completed"))
        self.assertEqual(len(self.events(log, "live_view_frames")), 1)

    def test_an_absent_camera_fails_the_run_and_nothing_was_streamed(self):
        log, doc = self.live({"camera_red": "absent"})
        self.assertEqual((log["ended"], doc["last_run"]["outcome"]), ("failed", "failed"))
        failed = self.events(log, "live_view_failed")
        self.assertEqual(len(failed), 1)
        self.assertIn("absent", failed[0]["error"])
        self.assertEqual(self.events(log, "live_view_frames"), [])
        self.assertIsNone(doc["last_run"]["last_snapshot"])
        self.assertNotIn("camera_red", json.dumps(doc["last_run"]["last_snapshot"]))

    def test_a_busy_camera_is_only_busy_for_a_read_and_a_live_view_makes_none(self):
        log, doc = self.live({"camera_red": "busy"})
        self.assertEqual(doc["last_run"]["outcome"], "completed")
        self.assertIsNone(doc["last_run"]["last_snapshot"], "a live view reads nothing, so shows no value")


if __name__ == "__main__":
    unittest.main()
