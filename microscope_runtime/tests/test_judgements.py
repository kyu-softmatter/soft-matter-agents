"""Card 081: the four judgements of plan.md 13.5, record-only.

    python -m unittest microscope_runtime/tests/test_judgements.py

DM-3 is card 076's watcher, whose flags carry the DM-3 reading of their choice; DM-1 and DM-2 are asked at
every point a plan names that the run reaches, DM-4 after a stop's abort and its save. Each question and answer
is a record: no code path leads from an answer to a move, a skip, a retry, the stop channel or a prompt to the
person. Mock only, every run folder a temporary directory; the run's clock is a settable one so the
order of events is the test's and not the machine's. Written BEFORE the code and watched failing without it,
then each rule switched off in turn.
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
from pathlib import Path

import numpy as np

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


op = _load("_op_judgements_under_test", SRC / "operator.py")
orch = op.orch
J = _load("_judgements_under_test", SRC / "judgements.py")
TW = _load("_test_watcher_helpers_for_judgements", TESTS / "test_watcher.py")
W = TW.W
R = W.R

OK_VALUE, BREAKS = 9.0, 1.0
CAMERA = op.LIVE_VIEW_ROUTES["Kinetix_red"]
DM12_CODES = ["too_dense", "too_sparse", "out_of_focus"]
HANG_S = 30.0       # a bound that only a hang crosses, never a busy machine
DM4_LABELS = ["focus_drift", "particle_lost", "unknown"]


def block(points, given=False, codes=None, labels=None, version="p1"):
    out = {"points": list(points), "prompt_version": version,
           "frames": {"given": given}}
    if given:
        out["frames"]["conversion"] = copy.deepcopy(TW.CONVERSION)
    if labels is not None:
        out["cause_labels"] = list(labels)
    else:
        out["reason_codes"] = list(codes or DM12_CODES)
    return out


def jplan(dm1=("after_measure:drift",), dm2=("before_measure:drift", "run_start"), dm4=("stop",), given=False,
          watcher=False, length=3.0, author="microscope_agent", extra_ids=()):
    plan = {"card": "plan", "id": "plan-test-081", "revision": 2, "actions": [], "author": author,
            "numbers": [{"name": "drift_um", "value": 5, "unit": "um", "source": "test", "grade": "E5"},
                        {"name": "camera_full_scale", "value": 65535, "unit": "ADU", "source": "test", "grade": "E5"}],
            "stop_criteria": [{"id": "drift", "number": "drift_um", "metric": "drift", "comparator": ">"}],
            "pre_stop_buffer": {"length_s": length}, "judgements": {}}
    for ident in extra_ids:
        plan["stop_criteria"].append({"id": ident, "number": "drift_um", "metric": "drift", "comparator": ">"})
    if dm1:
        plan["judgements"]["dm1"] = block(dm1, given)
    if dm2:
        plan["judgements"]["dm2"] = block(dm2, given)
    if dm4:
        plan["judgements"]["dm4"] = block(dm4, given, labels=DM4_LABELS)
    if watcher:
        plan["watcher"] = TW.make_plan(given=False)["watcher"]
    return plan


class SpyJudge(W.Backend):
    """Records every question; answers as told, by judgement."""

    name, version, kind = "spy-judge", "7", "test_double"

    def __init__(self, answers=None, gate=None, fail=None):
        self.calls, self.answers, self.gate, self.fail = [], answers or {}, gate, fail

    def judge(self, judgement, prompt, allowed_codes, images):
        self.calls.append({"judgement": judgement, "prompt": prompt, "codes": list(allowed_codes),
                           "images": images})
        if self.gate is not None:
            self.gate.wait(5)
        if self.fail is not None:
            raise self.fail
        if judgement in self.answers:
            return copy.deepcopy(self.answers[judgement])
        if judgement == "DM-4":
            return {"status": "OK", "answer": "YES", "cause_label": "focus_drift"}
        return {"status": "OK", "answer": "YES", "reason_codes": [allowed_codes[0]]}


class Spy:
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


class _Unit(unittest.TestCase):
    """The judgements object on its own: data in, events out."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.now = [0.0]
        self.events = []

    def make(self, plan=None, backend=None):
        backend = backend or SpyJudge()
        self.backend = backend
        j, started = J.build(plan or jplan(), backend, self.folder, lambda: self.now[0])
        self.assertIsNotNone(j, started)
        self.started = started
        j.start()
        self.addCleanup(j.close)
        return j

    def settle(self, j, wait_s=2.0):
        j.close(wait_s)
        self.events.extend(j.drain())
        return self.events

    def of(self, name, judgement=None):
        return [e for e in self.events if e["event"] == name
                and (judgement is None or e["judgement"]["judgement"] == judgement)]


