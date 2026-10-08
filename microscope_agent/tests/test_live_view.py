"""Card 062: live view from the console, switched on and off, with no plan.

    python -m unittest microscope_agent/tests/test_live_view.py

Mock only. Every list here is a TEST FIXTURE written by the test into a
temporary approvals/ folder: the person's real list lives in
microscope_agent/approvals/, which no session writes. The run lock, the
address file, the host log and the runs root are all temporary too.
"""

from __future__ import annotations

import copy
import hashlib
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
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


lv = _load("_live_view_under_test", SRC / "live_view.py")
op = lv.op
lock_mod = lv.run_lock
validate = _load("_validate_for_live_view", REPO / "contracts" / "validate.py")

LIST = {
    "artifact": "live_view_list", "schema_version": "0.1",
    "written_by": "TEST FIXTURE, not the person", "written_at": "2026-10-07",
    "label": "TEST FIXTURE: transmitted light, one sequence",
    "transmitted_lamp": {"device": "DiaLamp", "intensity": {"value": 100}},
    "camera": {"device": "Kinetix_red", "exposure_ms": 20, "frame_ceiling": 40},
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ask(addr, payload: bytes):
    out = b""
    try:
        with socket.create_connection((addr["host"], addr["port"]), timeout=20) as s:
            s.sendall(payload)
            s.shutdown(socket.SHUT_WR)
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                out += chunk
    except ConnectionResetError:
        pass
    return json.loads(out) if out.strip() else None


def _send_stop(addr, run_id, reason="test"):
    with socket.create_connection((addr["host"], addr["port"]), timeout=20) as s:
        s.sendall(json.dumps({"stop": run_id, "reason": reason}).encode() + b"\n")
        s.shutdown(socket.SHUT_WR)
        return s.recv(4096)


class _Base(unittest.TestCase):
    frame_delay = 0.0

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.approvals = root / "approvals"
        self.approvals.mkdir()
        self.runs = root / "runs"
        self.lock_path = root / "run.lock"
        self.address = root / "app" / "live_host.json"
        self.host_log = root / "app" / "live_host_log.jsonl"
        self._saved = op.RUN_LOCK_PATH, op.load_safety
        op.RUN_LOCK_PATH = self.lock_path
        op.load_safety = lambda: {"policy_version": "test", "targets": []}
        self.orchestrators = []

        def hook(o):
            self.orchestrators.append(o)
            mock = o.module_for("camera_red")
            mock.reset()
            mock.FRAME_DELAY_S = self.frame_delay
        self.host = lv.LiveHost(self.approvals, self.runs, address_file=self.address,
                                log_path=self.host_log, backend="mock",
                                run_lock_path=self.lock_path, on_orchestrator=hook)

    def tearDown(self):
        self.host.stop()
        op.RUN_LOCK_PATH, op.load_safety = self._saved

    def write_list(self, doc=None, name="live-view-fixture.json") -> str:
        data = (json.dumps(doc or LIST, indent=2) + "\n").encode()
        (self.approvals / name).write_bytes(data)
        return _sha(data)

    def live_on(self, sha):
        return _ask(self.host.address(), json.dumps({"live_on": sha}).encode() + b"\n")

    def wait_run(self, run_id, timeout=30):
        log = self.runs / run_id / "log.json"
        t0 = time.monotonic()
        while not log.exists() and time.monotonic() - t0 < timeout:
            time.sleep(0.05)
        self.assertTrue(log.exists(), f"{run_id} wrote no log.json")
        time.sleep(0.1)
        return json.loads(log.read_text(encoding="utf-8"))

    def events(self, run_id):
        path = self.runs / run_id / "events.jsonl"
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]

    def host_records(self):
        return [json.loads(l) for l in self.host_log.read_text(encoding="utf-8").splitlines() if l]


