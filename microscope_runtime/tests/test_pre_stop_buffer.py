"""Card 082: the rolling pre-stop buffer, its save after an abort, and the refusal of a plan without one.

    python -m unittest microscope_runtime/tests/test_pre_stop_buffer.py

plan.md 4.6.1 (the person's Q5, 2026-10-19): a stop keeps the last `length_s` seconds of frames the run
already acquired and saves them AFTER the abort has finished, lamps off and shutters closed and read back;
nothing emits light after a stop. A plan authored by microscope_agent that has no `pre_stop_buffer` block is
refused before any command. Mock only, every run folder a temporary directory.

The run's clock is replaced by a settable one, so which frames fall inside the window is decided by the test
and not by how fast the machine is. Written BEFORE the code and watched failing without it, then each rule
switched off in turn.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
sys.path.insert(0, str(SRC))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_pre_stop_buffer_under_test", SRC / "operator.py")
orch = op.orch

OK, BREAKS = 9.0, 1.0
CAMERA = op.LIVE_VIEW_ROUTES["Kinetix_red"]
FILE = "pre_stop_buffer.frames"


def device_plan(block="default", author="microscope_agent", **extra):
    plan = {"card": "plan", "id": "plan-test-082", "revision": 1, "actions": [], "author": author,
            "numbers": [{"name": "drift_um", "value": 5, "unit": "um", "source": "test", "grade": "E5"}],
            "stop_criteria": [{"id": "drift", "number": "drift_um", "metric": "drift", "comparator": ">"}]}
    if block == "default":
        block = {"length_s": 3.0}
    if block is not None:
        plan["pre_stop_buffer"] = block
    plan.update(extra)
    return plan


class Spy:
    """Logs every public call on a device module, with its arguments, and passes it through."""

    def __init__(self, name, module, log):
        self._name, self._m, self._log = name, module, log

    def __getattr__(self, attr):
        value = getattr(self._m, attr)
        if callable(value) and not attr.startswith("_") and attr[:1].islower():
            def call(*a, **k):
                self._log.append((self._name, attr, a, k))
                return value(*a, **k)
            return call
        return value


def send_stop(addr, run_id):
    payload = json.dumps({"stop": run_id, "reason": "test"}).encode() + b"\n"
    with socket.create_connection((addr["host"], addr["port"]), timeout=10) as s:
        s.sendall(payload)
        s.shutdown(socket.SHUT_WR)
        out = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                return out
            out += chunk


def read_buffer(path):
    """The saved file: one JSON header line, then every frame's bytes in the header's order."""
    raw = Path(path).read_bytes()
    head, _, body = raw.partition(b"\n")
    header = json.loads(head)
    frames, pos = [], 0
    for entry in header["frames"]:
        frames.append((entry, body[pos:pos + entry["bytes"]]))
        pos += entry["bytes"]
    assert pos == len(body), "bytes after the last frame"
    return header, frames


class _Run(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "runs"
        self.plan_path = Path(self.tmp.name) / "plan.json"
        saved = op.load_safety, op.approvals_on_disk, op.RUN_LOCK_PATH
        op.load_safety = lambda *a, **k: {"policy_version": "test", "targets": []}
        op.approvals_on_disk = lambda *a, **k: []
        op.RUN_LOCK_PATH = Path(self.tmp.name) / "run.lock"
        self.addCleanup(lambda: [setattr(op, "load_safety", saved[0]), setattr(op, "approvals_on_disk", saved[1]),
                                 setattr(op, "RUN_LOCK_PATH", saved[2])])
        self.o = None
        self.constructed = 0
        self.calls = []
        real_init, real_device = orch.Orchestrator.__init__, orch.Orchestrator._device_module

        def init(s, *a, **k):
            real_init(s, *a, **k)
            self.o = s
            self.constructed += 1
        orch.Orchestrator.__init__ = init
        orch.Orchestrator._device_module = lambda s, name, needed_by: Spy(name, real_device(s, name, needed_by),
                                                                          self.calls)
        self.addCleanup(lambda: [setattr(orch.Orchestrator, "__init__", real_init),
                                 setattr(orch.Orchestrator, "_device_module", real_device)])

    def run_it(self, plan, how="monitor", times=(), stop_t=None, run_id="run-test-082", before_stop=None):
        """One mock run. `times` are the instants (run seconds) at which one frame each is acquired, then
        the run is stopped at `stop_t` in the way `how` says: monitor, outside, blind or normal."""
        self.plan_path.write_text(json.dumps(plan))
        self.images = []
        now = [0.0]

        def observe(metric):
            o = self.o
            o.clock.offset = lambda: now[0]
            camera = o.module_for(CAMERA)
            getattr(camera, "_m", camera).FRAME_SHAPE = (6, 5)
            for t in times:
                now[0] = float(t)
                image, _ = o.acquire_snap(CAMERA)
                self.images.append((float(t), bytes(image.tobytes() if hasattr(image, "tobytes") else image)))
                if hasattr(image, "fill"):
                    image.fill(7)           # the run's own copy is changed; the buffer's must not be
            now[0] = float(times[-1] if stop_t is None and times else (stop_t if stop_t is not None else 0.0))
            if before_stop is not None:
                before_stop(o)
            if how == "outside":
                addr = self.lines(run_id)[0]["stop_channel"]
                send_stop(addr, run_id)
                return OK
            return {"monitor": BREAKS, "blind": None, "normal": OK}[how]
        return op.run(self.plan_path, run_id, backend="mock", observe=observe, runs_root=self.root)

    def lines(self, run_id="run-test-082"):
        text = (self.root / run_id / "events.jsonl").read_text(encoding="utf-8")
        return [json.loads(l) for l in text.splitlines() if l]

    def names(self, run_id="run-test-082"):
        return [e["event"] for e in self.lines(run_id)]

    def saved(self, run_id="run-test-082"):
        return [e for e in self.lines(run_id) if e["event"] == "pre_stop_buffer_saved"]

    def not_saved(self, run_id="run-test-082"):
        return [e for e in self.lines(run_id) if e["event"] == "pre_stop_buffer_not_saved"]


class T1RefusalWithoutTheBlock(_Run):
    def refused(self, plan):
        with self.assertRaises(op.Refusal) as caught:
            self.run_it(plan, times=(1.0,))
        return str(caught.exception)

    def test_a_device_plan_without_the_block_is_refused_naming_the_rule(self):
        reason = self.refused(device_plan(block=None))
        self.assertIn("4.6.1", reason)
        self.assertIn("pre_stop_buffer", reason)

    def test_nothing_goes_out_and_nothing_is_written(self):
        self.refused(device_plan(block=None))
        self.assertEqual(self.constructed, 0, "an orchestrator was built for a plan that is refused")
        self.assertEqual(self.calls, [], "a device was called for a plan that is refused")
        self.assertFalse(self.root.exists(), "a run folder exists for a plan that is refused")

    def test_a_block_that_does_not_state_a_length_is_refused(self):
        for block in ({}, {"length_s": None}, {"length_s": "3"}, {"length_s": True}, {"length_s": -1},
                      {"length_s": float("nan")}, {"length_s": float("inf")}):
            with self.subTest(block=block):
                self.assertIn("4.6.1", self.refused(device_plan(block=block)))

    def test_a_block_that_names_a_rate_or_anything_else_is_refused(self):
        self.assertIn("4.6.1", self.refused(device_plan(block={"length_s": 2, "rate_hz": 10})))

    def test_a_block_that_is_not_an_object_is_refused(self):
        self.assertIn("4.6.1", self.refused(device_plan(block=3)))

    def test_the_refusal_comes_before_the_run_lock_is_taken(self):
        self.refused(device_plan(block=None))
        self.assertFalse(op.RUN_LOCK_PATH.exists(), "the run lock was taken for a plan that is refused")

    def test_a_plan_with_the_block_is_not_refused_and_zero_written_is_allowed(self):
        for length in (0, 0.0, 2.5):
            with self.subTest(length=length):
                run_id = f"run-test-082-{length}"
                self.run_it(device_plan(block={"length_s": length}), how="normal", run_id=run_id,
                            times=(1.0,))
                self.assertEqual(self.lines(run_id)[-1]["how"], "completed")

    def test_a_plan_not_authored_by_microscope_agent_is_exempt(self):
        for author in ("simulation_agent", "human", None):
            with self.subTest(author=author):
                plan = device_plan(block=None, author=author)
                if author is None:
                    del plan["author"]
                run_id = f"run-test-082-{author}"
                self.run_it(plan, how="normal", run_id=run_id, times=(1.0,))
                self.assertEqual(self.lines(run_id)[-1]["how"], "completed")


class T2TheWindowIsSaved(_Run):
    def test_a_stop_from_outside_saves_exactly_the_frames_of_the_last_length_s(self):
        self.run_it(device_plan(block={"length_s": 3.0}), how="outside",
                    times=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], stop_t=9.5)
        event, = self.saved()
        buffer = event["buffer"]
        header, frames = read_buffer(self.root / "run-test-082" / buffer["path"])
        kept = [(f["index"], f["t_mono"]) for f, _ in frames]
        self.assertEqual(kept, [(7, 7.0), (8, 8.0), (9, 9.0)])        # t >= 9.5 - 3.0 = 6.5
        self.assertEqual((buffer["frames"], buffer["first_frame_index"], buffer["last_frame_index"]), (3, 7, 9))
        self.assertEqual(buffer["length_s"], 3.0)

    def test_every_kind_of_stop_saves_it(self):
        for how in ("monitor", "outside", "blind"):
            with self.subTest(how=how):
                run_id = f"run-test-082-{how}"
                self.run_it(device_plan(block={"length_s": 2.0}), how=how, times=[0, 1, 2, 3], stop_t=3.5,
                            run_id=run_id)
                event, = self.saved(run_id)
                self.assertEqual(event["buffer"]["frames"], 2)
                self.assertEqual(event["buffer"]["last_frame_index"], 3)

    def test_the_sha256_is_of_exactly_the_saved_bytes(self):
        self.run_it(device_plan(), how="monitor", times=[0, 1, 2], stop_t=2.5)
        event, = self.saved()
        raw = (self.root / "run-test-082" / event["buffer"]["path"]).read_bytes()
        self.assertEqual(event["buffer"]["sha256"], "sha256:" + hashlib.sha256(raw).hexdigest())

    def test_the_file_holds_the_frames_as_the_run_made_them_and_not_as_the_run_left_them(self):
        self.run_it(device_plan(block={"length_s": 5.0}), how="monitor", times=[0, 1, 2], stop_t=2.5)
        event, = self.saved()
        _, frames = read_buffer(self.root / "run-test-082" / event["buffer"]["path"])
        self.assertEqual([body for _, body in frames], [image for _, image in self.images])
        self.assertFalse(all(set(body) == {7} for _, body in frames), "the buffer holds the run's own array")

    def test_the_measured_rate_comes_from_the_frames_kept(self):
        self.run_it(device_plan(block={"length_s": 10.0}), how="monitor", times=[0, 0.5, 1.0, 1.5, 2.0],
                    stop_t=2.2)
        event, = self.saved()
        self.assertAlmostEqual(event["buffer"]["recorded_rate_hz"], 2.0, places=6)

    def test_fewer_than_two_frames_has_no_rate(self):
        self.run_it(device_plan(block={"length_s": 1.0}), how="monitor", times=[0, 5], stop_t=5.5)
        event, = self.saved()
        self.assertEqual(event["buffer"]["frames"], 1)
        self.assertIsNone(event["buffer"]["recorded_rate_hz"])

    def test_the_event_is_the_one_the_run_log_schema_asks_for(self):
        import jsonschema
        schema = json.loads((CONTRACTS / "schemas" / "run_log.schema.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator({"$ref": "#/$defs/event", "$defs": schema["$defs"]})
        self.run_it(device_plan(), how="monitor", times=[0, 1, 2], stop_t=2.5)
        event, = self.saved()
        self.assertEqual(event["from"], "pre_stop_buffer")
        validator.validate(event)
        for key in ("channel", "action", "params", "verification", "deletion"):
            self.assertNotIn(key, event)


class T3SavedAfterTheAbort(_Run):
    def test_the_save_follows_the_abort_whatever_kind_of_stop(self):
        for how in ("monitor", "outside", "blind"):
            with self.subTest(how=how):
                run_id = f"run-test-082-order-{how}"
                self.run_it(device_plan(), how=how, times=[0, 1], stop_t=1.5, run_id=run_id)
                names = self.names(run_id)
                saved = names.index("pre_stop_buffer_saved")
                for before in ("abort_begin", "abort_shutter_coverage", "abort_light_sources", "abort_end"):
                    self.assertLess(names.index(before), saved, f"{before} did not come first: {names}")
                self.assertLess(saved, names.index("run_ended"))

    def test_the_abort_reached_every_channel_before_the_buffer_was_touched(self):
        """A device-call order check: every module abort() the run makes precedes the save's event."""
        self.run_it(device_plan(), how="monitor", times=[0, 1], stop_t=1.5)
        names = self.names()
        report = [e for e in self.lines() if e["event"] == "abort_end"][0]["report"]
        self.assertTrue(report["channels"], "the abort reached no channel")
        self.assertLess(names.index("abort_end"), names.index("pre_stop_buffer_saved"))

    def test_a_save_that_fails_leaves_the_abort_whole_and_is_recorded_once(self):
        folder = self.root / "run-test-082"
        def block_the_file(o):
            (folder / FILE).mkdir()         # a directory where the file must go: writing it fails
        self.run_it(device_plan(), how="monitor", times=[0, 1], stop_t=1.5, before_stop=block_the_file)
        names = self.names()
        self.assertIn("abort_end", names)
        self.assertNotIn("pre_stop_buffer_saved", names)
        failed, = self.not_saved()
        self.assertEqual(failed["from"], "pre_stop_buffer")
        self.assertEqual(failed["why"], "save_failed")
        self.assertTrue(failed["detail"])
        self.assertLess(names.index("abort_end"), names.index("pre_stop_buffer_not_saved"))
        self.assertEqual(self.lines()[-1]["how"], "aborted_by_monitor")

    def test_a_second_abort_does_not_save_a_second_time(self):
        self.run_it(device_plan(), how="monitor", times=[0, 1], stop_t=1.5,
                    before_stop=lambda o: None)
        self.o.abort(reason="again")
        self.assertEqual([e["event"] for e in self.o.log].count("pre_stop_buffer_saved"), 1)