class T2AskedAtEveryPoint(_Unit):
    def test_dm1_and_dm2_are_asked_at_each_point_the_plan_names_each_time_it_is_reached(self):
        plan = jplan(dm1=("before_measure:drift", "after_measure:drift", "before_measure:c3"),
                     dm2=("after_measure:drift", "after_measure:c3"), dm4=None, extra_ids=("c3",))
        j = self.make(plan)
        for point in ("before_measure:drift", "after_measure:drift", "before_measure:c3", "after_measure:c3", "after_measure:drift"):
            self.now[0] += 1
            j.reach(point)
        self.settle(j)
        asked = [(e["judgement"]["judgement"], e["judgement"]["point"]) for e in self.of("judgement_asked")]
        self.assertEqual(sorted(asked), sorted([("DM-1", "before_measure:drift"), ("DM-1", "after_measure:drift"), ("DM-1", "before_measure:c3"), ("DM-1", "after_measure:drift"),
                                                ("DM-2", "after_measure:drift"), ("DM-2", "after_measure:c3"), ("DM-2", "after_measure:drift")]))

    def test_a_point_no_judgement_names_asks_nobody(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=("after_measure:drift",), dm4=None))
        j.reach("p9")
        self.settle(j)
        self.assertEqual(self.of("judgement_asked"), [])
        self.assertEqual(self.backend.calls, [])

    def test_the_stop_point_is_not_asked_by_reach_and_dm4_is_never_asked_at_a_moment_before_a_stop(self):
        j = self.make(jplan(dm1=None, dm2=None, dm4=("stop",)))
        j.reach("stop")
        self.settle(j)
        self.assertEqual(self.backend.calls, [])

    def test_every_answer_pairs_with_its_request_by_seq_and_seqs_are_unique(self):
        j = self.make(jplan(dm1=("before_measure:drift", "after_measure:drift"), dm2=("before_measure:drift",), dm4=None))
        j.reach("before_measure:drift")
        j.reach("after_measure:drift")
        self.settle(j)
        asked = {e["judgement"]["seq"]: e for e in self.of("judgement_asked")}
        answered = {e["judgement"]["seq"]: e for e in self.of("judgement_answered")}
        self.assertEqual(len(asked), 3)
        self.assertEqual(set(asked), set(answered))
        for seq in asked:
            self.assertEqual(asked[seq]["judgement"]["judgement"], answered[seq]["judgement"]["judgement"])
            self.assertEqual(asked[seq]["from"], answered[seq]["from"])

    def test_each_request_is_written_before_its_answer(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None))
        j.reach("before_measure:drift")
        self.settle(j)
        self.assertEqual([e["event"] for e in self.events], ["judgement_asked", "judgement_answered"])

    def test_from_names_the_plans_block(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=("before_measure:drift",), dm4=None))
        j.reach("before_measure:drift")
        self.settle(j)
        self.assertEqual(sorted(e["from"] for e in self.of("judgement_asked")), ["judgements.dm1", "judgements.dm2"])


class T5TheRecord(_Unit):
    def test_the_context_is_kept_whole_in_the_run_folder_with_its_hash(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None))
        j.reach("before_measure:drift")
        self.settle(j)
        request = self.of("judgement_asked")[0]["judgement"]
        self.assertRegex(request["context_path"], r"^judgement_\d{6}_context\.txt$")
        raw = (self.folder / request["context_path"]).read_bytes()
        self.assertEqual(request["context_sha256"], "sha256:" + hashlib.sha256(raw).hexdigest())
        self.assertEqual(request["allowed_answers"], ["YES", "NO"])
        self.assertEqual(request["allowed_codes"], DM12_CODES)
        self.assertIn(b"question:", raw)
        self.assertIn("before_measure:drift", raw.decode("utf-8"))

    def test_the_prompt_version_is_keyed_by_judgement_and_plan_in_the_request_and_the_answer(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=("before_measure:drift",), dm4=None))
        j.reach("before_measure:drift")
        self.settle(j)
        for judgement in ("DM-1", "DM-2"):
            asked = self.of("judgement_asked", judgement)[0]["judgement"]
            answered = self.of("judgement_answered", judgement)[0]["judgement"]
            self.assertEqual(asked["prompt_version"], answered["prompt_version"])
            for part in (judgement.lower().replace("-", ""), "plan-test-081", "p1"):
                self.assertIn(part, asked["prompt_version"])
        self.assertNotEqual(self.of("judgement_asked", "DM-1")[0]["judgement"]["prompt_version"],
                            self.of("judgement_asked", "DM-2")[0]["judgement"]["prompt_version"])

    def test_the_answer_names_the_model_and_its_version(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None))
        j.reach("before_measure:drift")
        self.settle(j)
        answer = self.of("judgement_answered")[0]["judgement"]
        self.assertEqual(answer["model"], {"name": "spy-judge", "version": "7", "kind": "test_double"})
        self.assertEqual(answer["status"], "OK")
        self.assertEqual((answer["answer"], answer["reason_codes"]), ("YES", ["too_dense"]))

    def test_an_abstain_has_no_answer(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None), SpyJudge({"DM-1": {"status": "ABSTAIN"}}))
        j.reach("before_measure:drift")
        self.settle(j)
        answer = self.of("judgement_answered")[0]["judgement"]
        self.assertEqual(answer["status"], "ABSTAIN")
        self.assertNotIn("answer", answer)

    def test_a_score_is_kept_as_the_model_gave_it_and_never_acted_on(self):
        score = {"kind": "suitability", "value": 0.37}
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None),
                      SpyJudge({"DM-1": {"status": "OK", "answer": "NO", "reason_codes": [], "score": score}}))
        j.reach("before_measure:drift")
        self.settle(j)
        self.assertEqual(self.of("judgement_answered")[0]["judgement"]["score"], score)

    def test_a_backend_that_fails_is_an_error_with_its_message(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None), SpyJudge(fail=RuntimeError("backend down")))
        j.reach("before_measure:drift")
        self.settle(j)
        answer = self.of("judgement_answered")[0]["judgement"]
        self.assertEqual(answer["status"], "ERROR")
        self.assertIn("backend down", answer["error"])
        self.assertNotIn("answer", answer)

    def test_an_answer_that_breaks_the_shape_is_an_error_not_a_record_of_something_else(self):
        bad = {"DM-1": {"status": "OK", "answer": "MAYBE", "reason_codes": ["too_dense"]}}
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None), SpyJudge(bad))
        j.reach("before_measure:drift")
        self.settle(j)
        self.assertEqual(self.of("judgement_answered")[0]["judgement"]["status"], "ERROR")

    def test_a_reason_code_the_plan_did_not_declare_is_an_error(self):
        bad = {"DM-1": {"status": "OK", "answer": "YES", "reason_codes": ["too_blue"]}}
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None), SpyJudge(bad))
        j.reach("before_measure:drift")
        self.settle(j)
        answer = self.of("judgement_answered")[0]["judgement"]
        self.assertEqual(answer["status"], "ERROR")
        self.assertIn("too_blue", answer["error"])

    def test_an_ok_answer_with_no_answer_is_an_error(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None), SpyJudge({"DM-1": {"status": "OK"}}))
        j.reach("before_measure:drift")
        self.settle(j)
        self.assertEqual(self.of("judgement_answered")[0]["judgement"]["status"], "ERROR")

    def test_a_question_still_open_when_the_run_ends_is_an_error_and_its_late_answer_is_dropped(self):
        gate = threading.Event()
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None), SpyJudge(gate=gate))
        j.reach("before_measure:drift")
        self.settle(j, wait_s=0.05)
        gate.set()
        time.sleep(0.2)
        self.events.extend(j.drain())
        answers = self.of("judgement_answered")
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["judgement"]["status"], "ERROR")
        self.assertIn("run", answers[0]["judgement"]["error"])

    def test_every_request_and_answer_validates_against_the_judgement_schema(self):
        import jsonschema
        from referencing import Registry, Resource
        judgement_schema = json.loads((CONTRACTS / "schemas" / "judgement.schema.json").read_text(encoding="utf-8"))
        run_log = json.loads((CONTRACTS / "schemas" / "run_log.schema.json").read_text(encoding="utf-8"))
        registry = Registry().with_resource("judgement.schema.json", Resource.from_contents(judgement_schema))
        validator = jsonschema.Draft202012Validator({"$ref": "#/$defs/event", "$defs": run_log["$defs"]},
                                                    registry=registry)
        answers = {"DM-1": {"status": "OK", "answer": "NO", "reason_codes": ["too_sparse"]},
                   "DM-2": {"status": "ABSTAIN"},
                   "DM-4": {"status": "OK", "answer": "YES", "cause_label": "particle_lost",
                            "score": {"kind": "confidence", "value": 0.9}}}
        j = self.make(jplan(), SpyJudge(answers))
        for point in ("after_measure:drift", "before_measure:drift", "run_start"):
            self.now[0] += 1
            j.reach(point)
        j.stopped("a test stop", [], None, [], self.now[0] + 1)
        self.settle(j)
        names = [e["event"] for e in self.events]
        self.assertGreaterEqual(names.count("judgement_asked"), 4)
        for event in self.events:
            event = {"t_mono": 0.0, "time_base": "software", **event}
            validator.validate(event)
            for key in ("channel", "action", "params", "verification", "deletion"):
                self.assertNotIn(key, event)

    def test_a_bad_answer_validates_too_because_it_is_an_error_record(self):
        import jsonschema
        from referencing import Registry, Resource
        judgement_schema = json.loads((CONTRACTS / "schemas" / "judgement.schema.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator({"$ref": "#/$defs/response", "$defs": judgement_schema["$defs"]})
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None), SpyJudge(fail=RuntimeError("down")))
        j.reach("before_measure:drift")
        self.settle(j)
        validator.validate(self.of("judgement_answered")[0]["judgement"])


