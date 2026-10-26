"""Card 084 with card 086 item 1: the frame tap answers per camera, on a mock that has two.

    python -m unittest tests.test_frame_tap_per_camera        (from microscope_runtime/)

The tap keeps the latest frame of each camera a run takes, keyed by the camera the orchestrator's
own call served, and answers two request forms: the bare one (the first camera in `tap_cameras`)
and the one that names a camera. A camera the run does not take is refused by name and recorded.
Every frame reply names its camera. The request and reply shapes are read from
contracts/schemas/run_interface.schema.json, never copied. Mock only; frames are synthetic.
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
REPO = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))

import test_console_signed_approval as t87                      # noqa: E402  (its _Base runs a plan)

orch = t87.orch
op = t87.op

try:
    import jsonschema
except ImportError:                                              # pragma: no cover
    jsonschema = None

SCHEMA = json.loads((REPO / "contracts" / "schemas" / "run_interface.schema.json").read_text(encoding="utf-8"))
RED, BLUE = "Kinetix_red", "Kinetix_blue"
BARE = {"get": "latest_frame"}


def line(message: dict) -> bytes:
    return json.dumps(message).encode() + b"\n"


def ask(addr, payload, timeout=5):
    """One request; returns (header dict or None, body bytes)."""
    data = b""
    try:
        with socket.create_connection((addr["host"], addr["port"]), timeout=timeout) as s:
            s.sendall(payload if isinstance(payload, bytes) else line(payload))
            s.shutdown(socket.SHUT_WR)
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
    except ConnectionResetError:
        pass
    if not data:
        return None, b""
    head, _, body = data.partition(b"\n")
    return json.loads(head), body


def _check(definition: str, instance) -> None:
    jsonschema.validate(instance, {"$ref": f"#/$defs/{definition}", "$defs": SCHEMA["$defs"]})


class _Rig:
    """A run with a tap and nothing else: the orchestrator's own calls are the only acquisition."""

    def __init__(self, test, cameras):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        self.o = orch.Orchestrator(backend="mock")
        self.mock = self.o.module_for("camera_red")
        self.mock.reset()
        saved = (self.mock.FRAME_SHAPE, self.mock.FRAME_BYTES, self.mock.FRAME_DELAY_S)
        self.mock.FRAME_SHAPE = (16, 16)                        # frames a viewer can draw and tell apart
        test.addCleanup(lambda: (setattr(self.mock, "FRAME_SHAPE", saved[0]),
                                 setattr(self.mock, "FRAME_BYTES", saved[1]),
                                 setattr(self.mock, "FRAME_DELAY_S", saved[2])))
        self.folder = Path(self.tmp.name) / "run-20261026-001"
        self.o.begin_run(self.folder, run_id="run-20261026-001", plan_id="p", revision=1, tap_cameras=cameras)
        test.addCleanup(self.end)

    @property
    def tap(self):
        return self.o.frame_tap_address()

    def end(self):
        if self.o.stop_channel_address() is not None:
            self.o.end_run("completed")

    def first_line(self) -> dict:
        return json.loads((self.folder / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])


