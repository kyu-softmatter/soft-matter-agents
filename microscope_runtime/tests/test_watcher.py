"""Card 076 parts B and D: the watcher thread and its backends.

    python -m unittest microscope_runtime/tests/test_watcher.py

The watcher is handed data and hands back events. It holds no device module, no
core, no reference to abort, the stop channel or dispatch, so it can command
nothing and stop nothing. These tests drive it on synthetic frames and a fake
snapshot, with backends that are spies. Written BEFORE the module and watched
failing without it, then each rule switched off in turn.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


W = _load("_watcher_under_test", SRC / "watcher.py")
R = W.R

OPTIONS = [{"id": "as_planned"}, {"id": "particles_lost", "about": "particle_count"},
           {"id": "drifting", "about": "drift_px"}, {"id": "focus_lost", "about": "focus_score"},
           {"id": "unsure"}]
CONVERSION = {"downscale": {"longest_side_px": 16, "method": "area_mean"},
              "stretch": {"method": "percentile", "low_percentile": 1, "high_percentile": 99},
              "saturated": {"marked_as": "red"}}


def make_plan(given=False, gap=False, budget=0.3, cadence=0.05, settle=0.0, drift=True):
    image = {"frame_stats": {"metric": "vollath4", "bin_px": 4,
                             "camera_ceiling": {"gap": "full_scale_gap"} if gap else {"number": "camera_full_scale"}},
             "intensity": {"settle_after_s": settle}, "frames": {"given": given}}
    if given:
        image["frames"]["conversion"] = copy.deepcopy(CONVERSION)
    if drift:
        image["drift"] = {"reference_frame": 0, "method": "phase_correlation", "arguments": {"upsample": 10}}
    image["particles"] = {"detector": "log_blob",
                          "arguments": {"sigma_px": 2, "threshold": 0.1, "min_separation_px": 5}}
    return {"card": "plan", "id": "plan-test-076", "revision": 1,
            "numbers": [{"name": "camera_full_scale", "value": 65535, "unit": "ADU"}],
            "watcher": {"options": copy.deepcopy(OPTIONS), "cadence_s": cadence,
                        "question_budget_s": budget, "image": image}}


def frame(seed=1, amp=3000.0):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:48, 0:48]
    a = 500.0 + rng.normal(0, 20, (48, 48))
    for cy, cx in ((12, 12), (36, 36)):
        a += amp * np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / 8.0)
    return np.clip(a, 0, 65535).astype(np.uint16)


def no_light(event):
    return False


class Clock:
    def __init__(self):
        self.t0 = time.monotonic()

    def __call__(self):
        return time.monotonic() - self.t0


class SpyBackend(W.Backend):
    name, version, kind = "spy", "1", "test_double"

    def __init__(self, probabilities=None, gate=None, fail=None):
        self.calls, self.probabilities, self.gate, self.fail = [], probabilities, gate, fail

    def ask(self, state_text, options, images):
        self.calls.append({"text": state_text, "options": options, "images": images})
        if self.gate is not None:
            self.gate.wait(5)
        if self.fail is not None:
            raise self.fail
        if self.probabilities is not None:
            return {"probabilities": dict(self.probabilities)}
        ids = [o["id"] for o in options]
        return {"probabilities": {i: (1.0 if i == "as_planned" else 0.0) for i in ids}}


SNAPSHOT = {"t_mono": 0.0, "states": {"stand_ti2e": {"state": {"PFS": {"State": "Off"}}}}}


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.clock = Clock()
        self.events = []
        self.watchers = []

    def watcher(self, plan=None, backend=None, light=no_light, **kw):
        plan = plan or make_plan()
        w, first = W.build(plan, backend or SpyBackend(), self.folder, self.clock, light, **kw)
        self.assertIsNotNone(w, first)
        self.events.append(first)
        w.start()
        self.watchers.append(w)
        self.addCleanup(w.close)
        return w

    def pump(self, w, until, timeout=4.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.events.extend(w.drain())
            if until(self.events):
                return
            time.sleep(0.01)
        self.events.extend(w.drain())
        self.fail(f"timed out; events so far: {[e['event'] for e in self.events]}")

    def of(self, name):
        return [e for e in self.events if e["event"] == name]

    def tick(self, w, frames=1, seed=1, snapshot=None, events=(), t=None):
        for k in range(frames):
            w.put_frame(frame(seed + k), {}, self.clock())
        w.tick(snapshot or {**SNAPSHOT, "t_mono": self.clock()}, list(events), {"stand_ti2e": {"read_back": True}},
               self.clock() if t is None else t)


class T1ItHoldsNothing(_Base):
    """Test 1 of the card: no device module, no core, no abort, no stop channel, no dispatch."""

    FORBIDDEN_NAMES = {"abort", "dispatch", "stop", "stop_channel", "_stop", "core", "_core", "module_for",
                       "_device_module", "orchestrator", "begin_run", "end_run", "apply", "snapshot"}

    def reachable(self, root, depth=7):
        seen, stack, out = set(), [(root, 0)], []
        while stack:
            obj, d = stack.pop()
            if id(obj) in seen or d > depth:
                continue
            seen.add(id(obj))
            out.append(obj)
            if isinstance(obj, dict):
                stack.extend((v, d + 1) for v in list(obj.values()) + list(obj.keys()))
            elif isinstance(obj, (list, tuple, set, frozenset)):
                stack.extend((v, d + 1) for v in obj)
            elif isinstance(obj, types.FunctionType):
                stack.extend((c.cell_contents, d + 1) for c in (obj.__closure__ or ()) if _filled(c))
            elif isinstance(obj, types.MethodType):
                stack.append((obj.__self__, d + 1))
            elif hasattr(obj, "__dict__") and not isinstance(obj, (type, types.ModuleType)):
                stack.extend((v, d + 1) for v in vars(obj).values())
        return out

    def test_nothing_the_watcher_can_reach_can_command_or_stop(self):
        w = self.watcher()
        self.tick(w)
        bad = []
        for obj in self.reachable(w):
            if isinstance(obj, (threading.Thread, type(threading.Lock()), threading.Condition, threading.Event)):
                continue
            for name in self.FORBIDDEN_NAMES:
                if not isinstance(obj, (str, bytes, int, float, type(None), np.ndarray)) and hasattr(obj, name) \
                        and not isinstance(obj, types.ModuleType):
                    bad.append((type(obj).__name__, name))
        self.assertEqual(bad, [])

    def test_no_orchestrator_stop_channel_or_device_module_is_reachable(self):
        w = self.watcher()
        self.tick(w)
        for obj in self.reachable(w):
            self.assertNotIn(type(obj).__name__, {"Orchestrator", "_StopChannel", "_FrameTap"})
            if isinstance(obj, types.ModuleType):
                self.assertNotIn(Path(getattr(obj, "__file__", "") or "").parent.name, {"devices"})
                self.assertFalse(hasattr(obj, "abort"), obj.__name__)

    def test_the_source_never_names_the_things_it_must_not_reach(self):
        for name in ("watcher.py", "watcher_render.py"):
            tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.add((node.module or "").split(".")[0])
                if isinstance(node, ast.Attribute) and node.attr in {"abort", "dispatch", "stop_channel"}:
                    self.fail(f"{name}: names .{node.attr}")
                if isinstance(node, ast.Name) and node.id in {"abort", "dispatch", "input", "ask_person"}:
                    self.fail(f"{name}: names {node.id}")
            self.assertFalse(imported & {"orchestrator", "operator", "devices", "live_view", "socket"}, name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "spec_from_file_location":
                    arg = ast.unparse(node.args[1]) if len(node.args) > 1 else ""
                    self.assertNotIn("devices", arg)
                    self.assertNotIn("orchestrator", arg)
                    self.assertNotIn("operator", arg)


def _filled(cell):
    try:
        cell.cell_contents
        return True
    except ValueError:
        return False


class T2TheStartAndTheOff(_Base):
    def test_no_watcher_in_the_plan_is_recorded_as_off(self):
        plan = make_plan()
        del plan["watcher"]
        w, event = W.build(plan, SpyBackend(), self.folder, self.clock, no_light)
        self.assertIsNone(w)
        self.assertEqual(event["event"], "watcher_off")
        self.assertEqual(event["watcher"]["why"], "plan_declares_no_watcher")

    def test_a_block_the_renderer_cannot_render_is_off_with_the_name_and_the_run_goes_on(self):
        plan = make_plan()
        plan["watcher"]["options"].insert(1, {"id": "blurry", "about": "blur_amount"})
        w, event = W.build(plan, SpyBackend(), self.folder, self.clock, no_light)
        self.assertIsNone(w)
        self.assertEqual(event["watcher"]["why"], "did_not_start")
        self.assertIn("blur_amount", event["watcher"]["detail"])

    def test_a_camera_ceiling_that_does_not_resolve_is_off_and_says_why(self):
        plan = make_plan()
        plan["numbers"] = []
        w, event = W.build(plan, SpyBackend(), self.folder, self.clock, no_light)
        self.assertIsNone(w)
        self.assertEqual(event["watcher"]["why"], "did_not_start")

    def test_started_carries_the_backend_the_renderer_version_the_options_and_the_cadence(self):
        w = self.watcher(backend=SpyBackend())
        started = self.events[0]
        self.assertEqual(started["event"], "watcher_started")
        self.assertEqual(started["from"], "watcher")
        body = started["watcher"]
        self.assertEqual(body["backend"], {"name": "spy", "version": "1", "kind": "test_double"})
        self.assertEqual(body["renderer_version"], R.RENDERER_VERSION)
        self.assertEqual(body["options"], [o["id"] for o in OPTIONS])
        self.assertEqual((body["cadence_s"], body["question_budget_s"]), (0.05, 0.3))

    def test_the_test_double_is_refused_on_every_backend_but_mock(self):
        for device_backend in ("hardware", "micromanager", "real"):
            with self.assertRaisesRegex(W.BackendRefused, "mock"):
                W.make_backend("test_double", device_backend)
        self.assertEqual(W.make_backend("test_double", "mock").kind, "test_double")

    def test_none_and_an_unknown_backend(self):
        self.assertEqual(W.make_backend("none", "hardware").kind, "none")
        with self.assertRaisesRegex(W.BackendRefused, "unknown"):
            W.make_backend("gpt", "mock")

    def test_the_backend_is_not_a_plan_field(self):
        plan = make_plan()
        plan["watcher"]["backend"] = "test_double"
        w, event = W.build(plan, W.make_backend("none", "mock"), self.folder, self.clock, no_light)
        self.assertEqual(event["watcher"]["backend"]["kind"], "none")


class T3EveryTickWritesItsState(_Base):
    def test_the_state_is_recorded_whether_or_not_anyone_answers(self):
        w = self.watcher(backend=W.make_backend("none", "mock"))
        self.tick(w)
        self.tick(w, seed=2)
        self.pump(w, lambda e: len([x for x in e if x["event"] == "watcher_state"]) == 2)
        self.assertFalse(self.of("watcher_flag") or self.of("watcher_unanswered"))
        for state in self.of("watcher_state"):
            self.assertFalse(state["watcher"]["asked"])

    def test_the_text_is_kept_whole_and_its_hash_is_of_those_bytes(self):
        w = self.watcher(backend=W.make_backend("none", "mock"))
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        body = self.of("watcher_state")[0]["watcher"]
        self.assertEqual(body["state_path"], "watcher_state_000001.txt")
        data = (self.folder / body["state_path"]).read_bytes()
        self.assertEqual("sha256:" + hashlib.sha256(data).hexdigest(), body["state_sha256"])
        self.assertIn(R.RENDERER_VERSION, data.decode("utf-8"))

    def test_the_state_names_its_frame_and_its_snapshot_and_its_renderer(self):
        w = self.watcher(backend=W.make_backend("none", "mock"))
        self.tick(w, frames=3, snapshot={**SNAPSHOT, "t_mono": 0.5}, t=0.7)
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        body = self.of("watcher_state")[0]["watcher"]
        self.assertEqual(body["seq"], 1)
        self.assertEqual(body["frame_index"], 2)
        self.assertEqual(body["snapshot_t_mono"], 0.5)
        self.assertEqual(body["renderer_version"], R.RENDERER_VERSION)
        self.assertIsNotNone(body["frame_t_mono"])

    def test_a_tick_before_any_frame_still_writes_a_state_with_absent_values(self):
        w = self.watcher(backend=W.make_backend("none", "mock"))
        w.tick({**SNAPSHOT, "t_mono": 0.1}, [], {"stand_ti2e": {"read_back": True}}, 0.2)
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        body = self.of("watcher_state")[0]["watcher"]
        self.assertIsNone(body["frame_index"])
        self.assertIsNone(body["image"]["mean"]["value"])
        self.assertIn("absent_because", body["image"]["mean"])

    def test_sequence_numbers_count_up_by_one(self):
        w = self.watcher(backend=W.make_backend("none", "mock"))
        for k in range(3):
            self.tick(w, seed=k + 1)
        self.pump(w, lambda e: len(self.of("watcher_state")) == 3)
        self.assertEqual([s["watcher"]["seq"] for s in self.of("watcher_state")], [1, 2, 3])

    def test_the_frame_is_a_copy_the_watcher_owns(self):
        w = self.watcher(backend=W.make_backend("none", "mock"))
        img = frame()
        w.put_frame(img, {}, self.clock())
        img[:] = 0                                          # the run's own buffer is reused
        w.tick({**SNAPSHOT, "t_mono": 0.1}, [], {}, 0.2)
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        self.assertGreater(self.of("watcher_state")[0]["watcher"]["image"]["mean"]["value"], 100)


class T4TheQuestion(_Base):
    def test_an_answer_is_recorded_as_a_flag_that_names_its_state_even_as_planned(self):
        w = self.watcher(backend=SpyBackend())
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        flag = self.of("watcher_flag")[0]
        state = self.of("watcher_state")[0]["watcher"]
        body = flag["watcher"]
        self.assertEqual(flag["from"], "watcher")
        self.assertEqual((body["seq"], body["state_seq"]), (1, state["seq"]))
        self.assertEqual(body["state_sha256"], state["state_sha256"])
        self.assertEqual(body["options"], [o["id"] for o in OPTIONS])
        self.assertEqual(body["signals"]["choice"], "as_planned")
        self.assertEqual(body["signals"]["confidence"], 1.0)
        self.assertEqual(set(body["signals"]["probabilities"]), {o["id"] for o in OPTIONS})
        self.assertLessEqual(body["asked_t_mono"], body["answered_t_mono"])
        self.assertEqual(body["backend"]["kind"], "test_double")
        self.assertEqual(body["renderer_version"], R.RENDERER_VERSION)
        self.assertEqual(body["prompt_version"], W.PROMPT_VERSION)

    def test_the_backend_gets_the_text_and_the_options_in_order_and_nothing_else(self):
        spy = SpyBackend()
        w = self.watcher(backend=spy)
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        call = spy.calls[0]
        self.assertIsInstance(call["text"], str)
        self.assertEqual(call["options"], OPTIONS)
        self.assertIsNone(call["images"])

    def test_the_choice_is_the_most_likely_option_and_ties_go_to_the_first(self):
        probs = {"as_planned": 0.1, "particles_lost": 0.4, "drifting": 0.4, "focus_lost": 0.05, "unsure": 0.05}
        w = self.watcher(backend=SpyBackend(probabilities=probs))
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        signals = self.of("watcher_flag")[0]["watcher"]["signals"]
        self.assertEqual(signals["choice"], "particles_lost")
        self.assertEqual(signals["confidence"], 0.4)

    def test_probabilities_that_do_not_cover_the_options_are_a_backend_failure(self):
        w = self.watcher(backend=SpyBackend(probabilities={"as_planned": 1.0}))
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_unanswered")))
        body = self.of("watcher_unanswered")[0]["watcher"]
        self.assertEqual(body["why"], "backend_failed")
        self.assertIn("options", body["detail"])
        self.assertFalse(self.of("watcher_flag"))

    def test_probabilities_that_do_not_sum_to_one_are_a_backend_failure(self):
        probs = {o["id"]: 0.5 for o in OPTIONS}
        w = self.watcher(backend=SpyBackend(probabilities=probs))
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_unanswered")))
        self.assertEqual(self.of("watcher_unanswered")[0]["watcher"]["why"], "backend_failed")

    def test_a_backend_that_raises_is_recorded_unanswered_and_the_watcher_goes_on(self):
        spy = SpyBackend(fail=RuntimeError("model server is down"))
        w = self.watcher(backend=spy)
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_unanswered")))
        body = self.of("watcher_unanswered")[0]["watcher"]
        self.assertEqual(body["why"], "backend_failed")
        self.assertIn("model server is down", body["detail"])
        spy.fail = None
        self.tick(w, seed=2)
        self.pump(w, lambda e: bool(self.of("watcher_flag")))

    def test_the_test_double_is_deterministic_and_never_a_model(self):
        a = W.make_backend("test_double", "mock")
        ids = [o["id"] for o in OPTIONS]
        first = a.ask("a state", OPTIONS, None)
        self.assertEqual(first, a.ask("a state", OPTIONS, None))
        self.assertNotEqual(first, a.ask("another state", OPTIONS, None))
        self.assertAlmostEqual(sum(first["probabilities"].values()), 1.0)
        self.assertEqual(set(first["probabilities"]), set(ids))
        self.assertEqual(a.kind, "test_double")


class T5OneQuestionAtATime(_Base):
    def test_a_tick_that_falls_due_while_one_is_in_flight_is_skipped_and_counted_never_queued(self):
        gate = threading.Event()
        spy = SpyBackend(gate=gate)
        w = self.watcher(plan=make_plan(budget=3.0), backend=spy)
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_state")) and bool(spy.calls))
        self.tick(w, seed=2)
        self.tick(w, seed=3)
        self.pump(w, lambda e: len(self.of("watcher_state")) == 3)
        states = [s["watcher"] for s in self.of("watcher_state")]
        self.assertEqual([s["asked"] for s in states], [True, False, False])
        self.assertEqual([s["skipped_so_far"] for s in states], [0, 1, 2])
        self.assertEqual(len(spy.calls), 1)
        gate.set()
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        self.assertEqual(len(spy.calls), 1)                     # nothing was queued behind it

    def test_after_the_answer_the_next_tick_asks_again(self):
        spy = SpyBackend()
        w = self.watcher(backend=spy)
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        self.tick(w, seed=2)
        self.pump(w, lambda e: len(self.of("watcher_flag")) == 2)
        self.assertEqual([f["watcher"]["seq"] for f in self.of("watcher_flag")], [1, 2])

    def test_a_question_past_its_budget_is_unanswered_and_its_late_answer_is_dropped(self):
        gate = threading.Event()
        spy = SpyBackend(gate=gate)
        w = self.watcher(plan=make_plan(budget=0.1), backend=spy)
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_unanswered")))
        body = self.of("watcher_unanswered")[0]["watcher"]
        self.assertEqual(body["why"], "time_budget")
        self.assertEqual(body["state_seq"], 1)
        gate.set()
        time.sleep(0.2)
        self.events.extend(w.drain())
        self.assertFalse(self.of("watcher_flag"), "a late answer became a flag")
        self.tick(w, seed=2)                                    # the slot is free again
        self.pump(w, lambda e: bool(self.of("watcher_flag")))

    def test_a_question_still_open_when_the_run_ends_is_unanswered_run_ended(self):
        gate = threading.Event()
        w = self.watcher(plan=make_plan(budget=30.0), backend=SpyBackend(gate=gate))
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        time.sleep(0.1)
        w.close()
        self.events.extend(w.drain())
        gate.set()
        body = self.of("watcher_unanswered")[0]["watcher"]
        self.assertEqual(body["why"], "run_ended")
        self.assertEqual(body["state_seq"], 1)

    def test_closing_with_nothing_open_adds_nothing(self):
        w = self.watcher(backend=W.make_backend("none", "mock"))
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        w.close()
        self.events.extend(w.drain())
        self.assertFalse(self.of("watcher_unanswered"))

    def test_a_tick_after_close_is_ignored(self):
        w = self.watcher(backend=W.make_backend("none", "mock"))
        w.close()
        self.tick(w)
        time.sleep(0.1)
        self.assertEqual(w.drain(), [])


class T6TheReducedImages(_Base):
    def plan(self, **kw):
        return make_plan(given=True, **kw)

    def settle_and_tick(self, w, spy_events=()):
        """A light command whose read-back matched at t=0, settle 0 s, then a tick."""
        light = {"event": "apply", "t_mono": 0.0, "channel": "widefield_source_a", "verification": "readback"}
        self.tick(w, frames=2, events=[light] + list(spy_events))

    def test_with_given_false_no_image_is_made_or_passed(self):
        spy = SpyBackend()
        w = self.watcher(plan=make_plan(given=False), backend=spy)
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        self.assertIsNone(spy.calls[0]["images"])
        self.assertNotIn("images", self.of("watcher_state")[0]["watcher"])
        self.assertEqual(list(self.folder.glob("watcher_image_*")), [])

    def test_with_given_true_exactly_two_8_bit_images_reach_the_backend_and_no_16_bit_array_does(self):
        spy = SpyBackend()
        w = self.watcher(plan=self.plan(), backend=spy, light=lambda e: e.get("channel") == "widefield_source_a")
        self.settle_and_tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        images = spy.calls[0]["images"]
        self.assertEqual([i["role"] for i in images], ["current", "reference"])
        for image in images:
            self.assertIsInstance(image["png"], bytes)
            self.assertEqual(image["png"][:8], b"\x89PNG\r\n\x1a\n")
        seen = [spy.calls[0]["text"], spy.calls[0]["options"], images]
        self.assertFalse(self.contains_array(seen))

    def contains_array(self, obj, depth=0):
        if isinstance(obj, np.ndarray):
            return True
        if depth > 6:
            return False
        if isinstance(obj, dict):
            return any(self.contains_array(v, depth + 1) for v in obj.values())
        if isinstance(obj, (list, tuple)):
            return any(self.contains_array(v, depth + 1) for v in obj)
        return False

    def test_each_image_is_kept_whole_in_the_run_folder_and_its_hash_is_of_those_bytes(self):
        w = self.watcher(plan=self.plan(), backend=SpyBackend(), light=lambda e: e.get("channel") == "widefield_source_a")
        self.settle_and_tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        images = self.of("watcher_state")[0]["watcher"]["images"]
        self.assertEqual([i["role"] for i in images], ["current", "reference"])
        self.assertEqual([i["path"] for i in images], ["watcher_image_000001_current.png",
                                                       "watcher_image_000001_reference.png"])
        for image in images:
            data = (self.folder / image["path"]).read_bytes()
            self.assertEqual("sha256:" + hashlib.sha256(data).hexdigest(), image["sha256"])
            self.assertEqual(image["conversion_version"], R.CONVERSION_VERSION)
            self.assertEqual(len(image["shape"]), 3)
            self.assertGreater(image["stretch_limits"]["high"], image["stretch_limits"]["low"])
            self.assertIsInstance(image["saturated_pixels"], int)

    def test_the_two_images_are_the_current_frame_and_the_first_frame_after_the_light_settled(self):
        w = self.watcher(plan=self.plan(), backend=SpyBackend(), light=lambda e: e.get("channel") == "widefield_source_a")
        light = {"event": "apply", "t_mono": 0.0, "channel": "widefield_source_a", "verification": "readback"}
        self.tick(w, frames=2, events=[light], seed=1)            # frames 0 and 1; the reference is the first held
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        self.tick(w, frames=2, seed=10)                           # frames 2 and 3
        self.pump(w, lambda e: len(self.of("watcher_flag")) == 2)
        first, second = [s["watcher"]["images"] for s in self.of("watcher_state")]
        self.assertEqual(first[1]["frame_index"], second[1]["frame_index"])    # the reference never moves
        self.assertEqual(first[1]["sha256"], second[1]["sha256"])
        self.assertNotEqual(first[0]["frame_index"], second[0]["frame_index"])  # the current one does
        self.assertEqual(second[0]["frame_index"], 3)

    def test_before_the_light_has_settled_there_is_no_reference_and_that_tick_is_not_asked_text_only(self):
        spy = SpyBackend()
        w = self.watcher(plan=self.plan(settle=1000.0), backend=spy,
                         light=lambda e: e.get("channel") == "widefield_source_a")
        light = {"event": "apply", "t_mono": 0.0, "channel": "widefield_source_a", "verification": "readback"}
        self.tick(w, frames=2, events=[light])
        self.pump(w, lambda e: bool(self.of("watcher_unanswered")))
        self.assertEqual(spy.calls, [])
        state = self.of("watcher_state")[0]["watcher"]
        self.assertIn("images_not_given_because", state)
        self.assertEqual(self.of("watcher_unanswered")[0]["watcher"]["why"], "image_conversion_refused")

    def test_a_gap_ceiling_refuses_the_conversion_and_the_tick_is_unanswered_never_asked_text_only(self):
        spy = SpyBackend()
        w = self.watcher(plan=self.plan(gap=True), backend=spy,
                         light=lambda e: e.get("channel") == "widefield_source_a")
        self.settle_and_tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_unanswered")))
        self.assertEqual(spy.calls, [])
        state = self.of("watcher_state")[0]["watcher"]
        self.assertIn("gap", state["images_not_given_because"])
        self.assertNotIn("images", state)
        un = self.of("watcher_unanswered")[0]["watcher"]
        self.assertEqual(un["why"], "image_conversion_refused")
        self.assertIn("gap", un["detail"])
        self.assertFalse(self.of("watcher_flag"))

    def test_the_images_are_the_same_whichever_backend_answers(self):
        shots = []
        for backend in (SpyBackend(), W.make_backend("test_double", "mock")):
            with tempfile.TemporaryDirectory() as d:
                w, first = W.build(self.plan(), backend, Path(d), self.clock,
                                   lambda e: e.get("channel") == "widefield_source_a")
                w.start()
                light = {"event": "apply", "t_mono": 0.0, "channel": "widefield_source_a", "verification": "readback"}
                w.put_frame(frame(1), {}, 0.0)
                w.put_frame(frame(2), {}, 0.0)
                w.tick({**SNAPSHOT, "t_mono": 0.0}, [light], {}, 0.1)
                end = time.monotonic() + 4
                got = []
                while time.monotonic() < end and not [e for e in got if e["event"] == "watcher_state"]:
                    got.extend(w.drain())
                    time.sleep(0.01)
                shots.append([i["sha256"] for i in
                              [e for e in got if e["event"] == "watcher_state"][0]["watcher"]["images"]])
                w.close()
        self.assertEqual(shots[0], shots[1])


class T7TheLightAndTheLevel(_Base):
    def test_intensity_is_absent_and_says_settling_until_a_matched_light_command_has_settled(self):
        w = self.watcher(plan=make_plan(settle=1000.0), backend=W.make_backend("none", "mock"),
                         light=lambda e: e.get("channel") == "widefield_source_a")
        light = {"event": "apply", "t_mono": 0.0, "channel": "widefield_source_a", "verification": "readback"}
        self.tick(w, events=[light])
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        v = self.of("watcher_state")[0]["watcher"]["image"]["intensity_normalised"]
        self.assertIsNone(v["value"])
        self.assertIn("settling", v["absent_because"])

    def test_with_no_light_command_at_all_it_says_so_and_is_not_zero(self):
        w = self.watcher(backend=W.make_backend("none", "mock"))
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        v = self.of("watcher_state")[0]["watcher"]["image"]["intensity_normalised"]
        self.assertIsNone(v["value"])
        self.assertIn("no light-source command", v["absent_because"])

    def test_a_light_command_that_did_not_read_back_does_not_start_the_clock(self):
        w = self.watcher(backend=W.make_backend("none", "mock"), light=lambda e: True)
        light = {"event": "apply", "t_mono": 0.0, "channel": "widefield_source_a", "verification": "none"}
        self.tick(w, events=[light])
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        v = self.of("watcher_state")[0]["watcher"]["image"]["intensity_normalised"]
        self.assertIsNone(v["value"])
        self.assertIn("no light-source command", v["absent_because"])

    def test_once_settled_the_value_is_the_total_over_the_settled_frames_total(self):
        w = self.watcher(backend=W.make_backend("none", "mock"), light=lambda e: e.get("channel") == "widefield_source_a")
        light = {"event": "apply", "t_mono": 0.0, "channel": "widefield_source_a", "verification": "readback"}
        self.tick(w, frames=1, events=[light], seed=1)
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        v = self.of("watcher_state")[0]["watcher"]["image"]["intensity_normalised"]
        self.assertAlmostEqual(v["value"], 1.0)                 # the settled frame is its own level
        self.tick(w, frames=1, seed=1)
        self.pump(w, lambda e: len(self.of("watcher_state")) == 2)
        self.assertAlmostEqual(self.of("watcher_state")[1]["watcher"]["image"]["intensity_normalised"]["value"], 1.0)

    def test_the_drift_reference_is_the_frame_the_plan_names(self):
        w = self.watcher(backend=W.make_backend("none", "mock"))
        w.put_frame(frame(1), {}, 0.0)                          # frame 0, the plan's reference
        w.put_frame(np.roll(frame(1), (3, 4), axis=(0, 1)), {}, 0.1)
        w.tick({**SNAPSHOT, "t_mono": 0.1}, [], {}, 0.2)
        self.pump(w, lambda e: bool(self.of("watcher_state")))
        v = self.of("watcher_state")[0]["watcher"]["image"]["drift_px"]
        self.assertAlmostEqual(v["value"], 5.0, places=6)
        self.assertEqual(v["frame_index"], 1)


class T8TheRecords(_Base):
    BANNED = {"channel", "action", "params", "verification", "element"}

    def schema_check(self, event):
        try:
            import jsonschema
            from referencing import Registry, Resource
        except ImportError:                                     # pragma: no cover
            self.skipTest("jsonschema and referencing are not importable")
        resources = {f.name: Resource.from_contents(json.loads(f.read_text(encoding="utf-8")))
                     for f in (CONTRACTS / "schemas").glob("*.json")}
        registry = Registry().with_resources(resources.items())
        name = event["event"]
        validator = jsonschema.Draft202012Validator({"$ref": f"run_log.schema.json#/$defs/{name}"},
                                                    registry=registry)
        errors = [e.message for e in validator.iter_errors(event["watcher"])]
        self.assertEqual(errors, [], f"{name}: {errors}")

    def run_everything(self):
        w = self.watcher(plan=make_plan(given=True), backend=SpyBackend(),
                         light=lambda e: e.get("channel") == "widefield_source_a")
        light = {"event": "apply", "t_mono": 0.0, "channel": "widefield_source_a", "verification": "readback"}
        self.tick(w, frames=2, events=[light])
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        w.close()
        self.events.extend(w.drain())

    def test_every_watcher_event_carries_from_watcher_and_none_carries_a_commands_keys(self):
        self.run_everything()
        for event in self.events:
            if event["event"] == "watcher_off":
                continue
            self.assertEqual(event["from"], "watcher", event["event"])
            self.assertFalse(self.BANNED & set(event), (event["event"], self.BANNED & set(event)))
            self.assertFalse(self.BANNED & set(event["watcher"]), event["event"])

    def test_every_event_is_json_and_has_its_own_t_mono(self):
        self.run_everything()
        for event in self.events:
            json.dumps(event)
            self.assertIsInstance(event["t_mono"], float, event["event"])

    def test_every_payload_validates_against_the_run_log_schema(self):
        self.run_everything()
        for event in self.events:
            self.schema_check(event)

    def test_the_unanswered_and_off_payloads_validate_too(self):
        plan = make_plan()
        del plan["watcher"]
        _, off = W.build(plan, SpyBackend(), self.folder, self.clock, no_light)
        self.schema_check(off)
        gate = threading.Event()
        w = self.watcher(plan=make_plan(budget=0.1), backend=SpyBackend(gate=gate))
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_unanswered")))
        gate.set()
        for event in self.events:
            self.schema_check(event)

    def test_dm3_reading_of_an_answer(self):
        self.assertEqual(W.dm3_reading("as_planned"), {"judgement": "DM-3", "status": "OK", "answer": "NO"})
        self.assertEqual(W.dm3_reading("unsure"), {"judgement": "DM-3", "status": "ABSTAIN"})
        self.assertEqual(W.dm3_reading("drifting"),
                         {"judgement": "DM-3", "status": "OK", "answer": "YES", "class": "drifting"})

    def test_a_flag_carries_the_dm3_reading_of_its_choice(self):
        w = self.watcher(backend=SpyBackend(probabilities={"as_planned": 0.0, "particles_lost": 0.0,
                                                           "drifting": 1.0, "focus_lost": 0.0, "unsure": 0.0}))
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        self.assertEqual(self.of("watcher_flag")[0]["watcher"]["judgement"],
                         {"judgement": "DM-3", "status": "OK", "answer": "YES", "class": "drifting"})

    def test_there_is_no_path_from_an_answer_to_a_stop_or_a_prompt(self):
        spy = SpyBackend(probabilities={"as_planned": 0.0, "particles_lost": 1.0, "drifting": 0.0,
                                        "focus_lost": 0.0, "unsure": 0.0})
        w = self.watcher(backend=spy)
        self.tick(w)
        self.pump(w, lambda e: bool(self.of("watcher_flag")))
        names = {e["event"] for e in self.events}
        self.assertFalse(names & {"stop_criterion_violated", "abort_begin", "person_asked", "handover"})
        self.assertFalse(hasattr(W.Watcher, "abort") or hasattr(W.Watcher, "stop") or hasattr(W.Watcher, "ask_person"))


if __name__ == "__main__":
    unittest.main()