class Dm4Answers(_Unit):
    def stopped(self, j, window=(), saved=None):
        j.stopped("monitor said so", list(window), saved, ["abort_begin", "abort_end"], self.now[0])
        self.settle(j)

    def test_unknown_is_a_no_and_never_a_cause(self):
        j = self.make(jplan(dm1=None, dm2=None), SpyJudge({"DM-4": {"status": "OK", "answer": "NO",
                                                                   "cause_label": "unknown"}}))
        self.stopped(j)
        answer = self.of("judgement_answered", "DM-4")[0]["judgement"]
        self.assertEqual((answer["status"], answer["answer"], answer["cause_label"]), ("OK", "NO", "unknown"))

    def test_a_yes_that_names_unknown_is_an_error(self):
        j = self.make(jplan(dm1=None, dm2=None), SpyJudge({"DM-4": {"status": "OK", "answer": "YES",
                                                                   "cause_label": "unknown"}}))
        self.stopped(j)
        self.assertEqual(self.of("judgement_answered", "DM-4")[0]["judgement"]["status"], "ERROR")

    def test_a_yes_without_a_cause_or_with_one_the_plan_did_not_list_is_an_error(self):
        for answer in ({"status": "OK", "answer": "YES"},
                       {"status": "OK", "answer": "YES", "cause_label": "gremlins"}):
            with self.subTest(answer=answer):
                self.events = []
                j = self.make(jplan(dm1=None, dm2=None), SpyJudge({"DM-4": answer}))
                self.stopped(j)
                self.assertEqual(self.of("judgement_answered", "DM-4")[-1]["judgement"]["status"], "ERROR")

    def test_a_dm4_answer_carries_a_cause_label_and_never_reason_codes(self):
        j = self.make(jplan(dm1=None, dm2=None))
        self.stopped(j)
        answer = self.of("judgement_answered", "DM-4")[0]["judgement"]
        self.assertEqual(answer["cause_label"], "focus_drift")
        self.assertNotIn("reason_codes", answer)
        self.assertEqual(self.of("judgement_asked", "DM-4")[0]["judgement"]["allowed_codes"], DM4_LABELS)

    def test_dm4_naming_anything_but_the_stop_is_off_naming_the_point(self):
        built, event = J.build(jplan(dm1=None, dm2=None, dm4=("somewhere_else",)), SpyJudge(), self.folder,
                               lambda: 0.0)
        self.assertIsNone(built)
        self.assertEqual((event["event"], event["judgements"]["why"]), ("judgements_off", "did_not_start"))
        self.assertIn("somewhere_else", event["judgements"]["detail"])

    def test_a_plan_with_no_dm4_asks_nothing_after_a_stop(self):
        j = self.make(jplan(dm4=None))
        self.stopped(j)
        self.assertEqual(self.of("judgement_asked", "DM-4"), [])