class T4NoDeviceCallOfItsOwn(_Run):
    def device_calls(self):
        return [(name, attr) for name, attr, _, _ in self.calls]

    def test_the_only_device_calls_are_the_ones_the_run_makes_without_it(self):
        for how in ("monitor", "outside", "normal"):
            with self.subTest(how=how):
                self.calls.clear()
                self.run_it(device_plan(block={"length_s": 3.0}), how=how, times=[0, 1, 2], stop_t=2.5,
                            run_id=f"run-test-082-with-{how}")
                with_it = self.device_calls()
                self.calls.clear()
                self.run_it(device_plan(block=None, author="human"), how=how, times=[0, 1, 2], stop_t=2.5,
                            run_id=f"run-test-082-without-{how}")
                self.assertEqual(with_it, self.device_calls())

    def test_the_buffer_holds_no_device_module_or_core(self):
        buffer = orch._PreStopBuffer(2.0)
        for value in vars(buffer).values():
            self.assertNotIsInstance(value, (orch.Orchestrator, Spy))
            self.assertFalse(hasattr(value, "snap") or hasattr(value, "sequence") or hasattr(value, "abort"),
                             f"the buffer holds {type(value).__name__}")

    def test_it_acquires_nothing_when_no_frame_arrives(self):
        self.run_it(device_plan(), how="monitor", times=[], stop_t=1.0)
        failed, = self.not_saved()
        self.assertEqual(failed["why"], "no_frames")
        self.assertFalse([c for c in self.device_calls() if c[1] in ("snap", "sequence")],
                         "the run acquired a frame it was not asked for")


