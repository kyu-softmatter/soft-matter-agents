"""Card 090: the console's "run" button starts one signed plan, and nothing else.

    python -m unittest tests.test_run_request        (from microscope_runtime/)

The live-view host answers a third message, exactly {"run": "<sha256>"}: the hash of a plan_approval
file's bytes in the approvals folder. It finds the plan that approval names, judges it with the
approval reader (and the console gate) before an id or the run lock is taken, and starts it through
operator.run. On the mock backend the run starts at once. On any other backend the host replies
"waiting_for_bench" and the run waits for the hand-over typed on the host's OWN terminal.

Mock only. Every approval, login, plan, list and run folder here is a TEST value in a temporary
directory, and the instrument path is exercised with operator.run replaced by a recorder: nothing
here opens a device. The console's real inbox is never written.
"""

from __future__ import annotations

import io
import json
import queue
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_idle_status_and_check_now as t85                    # noqa: E402  (its _Base builds the host)

lv, op, lock_mod = t85.lv, t85.op, t85.lock_mod
jsonschema = t85.jsonschema

LOGIN = "person-test"
PLAN = {"card": "plan", "id": "plan-test-090-run", "revision": 1, "actions": [],
        "numbers": [{"name": "n", "value": 1, "unit": "1", "source": "test", "grade": "E5"}],
        "stop_criteria": [{"id": "n", "number": "n", "metric": "n", "comparator": ">="}]}
HANDOVER_WORDS = "the bench is mine, the stage is clear"


def _validates(reply, name="run_reply"):
    if jsonschema is None:
        raise unittest.SkipTest("jsonschema is not installed")
    jsonschema.validate(reply, {"$ref": f"#/$defs/{name}", "$defs": t85.INTERFACE["$defs"]})


class _RunBase(t85._Base):
    def setUp(self):
        super().setUp()
        # What card 085's base stubs for a host that never runs a plan, put back for one that does.
        op.approvals_on_disk = self._saved[2]
        op.load_safety = lambda agent=None: {"policy_version": "test", "targets": []}
        root = Path(self.tmp.name)
        self.questions = root / "questions"
        self.login_path = root / "envelope" / "console_login.json"
        self.login_path.parent.mkdir()
        self.host.questions_dir = self.questions
        self.prompts, self.answer, self.answer_ready = [], None, threading.Event()
        self.asked = threading.Event()
        self.host.ask_bench = self._ask_bench
        self.host.bench_lapse_s = 20.0
        self.addCleanup(self._let_the_ask_go)
        self.run_calls = []

    # -- the stand-in for the host's terminal ----------------------------------------------
    def _ask_bench(self, prompt, lapse_s, cancel):
        self.prompts.append((prompt, lapse_s))
        self.asked.set()
        self.answer_ready.wait(20)
        return self.answer

    def _let_the_ask_go(self):
        self.answer, _ = None, self.answer_ready.set()

    def type_at_terminal(self, words):
        self.answer = words
        self.answer_ready.set()

    # -- files the person (or the console) put in place ------------------------------------
    def put_login(self, login=LOGIN):
        doc = {"artifact": "console_login", "schema_version": "0.1", "login": login,
               "written_by": "the person, by hand (test)", "written_at": "2026-10-26"}
        self.login_path.write_text(json.dumps(doc), encoding="utf-8")

    def put_plan(self, plan=PLAN, qid="q-a", name="plan_a.json"):
        folder = self.questions / qid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(json.dumps(plan), encoding="utf-8")
        return folder / name

    def put_approval(self, plan=PLAN, name="appr-run-090.json", signed=True, **over) -> str:
        doc = {"card": "plan_approval", "id": name[:-5], "plan_id": plan["id"],
               "plan_revision": plan["revision"], "plan_hash": t85.validate.plan_hash(plan),
               "approved_by": "Test Person", "approved_at": "2026-10-26T10:00:00Z"}
        if signed:
            doc["signed_through"] = {"via": "console", "login": LOGIN}
        doc.update(over)
        data = json.dumps(doc, indent=2).encode()
        (self.approvals / name).write_bytes(data)
        return t85._sha(data)

    def ready(self, **kw) -> str:
        """The usual case: the person's login, the plan, and an approval the console signed."""
        self.put_login()
        self.put_plan()
        return self.put_approval(**kw)

    # -- asking ----------------------------------------------------------------------------
    def run_req(self, sha):
        return self.ask({"run": sha})

    def ask(self, message):
        if self.host.address() is None:
            self.host.start()
        return t85._ask(self.host.address(), json.dumps(message).encode() + b"\n")

    def wait_for(self, what, test, timeout=15):
        t0 = time.monotonic()
        while not test() and time.monotonic() - t0 < timeout:
            time.sleep(0.05)
        self.assertTrue(test(), f"timed out waiting for {what}")

    def events(self, run_id):
        path = self.runs / run_id / "events.jsonl"
        if not path.exists():
            return []
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def wait_ended(self, run_id):
        self.wait_for(f"{run_id} to end", lambda: any(e.get("event") == "run_ended" for e in self.events(run_id)))
        return self.events(run_id)

    def assert_lock_free(self):
        lock = lock_mod.RunLock(self.lock_path)
        lock.acquire({"kind": "test", "run_id": "probe"})           # raises RunLockHeld if it was kept
        lock.release()

    def assert_refused(self, reply, *words):
        self.assertEqual(reply["run"], "refused", reply)
        self.assertEqual(set(reply), {"run", "reason"})
        _validates(reply)
        for w in words:
            self.assertIn(w, reply["reason"])
        self.assertTrue(any(r.get("event") == "run_refused" and r.get("reason") == reply["reason"]
                            for r in self.host_records()), "the refusal is in the host's log")

    def assert_nothing_started(self):
        self.assertEqual(self.orchestrators, [], "no orchestrator was built")
        self.assertEqual(self.opened, [], "no device was opened")
        self.assertEqual(self.run_calls, [], "operator.run was not called")
        self.assertFalse(self.runs.exists() and list(self.runs.iterdir()), "no run folder exists")
        self.assertEqual(self.prompts, [], "nobody was asked for the bench")
        self.assert_lock_free()

    # -- the instrument path, with operator.run replaced by a recorder ---------------------
    def as_instrument(self):
        saved_run, saved_agent = op.run, op.AGENT

        def fake_run(plan_path, run_id, **kw):
            self.run_calls.append((Path(plan_path), run_id, kw))
            kw["started"].set()
            return {"ended": "completed"}
        op.run, op.AGENT = fake_run, Path(self.tmp.name)            # AGENT / "approvals" is self.approvals
        self.addCleanup(setattr, op, "run", saved_run)
        self.addCleanup(setattr, op, "AGENT", saved_agent)
        self.host.backend = "hardware"