class T7Images(_Unit):
    def setUp(self):
        super().setUp()
        self.plan = jplan(dm1=("before_measure:drift",), dm2=None, dm4=None, given=True, watcher=True)

    def test_with_images_given_the_backend_gets_only_reduced_png_copies_and_never_the_raw_frame(self):
        j = self.make(self.plan)
        raw = TW.frame(3)
        j.put_frame(raw, {}, 1.0)
        j.reach("before_measure:drift")
        self.settle(j)
        images = self.backend.calls[0]["images"]
        self.assertEqual(len(images), 1)
        self.assertTrue(images[0]["png"].startswith(b"\x89PNG"))
        self.assertNotEqual(images[0]["png"], raw.tobytes())
        ref = self.of("judgement_asked")[0]["judgement"]["images"][0]
        self.assertEqual(ref["role"], "current")
        self.assertEqual(ref["sha256"], "sha256:" + hashlib.sha256(images[0]["png"]).hexdigest())
        self.assertEqual((self.folder / ref["path"]).read_bytes(), images[0]["png"])
        data, _ = R.convert_frame(raw, TW.CONVERSION, 65535)
        self.assertEqual(images[0]["png"], data)

    def test_with_images_not_given_the_backend_gets_none(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None, given=False, watcher=True))
        j.put_frame(TW.frame(3), {}, 1.0)
        j.reach("before_measure:drift")
        self.settle(j)
        self.assertIn(self.backend.calls[0]["images"], (None, []))
        self.assertEqual(self.of("judgement_asked")[0]["judgement"]["images"], [])

    def test_a_frame_that_is_not_a_2d_image_gives_no_image_and_says_why_in_the_context(self):
        j = self.make(self.plan)
        j.put_frame(b"\x00\x01\x02", {}, 1.0)
        j.reach("before_measure:drift")
        self.settle(j)
        request = self.of("judgement_asked")[0]["judgement"]
        self.assertEqual(request["images"], [])
        self.assertIn("2-D", (self.folder / request["context_path"]).read_text(encoding="utf-8"))

    def test_no_frame_yet_gives_no_image_and_says_so(self):
        j = self.make(self.plan)
        j.reach("before_measure:drift")
        self.settle(j)
        request = self.of("judgement_asked")[0]["judgement"]
        self.assertEqual(request["images"], [])
        self.assertIn("no frame", (self.folder / request["context_path"]).read_text(encoding="utf-8"))

    def test_with_the_camera_ceiling_a_gap_no_image_is_made_against_an_assumed_count(self):
        plan = copy.deepcopy(self.plan)
        plan["watcher"]["image"]["frame_stats"]["camera_ceiling"] = {"gap": "full_scale_gap"}
        j = self.make(plan)
        j.put_frame(TW.frame(3), {}, 1.0)
        j.reach("before_measure:drift")
        self.settle(j)
        self.assertEqual(self.of("judgement_asked")[0]["judgement"]["images"], [])

    def test_a_plan_with_no_watcher_block_has_no_ceiling_so_no_image(self):
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None, given=True, watcher=False))
        j.put_frame(TW.frame(3), {}, 1.0)
        j.reach("before_measure:drift")
        self.settle(j)
        request = self.of("judgement_asked")[0]["judgement"]
        self.assertEqual(request["images"], [])
        self.assertIn("ceiling", (self.folder / request["context_path"]).read_text(encoding="utf-8"))

    def test_the_fixed_detections_are_in_the_context_when_the_plan_declares_a_detector(self):
        j = self.make(self.plan)
        j.put_frame(TW.frame(3), {}, 1.0)
        j.reach("before_measure:drift")
        self.settle(j)
        text = (self.folder / self.of("judgement_asked")[0]["judgement"]["context_path"]).read_text(encoding="utf-8")
        self.assertIn("particle_count", text)
        self.assertNotIn("drift_px", text)       # a drift needs a reference this object does not track

    def test_dm4_images_are_the_buffers_frames_reduced_in_order(self):
        plan = jplan(dm1=None, dm2=None, given=True, watcher=True)
        j = self.make(plan)
        window = [(i, 10.0 + i, TW.frame(i), {"n": i}) for i in (4, 5, 6)]
        j.stopped("a stop", window, {"frames": 3}, [], 13.0)
        self.settle(j)
        refs = self.of("judgement_asked", "DM-4")[0]["judgement"]["images"]
        self.assertEqual([r["frame_index"] for r in refs], [4, 5, 6])
        self.assertEqual([r["role"] for r in refs], ["pre_stop_000", "pre_stop_001", "pre_stop_002"])
        for ref, (index, _, array, _) in zip(refs, window):
            data, _ = R.convert_frame(array, TW.CONVERSION, 65535)
            self.assertEqual(ref["sha256"], "sha256:" + hashlib.sha256(data).hexdigest())
        for call_image in self.backend.calls[0]["images"]:
            self.assertTrue(call_image["png"].startswith(b"\x89PNG"))


class T3NothingReachesAnythingElse(_Unit):
    FORBIDDEN_NAMES = {"abort", "dispatch", "stop", "stop_channel", "_stop", "core", "_core", "module_for",
                       "_device_module", "orchestrator", "begin_run", "end_run", "apply", "snapshot",
                       "ask_person", "record"}

    def test_the_object_reaches_no_device_module_core_abort_stop_channel_dispatch_or_prompt(self):
        j = self.make()
        seen, stack = set(), [(j, 0)]
        while stack:
            obj, depth = stack.pop()
            if id(obj) in seen or depth > 6:
                continue
            seen.add(id(obj))
            self.assertNotIsInstance(obj, (orch.Orchestrator,), "the judgements object reaches the orchestrator")
            if isinstance(obj, dict):
                for key, value in obj.items():
                    self.assertNotIn(key, self.FORBIDDEN_NAMES)
                    stack.append((value, depth + 1))
            elif isinstance(obj, (list, tuple, set)):
                stack.extend((v, depth + 1) for v in obj)
            elif hasattr(obj, "__dict__") and not isinstance(obj, (type, Path, threading.Thread)):
                for key, value in vars(obj).items():
                    self.assertNotIn(key, self.FORBIDDEN_NAMES)
                    stack.append((value, depth + 1))

    def test_the_source_imports_nothing_that_commands_and_calls_nothing_that_stops(self):
        text = (SRC / "judgements.py").read_text(encoding="utf-8")
        code = "\n".join(re.sub(r"#.*", "", line) for line in text.splitlines())
        code = re.sub(r'""".*?"""', "", code, flags=re.S)
        for token in ("orchestrator", "devices", "operator", ".abort(", "module_for", "stop_channel", "ask_person",
                      "dispatch(", "subprocess", "socket"):
            self.assertNotIn(token, code, f"judgements.py mentions {token!r}")
        for line in code.splitlines():
            if line.startswith(("import ", "from ")):
                self.assertNotRegex(line, r"orchestrator|devices|operator|mock|micromanager")

    def test_what_a_backend_answers_cannot_name_an_action(self):
        wild = {"DM-1": {"status": "OK", "answer": "YES", "reason_codes": ["too_dense"], "action": "stop",
                         "abort": True, "move_um": 5}}
        j = self.make(jplan(dm1=("before_measure:drift",), dm2=None, dm4=None), SpyJudge(wild))
        j.reach("before_measure:drift")
        self.settle(j)
        answer = self.of("judgement_answered")[0]["judgement"]
        for key in ("action", "abort", "move_um"):
            self.assertNotIn(key, answer)


