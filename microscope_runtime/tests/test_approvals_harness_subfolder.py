"""Card 088: the three readers of approvals/ read its top level only, never approvals/harness/.

    python -m unittest tests.test_approvals_harness_subfolder        (from microscope_runtime/)

The person's word on a harness proposal may be given through the console, which writes it into
`approvals/harness/HP-<n>-<12 hex>.json` (plan.md 8.3, 15.1 item 4). One of the three things that
keep such a word away from the instrument is that the runtime's readers glob `approvals/*.json` and
never recurse. This holds each of the three to it: the operator's `approvals_on_disk`, the live-view
host's list lookup and `mm_config_gate.read_approvals`.

For each, a temporary approvals folder holds one valid top-level file; a `harness/HP-902-<12 hex>.json`
is planted once as a valid harness_permission and once as malformed JSON, and the reader must return
what it returned without the subfolder and refuse nothing because of it. A malformed file at the
top level still refuses, which is what shows the test can tell the two apart. Each test is then
held against a RECURSING variant of the same reader -- its own source with `*.json` made
`**/*.json`, built here, with no edit to `src/` -- and must fail on it.

Mock only. Every file is a TEST value in a temporary folder.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


lv = _load("_live_view_088", SRC / "live_view.py")
op = lv.op
gate = _load("_mm_config_gate_088", SRC / "mm_config_gate.py")
validate = _load("_validate_088", REPO / "contracts" / "validate.py")

try:
    import jsonschema
except ImportError:                                              # pragma: no cover
    jsonschema = None

PROPOSAL_SHA = "ab12cd34ef56" + "0" * 52
HARNESS_NAME = f"HP-902-{PROPOSAL_SHA[:12]}.json"
HARNESS_VALID = {
    "artifact": "harness_permission", "schema_version": "0.1", "proposal": "HP-902",
    "proposal_commit": "1" * 40, "proposal_sha256": PROPOSAL_SHA, "decision": "yes",
    "screen_words": "I allow HP-902 at " + PROPOSAL_SHA[:12] + " (TEST)",
    "signed_at": "2026-10-26T10:00:00Z", "signed_through": {"via": "console", "login": "person-test"},
}
HARNESS_VALID_BYTES = json.dumps(HARNESS_VALID, indent=2).encode("utf-8")
HARNESS_MALFORMED_BYTES = b'{"artifact": "harness_permission", "proposal": '      # cut off, never closes

#: a top-level file each reader accepts
PLAN_APPROVAL = {"card": "plan_approval", "id": "appr-test-088", "plan_id": "plan-test-088",
                 "plan_revision": 1, "plan_hash": "sha256:" + "a" * 64,
                 "approved_by": "Test Person", "approved_at": "2026-10-26T10:00:00Z"}
MM_APPROVAL = {"artifact": "mm_config_approval", "schema_version": "0.1",
               "written_by": "TEST FIXTURE, not the person", "written_at": "2026-10-26",
               "label": "TEST", "configuration": {"sha256": "c" * 64}}
LIVE_LIST = {"artifact": "live_view_list", "schema_version": "0.1",
             "written_by": "TEST FIXTURE, not the person", "written_at": "2026-10-26",
             "label": "TEST FIXTURE: transmitted light",
             "transmitted_lamp": {"device": "DiaLamp", "intensity": {"value": 100}},
             "camera": {"device": "Kinetix_red", "exposure_ms": 20, "frame_ceiling": 40}}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def recursing(func, glob_text: str, module):
    """`func` as it is, but its glob of `*.json` recursing: the reader this test must catch.

    Built from the real function's own source, so the variant differs from it in nothing else, and
    refuses to build if the glob it is to change is not there exactly once (a reader that moved).
    """
    source = textwrap.dedent(inspect.getsource(func))
    if source.count(glob_text) != 1:
        raise AssertionError(f"{func.__name__} no longer holds {glob_text!r} exactly once; this test "
                             "has to be read against the reader as it is now")
    changed = source.replace(glob_text, glob_text.replace('"*.json"', '"**/*.json"'))
    scope: dict = {}
    exec(compile(changed, f"<recursing {func.__name__}>", "exec"), module.__dict__, scope)
    return scope[func.__name__]


class _Base:
    #: set by each subclass
    top_name = "top.json"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "approvals"
        self.folder.mkdir()
        self.top_bytes = json.dumps(self.top_doc, indent=2).encode("utf-8")
        (self.folder / self.top_name).write_bytes(self.top_bytes)

    # -- planting ----------------------------------------------------------------------------
    def plant(self, data: bytes) -> Path:
        path = self.folder / "harness" / HARNESS_NAME
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        return path

    def unplant(self):
        path = self.folder / "harness" / HARNESS_NAME
        if path.exists():
            path.unlink()

    # -- the reader under test: set by each subclass -----------------------------------------
    def observe(self, reader):
        """What `reader` returns for self.folder, as something that compares with ==."""
        raise NotImplementedError

    def refuses_malformed_top_level(self, reader) -> bool:
        raise NotImplementedError

    def real(self):
        raise NotImplementedError

    def variant(self):
        raise NotImplementedError

    # -- the one assertion, run against the real reader and against the recursing variant ----------
    def judge(self, reader):
        """Raises AssertionError when `reader` lets the subfolder change anything."""
        without = self.observe(reader)
        self.assertTrue(without, "the reader returned nothing for the valid top-level file, so the "
                                 "test would pass vacuously")
        for what, data in (("a valid harness_permission", HARNESS_VALID_BYTES),
                           ("malformed JSON", HARNESS_MALFORMED_BYTES)):
            self.plant(data)
            try:
                with_it = self.observe(reader)
            except Exception as exc:                         # noqa: BLE001 - any refusal is the failure
                self.fail(f"{what} in approvals/harness/ made the reader refuse: {type(exc).__name__}: {exc}")
            finally:
                self.unplant()
            self.assertEqual(with_it, without, f"{what} in approvals/harness/ changed what the reader returns")
        self.plant(HARNESS_VALID_BYTES)
        (self.folder / "harness" / "HP-903-malformed.json").write_bytes(HARNESS_MALFORMED_BYTES)
        try:
            self.assertEqual(self.observe(reader), without, "both together changed what the reader returns")
        finally:
            self.unplant()
            (self.folder / "harness" / "HP-903-malformed.json").unlink()

    # -- the tests ---------------------------------------------------------------------------
    def test_the_valid_harness_permission_is_one_the_schema_accepts(self):
        if jsonschema is None:
            self.skipTest("jsonschema is not installed")
        schema = json.loads((REPO / "contracts/schemas/harness_permission.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(HARNESS_VALID)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(HARNESS_MALFORMED_BYTES)

    def test_the_real_reader_ignores_the_harness_folder(self):
        self.judge(self.real())

    def test_the_test_fails_against_a_recursing_reader(self):
        with self.assertRaises(AssertionError):
            self.judge(self.variant())

    def test_a_malformed_top_level_file_still_refuses_the_real_reader(self):
        # Without this the two outcomes above could be one outcome: a reader that never refuses.
        self.assertFalse(self.refuses_malformed_top_level(self.real()), "a good folder refused")
        (self.folder / "broken.json").write_bytes(HARNESS_MALFORMED_BYTES)
        self.assertTrue(self.refuses_malformed_top_level(self.real()))

    def test_a_malformed_top_level_file_refuses_the_variant_too(self):
        # The variant differs in recursion and in nothing else, so its top-level behaviour is the
        # real reader's; if it were not, it would be a variant of something else.
        (self.folder / "broken.json").write_bytes(HARNESS_MALFORMED_BYTES)
        self.assertTrue(self.refuses_malformed_top_level(self.variant()))


class OperatorApprovalsOnDisk(_Base, unittest.TestCase):
    top_name = "appr-test-088.json"
    top_doc = PLAN_APPROVAL

    def real(self):
        return op.approvals_on_disk

    def variant(self):
        return recursing(op.approvals_on_disk, 'folder.glob("*.json")', op)

    def observe(self, reader):
        return reader(folder=self.folder)

    def refuses_malformed_top_level(self, reader) -> bool:
        try:
            reader(folder=self.folder)
        except op.Refusal:
            return True
        return False

    def test_the_top_level_card_is_what_comes_back(self):
        cards = op.approvals_on_disk(folder=self.folder)
        self.assertEqual([c["id"] for c in cards], ["appr-test-088"])
        self.assertEqual(cards[0]["__sha256"], sha(self.top_bytes))


class MmConfigGateReadApprovals(_Base, unittest.TestCase):
    top_name = "mm-approval-088.json"
    top_doc = MM_APPROVAL

    def real(self):
        return gate.read_approvals

    def variant(self):
        return recursing(gate.read_approvals, 'folder.glob("*.json")', gate)

    def observe(self, reader):
        return reader(self.folder)

    def refuses_malformed_top_level(self, reader) -> bool:
        try:
            reader(self.folder)
        except gate.ConfigRefused:
            return True
        return False

    def test_the_top_level_card_is_what_comes_back(self):
        docs = gate.read_approvals(self.folder)
        self.assertEqual([d["__name"] for d in docs], [self.top_name])

    def test_a_harness_permission_never_approves_a_configuration(self):
        # Planted with the very sha256 the top-level approval holds, as a file that would approve
        # the configuration were it read: approval_for must find the top-level one only.
        doc = dict(HARNESS_VALID, configuration={"sha256": "c" * 64}, artifact=gate.APPROVAL_ARTIFACT)
        self.plant(json.dumps(doc).encode("utf-8"))
        found = gate.approval_for("c" * 64, self.folder)
        self.assertEqual(found["id"], self.top_name)


class LiveViewHostLookup(_Base, unittest.TestCase):
    top_name = "live-list-088.json"
    top_doc = LIVE_LIST

    def setUp(self):
        super().setUp()
        root = Path(self.tmp.name)
        self.host = lv.LiveHost(self.folder, root / "runs", address_file=root / "live_host.json",
                                log_path=root / "live_host_log.jsonl")

    def real(self):
        return lv.LiveHost._find

    def variant(self):
        return recursing(lv.LiveHost._find, 'self.approvals_dir.glob("*.json")', lv)

    def _ask(self, finder, digest: str):
        """The host's own answer to a request for this hash, through `finder` in place of `_find`."""
        saved = lv.LiveHost._find
        lv.LiveHost._find = finder
        try:
            return self.host._handle(json.dumps({"live_on": digest}).encode("utf-8") + b"\n")
        finally:
            lv.LiveHost._find = saved

    def observe(self, reader):
        return {
            "top level": reader(self.host, sha(self.top_bytes)),
            "harness (valid)": reader(self.host, sha(HARNESS_VALID_BYTES)),
            "harness (malformed)": reader(self.host, sha(HARNESS_MALFORMED_BYTES)),
            "nothing": reader(self.host, "0" * 64),
            "asked for the harness file": self._ask(reader, sha(HARNESS_VALID_BYTES)),
            "asked for the malformed one": self._ask(reader, sha(HARNESS_MALFORMED_BYTES)),
        }

    def refuses_malformed_top_level(self, reader) -> bool:
        bad = self.folder / "broken.json"
        if not bad.exists():
            return False
        reply = self._ask(reader, sha(bad.read_bytes()))
        return reply.get("live_on") == "refused" and "broken.json" in reply.get("reason", "")

    def test_the_top_level_list_is_what_the_lookup_finds(self):
        path, data = self.host._find(sha(self.top_bytes))
        self.assertEqual((path.name, data), (self.top_name, self.top_bytes))
        self.assertIsNone(self.host._find(sha(HARNESS_VALID_BYTES)))

    def test_a_harness_file_is_not_a_list_the_host_will_run(self):
        self.plant(HARNESS_VALID_BYTES)
        reply = self.host._handle(json.dumps({"live_on": sha(HARNESS_VALID_BYTES)}).encode() + b"\n")
        self.assertEqual(reply["live_on"], "refused")
        self.assertIn("no approved live-view list has that sha256", reply["reason"])


if __name__ == "__main__":
    unittest.main()
