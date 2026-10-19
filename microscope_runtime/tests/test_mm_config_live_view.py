"""Card 069: the live view on hardware loads a configuration the person approved.

    python -m unittest microscope_runtime/tests/test_mm_config_live_view.py

The live-view host's `--mm-config`, against a FAKE MMCore on a non-mock backend:
the loader is injected, the camera is the mock's, and no instrument or
Micro-Manager install is involved. The same gate as the operator's: approved
by sha256, the focus direction checked, the startup preset never run. Each
test was watched failing before the code that passes it existed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


lv = _load("_live_view_card069_under_test", SRC / "live_view.py")
op = lv.op
orch = op.orch
in_run = _load("_in_run_tests_for_069_live_view", TESTS / "test_mm_config_in_run.py")
cfg_text, sha = in_run.cfg_text, in_run.sha

LIVE_LIST = {"artifact": "live_view_list", "schema_version": "0.1", "written_by": "tester",
             "written_at": "2026-10-19", "label": "TEST list",
             "transmitted_lamp": {"device": "DiaLamp", "intensity": {"value": 100}},
             "camera": {"device": "Kinetix_red", "exposure_ms": 10, "frame_ceiling": 3}}


class _FakeCore:
    """The stand, the lamp, both turret shutters and the camera: what a live view and an abort read."""

    def __init__(self):
        self.props = {("Core", "AutoShutter"): "0", ("DiaLamp", "State"): "0",
                      ("DiaLamp", "Intensity"): "0", ("Turret1Shutter", "State"): "1",
                      ("Turret2Shutter", "State"): "1", ("PFS", "State"): "Off"}
        self.writes = []

    def getLoadedDevices(self):
        return ("Core", "ZDrive", "PFS", "DiaLamp", "Turret1Shutter", "Turret2Shutter", "Kinetix_red")

    def getProperty(self, device, prop):
        return self.props[(device, prop)]

    def setProperty(self, device, prop, value):
        self.writes.append((device, prop, str(value)))
        self.props[(device, prop)] = str(value)

    def getAutoShutter(self):
        return False

    def getPosition(self, device):
        return 100.0

    def waitForDevice(self, device):
        return None

    def waitForSystem(self):
        return None


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.approvals = self.root / "approvals"
        self.approvals.mkdir()
        self.runs = self.root / "runs"
        self.list_path = self.root / "live.json"
        self.list_path.write_text(json.dumps(LIVE_LIST), encoding="utf-8")
        saved_lock = op.RUN_LOCK_PATH
        op.RUN_LOCK_PATH = self.root / "run.lock"
        self.addCleanup(setattr, op, "RUN_LOCK_PATH", saved_lock)
        real_module_for = orch.Orchestrator.module_for

        def module_for(s, cid):
            kind = "micromanager" if cid == "stand_ti2e" else "mock"
            return s._device_module(kind, needed_by="card 069 live-view test")
        orch.Orchestrator.module_for = module_for
        self.addCleanup(setattr, orch.Orchestrator, "module_for", real_module_for)
        self.core = _FakeCore()
        self.loaded = []

    def write_cfg(self, text, name="single.cfg"):
        path = self.root / name
        path.write_bytes(text.encode("utf-8"))
        return path

    def approve(self, text, name="appr-cfg.json"):
        (self.approvals / name).write_text(json.dumps(
            {"artifact": "mm_config_approval", "schema_version": "0.1", "written_by": "tester",
             "written_at": "2026-10-19", "configuration": {"file": "single.cfg", "sha256": sha(text)}}),
            encoding="utf-8")

    def loader(self, verified=True):
        def load(mm, path):
            self.loaded.append(Path(path))
            mm._core = lambda: mm.GuardedCore(self.core)
            return {"path": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    "changed_during_load": False, "loaded_devices": list(self.core.getLoadedDevices()),
                    "autoshutter": {"wanted": "0", "read_getAutoShutter": not verified,
                                    "read_property": "0" if verified else "1", "verified": verified}}
        return load

    def live(self, run_id="run-test-069-lv", backend="hardware", state=None, **kw):
        return op.run_live_view(self.list_path, run_id, runs_root=self.runs, backend=backend,
                                mm_approvals=self.approvals, mm_state=state, **kw)

    def names(self, run_id="run-test-069-lv"):
        lines = (self.runs / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(l)["event"] for l in lines]


class T1TheRunLoadsTheApprovedFile(_Base):
    def test_the_option_is_refused_on_the_mock_backend_not_ignored(self):
        text = cfg_text()
        self.approve(text)
        with self.assertRaisesRegex(op.Refusal, "mock"):
            self.live(backend="mock", mm_config=self.write_cfg(text), config_loader=self.loader())
        self.assertEqual(self.loaded, [])

    def test_a_file_that_is_not_approved_is_refused_and_nothing_is_loaded(self):
        with self.assertRaisesRegex(op.Refusal, "approved list"):
            self.live(mm_config=self.write_cfg(cfg_text()), config_loader=self.loader())
        self.assertEqual(self.loaded, [])
        self.assertFalse((self.runs / "run-test-069-lv").exists())

    def test_a_negative_zdrive_direction_is_refused_before_the_load(self):
        text = cfg_text(zdrive="FocusDirection,ZDrive,-1\n")
        self.approve(text)
        with self.assertRaisesRegex(op.Refusal, "negative"):
            self.live(mm_config=self.write_cfg(text), config_loader=self.loader())
        self.assertEqual(self.loaded, [])

    def test_the_load_event_comes_before_the_lamp_and_the_run_completes(self):
        text = cfg_text()
        self.approve(text)
        record = self.live(mm_config=self.write_cfg(text), config_loader=self.loader())
        self.assertEqual(record["ended"], "completed")
        names = self.names()
        self.assertIn("mm_config_loaded", names)
        self.assertLess(names.index("mm_config_loaded"), names.index("apply"))
        self.assertEqual(len(self.loaded), 1)
        self.assertEqual(self.loaded[0].parent, self.runs / "run-test-069-lv")
        body = self.loaded[0].read_text(encoding="utf-8").split("Nothing else changed.\n", 1)[1]
        self.assertNotIn("ConfigGroup,System,Startup", body)
        self.assertEqual(self.core.props[("DiaLamp", "State")], "0")     # the lamp ends off

    def test_an_autoshutter_that_did_not_verify_stops_the_run_before_the_lamp(self):
        text = cfg_text()
        self.approve(text)
        record = self.live(mm_config=self.write_cfg(text), config_loader=self.loader(verified=False))
        self.assertEqual(record["ended"], "failed")
        names = self.names()
        self.assertIn("mm_config_loaded", names)
        self.assertIn("live_view_failed", names)
        self.assertNotIn("apply", names)                                 # no lamp write was sent
        self.assertNotIn(("DiaLamp", "State", "1"), self.core.writes)


class T2OnceForTheHost(_Base):
    def test_a_second_live_view_records_that_it_is_loaded_and_loads_nothing(self):
        text = cfg_text()
        self.approve(text)
        state = {}
        cfg = self.write_cfg(text)
        self.live("run-test-069-lv", state=state, mm_config=cfg, config_loader=self.loader())
        self.live("run-test-069-lv2", state=state, mm_config=cfg, config_loader=self.loader())
        self.assertEqual(len(self.loaded), 1)
        self.assertIn("mm_config_already_loaded", self.names("run-test-069-lv2"))
        self.assertNotIn("mm_config_loaded", self.names("run-test-069-lv2"))

    def test_the_file_is_judged_afresh_so_changed_bytes_are_refused(self):
        text = cfg_text()
        self.approve(text)
        state = {}
        cfg = self.write_cfg(text)
        self.live("run-test-069-lv", state=state, mm_config=cfg, config_loader=self.loader())
        cfg.write_bytes((text + "# edited after it was approved\n").encode("utf-8"))
        with self.assertRaisesRegex(op.Refusal, "approved list"):
            self.live("run-test-069-lv2", state=state, mm_config=cfg, config_loader=self.loader())

    def test_another_approved_file_is_not_the_one_this_host_loaded(self):
        text = cfg_text()
        self.approve(text)
        state = {}
        cfg = self.write_cfg(text)
        self.live("run-test-069-lv", state=state, mm_config=cfg, config_loader=self.loader())
        other = text + "# a second approved version\n"
        self.approve(other, name="appr-cfg-2.json")
        cfg.write_bytes(other.encode("utf-8"))
        with self.assertRaisesRegex(op.Refusal, "Restart the host"):
            self.live("run-test-069-lv2", state=state, mm_config=cfg, config_loader=self.loader())


class T3AbortReadsEveryRowAfterTheLoad(_Base):
    """The card's abort test: after a load an abort reads the shutter rows back; before one, it refuses."""

    def fail_the_camera(self):
        real = orch.Orchestrator.acquire_sequence

        def boom(s, *a, **k):
            raise RuntimeError("the camera dropped (test)")
        orch.Orchestrator.acquire_sequence = boom
        self.addCleanup(setattr, orch.Orchestrator, "acquire_sequence", real)

    def abort_report(self, run_id):
        lines = (self.runs / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ends = [json.loads(l) for l in lines if json.loads(l)["event"] == "abort_end"]
        self.assertEqual(len(ends), 1, "the run did not abort exactly once")
        return ends[0]["report"]

    def test_after_a_load_the_abort_reads_each_turret_shutter_back_closed(self):
        self.fail_the_camera()
        text = cfg_text()
        self.approve(text)
        record = self.live(mm_config=self.write_cfg(text), config_loader=self.loader())
        self.assertEqual(record["ended"], "failed")
        report = self.abort_report("run-test-069-lv")
        rows = {r.get("element") or r.get("channel"): r for r in report["shutters"]}
        closed = [r for r in report["shutters"] if r.get("closed") is True]
        self.assertTrue(closed, f"no shutter row was read back closed: {report['shutters']}")
        self.assertEqual(self.core.props[("Turret1Shutter", "State")], "0")
        self.assertEqual(self.core.props[("Turret2Shutter", "State")], "0")
        self.assertEqual(self.core.props[("DiaLamp", "State")], "0")
        self.assertTrue(rows)

    def test_before_a_load_the_abort_has_no_core_and_reads_nothing_back(self):
        self.fail_the_camera()
        record = self.live()                                              # no configuration, as today
        self.assertEqual(record["ended"], "failed")
        report = self.abort_report("run-test-069-lv")
        self.assertFalse([r for r in report["shutters"] if r.get("closed") is True],
                         "a shutter row claimed closed with no configuration loaded")
        self.assertNotIn("mm_config_loaded", self.names())
        self.assertEqual(self.core.writes, [])


class T4TheHost(_Base):
    def host(self, **kw):
        return lv.LiveHost(self.approvals, self.runs, address_file=self.root / "addr.json",
                           log_path=self.root / "log.jsonl", **kw)

    def test_the_host_refuses_to_start_with_a_file_that_is_not_approved(self):
        host = self.host(backend="hardware", mm_config=self.write_cfg(cfg_text()))
        with self.assertRaisesRegex(op.Refusal, "approved list"):
            host.start()
        self.assertIsNone(host.address())
        self.assertFalse((self.root / "addr.json").exists())

    def test_the_host_refuses_to_start_with_a_wrong_focus_direction(self):
        text = cfg_text(zdrive="FocusDirection,ZDrive,0\n")
        self.approve(text)
        host = self.host(backend="hardware", mm_config=self.write_cfg(text))
        with self.assertRaisesRegex(op.Refusal, "zero"):
            host.start()
        self.assertIsNone(host.address())

    def test_the_host_refuses_the_option_with_the_mock_backend(self):
        text = cfg_text()
        self.approve(text)
        host = self.host(backend="mock", mm_config=self.write_cfg(text))
        with self.assertRaisesRegex(op.Refusal, "mock"):
            host.start()
        self.assertIsNone(host.address())

    def test_an_approved_file_lets_the_host_start(self):
        text = cfg_text()
        self.approve(text)
        host = self.host(backend="hardware", mm_config=self.write_cfg(text),
                         config_loader=self.loader())
        try:
            self.assertIsNotNone(host.start())
        finally:
            host.stop()
        self.assertEqual(self.loaded, [])                                 # nothing loads until a live_on

    def test_a_live_on_through_the_host_loads_the_approved_file_into_that_runs_folder(self):
        import socket
        text = cfg_text()
        self.approve(text)
        listing = self.approvals / "live.json"
        listing.write_text(json.dumps(LIVE_LIST), encoding="utf-8")
        host = self.host(backend="hardware", mm_config=self.write_cfg(text),
                         config_loader=self.loader())
        addr = host.start()
        try:
            with socket.create_connection((addr["host"], addr["port"]), timeout=5) as conn:
                digest = hashlib.sha256(listing.read_bytes()).hexdigest()
                conn.sendall(json.dumps({"live_on": digest}).encode() + b"\n")
                reply = json.loads(conn.makefile().readline())
        finally:
            host.stop()                                                   # joins the run it started
        self.assertEqual(reply["live_on"], "started", reply)
        run_id = reply["run_id"]
        self.assertEqual(len(self.loaded), 1)
        self.assertEqual(self.loaded[0].parent, self.runs / run_id)
        self.assertIn("mm_config_loaded", self.names(run_id))
        self.assertEqual(host._mm_state["loaded"]["run_id"], run_id)


class T5Main(_Base):
    def test_mm_config_with_the_mock_backend_is_a_usage_error(self):
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as caught:
            lv.main(["--backend", "mock", "--mm-config", str(self.root / "x.cfg"),
                     "--approvals", str(self.approvals), "--runs-root", str(self.runs)])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("--mm-config", err.getvalue())

    def test_an_unapproved_file_on_hardware_exits_two_and_starts_no_host(self):
        err = io.StringIO()
        # main() waits for Ctrl-C once a host is up. If the refusal ever stopped happening this
        # test would wait for ever, so the wait is made to end at once, and the missing refusal
        # shows as a failed assertion and not as a hang.
        with redirect_stderr(err), mock.patch.object(lv.time, "sleep", side_effect=KeyboardInterrupt):
            code = lv.main(["--backend", "hardware", "--mm-config", str(self.write_cfg(cfg_text())),
                            "--approvals", str(self.approvals), "--runs-root", str(self.runs),
                            "--address-file", str(self.root / "addr.json")])
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", err.getvalue())
        self.assertFalse((self.root / "addr.json").exists())


if __name__ == "__main__":
    unittest.main()