class T5ZeroKeepsNothing(_Run):
    def test_zero_saves_no_file_and_says_so(self):
        self.run_it(device_plan(block={"length_s": 0}), how="monitor", times=[0, 1, 2], stop_t=2.5)
        self.assertEqual(self.saved(), [])
        said, = self.not_saved()
        self.assertEqual((said["why"], said["from"]), ("length_zero", "pre_stop_buffer"))
        self.assertEqual((said["length_s"], said["frames"]), (0, 0))
        self.assertNotIn("buffer", said)       # the schema reserves `buffer` for the saved event
        self.assertFalse((self.root / "run-test-082" / FILE).exists())

    def test_zero_holds_no_copy_while_the_run_goes(self):
        held = {}
        self.run_it(device_plan(block={"length_s": 0}), how="monitor", times=[0, 1, 2], stop_t=2.5,
                    before_stop=lambda o: held.setdefault("n", o._pre_stop.kept()))
        self.assertEqual(held["n"], 0)


class T5bNowhereToSave(_Run):
    def test_a_stop_with_no_run_folder_says_it_had_nowhere_to_save(self):
        """Without --write there is no run folder, so no ring: the stop records that, never a file."""
        plan = device_plan()
        self.plan_path.write_text(json.dumps(plan))
        op.run(self.plan_path, "run-test-082-nofolder", backend="mock", observe=lambda m: BREAKS)
        events = [e for e in self.o.log if e["event"].startswith("pre_stop_buffer")]
        said, = events
        self.assertEqual((said["event"], said["why"]), ("pre_stop_buffer_not_saved", "no_run_folder"))
        self.assertEqual(list(self.root.glob("*")) if self.root.exists() else [], [])