class T1AnApprovedListStartsAPreparatoryRun(_Base):
    def test_check_85_shape(self):
        self.host.start()
        sha = self.write_list()
        reply = self.live_on(sha)
        self.assertEqual(reply["live_on"], "started", reply)
        self.assertEqual(set(reply), {"live_on", "run_id"})
        log = self.wait_run(reply["run_id"])
        self.assertIsNone(log["plan_id"])
        self.assertIsNone(log["revision"])
        self.assertIn("live view", log["no_plan_because"])
        self.assertEqual(log["approved_commands"]["sha256"], sha)
        self.assertEqual(Path(log["approved_commands"]["path"]).name, "live-view-fixture.json")
        schema = json.loads((REPO / "contracts/schemas/run_log.schema.json").read_text(encoding="utf-8"))
        import jsonschema
        jsonschema.validate(log, schema)
        moved = [e for e in log["events"] if e.get("event") in ("apply", "apply_failed", "dispatch")
                 and ({e.get("channel"), e.get("element")} | set((e.get("params") or {})))
                 & validate.PREPARATORY_MOTION_SET]
        self.assertEqual(moved, [])


class T2RefusalsStartNothing(_Base):
    def _refused(self, payload, why):
        before = set(self.runs.iterdir()) if self.runs.exists() else set()
        reply = _ask(self.host.address(), payload)
        self.assertEqual(reply["live_on"], "refused", (why, reply))
        self.assertEqual(set(reply), {"live_on", "reason"})
        after = set(self.runs.iterdir()) if self.runs.exists() else set()
        self.assertEqual(after, before, why)
        return reply

    def test_unknown_sha_excitation_and_extra_keys(self):
        self.host.start()
        self.write_list()
        r = self._refused(json.dumps({"live_on": "0" * 64}).encode() + b"\n", "unknown sha")
        self.assertIn("no approved live-view list has that sha256", r["reason"])
        bad = copy.deepcopy(LIST)
        bad["excitation"] = {"device": "Aura", "settings": {"State": 1}}
        sha_bad = self.write_list(bad, "live-view-with-aura.json")
        self._refused(json.dumps({"live_on": sha_bad}).encode() + b"\n", "excitation")
        sha = self.write_list()
        self._refused(json.dumps({"live_on": sha, "intensity": 5}).encode() + b"\n", "extra key")
        self._refused(b"live on\n", "not JSON")
        refused = [r for r in self.host_records() if r.get("event") == "live_on_refused"]
        self.assertEqual(len(refused), 4)


class T3AStopEndsItWithinAFrame(_Base):
    frame_delay = 0.02

    def test_stop_channel(self):
        self.host.start()
        doc = copy.deepcopy(LIST)
        doc["camera"]["frame_ceiling"] = 100000
        sha = self.write_list(doc)
        reply = self.live_on(sha)
        run_id = reply["run_id"]
        first = self.events(run_id)[0]
        time.sleep(0.3)
        self.assertIn(b"begun", _send_stop(first["stop_channel"], run_id))
        log = self.wait_run(run_id)
        names = [e["event"] for e in log["events"]]
        self.assertIn("stop_requested", names)
        end = [e for e in log["events"] if e["event"] == "abort_end"][0]["report"]
        dia = [r for r in end["light_sources"] if r["source"] == "DiaLamp"][0]
        self.assertEqual((dia["commanded"], dia["read_back"]), ("0", "0"))
        self.assertTrue(end["shutters"])
        acquired = [e for e in log["events"] if e["event"] == "live_view_frames"][0]
        self.assertTrue(acquired["aborted"])
        self.assertLess(acquired["received"], 100000)
        self.assertEqual(self.events(run_id)[-1]["how"], "stopped_from_outside")


class T4TheCeilingEndsItCompletedWithTheLampOff(_Base):
    def test_ceiling(self):
        self.host.start()
        reply = self.live_on(self.write_list())
        log = self.wait_run(reply["run_id"])
        acquired = [e for e in log["events"] if e["event"] == "live_view_frames"][0]
        self.assertEqual((acquired["received"], acquired["aborted"]), (40, False))
        offs = [e for e in log["events"] if e.get("event") == "apply"
                and e.get("settings_sent") == {"settings": {"DiaLamp": {"State": "0"}}}]
        self.assertEqual(len(offs), 1)
        self.assertEqual(offs[0]["verification"], "readback")
        self.assertEqual(self.events(reply["run_id"])[-1]["how"], "completed")
        mock = self.orchestrators[-1].module_for("stand_ti2e")
        self.assertEqual(mock.read_property("DiaLamp", "State"), "0")