# --------------------------------------------------------------------------- #
# 1. on the mock the run starts at once, as a run started by command
# --------------------------------------------------------------------------- #

class T1TheMockStartsTheApprovedPlan(_RunBase):
    def test_a_signed_approval_starts_its_plan_and_the_reply_says_which_run(self):
        sha = self.ready()
        reply = self.run_req(sha)
        self.assertEqual(set(reply), {"run", "run_id"}, reply)
        self.assertEqual(reply["run"], "started")
        self.assertRegex(reply["run_id"], t85.RUN_ID)
        self.assertGreaterEqual(int(reply["run_id"][-3:]), 900, "a host-started id is in 900-999")
        _validates(reply)
        events = self.wait_ended(reply["run_id"])
        names = [e["event"] for e in events]
        self.assertIn("run_started", names)
        self.assertLess(names.index("run_started"), names.index("run_ended"))
        handover = next(e for e in events if e["event"] == "handover")
        self.assertIsNone(handover["bench"])
        self.assertIn("mock", handover["no_bench_because"])
        self.assertEqual(len(self.orchestrators), 1)
        records = {r["event"]: r for r in self.host_records() if r.get("run_id") == reply["run_id"]}
        self.assertEqual(records["run_started"]["sha256"], sha)
        self.assertEqual(records["run_started"]["plan_id"], PLAN["id"])
        self.assertIn("run_ended", records)
        self.wait_for("the lock to be freed", lambda: not self.lock_path.exists() or self._lock_free())

    def _lock_free(self):
        try:
            self.assert_lock_free()
            return True
        except lock_mod.RunLockHeld:
            return False

    def test_the_hosts_log_names_the_approval_file_that_covered_the_run(self):
        sha = self.ready(name="appr-covering.json")
        reply = self.run_req(sha)
        self.wait_ended(reply["run_id"])
        for event in ("run_requested", "run_started", "run_ended"):
            record = next(r for r in self.host_records() if r.get("event") == event)
            self.assertEqual(record["sha256"], sha, event)
        started = next(r for r in self.host_records() if r.get("event") == "run_started")
        self.assertEqual(started["approval"], "appr-covering.json")

    def test_two_requests_in_a_row_get_two_runs_when_the_first_has_ended(self):
        sha = self.ready()
        first = self.run_req(sha)
        self.wait_ended(first["run_id"])
        self.wait_for("the lock to be freed", self._lock_free)
        second = self.run_req(sha)
        self.assertEqual(second["run"], "started", second)
        self.assertNotEqual(second["run_id"], first["run_id"])

    def test_a_copy_of_the_plan_beside_it_is_told_apart_by_the_approvals_hash(self):
        sha = self.ready()
        edited = json.loads(json.dumps(PLAN))
        edited["numbers"][0]["value"] = 2                           # same id and revision, other bytes
        self.put_plan(edited, qid="q-b", name="plan_b.json")
        reply = self.run_req(sha)
        self.assertEqual(reply["run"], "started", reply)
        self.wait_ended(reply["run_id"])
        records = [r for r in self.host_records() if r.get("event") == "run_started"]
        self.assertTrue(records[0]["plan_path"].endswith("q-a/plan_a.json"), records)

    def test_two_identical_copies_are_not_guessed_between(self):
        sha = self.ready()
        self.put_plan(PLAN, qid="q-b", name="plan_b.json")
        reply = self.run_req(sha)
        self.assert_refused(reply, "2 plan files")
        self.assert_nothing_started()


