"""The request forms' shapes (console card 016): what the web forms build is what the librarian's request schema takes.

`web/src/features/library/shapes.fixture.json` holds one case per shape. The web tests assert that the form builders
make exactly each case's request; this test asserts that each request, wrapped in a full inbox item, passes
`console_store_request.schema.json`, so the two cannot drift apart unnoticed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sma_console.agents.schema_lite import Schemas
from sma_console.agents.sma_files import repository_root

REPO = repository_root()
FIXTURE = Path(__file__).resolve().parents[2] / "web" / "src" / "features" / "library" / "shapes.fixture.json"
DOC = json.loads(FIXTURE.read_text(encoding="utf-8"))
SCHEMAS = Schemas(REPO / "contracts" / "schemas")
FORMS = {"add": "enter_document", "withdraw": "withdraw_value", "offer": "offer_result", "ask": "ask"}


def documents(x: Any) -> list[str]:
    """Every attached file name a request holds, at any depth."""
    if isinstance(x, dict):
        return [v for k, v in x.items() if k == "document" and isinstance(v, str)] + [d for v in x.values() for d in documents(v)]
    if isinstance(x, list):
        return [d for v in x for d in documents(v)]
    return []


def item(case: dict[str, Any], **over: Any) -> dict[str, Any]:
    out = {
        "schema_version": "0.1", "item_id": DOC["item_id"], "words": case["name"],
        "asked_by": {"login": "kyuhwan", "console_role": {"may_ask": True, "may_draft": True, "agents": ["librarian"], "may_ask_model_run": False}},
        "asked_at": "2026-10-26T10:15:00Z", "asker_mark": {"kind": "other_login"},
        "attachments": [{"file": d, "sha256": "ab" * 32} for d in documents(case["request"])],
        "artifact": "console_store_request", "request": case["request"],
    }
    return {**out, **over}


def test_the_fixture_covers_every_request_kind_the_forms_make():
    assert {c["request"]["kind"] for c in DOC["cases"]} == set(FORMS.values())
    assert {c["form"] for c in DOC["cases"]} == set(FORMS)


@pytest.mark.parametrize("case", DOC["cases"], ids=lambda c: c["name"])
def test_each_shape_passes_the_librarians_request_schema(case):
    assert case["request"]["kind"] == FORMS[case["form"]]
    assert SCHEMAS.validate(item(case), "console_store_request.schema.json") == []


@pytest.mark.parametrize("case", DOC["cases"], ids=lambda c: c["name"])
def test_each_attached_file_is_named_as_the_inbox_names_it(case):
    for d in documents(case["request"]):
        assert d.startswith(DOC["item_id"] + "--")
        assert case["request"]["kind"] in ("enter_document", "withdraw_value")


def test_the_check_is_not_vacuous_a_spoiled_shape_fails():
    case = next(c for c in DOC["cases"] if c["name"] == "a remembered value")
    spoiled = {**case["request"], "document": f"{DOC['item_id']}--x.pdf"}  # a remembered value has no file
    assert SCHEMAS.validate(item({**case, "request": spoiled}), "console_store_request.schema.json") != []
    no_unit = {**case["request"], "value": {"value": 0.75}}
    assert SCHEMAS.validate(item({**case, "request": no_unit}), "console_store_request.schema.json") != []