class T6NormalEndSavesNothing(_Run):
    def test_a_run_that_completes_writes_neither_event_nor_file(self):
        self.run_it(device_plan(), how="normal", times=[0, 1, 2], stop_t=2.5)
        names = self.names()
        self.assertNotIn("pre_stop_buffer_saved", names)
        self.assertNotIn("pre_stop_buffer_not_saved", names)
        self.assertEqual(self.lines()[-1]["how"], "completed")
        self.assertFalse((self.root / "run-test-082" / FILE).exists())


class T7TheRing(unittest.TestCase):
    """The ring on its own: a window in the run's seconds, not a count of frames."""

    @staticmethod
    def frame(n):
        return np.full((2, 2), n, dtype=np.uint8)

    def test_it_keeps_by_time_and_drops_what_has_aged_out(self):
        ring = orch._PreStopBuffer(3.0)
        for t in range(0, 101):
            ring.put(self.frame(t % 250), {}, float(t))
        self.assertLessEqual(ring.kept(), 4)
        self.assertGreaterEqual(ring.kept(), 3)

    def test_the_rate_is_the_runs_own_so_more_frames_in_the_window_are_all_kept(self):
        ring = orch._PreStopBuffer(1.0)
        for i in range(50):
            ring.put(self.frame(1), {}, i * 0.01)
        self.assertEqual(ring.kept(), 50)

    def test_a_frame_exactly_length_s_before_the_stop_is_inside_the_window(self):
        ring = orch._PreStopBuffer(3.0)
        for t in (5.0, 6.0, 7.0, 8.0, 9.0):
            ring.put(self.frame(1), {}, t)
        ring.stop_at(9.0)
        self.assertEqual([e[1] for e in ring.window()], [6.0, 7.0, 8.0, 9.0])

    def test_a_frame_after_the_stop_is_not_kept_and_pushes_nothing_out(self):
        ring = orch._PreStopBuffer(3.0)
        for t in (6.0, 7.0, 8.0, 9.0):
            ring.put(self.frame(1), {}, t)
        ring.stop_at(9.0)
        ring.put(self.frame(2), {}, 9.4)
        ring.put(self.frame(2), {}, 20.0)
        self.assertEqual([e[1] for e in ring.window()], [6.0, 7.0, 8.0, 9.0])

    def test_a_frame_that_read_its_clock_after_the_stop_but_landed_before_the_freeze_is_outside(self):
        """The tee reads the clock, the abort reads it, then each takes the lock in either order: a frame can
        sit in the ring with a t_mono later than the stop's own instant. It is not before the stop."""
        ring = orch._PreStopBuffer(3.0)
        for t in (6.0, 7.0, 8.0, 9.0, 9.4):
            ring.put(self.frame(1), {}, t)
        ring.stop_at(9.0)
        self.assertEqual([e[1] for e in ring.window()], [7.0, 8.0, 9.0])

    def test_the_window_is_cut_at_the_stop_even_if_the_ring_holds_older_frames(self):
        ring = orch._PreStopBuffer(2.0)
        for t in (0.0, 1.0, 2.0, 3.0):
            ring.put(self.frame(1), {}, t)
        ring.stop_at(3.5)
        self.assertEqual([e[1] for e in ring.window()], [2.0, 3.0])

    def test_it_copies_what_it_is_given(self):
        ring = orch._PreStopBuffer(5.0)
        image = self.frame(3)
        ring.put(image, {"k": 1}, 1.0)
        image.fill(9)
        (_, _, kept, metadata), = ring.window()
        self.assertEqual(int(kept[0, 0]), 3)
        self.assertEqual(metadata, {"k": 1})

    def test_byte_frames_are_kept_too(self):
        ring = orch._PreStopBuffer(5.0)
        ring.put(bytearray(b"abc"), {}, 1.0)
        self.assertEqual(ring.kept(), 1)

    def test_zero_keeps_nothing(self):
        ring = orch._PreStopBuffer(0)
        ring.put(self.frame(1), {}, 1.0)
        self.assertEqual(ring.kept(), 0)

    def test_indexes_count_every_frame_the_run_offered_in_order(self):
        ring = orch._PreStopBuffer(1.0)
        for t in (0.0, 1.0, 2.0, 3.0):
            ring.put(self.frame(1), {}, t)
        ring.stop_at(3.0)
        self.assertEqual([e[0] for e in ring.window()], [2, 3])


if __name__ == "__main__":
    unittest.main()
