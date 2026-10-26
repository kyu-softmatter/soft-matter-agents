"""Every authorisation the orchestrator asks for logs the file it judged.

    python -m unittest tests.test_authorisation_logged        (from microscope_runtime/)

The run's own decision names its file in the run log's `approval.file` (card 087). The gates
inside a run -- the focus search's, the operation moves', the trap steps' -- each ask again, and
for a scratch root they ask through the `plan_authoriser` that `operator.run` installs. Each ask
is an `authorisation` event carrying the path and the sha256 of the bytes THAT ask's reader
judged, so two asks with the approval rewritten between them name two different files, and a file
rewritten after a read leaves the hash of what was read.

Mock only. Every approval and plan here is a TEST value in a temporary root.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

import test_console_signed_approval as t87                    # noqa: E402

op, orch = t87.op, t87.orch
PLAN = t87.PLAN_TIER2


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AuthorisationIsLogged(t87._Base):
    def authorisations(self, o):
        return [e for e in o.log if e["event"] == "authorisation"]

    def run_with_two_asks(self, rewrite_after_first_read=False):
        plan = t87.PLAN_OK
        path = self.approval(plan)
        seen = {}

        def observe(metric):
            o = self.built[-1]
            seen["first_bytes"] = path.read_bytes()
            seen["first"] = o._authorise(plan)
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["approved_by"] = "Test Person, again"
            path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
            seen["second_bytes"] = path.read_bytes()
            if rewrite_after_first_read:
                real, count = Path.read_bytes, []

                def rewriting(this):
                    data = real(this)
                    if this == path:
                        count.append(data)
                        if len(count) == 1:
                            this.write_bytes(data + b"\n\n")
                    return data
                Path.read_bytes = rewriting
                try:
                    seen["second"] = o._authorise(plan)
                finally:
                    Path.read_bytes = real
                seen["judged_bytes"] = count[0]
            else:
                seen["second"] = o._authorise(plan)
            return 5

        op.run(self.plan_file(plan), "run-test-d-1", backend="mock", root=self.root, observe=observe)
        return path, seen, self.authorisations(self.built[-1])

    def test_each_ask_logs_the_path_and_hash_of_the_file_it_judged(self):
        path, seen, events = self.run_with_two_asks()
        self.assertEqual(len(events), 2)
        self.assertNotEqual(seen["first_bytes"], seen["second_bytes"])
        for event, data in zip(events, (seen["first_bytes"], seen["second_bytes"])):
            self.assertTrue(event["permitted"])
            self.assertEqual(event["file"]["sha256"], sha(data))
            self.assertEqual(Path(event["file"]["path"]), path)

    def test_two_asks_with_the_file_changed_between_them_name_two_different_hashes(self):
        _, _, events = self.run_with_two_asks()
        self.assertNotEqual(events[0]["file"]["sha256"], events[1]["file"]["sha256"])

    def test_a_file_rewritten_right_after_it_was_read_is_logged_as_what_was_read(self):
        path, seen, events = self.run_with_two_asks(rewrite_after_first_read=True)
        self.assertEqual(events[1]["file"]["sha256"], sha(seen["judged_bytes"]))
        self.assertNotEqual(events[1]["file"]["sha256"], sha(path.read_bytes()),
                            "the log named the file as it stands now, not as it was judged")

    def test_the_event_names_the_decision_the_caller_got(self):
        _, seen, events = self.run_with_two_asks()
        self.assertEqual(len(events), 2)
        for event, decision in zip(events, (seen["first"], seen["second"])):
            self.assertEqual(event["approval_id"], decision.approval_id)
            self.assertEqual(event["kind"], decision.kind)
            self.assertEqual(event["file"], decision.approval_file)

    def test_a_refused_ask_is_logged_too_with_its_reasons_and_no_file_when_nothing_was_read(self):
        o = orch.Orchestrator(backend="mock")
        o.plan_authoriser = lambda p: op.authorise(p, op.approvals_on_disk(self.agent))
        decision = o._authorise(PLAN)                           # no approval anywhere in this root
        self.assertFalse(decision.permitted)
        event = self.authorisations(o)[0]
        self.assertIs(event["permitted"], False)
        self.assertEqual(event["reasons"], list(decision.reasons))
        self.assertIsNone(event["file"])

    def test_the_default_authoriser_logs_too(self):
        o = orch.Orchestrator(backend="mock")
        saved = op.approvals_on_disk
        op.approvals_on_disk = lambda *a, **k: []
        self.addCleanup(setattr, op, "approvals_on_disk", saved)
        o._authorise(PLAN)
        self.assertEqual(len(self.authorisations(o)), 1)


if __name__ == "__main__":
    unittest.main()
