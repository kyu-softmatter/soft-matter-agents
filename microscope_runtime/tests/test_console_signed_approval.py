"""Card 087: the reader of a console-signed approval, and the approval file in every run log.

    python -m unittest tests.test_console_signed_approval        (from microscope_runtime/)

An approval the console wrote carries `signed_through = {via: console, login}`. The
operator's reader then asks three things before the plan hash is looked at (plan.md 15.1
item 4): the login must be the one the person placed by hand in envelope/console_login.json
beside the safety policy, byte for byte; a missing or invalid login file refuses; and the plan
hash binds as for any approval. Every run with an approval writes `approval.file`, the path and
the sha256 of the bytes the reader judged. `--approvals <folder>` points a run at a test
folder, and only with the mock backend.

Mock only. Every approval, login file and plan here is a TEST value in a temporary root.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
REPO = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_card087_under_test", SRC / "operator.py")
orch = op.orch
validate = _load("_validate_card087", REPO / "contracts" / "validate.py")
focus_plan_tests = _load("_focus_plan_tests_for_087", TESTS / "test_focus_plan_and_scratch_root.py")

try:
    import jsonschema
except ImportError:                                              # pragma: no cover
    jsonschema = None

LOGIN = "person-test"
PLAN_OK = {"card": "plan", "id": "plan-test-087-ok", "revision": 1, "actions": [],
           "numbers": [{"name": "n", "value": 1, "unit": "1", "source": "test", "grade": "E5"}],
           "stop_criteria": [{"id": "n", "number": "n", "metric": "n", "comparator": ">="}]}
#: A plan that reaches Tier 2, so that an approval that does not cover it is a refusal before
#: anything is built. It is never run past the gate here.
PLAN_TIER2 = {"card": "plan", "id": "plan-test-087-tier2", "revision": 1,
              "actions": [{"id": "a1", "tier": 2, "reversible": True}],
              "numbers": [], "stop_criteria": []}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def login_doc(login: str = LOGIN, **over) -> dict:
    doc = {"artifact": "console_login", "schema_version": "0.1", "login": login,
           "written_by": "the person, by hand (test)", "written_at": "2026-10-26"}
    doc.update(over)
    return doc


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = focus_plan_tests._scratch(Path(self.tmp.name))
        self.agent = self.root / "microscope_runtime"
        self.approvals = self.agent / "approvals"
        self.login_path = self.agent / "envelope" / "console_login.json"
        self._saved_lock = op.RUN_LOCK_PATH
        op.RUN_LOCK_PATH = Path(self.tmp.name) / "run.lock"
        self.addCleanup(setattr, op, "RUN_LOCK_PATH", self._saved_lock)
        self.built = []                                           # every Orchestrator a test built
        init = orch.Orchestrator.__init__
        built = self.built

        def counting(s, *a, **k):
            built.append(s)
            init(s, *a, **k)
        orch.Orchestrator.__init__ = counting
        self.addCleanup(setattr, orch.Orchestrator, "__init__", init)

    # -- files -----------------------------------------------------------------------------
    def plan_file(self, plan: dict) -> Path:
        path = Path(self.tmp.name) / f"{plan['id']}.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        return path

    def approval(self, plan: dict, signed_through="absent", name="appr-test-087.json",
                 folder: Path | None = None, **over) -> Path:
        doc = {"card": "plan_approval", "id": "appr-test-087", "plan_id": plan["id"],
               "plan_revision": plan["revision"], "plan_hash": validate.plan_hash(plan),
               "approved_by": "Test Person", "approved_at": "2026-10-26T10:00:00Z"}
        if signed_through == "absent":
            pass
        elif signed_through == "console":
            doc["signed_through"] = {"via": "console", "login": LOGIN}
        else:
            doc["signed_through"] = signed_through
        doc.update(over)
        folder = self.approvals if folder is None else folder
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        return path

    def put_login(self, doc: dict | None = None) -> Path:
        self.login_path.write_text(json.dumps(login_doc() if doc is None else doc), encoding="utf-8")
        return self.login_path

    # -- runs ------------------------------------------------------------------------------
    def run_plan(self, plan: dict, run_id: str, **kw):
        return op.run(self.plan_file(plan), run_id, backend="mock", root=self.root,
                      observe=lambda m: 5, **kw)

    def decide(self, plan: dict):
        return op.authorise(plan, op.approvals_on_disk(self.agent))

    def validates(self, log: dict):
        if jsonschema is None:
            self.skipTest("jsonschema is not installed")
        schema = json.loads((REPO / "contracts/schemas/run_log.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(log, schema)


class T1TheConsoleApprovalBindsOnItsLogin(_Base):
    def test_a_matching_login_and_hash_authorises_and_the_log_names_the_file(self):
        path = self.approval(PLAN_OK, "console")
        self.put_login()
        record = self.run_plan(PLAN_OK, "run-test-087-1", runs_root=self.agent / "runs")
        self.assertEqual(record["ended"], "completed")
        approval = record["approval"]
        self.assertEqual((approval["id"], approval["kind"]), ("appr-test-087", "plan_approval"))
        self.assertEqual(Path(approval["file"]["path"]), path)
        self.assertEqual(approval["file"]["sha256"], sha256_of(path))
        self.assertEqual(approval["file"]["signed_through"], {"via": "console", "login": LOGIN})
        self.validates(record)

    def test_a_different_login_covers_nothing_and_no_device_is_touched(self):
        self.approval(PLAN_TIER2, {"via": "console", "login": "somebody-else"})
        self.put_login()
        decision = self.decide(PLAN_TIER2)
        self.assertFalse(decision.permitted)
        self.assertTrue(any("somebody-else" in r and LOGIN in r for r in decision.reasons), decision.reasons)
        with self.assertRaises(op.Refusal) as caught:
            self.run_plan(PLAN_TIER2, "run-test-087-2")
        self.assertIn("somebody-else", str(caught.exception))
        self.assertEqual(self.built, [], "an orchestrator was built for a refused plan")

    def test_a_missing_login_file_covers_nothing_and_names_the_file(self):
        self.approval(PLAN_TIER2, "console")
        decision = self.decide(PLAN_TIER2)
        self.assertFalse(decision.permitted)
        self.assertTrue(any("console_login.json" in r and "absent" in r for r in decision.reasons),
                        decision.reasons)
        with self.assertRaises(op.Refusal):
            self.run_plan(PLAN_TIER2, "run-test-087-3")
        self.assertEqual(self.built, [])

    def test_an_invalid_login_file_covers_nothing_whatever_is_wrong_with_it(self):
        self.approval(PLAN_TIER2, "console")
        bad = {
            "not json": "{\"login\": ",
            "no login": json.dumps({k: v for k, v in login_doc().items() if k != "login"}),
            "extra key": json.dumps(login_doc(email="x@example.org")),
            "wrong artifact": json.dumps(login_doc(artifact="safety")),
            "wrong version": json.dumps(login_doc(schema_version="9")),
            "login not a plain id": json.dumps(login_doc(login="a b")),
            "login an email": json.dumps(login_doc(login="x@example.org")),
            "login empty": json.dumps(login_doc(login="")),
            "login not a string": json.dumps(login_doc(login=7)),
            "no written_by": json.dumps({k: v for k, v in login_doc().items() if k != "written_by"}),
            "date not a date": json.dumps(login_doc(written_at="yesterday")),
            "a list": json.dumps([login_doc()]),
        }
        for what, text in bad.items():
            with self.subTest(what):
                self.login_path.write_text(text, encoding="utf-8")
                decision = self.decide(PLAN_TIER2)
                self.assertFalse(decision.permitted, what)
                self.assertTrue(any("console_login.json" in r and "not valid" in r for r in decision.reasons),
                                decision.reasons)
        self.assertEqual(self.built, [])

    def test_a_matching_login_with_a_wrong_plan_hash_is_still_refused(self):
        self.approval(PLAN_TIER2, "console", plan_hash="sha256:" + "0" * 64)
        self.put_login()
        decision = self.decide(PLAN_TIER2)
        self.assertFalse(decision.permitted)
        self.assertTrue(any("plan_hash" in r for r in decision.reasons), decision.reasons)
        with self.assertRaises(op.Refusal):
            self.run_plan(PLAN_TIER2, "run-test-087-4")
        self.assertEqual(self.built, [])

    def test_the_login_is_compared_byte_for_byte(self):
        self.put_login(login_doc(login="Person-Test"))               # same letters, another case
        self.approval(PLAN_TIER2, "console")
        self.assertFalse(self.decide(PLAN_TIER2).permitted)

    def test_a_test_login_binds_nothing_because_it_is_only_another_login(self):
        self.put_login()
        self.approval(PLAN_TIER2, {"via": "console", "login": "test"})
        decision = self.decide(PLAN_TIER2)
        self.assertFalse(decision.permitted)
        self.assertTrue(any("'test'" in r for r in decision.reasons), decision.reasons)

    def test_a_signed_through_that_is_not_the_console_mark_covers_nothing(self):
        self.put_login()
        for what, mark in {"another via": {"via": "email", "login": LOGIN},
                           "an extra key": {"via": "console", "login": LOGIN, "who": "x"},
                           "no login": {"via": "console"},
                           "not an object": "console-signed",
                           "null": None}.items():
            with self.subTest(what):
                self.approval(PLAN_TIER2, mark)
                decision = self.decide(PLAN_TIER2)
                self.assertFalse(decision.permitted, what)
                self.assertTrue(any("signed_through" in r for r in decision.reasons), decision.reasons)

    def test_another_plans_signed_approval_is_not_judged_against_this_plan(self):
        # An approval for a different plan leaves no reason about its login in this plan's refusal.
        self.approval(PLAN_OK, {"via": "console", "login": "somebody-else"})
        decision = self.decide(PLAN_TIER2)
        self.assertFalse(any("somebody-else" in r for r in decision.reasons), decision.reasons)


class T2AHandPlacedApprovalIsJudgedAsBefore(_Base):
    def test_no_login_file_is_needed_and_the_log_carries_the_file_without_signed_through(self):
        path = self.approval(PLAN_OK)
        self.assertFalse(self.login_path.exists())
        record = self.run_plan(PLAN_OK, "run-test-087-5")
        file = record["approval"]["file"]
        self.assertEqual(Path(file["path"]), path)
        self.assertEqual(file["sha256"], sha256_of(path))
        self.assertNotIn("signed_through", file)
        self.validates(record)

    def test_a_hand_placed_approval_is_not_made_to_wait_for_a_login_file(self):
        self.approval(PLAN_TIER2)
        self.assertTrue(self.decide(PLAN_TIER2).permitted)

    def test_a_run_with_no_approval_has_no_file_and_still_validates(self):
        record = self.run_plan(PLAN_OK, "run-test-087-6")
        self.assertEqual(record["approval"], {"id": None, "kind": None})
        self.validates(record)


class T3TheHashInTheLogIsOfTheBytesThatWereJudged(_Base):
    def test_a_file_rewritten_after_the_read_leaves_the_hash_of_what_was_read(self):
        path = self.approval(PLAN_TIER2)
        read = op.approvals_on_disk(self.agent)
        judged_bytes = path.read_bytes()
        path.write_bytes(judged_bytes + b"\n\n")                    # another process writes it after the read
        self.assertNotEqual(sha256_of(path), hashlib.sha256(judged_bytes).hexdigest())
        decision = op.authorise(PLAN_TIER2, read)
        self.assertTrue(decision.permitted)
        self.assertEqual(decision.approval_file["sha256"], hashlib.sha256(judged_bytes).hexdigest())

    def test_the_file_is_read_once_so_a_rewrite_between_two_reads_cannot_split_hash_from_judgement(self):
        # The file is rewritten the moment its bytes have been handed over once. A reader that read
        # it a second time to hash it would hash what the first read never saw.
        path = self.approval(PLAN_TIER2)
        first = path.read_bytes()
        seen, real = [], Path.read_bytes

        def rewriting(this):
            data = real(this)
            if this == path:
                seen.append(data)
                if len(seen) == 1:
                    this.write_bytes(data + b"\n\n")
            return data
        Path.read_bytes = rewriting
        self.addCleanup(setattr, Path, "read_bytes", real)
        cards = op.approvals_on_disk(self.agent)
        Path.read_bytes = real
        self.assertEqual(cards[0]["__sha256"], hashlib.sha256(first).hexdigest(),
                         "the hash is of bytes the parse never saw")

    def test_a_bom_is_part_of_the_bytes_that_are_hashed(self):
        path = self.approval(PLAN_TIER2)
        raw = b"\xef\xbb\xbf" + path.read_bytes()
        path.write_bytes(raw)
        decision = self.decide(PLAN_TIER2)
        self.assertTrue(decision.permitted)
        self.assertEqual(decision.approval_file["sha256"], hashlib.sha256(raw).hexdigest())

    def test_a_run_reads_the_folder_once(self):
        self.approval(PLAN_OK)
        real, calls = op.approvals_on_disk, []

        def counting(*a, **k):
            calls.append(a)
            return real(*a, **k)
        op.approvals_on_disk = counting
        self.addCleanup(setattr, op, "approvals_on_disk", real)
        self.run_plan(PLAN_OK, "run-test-087-7")
        self.assertEqual(len(calls), 1, "the run read the approvals more than once, so the log's hash "
                                        "could be of a file the gate did not judge")


class T4EveryLogWithAnApprovalCarriesTheFile(_Base):
    def test_a_refused_log_after_an_approval_carries_it_too(self):
        path = self.approval(PLAN_OK, "console")
        self.put_login()
        decision = self.decide(PLAN_OK)
        o = orch.Orchestrator(backend="mock")
        record = op._refused_record(o, PLAN_OK, "run-test-087-8", decision, {"policy_version": "TEST"}, "why")
        self.assertEqual(record["approval"]["file"]["sha256"], sha256_of(path))
        self.validates(record)

    def test_a_refused_log_with_no_approval_has_no_file(self):
        decision = self.decide(PLAN_OK)
        o = orch.Orchestrator(backend="mock")
        record = op._refused_record(o, PLAN_OK, "run-test-087-9", decision, {"policy_version": "TEST"}, "why")
        self.assertEqual(record["approval"], {"id": None, "kind": None})
        self.validates(record)

    def test_every_run_log_a_test_writes_here_with_an_approval_id_has_the_file(self):
        self.approval(PLAN_OK)
        record = self.run_plan(PLAN_OK, "run-test-087-10", runs_root=self.agent / "runs")
        written = json.loads((self.agent / "runs" / "run-test-087-10" / "events.jsonl").read_text(
            encoding="utf-8").splitlines()[-1])
        self.assertEqual(written["event"], "run_ended")
        self.assertIsNotNone(record["approval"]["id"])
        self.assertIn("file", record["approval"])


class T5NoFallbackToTheOldFolder(_Base):
    def test_nothing_is_read_from_microscope_agent_approvals(self):
        old = self.root / "microscope_agent" / "approvals"
        self.approval(PLAN_TIER2, folder=old)
        self.put_login()
        self.assertFalse(self.approvals.exists() and any(self.approvals.glob("*.json")))
        self.assertEqual(op.approvals_on_disk(self.agent), [])
        self.assertFalse(self.decide(PLAN_TIER2).permitted)

    def test_an_absent_approvals_folder_refuses_a_plan_that_needs_one(self):
        self.approvals.rmdir()
        with self.assertRaises(op.Refusal):
            self.run_plan(PLAN_TIER2, "run-test-087-11")

    def test_the_real_reader_names_no_other_folder(self):
        text = (SRC / "operator.py").read_text(encoding="utf-8")
        start = text.index("def approvals_on_disk")
        body = text[start:text.index("def authorise", start)]
        self.assertNotIn("microscope_agent", body)


class T6ApprovalsOptionIsMockOnly(_Base):
    """`--approvals <folder>` on a plan-run entry point: honoured with the mock backend only."""

    def test_a_mock_run_is_authorised_by_a_console_signed_approval_in_that_folder(self):
        test_root = Path(self.tmp.name) / "console_test_root" / "microscope_runtime"
        folder = test_root / "approvals"
        path = self.approval(PLAN_OK, "console", folder=folder)
        (test_root / "envelope").mkdir()
        (test_root / "envelope" / "console_login.json").write_text(json.dumps(login_doc()), encoding="utf-8")
        record = op.run(self.plan_file(PLAN_OK), "run-test-087-12", backend="mock",
                        root=self.root, approvals_dir=folder, observe=lambda m: 5)
        self.assertEqual(record["approval"]["id"], "appr-test-087")
        self.assertEqual(Path(record["approval"]["file"]["path"]), path)
        self.assertEqual(record["approval"]["file"]["signed_through"]["login"], LOGIN)
        self.assertEqual(list(self.approvals.glob("*.json")), [], "the run read the scratch default, not the folder named")

    def test_the_folders_own_login_file_is_the_one_read(self):
        # A login file in the scratch runtime does not stand in for the test folder's own.
        folder = Path(self.tmp.name) / "console_test_root" / "microscope_runtime" / "approvals"
        self.approval(PLAN_TIER2, "console", folder=folder)
        self.put_login()
        with self.assertRaises(op.Refusal) as caught:
            op.run(self.plan_file(PLAN_TIER2), "run-test-087-13", backend="mock", root=self.root,
                   approvals_dir=folder)
        self.assertIn("console_login.json", str(caught.exception))

    def test_a_non_mock_backend_refuses_the_option_before_anything_is_read_or_opened(self):
        folder = Path(self.tmp.name) / "elsewhere"
        for backend in ("hardware", "anything-else"):
            with self.subTest(backend):
                with self.assertRaises(op.Refusal) as caught:
                    op.run(Path(self.tmp.name) / "no-such-plan.json", "run-test-087-14",
                           backend=backend, approvals_dir=folder)
                self.assertIn("--approvals", str(caught.exception))
                self.assertIn("mock", str(caught.exception))
        self.assertEqual(self.built, [])

    def test_the_default_folder_named_outright_is_not_a_test_folder(self):
        self.assertEqual(op.approvals_source(op.AGENT / "approvals", "hardware"), op.AGENT / "approvals")
        self.assertIsNone(op.approvals_source(None, "hardware"))
        self.assertEqual(op.approvals_source(Path("x"), "mock"), Path("x"))
        with self.assertRaises(op.Refusal):
            op.approvals_source(Path("x"), "hardware")

    def test_the_command_line_passes_the_option_and_refuses_hardware_with_it(self):
        folder = Path(self.tmp.name) / "console_test_root" / "microscope_runtime" / "approvals"
        captured = {}

        def spy(*a, **k):
            captured.update(k)
            raise op.Refusal("stop here, the arguments are what is under test")
        saved = op.run
        op.run = spy
        self.addCleanup(setattr, op, "run", saved)
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = op.main(["--plan", "p.json", "--run-id", "r", "--backend", "mock",
                            "--approvals", str(folder)])
        self.assertEqual(code, 2)
        self.assertEqual(Path(captured["approvals_dir"]), folder)
        captured.clear()
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            op.main(["--plan", "p.json", "--run-id", "r"])
        self.assertIsNone(captured["approvals_dir"])
        op.run = saved
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = op.main(["--plan", "p.json", "--run-id", "r", "--backend", "hardware",
                            "--approvals", str(folder)])
        self.assertEqual(code, 2)
        self.assertIn("--approvals", err.getvalue())
        self.assertEqual(self.built, [])

    def test_the_command_line_run_prints_the_approval_that_authorised_it(self):
        folder = Path(self.tmp.name) / "console_test_root" / "microscope_runtime" / "approvals"
        path = self.approval(PLAN_OK, "console", folder=folder)
        (folder.parent / "envelope").mkdir()
        (folder.parent / "envelope" / "console_login.json").write_text(json.dumps(login_doc()), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        saved_agent = op.AGENT                                    # main reads the runtime's own policy
        op.AGENT = self.agent
        self.addCleanup(setattr, op, "AGENT", saved_agent)
        with redirect_stdout(out), redirect_stderr(err):
            code = op.main(["--plan", str(self.plan_file(PLAN_OK)), "--run-id", "run-test-087-15",
                            "--backend", "mock", "--approvals", str(folder)])
        self.assertEqual(code, 0, out.getvalue() + err.getvalue())
        self.assertIn(sha256_of(path), out.getvalue())
        self.assertIn(LOGIN, out.getvalue())

    def test_the_operation_plan_script_refuses_the_option_before_its_link_opens(self):
        script = _load("_run_operation_plan_087", SRC / "run_operation_plan.py")
        opened = []
        real = script._load

        def guard(name, path):
            if "python_serial" in str(path):
                opened.append(path)
                raise AssertionError("the serial link was reached")
            return real(name, path)
        script._load = guard
        self.addCleanup(setattr, script, "_load", real)
        with self.assertRaises(Exception) as caught:
            script.run(Path("p.json"), "run-test-087-16", "the person's words", approvals=Path("x"))
        self.assertEqual(type(caught.exception).__name__, "Refusal")
        self.assertEqual(opened, [])


class T7TheHandWrittenLoginCheckAgreesWithTheSchema(_Base):
    @unittest.skipIf(jsonschema is None, "jsonschema is not installed")
    def test_every_case_is_judged_as_the_schema_judges_it(self):
        schema = json.loads((REPO / "contracts/schemas/console_login.schema.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        cases = [login_doc(), login_doc(login="a"), login_doc(login="A.b_c-d"), login_doc(login="a" * 64),
                 login_doc(login="a" * 65), login_doc(login="-a"), login_doc(login="a b"), login_doc(login=""),
                 login_doc(login=None), login_doc(login="x@y"), login_doc(written_at="2026-13-40"),
                 login_doc(written_at="26-10-26"), login_doc(written_by=""), login_doc(written_by=3),
                 login_doc(extra=1), login_doc(artifact="x"), login_doc(schema_version="0.2"),
                 {k: v for k, v in login_doc().items() if k != "written_at"}, [], "login", 3, None]
        for doc in cases:
            with self.subTest(doc=doc):
                self.assertEqual(op.console_login_problem(doc) is None, validator.is_valid(doc),
                                 f"{doc!r}: {op.console_login_problem(doc)}")


if __name__ == "__main__":
    unittest.main()
