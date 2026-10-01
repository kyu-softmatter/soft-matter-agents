"""Card 052: what `synthesis.py --write` writes must pass the validator.

    python -m unittest microscope_agent/tests/test_synthesis_write.py

The writer is run on a copy of a committed fan-out (mic-20260930-001: one
configuration, an interval, an allowed set, nine preconditions and nine
abstentions, so every carried field is exercised), inside a scratch root
whose `contracts/` is the repository's own. The validator is then run on the
copied cards and must report no FAIL against the written synthesis card.

Nothing here touches hardware or the shared working tree: the card is written
under a temporary directory and removed with it.
"""

from __future__ import annotations

import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1]
REPO = AGENT.parent
SRC = AGENT / "src"
QID = "mic-20260930-001"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class SynthesisWriteTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="synthesis-write-"))
        root = cls.tmp / "root"
        folder = root / "microscope_agent" / "questions" / QID
        folder.mkdir(parents=True)
        (root / "contracts").symlink_to(REPO / "contracts")
        source = AGENT / "questions" / QID
        for name in ["goal.json", "configs.json"] + sorted(p.name for p in source.glob("axis_*.json")):
            shutil.copy(source / name, folder / name)
        s4 = _load("_synthesis_under_test", SRC / "synthesis.py")
        s4.REPO = root
        s4.QUESTIONS = root / "microscope_agent" / "questions"
        cls.code = s4.main(["--qid", QID, "--write"])
        cls.folder = folder
        cls.card_path = folder / "synthesis.json"
        cls.card = json.loads(cls.card_path.read_text()) if cls.card_path.exists() else None
        run = subprocess.run(
            [sys.executable, str(REPO / "contracts" / "validate.py"),
             *sorted(str(p) for p in folder.glob("*.json"))],
            capture_output=True, text=True, cwd=REPO)
        cls.failures = [line for line in run.stdout.splitlines()
                        if " FAIL " in line and "synthesis.json" in line]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_writer_writes(self):
        self.assertEqual(self.code, 0)
        self.assertIsNotNone(self.card)

    def test_validator_finds_nothing_wrong_with_the_written_card(self):
        self.assertEqual(self.failures, [], "\n".join(self.failures))

    def test_carried_bounds_name_their_axes(self):
        for row in self.card.get("allowed_sets", []):
            self.assertTrue(row.get("from_axes"), row)
            self.assertNotIn("origin", row)
        for row in self.card.get("preconditions", []):
            self.assertTrue(row.get("axis"), row)
            self.assertNotIn("origin", row)

    def test_operating_point_carries_no_more_digits_than_a_decade(self):
        chosen = {p["number"] for p in self.card.get("operating_point", [])}
        self.assertTrue(chosen)
        for n in self.card["numbers"]:
            if n["name"] not in chosen:
                continue
            self.assertEqual(n["precision"], "order_of_magnitude")
            v = float(n["value"])
            digits = len(f"{v:.15g}".replace(".", "").replace("-", "").strip("0"))
            self.assertLessEqual(digits, 1, f"{n['name']} = {v} claims {digits} figures")
            self.assertTrue(n.get("formula") and n.get("inputs"), n)
            self.assertFalse(math.isnan(v))


if __name__ == "__main__":
    unittest.main()
