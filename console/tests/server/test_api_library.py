"""The library screen's server side (console card 016): the librarian's generated pages, shown and nothing else.

Four GET routes and no write. The pages, the data map and the version come from `librarian_agent/kb/` of the tree
the store reads; the answers list is the mock store's example answers, or "No answers yet." from a real tree,
whatever lies in a real tree's `librarian_agent/answers/` (the console shows no answers from the real store
until the librarian's inbox is open).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from server_fakes import VIEWER
from sma_fake_run import sma_tree

from sma_console.agents import MockStore, SmaFiles
from sma_console.agents.mock_store import MOCK_DATA
from sma_console.agents.schema_lite import Schemas
from sma_console.agents.sma_files import repository_root
from sma_console.server.api import REFUSAL_HEADER

REPO = repository_root()
INDEX, MAP, ANSWERS = ("/api/library/" + p for p in ("index", "map", "answers"))
SEVEN = {"entered", "waiting_for_a_name", "refuted", "in_conflict", "superseded", "kept", "no_entry_of_that_name"}
V = "kbv-0123456789ab"


def footer(v: str = V) -> str:
    return f"Generated from the knowledge store at {v}. Do not edit by hand: correct the store and regenerate."


@pytest.fixture
def tree(tmp_path):
    root = sma_tree(tmp_path / "sma")
    kb = root / "librarian_agent" / "kb"
    (kb / "wiki").mkdir(parents=True)
    (kb / "index.json").write_text(json.dumps({"kb_version": V}), encoding="utf-8")
    (kb / "wiki" / "index.md").write_text(
        f"# The knowledge store\n\n## Device pages\n\n- [dia_lamp](../wiki/device_dia_lamp.md) (1 entries)\n\n---\n\n{footer()}\n",
        encoding="utf-8")
    (kb / "wiki" / "device_dia_lamp.md").write_text(
        f"# Device: dia_lamp\n\nSee [entry](../entries/x.json).\n\n---\n\n{footer()}\n", encoding="utf-8")
    return root


@pytest.fixture
def client(engine, make_client, tree):
    return lambda **kw: make_client(engine, agent_store=SmaFiles(tree, source="soft-matter-agents"), **kw)


@pytest.fixture
def mock_client(engine, make_client, tmp_path):
    return lambda **kw: make_client(engine, agent_store=MockStore(tmp_path / "practice"), **kw)


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


# -- the routes -------------------------------------------------------------------------------------------


def test_the_index_comes_from_the_tree_the_store_reads(client):
    got = client().get(INDEX).json()
    assert got["state"] == "shown" and got["groups"][0]["links"][0]["page"] == "device_dia_lamp"
    assert got["example"] is False and got["example_note"] is None


def test_a_page_comes_with_its_version_notes(client):
    got = client().get("/api/library/pages/device_dia_lamp").json()
    assert got["title"] == "Device: dia_lamp" and got["behind"] is False
    spans = [s for b in got["blocks"] if b["type"] == "paragraph" for s in b["spans"]]
    assert [s["page"] for s in spans] == [None, None, None]  # the entry link is text and nothing more


def test_a_page_built_from_an_older_version_says_so_over_the_wire(client, tree):
    (tree / "librarian_agent" / "kb" / "index.json").write_text(json.dumps({"kb_version": "kbv-ba9876543210"}),
                                                                 encoding="utf-8")
    got = client().get("/api/library/pages/device_dia_lamp").json()
    assert got["behind"] is True and "older version of the store" in got["note"]


def test_a_page_that_is_not_there_is_404_and_a_name_that_is_not_a_name_is_404_too(client):
    c = client()
    assert c.get("/api/library/pages/device_camera_blue").status_code == 404
    for bad in ("entries", "..%2Findex", "answers", "device_x%2F..%2F..%2Findex", "map.json", "INDEX"):
        r = c.get(f"/api/library/pages/{bad}")
        assert r.status_code in (404, 422), (bad, r.status_code)
        assert "secret" not in r.text


def test_the_map_is_not_built_until_the_librarian_has_built_it(client):
    got = client().get(MAP).json()
    assert got["state"] == "not_built" and "not built yet" in got["message"].lower()


def test_a_built_map_comes_as_counts(client, tree):
    doc = {"artifact": "kb_map", "schema_version": "0.1", "kb_version": V, "footer": footer(),
           "nodes": [{"id": "page:device_dia_lamp", "kind": "device", "page": "device_dia_lamp.md",
                      "coverage": {"E1": 1, "E2": 0, "E3": 0, "E4": 0, "E5": 0}, "disputed": 0}],
           "edges": [{"type": "supports", "from": "entry:a", "to": "entry:b", "stated_by": "entry:a"}],
           "dangling": []}
    (tree / "librarian_agent" / "kb" / "wiki" / "map.json").write_text(json.dumps(doc), encoding="utf-8")
    got = client().get(MAP).json()
    assert got["state"] == "built"
    assert got["subjects"] == [{"id": "page:device_dia_lamp", "kind": "device", "page": "device_dia_lamp",
                                "coverage": {"E1": 1, "E2": 0, "E3": 0, "E4": 0, "E5": 0}, "disputed": 0}]
    assert got["relations"] == [{"type": "supports", "from": "entry:a", "to": "entry:b", "stated_by": "entry:a"}]


def test_a_remote_viewer_may_read_the_library(engine, make_client, tree):
    c = make_client(engine, agent_store=SmaFiles(tree, source="soft-matter-agents"), remote=True, login=VIEWER)
    assert c.get(INDEX).status_code == 200


def test_nothing_of_the_library_works_without_a_login(engine, make_client, tree):
    c = make_client(engine, agent_store=SmaFiles(tree, source="soft-matter-agents"), login=None)
    for path in (INDEX, MAP, ANSWERS, "/api/library/pages/index"):
        r = c.get(path)
        assert r.status_code == 401 and r.headers[REFUSAL_HEADER] == "login_required", path


def test_there_is_no_write_route_under_the_library(client):
    c = client()
    for path in (INDEX, MAP, ANSWERS, "/api/library/pages/index", "/api/library/send", "/api/library/request"):
        for method in ("post", "put", "patch", "delete"):
            assert getattr(c, method)(path).status_code in (404, 405), (method, path)


def test_reading_the_library_changes_no_byte_of_the_tree(client, tree):
    before = tree_bytes(tree)
    c = client()
    for path in (INDEX, MAP, ANSWERS, "/api/library/pages/index", "/api/library/pages/device_dia_lamp"):
        c.get(path)
    assert tree_bytes(tree) == before


# -- the answers list -------------------------------------------------------------------------------------


def test_the_real_store_has_no_answers_yet_even_when_the_folder_holds_some(client, tree):
    answers = tree / "librarian_agent" / "answers"
    answers.mkdir(parents=True)
    shutil.copy(next((MOCK_DATA / "librarian_agent" / "answers").glob("*.json")), answers)
    got = client().get(ANSWERS).json()
    assert got["answers"] == [] and got["message"] == "No answers yet."
    assert got["example"] is False and got["example_note"] is None


def test_the_mock_answers_cover_the_seven_outcomes_and_each_is_labelled_example(mock_client):
    got = mock_client().get(ANSWERS).json()
    assert got["example"] is True and "example data" in got["example_note"].lower()
    assert {a["outcome"] for a in got["answers"]} >= SEVEN
    assert {a["outcome"] for a in got["answers"]} == SEVEN | {"answered", "not_in_the_store"}
    assert got["message"] is None
    assert all(a["example"] is True for a in got["answers"])


def test_the_mock_answers_are_the_librarians_answers_as_the_schema_has_them():
    schemas = Schemas(REPO / "contracts" / "schemas")
    files = sorted((MOCK_DATA / "librarian_agent" / "answers").glob("*.json"))
    assert len(files) >= 9
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        assert schemas.validate(doc, "store_answer.schema.json") == [], f.name
        assert all(n["grade"] != "E6" for n in doc.get("numbers", [])), f.name


def test_every_number_in_an_answer_comes_with_its_entry_grade_and_source(mock_client):
    answered = [a for a in mock_client().get(ANSWERS).json()["answers"] if a["outcome"] == "answered"]
    assert answered and answered[0]["numbers"]
    for n in answered[0]["numbers"]:
        assert {"name", "value", "unit", "entry_id", "grade", "source", "covers_conditions"} <= set(n)
        assert n["covers_conditions"] in ("yes", "no", "not_stated")


def test_the_mock_library_is_the_shipped_sample_and_says_it_is_example_data(mock_client):
    got = mock_client().get(INDEX).json()
    assert got["example"] is True and "mock_data/SOURCE.md" in got["example_note"]
    assert mock_client().get("/api/library/pages/device_dia_lamp").json()["example"] is True


def test_a_tree_store_is_not_example_data_even_when_it_is_a_copy_of_the_mock(engine, make_client, tmp_path):
    root = tmp_path / "copy"
    shutil.copytree(MOCK_DATA, root)
    c = make_client(engine, agent_store=SmaFiles(root, source="soft-matter-agents"))
    assert c.get(INDEX).json()["example"] is False
    assert c.get(ANSWERS).json()["answers"] == []

def test_the_mock_answers_come_newest_first(mock_client):
    ids = [a["answer_id"] for a in mock_client().get(ANSWERS).json()["answers"]]
    assert len(ids) >= 9 and ids == sorted(ids, reverse=True)


def test_an_answer_from_a_real_tree_is_not_marked_example_data(engine, make_client, tree):
    docs = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((MOCK_DATA / "librarian_agent" / "answers").glob("*.json"))]

    class Serving(SmaFiles):
        def library_answers(self):
            return docs

    got = make_client(engine, agent_store=Serving(tree, source="soft-matter-agents")).get(ANSWERS).json()
    assert len(got["answers"]) == len(docs) and got["example"] is False and got["example_note"] is None
    assert all(a["example"] is False for a in got["answers"])