# --------------------------------------------------------------------------- #
# 2. every way of not covering a plan is a refusal with the reason, and nothing opens
# --------------------------------------------------------------------------- #

class T2ARequestThatCoversNothingStartsNothing(_RunBase):
    def check(self, sha, *words):
        reply = self.run_req(sha)
        self.assert_refused(reply, *words)
        self.assert_nothing_started()
        return reply

    def test_a_hash_that_names_no_approval(self):
        self.ready()
        self.check("0" * 64, "no approval")

    def test_an_approval_for_a_revision_no_plan_file_holds(self):
        self.put_login()
        self.put_plan()
        r2 = dict(PLAN, revision=2)
        sha = self.put_approval(r2)
        self.check(sha, "no plan", "revision 2")

    def test_an_approval_whose_plan_is_missing(self):
        self.put_login()
        sha = self.put_approval()
        self.check(sha, "no plan")

    def test_a_plan_edited_after_it_was_approved(self):
        self.put_login()
        sha = self.put_approval()                                   # the hash of PLAN as it was
        edited = json.loads(json.dumps(PLAN))
        edited["numbers"][0]["value"] = 99
        self.put_plan(edited)
        self.check(sha, "plan_hash does not match")

    def test_a_console_signature_with_another_login(self):
        self.put_login("someone-else")
        self.put_plan()
        sha = self.put_approval()
        self.check(sha, "covers nothing")

    def test_a_console_signature_with_no_login_file(self):
        self.put_plan()
        sha = self.put_approval()
        self.check(sha, "absent")

    def test_a_file_that_is_not_a_plan_approval(self):
        self.ready()
        data = json.dumps({"card": "scope_approval", "id": "scope-x"}).encode()
        (self.approvals / "scope-x.json").write_bytes(data)
        self.check(t85._sha(data), "not a plan_approval")

    def test_a_file_that_is_not_json(self):
        self.ready()
        (self.approvals / "junk.json").write_bytes(b"{ not json")
        self.check(t85._sha(b"{ not json"), "not a plan_approval")

    def test_an_approval_that_cannot_name_a_revision(self):
        self.put_login()
        self.put_plan()
        doc = {"card": "plan_approval", "id": "appr-x", "plan_id": PLAN["id"],
               "plan_hash": t85.validate.plan_hash(PLAN), "approved_by": "Test", "approved_at": "2026-10-26"}
        data = json.dumps(doc).encode()
        (self.approvals / "appr-x.json").write_bytes(data)
        self.check(t85._sha(data), "no plan")

    def test_a_second_approval_for_the_same_revision_that_is_not_the_one_named(self):
        sha_b = self.ready(name="appr-b.json")
        self.put_approval(name="appr-a.json")                       # sorts first, covers the same plan
        self.check(sha_b, "another approval file")

    def test_another_logins_question_without_its_item_in_the_inbox(self):
        self.put_login()
        plan = dict(PLAN, qid="microscope-20261027-c999")
        self.put_plan(plan)
        sha = self.put_approval(plan)
        reply = self.check(sha)
        self.assertIn("console", reply["reason"].lower())

    def test_a_run_holds_the_lock_and_the_retry_after_it_ends_starts(self):
        sha = self.ready()
        held = lock_mod.RunLock(self.lock_path)
        held.acquire({"kind": "plan", "plan_id": "plan-other", "run_id": "run-20261027-001"})
        try:
            reply = self.run_req(sha)
            self.assert_refused(reply, "holds the lock", "run-20261027-001")
            self.assertEqual(self.orchestrators, [])
            self.assertFalse(self.runs.exists() and list(self.runs.iterdir()))
        finally:
            held.release()
        again = self.run_req(sha)
        self.assertEqual(again["run"], "started", again)
        self.wait_ended(again["run_id"])

    def test_a_plan_that_fails_its_own_checks_is_refused_without_a_run_folder(self):
        broken = dict(PLAN)
        broken["stop_criteria"] = []                                # a run that cannot stop is not started
        self.put_login()
        self.put_plan(broken)
        sha = self.put_approval(broken)
        reply = self.run_req(sha)
        if reply["run"] == "started":                               # operator.run's own refusal is the judge
            self.fail(f"a plan operator.run refuses was reported started: {reply}")
        self.assert_refused(reply)
        self.assertEqual(self.opened, [])
        self.wait_for("the lock to be freed", lambda: self._lock_ok())

    def _lock_ok(self):
        try:
            self.assert_lock_free()
            return True
        except lock_mod.RunLockHeld:
            return False


