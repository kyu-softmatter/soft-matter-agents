"""The example drawing the sample shows until a recorded order arrives (console card 025, part 1, 2 and 5): the server side.

The example is one file in the sample, `mock_data/console/example/light_path.json`. It is not an order: it carries no entry,
no grade and no read-back, so it is offered beside `path.order` and never inside it, and only when the store is the
sample and the order's state is `none`. The page's words come in the web tests; this side says where the file is read
from, when it is given, and what the file may not hold.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from test_instruments import (  # noqa: F401  -- the fixtures of the Instruments tests, shared
    LATEST,
    client,
    idle,
    runs,
    tree,
    write_status,
)
from test_light_path_order import NOT_IN, READ, REFUSED

from sma_console.agents import MockStore, SmaFiles
from sma_console.agents.mock_store import MOCK_DATA

CONSOLE = Path(__file__).resolve().parents[2]
EXAMPLE_FILE = MOCK_DATA / "console" / "example" / "light_path.json"
FORBIDDEN_KEYS = ("entry_ref", "grade", "source", "source_kind", "read_back", "channel")


def load() -> dict:
    return json.loads(EXAMPLE_FILE.read_text(encoding="utf-8"))


class StatusMock(MockStore):
    """The sample with a runtime folder that holds a status file: how a source gives an order of each state."""

    def __init__(self, root: Path, write_dir: Path):
        super().__init__(write_dir)
        self._root = root

    def runtime_root(self) -> Path | None:
        return self._root


def walk(node, path=()):
    """Every (path, value) in the document, containers included."""
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, (*path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, (*path, i))


# -- the file ------------------------------------------------------------------------------------------------


def test_the_file_is_marked_as_an_example_and_nothing_else_is_its_status():
    assert load()["status"] == "EXAMPLE"


def test_the_file_has_branches_of_elements_each_with_a_label_a_kind_of_control_and_a_setting():
    doc = load()
    assert doc["branches"], "no branch is drawn"
    for b in doc["branches"]:
        assert b["elements"], b
        for e in b["elements"]:
            assert isinstance(e["label"], str) and e["label"], e
            assert isinstance(e["control"], str) and e["control"], e
            assert isinstance(e["setting"], str) and e["setting"], e


def test_every_element_id_begins_with_example_and_none_repeats():
    ids = [e["id"] for b in load()["branches"] for e in b["elements"]]
    assert ids and all(i.startswith("example_") for i in ids), ids
    assert len(ids) == len(set(ids))


def test_no_number_stands_anywhere_in_the_file_as_a_json_number_or_as_a_digit_in_a_string():
    for path, v in walk(load()):
        assert not isinstance(v, (int, float)), (path, v)  # a bool is an int here, and no flag stands in it either
        if isinstance(v, str):
            assert not re.search(r"\d", v), (path, v)
        for part in path:
            assert not (isinstance(part, str) and re.search(r"\d", part)), path


@pytest.mark.parametrize("key", FORBIDDEN_KEYS)
def test_the_file_holds_none_of_the_keys_an_order_or_a_reading_has(key):
    for path, _ in walk(load()):
        assert key not in path, path


def test_the_file_is_not_under_the_samples_runtime_folder():
    assert "microscope_runtime" not in EXAMPLE_FILE.relative_to(MOCK_DATA).parts


def test_source_md_names_the_file_as_written_for_the_screen_and_not_copied():
    text = (MOCK_DATA / "SOURCE.md").read_text(encoding="utf-8")
    assert "console/example/light_path.json" in text
    section = text[text.index("console/example/light_path.json"):]
    assert "not copied" in section.lower() and "this microscope's" in section.lower()


# -- the store and the payload -------------------------------------------------------------------------------


def test_the_mock_store_returns_the_file_and_the_other_stores_return_nothing_for_it():
    assert MockStore().example_path() == load()
    assert not hasattr(SmaFiles, "example_path")


def test_the_sample_with_its_recorded_runs_gives_the_example_beside_the_order_and_not_inside_it(engine, make_client, tmp_path):
    got = make_client(engine, agent_store=MockStore(tmp_path / "p")).get(LATEST).json()
    assert got["path"]["order"]["state"] == "none"
    assert got["path"]["example"] == load()
    assert "example" not in got["path"]["order"] and got["path"]["order"]["data"] is None


@pytest.mark.parametrize(("order", "state"), [(READ, "read"), (NOT_IN, "not_in_snapshot"), (REFUSED[0], "not_understood")])
def test_a_source_that_gives_an_order_of_any_state_gives_no_example(engine, make_client, tmp_path, tree, order, state):
    root = tree  # the tree holds the schemas the status file and its order are judged by
    write_status(root, idle(light_path_order=order))
    got = make_client(engine, agent_store=StatusMock(root, tmp_path / "p")).get(LATEST).json()
    assert got["path"]["order"]["state"] == state
    assert got["path"]["example"] is None


def test_a_status_file_with_no_order_still_gives_the_example_on_the_sample(engine, make_client, tmp_path, tree):
    root = tree
    write_status(root, idle())
    got = make_client(engine, agent_store=StatusMock(root, tmp_path / "p")).get(LATEST).json()
    assert got["path"]["order"]["state"] == "none" and got["path"]["example"] == load()


def test_the_example_is_not_read_from_the_runtime_folder(engine, make_client, tmp_path, tree):
    root = tree
    write_status(root, idle())
    other = root / "console" / "example"
    other.mkdir(parents=True)
    (other / "light_path.json").write_text(json.dumps({"status": "EXAMPLE", "branches": []}), encoding="utf-8")
    got = make_client(engine, agent_store=StatusMock(root, tmp_path / "p")).get(LATEST).json()
    assert got["path"]["example"] == load()


def test_a_real_tree_gives_null_even_with_a_file_at_the_same_relative_path(client, tree, runs):
    runs("run-20261026-001")
    folder = tree / "console" / "example"
    folder.mkdir(parents=True)
    (folder / "light_path.json").write_text(json.dumps(load()), encoding="utf-8")
    got = client().get(LATEST).json()
    assert got["path"]["order"]["state"] == "none"
    assert got["path"]["example"] is None


def test_a_real_tree_with_no_run_gives_null(client, tree):
    got = client().get(LATEST).json()
    assert got["path"]["example"] is None


# -- nowhere else --------------------------------------------------------------------------------------------


def _scanned():
    roots = [CONSOLE / "src", CONSOLE / "web" / "src"]
    for root in roots:
        for p in root.rglob("*"):
            if not p.is_file() or "node_modules" in p.parts or "__pycache__" in p.parts:
                continue
            if MOCK_DATA in p.parents:
                continue
            if root.name == "src" and root.parent.name == "web" and re.search(r"\.test\.tsx?$", p.name):
                continue
            if p.suffix in {".ts", ".tsx", ".py", ".css", ".json", ".md", ".html"}:
                yield p


def test_no_file_outside_the_sample_names_an_example_id_or_label():
    names = [e[k] for b in load()["branches"] for e in b["elements"] for k in ("id", "label")]
    assert names
    hits = []
    for p in _scanned():
        text = p.read_text(encoding="utf-8", errors="replace")
        hits += [(p.relative_to(CONSOLE).as_posix(), n) for n in names if n in text]
    assert hits == []