class T6Backends(unittest.TestCase):
    def test_the_test_double_is_refused_off_mock(self):
        with self.assertRaises(J.W.BackendRefused):
            J.make_backend("test_double", "micromanager")

    def test_none_asks_nobody_and_the_test_double_answers_all_four(self):
        none = J.make_backend("none", "mock")
        with self.assertRaises(RuntimeError):
            none.judge("DM-1", "q", ["a"], None)
        double = J.make_backend("test_double", "mock")
        for judgement, codes in (("DM-1", DM12_CODES), ("DM-2", DM12_CODES), ("DM-4", DM4_LABELS)):
            first = double.judge(judgement, "the same prompt", codes, None)
            self.assertEqual(first, double.judge(judgement, "the same prompt", codes, None))
            self.assertIn(first["status"], ("OK", "ABSTAIN"))
        self.assertEqual(double.kind, "test_double")

    def test_the_test_doubles_answers_always_fit_the_shape_the_object_accepts(self):
        double = J.make_backend("test_double", "mock")
        seen = set()
        for n in range(40):
            for judgement, codes in (("DM-1", DM12_CODES), ("DM-4", DM4_LABELS)):
                a = double.judge(judgement, f"prompt {n}", codes, None)
                seen.add((judgement, a["status"], a.get("answer"), a.get("cause_label")))
                if a["status"] == "OK" and judgement == "DM-4" and a["cause_label"] == "unknown":
                    self.assertEqual(a["answer"], "NO")
        self.assertTrue({s[1] for s in seen} >= {"OK"})


class T9BuildOrNot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def test_a_plan_with_no_judgements_block_builds_nothing_and_says_nothing(self):
        plan = jplan()
        del plan["judgements"]
        built, event = J.build(plan, SpyJudge(), self.folder, lambda: 0.0)
        self.assertEqual((built, event), (None, None))

    def test_the_started_event_names_the_backend_the_points_and_the_prompt_versions(self):
        built, event = J.build(jplan(), SpyJudge(), self.folder, lambda: 0.0)
        self.assertIsNotNone(built)
        self.assertEqual((event["event"], event["from"]), ("judgements_started", "judgements"))
        body = event["judgements"]
        self.assertEqual(body["backend"], {"name": "spy-judge", "version": "7", "kind": "test_double"})
        self.assertEqual(body["dm1"]["points"], ["after_measure:drift"])
        self.assertEqual(body["dm4"]["points"], ["stop"])
        self.assertIn("plan-test-081", body["dm1"]["prompt_version"])

    def test_a_point_the_run_never_reaches_is_off_naming_the_point(self):
        for key, point in (("dm1", "before_measure:nothing"), ("dm2", "after_measure:"), ("dm1", "after_detection"),
                           ("dm2", "before_measurement"), ("dm1", "stop")):
            with self.subTest(key=key, point=point):
                plan = jplan()
                plan["judgements"][key]["points"] = ["run_start", point]
                built, event = J.build(plan, SpyJudge(), self.folder, lambda: 0.0)
                self.assertIsNone(built)
                self.assertEqual((event["event"], event["judgements"]["why"]), ("judgements_off", "did_not_start"))
                self.assertIn(repr(point), event["judgements"]["detail"])

    def test_every_point_the_run_does_reach_is_accepted_for_dm1_and_dm2(self):
        plan = jplan(dm1=("run_start", "before_measure:drift", "after_measure:c3"),
                     dm2=("after_measure:drift", "before_measure:c3"), extra_ids=("c3",))
        built, event = J.build(plan, SpyJudge(), self.folder, lambda: 0.0)
        self.assertIsNotNone(built, event)

    def test_a_malformed_block_is_off_with_the_reason_and_the_run_goes_on(self):
        plan = jplan()
        plan["judgements"]["dm1"]["points"] = []
        built, event = J.build(plan, SpyJudge(), self.folder, lambda: 0.0)
        self.assertIsNone(built)
        self.assertEqual(event["event"], "judgements_off")
        self.assertIn("points", event["judgements"]["detail"])

    def test_none_is_built_and_started_but_asks_nobody(self):
        built, event = J.build(jplan(), J.make_backend("none", "mock"), self.folder, lambda: 0.0)
        self.assertEqual(event["judgements"]["backend"]["kind"], "none")
        built.start()
        built.reach("after_measure:drift")
        built.close(0.1)
        self.assertEqual(built.drain(), [])
        self.assertEqual(built.reached["after_measure:drift"], 1)