# --------------------------------------------------------------------------- #
# 3. the request is one key and one hash
# --------------------------------------------------------------------------- #

class T3TheRequestCarriesOneKeyAndOneHash(_RunBase):
    def test_nothing_rides_with_the_hash(self):
        sha = self.ready()
        for extra in ({"backend": "hardware"}, {"bench": "handed over"}, {"plan": {}},
                      {"plan": "q-a/plan_a.json"}, {"mm_config": "x.cfg"}, {"live_on": sha}, {"check_now": sha}):
            with self.subTest(extra=sorted(extra)):
                reply = self.ask({"run": sha, **extra})
                self.assertEqual(reply.get("run", reply.get("check_now")), "refused", reply)
                self.assertEqual(self.orchestrators, [])
                self.assertEqual(self.opened, [])
                self.assertFalse(self.runs.exists() and list(self.runs.iterdir()))
                self.assertEqual(self.prompts, [])

    def test_a_run_request_with_a_foreign_key_is_refused_under_run(self):
        sha = self.ready()
        reply = self.ask({"run": sha, "bench": "handed over"})
        self.assert_refused(reply, "no other key", "bench")

    def test_only_a_lowercase_hash_is_accepted(self):
        sha = self.ready()
        for name, value in (("a path", "approvals/appr-run-090.json"), ("a bare name", "appr-run-090.json"),
                            ("uppercase hex", sha.upper()), ("too short", sha[:-1]), ("too long", sha + "0"),
                            ("empty", ""), ("a number", 12), ("a list", [sha]), ("null", None),
                            ("a dict", {"sha": sha}), ("padded", f" {sha}")):
            with self.subTest(value=name):
                reply = self.ask({"run": value})
                self.assert_refused(reply, "64 lowercase hex digits")
                self.assertEqual(self.orchestrators, [])
                self.assertFalse(self.runs.exists() and list(self.runs.iterdir()))
        self.assert_lock_free()

    def test_a_request_that_is_not_a_run_is_not_answered_as_one(self):
        self.ready()
        reply = self.ask({"go": "0" * 64})
        self.assertEqual(reply["live_on"], "refused")
        self.assertIn('{"run": "<sha256>"}', reply["reason"])


# --------------------------------------------------------------------------- #
# 4. on the instrument the run waits for the hand-over typed at the host's own terminal
# --------------------------------------------------------------------------- #