class T5OneRunAtATime(_Base):
    frame_delay = 0.02

    def test_live_on_refused_while_another_run_holds_the_lock(self):
        self.host.start()
        sha = self.write_list()
        other = lock_mod.RunLock(self.lock_path)
        other.acquire({"kind": "test", "run_id": "run-test-holder"})
        try:
            reply = self.live_on(sha)
        finally:
            other.release()
        self.assertEqual(reply["live_on"], "refused")
        self.assertIn("lock", reply["reason"])
        self.assertIn("run-test-holder", reply["reason"])

    def test_a_plan_run_is_refused_while_a_live_view_holds_it(self):
        self.host.start()
        doc = copy.deepcopy(LIST)
        doc["camera"]["frame_ceiling"] = 100000
        reply = self.live_on(self.write_list(doc))
        run_id = reply["run_id"]
        # A plan that passes the gate, so the lock is what refuses it.
        plan = {"card": "plan", "id": "plan-test-062", "revision": 1, "actions": [],
                "numbers": [{"name": "n_min", "value": 1, "unit": "1", "source": "test",
                             "grade": "E5"}],
                "stop_criteria": [{"id": "n", "number": "n_min", "metric": "n",
                                   "comparator": ">="}]}
        plan_path = Path(self.tmp.name) / "plan.json"
        plan_path.write_text(json.dumps(plan))
        try:
            with self.assertRaises(op.Refusal) as caught:
                op.run(plan_path, "run-test-062-plan", backend="mock",
                       runs_root=self.runs)
        finally:
            _send_stop(self.events(run_id)[0]["stop_channel"], run_id)
            self.wait_run(run_id)
        self.assertIn("lock", str(caught.exception))
        self.assertIn(run_id, str(caught.exception))
        self.assertFalse((self.runs / "run-test-062-plan").exists())
        reply2 = self.live_on(self.write_list())       # the lock is free again
        self.assertEqual(reply2["live_on"], "started")
        self.wait_run(reply2["run_id"])


class T6NoFrameOnDisk(_Base):
    frame_delay = 0.01

    def test_frames_feed_the_tap_and_nothing_else(self):
        self.host.start()
        reply = self.live_on(self.write_list())
        run_id = reply["run_id"]
        tap = self.events(run_id)[0]["frame_tap"]
        head = None
        for _ in range(100):
            got = b""
            with socket.create_connection((tap["host"], tap["port"]), timeout=5) as s:
                s.sendall(b'{"get": "latest_frame"}\n')
                s.shutdown(socket.SHUT_WR)
                while True:
                    c = s.recv(65536)
                    if not c:
                        break
                    got += c
            head = json.loads(got.partition(b"\n")[0])
            if head.get("frame"):
                break
            time.sleep(0.01)
        self.assertTrue(head and head["frame"], head)
        self.wait_run(run_id)
        self.assertEqual(sorted(p.name for p in (self.runs / run_id).iterdir()),
                         ["deviations.json", "events.jsonl", "log.json"])


class T7LoopbackAndOnlyWhileStarted(_Base):
    def test_bind_and_lifetime(self):
        self.assertFalse(self.address.exists())
        self.assertIsNone(self.host.address())
        addr = self.host.start()
        self.assertEqual(addr["host"], "127.0.0.1")
        on_disk = json.loads(self.address.read_text(encoding="utf-8"))
        self.assertEqual(set(on_disk), {"host", "port", "pid", "started_at"})
        self.assertEqual((on_disk["host"], on_disk["port"]), ("127.0.0.1", addr["port"]))
        self.host.stop()
        self.assertFalse(self.address.exists())
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", addr["port"]), timeout=1).close()

    def test_a_second_host_refuses_while_one_answers(self):
        self.host.start()
        second = lv.LiveHost(self.approvals, self.runs, address_file=self.address,
                             log_path=self.host_log, run_lock_path=self.lock_path)
        with self.assertRaises(RuntimeError):
            second.start()


if __name__ == "__main__":
    unittest.main()