class T1ATwoCameraRunAnswersEachCameraItsOwnFrame(unittest.TestCase):
    def test_named_requests_and_the_bare_one(self):
        rig = _Rig(self, [RED, BLUE])
        red, blue = [], []
        rig.o.acquire_sequence("camera_red", 3, lambda i, img, md: red.append((img.copy(), dict(md))))
        rig.o.acquire_sequence("camera_blue", 5, lambda i, img, md: blue.append((img.copy(), dict(md))))
        # each camera's frames reach the run's sink under that camera's name (card 086 item 1)
        self.assertEqual({md["Camera"] for _, md in red}, {RED})
        self.assertEqual({md["Camera"] for _, md in blue}, {BLUE})
        # and the two cameras' frames differ, frame for frame, so a screen that mixes them up is caught
        self.assertTrue(all((r[0] != b[0]).any() for r, b in zip(red, blue)))
        head_r, body_r = ask(rig.tap, {"get": "latest_frame", "camera": RED})
        head_b, body_b = ask(rig.tap, {"get": "latest_frame", "camera": BLUE})
        head_0, body_0 = ask(rig.tap, BARE)
        self.assertEqual((head_r["camera"], head_b["camera"], head_0["camera"]), (RED, BLUE, RED))
        self.assertEqual(body_r, red[-1][0].tobytes())
        self.assertEqual(body_b, blue[-1][0].tobytes())
        self.assertNotEqual(body_r, body_b)
        self.assertEqual((head_0, body_0), (head_r, body_r))     # the bare form answers for the first camera
        self.assertEqual(head_r["metadata"]["ImageNumber"], red[-1][1]["ImageNumber"])
        self.assertEqual(head_b["metadata"]["ImageNumber"], blue[-1][1]["ImageNumber"])

    def test_a_snap_is_keyed_by_the_camera_it_was_taken_on(self):
        rig = _Rig(self, [RED, BLUE])
        image, meta = rig.o.acquire_snap("camera_blue")
        self.assertEqual(meta["camera"], BLUE)
        head, body = ask(rig.tap, {"get": "latest_frame", "camera": BLUE})
        self.assertEqual((head["frame"], head["camera"], body), (True, BLUE, image.tobytes()))
        head, body = ask(rig.tap, {"get": "latest_frame", "camera": RED})
        self.assertEqual((head["frame"], head["camera"], body), (False, RED, b""))

    def test_the_tap_keys_by_the_call_and_not_by_the_metadata_text(self):
        rig = _Rig(self, [RED, BLUE])
        real = rig.mock.sequence_for

        def lying(channel_id, n, sink, timeout_s=None):
            return real(channel_id, n, lambda i, img, md: sink(i, img, {**md, "Camera": BLUE, "camera": BLUE}),
                        timeout_s=timeout_s)
        rig.mock.sequence_for = lying
        self.addCleanup(setattr, rig.mock, "sequence_for", real)
        rig.o.acquire_sequence("camera_red", 2, lambda i, img, md: None)
        head, _ = ask(rig.tap, {"get": "latest_frame", "camera": RED})
        self.assertTrue(head["frame"])
        head, _ = ask(rig.tap, {"get": "latest_frame", "camera": BLUE})
        self.assertFalse(head["frame"])

    def test_a_snap_is_keyed_by_the_call_and_not_by_the_metadata_text_either(self):
        rig = _Rig(self, [RED, BLUE])
        real = rig.mock.snap_for

        def lying(channel_id):
            image, md = real(channel_id)
            return image, {**md, "camera": BLUE, "Camera": BLUE}
        rig.mock.snap_for = lying
        self.addCleanup(setattr, rig.mock, "snap_for", real)
        rig.o.acquire_snap("camera_red")
        head, _ = ask(rig.tap, {"get": "latest_frame", "camera": RED})
        self.assertTrue(head["frame"])
        head, _ = ask(rig.tap, {"get": "latest_frame", "camera": BLUE})
        self.assertFalse(head["frame"])

    def test_an_empty_list_answers_frame_false_to_the_bare_request(self):
        rig = _Rig(self, [])
        rig.o.acquire_snap("camera_red")                       # a frame nobody listed is never served
        head, body = ask(rig.tap, BARE)
        self.assertEqual((head["frame"], body), (False, b""))
        self.assertNotIn("camera", head)


class T2AnUnknownCameraIsRefusedByNameAndRecorded(unittest.TestCase):
    def _counting(self, rig):
        calls = []
        for name in ("snap", "sequence", "apply", "snap_for", "sequence_for", "apply_for", "read", "read_for"):
            real = getattr(rig.mock, name, None)
            if real is None:
                continue

            def counted(*a, __n=name, __r=real, **k):
                calls.append(__n)
                return __r(*a, **k)
            setattr(rig.mock, name, counted)
            self.addCleanup(setattr, rig.mock, name, real)
        return calls

    def test_named_in_the_reply_recorded_and_no_device_call(self):
        rig = _Rig(self, [RED])
        rig.o.acquire_snap("camera_red")
        calls = self._counting(rig)
        head, body = ask(rig.tap, {"get": "latest_frame", "camera": "Kinetix_green"})
        self.assertEqual((head["frame"], head["camera"], body), (False, "Kinetix_green", b""))
        self.assertIn("Kinetix_green", head["note"])
        self.assertIn("does not take", head["note"])
        self.assertIn(RED, head["note"])
        refused = [e for e in rig.o.log if e["event"] == "frame_tap_refused"]
        self.assertEqual(len(refused), 1)
        self.assertEqual(refused[0]["camera"], "Kinetix_green")
        self.assertIn("Kinetix_green", refused[0]["reason"])
        self.assertEqual(calls, [])

    def test_a_malformed_name_is_refused_like_any_other_request(self):
        rig = _Rig(self, [RED])
        for bad in ({"get": "latest_frame", "camera": ""}, {"get": "latest_frame", "camera": 7},
                    {"get": "latest_frame", "camera": None}, {"get": "latest_frame", "camera": "a b"},
                    {"get": "latest_frame", "camera": RED, "exposure_ms": 10},
                    {"get": "latest_frame", "camera": ["Kinetix_red"]}):
            self.assertEqual(ask(rig.tap, bad), (None, b""), bad)
        self.assertEqual(len([e for e in rig.o.log if e["event"] == "frame_tap_refused"]), 6)


