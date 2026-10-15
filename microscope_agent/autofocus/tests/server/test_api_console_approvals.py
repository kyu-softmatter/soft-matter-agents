"""C-03: `GET /api/console/approvals`, the plan hash and approvals on a question, and
`--store sma --sma-root` choosing the soft-matter-agents files (read only)."""

from __future__ import annotations

import json
import shutil

import pytest

from dino_autofocus.agents import SmaFiles
from dino_autofocus.agents.mock_store import MOCK_DATA
from dino_autofocus.agents.sma_files import plan_hash
from dino_autofocus.server.__main__ import agent_store_of, parse_args

QID = "mic-20260925-002"


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "sma"
    shutil.copytree(MOCK_DATA, root)
    plan = json.loads((root / "microscope_agent/questions" / QID /
                       f"plan_microscope_{QID}.json").read_text("utf-8"))
    (root / "microscope_agent" / "approvals").mkdir()
    card = {"card": "plan_approval", "id": f"appr-{QID}-r1", "qid": QID, "revision": 1,
            "status": "APPROVED", "plan_id": plan.get("id"), "plan_revision": 1,
            "plan_hash": plan_hash(plan), "approved_by": "kyuhwan",
            "approved_at": "2026-09-25T10:00:00Z", "note": ""}
    (root / "microscope_agent/approvals" / f"appr-{QID}-r1.json").write_bytes(
        b"\xef\xbb\xbf" + json.dumps(card).encode())
    return root


def test_approvals_route_and_question_detail(engine, make_client, root):
    c = make_client(engine, agent_store=SmaFiles(root))
    got = c.get("/api/console/approvals").json()
    assert [a["name"] for a in got] == [f"appr-{QID}-r1.json"]
    assert got[0]["plan_found"] is True and got[0]["agent"] == "microscope"
    assert c.get("/api/console/approvals", params={"agent": "simulation"}).json() == []
    d = c.get(f"/api/console/questions/{QID}").json()
    assert d["plan_hash"] == got[0]["plan_hash"]
    assert [a["id"] for a in d["approvals"]] == [f"appr-{QID}-r1"]


def test_mock_store_answers_no_approvals(engine, make_client):
    assert make_client(engine).get("/api/console/approvals").json() == []


def test_store_flag(tmp_path, root, monkeypatch):
    assert agent_store_of(parse_args([])) is None  # create_app's own MockStore
    s = agent_store_of(parse_args(["--store", "sma", "--sma-root", str(root)]))
    assert isinstance(s, SmaFiles) and s.root == root and not s.writable
    monkeypatch.setenv("DINO_AF_SMA_ROOT", str(root))
    assert agent_store_of(parse_args(["--store", "sma"])).root == root
    with pytest.raises(SystemExit, match="no microscope_agent"):
        agent_store_of(parse_args(["--store", "sma", "--sma-root", str(tmp_path / "empty")]))