# ---------------------------------------------------------------------------------------------------------- #
# In a run
# ---------------------------------------------------------------------------------------------------------- #

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
        self.o, self.calls, self.asked_person = None, [], []
        real_init, real_device = orch.Orchestrator.__init__, orch.Orchestrator._device_module

        def init(s, *a, **k):
            real_init(s, *a, **k)
            self.o = s
        orch.Orchestrator.__init__ = init
        orch.Orchestrator._device_module = lambda s, name, needed_by: Spy(name, real_device(s, name, needed_by),
                                                                          self.calls)
        self.addCleanup(lambda: [setattr(orch.Orchestrator, "__init__", real_init),
                                 setattr(orch.Orchestrator, "_device_module", real_device)])

    def run_it(self, plan, backend=None, how="normal", times=(), stop_t=None, run_id="run-test-081",
               judgement_backend="default", run_backend="mock", during=None, **kw):
        self.plan_path.write_text(json.dumps(plan))
        self.backend = SpyJudge() if judgement_backend == "default" else judgement_backend
        now = [0.0]
        self.images = []

        def observe(metric):
            o = self.o
            o.clock.offset = lambda: now[0]
            camera = o.module_for(CAMERA)
            getattr(camera, "_m", camera).FRAME_SHAPE = (48, 48)
            for t in times:
                now[0] = float(t)
                o.acquire_snap(CAMERA)
            if during is not None:
                during(o)
            now[0] = float(stop_t if stop_t is not None else (times[-1] if times else 0.0))
            if how == "outside":
                send_stop(self.lines(run_id)[0]["stop_channel"], run_id)
                return OK_VALUE
            return {"monitor": BREAKS, "blind": None, "normal": OK_VALUE}[how]
        return op.run(self.plan_path, run_id, backend=run_backend, observe=observe, runs_root=self.root,
                      judgement_backend=self.backend, ask_person=lambda *a, **k: self.asked_person.append(a), **kw)

    def lines(self, run_id="run-test-081"):
        text = (self.root / run_id / "events.jsonl").read_text(encoding="utf-8")
        return [json.loads(l) for l in text.splitlines() if l]

    def names(self, run_id="run-test-081"):
        return [e["event"] for e in self.lines(run_id)]

    def of(self, name, judgement=None, run_id="run-test-081"):
        return [e for e in self.lines(run_id) if e["event"] == name
                and (judgement is None or e["judgement"]["judgement"] == judgement)]


class T2InARun(_Run):
    def test_dm1_and_dm2_are_asked_at_each_point_the_run_reaches_and_in_this_order(self):
        self.run_it(jplan(dm4=None), how="normal", times=[0, 1])
        asked = [(e["judgement"]["judgement"], e["judgement"]["point"]) for e in self.of("judgement_asked")]
        self.assertEqual(asked, [("DM-2", "run_start"), ("DM-2", "before_measure:drift"),
                                 ("DM-1", "after_measure:drift")])
        names = self.names()
        self.assertLess(names.index("run_started"), names.index("judgements_started"))
        self.assertLess(names.index("judgements_started"), names.index("judgement_asked"))

    def test_each_request_comes_before_the_event_it_precedes_in_the_run(self):
        self.run_it(jplan(dm4=None), how="normal", times=[0, 1])
        lines = self.lines()
        points = [(i, e["judgement"]["point"]) for i, e in enumerate(lines) if e["event"] == "judgement_asked"]
        self.assertEqual([p for _, p in points], ["run_start", "before_measure:drift", "after_measure:drift"])
        self.assertEqual(lines[-1]["event"], "run_ended")
        self.assertEqual(lines[-1]["how"], "completed")

    def test_a_point_the_run_stopped_before_reaching_is_written_in_run_ended(self):
        plan = jplan(dm1=("after_measure:drift", "after_measure:later"), dm4=None, extra_ids=("later",))
        self.run_it(plan, how="monitor", times=[0], stop_t=0.5)
        ended = self.lines()[-1]
        self.assertEqual(ended["judgements"]["unreached"], {"dm1": ["after_measure:later"]})
        self.assertEqual(ended["judgements"]["reached"]["after_measure:drift"], 1)

    def test_a_plan_naming_a_point_the_run_never_reaches_runs_with_the_judgements_off(self):
        plan = jplan(dm1=("after_detection",), dm4=None)
        self.run_it(plan, how="normal", times=[0])
        off = [e for e in self.lines() if e["event"] == "judgements_off"]
        self.assertEqual(len(off), 1)
        self.assertIn("after_detection", off[0]["judgements"]["detail"])
        self.assertNotIn("judgement_asked", self.names())
        self.assertEqual(self.lines()[-1]["how"], "completed")

    def test_a_run_that_never_stopped_does_not_list_the_stop_point_as_missed(self):
        self.run_it(jplan(), how="normal", times=[0, 1])
        self.assertEqual(self.lines()[-1]["judgements"]["unreached"], {})

    def test_a_plan_with_no_judgements_block_is_unchanged(self):
        plan = jplan(dm4=None)
        del plan["judgements"]
        self.run_it(plan, how="normal", times=[0])
        self.assertFalse([n for n in self.names() if n.startswith("judgement")])
        self.assertNotIn("judgements", self.lines()[-1])

    def test_none_records_the_start_and_the_points_and_asks_nobody(self):
        self.run_it(jplan(), judgement_backend=None, how="monitor", times=[0, 1], stop_t=1.5)
        names = self.names()
        self.assertIn("judgements_started", names)
        self.assertNotIn("judgement_asked", names)
        self.assertEqual(self.lines()[names.index("judgements_started")]["judgements"]["backend"]["kind"], "none")
        self.assertEqual(self.lines()[-1]["judgements"]["reached"]["before_measure:drift"], 1)