class T4TheInstrumentWaitsForTheBench(_RunBase):
    def setUp(self):
        super().setUp()
        self.as_instrument()

    def test_the_reply_comes_first_and_the_run_starts_only_after_the_words_are_typed(self):
        sha = self.ready()
        reply = self.run_req(sha)
        self.assertEqual(set(reply), {"run", "run_id"}, reply)
        self.assertEqual(reply["run"], "waiting_for_bench")
        _validates(reply)
        self.assertTrue(self.asked.wait(10), "the host asked for the hand-over")
        prompt, lapse = self.prompts[0]
        self.assertIn(PLAN["id"], prompt)
        self.assertIn(reply["run_id"], prompt)
        self.assertEqual(lapse, 20.0)
        time.sleep(0.3)
        self.assertEqual(self.run_calls, [], "nothing starts before the words are typed")
        with self.assertRaises(lock_mod.RunLockHeld):               # the wait holds the bench for this run
            self.assert_lock_free()
        other = self.run_req(sha)
        self.assert_refused(other, "holds the lock", reply["run_id"])
        self.type_at_terminal(HANDOVER_WORDS)
        self.wait_for("operator.run to be called", lambda: len(self.run_calls) == 1)
        plan_path, run_id, kw = self.run_calls[0]
        self.assertEqual(run_id, reply["run_id"])
        self.assertTrue(str(plan_path).endswith("plan_a.json"))
        self.assertEqual(kw["backend"], "hardware")
        self.assertEqual(kw["handover"]["bench"], HANDOVER_WORDS)
        self.assertIn("terminal", kw["handover"]["stated_by"])
        self.assertEqual(Path(kw["approvals_dir"]), self.approvals)
        self.assertEqual(Path(kw["runs_root"]), self.runs)
        self.assertIsNotNone(kw["lock"], "the lock taken before the wait is the one the run holds")
        self.wait_for("the host's log of the hand-over", lambda: any(
            r.get("event") == "run_bench_handed_over" for r in self.host_records()))
        handed = next(r for r in self.host_records() if r.get("event") == "run_bench_handed_over")
        self.assertEqual((handed["bench"], handed["run_id"]), (HANDOVER_WORDS, reply["run_id"]))
        self.wait_for("the lock to be freed", self._lock_ok)

    def _lock_ok(self):
        try:
            self.assert_lock_free()
            return True
        except lock_mod.RunLockHeld:
            return False

    def test_a_hand_over_in_the_request_is_refused_and_nobody_is_asked(self):
        sha = self.ready()
        reply = self.ask({"run": sha, "bench": HANDOVER_WORDS})
        self.assert_refused(reply, "no other key")
        self.assert_nothing_started()

    def test_a_blank_line_declines_and_nothing_starts(self):
        sha = self.ready()
        reply = self.run_req(sha)
        self.assertEqual(reply["run"], "waiting_for_bench")
        self.assertTrue(self.asked.wait(10))
        self.type_at_terminal("")
        self.wait_for("the lock to be freed", self._lock_ok)
        self.assertEqual(self.run_calls, [])
        end = next(r for r in self.host_records() if r.get("event") == "run_not_started")
        self.assertIn("declined", end["why"])

    def test_a_lapse_starts_nothing_and_frees_the_bench(self):
        sha = self.ready()
        reply = self.run_req(sha)
        self.assertEqual(reply["run"], "waiting_for_bench")
        self.assertTrue(self.asked.wait(10))
        self.type_at_terminal(None)                                 # the terminal's answer to a lapse
        self.wait_for("the lock to be freed", self._lock_ok)
        self.assertEqual(self.run_calls, [])
        end = next(r for r in self.host_records() if r.get("event") == "run_not_started")
        self.assertIn("lapsed", end["why"])

    def test_the_hosts_own_wait_is_the_lapse_it_passes_on(self):
        self.host.bench_lapse_s = 123.0
        sha = self.ready()
        self.run_req(sha)
        self.assertTrue(self.asked.wait(10))
        self.assertEqual(self.prompts[0][1], 123.0)
        self.assertEqual(lv.BENCH_LAPSE_S, 600.0, "ten minutes unless the host is told otherwise")

    def test_stopping_the_host_cancels_the_wait(self):
        sha = self.ready()
        seen = {}

        def ask(prompt, lapse_s, cancel):
            seen["cancel"] = cancel
            self.asked.set()
            cancel.wait(20)
            return None if cancel.is_set() else "should not start"
        self.host.ask_bench = ask
        self.run_req(sha)
        self.assertTrue(self.asked.wait(10))
        self.host.stop()
        self.assertTrue(seen["cancel"].is_set())
        self.assertEqual(self.run_calls, [])
        self._lock_ok() or self.fail("the lock is still held after the host stopped")

    def test_a_test_approvals_folder_never_reaches_the_instrument(self):
        sha = self.ready()
        op.AGENT = Path(self.tmp.name) / "elsewhere"                # the runtime's own folder is not this one
        reply = self.run_req(sha)
        self.assert_refused(reply, "mock backend only")
        self.assert_nothing_started()


