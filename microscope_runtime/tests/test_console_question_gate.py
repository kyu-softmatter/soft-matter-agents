"""Card 089: a run from another login's question waits for the person's own plan approval.

    python -m unittest tests.test_console_question_gate        (from microscope_runtime/)

plan.md 6 and 7.1.1 rule 9. The console's server mints a question id `<agent>-<YYYYMMDD>-c<NNN>`;
a window question never carries the `c`. The runtime keys on the plan's `qid` alone: a plan whose
qid ends in `-c<NNN>` is another login's, only an exact plan approval covers it (never a scope
approval, never Tier 0 or 1 on their own), and the inbox item that asked it is read to confirm it,
by path and by the sha256 of its bytes. Until the inbox opens no such folder exists, so every such
plan is refused even with an approval.

Mock only. Every plan, approval and inbox item here is a TEST value in a temporary root; nothing
is written to microscope_agent/console_inbox/.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

import test_console_signed_approval as t87                    # noqa: E402

op, orch = t87.op, t87.orch

QID = "mic-20261026-c001"
WINDOW_QID = "mic-20261026-001"
#: A Tier 1 action on a device nobody may command: it passes the gate and is refused after it, by name.
BOGUS = {"id": "a1", "device": "NoSuchDevice", "action": "move", "tier": 1, "reversible": True}
ITEM_ID = "ci-20261026-101500-ab12"


def plan_for(qid, plan_id="plan-test-089", actions=None, **extra):
    plan = copy.deepcopy(t87.PLAN_OK)
    plan.update({"id": plan_id, "qid": qid, "actions": actions or []})
    plan.update(extra)
    return plan


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Gate(t87._Base):
    def setUp(self):
        super().setUp()
        self.inbox = self.root / "microscope_agent" / "console_inbox"

    # -- the inbox, in a temp folder ----------------------------------------------------------
    def put_item(self, qid=QID, item_id=ITEM_ID, attachments=(), raw=None, name=None):
        """Write an inbox item and the attachments it names; return (path, bytes)."""
        self.inbox.mkdir(parents=True, exist_ok=True)
        listed = []
        for file, data in attachments:
            (self.inbox / file).write_bytes(data)
            listed.append({"file": file, "sha256": sha(data)})
        doc = {"artifact": "console_question", "schema_version": "0.1", "item_id": item_id,
               "question_id": qid, "words": "a test question", "attachments": listed,
               "asked_by": {"login": "other-login", "console_role": {
                   "may_ask": True, "may_draft": False, "agents": ["microscope"],
                   "may_ask_model_run": False}},
               "asked_at": "2026-10-26T10:15:00Z", "asker_mark": {"kind": "other_login"}}
        data = raw if raw is not None else json.dumps(doc, indent=2).encode("utf-8")
        path = self.inbox / (name or f"{item_id}.json")
        path.write_bytes(data)
        return path, data

    def scope_approval(self, qid):
        self.approvals.mkdir(parents=True, exist_ok=True)
        path = self.approvals / "scope-test-089.json"
        path.write_text(json.dumps({
            "card": "scope_approval", "id": "scope-test-089", "qids": [qid],
            "applies_to_all_qids": True, "voided": False,
            "approved_by": "Test Person", "approved_at": "2026-10-26T10:00:00Z"}), encoding="utf-8")
        return path

    def assertRefusedAtTheGate(self, plan, *words):
        """Refused before any command: no orchestrator was ever built, so no device was touched."""
        with self.assertRaises(op.Refusal) as caught:
            self.run_plan(plan, "run-test-089")
        for word in words:
            self.assertIn(word, str(caught.exception))
        self.assertEqual(self.built, [], "an orchestrator was built, so the gate was not first")
        return str(caught.exception)


class T1AnApprovedQuestionRunsAndNamesItsItem(_Gate):
    def test_an_exact_approval_and_a_readable_item_run_and_the_log_names_the_item(self):
        plan = plan_for(QID)
        self.approval(plan)
        path, data = self.put_item(attachments=[(f"{ITEM_ID}--notes.txt", b"some notes")])
        log = self.run_plan(plan, "run-test-089-1")
        self.assertEqual(log["console_item"], {
            "path": log["console_item"]["path"], "sha256": sha(data), "item_id": ITEM_ID,
            "question_id": QID,
            "attachments": [{"file": f"{ITEM_ID}--notes.txt", "sha256": sha(b"some notes")}]})
        self.assertEqual(Path(log["console_item"]["path"]).name, path.name)
        self.assertEqual(log["approval"]["kind"], "plan_approval")
        self.assertIn("file", log["approval"], "approval.file went missing beside console_item")
        self.validates(log)

    def test_the_console_signed_form_of_an_exact_approval_covers_it_too(self):
        plan = plan_for(QID)
        self.put_login()
        self.approval(plan, signed_through="console")
        self.put_item()
        log = self.run_plan(plan, "run-test-089-2")
        self.assertEqual(log["console_item"]["question_id"], QID)
        self.assertEqual(log["approval"]["file"]["signed_through"]["login"], t87.LOGIN)

    def test_a_console_plan_that_ends_in_a_refusal_after_the_gate_still_names_its_item(self):
        # An action no device takes: refused after the gate, before any command, so the refused
        # log is written and check 91 reads its item.
        plan = plan_for(QID, actions=[BOGUS])
        self.approval(plan)
        self.put_item()
        with self.assertRaises((op.Refusal, orch.InterlockError)):
            self.run_plan(plan, "run-test-089-3", runs_root=Path(self.tmp.name) / "runs")
        written = json.loads((Path(self.tmp.name) / "runs" / "run-test-089-3" / "log.json").read_text(encoding="utf-8"))
        self.assertEqual(written["ended"], "refused")
        self.assertEqual(written["console_item"]["question_id"], QID)


class T2NothingButAnExactApprovalCoversIt(_Gate):
    def test_no_approval_is_refused_with_the_qid_and_the_rule(self):
        self.put_item()
        reason = self.assertRefusedAtTheGate(plan_for(QID), QID, "another login")
        self.assertIn("plan_approval", reason)

    def test_a_scope_approval_whose_range_covers_it_does_not(self):
        self.scope_approval(QID)
        self.put_item()
        self.assertRefusedAtTheGate(plan_for(QID), QID, "another login")

    def test_a_tier_1_plan_with_no_approval_does_not_run_either(self):
        self.put_item()
        plan = plan_for(QID, actions=[BOGUS])
        self.assertRefusedAtTheGate(plan, QID, "another login")

    def test_the_decision_itself_never_permits_it_through_a_scope_approval(self):
        self.scope_approval(QID)
        decision = self.decide(plan_for(QID))
        self.assertFalse(decision.permitted)
        self.assertTrue(any("another login" in r for r in decision.reasons), decision.reasons)

    def test_a_refused_console_plan_leaves_no_run_folder_and_no_device_call(self):
        runs = Path(self.tmp.name) / "runs"
        with self.assertRaises(op.Refusal):
            self.run_plan(plan_for(QID), "run-test-089-4", runs_root=runs)
        self.assertFalse((runs / "run-test-089-4").exists())
        self.assertEqual(self.built, [])

    def test_an_approval_of_another_revision_or_hash_does_not_cover_it(self):
        plan = plan_for(QID)
        self.approval(plan, plan_hash="0" * 64)
        self.put_item()
        self.assertRefusedAtTheGate(plan, QID)


class T3TheConfirmingRead(_Gate):
    def refused_with_approval(self, *words):
        plan = plan_for(QID)
        self.approval(plan)
        return self.assertRefusedAtTheGate(plan, QID, *words)

    def test_no_inbox_folder_refuses_even_with_an_approval(self):
        self.assertFalse(self.inbox.exists())
        self.refused_with_approval("not open")

    def test_an_inbox_with_no_item_for_this_question_refuses(self):
        self.put_item(qid="mic-20261026-c002", item_id="ci-20261026-101600-cd34")
        self.refused_with_approval("0 items")

    def test_an_unreadable_item_refuses(self):
        self.put_item(raw=b"{ this is not json")
        self.refused_with_approval("cannot be read")

    def test_an_unreadable_item_for_some_other_question_refuses_too(self):
        # Any item that cannot be read could be the one that asked it.
        self.put_item()
        self.put_item(raw=b"\xff\xfe not an item", item_id="ci-20261026-101700-ef56")
        self.refused_with_approval("cannot be read")

    def test_an_attachment_whose_sha256_does_not_match_refuses(self):
        path, _ = self.put_item(attachments=[(f"{ITEM_ID}--notes.txt", b"some notes")])
        (self.inbox / f"{ITEM_ID}--notes.txt").write_bytes(b"swapped after it was asked with")
        self.refused_with_approval("sha256")

    def test_an_attachment_that_is_missing_refuses(self):
        self.put_item(attachments=[(f"{ITEM_ID}--notes.txt", b"some notes")])
        (self.inbox / f"{ITEM_ID}--notes.txt").unlink()
        self.refused_with_approval("cannot be read")

    def test_two_items_for_one_question_refuse(self):
        self.put_item()
        self.put_item(item_id="ci-20261026-101800-aa11")
        self.refused_with_approval("2 items")

    def test_an_item_whose_file_name_is_not_its_id_refuses(self):
        self.put_item(name="ci-20261026-101900-bb22.json")
        self.refused_with_approval("named by its id")


class T4AWindowQuestionIsAsItWasBefore(_Gate):
    def test_without_an_approval_a_tier_0_plan_still_runs_and_names_no_item(self):
        log = self.run_plan(plan_for(WINDOW_QID), "run-test-089-5")
        self.assertNotIn("console_item", log)
        self.assertIsNone(log["approval"]["id"])

    def test_a_scope_approval_changes_nothing_for_it(self):
        self.scope_approval(WINDOW_QID)
        log = self.run_plan(plan_for(WINDOW_QID), "run-test-089-6")
        self.assertNotIn("console_item", log)

    def test_a_tier_1_plan_passes_the_gate_as_before(self):
        # It is refused later for the action's device, which is not the console rule's reason.
        plan = plan_for(WINDOW_QID, actions=[BOGUS])
        with self.assertRaises(orch.InterlockError) as caught:
            self.run_plan(plan, "run-test-089-7")
        self.assertNotIn("another login", str(caught.exception))
        self.assertTrue(self.built, "the gate refused a window plan")

    def test_an_approval_is_not_asked_to_have_an_item(self):
        plan = plan_for(WINDOW_QID)
        self.approval(plan)
        self.assertFalse(self.inbox.exists())
        log = self.run_plan(plan, "run-test-089-8")
        self.assertNotIn("console_item", log)
        self.assertEqual(log["approval"]["kind"], "plan_approval")

    def test_a_plan_with_no_qid_at_all_stays_as_it_was(self):
        plan = plan_for(WINDOW_QID)
        del plan["qid"]
        log = self.run_plan(plan, "run-test-089-9")
        self.assertNotIn("console_item", log)


class T5TheIdIsReadFromTheQidAlone(_Gate):
    LOOKS_LIKE_A_WINDOW_QUESTION = {
        "thread": "solo-mic-20261026-001",
        "asked_by": {"login": "the-person", "console_role": {"may_ask": True}},
        "asker_mark": {"kind": "persons_own"},
        "source": "window", "console": False, "from_console": False,
    }

    def test_every_other_field_looking_like_a_window_question_still_refuses(self):
        plan = plan_for(QID, plan_id="plan-mic-20261026-001", **self.LOOKS_LIKE_A_WINDOW_QUESTION)
        self.assertRefusedAtTheGate(plan, QID, "another login")

    def test_and_the_same_with_an_approval_but_no_item(self):
        plan = plan_for(QID, plan_id="plan-mic-20261026-001", **self.LOOKS_LIKE_A_WINDOW_QUESTION)
        self.approval(plan)
        self.assertRefusedAtTheGate(plan, QID)

    def test_every_other_field_looking_like_a_console_question_does_not_make_it_one(self):
        plan = plan_for(WINDOW_QID, plan_id="plan-mic-20261026-c001", thread="solo-mic-20261026-c001",
                        console_item={"path": "x"}, asker_mark={"kind": "other_login"})
        log = self.run_plan(plan, "run-test-089-10")
        self.assertNotIn("console_item", log)

    def test_the_item_s_own_asker_mark_is_not_read(self):
        # An item that says it is the person's own changes nothing: the `c` decided it.
        plan = plan_for(QID)
        self.approval(plan)
        doc = json.loads(self.put_item()[1])
        doc["asker_mark"] = {"kind": "persons_own"}
        self.put_item(raw=json.dumps(doc).encode("utf-8"))
        self.assertEqual(self.run_plan(plan, "run-test-089-11")["console_item"]["question_id"], QID)


class T7EveryLogNamesTheFileTheRunOpened(_Gate):
    def check(self, log, plan_file):
        self.assertIn("plan_path", log)
        self.assertNotIn(chr(92), log["plan_path"], "a backslash names no card")
        self.assertTrue((op.REPO / log["plan_path"]).samefile(plan_file),
                        f"{log['plan_path']} is not the file the run opened")

    def test_a_completed_window_run_names_its_plan(self):
        plan = plan_for(WINDOW_QID)
        plan_file = self.plan_file(plan)
        log = op.run(plan_file, "run-test-089-12", backend="mock", root=self.root, observe=lambda m: 5)
        self.check(log, plan_file)
        self.validates(log)

    def test_a_completed_console_run_names_its_plan_beside_its_item(self):
        plan = plan_for(QID)
        self.approval(plan)
        self.put_item()
        plan_file = self.plan_file(plan)
        log = op.run(plan_file, "run-test-089-13", backend="mock", root=self.root, observe=lambda m: 5)
        self.check(log, plan_file)
        self.assertIn("console_item", log)
        self.validates(log)

    def test_a_run_refused_after_the_gate_names_its_plan_in_the_log_it_writes(self):
        plan = plan_for(WINDOW_QID, actions=[BOGUS])
        plan_file = self.plan_file(plan)
        runs = Path(self.tmp.name) / "runs"
        with self.assertRaises(orch.InterlockError):
            op.run(plan_file, "run-test-089-14", backend="mock", root=self.root, runs_root=runs,
                   observe=lambda m: 5)
        written = json.loads((runs / "run-test-089-14" / "log.json").read_text(encoding="utf-8"))
        self.assertEqual(written["ended"], "refused")
        self.check(written, plan_file)

    def test_a_plan_inside_the_repository_is_named_relative_with_forward_slashes(self):
        inside = op.REPO / "microscope_runtime" / "tests" / "no-such-dir" / "plan.json"
        self.assertEqual(op.plan_path_of(inside), "microscope_runtime/tests/no-such-dir/plan.json")

    def test_a_plan_given_by_a_relative_path_is_named_by_the_file_it_is(self):
        plan = plan_for(WINDOW_QID)
        plan_file = self.plan_file(plan)
        import os
        here = os.getcwd()
        os.chdir(plan_file.parent)
        self.addCleanup(os.chdir, here)
        log = op.run(Path(plan_file.name), "run-test-089-15", backend="mock", root=self.root,
                     observe=lambda m: 5)
        self.check(log, plan_file)


class T6TheMark(unittest.TestCase):
    def test_what_the_c_form_is(self):
        for qid, console in [("mic-20261026-c001", True), ("sim-20261026-c999", True),
                             ("mic-20261026-001", False), ("mic-20261026-c01", False),
                             ("mic-20261026-c0011", False), ("mic-20261026-001c001x", False),
                             ("mic-20261026-001-c001", True)]:
            self.assertIs(op.is_console(qid), console, qid)

    def test_a_missing_qid_is_not_a_console_question(self):
        self.assertFalse(op.is_console(None))


if __name__ == "__main__":
    unittest.main()