class T3NoPathToAnythingElse(_Run):
    def device_calls(self):
        return [(name, attr) for name, attr, _, _ in self.calls]

    def test_with_every_answer_a_yes_the_run_does_what_it_does_without_judgements(self):
        for how in ("normal", "monitor"):
            with self.subTest(how=how):
                self.calls.clear()
                self.run_it(jplan(), how=how, times=[0, 1], stop_t=1.5, run_id=f"run-with-{how}")
                with_it = self.device_calls()
                with_names = [n for n in self.names(f"run-with-{how}") if not n.startswith(("judgement", "pre_stop"))]
                self.calls.clear()
                plain = jplan(dm1=None, dm2=None, dm4=None)
                del plain["judgements"]
                self.run_it(plain, how=how, times=[0, 1], stop_t=1.5, run_id=f"run-without-{how}")
                self.assertEqual(with_it, self.device_calls())
                without_names = [n for n in self.names(f"run-without-{how}") if not n.startswith(("judgement", "pre_stop"))]
                self.assertEqual(with_names, without_names)

    def test_no_answer_moves_the_stop_channel_or_asks_the_person(self):
        answers = {"DM-1": {"status": "OK", "answer": "YES", "reason_codes": ["too_dense"]},
                   "DM-2": {"status": "OK", "answer": "NO", "reason_codes": []},
                   "DM-4": {"status": "OK", "answer": "YES", "cause_label": "particle_lost"}}
        self.run_it(jplan(), judgement_backend=SpyJudge(answers), how="normal", times=[0, 1])
        names = self.names()
        for forbidden in ("stop_requested", "abort_begin", "stop_refused", "stop_criterion_violated"):
            self.assertNotIn(forbidden, names)
        self.assertEqual(self.asked_person, [])
        self.assertEqual(self.lines()[-1]["how"], "completed")

    def test_a_judgement_that_breaks_inside_the_run_is_said_in_run_ended_and_never_stops_it(self):
        def boom(point, t_mono=None):
            raise RuntimeError("judgement broke")
        self.run_it(jplan(dm4=None), how="normal", times=[0, 1],
                    during=lambda o: setattr(o._judgements, "reach", boom))
        ended = self.lines()[-1]
        self.assertEqual(ended["how"], "completed")
        self.assertIn("judgement broke", ended["judgements_failure"])

    def test_a_backend_that_fails_every_question_never_changes_how_the_run_ends(self):
        self.run_it(jplan(), judgement_backend=SpyJudge(fail=RuntimeError("down")), how="monitor", times=[0, 1],
                    stop_t=1.5)
        self.assertEqual(self.lines()[-1]["how"], "aborted_by_monitor")
        self.assertTrue(all(e["judgement"]["status"] == "ERROR" for e in self.of("judgement_answered")))


