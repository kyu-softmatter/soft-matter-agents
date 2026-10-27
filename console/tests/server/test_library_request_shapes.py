"""The request forms' shapes (console cards 016 and 020): what the web forms build is what the server delivers.

`web/src/features/library/shapes.fixture.json` holds one case per shape: the form's input, the words and the
request the form builds, and the file it names. The web tests assert that the form builders make exactly each
case's words and request. This test hands each case to the server's own writer, into a `tmp_path` inbox, and
checks the item that lands against `console_store_request.schema.json` (with the real `jsonschema` when it is
installed, and with the console's own checker always), so the two cannot drift apart unnoticed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sma_console.agents import store_requests
from sma_console.agents.schema_lite import Schemas
from sma_console.agents.sma_files import repository_root

REPO = repository_root()
SCHEMA_FOLDER = REPO / "contracts" / "schemas"
FIXTURE = Path(__file__).resolve().parents[2] / "web" / "src" / "features" / "library" / "shapes.fixture.json"
DOC = json.loads(FIXTURE.read_text(encoding="utf-8"))
SCHEMAS = Schemas(SCHEMA_FOLDER)
ITEM_SCHEMA = "console_store_request.schema.json"
FORMS = {"add": "enter_document", "withdraw": "withdraw_value", "offer": "offer_result", "ask": "ask"}
WORDS_FIELD = {"enter_document": "fact_wanted", "withdraw_value": "reason", "offer_result": "fact_in_words", "ask": "question"}
CASES = DOC["cases"]


def deliver(case: dict[str, Any], tmp_path: Path) -> tuple[dict[str, Any], Path]:
    inbox, outgoing = tmp_path / "console_inbox", tmp_path / "outgoing"
    inbox.mkdir()
    outgoing.mkdir()
    attached = store_requests.Attached(case["file"], b"%PDF-1.4 a file") if case.get("file") else None
    item = store_requests.deliver(
        words=case["words"], request=case["request"], attached=attached, login="kyuhwan", role="operator",
        inbox=inbox, outgoing=outgoing, schemas=SCHEMAS)
    assert list(outgoing.iterdir()) == []
    return item, inbox


def test_the_fixture_covers_every_request_kind_the_forms_make():
    assert {c["request"]["kind"] for c in CASES} == set(FORMS.values())
    assert {c["form"] for c in CASES} == set(FORMS)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_each_shape_leaves_out_the_field_the_words_fill(case):
    assert case["request"]["kind"] == FORMS[case["form"]]
    assert WORDS_FIELD[case["request"]["kind"]] not in case["request"]
    assert case["words"].strip() != ""


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_each_shape_is_delivered_and_the_item_passes_the_librarians_request_schema(case, tmp_path):
    item, inbox = deliver(case, tmp_path)
    assert SCHEMAS.validate(item, ITEM_SCHEMA) == []
    on_disk = json.loads((inbox / f"{item['item_id']}.json").read_bytes().decode("utf-8"))
    assert on_disk == item
    assert on_disk["request"][WORDS_FIELD[on_disk["request"]["kind"]]] == case["words"].strip()
    assert on_disk["words"] == case["words"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_each_item_passes_the_real_jsonschema_when_it_is_installed(case, tmp_path):
    jsonschema = pytest.importorskip("jsonschema")
    item, _ = deliver(case, tmp_path)
    from referencing import Registry, Resource  # installed with jsonschema

    store = {}
    for p in SCHEMA_FOLDER.glob("*.schema.json"):
        s = json.loads(p.read_text(encoding="utf-8"))
        store[s.get("$id", p.name)] = s
        store[p.name] = s
    registry = Registry().with_resources((k, Resource.from_contents(v)) for k, v in store.items())
    jsonschema.Draft202012Validator(store[ITEM_SCHEMA], registry=registry).validate(item)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_each_attached_file_is_written_under_the_item_id_and_named_as_the_inbox_names_it(case, tmp_path):
    item, inbox = deliver(case, tmp_path)
    if not case.get("file"):
        assert item["attachments"] == []
        assert sorted(p.name for p in inbox.iterdir()) == [f"{item['item_id']}.json"]
        return
    kept = f"{item['item_id']}--{case['file']}"
    assert [a["file"] for a in item["attachments"]] == [kept]
    assert sorted(p.name for p in inbox.iterdir()) == sorted([f"{item['item_id']}.json", kept])
    holder = item["request"] if "document" in item["request"] else item["request"]["evidence"]
    assert holder["document"] == kept
    assert case["request"]["kind"] in ("enter_document", "withdraw_value")


def test_a_request_that_already_carries_the_words_field_is_refused(tmp_path):
    case = next(c for c in CASES if c["form"] == "ask")
    spoiled = {**case, "request": {**case["request"], "question": "typed twice"}}
    with pytest.raises(store_requests.RequestError):
        deliver(spoiled, tmp_path)
    assert list((tmp_path / "console_inbox").iterdir()) == []


def test_the_check_is_not_vacuous_a_spoiled_shape_fails():
    case = next(c for c in CASES if c["name"] == "a remembered value")
    base = {
        "artifact": "console_store_request", "schema_version": "0.1", "item_id": "ci-20261026-101500-abcd",
        "words": case["words"],
        "asked_by": {"login": "kyuhwan", "console_role": {"may_ask": True, "may_draft": True,
                                                          "agents": ["librarian"], "may_ask_model_run": False}},
        "asked_at": "2026-10-26T10:15:00Z", "asker_mark": {"kind": "other_login"}, "attachments": [],
        "request": {**case["request"], WORDS_FIELD[case["request"]["kind"]]: case["words"]},
    }
    assert SCHEMAS.validate(base, ITEM_SCHEMA) == []
    spoiled = {**base, "request": {**base["request"], "document": "ci-20261026-101500-abcd--x.pdf"}}  # a remembered value has no file
    assert SCHEMAS.validate(spoiled, ITEM_SCHEMA) != []
    no_unit = {**base, "request": {**base["request"], "value": {"value": 0.75}}}
    assert SCHEMAS.validate(no_unit, ITEM_SCHEMA) != []