class T3RunStartedCarriesTapCameras(t87._Base):
    ACQ = {"id": "a_red", "tier": 0, "device": "camera_red", "action": "acquire", "reversible": True}
    ACQ_BLUE = {"id": "a_blue", "tier": 0, "device": "camera_blue", "action": "acquire_series", "reversible": True}
    PLAN = {"card": "plan", "id": "plan-test-084", "revision": 1, "actions": [],
            "numbers": [{"name": "n", "value": 1, "unit": "1", "source": "test", "grade": "E5"}],
            "stop_criteria": [{"id": "n", "number": "n", "metric": "n", "comparator": ">="}]}

    def setUp(self):
        super().setUp()
        # Until the software-motion check resolves a registry name to its Micro-Manager label (card
        # 091), it refuses a plan naming camera_red or camera_blue, so no plan acquires on a camera
        # on mock. This class lets that one check pass and changes nothing else in the run.
        real = orch.Orchestrator.check_software_motion_for
        orch.Orchestrator.check_software_motion_for = lambda o, plan, commands: None
        self.addCleanup(setattr, orch.Orchestrator, "check_software_motion_for", real)

    def _first_line(self, plan, run_id):
        runs = Path(self.tmp.name) / "runs"
        record = self.run_plan(plan, run_id, runs_root=runs)
        folder = runs / run_id
        return json.loads((folder / "events.jsonl").read_text(encoding="utf-8").splitlines()[0]), record

    def test_derived_from_the_plans_acquisition_fields_in_order(self):
        plan = {**self.PLAN, "id": "plan-test-084-two", "actions": [self.ACQ_BLUE, self.ACQ]}
        first, _ = self._first_line(plan, "run-20261026-841")
        self.assertEqual(first["tap_cameras"], [BLUE, RED])
        self.assertEqual(first["event"], "run_started")

    def test_a_plan_may_name_a_camera_by_its_device_label_too(self):
        plan = {**self.PLAN, "actions": [{**self.ACQ, "device": BLUE}, {**self.ACQ, "id": "a2", "device": "camera_red"}]}
        self.assertEqual(op.derive_tap_cameras(plan), [BLUE, RED])
        self.assertEqual(op.derive_tap_cameras({**self.PLAN, "focus_search": {"action": "a_red"}}), [RED])

    def test_a_camera_named_twice_is_listed_once(self):
        plan = {**self.PLAN, "id": "plan-test-084-dup", "actions": [self.ACQ, {**self.ACQ, "id": "a_red2"}]}
        first, _ = self._first_line(plan, "run-20261026-842")
        self.assertEqual(first["tap_cameras"], [RED])

    def test_a_plan_that_acquires_nothing_writes_an_empty_list(self):
        first, _ = self._first_line({**self.PLAN, "id": "plan-test-084-none"}, "run-20261026-843")
        self.assertEqual(first["tap_cameras"], [])

    def test_a_verb_that_does_not_acquire_names_no_camera(self):
        plan = {**self.PLAN, "id": "plan-test-084-set", "actions": [
            {"id": "a_set", "tier": 0, "device": "camera_red", "action": "set_exposure", "reversible": True}]}
        first, _ = self._first_line(plan, "run-20261026-844")
        self.assertEqual(first["tap_cameras"], [])

    def test_the_cameras_a_plan_lists_are_the_ones_the_tap_serves_after_the_run_acquires(self):
        plan = {**self.PLAN, "id": "plan-test-084-run", "actions": [self.ACQ, self.ACQ_BLUE]}
        captured = {}
        real = orch.Orchestrator.end_run

        def end_run(o, *a, **k):
            if o.frame_tap_address() is not None:
                captured["red"] = ask(o.frame_tap_address(), {"get": "latest_frame", "camera": RED})
                captured["blue"] = ask(o.frame_tap_address(), {"get": "latest_frame", "camera": BLUE})
            return real(o, *a, **k)
        orch.Orchestrator.end_run = end_run
        self.addCleanup(setattr, orch.Orchestrator, "end_run", real)
        self._first_line(plan, "run-20261026-845")
        for key, camera in (("red", RED), ("blue", BLUE)):
            head, body = captured[key]
            self.assertEqual((head["frame"], head["camera"]), (True, camera))
            self.assertGreater(len(body), 0)
        self.assertNotEqual(captured["red"][1], captured["blue"][1])