class T4Dm4AfterTheAbort(_Run):
    def test_dm4_is_asked_after_the_abort_and_the_save_for_every_kind_of_stop(self):
        for how in ("monitor", "outside", "blind"):
            with self.subTest(how=how):
                run_id = f"run-dm4-{how}"
                self.run_it(jplan(dm1=None, dm2=None), how=how, times=[0, 1, 2], stop_t=2.5, run_id=run_id)
                names = self.names(run_id)
                asked = names.index("judgement_asked")
                for before in ("abort_begin", "abort_light_sources", "abort_end", "pre_stop_buffer_saved"):
                    self.assertLess(names.index(before), asked, f"{before} did not come first: {names}")
                self.assertLess(asked, names.index("run_ended"))
                self.assertEqual(self.of("judgement_asked", run_id=run_id)[0]["from"], "judgements.dm4")

    def test_a_second_abort_in_one_run_asks_dm4_once(self):
        self.run_it(jplan(dm1=None, dm2=None), how="monitor", times=[0, 1], stop_t=1.5,
                    during=lambda o: o.abort(reason="a first abort, before the monitor's own"))
        self.assertEqual(len(self.of("judgement_asked", "DM-4")), 1)
        self.assertEqual(self.names().count("abort_begin"), 2)

    def test_dm4_is_not_asked_when_the_run_ends_normally(self):
        self.run_it(jplan(dm1=None, dm2=None), how="normal", times=[0, 1])
        self.assertNotIn("judgement_asked", self.names())

    def test_dm4_images_are_the_saved_buffers_frames_reduced_and_nothing_else(self):
        self.run_it(jplan(dm1=None, dm2=None, given=True, watcher=True, length=2.0), how="monitor",
                    times=[0, 1, 2, 3], stop_t=3.5)
        saved = self.of("pre_stop_buffer_saved")[0]["buffer"]
        header, _, body = (self.root / "run-test-081" / saved["path"]).read_bytes().partition(b"\n")
        header = json.loads(header)
        refs = self.of("judgement_asked", "DM-4")[0]["judgement"]["images"]
        self.assertEqual([r["frame_index"] for r in refs], [f["index"] for f in header["frames"]])
        self.assertEqual(len(refs), saved["frames"])
        pos = 0
        for ref, entry in zip(refs, header["frames"]):
            raw = np.frombuffer(body[pos:pos + entry["bytes"]], dtype=entry["dtype"]).reshape(entry["shape"])
            pos += entry["bytes"]
            data, _ = R.convert_frame(raw, TW.CONVERSION, 65535)
            self.assertEqual(ref["sha256"], "sha256:" + hashlib.sha256(data).hexdigest())
            self.assertNotEqual((self.root / "run-test-081" / ref["path"]).read_bytes(), raw.tobytes())
        for image in self.backend.calls[0]["images"]:
            self.assertTrue(image["png"].startswith(b"\x89PNG"))

    def test_dm4_with_a_zero_length_buffer_is_asked_on_what_there_is_and_says_nothing_was_saved(self):
        self.run_it(jplan(dm1=None, dm2=None, length=0), how="monitor", times=[0, 1], stop_t=1.5)
        request = self.of("judgement_asked", "DM-4")[0]["judgement"]
        self.assertEqual(request["images"], [])
        text = (self.root / "run-test-081" / request["context_path"]).read_text(encoding="utf-8")
        self.assertIn("stop reason:", text)
        self.assertIn("nothing was saved", text)

    def test_the_abort_is_whole_before_the_question_so_it_is_never_delayed_by_one(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        saved_wait = J.CLOSE_WAIT_S
        J.CLOSE_WAIT_S = 0.2                    # the run's own wait for open questions, shortened for the test
        self.addCleanup(setattr, J, "CLOSE_WAIT_S", saved_wait)
        t0 = time.monotonic()
        self.run_it(jplan(dm1=None, dm2=None), judgement_backend=SpyJudge(gate=gate), how="monitor", times=[0, 1],
                    stop_t=1.5)
        # The question is never answered (the gate stays shut), so the run ending at all is the proof it did
        # not wait on one; the bound only catches a hang, and a loaded machine is nowhere near it.
        self.assertLess(time.monotonic() - t0, HANG_S, "the run hung on a question")
        names = self.names()
        self.assertLess(names.index("abort_end"), names.index("judgement_asked"))
        answered = self.of("judgement_answered", "DM-4")[0]["judgement"]
        self.assertEqual(answered["status"], "ERROR")


class T5RunLog(_Run):
    def test_every_judgement_event_of_a_run_validates_and_the_context_files_match_their_hashes(self):
        import jsonschema
        from referencing import Registry, Resource
        judgement_schema = json.loads((CONTRACTS / "schemas" / "judgement.schema.json").read_text(encoding="utf-8"))
        run_log = json.loads((CONTRACTS / "schemas" / "run_log.schema.json").read_text(encoding="utf-8"))
        registry = Registry().with_resource("judgement.schema.json", Resource.from_contents(judgement_schema))
        validator = jsonschema.Draft202012Validator({"$ref": "#/$defs/event", "$defs": run_log["$defs"]},
                                                    registry=registry)
        self.run_it(jplan(given=True, watcher=True), how="monitor", times=[0, 1, 2], stop_t=2.5)
        events = [e for e in self.lines() if e["event"].startswith("judgement_")]
        self.assertGreaterEqual(len(events), 8)
        for event in events:
            validator.validate(event)
        for e in self.of("judgement_asked"):
            raw = (self.root / "run-test-081" / e["judgement"]["context_path"]).read_bytes()
            self.assertEqual(e["judgement"]["context_sha256"], "sha256:" + hashlib.sha256(raw).hexdigest())
            for ref in e["judgement"]["images"]:
                data = (self.root / "run-test-081" / ref["path"]).read_bytes()
                self.assertEqual(ref["sha256"], "sha256:" + hashlib.sha256(data).hexdigest())

    def test_the_runs_frames_reach_the_judgements_so_dm1_and_dm2_get_a_current_image(self):
        self.run_it(jplan(dm4=None, given=True, watcher=True), how="normal", times=[0, 1])
        after = [e for e in self.of("judgement_asked", "DM-1")][0]["judgement"]
        self.assertEqual([i["role"] for i in after["images"]], ["current"])
        self.assertEqual(after["images"][0]["frame_index"], 1)         # the latest frame the run made
        before = [e for e in self.of("judgement_asked", "DM-2") if e["judgement"]["point"] == "before_measure:drift"]
        self.assertEqual(before[0]["judgement"]["images"], [])         # nothing had arrived yet, and it says so

    def test_seqs_are_distinct_across_all_judgements_of_a_run(self):
        self.run_it(jplan(), how="monitor", times=[0, 1], stop_t=1.5)
        seqs = [e["judgement"]["seq"] for e in self.of("judgement_asked")]
        self.assertEqual(len(seqs), len(set(seqs)))
        self.assertGreaterEqual(len(seqs), 4)


class T6RefusedOffMock(_Run):
    def test_the_test_double_is_refused_on_any_backend_but_mock_before_anything_starts(self):
        self.plan_path.write_text(json.dumps(jplan()))
        with self.assertRaisesRegex(op.Refusal, "mock"):
            op.run(self.plan_path, "run-test-081", backend="hardware", runs_root=self.root,
                   judgement_backend="test_double")
        self.assertFalse((self.root / "run-test-081").exists())
        self.assertFalse((Path(self.tmp.name) / "run.lock").exists())

    def test_a_test_double_object_is_refused_off_mock_too(self):
        self.plan_path.write_text(json.dumps(jplan()))
        with self.assertRaisesRegex(op.Refusal, "mock"):
            op.run(self.plan_path, "run-test-081", backend="hardware", runs_root=self.root,
                   judgement_backend=SpyJudge())
        self.assertFalse((self.root / "run-test-081").exists())

    def test_an_unknown_judgement_backend_is_refused(self):
        self.plan_path.write_text(json.dumps(jplan()))
        with self.assertRaisesRegex(op.Refusal, "unknown"):
            op.run(self.plan_path, "run-test-081", backend="mock", runs_root=self.root, judgement_backend="gpt")

    def test_main_passes_the_option_through(self):
        got = {}
        real = op.run
        op.run = lambda plan, **kw: (got.update(kw), (_ for _ in ()).throw(op.Refusal("stop here")))[1]
        self.addCleanup(setattr, op, "run", real)
        self.plan_path.write_text(json.dumps(jplan()))
        op.main(["--plan", str(self.plan_path), "--run-id", "run-test-081", "--judgement-backend", "test_double"])
        self.assertEqual(got["judgement_backend"], "test_double")

    def test_the_real_test_double_runs_on_mock_and_answers_all_four(self):
        self.run_it(jplan(), judgement_backend="test_double", how="monitor", times=[0, 1], stop_t=1.5)
        judged = {e["judgement"]["judgement"] for e in self.of("judgement_answered")}
        self.assertEqual(judged, {"DM-1", "DM-2", "DM-4"})
        self.assertTrue(all(e["judgement"]["model"]["kind"] == "test_double" for e in self.of("judgement_answered")))


class T1Dm3OnTheWatcher(_Run):
    def test_every_watcher_flag_of_a_run_carries_the_dm3_reading_of_its_choice(self):
        plan = jplan(dm1=None, dm2=None, dm4=None, watcher=True)
        plan["watcher"]["cadence_s"] = 0.05
        self.plan_path.write_text(json.dumps(plan))

        def observe(metric):
            camera = self.o.module_for(CAMERA)
            getattr(camera, "_m", camera).FRAME_SHAPE = (48, 48)
            for _ in range(4):
                self.o.acquire_snap(CAMERA)
                time.sleep(0.12)
            return OK_VALUE
        op.run(self.plan_path, "run-test-081", backend="mock", observe=observe, runs_root=self.root,
               watcher_backend="test_double", judgement_backend=None)
        flags = [e for e in self.lines() if e["event"] == "watcher_flag"]
        self.assertTrue(flags, "the run produced no flag to read")
        for flag in flags:
            body = flag["watcher"]
            self.assertEqual(body["judgement"], W.dm3_reading(body["signals"]["choice"]))
            self.assertEqual(body["prompt_version"], W.PROMPT_VERSION)


if __name__ == "__main__":
    unittest.main()
