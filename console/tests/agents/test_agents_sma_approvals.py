"""SmaFiles reads the seats' approvals/ (C-03): utf-8-sig, each approval checked against the plan
cards of its question by soft-matter-agents' plan hash, and nothing written."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from dino_autofocus.agents import MockStore, SmaFiles
from dino_autofocus.agents.mock_store import MOCK_DATA
from dino_autofocus.agents.sma_files import plan_hash

QID = "mic-20260925-002"
PLAN_FILE = f"plan_microscope_{QID}.json"


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


def approval(qid: str, rev: int, h: str, when: str) -> dict:
    return {"card": "plan_approval", "schema_version": "0.1", "id": f"appr-{qid}-r{rev}",
            "qid": qid, "thread": f"solo-{qid}", "round": 0, "revision": rev, "author": "human",
            "created_at": when, "status": "APPROVED", "plan_id": f"plan-{qid}-r{rev}",
            "plan_revision": rev, "plan_hash": h, "approved_by": "kyuhwan", "approved_at": when,
            "note": "", "numbers": [], "degraded": []}


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "sma"
    shutil.copytree(MOCK_DATA, root)
    plan = json.loads((root / "microscope_agent/questions" / QID / PLAN_FILE).read_text("utf-8"))
    appr = root / "microscope_agent" / "approvals"
    appr.mkdir()
    good = approval(QID, 1, plan_hash(plan), "2026-09-25T10:00:00Z")
    stale = approval(QID, 2, "sha256:" + "0" * 64, "2026-09-26T10:00:00Z")
    orphan = approval("mic-20990101-001", 1, "sha256:" + "1" * 64, "2026-09-24T10:00:00Z")
    # the first with a byte-order mark, as soft-matter-agents' Windows-written approvals have
    (appr / f"appr-{QID}-r1.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(good).encode())
    (appr / f"appr-{QID}-r2.json").write_text(json.dumps(stale), encoding="utf-8")
    (appr / "appr-mic-20990101-001-r1.json").write_text(json.dumps(orphan), encoding="utf-8")
    (appr / "notes.txt").write_text("not a card", encoding="utf-8")
    return root, plan


def test_plan_hash_is_soft_matter_agents_card_sha():
    card = {"status": "PROPOSED", "b": [1, 2], "a": "é"}
    blob = json.dumps({"a": "é", "b": [1, 2]}, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()
    assert plan_hash(card) == "sha256:" + hashlib.sha256(blob).hexdigest()
    assert plan_hash({**card, "status": "APPROVED"}) == plan_hash(card)  # status moves; hash not


def test_approvals_listed_newest_first_and_checked_against_the_plans(tree):
    root, plan = tree
    got = SmaFiles(root).list_approvals("microscope")
    assert [a.name for a in got] == [f"appr-{QID}-r2.json", f"appr-{QID}-r1.json",
                                     "appr-mic-20990101-001-r1.json"]
    by = {a.revision if a.qid == QID else "orphan": a for a in got}
    assert by[1].plan_found is True and by[1].plan_hash == plan_hash(plan)
    assert by[1].approved_by == "kyuhwan" and by[1].status == "APPROVED"
    assert by[1].data["card"] == "plan_approval"  # the BOM did not make it unreadable
    assert by[2].plan_found is False  # signs a plan that is not on disk
    assert by["orphan"].plan_found is None  # no such question folder
    assert SmaFiles(root).list_approvals("simulation") == []


def test_question_detail_carries_its_plan_hash_and_approvals(tree):
    root, plan = tree
    d = SmaFiles(root).get_question(QID)
    assert d.plan_hash == plan_hash(plan)
    assert {a.revision for a in d.approvals} == {1, 2}
    again = type(d).from_dict(json.loads(json.dumps(d.to_dict())))
    assert again.plan_hash == d.plan_hash and [a.name for a in again.approvals] == \
        [a.name for a in d.approvals]


def test_reading_approvals_writes_nothing(tree):
    root, _ = tree
    before = snapshot(root)
    s = SmaFiles(root)
    s.list_approvals("microscope")
    s.get_question(QID)
    assert snapshot(root) == before


def test_mock_store_has_no_approvals(tmp_path):
    assert MockStore(tmp_path / "w").list_approvals("microscope") == []