class T4TheSchemasExamplesAreTheTestsTable(unittest.TestCase):
    def setUp(self):
        if jsonschema is None:
            self.skipTest("jsonschema is not installed")

    def test_every_example_is_accepted_and_every_refused_one_is_refused_by_the_schema(self):
        for name in ("frame_tap_request", "frame_tap_header", "run_started"):
            definition = SCHEMA["$defs"][name]
            self.assertTrue(definition.get("examples"), name)
            for example in definition["examples"]:
                _check(name, example)
            for refused in definition.get("x_refused", []):
                with self.assertRaises(jsonschema.ValidationError, msg=(name, refused)):
                    _check(name, refused)

    def test_camera_name_is_the_pattern_the_tap_judges_by(self):
        for good in (RED, BLUE, "a", "Kinetix_red.2-b"):
            _check("camera_name", good)
        for bad in ("", "_x", "a b", "x" * 65, 7):
            with self.assertRaises(jsonschema.ValidationError, msg=bad):
                _check("camera_name", bad)

    def test_the_tap_accepts_each_request_example_and_refuses_each_x_refused(self):
        rig = _Rig(self, [RED, BLUE])
        rig.o.acquire_snap("camera_red")
        rig.o.acquire_snap("camera_blue")
        for example in SCHEMA["$defs"]["frame_tap_request"]["examples"]:
            camera = example.get("camera")
            head, body = ask(rig.tap, example)
            _check("frame_tap_header", head)
            self.assertTrue(head["frame"], example)
            self.assertEqual(head["camera"], camera or RED)
        refused = SCHEMA["$defs"]["frame_tap_request"]["x_refused"]
        for request in refused:
            self.assertEqual(ask(rig.tap, request), (None, b""), request)
        self.assertEqual(len([e for e in rig.o.log if e["event"] == "frame_tap_refused"]), len(refused))

    def test_every_reply_the_tap_gives_validates_against_the_header_schema(self):
        rig = _Rig(self, [RED, BLUE])
        for request in (BARE, {"get": "latest_frame", "camera": BLUE}, {"get": "latest_frame", "camera": "Kinetix_green"}):
            head, _ = ask(rig.tap, request)
            _check("frame_tap_header", head)
        rig.o.acquire_snap("camera_red")
        for request in (BARE, {"get": "latest_frame", "camera": RED}):
            head, _ = ask(rig.tap, request)
            _check("frame_tap_header", head)
            self.assertTrue(head["frame"])

    def test_run_started_validates_against_the_schema(self):
        rig = _Rig(self, [RED, BLUE])
        _check("run_started", rig.first_line())
        self.assertEqual(rig.first_line()["tap_cameras"], [RED, BLUE])


class T5ASlowReaderOfOneCameraDelaysNeitherTheRunNorTheOtherCamera(unittest.TestCase):
    def test_the_run_and_the_other_camera_go_on(self):
        rig = _Rig(self, [RED, BLUE])
        rig.mock.FRAME_SHAPE = (2048, 2048)                    # 8 MB, far more than a socket buffer holds
        rig.mock.FRAME_DELAY_S = 0.01
        rig.o.acquire_snap("camera_red")
        held = []
        for _ in range(3):
            # asks for red and never reads, so serving it fills the socket and that send blocks
            s = socket.create_connection((rig.tap["host"], rig.tap["port"]))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            s.sendall(line({"get": "latest_frame", "camera": RED}))
            held.append(s)
        held.append(socket.create_connection((rig.tap["host"], rig.tap["port"])))    # and one that never sends
        self.addCleanup(lambda: [s.close() for s in held])
        t0 = time.monotonic()
        got = []
        rig.o.acquire_sequence("camera_blue", 12, lambda i, img, md: got.append(i))
        run_s = time.monotonic() - t0
        self.assertEqual(got, list(range(12)))
        self.assertLess(run_s, 4.0)
        t1 = time.monotonic()
        head, body = ask(rig.tap, {"get": "latest_frame", "camera": BLUE}, timeout=5)
        answered_s = time.monotonic() - t1
        self.assertEqual((head["frame"], head["camera"], len(body)), (True, BLUE, 2048 * 2048 * 2))
        self.assertLess(answered_s, 0.5, "the other camera's reader waited behind the stuck one")


if __name__ == "__main__":
    unittest.main()
