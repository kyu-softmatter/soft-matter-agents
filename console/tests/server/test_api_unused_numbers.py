"""Console card 021: `GET /api/console/questions/{qid}` carries the numbers the plan lists and nothing uses,
in the three states the sign dialog tells apart. The list is read-only information: no route reads it back."""

from __future__ import annotations

import json
import shutil

import pytest

from sma_console.agents import SmaFiles
from sma_console.agents.mock_store import MOCK_DATA
from sma_console.agents.sma_files import plan_hash

QID = "mic-20260925-002"
NO_PLAN_QID = "mic-20260925-001"


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "sma"
    shutil.copytree(MOCK_DATA, root)
    return root


def _plan_path(root):
    return root / "microscope_agent/questions" / QID / f"plan_microscope_{QID}.json"


def _detail(engine, make_client, root, qid=QID):
    return make_client(engine, agent_store=SmaFiles(root)).get(f"/api/console/questions/{qid}").json()


def test_the_mocks_plan_lists_its_number_with_from_as_the_card_places_it(engine, make_client):
    d = make_client(engine).get(f"/api/console/questions/{QID}").json()
    assert d["unused_numbers"] == {
        "worked_out": True, "reason": None,
        "numbers": [{"name": "nosepiece_position", "value": 5, "unit": "count", "from": "numbers[0]"}]}


def test_the_key_on_the_wire_is_from_and_not_from_underscore(engine, make_client, root):
    d = _detail(engine, make_client, root)
    assert set(d["unused_numbers"]["numbers"][0]) == {"name", "value", "unit", "from"}


def test_a_plan_card_with_nothing_unused_gives_an_empty_list_not_no_list(engine, make_client, root):
    plan = json.loads(_plan_path(root).read_text("utf-8"))
    plan["numbers"] = []
    _plan_path(root).write_text(json.dumps(plan), encoding="utf-8")
    d = _detail(engine, make_client, root)
    assert d["unused_numbers"] == {"worked_out": True, "numbers": [], "reason": None}


def test_a_question_without_a_plan_has_none(engine, make_client, root):
    d = _detail(engine, make_client, root, NO_PLAN_QID)
    assert d["plan"] is None and d["plan_hash"] is None and d["unused_numbers"] is None


def test_a_plan_the_rule_cannot_read_answers_200_with_the_reason(engine, make_client, root):
    plan = json.loads(_plan_path(root).read_text("utf-8"))
    plan["actions"] = [3]
    _plan_path(root).write_text(json.dumps(plan), encoding="utf-8")
    c = make_client(engine, agent_store=SmaFiles(root))
    r = c.get(f"/api/console/questions/{QID}")
    assert r.status_code == 200
    d = r.json()
    assert d["plan_hash"] == plan_hash(plan)
    assert d["unused_numbers"]["worked_out"] is False and d["unused_numbers"]["numbers"] == []
    assert d["unused_numbers"]["reason"]


def test_the_list_and_the_fingerprint_are_of_one_read(engine, make_client, root):
    plan = json.loads(_plan_path(root).read_text("utf-8"))
    plan["numbers"].append({"name": "bleach_window", "value": 4, "unit": "s", "source": "assumed:x", "grade": "E5"})
    _plan_path(root).write_text(json.dumps(plan), encoding="utf-8")
    d = _detail(engine, make_client, root)
    assert d["plan_hash"] == plan_hash(plan)
    assert [n["name"] for n in d["unused_numbers"]["numbers"]] == ["nosepiece_position", "bleach_window"]
    assert d["unused_numbers"]["numbers"][1]["from"] == "numbers[1]"
