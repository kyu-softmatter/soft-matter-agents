"""Card 085: the idle status file, and "check now" in the live-view host.

    python -m unittest tests.test_idle_status_and_check_now

Mock only. Every list here is a TEST FIXTURE written into a temporary approvals/ folder, the
status file is written into a temporary folder, and the run lock, the address file, the host log
and the runs root are temporary too. Nothing here writes microscope_runtime/.runtime_status/ or
the person's real check-now list.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import socket
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock as umock

SRC = Path(__file__).resolve().parents[1] / "src"
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC))

try:
    import jsonschema
except ImportError:                                             # pragma: no cover
    jsonschema = None


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


lv = _load("_live_view_for_idle_status", SRC / "live_view.py")
op = lv.op
orch = op.orch
lock_mod = lv.run_lock
validate = _load("_validate_for_idle_status", REPO / "contracts" / "validate.py")

SCHEMAS = REPO / "contracts" / "schemas"
STATUS_SCHEMA = json.loads((SCHEMAS / "idle_status.schema.json").read_text(encoding="utf-8"))
RUN_LOG_SCHEMA = json.loads((SCHEMAS / "run_log.schema.json").read_text(encoding="utf-8"))
INTERFACE = json.loads((SCHEMAS / "run_interface.schema.json").read_text(encoding="utf-8"))
RUN_ID = re.compile(r"^run-[0-9]{8}-[0-9]{3}$")

CHECK_NOW_LIST = {
    "artifact": "check_now_list", "schema_version": "0.1",
    "written_by": "TEST FIXTURE, not the person", "written_at": "2026-10-26",
    "label": "TEST FIXTURE: the two cameras opened, read and closed",
    "channels": [
        {"channel": "camera_red", "opening_is_inert_because": "TEST FIXTURE reason: an open starts no acquisition"},
        {"channel": "camera_blue", "opening_is_inert_because": "TEST FIXTURE reason: as camera_red"},
    ],
}
LIVE_LIST = {
    "artifact": "live_view_list", "schema_version": "0.1",
    "written_by": "TEST FIXTURE, not the person", "written_at": "2026-10-26",
    "label": "TEST FIXTURE: transmitted light, one sequence",
    "transmitted_lamp": {"device": "DiaLamp", "intensity": {"value": 100}},
    "camera": {"device": "Kinetix_red", "exposure_ms": 20, "frame_ceiling": 40},
}
PLAN = {"card": "plan", "id": "plan-test-status", "revision": 1, "actions": [],
        "numbers": [{"name": "drift_um", "value": 5, "unit": "um", "source": "test", "grade": "E5"}],
        "stop_criteria": [{"id": "drift", "number": "drift_um", "metric": "drift",
                           "comparator": ">"}]}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _when(text: str) -> datetime:
    return datetime.fromisoformat(text)


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


def _with_channels(*ids):
    doc = copy.deepcopy(CHECK_NOW_LIST)
    doc["channels"] = [{"channel": c, "opening_is_inert_because": f"TEST FIXTURE reason for {c}"} for c in ids]
    return doc


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
        self.status_dir = root / "state" / ".runtime_status"       # does not exist yet
        self.status_file = self.status_dir / "idle_status.json"
        self.address = root / "app" / "live_host.json"
        self.host_log = root / "app" / "live_host_log.jsonl"
        self._saved = op.RUN_LOCK_PATH, op.load_safety, op.approvals_on_disk
        op.RUN_LOCK_PATH = self.lock_path
        op.load_safety = lambda: {"policy_version": "test", "targets": []}
        op.approvals_on_disk = lambda: []
        self.orchestrators = []
        self.opened = []                                        # every open_for a module was asked for
        self.on_orchestrator = self._hook
        self.host = lv.LiveHost(self.approvals, self.runs, address_file=self.address,
                                log_path=self.host_log, backend="mock",
                                run_lock_path=self.lock_path,
                                on_orchestrator=lambda o: self.on_orchestrator(o),
                                status_dir=self.status_dir)
        self.addCleanup(self._restore)

    def _restore(self):
        self.host.stop()
        op.RUN_LOCK_PATH, op.load_safety, op.approvals_on_disk = self._saved

    def _hook(self, o):
        self.orchestrators.append(o)
        mock = o.module_for("camera_red")
        mock.reset()
        mock.FRAME_DELAY_S = self.frame_delay
        spy = getattr(mock, "open_for", None)
        if spy is not None:
            def counting(cid, *a, **kw):
                self.opened.append(cid)
                return spy(cid, *a, **kw)
            mock.open_for = counting

    def write_list(self, doc, name="check-now-fixture.json") -> str:
        data = (json.dumps(doc, indent=2) + "\n").encode()
        (self.approvals / name).write_bytes(data)
        return _sha(data)

    def check_now(self, sha):
        return _ask(self.host.address(), json.dumps({"check_now": sha}).encode() + b"\n")

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

    def status(self) -> dict:
        self.assertTrue(self.status_file.exists(), "no status file was written")
        return json.loads(self.status_file.read_text(encoding="utf-8"))

    def assert_status_valid(self, doc):
        if jsonschema is None:
            self.skipTest("jsonschema is not installed")
        jsonschema.Draft202012Validator(STATUS_SCHEMA).validate(doc)
        for text in (doc["written_at"], *(r["ended_at"] for r in [doc["last_run"]] if r)):
            _when(text)

    def host_records(self):
        return [json.loads(l) for l in self.host_log.read_text(encoding="utf-8").splitlines() if l]

    def run_check_now_here(self, doc, run_id="run-20261026-901", **kw):
        """A check-now run in this thread, without the host: the list is written and run directly."""
        sha = self.write_list(doc)
        path = self.approvals / "check-now-fixture.json"
        record = op.run_check_now(path, run_id, runs_root=self.runs, backend="mock",
                                  on_orchestrator=self.on_orchestrator, status_dir=self.status_dir, **kw)
        return sha, record


def _steps(events):
    names = ("preflight", "check_now_open", "check_now_read", "check_now_close", "check_now_step_failed")
    return [(e["event"], e.get("channel"), e.get("step")) for e in events if e.get("event") in names]


# --------------------------------------------------------------------------- #
# 1. a check-now run opens, reads and closes each listed channel, and sends nothing
# --------------------------------------------------------------------------- #

class T1CheckNowOpensReadsClosesAndSendsNothing(_Base):
    def test_each_channel_in_order_and_no_apply(self):
        self.host.start()
        sha = self.write_list(CHECK_NOW_LIST)
        reply = self.check_now(sha)
        self.assertEqual(reply["check_now"], "started", reply)
        self.assertEqual(set(reply), {"check_now", "run_id"})
        self.assertRegex(reply["run_id"], RUN_ID)
        log = self.wait_run(reply["run_id"])
        events = log["events"]
        self.assertEqual(_steps(events), [
            ("preflight", "camera_red", None), ("check_now_open", "camera_red", None),
            ("check_now_read", "camera_red", None), ("check_now_close", "camera_red", None),
            ("preflight", "camera_blue", None), ("check_now_open", "camera_blue", None),
            ("check_now_read", "camera_blue", None), ("check_now_close", "camera_blue", None)])
        self.assertEqual(self.opened, ["camera_red", "camera_blue"])
        sent = [e for e in events if e.get("event") in ("apply", "apply_failed", "dispatch")]
        self.assertEqual(sent, [], "a check-now run has no apply and no dispatch")
        self.assertFalse(any(orch.is_light_command(e) for e in events))
        touched = [e for e in events if ({e.get("channel"), e.get("element")} | set((e.get("params") or {})))
                   & validate.PREPARATORY_MOTION_SET]
        self.assertEqual(touched, [])
        self.assertEqual(sum(e["event"] == "check_now_read" for e in events), 2)
        self.assertEqual(log["ended"], "completed")

    def test_the_run_log_is_a_run_log(self):
        if jsonschema is None:
            self.skipTest("jsonschema is not installed")
        self.host.start()
        reply = self.check_now(self.write_list(CHECK_NOW_LIST))
        log = self.wait_run(reply["run_id"])
        jsonschema.validate(log, RUN_LOG_SCHEMA)

    def test_a_failed_step_is_recorded_and_the_next_channel_is_tried(self):
        self.host.start()
        sha = self.write_list(CHECK_NOW_LIST)

        def hook(o):
            self._hook(o)
            mock = o.module_for("camera_red")
            real = mock.preflight

            def preflight(channel=None):
                if (channel or {}).get("id") == "camera_red":
                    raise RuntimeError("TEST: red will not answer a preflight")
                return real(channel)
            mock.preflight = preflight
        self.on_orchestrator = hook
        log = self.wait_run(self.check_now(sha)["run_id"])
        steps = _steps(log["events"])
        self.assertEqual(steps[0], ("check_now_step_failed", "camera_red", "preflight"))
        self.assertNotIn(("check_now_open", "camera_red", None), steps)
        self.assertEqual(steps[1:], [
            ("preflight", "camera_blue", None), ("check_now_open", "camera_blue", None),
            ("check_now_read", "camera_blue", None), ("check_now_close", "camera_blue", None)])
        self.assertEqual(self.opened, ["camera_blue"])
        entries = {c["channel"]: c for c in self.status()["check_now"]["channels"]}
        self.assertEqual((entries["camera_red"]["opened"], entries["camera_red"]["closed"],
                          entries["camera_red"]["how"]), (False, None, "not_read"))
        self.assertIn("will not answer", entries["camera_red"]["error"])
        self.assertEqual((entries["camera_blue"]["opened"], entries["camera_blue"]["closed"],
                          entries["camera_blue"]["how"]), (True, True, "read_back"))
        self.assert_status_valid(self.status())

    def test_a_channel_that_was_opened_is_closed_whatever_the_read_did(self):
        self.host.start()
        sha = self.write_list(CHECK_NOW_LIST)

        def hook(o):
            self._hook(o)
            mock = o.module_for("camera_red")
            real = mock.read_for

            def read_for(cid, wait=True, elements=()):
                if cid == "camera_red":
                    raise RuntimeError("TEST: the read of red failed")
                return real(cid, wait=wait, elements=elements)
            mock.read_for = read_for
        self.on_orchestrator = hook
        log = self.wait_run(self.check_now(sha)["run_id"])
        steps = _steps(log["events"])
        self.assertEqual(steps[:4], [
            ("preflight", "camera_red", None), ("check_now_open", "camera_red", None),
            ("check_now_step_failed", "camera_red", "read"), ("check_now_close", "camera_red", None)])
        self.assertEqual(steps[4:], [
            ("preflight", "camera_blue", None), ("check_now_open", "camera_blue", None),
            ("check_now_read", "camera_blue", None), ("check_now_close", "camera_blue", None)])
        red = {c["channel"]: c for c in self.status()["check_now"]["channels"]}["camera_red"]
        self.assertEqual((red["opened"], red["closed"], red["how"], red["t_wall"], red["value"]),
                         (True, True, "not_read", None, None))
        self.assertIn("failed", red["error"])

    def test_a_close_that_fails_is_recorded_and_the_next_channel_still_runs(self):
        self.host.start()
        sha = self.write_list(CHECK_NOW_LIST)

        def hook(o):
            self._hook(o)
            mock = o.module_for("camera_red")

            def close_for(cid, *a, **kw):
                if cid == "camera_red":
                    raise RuntimeError("TEST: red would not close")
            mock.close_for = close_for
        self.on_orchestrator = hook
        log = self.wait_run(self.check_now(sha)["run_id"])
        steps = _steps(log["events"])
        self.assertEqual(steps[:4], [
            ("preflight", "camera_red", None), ("check_now_open", "camera_red", None),
            ("check_now_read", "camera_red", None), ("check_now_step_failed", "camera_red", "close")])
        self.assertEqual(steps[4:], [
            ("preflight", "camera_blue", None), ("check_now_open", "camera_blue", None),
            ("check_now_read", "camera_blue", None), ("check_now_close", "camera_blue", None)])
        entries = {c["channel"]: c for c in self.status()["check_now"]["channels"]}
        red = entries["camera_red"]
        self.assertEqual((red["opened"], red["closed"], red["how"]), (True, False, "read_back"))
        self.assertIn("would not close", red["error"])
        self.assertEqual((entries["camera_blue"]["closed"], "error" in entries["camera_blue"]), (True, False))
        self.assert_status_valid(self.status())

    def test_the_run_lock_is_free_again_however_the_run_ended(self):
        self.run_check_now_here(CHECK_NOW_LIST, "run-20261026-901")
        again = lock_mod.RunLock(self.lock_path)
        again.acquire({"kind": "plan", "run_id": "run-20261026-950", "plan_id": "plan-x"})
        again.release()
        with self.assertRaises(op.Refusal):                     # an unregistered channel refuses the run
            self.run_check_now_here(_with_channels("camera_red", "camera_green"), "run-20261026-902")
        again.acquire({"kind": "plan", "run_id": "run-20261026-951", "plan_id": "plan-x"})
        again.release()

    def test_the_run_lock_is_released_and_not_left_for_the_garbage_collector(self):
        # A lock that is merely dropped is closed when its last reference goes, which hides a missing
        # release(); release() is also what removes the holder file, so a left file names a run that is over.
        self.run_check_now_here(CHECK_NOW_LIST, "run-20261026-901")
        self.assertIsNone(lock_mod.RunLock(self.lock_path).read_holder(), "the holder file of an ended run")
        with self.assertRaises(op.Refusal):
            self.run_check_now_here(_with_channels("camera_red", "camera_green"), "run-20261026-902")
        self.assertIsNone(lock_mod.RunLock(self.lock_path).read_holder(), "the holder file of a refused run")

    def test_a_busy_read_is_not_read_and_never_the_last_value(self):
        # A first run reads camera_red; a second finds it busy. The second must not show the first's value.
        self.run_check_now_here(_with_channels("camera_red"), "run-20261026-901")
        first = {c["channel"]: c for c in self.status()["check_now"]["channels"]}["camera_red"]
        self.assertEqual(first["how"], "read_back")
        self.assertIsNotNone(first["value"])

        def hook(o):
            self._hook(o)
            mock = o.module_for("camera_red")
            mock._LOCK.acquire()                                # the device is busy
            self.addCleanup(lambda: mock._LOCK.locked() and mock._LOCK.release())
        self.on_orchestrator = hook
        self.run_check_now_here(_with_channels("camera_red"), "run-20261026-902")
        second = {c["channel"]: c for c in self.status()["check_now"]["channels"]}["camera_red"]
        self.assertEqual((second["how"], second["t_wall"], second["value"]), ("not_read", None, None))
        self.assertEqual((second["opened"], second["closed"]), (True, True))
        self.assertTrue(second["error"])
        self.assert_status_valid(self.status())

    def test_a_channel_with_no_read_back_is_not_readable_with_its_time(self):
        self.run_check_now_here(_with_channels("laser_combiner"), "run-20261026-901")
        row = self.status()["check_now"]["channels"][0]
        self.assertEqual((row["channel"], row["how"]), ("laser_combiner", "not_readable"))
        self.assertIsNotNone(row["t_wall"])
        self.assertIsNone(row["value"])                         # nothing was sent in this run
        self.assert_status_valid(self.status())


# --------------------------------------------------------------------------- #
# 2. check 85's conditions hold on that log
# --------------------------------------------------------------------------- #

class T2CheckEightyFiveHolds(_Base):
    def test_a_preparatory_run_that_names_its_list(self):
        self.host.start()
        sha = self.write_list(CHECK_NOW_LIST)
        reply = self.check_now(sha)
        log = self.wait_run(reply["run_id"])
        self.assertIsNone(log["plan_id"])
        self.assertIsNone(log["revision"])
        self.assertIn("check now", log["no_plan_because"])
        self.assertEqual(log["approved_commands"]["sha256"], sha)
        self.assertEqual(Path(log["approved_commands"]["path"]).name, "check-now-fixture.json")
        self.assertEqual(log["approval"], {"id": None, "kind": None})
        moved = [e for e in log["events"] if e.get("event") in ("apply", "apply_failed", "dispatch")
                 and ({e.get("channel"), e.get("element")} | set((e.get("params") or {})))
                 & validate.PREPARATORY_MOTION_SET]
        self.assertEqual(moved, [])
        # the run id is the one the reply named, and it is one the interface accepts
        self.assertEqual(log["run_id"], reply["run_id"])
        self.assertRegex(log["run_id"], RUN_ID)

    def test_its_list_may_not_name_anything_in_the_motion_set(self):
        # check 85 refuses such a list at commit time; the host refuses it at run time, before a run exists
        self.host.start()
        for motion in ("z_drive", "piezo_stage", "optical_tweezers"):
            sha = self.write_list(_with_channels("camera_red", motion), f"motion-{motion}.json")
            reply = self.check_now(sha)
            self.assertEqual(reply["check_now"], "refused", (motion, reply))
            self.assertIn(motion, reply["reason"])
        self.assertFalse(self.runs.exists() and any(self.runs.iterdir()))
        self.assertEqual(self.opened, [])


# --------------------------------------------------------------------------- #
# 3. refusals, with the reason, and nothing is opened
# --------------------------------------------------------------------------- #

class T3Refusals(_Base):
    def _refused(self, payload, why):
        before = set(self.runs.iterdir()) if self.runs.exists() else set()
        reply = _ask(self.host.address(), payload)
        self.assertEqual(reply["check_now"], "refused", (why, reply))
        self.assertEqual(set(reply), {"check_now", "reason"})
        self.assertTrue(reply["reason"])
        if jsonschema is not None:
            jsonschema.validate(reply, {"$ref": "#/$defs/check_now_reply", "$defs": INTERFACE["$defs"]})
        after = set(self.runs.iterdir()) if self.runs.exists() else set()
        self.assertEqual(after, before, why)
        self.assertEqual(self.opened, [], why)
        self.assertFalse(self.status_file.exists(), f"{why}: a refusal is not a run and writes no status")
        return reply

    def test_unknown_hash_and_extra_keys_and_not_a_hash(self):
        self.host.start()
        self.write_list(CHECK_NOW_LIST)
        r = self._refused(json.dumps({"check_now": "0" * 64}).encode() + b"\n", "unknown hash")
        self.assertIn("no approved check-now list has that sha256", r["reason"])
        sha = self.write_list(CHECK_NOW_LIST)
        self._refused(json.dumps({"check_now": sha, "channel": "camera_red"}).encode() + b"\n", "extra key")
        self._refused(json.dumps({"check_now": sha, "live_on": sha}).encode() + b"\n", "two messages in one")
        self._refused(json.dumps({"check_now": "not-a-hash"}).encode() + b"\n", "not a sha256")
        # not JSON is no check_now message at all: the host's one standing refusal answers it
        reply = _ask(self.host.address(), b"check now\n")
        self.assertEqual(reply["live_on"], "refused", reply)
        self.assertEqual(self.opened, [])
        refused = [r for r in self.host_records() if r.get("event") == "check_now_refused"]
        self.assertGreaterEqual(len(refused), 3)

    def test_invalid_list(self):
        self.host.start()
        for why, mutate in (
                ("an extra key", lambda d: d.update(excitation={"device": "Aura"})),
                ("no channels", lambda d: d.update(channels=[])),
                ("no inert reason", lambda d: d["channels"][0].pop("opening_is_inert_because")),
                ("a short inert reason", lambda d: d["channels"][0].update(opening_is_inert_because="ok")),
                ("an extra key on a channel", lambda d: d["channels"][0].update(settings={"State": 1})),
                ("a channel named twice", lambda d: d["channels"].append(copy.deepcopy(d["channels"][0]))),
                ("a wrong artifact", lambda d: d.update(artifact="live_view_list"))):
            doc = copy.deepcopy(CHECK_NOW_LIST)
            mutate(doc)
            sha = self.write_list(doc, "invalid.json")
            r = self._refused(json.dumps({"check_now": sha}).encode() + b"\n", why)
            self.assertTrue(r["reason"].startswith("invalid.json:"),
                            f"{why}: the host judges the list itself, before any run is started: {r['reason']}")

    def test_a_list_written_for_live_view_is_not_a_check_now_list(self):
        self.host.start()
        sha = self.write_list(LIVE_LIST, "live.json")
        r = self._refused(json.dumps({"check_now": sha}).encode() + b"\n", "a live-view list")
        self.assertTrue(r["reason"].startswith("live.json:"), r["reason"])
        reply = self.live_on(self.write_list(CHECK_NOW_LIST))
        self.assertEqual(reply["live_on"], "refused")

    def test_a_channel_not_in_the_registry_refuses_the_whole_run_before_anything_opens(self):
        self.host.start()
        sha = self.write_list(_with_channels("camera_red", "camera_green"))
        r = self._refused(json.dumps({"check_now": sha}).encode() + b"\n", "unregistered channel")
        self.assertIn("camera_green", r["reason"])

    def test_a_held_run_lock(self):
        self.host.start()
        sha = self.write_list(CHECK_NOW_LIST)
        held = lock_mod.RunLock(self.lock_path)
        held.acquire({"kind": "plan", "run_id": "run-20261026-001", "plan_id": "plan-x"})
        self.addCleanup(lambda: held.held and held.release())
        r = self._refused(json.dumps({"check_now": sha}).encode() + b"\n", "lock held")
        self.assertIn("run-20261026-001", r["reason"])
        held.release()
        self.assertEqual(self.check_now(sha)["check_now"], "started")


class T3bLiveViewAndCheckNowNeverRunTogether(_Base):
    frame_delay = 0.02

    def test_check_now_while_a_live_view_runs_and_live_on_while_a_check_now_holds_the_lock(self):
        self.host.start()
        doc = copy.deepcopy(LIVE_LIST)
        doc["camera"]["frame_ceiling"] = 100000
        live = self.live_on(self.write_list(doc, "live.json"))
        self.assertEqual(live["live_on"], "started", live)
        self.assertRegex(live["run_id"], RUN_ID)
        try:
            reply = self.check_now(self.write_list(CHECK_NOW_LIST))
            self.assertEqual(reply["check_now"], "refused", reply)
            self.assertIn(live["run_id"], reply["reason"])
            self.assertEqual(self.opened, [])
        finally:
            _send_stop(self.orch_stop_address(live["run_id"]), live["run_id"])
        self.wait_run(live["run_id"])

    def test_a_live_on_while_a_check_now_runs_is_refused_naming_it(self):
        self.host.start()
        sha = self.write_list(CHECK_NOW_LIST)
        inside, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        seen = {}

        def hook(o):
            self._hook(o)
            mock = o.module_for("camera_red")
            counting = mock.open_for

            def held_open(cid, *a, **kw):
                seen.setdefault("holder", lock_mod.RunLock(self.lock_path).read_holder())
                inside.set()
                release.wait(20)
                return counting(cid, *a, **kw)
            mock.open_for = held_open
        self.on_orchestrator = hook
        started = self.check_now(sha)
        self.assertEqual(started["check_now"], "started", started)
        self.assertTrue(inside.wait(20), "the run never reached its first open")
        reply = self.live_on(self.write_list(LIVE_LIST, "live.json"))
        release.set()
        self.wait_run(started["run_id"])
        self.assertEqual(seen["holder"]["kind"], "check_now")
        self.assertEqual(seen["holder"]["run_id"], started["run_id"])
        self.assertEqual(reply["live_on"], "refused", reply)
        self.assertIn(started["run_id"], reply["reason"])
        self.assertIn("check_now", reply["reason"])

    def orch_stop_address(self, run_id):
        path = self.runs / run_id / "events.jsonl"
        first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        return first["stop_channel"]


# --------------------------------------------------------------------------- #
# 4. the status file validates after every kind of run, and nothing is carried forward
# --------------------------------------------------------------------------- #

class T4TheStatusFile(_Base):
    def test_after_a_check_now_run(self):
        self.host.start()
        reply = self.check_now(self.write_list(CHECK_NOW_LIST))
        log = self.wait_run(reply["run_id"])
        doc = self.status()
        self.assert_status_valid(doc)
        self.assertEqual(doc["written_by_run"], reply["run_id"])
        self.assertEqual(doc["last_run"]["run_id"], reply["run_id"])
        self.assertEqual((doc["last_run"]["kind"], doc["last_run"]["outcome"]), ("check_now", "completed"))
        self.assertEqual(doc["check_now"]["run_id"], reply["run_id"])
        self.assertEqual(doc["check_now"]["list"]["sha256"], log["approved_commands"]["sha256"])
        self.assertEqual(doc["check_now"]["list"]["path"], log["approved_commands"]["path"])
        self.assertEqual([c["channel"] for c in doc["check_now"]["channels"]], ["camera_red", "camera_blue"])
        self.assertEqual(doc["ownership"], {"status": "not_built"})
        # the registry is pointed to, not copied
        registry = REPO / doc["registry"]["path"]
        self.assertEqual(doc["registry"]["sha256"], _sha(registry.read_bytes()))
        self.assertEqual(self.orchestrators[0].registry_source.replace("\\", "/"), doc["registry"]["path"])
        # every value carries the time it was read, inside the run
        t0 = _when(log["t0_wall"])
        for row in doc["check_now"]["channels"]:
            self.assertTrue(row["opened"] and row["closed"], row)
            self.assertEqual(row["how"], "read_back")
            # a read's wall time is the run's t0 plus a monotonic offset, and Windows' monotonic clock
            # ticks in about 16 ms, so "inside the run" holds to that resolution and no finer
            slack = timedelta(milliseconds=50)
            self.assertTrue(t0 <= _when(row["t_wall"]) <= _when(doc["written_at"]) + slack, row)
            self.assertIsInstance(row["value"], dict)
        # the last run's preflight rows and snapshot come from this run's own log
        self.assertEqual([r["channel"] for r in doc["last_run"]["preflight"]["rows"]],
                         ["camera_red", "camera_blue"])
        snap = doc["last_run"]["last_snapshot"]
        self.assertEqual([c["channel"] for c in snap["channels"]], ["camera_red", "camera_blue"])

    def test_after_a_live_view_run(self):
        self.host.start()
        reply = self.live_on(self.write_list(LIVE_LIST, "live.json"))
        self.assertEqual(reply["live_on"], "started", reply)
        self.assertRegex(reply["run_id"], RUN_ID)
        self.wait_run(reply["run_id"])
        doc = self.status()
        self.assert_status_valid(doc)
        self.assertEqual((doc["last_run"]["run_id"], doc["last_run"]["kind"]), (reply["run_id"], "live_view"))
        self.assertIsNone(doc["check_now"], "no check-now ran, and the last one is not carried over")

    def test_after_a_plan_run(self):
        plan_path = Path(self.tmp.name) / "plan.json"
        plan_path.write_text(json.dumps(PLAN))
        op.run(plan_path, "run-20261026-001", backend="mock", observe=lambda m: 9.0,
               runs_root=self.runs, status_dir=self.status_dir)
        doc = self.status()
        self.assert_status_valid(doc)
        self.assertEqual((doc["last_run"]["run_id"], doc["last_run"]["kind"], doc["last_run"]["outcome"]),
                         ("run-20261026-001", "plan", "completed"))
        self.assertIsNone(doc["check_now"])

    def test_the_status_dir_is_created_and_holds_only_the_file(self):
        self.assertFalse(self.status_dir.exists())
        self.run_check_now_here(CHECK_NOW_LIST)
        self.assertEqual([p.name for p in self.status_dir.iterdir()], ["idle_status.json"])

    def test_nothing_is_carried_forward(self):
        self.run_check_now_here(CHECK_NOW_LIST, "run-20261026-901")
        self.assertEqual([c["channel"] for c in self.status()["check_now"]["channels"]],
                         ["camera_red", "camera_blue"])
        # a later run that opens only red: blue is absent everywhere, not shown with its old value
        self.run_check_now_here(_with_channels("camera_red"), "run-20261026-902")
        doc = self.status()
        self.assertEqual(doc["written_by_run"], "run-20261026-902")
        self.assertEqual([c["channel"] for c in doc["check_now"]["channels"]], ["camera_red"])
        self.assertEqual([c["channel"] for c in doc["last_run"]["last_snapshot"]["channels"]], ["camera_red"])
        self.assertNotIn("camera_blue", json.dumps(doc["last_run"]["preflight"]))
        self.assert_status_valid(doc)
        # and a plan run after that leaves no check-now at all
        plan_path = Path(self.tmp.name) / "plan.json"
        plan_path.write_text(json.dumps(PLAN))
        op.run(plan_path, "run-20261026-002", backend="mock", observe=lambda m: 9.0,
               runs_root=self.runs, status_dir=self.status_dir)
        doc = self.status()
        self.assertIsNone(doc["check_now"])
        self.assertNotIn("camera_red", json.dumps(doc["last_run"]["last_snapshot"]))
        self.assert_status_valid(doc)

    def test_a_run_given_no_status_dir_writes_none(self):
        plan_path = Path(self.tmp.name) / "plan.json"
        plan_path.write_text(json.dumps(PLAN))
        op.run(plan_path, "run-20261026-003", backend="mock", observe=lambda m: 9.0, runs_root=self.runs)
        self.assertFalse(self.status_dir.exists())


# --------------------------------------------------------------------------- #
# 5. a failed status write changes nothing about the run, and is recorded
# --------------------------------------------------------------------------- #

class T5AFailedWrite(_Base):
    def _blocked(self) -> Path:
        blocker = Path(self.tmp.name) / "a-file-where-a-folder-should-be"
        blocker.write_text("not a folder")
        return blocker / ".runtime_status"                      # cannot be created beneath a file

    def test_a_plan_run_ends_as_it_would_and_says_so(self):
        plan_path = Path(self.tmp.name) / "plan.json"
        plan_path.write_text(json.dumps(PLAN))
        record = op.run(plan_path, "run-20261026-004", backend="mock", observe=lambda m: 9.0,
                        runs_root=self.runs, status_dir=self._blocked())
        self.assertEqual(record["ended"], "completed")
        failed = [e for e in record["events"] if e.get("event") == "idle_status_write_failed"]
        self.assertEqual(len(failed), 1, failed)
        self.assertTrue(failed[0]["error"])
        lines = [json.loads(l) for l in (self.runs / "run-20261026-004" / "events.jsonl")
                 .read_text(encoding="utf-8").splitlines() if l]
        self.assertEqual(lines[-1]["event"], "run_ended")
        self.assertEqual(lines[-1]["how"], "completed")
        self.assertEqual(lines[1:-1], json.loads(json.dumps(record["events"])),
                         "the failure is in the stream as well as the log, before run_ended")

    def test_a_run_id_the_status_file_cannot_name_is_a_failed_write_not_a_bad_file(self):
        plan_path = Path(self.tmp.name) / "plan.json"
        plan_path.write_text(json.dumps(PLAN))
        record = op.run(plan_path, "run-not-a-status-id", backend="mock", observe=lambda m: 9.0,
                        runs_root=self.runs, status_dir=self.status_dir)
        self.assertEqual(record["ended"], "completed")
        failed = [e for e in record["events"] if e.get("event") == "idle_status_write_failed"]
        self.assertEqual(len(failed), 1, failed)
        self.assertIn("run id", failed[0]["error"])
        self.assertFalse(self.status_file.exists(), "a file naming a run the schema cannot name was written")

    def test_a_check_now_run_ends_as_it_would_and_says_so(self):
        _sha_, record = self.run_check_now_here(CHECK_NOW_LIST, "run-20261026-905")
        self.assertEqual(record["ended"], "completed")
        # same run again with the write blocked
        sha = self.write_list(CHECK_NOW_LIST)
        record = op.run_check_now(self.approvals / "check-now-fixture.json", "run-20261026-906",
                                  runs_root=self.runs, backend="mock", on_orchestrator=self.on_orchestrator,
                                  status_dir=self._blocked())
        self.assertEqual(record["ended"], "completed")
        self.assertEqual(sum(e.get("event") == "idle_status_write_failed" for e in record["events"]), 1)
        self.assertEqual(sum(e.get("event") == "check_now_read" for e in record["events"]), 2)

    def test_a_write_that_fails_part_way_leaves_the_old_file_whole(self):
        self.run_check_now_here(CHECK_NOW_LIST, "run-20261026-901")
        before = self.status_file.read_bytes()
        real = op.idle_status.os.replace

        def fail_for_the_status_file(src, dst, *a, **kw):
            if Path(dst).name == "idle_status.json":
                raise OSError("TEST: replace failed")
            return real(src, dst, *a, **kw)                     # the run lock's own rename is not under test
        with umock.patch.object(op.idle_status.os, "replace", fail_for_the_status_file):
            record = op.run_check_now(self.approvals / "check-now-fixture.json", "run-20261026-902",
                                      runs_root=self.runs, backend="mock",
                                      on_orchestrator=self.on_orchestrator, status_dir=self.status_dir)
        self.assertEqual(record["ended"], "completed")
        self.assertEqual(self.status_file.read_bytes(), before)
        self.assertEqual([p.name for p in self.status_dir.iterdir()], ["idle_status.json"],
                         "the temporary file does not stay behind")


# --------------------------------------------------------------------------- #
# 6. a reader sees the old file or the new one, never half of either
# --------------------------------------------------------------------------- #

class T6AtomicWrite(unittest.TestCase):
    def test_the_temporary_file_is_beside_the_file_and_renamed_over_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / ".runtime_status"
            seen = []
            real = op.idle_status.os.replace

            def spy(src, dst, *a, **kw):
                seen.append((Path(src), Path(dst)))
                return real(src, dst, *a, **kw)
            with umock.patch.object(op.idle_status.os, "replace", spy):
                op.idle_status.write(folder, {"artifact": "idle_status", "n": 1})
            self.assertEqual(len(seen), 1)
            src, dst = seen[0]
            self.assertEqual(src.parent, folder)
            self.assertEqual(dst, folder / "idle_status.json")
            self.assertNotEqual(src, dst)

    def test_a_reader_never_sees_half_a_file(self):
        padding = "x" * 400_000
        docs = [{"artifact": "idle_status", "which": "A", "pad": padding},
                {"artifact": "idle_status", "which": "B", "pad": padding + "yy"}]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / ".runtime_status"
            op.idle_status.write(folder, docs[0])
            path = folder / "idle_status.json"
            done = threading.Event()
            errors = []

            def writer():
                try:
                    for i in range(120):
                        op.idle_status.write(folder, docs[i % 2])
                except Exception as exc:                        # noqa: BLE001 - reported below
                    errors.append(exc)
                finally:
                    done.set()
            thread = threading.Thread(target=writer)
            thread.start()
            reads = torn = 0
            while not done.is_set() or reads < 20:
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue                                    # the file was being swapped; not a read
                reads += 1
                try:
                    doc = json.loads(text)
                except ValueError:
                    torn += 1
                    continue
                if doc not in docs:
                    torn += 1
            thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(torn, 0, f"{torn} of {reads} reads saw a file that was neither the old nor the new")
            self.assertGreaterEqual(reads, 20)


# --------------------------------------------------------------------------- #
# 7. the interface schema's own examples and refusals
# --------------------------------------------------------------------------- #

@unittest.skipIf(jsonschema is None, "jsonschema is not installed")
class T7TheInterfaceSchema(unittest.TestCase):
    def _each(self, name):
        definition = INTERFACE["$defs"][name]
        schema = {"$ref": f"#/$defs/{name}", "$defs": INTERFACE["$defs"]}
        self.assertTrue(definition.get("examples"), f"{name} has no examples")
        self.assertTrue(definition.get("x_refused"), f"{name} has no x_refused")
        return definition, schema

    def test_check_now_request(self):
        definition, schema = self._each("check_now_request")
        for example in definition["examples"]:
            jsonschema.validate(example, schema)
        for refused in definition["x_refused"]:
            with self.assertRaises(jsonschema.ValidationError, msg=json.dumps(refused)):
                jsonschema.validate(refused, schema)

    def test_check_now_reply(self):
        definition, schema = self._each("check_now_reply")
        for example in definition["examples"]:
            jsonschema.validate(example, schema)
        for refused in definition["x_refused"]:
            with self.assertRaises(jsonschema.ValidationError, msg=json.dumps(refused)):
                jsonschema.validate(refused, schema)

    def test_what_the_host_says_is_what_the_schema_accepts(self):
        # every reply this host gives is one the schema accepts: started with a conforming id,
        # or refused with a reason
        _, schema = self._each("check_now_reply")
        for reply in ({"check_now": "started", "run_id": "run-20261026-901"},
                      {"check_now": "refused", "reason": "a run holds the lock"}):
            jsonschema.validate(reply, schema)


if __name__ == "__main__":
    unittest.main()
