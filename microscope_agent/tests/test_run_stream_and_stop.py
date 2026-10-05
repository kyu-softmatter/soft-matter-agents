"""Card 057: a run a viewer can follow (events.jsonl), and a stop that reaches it.

    python -m unittest microscope_agent/tests/test_run_stream_and_stop.py

Mock only, and every run folder is a temporary directory, never runs/ in the
tree. The plan has no actions and one stop criterion: on mock no ordinary
action survives the software-motion check, so the run's "middle" is the
monitor's observe() call, which these tests hold open to look in and to
stop the run from outside. Dispatch-phase stopping is tested on the
orchestrator directly, with the allow-list check stubbed out because it is
not what is under test.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
import tempfile
import threading
import time
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


op = _load("_op_stream_under_test", SRC / "operator.py")
orch = op.orch

PLAN = {"card": "plan", "id": "plan-test-stream", "revision": 1, "actions": [],
        "numbers": [{"name": "drift_um", "value": 5, "unit": "um", "source": "test", "grade": "E5"}],
        "stop_criteria": [{"id": "drift", "number": "drift_um", "metric": "drift",
                           "comparator": ">"}]}
OK, BREAKS = 9.0, 1.0          # `drift > 5` must hold, so 9 passes and 1 breaks it


def _lines(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l]


def _send(addr, payload: bytes):
    """Send one message and read the reply. A reset is a refusal with no reply: the
    channel closes on an oversized message without reading the rest, and on
    Windows closing with unread data resets the connection."""
    out = b""
    try:
        with socket.create_connection((addr["host"], addr["port"]), timeout=5) as s:
            s.sendall(payload)
            s.shutdown(socket.SHUT_WR)
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    return out
                out += chunk
    except ConnectionResetError:
        return out


class _Base(unittest.TestCase):
    def setUp(self):
        self._saved = op.load_safety, op.approvals_on_disk
        op.load_safety = lambda: {"policy_version": "test", "targets": []}
        op.approvals_on_disk = lambda: []
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "runs"
        self.plan_path = Path(self.tmp.name) / "plan.json"
        self.plan_path.write_text(json.dumps(PLAN))

    def tearDown(self):
        op.load_safety, op.approvals_on_disk = self._saved
        self.tmp.cleanup()

    def run_plan(self, observe, run_id="run-test-stream"):
        return op.run(self.plan_path, run_id, backend="mock", observe=observe,
                      runs_root=self.root)

    def events_path(self, run_id="run-test-stream"):
        return self.root / run_id / "events.jsonl"


class T1VisibleWhileRunning(_Base):
    def test_a_reader_mid_run_sees_run_started_and_the_events_so_far(self):
        seen = {}

        def observe(metric):
            seen["lines"] = _lines(self.events_path())
            return OK
        self.run_plan(observe)
        lines = seen["lines"]
        self.assertEqual(lines[0]["event"], "run_started")
        self.assertEqual((lines[0]["run_id"], lines[0]["plan_id"], lines[0]["revision"]),
                         ("run-test-stream", "plan-test-stream", 1))
        self.assertIn("t0_wall", lines[0])
        self.assertIn("software_motion_checked", [l["event"] for l in lines])
        self.assertNotEqual(lines[-1]["event"], "run_ended")


class T2SameEventsAsTheLog(_Base):
    def test_log_events_equal_the_stream_between_first_and_last_line(self):
        record = self.run_plan(lambda m: OK)
        lines = _lines(self.events_path())
        self.assertEqual(lines[1:-1], json.loads(json.dumps(record["events"])))


class T3RunEndedSaysHow(_Base):
    def test_completed(self):
        self.run_plan(lambda m: OK)
        last = _lines(self.events_path())[-1]
        self.assertEqual((last["event"], last["how"]), ("run_ended", "completed"))

    def test_aborted_by_a_monitor(self):
        self.run_plan(lambda m: BREAKS)
        last = _lines(self.events_path())[-1]
        self.assertEqual((last["event"], last["how"]), ("run_ended", "aborted_by_monitor"))

    def test_stopped_from_outside(self):
        def observe(metric):
            addr = _lines(self.events_path())[0]["stop_channel"]
            _send(addr, json.dumps({"stop": "run-test-stream", "reason": "test"}).encode() + b"\n")
            return OK
        self.run_plan(observe)
        last = _lines(self.events_path())[-1]
        self.assertEqual((last["event"], last["how"]), ("run_ended", "stopped_from_outside"))


class T4WriteRunGuard(_Base):
    def test_events_folder_does_not_refuse_and_a_log_does(self):
        record = self.run_plan(lambda m: OK)
        self.assertTrue(self.events_path().exists())
        folder = op.write_run(record, runs_root=self.root)
        self.assertTrue((folder / "log.json").exists())
        with self.assertRaises(op.Refusal):
            op.write_run(record, runs_root=self.root)

    def test_a_run_id_is_never_reused(self):
        self.run_plan(lambda m: OK)
        with self.assertRaises(op.Refusal):
            self.run_plan(lambda m: OK)


class T5LoopbackOnly(_Base):
    def test_bound_to_127_0_0_1_and_closed_after(self):
        seen = {}

        def observe(metric):
            seen["addr"] = _lines(self.events_path())[0]["stop_channel"]
            return OK
        self.run_plan(observe)
        self.assertEqual(seen["addr"]["host"], "127.0.0.1")
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", seen["addr"]["port"]), timeout=1).close()


class T6AValidStopMidDispatch(unittest.TestCase):
    def test_stop_then_abort_and_no_command_after(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        o = orch.Orchestrator(backend="mock")
        mock = o.module_for("stand_ti2e")
        mock.reset()
        o.check_software_motion_for = lambda plan, commands: None   # not under test here
        started = threading.Event()
        original = mock.apply

        def slow(params):
            if "n" in params:
                o.record(event="test_command_ran", n=params["n"])
                started.set()
                time.sleep(0.05)
            return original(params)
        mock.apply = slow
        addr = o.begin_run(Path(tmp.name) / "run-x", run_id="run-x", plan_id="p", revision=1)
        commands = [orch.Command(channel="stand_ti2e", action="t", params={"n": i},
                                 from_field=f"test[{i}]") for i in range(40)]
        worker = threading.Thread(target=o.dispatch, args=(commands,))
        worker.start()
        started.wait(5)
        reply = _send(addr, json.dumps({"stop": "run-x", "reason": "enough"}).encode() + b"\n")
        worker.join(10)
        o.end_run("stopped_from_outside")
        self.assertIn(b"abort", reply)
        names = [e["event"] for e in o.log]
        i_stop = names.index("stop_requested")
        self.assertEqual(names[i_stop + 1], "abort_begin")
        self.assertIn("enough", o.log[i_stop + 1]["reason"])
        self.assertIn("abort_end", names[i_stop:])
        ran_after = [e for e in o.log[i_stop:] if e["event"] == "test_command_ran"]
        self.assertLessEqual(len(ran_after), 1)        # at most the one already in its sleep
        self.assertLess(names.count("test_command_ran"), 40)
        delay = o.log[i_stop + 1]["t_mono"] - o.log[i_stop]["t_mono"]
        print(f"\n  stop_requested -> abort_begin: {delay * 1000:.1f} ms")
        self.assertLess(delay, 0.5)


class T7BadStopsChangeNothing(_Base):
    def test_each_malformed_stop_is_refused_and_the_run_continues(self):
        bad = [json.dumps({"stop": "another-run", "reason": "x"}).encode() + b"\n",
               json.dumps({"stop": "run-test-stream", "reason": "x", "set": 1}).encode() + b"\n",
               json.dumps({"stop": "run-test-stream", "reason": "x" * 5000}).encode() + b"\n",
               b"stop now please\n",
               b'{"stop": "run-test-stream",\n "reason": "two lines"}\n']
        replies = []

        def observe(metric):
            addr = _lines(self.events_path())[0]["stop_channel"]
            for payload in bad:
                replies.append(_send(addr, payload))
            return OK
        record = self.run_plan(observe)
        names = [e["event"] for e in record["events"]]
        self.assertEqual(names.count("stop_refused"), len(bad))
        reasons = [e["reason"] for e in record["events"] if e["event"] == "stop_refused"]
        self.assertIn("not this run", reasons[0])
        self.assertIn("keys", reasons[1])
        self.assertIn("longer than", reasons[2])
        self.assertIn("not JSON", reasons[3])
        self.assertTrue(any(w in reasons[4] for w in ("not one line", "not JSON")), reasons[4])
        self.assertNotIn("stop_requested", names)
        self.assertNotIn("abort_begin", names)
        self.assertEqual(replies, [b""] * len(bad))
        self.assertEqual(_lines(self.events_path())[-1]["how"], "completed")


class T8NothingListensOutsideARun(unittest.TestCase):
    def test_no_listener_before_begin_or_after_end(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        o = orch.Orchestrator(backend="mock")
        self.assertIsNone(o.stop_channel_address())
        addr = o.begin_run(Path(tmp.name) / "run-y", run_id="run-y", plan_id="p", revision=1)
        socket.create_connection((addr["host"], addr["port"]), timeout=1).close()
        o.end_run("completed")
        self.assertIsNone(o.stop_channel_address())
        with self.assertRaises(OSError):
            socket.create_connection((addr["host"], addr["port"]), timeout=1).close()


if __name__ == "__main__":
    unittest.main()
