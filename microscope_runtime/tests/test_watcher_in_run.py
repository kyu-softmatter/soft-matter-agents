"""Card 076 part C: the orchestrator's sampling, the tee, and the watcher on a mock run.

    python -m unittest microscope_runtime/tests/test_watcher_in_run.py

A run on the mock backend whose `observe` hook takes real time, so ticks fall due while it runs.
The orchestrator takes the watcher's snapshots, with `read(wait=False)` -- or, for a module that reads
per channel, `read_for(channel, wait=False, elements=...)` -- and nothing else, only on
channels this run's preflight reached; it feeds the watcher the run's frames through the same tee as
the frame tap; and it closes the watcher before `run_ended`. Written BEFORE the code and watched
failing without it, then each rule switched off in turn.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
TESTS = Path(__file__).resolve().parent
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_watcher_in_run_under_test", SRC / "operator.py")
orch = op.orch
TW = _load("_test_watcher_helpers_for_in_run", TESTS / "test_watcher.py")
W = TW.W

OK, BREAKS = 9.0, 1.0
CAMERA = op.LIVE_VIEW_ROUTES["Kinetix_red"]


def stream_plan(watcher=True, **kw):
    plan = {"card": "plan", "id": "plan-test-076", "revision": 1, "actions": [],
            "numbers": [{"name": "drift_um", "value": 5, "unit": "um", "source": "test", "grade": "E5"},
                        {"name": "camera_full_scale", "value": 65535, "unit": "ADU", "source": "test",
                         "grade": "E5"}],
            "stop_criteria": [{"id": "drift", "number": "drift_um", "metric": "drift", "comparator": ">"}]}
    if watcher:
        plan["watcher"] = TW.make_plan(**kw)["watcher"]
    return plan


#: What counts as a read at the device boundary: the generic one, and the per-channel one the mock
#: offers (card 086), which the orchestrator prefers when a module has it.
READS = ("read", "read_for")


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
        self.calls = []
        real_init, real_device = orch.Orchestrator.__init__, orch.Orchestrator._device_module

        def init(s, *a, **k):
            real_init(s, *a, **k)
            self.o = s
        orch.Orchestrator.__init__ = init
        orch.Orchestrator._device_module = lambda s, name, needed_by: Spy(name, real_device(s, name, needed_by),
                                                                          self.calls)
        self.addCleanup(lambda: [setattr(orch.Orchestrator, "__init__", real_init),
                                 setattr(orch.Orchestrator, "_device_module", real_device)])

    def run_it(self, plan, watcher_backend="none", hold=0.5, during=None, run_id="run-test-076",
               backend="mock"):
        self.plan_path.write_text(json.dumps(plan))

        def observe(metric):
            if during is not None:
                during(self.o)
            time.sleep(hold)
            return OK
        return op.run(self.plan_path, run_id, backend=backend, observe=observe, runs_root=self.root,
                      watcher_backend=watcher_backend)

    def lines(self, run_id="run-test-076"):
        text = (self.root / run_id / "events.jsonl").read_text(encoding="utf-8")
        return [json.loads(l) for l in text.splitlines() if l]

    def names(self, run_id="run-test-076"):
        return [e["event"] for e in self.lines(run_id)]

    def watcher_snapshots(self, run_id="run-test-076"):
        return [e for e in self.lines(run_id) if e["event"] == "snapshot" and e.get("label") == "watcher"]

    @staticmethod
    def frames(o):
        camera = o.module_for(CAMERA)
        getattr(camera, "_m", camera).FRAME_SHAPE = (48, 48)      # 2-D frames, as live view tests ask
        for _ in range(3):
            o.acquire_snap(CAMERA)
            time.sleep(0.05)


class T1RightAfterRunStarted(_Run):
    def test_a_watched_run_records_watcher_started_as_its_second_line(self):
        self.run_it(stream_plan(), hold=0.1)
        lines = self.lines()
        self.assertEqual([lines[0]["event"], lines[1]["event"]], ["run_started", "watcher_started"])
        self.assertEqual(lines[1]["from"], "watcher")
        self.assertEqual(lines[1]["watcher"]["backend"]["kind"], "none")

    def test_a_plan_with_no_watcher_records_watcher_off_as_its_second_line(self):
        self.run_it(stream_plan(watcher=False), hold=0.1)
        lines = self.lines()
        self.assertEqual(lines[1]["event"], "watcher_off")
        self.assertEqual(lines[1]["watcher"]["why"], "plan_declares_no_watcher")

    def test_a_watcher_that_could_not_start_is_off_with_the_name_and_the_run_goes_on(self):
        plan = stream_plan()
        plan["watcher"]["options"].insert(1, {"id": "blurry", "about": "blur_amount"})
        record = self.run_it(plan, hold=0.1)
        self.assertEqual(record["ended"], "completed")
        off = self.lines()[1]
        self.assertEqual((off["event"], off["watcher"]["why"]), ("watcher_off", "did_not_start"))
        self.assertIn("blur_amount", off["watcher"]["detail"])

    def test_the_backend_the_run_names_is_the_one_recorded(self):
        self.run_it(stream_plan(), watcher_backend="test_double", hold=0.1)
        self.assertEqual(self.lines()[1]["watcher"]["backend"],
                         {"name": "test_double", "version": "1", "kind": "test_double"})


class T2TheTicksHappenDuringTheRun(_Run):
    def test_snapshots_states_and_answers_are_recorded_while_it_runs_and_before_run_ended(self):
        self.run_it(stream_plan(), watcher_backend="test_double", hold=0.5, during=self.frames)
        names = self.names()
        self.assertEqual(names[-1], "run_ended")
        self.assertGreaterEqual(len(self.watcher_snapshots()), 3)
        self.assertGreaterEqual(names.count("watcher_state"), 3)
        self.assertGreaterEqual(names.count("watcher_flag"), 1)
        last_watcher = max(i for i, n in enumerate(names) if n.startswith("watcher_"))
        self.assertLess(last_watcher, len(names) - 1)

    def test_a_reader_following_the_run_sees_the_watchers_events_while_it_is_going(self):
        seen = {}

        def during(o):
            self.frames(o)
            time.sleep(0.4)
            seen["names"] = self.names()                        # the stream, read mid-run
        self.run_it(stream_plan(), watcher_backend="test_double", hold=0.1, during=during)
        self.assertIn("watcher_state", seen["names"], "the watcher's events reached the log only at the end")
        self.assertIn("watcher_flag", seen["names"])
        self.assertNotIn("run_ended", seen["names"])

    def test_the_log_and_the_stream_agree_and_the_run_still_completes(self):
        record = self.run_it(stream_plan(), watcher_backend="test_double", hold=0.4, during=self.frames)
        self.assertEqual(record["ended"], "completed")
        stream = [e for e in self.lines() if e["event"] != "run_started" and e["event"] != "run_ended"]
        self.assertEqual([e["event"] for e in stream], [e["event"] for e in record["events"]])

    def test_the_state_text_each_state_names_is_in_the_run_folder_and_its_hash_matches(self):
        import hashlib
        self.run_it(stream_plan(), watcher_backend="test_double", hold=0.4, during=self.frames)
        states = [e for e in self.lines() if e["event"] == "watcher_state"]
        self.assertTrue(states)
        for state in states:
            body = state["watcher"]
            data = (self.root / "run-test-076" / body["state_path"]).read_bytes()
            self.assertEqual("sha256:" + hashlib.sha256(data).hexdigest(), body["state_sha256"])

    def test_frames_the_run_acquires_reach_the_watcher_through_the_tee(self):
        self.run_it(stream_plan(), watcher_backend="none", hold=0.5, during=self.frames)
        states = [e["watcher"] for e in self.lines() if e["event"] == "watcher_state"]
        self.assertTrue([s for s in states if s["frame_index"] is not None], "no state ever saw a frame")
        self.assertTrue([s for s in states if s["image"]["mean"]["value"] is not None])

    def test_nothing_in_the_log_names_a_watcher_answer_as_a_stop(self):
        probs = {"as_planned": 0.0, "particles_lost": 0.0, "drifting": 1.0, "focus_lost": 0.0, "unsure": 0.0}
        record = self.run_it(stream_plan(), watcher_backend=TW.SpyBackend(probabilities=probs), hold=0.4,
                             during=self.frames)
        names = self.names()
        self.assertEqual(record["ended"], "completed")
        self.assertIn("watcher_flag", names)
        self.assertFalse({"abort_begin", "stop_criterion_violated", "person_asked"} & set(names))


class T3OnlyReadsAndOnlyOnOpenInterfaces(_Run):
    @staticmethod
    def open_stand(o):
        o.preflight(["stand_ti2e"])

    def non_reads(self):
        return [(m, a, args, kw) for (m, a, args, kw) in self.calls if a not in READS]

    def test_with_the_watcher_on_the_only_device_calls_a_run_gains_are_reads_with_wait_false(self):
        def during(o):
            self.open_stand(o)
            self.frames(o)
        self.run_it(stream_plan(watcher=False), hold=0.4, during=during, run_id="run-test-off")
        off_calls, self.calls[:] = list(self.calls), []
        self.run_it(stream_plan(), watcher_backend="test_double", hold=0.4, during=during, run_id="run-test-on")
        on = list(self.calls)
        on_non_reads = [(m, a) for (m, a, args, kw) in on if a not in READS]
        off_non_reads = [(m, a) for (m, a, args, kw) in off_calls if a not in READS]
        self.assertEqual(on_non_reads, off_non_reads, "the watcher added a device call that is not a read")
        extra = [(m, args, kw) for (m, a, args, kw) in on if a in READS]
        self.assertTrue(extra, "the watcher took no reads")
        watcher_reads = [(args, kw) for (_, args, kw) in extra if kw.get("wait") is False]
        self.assertTrue(watcher_reads, "none of the extra reads was a no-wait read")
        for args, kw in watcher_reads:
            self.assertLessEqual(len(args), 1, "a read took more than the channel it is for")
            self.assertEqual(set(kw) - {"elements"}, {"wait"})
            self.assertIs(kw["wait"], False)

    def test_a_channel_this_run_did_not_open_is_recorded_as_not_open_and_never_read(self):
        self.run_it(stream_plan(), hold=0.4, during=self.open_stand)
        snaps = self.watcher_snapshots()
        states = snaps[-1]["states"]
        closed = [c for c, st in states.items() if isinstance(st, dict) and st.get("not_open")]
        self.assertTrue(closed)
        self.assertNotIn("stand_ti2e", closed)
        self.assertIn("state", states["stand_ti2e"])
        no_wait_reads = [c for c in self.calls if c[1] in READS and c[3].get("wait") is False]
        self.assertEqual(len(no_wait_reads), len(snaps),
                         "the watcher read more than the one channel preflight opened")

    def test_without_any_preflight_nothing_is_read_at_all(self):
        self.run_it(stream_plan(), hold=0.4)
        for event in self.watcher_snapshots():
            for state in event["states"].values():
                self.assertTrue(state.get("not_open"), state)
        self.assertEqual([c for c in self.calls if c[1] in READS and c[3].get("wait") is False], [])

    def test_the_snapshot_reads_nothing_once_an_abort_has_begun_even_when_called_directly(self):
        o = orch.Orchestrator(backend="mock")
        o._preflight_state["stand_ti2e"] = {}
        before = o.watcher_snapshot()
        self.assertIn("state", before["stand_ti2e"])
        reads_before = len([c for c in self.calls if c[1] in READS and c[3].get("wait") is False])
        o._aborted.set()
        after = o.watcher_snapshot()
        self.assertEqual(len([c for c in self.calls if c[1] in READS and c[3].get("wait") is False]), reads_before,
                         "a read was taken after the abort began")
        for cid, state in after.items():
            self.assertTrue(state.get("not_read"), (cid, state))
            self.assertIn("abort", state["why"])

    def test_a_snapshot_event_carries_no_command_keys_and_is_labelled_for_the_watcher(self):
        self.run_it(stream_plan(), hold=0.4, during=self.open_stand)
        for event in self.watcher_snapshots():
            self.assertEqual(event["label"], "watcher")
            self.assertFalse({"channel", "action", "params", "verification"} & set(event))


class T4NeverWaitsAndNeverCarriesALastValue(_Run):
    def test_a_channel_whose_device_is_busy_is_recorded_not_read_with_why(self):
        held = {}

        def during(o):
            o.preflight(["stand_ti2e"])
            mod = o._modules.get("mock") or o._device_module("mock", needed_by="test")
            raw = getattr(mod, "_m", mod)
            held["lock"] = raw._LOCK
            time.sleep(0.12)                                    # let one clean tick happen first
            raw._LOCK.acquire()
            held["since"] = o.clock.offset()
            time.sleep(0.25)
            raw._LOCK.release()
            held["until"] = o.clock.offset()
        self.run_it(stream_plan(), hold=0.1, during=during)
        mid = [e for e in self.watcher_snapshots() if held["since"] + 0.05 < e["t_mono"] < held["until"]]
        self.assertTrue(mid, "no tick fell inside the held interval")
        for event in mid:
            state = event["states"]["stand_ti2e"]
            self.assertTrue(state.get("not_read"), state)
            self.assertIn("not to wait", state["why"])
            self.assertNotIn("state", state, "a busy channel was given a value")
        before = [e for e in self.watcher_snapshots() if e["t_mono"] < held["since"] - 0.02]
        self.assertTrue(before and "state" in before[-1]["states"]["stand_ti2e"])

    def test_a_channel_that_raises_is_recorded_with_its_error_and_the_run_goes_on(self):
        def during(o):
            o.preflight(["stand_ti2e"])
            raw = o._modules["mock"]
            def gone(*a, **k):
                raise RuntimeError("the interface went away")
            raw.read = gone
            raw.read_for = gone
        record = self.run_it(stream_plan(), hold=0.3, during=during)
        self.assertEqual(record["ended"], "completed")
        state = self.watcher_snapshots()[-1]["states"]["stand_ti2e"]
        self.assertTrue(state.get("not_read"))
        self.assertIn("the interface went away", state["why"])


class T5AbortAndTheEnd(_Run):
    def test_the_reads_stop_the_moment_an_abort_begins(self):
        marks = {}

        def during(o):
            o.preflight(["stand_ti2e"])
            time.sleep(0.2)
            marks["abort"] = o.clock.offset()
            o.abort("test")
            time.sleep(0.4)
        self.run_it(stream_plan(), hold=0.1, during=during)
        before = [e for e in self.watcher_snapshots() if e["t_mono"] <= marks["abort"]]
        after = [e for e in self.watcher_snapshots() if e["t_mono"] > marks["abort"] + 0.05]
        self.assertTrue(before)
        self.assertEqual(after, [], "a snapshot was taken after the abort began")

    def test_a_question_still_open_when_the_run_ends_is_unanswered_run_ended_before_run_ended(self):
        gate = threading.Event()
        spy = TW.SpyBackend(gate=gate)
        plan = stream_plan(budget=30.0)
        try:
            self.run_it(plan, watcher_backend=spy, hold=0.4, during=self.frames)
        finally:
            gate.set()
        names = self.names()
        un = [e for e in self.lines() if e["event"] == "watcher_unanswered"]
        self.assertTrue(un)
        self.assertEqual(un[-1]["watcher"]["why"], "run_ended")
        self.assertLess(names.index("watcher_unanswered"), names.index("run_ended"))
        self.assertEqual(names[-1], "run_ended")

    def test_closing_the_watcher_happens_before_run_ended_even_when_the_run_fails(self):
        def during(o):
            raise RuntimeError("the observer broke")
        try:
            self.run_it(stream_plan(), watcher_backend="test_double", hold=0.1, during=during)
        except RuntimeError:
            pass
        names = self.names()
        self.assertEqual(names[-1], "run_ended")


class T6TheBackendIsTheRunsArgument(_Run):
    def test_the_test_double_is_refused_on_any_backend_but_mock_before_anything_starts(self):
        self.plan_path.write_text(json.dumps(stream_plan()))
        with self.assertRaisesRegex(op.Refusal, "mock"):
            op.run(self.plan_path, "run-test-076", backend="hardware", runs_root=self.root,
                   watcher_backend="test_double")
        self.assertFalse((self.root / "run-test-076").exists())
        self.assertFalse((Path(self.tmp.name) / "run.lock").exists())

    def test_the_test_double_is_refused_even_when_the_plan_has_no_watcher(self):
        self.plan_path.write_text(json.dumps(stream_plan(watcher=False)))
        with self.assertRaisesRegex(op.Refusal, "mock"):
            op.run(self.plan_path, "run-test-076", backend="hardware", runs_root=self.root,
                   watcher_backend="test_double")

    def test_an_unknown_watcher_backend_is_refused(self):
        self.plan_path.write_text(json.dumps(stream_plan()))
        with self.assertRaisesRegex(op.Refusal, "unknown"):
            op.run(self.plan_path, "run-test-076", backend="mock", runs_root=self.root, watcher_backend="gpt")

    def test_no_watcher_backend_means_none_and_nobody_is_asked(self):
        self.run_it(stream_plan(), watcher_backend=None, hold=0.3, during=self.frames)
        names = self.names()
        self.assertEqual(self.lines()[1]["watcher"]["backend"]["kind"], "none")
        self.assertIn("watcher_state", names)
        self.assertFalse({"watcher_flag", "watcher_unanswered"} & set(names))

    def test_main_passes_the_option_through(self):
        got = {}
        real = op.run
        op.run = lambda plan, **kw: (got.update(kw), (_ for _ in ()).throw(op.Refusal("stop here")))[1]
        self.addCleanup(setattr, op, "run", real)
        self.plan_path.write_text(json.dumps(stream_plan()))
        op.main(["--plan", str(self.plan_path), "--run-id", "run-test-076", "--watcher-backend", "test_double"])
        self.assertEqual(got["watcher_backend"], "test_double")
        got.clear()
        op.main(["--plan", str(self.plan_path), "--run-id", "run-test-076"])
        self.assertIsNone(got["watcher_backend"])


class T7LightCommands(unittest.TestCase):
    def test_a_light_source_command_is_found_by_the_devices_the_orchestrator_declares(self):
        light = orch.is_light_command
        self.assertTrue(light({"event": "apply", "params": {"Aura.State": {"value": 1}}}))
        self.assertTrue(light({"event": "apply", "params": {"DiaLamp.Intensity": {"value": 100}}}))
        self.assertTrue(light({"event": "apply", "params": {"settings": {"Aura": {"State": 1}}}}))

    def test_other_events_and_other_devices_are_not_light_commands(self):
        light = orch.is_light_command
        self.assertFalse(light({"event": "snapshot", "params": {"Aura.State": 1}}))
        self.assertFalse(light({"event": "apply", "params": {"ZDrive.Position": {"value": 100}}}))
        self.assertFalse(light({"event": "apply", "params": None}))
        self.assertFalse(light({"event": "apply"}))

    def test_a_source_that_software_may_not_command_is_not_matched_by_name(self):
        self.assertFalse(orch.is_light_command({"event": "apply", "params": {"LightEngine.State": 1}}))


class T8TheRecordsValidate(_Run):
    def test_every_watcher_event_and_snapshot_of_a_mock_run_validates_against_the_run_log_schema(self):
        try:
            import jsonschema
            from referencing import Registry, Resource
        except ImportError:                                     # pragma: no cover
            self.skipTest("jsonschema and referencing are not importable")
        resources = {f.name: Resource.from_contents(json.loads(f.read_text(encoding="utf-8")))
                     for f in (CONTRACTS / "schemas").glob("*.json")}
        registry = Registry().with_resources(resources.items())
        self.run_it(stream_plan(), watcher_backend="test_double", hold=0.5, during=self.frames)
        checked = 0
        for event in self.lines():
            if event["event"].startswith("watcher_") and "watcher" in event:
                validator = jsonschema.Draft202012Validator(
                    {"$ref": f"run_log.schema.json#/$defs/{event['event']}"}, registry=registry)
                errors = [e.message for e in validator.iter_errors(event["watcher"])]
                self.assertEqual(errors, [], f"{event['event']}: {errors}")
                checked += 1
        self.assertGreaterEqual(checked, 5)


class T9TheAbortDelay(_Run):
    """Test 4 of the card: how long one read in progress delays an abort, measured on mock."""

    READ_S = 0.4

    def measure(self, slow, run_id):
        out = {}

        def during(o):
            o.preflight(["stand_ti2e"])
            raw = o._modules["mock"]
            if slow:
                entered = threading.Event()

                def slow_read(wait=True):
                    if not raw._LOCK.acquire(blocking=wait):
                        raise raw.ReadWouldWait("mock: busy, asked not to wait")
                    try:
                        entered.set()
                        time.sleep(self.READ_S)
                        return {"state": {}, "backend": "mock"}
                    finally:
                        raw._LOCK.release()
                raw.read = slow_read
                raw.read_for = lambda cid, wait=True, elements=(): slow_read(wait)
                self.assertTrue(entered.wait(3.0), "the watcher never began a read")
            else:
                time.sleep(0.2)
            started = time.perf_counter()
            o.abort("measure the delay")
            out["delay_s"] = time.perf_counter() - started
        self.run_it(stream_plan(), hold=0.05, during=during, run_id=run_id)
        return out["delay_s"]

    def test_an_abort_waits_at_most_one_read_for_a_read_already_in_progress(self):
        idle = self.measure(slow=False, run_id="run-test-076-idle")
        self.calls.clear()
        busy = self.measure(slow=True, run_id="run-test-076-busy")
        extra = busy - idle
        print(f"\n[abort delay on mock] idle abort {idle * 1000:.1f} ms, abort during a "
              f"{self.READ_S * 1000:.0f} ms read {busy * 1000:.1f} ms, delay {extra * 1000:.1f} ms", flush=True)
        self.assertLessEqual(extra, self.READ_S + 0.25, "an abort waited longer than one read")
        self.assertGreaterEqual(extra, -0.05)


if __name__ == "__main__":
    unittest.main()
