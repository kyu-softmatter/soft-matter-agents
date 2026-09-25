"""Card 041 item 3: an approval written from Windows PowerShell is readable.

    python -m unittest microscope_agent/tests/test_approval_encoding.py

PowerShell 5.1's `Set-Content -Encoding utf8` writes a byte-order mark, and
approvals_on_disk() refused such a file as unreadable JSON. Refusing was
fail-closed and correct; the fix reads utf-8-sig, which accepts the mark and
changes nothing else. So there are two tests and both matter: the mark is
read, and a file malformed for any other reason is still refused.

Watched failing: with `encoding="utf-8-sig"` put back to a bare read_text(),
test_bom_approval_is_read fails with Refusal and the other still passes.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


op = _load("_op_encoding_under_test", SRC / "operator.py")

CARD = {"card": "plan_approval", "id": "appr-test-bom", "plan_id": "plan-test", "plan_revision": 1}


class ApprovalEncoding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "agent" / "approvals").mkdir(parents=True)
        self.folder = root / "agent" / "approvals"
        self._agent, self._repo = op.AGENT, op.REPO
        op.AGENT, op.REPO = root / "agent", root

    def tearDown(self):
        op.AGENT, op.REPO = self._agent, self._repo
        self.tmp.cleanup()

    def test_bom_approval_is_read(self):
        (self.folder / "a.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(CARD).encode("utf-8"))
        cards = op.approvals_on_disk()
        self.assertEqual([c["id"] for c in cards], ["appr-test-bom"])

    def test_malformed_approval_is_still_refused(self):
        (self.folder / "a.json").write_bytes(b"\xef\xbb\xbf{\"card\": \"plan_approval\",")
        with self.assertRaises(op.Refusal):
            op.approvals_on_disk()


if __name__ == "__main__":
    unittest.main()