# --------------------------------------------------------------------------- #
# the terminal reader, on its own
# --------------------------------------------------------------------------- #

class _Feed:
    """A terminal: readline blocks until a line is typed; typing "" closes it."""

    def __init__(self):
        self.q = queue.Queue()

    def readline(self):
        return self.q.get()

    def type(self, text):
        self.q.put(text)


class T5TheTerminalReader(unittest.TestCase):
    def setUp(self):
        self.feed, self.out = _Feed(), io.StringIO()
        self.bench = lv.TerminalBench(self.feed, self.out)
        self.cancel = threading.Event()
        self.addCleanup(self.feed.type, "")

    def ask_in_thread(self, lapse_s=10.0):
        box = {}
        t = threading.Thread(target=lambda: box.update(words=self.bench("PROMPT TEXT", lapse_s, self.cancel)))
        t.start()
        self.addCleanup(t.join, 5)
        return t, box

    def wait_printed(self):
        t0 = time.monotonic()
        while "PROMPT TEXT" not in self.out.getvalue() and time.monotonic() - t0 < 5:
            time.sleep(0.02)
        self.assertIn("PROMPT TEXT", self.out.getvalue())

    def test_a_line_typed_after_the_prompt_is_the_answer(self):
        t, box = self.ask_in_thread()
        self.wait_printed()
        self.feed.type("  hand over  \r\n")
        t.join(5)
        self.assertEqual(box["words"], "hand over")

    def test_words_typed_before_the_prompt_never_stand_in_for_the_hand_over(self):
        self.bench.begin()
        self.feed.type("typed long ago\n")
        t0 = time.monotonic()
        while self.bench._lines.qsize() < 1 and time.monotonic() - t0 < 5:
            time.sleep(0.02)
        t, box = self.ask_in_thread()
        self.wait_printed()
        time.sleep(0.2)
        self.assertNotIn("words", box, "the old line was not taken as the answer")
        self.feed.type("typed now\n")
        t.join(5)
        self.assertEqual(box["words"], "typed now")

    def test_a_blank_line_is_an_empty_answer(self):
        t, box = self.ask_in_thread()
        self.wait_printed()
        self.feed.type("\n")
        t.join(5)
        self.assertEqual(box["words"], "")

    def test_a_lapse_is_none(self):
        t, box = self.ask_in_thread(lapse_s=0.3)
        t.join(5)
        self.assertIsNone(box["words"])

    def test_a_cancel_is_none_before_the_lapse(self):
        t, box = self.ask_in_thread(lapse_s=30)
        self.wait_printed()
        self.cancel.set()
        t.join(5)
        self.assertIsNone(box["words"])

    def test_a_closed_terminal_is_none(self):
        t, box = self.ask_in_thread()
        self.wait_printed()
        self.feed.type("")
        t.join(5)
        self.assertIsNone(box["words"])


# --------------------------------------------------------------------------- #
# 6. the settled interface: what the schema accepts, what it refuses
# --------------------------------------------------------------------------- #

class T6TheSchemasExamples(_RunBase):
    def test_the_schemas_run_request_examples_pass_the_shape_and_its_x_refused_are_refused(self):
        spec = t85.INTERFACE["$defs"]["run_request"]
        for message in spec["examples"]:
            with self.subTest(example=message):
                _validates(message, "run_request")
                reply = self.ask(message)                           # well-formed, but names no approval
                self.assert_refused(reply, "no approval")
        for message in spec["x_refused"]:
            with self.subTest(refused=message):
                if jsonschema is not None:
                    with self.assertRaises(jsonschema.ValidationError):
                        _validates(message, "run_request")
                reply = self.ask(message)
                self.assert_refused(reply)
        self.assert_nothing_started()

    def test_the_schemas_reply_examples_validate_and_its_x_refused_do_not(self):
        spec = t85.INTERFACE["$defs"]["run_reply"]
        for reply in spec["examples"]:
            _validates(reply)
        if jsonschema is not None:
            for reply in spec["x_refused"]:
                with self.subTest(refused=reply), self.assertRaises(jsonschema.ValidationError):
                    _validates(reply)


if __name__ == "__main__":
    unittest.main()
