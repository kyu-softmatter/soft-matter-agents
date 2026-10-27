"""A question to the microscope or the simulation reaches that agent's inbox (console card 019, plan.md 7.1.1).

An item is `contracts/schemas/console_inbox_item.schema.json`'s `console_question`, written once and whole
into `<tree>/<agent>_agent/console_inbox/<item_id>.json`, and never rewritten. There are three addressees;
anything else is refused and nothing is written (card 022). A request an earlier console left in its own
folder is still read, marked not delivered. Every test here runs in a `tmp_path` tree.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from server_fakes import OPERATOR, VIEWER

from sma_console.agents import MockStore, SmaFiles
from sma_console.agents.mock_store import MOCK_DATA
from sma_console.agents.schema_lite import Schemas
from sma_console.agents.sma_files import repository_root
from sma_console.server.api import REFUSAL_HEADER

REPO = repository_root()
SCHEMAS = REPO / "contracts" / "schemas"
POST = "/api/console/question-requests"
CARDS = "/api/console/question-cards"
NOW = datetime(2026, 10, 26, 17, 45, 12, tzinfo=UTC)
FULL = "This agent has had 999 questions from the console today, which is the most a day can hold. Ask again after midnight UTC."
NO_INBOX = "This agent's inbox is not there, so nothing was sent."
NOT_DELIVERED = "written in the console · not delivered"
UNREADABLE = "an answer is on disk and cannot be read"


def inbox_items_module():
    import importlib

    return importlib.import_module("sma_console.agents.inbox_items")


def tree_hash(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def refusal(r) -> tuple[int, str]:
    assert r.headers[REFUSAL_HEADER] == r.json()["detail"]["code"]
    return r.status_code, r.json()["detail"]["code"]


def inbox_of(root: Path, agent: str) -> Path:
    return root / f"{agent}_agent" / "console_inbox"


def answers_of(root: Path, agent: str) -> Path:
    return root / f"{agent}_agent" / "answers"


def outgoing_of(root: Path) -> Path:
    return root / "console" / "requests" / "outgoing"


def entries(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def items(root: Path, agent: str) -> list[Path]:
    return sorted(inbox_of(root, agent).glob("ci-*.json"))


@pytest.fixture
def tree(tmp_path):
    """A soft-matter-agents tree: the sample's agents, the contracts' two inbox schemas and an inbox folder
    for each executing agent, empty but for its `.gitkeep`."""
    root = tmp_path / "sma"
    shutil.copytree(MOCK_DATA, root)
    shutil.rmtree(root / "console")
    shutil.rmtree(root / "microscope_runtime")
    (root / "contracts" / "schemas").mkdir(parents=True)
    for name in ("console_inbox_item.schema.json", "console_answer.schema.json",
                 "console_store_request.schema.json", "store_answer.schema.json"):
        shutil.copy(SCHEMAS / name, root / "contracts" / "schemas" / name)
    (root / "contracts" / "quantities.json").write_text(json.dumps({"quantities": []}), encoding="utf-8")
    shutil.rmtree(root / "librarian_agent" / "console_inbox", ignore_errors=True)  # the sample's examples
    shutil.rmtree(root / "librarian_agent" / "answers", ignore_errors=True)
    for agent in ("microscope", "simulation", "librarian"):
        inbox_of(root, agent).mkdir(parents=True)
        (inbox_of(root, agent) / ".gitkeep").write_bytes(b"")
    return root


@pytest.fixture
def client(engine, make_client, tree):
    return lambda **kw: make_client(engine, agent_store=SmaFiles(tree, source="soft-matter-agents"), **kw)


@pytest.fixture
def clock(monkeypatch):
    """Fix the module's clock and its four random characters; the test moves them."""
    M = inbox_items_module()
    state = {"now": NOW, "suffixes": iter(f"{c}{c}{c}{c}" for c in "abcdefghijklmnopqrstuvwxyz")}
    monkeypatch.setattr(M, "utc_now", lambda: state["now"])
    monkeypatch.setattr(M, "random_suffix", lambda: next(state["suffixes"]))
    return state


def ask(c, agent, words="Does the gel flow more easily after it rests?"):
    return c.post(POST, json={"words": words, "addressed_to": agent})


def check_item(doc: dict) -> list[str]:
    return Schemas(SCHEMAS).validate(doc, "console_inbox_item.schema.json")


def an_item(agent="microscope", question_id=None, item_id="ci-20261026-090000-aaaa", words="old words",
            asked_at="2026-10-26T09:00:00Z", login="member-1") -> dict:
    prefix = "mic" if agent == "microscope" else "sim"
    return {
        "artifact": "console_question", "schema_version": "0.1", "item_id": item_id,
        "question_id": question_id or f"{prefix}-20261026-c001", "words": words,
        "asked_by": {"login": login, "console_role": {
            "may_ask": True, "may_draft": True, "agents": [agent], "may_ask_model_run": False}},
        "asked_at": asked_at, "asker_mark": {"kind": "other_login"}, "attachments": []}


def put_item(root: Path, agent: str, **kw) -> dict:
    doc = an_item(agent, **kw)
    assert check_item(doc) == []
    (inbox_of(root, agent) / f"{doc['item_id']}.json").write_text(json.dumps(doc), encoding="utf-8")
    return doc


def put_answer(root: Path, agent: str, item: dict, name=None, **kw) -> dict:
    doc = {"artifact": "console_answer", "schema_version": "0.1", "answer_id": "ca-20261026-120000-aaaa",
           "item_id": item["item_id"], "question_id": item["question_id"], "outcome": "refused",
           "reason": "the microscope cannot plan this yet", "answered_at": "2026-10-26T12:00:00Z",
           "answered_by": f"{agent}-office-20261015-1", **kw}
    folder = answers_of(root, agent)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (name or f"{doc['answer_id']}.json")).write_text(json.dumps(doc), encoding="utf-8")
    return doc


# -- an item for each agent, in the schema's shape ---------------------------------------------------


@pytest.mark.parametrize("agent,prefix", [("microscope", "mic"), ("simulation", "sim")])
def test_an_item_is_written_into_the_agents_inbox_in_the_schemas_shape(client, tree, clock, agent, prefix):
    r = ask(client(), agent)
    assert r.status_code == 201, r.text
    files = items(tree, agent)
    assert len(files) == 1
    doc = json.loads(files[0].read_bytes().decode("utf-8"))
    assert check_item(doc) == []
    assert files[0].name == doc["item_id"] + ".json"
    assert re.fullmatch(r"ci-20261026-174512-[a-z0-9]{4}", doc["item_id"])
    assert doc["question_id"] == f"{prefix}-20261026-c001"
    assert doc["artifact"] == "console_question" and doc["asked_at"] == "2026-10-26T17:45:12Z"
    assert doc["asker_mark"] == {"kind": "other_login"} and doc["attachments"] == []
    assert doc["asked_by"]["login"] == OPERATOR
    assert doc["asked_by"]["console_role"] == {
        "may_ask": True, "may_draft": True, "agents": ["microscope", "simulation", "librarian"],
        "may_ask_model_run": True}
    assert set(doc) == {"artifact", "schema_version", "item_id", "question_id", "words", "asked_by",
                        "asked_at", "asker_mark", "attachments"}
    assert r.json() == doc  # what the screen is told is what was written
    data = files[0].read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf") and b"\r" not in data
    assert data.endswith(b"}\n") and not data.endswith(b"\n\n")
    other = "simulation" if agent == "microscope" else "microscope"
    assert items(tree, other) == []  # nothing in the other agent's inbox


def test_the_item_also_passes_the_repositorys_schema_under_jsonschema_when_it_is_there(client, tree, clock):
    jsonschema = pytest.importorskip("jsonschema")
    ask(client(), "microscope")
    doc = json.loads(items(tree, "microscope")[0].read_text("utf-8"))
    spec = json.loads((SCHEMAS / "console_inbox_item.schema.json").read_text("utf-8"))
    jsonschema.Draft202012Validator(spec).validate(doc)


def test_the_checker_the_console_uses_accepts_the_example_and_rejects_a_stray_key():
    example = json.loads((REPO / "contracts" / "examples" / "console_question.json").read_text("utf-8"))
    assert check_item(example) == []
    assert check_item({**example, "persons_own": True})
    assert check_item({**example, "question_id": "lib-20261024-c001"})


TYPED = "  Does the gel flow more easily\nafter it rests?  \n\n\"quoted\" μm — é\\  "


def test_the_words_are_byte_equal_to_what_was_typed(client, tree, clock):
    ask(client(), "simulation", TYPED)
    doc = json.loads(items(tree, "simulation")[0].read_bytes().decode("utf-8"))
    assert doc["words"].encode("utf-8") == TYPED.encode("utf-8") and doc["words"] != TYPED.strip()


# -- the question id: the next number of that UTC date, for each agent apart --------------------------


def test_the_question_numbers_run_from_c001_and_the_two_agents_count_apart(client, tree, clock):
    c = client()
    got = [ask(c, a).json()["question_id"] for a in ("microscope", "microscope", "simulation", "microscope", "simulation")]
    assert got == ["mic-20261026-c001", "mic-20261026-c002", "sim-20261026-c001", "mic-20261026-c003",
                   "sim-20261026-c002"]


def test_a_new_utc_date_starts_again_at_c001(client, tree, clock):
    c = client()
    assert ask(c, "microscope").json()["question_id"] == "mic-20261026-c001"
    assert ask(c, "microscope").json()["question_id"] == "mic-20261026-c002"
    clock["now"] = datetime(2026, 10, 27, 0, 0, 1, tzinfo=UTC)
    assert ask(c, "microscope").json()["question_id"] == "mic-20261027-c001"
    clock["now"] = NOW
    assert ask(c, "microscope").json()["question_id"] == "mic-20261026-c003"  # the earlier date goes on


def test_the_next_number_follows_the_highest_already_in_the_inbox(client, tree, clock):
    put_item(tree, "microscope", item_id="ci-20261026-080000-aaaa", question_id="mic-20261026-c005")
    put_item(tree, "microscope", item_id="ci-20261026-080001-bbbb", question_id="mic-20261026-c002")
    put_item(tree, "microscope", item_id="ci-20261025-080001-cccc", question_id="mic-20261025-c009")
    put_item(tree, "simulation", item_id="ci-20261026-080002-dddd", question_id="sim-20261026-c007")
    assert ask(client(), "microscope").json()["question_id"] == "mic-20261026-c006"


def test_the_thousandth_of_a_day_is_refused_and_writes_nothing(client, tree, clock):
    put_item(tree, "microscope", question_id="mic-20261026-c999")
    before = tree_hash(tree)
    r = ask(client(), "microscope")
    assert refusal(r) == (409, "inbox_full")
    assert r.json()["detail"]["message"] == FULL
    assert tree_hash(tree) == before
    assert entries(outgoing_of(tree)) == []
    assert ask(client(), "simulation").status_code == 201  # the other agent's day is its own


# -- the inbox folder is the agent's: the console never makes it -------------------------------------


def test_an_inbox_that_is_not_there_is_refused_and_not_made(client, tree, clock):
    shutil.rmtree(inbox_of(tree, "microscope"))
    before = tree_hash(tree)
    r = ask(client(), "microscope")
    assert refusal(r) == (409, "inbox_missing")
    assert r.json()["detail"]["message"] == NO_INBOX
    assert not inbox_of(tree, "microscope").exists()
    assert tree_hash(tree) == before
    assert entries(outgoing_of(tree)) == []


def test_an_inbox_that_is_a_file_is_refused(client, tree, clock):
    shutil.rmtree(inbox_of(tree, "simulation"))
    inbox_of(tree, "simulation").write_text("not a folder", encoding="utf-8")
    assert refusal(ask(client(), "simulation")) == (409, "inbox_missing")


# -- never rewritten, written whole ------------------------------------------------------------------


def test_a_taken_item_id_is_never_rewritten_and_the_second_lands_under_a_new_id(client, tree, clock, monkeypatch):
    M = inbox_items_module()
    suffixes = iter(["aaaa", "aaaa", "bbbb"])
    monkeypatch.setattr(M, "random_suffix", lambda: next(suffixes))
    c = client()
    first = ask(c, "microscope", "first").json()
    path = inbox_of(tree, "microscope") / (first["item_id"] + ".json")
    before = path.read_bytes()
    second = ask(c, "microscope", "second").json()
    assert (first["item_id"], second["item_id"]) == ("ci-20261026-174512-aaaa", "ci-20261026-174512-bbbb")
    assert path.read_bytes() == before
    assert (first["question_id"], second["question_id"]) == ("mic-20261026-c001", "mic-20261026-c002")
    assert entries(inbox_of(tree, "microscope")) == sorted([".gitkeep", first["item_id"] + ".json", second["item_id"] + ".json"])


def test_an_id_taken_five_times_is_refused_and_the_first_file_is_unchanged(client, tree, clock, monkeypatch):
    M = inbox_items_module()
    monkeypatch.setattr(M, "random_suffix", lambda: "aaaa")
    c = client()
    first = ask(c, "microscope", "first").json()
    path = inbox_of(tree, "microscope") / (first["item_id"] + ".json")
    before = path.read_bytes()
    r = ask(c, "microscope", "second")
    assert refusal(r) == (409, "item_exists")
    assert path.read_bytes() == before
    assert entries(inbox_of(tree, "microscope")) == sorted([".gitkeep", path.name])
    assert entries(outgoing_of(tree)) == []


def test_a_write_that_fails_between_the_temporary_file_and_the_link_leaves_nothing(client, tree, clock, monkeypatch):
    M = inbox_items_module()

    def broken(*a, **k):
        raise OSError("disk says no")

    monkeypatch.setattr(M.os, "link", broken)
    r = ask(client(), "microscope")
    assert r.status_code == 500
    assert entries(inbox_of(tree, "microscope")) == [".gitkeep"]
    assert entries(outgoing_of(tree)) == []


def test_the_inbox_holds_only_items_and_gitkeep_after_a_write(client, tree, clock):
    c = client()
    for agent in ("microscope", "simulation", "microscope"):
        ask(c, agent)
    for agent in ("microscope", "simulation"):
        assert all(n == ".gitkeep" or re.fullmatch(r"ci-\d{8}-\d{6}-[a-z0-9]{4}\.json", n)
                   for n in entries(inbox_of(tree, agent)))
    assert entries(outgoing_of(tree)) == []  # the temporary name is in the console's folder, and gone


def test_an_item_appears_whole_and_through_the_consoles_own_folder(client, tree, clock, monkeypatch):
    M = inbox_items_module()
    seen: list[tuple[Path, bytes]] = []
    real = M.os.link

    def link(src, dst, *a, **k):
        seen.append((Path(src), Path(src).read_bytes()))
        assert not Path(dst).exists()
        assert Path(dst).parent.name == "console_inbox"
        return real(src, dst, *a, **k)

    monkeypatch.setattr(M.os, "link", link)
    ask(client(), "simulation")
    assert len(seen) == 1
    src, data = seen[0]
    assert os.path.samefile(src.parent, outgoing_of(tree))
    assert check_item(json.loads(data)) == []


def test_the_writer_refuses_an_item_that_fails_the_schema_and_writes_nothing(client, tree, clock, monkeypatch):
    M = inbox_items_module()
    real = M.build_item

    def bad(**kw):
        return {**real(**kw), "persons_own": True}

    monkeypatch.setattr(M, "build_item", bad)
    before = tree_hash(tree)
    r = ask(client(), "microscope")
    assert r.status_code == 500 and refusal(r)[1] == "store_error"
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []


def test_a_schema_that_cannot_be_found_refuses_and_writes_nothing(client, tree, clock):
    (tree / "contracts" / "schemas" / "console_inbox_item.schema.json").unlink()
    before = tree_hash(tree)
    r = ask(client(), "microscope")
    assert r.status_code == 500
    assert tree_hash(tree) == before


# -- what does not deliver ---------------------------------------------------------------------------


@pytest.mark.parametrize("addressee", ["agents_decide", "everyone", "", "Microscope", "bridge"])
def test_an_addressee_that_is_not_one_of_three_is_refused_and_nothing_is_written(client, tree, clock, seat, addressee):
    c = client()  # logging in is itself an audit line; the baseline is taken after it
    before, lines = tree_hash(tree), len(list(seat.audit.entries()))
    r = ask(c, addressee)
    assert r.status_code == 422
    assert tree_hash(tree) == before  # no inbox, no part of the console's folder, nothing anywhere
    assert not (tree / "console").exists() and entries(outgoing_of(tree)) == []
    for agent in ("microscope", "simulation", "librarian"):
        assert entries(inbox_of(tree, agent)) == [".gitkeep"]
    assert len(list(seat.audit.entries())) == lines


def test_a_question_with_no_addressee_is_refused_the_same_way(client, tree, clock, seat):
    c = client()
    before, lines = tree_hash(tree), len(list(seat.audit.entries()))
    r = c.post(POST, json={"words": "no one is named"})
    assert r.status_code == 422
    assert tree_hash(tree) == before and not (tree / "console").exists()
    assert len(list(seat.audit.entries())) == lines


def test_the_refusal_of_an_addressee_says_it_is_not_one_of_three():
    from sma_console.server.api import console as route

    paths = route.router.routes
    post = next(p for p in paths if getattr(p, "path", "").endswith("/question-requests"))
    assert post.responses[422]["description"].endswith("an addressee that is not one of three")


def test_the_librarian_is_delivered_as_a_store_request_and_nothing_else_changes(client, tree, clock):
    before = tree_hash(tree)
    r = ask(client(), "librarian")
    assert r.status_code == 201
    item = r.json()
    assert item["kind"] == "ask" if "kind" in item else True
    new = set(tree_hash(tree)) - set(before)
    assert new == {f"librarian_agent/console_inbox/{item['item_id']}.json"}
    for agent in ("microscope", "simulation"):
        assert entries(inbox_of(tree, agent)) == [".gitkeep"]


def test_a_viewer_cannot_send_and_nothing_is_written(client, tree, clock):
    before = tree_hash(tree)
    for agent in ("microscope", "simulation"):
        assert refusal(ask(client(login=VIEWER), agent)) == (403, "role")
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []


@pytest.mark.parametrize("body", [
    {"words": "", "addressed_to": "microscope"},
    {"words": "   \n ", "addressed_to": "simulation"},
    {"words": "x" * 4001, "addressed_to": "microscope"},
    {"words": "q", "addressed_to": "microscope", "persons_own": True},
])
def test_a_bad_body_is_refused_and_writes_nothing(client, tree, clock, body):
    before = tree_hash(tree)
    assert client().post(POST, json=body).status_code == 422
    assert tree_hash(tree) == before


def test_a_lone_surrogate_is_refused_not_a_server_error(client, tree, clock):
    before = tree_hash(tree)
    r = client().post(POST, content='{"words": "a\\ud800b", "addressed_to": "microscope"}',
                      headers={"content-type": "application/json"})
    assert r.status_code == 422 and tree_hash(tree) == before


def test_nothing_else_in_any_agents_tree_is_touched(client, tree, clock):
    before = tree_hash(tree)
    r = ask(client(), "microscope")
    new = set(tree_hash(tree)) - set(before)
    assert new == {f"microscope_agent/console_inbox/{r.json()['item_id']}.json"}
    assert {k: v for k, v in tree_hash(tree).items() if k in before} == before
    assert not any(p.startswith(("bridge", "librarian_agent", "simulation_agent", "console")) for p in new)


# -- the mock: a practice copy, never the sample and never the real tree ------------------------------


def test_under_the_mock_only_the_write_dir_changes(engine, make_client, tmp_path, clock):
    store = MockStore(tmp_path / "practice")
    sample_before = tree_hash(MOCK_DATA)
    real_before = {a: tree_hash(REPO / f"{a}_agent" / "console_inbox")
                   for a in ("microscope", "simulation") if (REPO / f"{a}_agent" / "console_inbox").is_dir()}
    requests_before = (REPO / "console" / "requests").exists()
    c = make_client(engine, agent_store=store)
    r = ask(c, "microscope")
    assert r.status_code == 201 and r.json()["artifact"] == "console_question"
    mine = inbox_of(tmp_path / "practice", "microscope")
    assert entries(mine) == [r.json()["item_id"] + ".json"]  # the mock made the folder, in its write dir
    assert entries(outgoing_of(tmp_path / "practice")) == []
    assert tree_hash(MOCK_DATA) == sample_before
    assert {a: tree_hash(REPO / f"{a}_agent" / "console_inbox") for a in real_before} == real_before
    assert (REPO / "console" / "requests").exists() == requests_before
    shown = c.get(CARDS).json()["items"]
    assert shown[0]["item_id"] == r.json()["item_id"]  # newest first
    assert [i["item_id"] for i in shown[1:]] == sorted(
        (i["item_id"] for i in shown[1:]), reverse=True) and len(shown) == 1 + 9  # and the sample's nine examples


def test_under_the_mock_the_librarian_ask_is_delivered_into_the_write_dir_only(engine, make_client, tmp_path, clock):
    store = MockStore(tmp_path / "practice")
    sample_before = tree_hash(MOCK_DATA)
    c = make_client(engine, agent_store=store)
    r = ask(c, "librarian")
    assert r.status_code == 201
    mine = inbox_of(tmp_path / "practice", "librarian")
    assert entries(mine) == [r.json()["item_id"] + ".json"]
    assert json.loads((mine / entries(mine)[0]).read_text(encoding="utf-8"))["artifact"] == "console_store_request"
    assert tree_hash(MOCK_DATA) == sample_before


def test_the_mock_counts_its_own_questions_from_c001(engine, make_client, tmp_path, clock):
    c = make_client(engine, agent_store=MockStore(tmp_path / "practice"))
    assert [ask(c, "microscope").json()["question_id"], ask(c, "microscope").json()["question_id"]] == [
        "mic-20261026-c001", "mic-20261026-c002"]


# -- the audit line ----------------------------------------------------------------------------------


def test_the_audit_line_names_the_agent_the_item_and_the_question_and_not_the_words(client, seat, clock):
    r = ask(client(), "simulation", "a private-looking sentence").json()
    line = [e for e in seat.audit.entries() if e["kind"] == "question_submitted"][-1]
    assert line["user_id"] == OPERATOR and line["target"] == "simulation"
    assert line["item_id"] == r["item_id"] and line["question_id"] == r["question_id"]
    assert "private-looking" not in json.dumps(line)


# -- the cards below the field -----------------------------------------------------------------------


def cards(c) -> dict:
    r = c.get(CARDS)
    assert r.status_code == 200, r.text
    return r.json()


def item_cards(c) -> list[dict]:
    return cards(c)["items"]


def test_a_delivered_item_is_a_card_not_answered_yet_and_runs_wait_for_the_person(client, tree, clock):
    c = client()
    mine = ask(c, "microscope", "newer words").json()
    got = item_cards(c)
    assert got == [{
        "item_id": mine["item_id"], "question_id": mine["question_id"], "agent": "microscope",
        "words": "newer words", "login": OPERATOR, "asked_at": mine["asked_at"],
        "state": "delivered · not answered yet", "runs_wait_for_signature": True, "latest_answer": None}]


def test_every_item_in_the_two_inboxes_is_shown_newest_first_and_the_file_name_plays_no_part(client, tree):
    put_item(tree, "microscope", item_id="ci-20261026-090000-zzzz", asked_at="2026-10-26T09:00:00Z",
             question_id="mic-20261026-c001", words="oldest")
    put_item(tree, "simulation", item_id="ci-20261026-100000-aaaa", asked_at="2026-10-26T10:00:00Z",
             question_id="sim-20261026-c001", words="middle")
    put_item(tree, "microscope", item_id="ci-20261026-110000-bbbb", asked_at="2026-10-26T11:00:00Z",
             question_id="mic-20261026-c002", words="tie b")
    put_item(tree, "simulation", item_id="ci-20261026-110000-cccc", asked_at="2026-10-26T11:00:00Z",
             question_id="sim-20261026-c002", words="tie c")
    # the file name says an early hour and the item says a late one: the item decides
    put_item(tree, "microscope", item_id="ci-20261026-000000-eeee", asked_at="2026-10-26T12:00:00Z",
             question_id="mic-20261026-c003", words="newest")
    got = item_cards(client())
    assert [i["words"] for i in got] == ["newest", "tie c", "tie b", "middle", "oldest"]  # item_id breaks the tie
    assert [i["agent"] for i in got] == ["microscope", "simulation", "microscope", "simulation", "microscope"]
    assert got[1]["question_id"] == "sim-20261026-c002" and got[1]["login"] == "member-1"


def test_a_file_in_an_inbox_that_is_not_an_item_is_not_shown(client, tree):
    inbox = inbox_of(tree, "microscope")
    (inbox / "notes.json").write_text(json.dumps(an_item()), encoding="utf-8")  # a name that is not its id
    (inbox / "ci-20261026-090000-zzzz.json").write_text("{not json", encoding="utf-8")
    (inbox / "ci-20261026-090001-yyyy.json").write_text(json.dumps({"artifact": "other"}), encoding="utf-8")
    assert item_cards(client()) == []


def test_requests_in_the_consoles_folder_keep_their_cards_marked_not_delivered(client, tree, clock):
    c = client()
    folder = tree / "console" / "requests" / "questions"  # an earlier console left it; nothing writes it now
    folder.mkdir(parents=True)
    (folder / "qr-20261024-174512-k3p9.json").write_text(json.dumps({
        "artifact": "question_request", "schema_version": "0.1", "id": "qr-20261024-174512-k3p9",
        "words": "to the agents", "asked_by": {"login": OPERATOR, "console_role": {
            "may_ask": True, "may_draft": True, "agents": ["microscope"], "may_ask_model_run": False}},
        "asked_at": "2026-10-24T17:45:12Z", "addressed_to": "agents_decide"}), encoding="utf-8")
    got = cards(c)
    assert [r["words"] for r in got["requests"]] == ["to the agents"]
    assert {r["state"] for r in got["requests"]} == {NOT_DELIVERED}
    assert all(r["runs_wait_for_signature"] is True for r in got["requests"])
    assert got["items"] == []


def test_a_question_to_the_librarian_is_a_delivered_card_that_does_not_wait_for_a_signature(client, tree, clock):
    c = client()
    sent = ask(c, "librarian", "to the library").json()
    got = cards(c)
    assert got["requests"] == []
    (card,) = got["items"]
    assert card["item_id"] == sent["item_id"] and card["agent"] == "librarian" and card["words"] == "to the library"
    assert card["state"] == "delivered · not answered yet" and card["question_id"] is None
    assert card["runs_wait_for_signature"] is False and card["latest_answer"] is None


def test_an_item_with_no_answer_says_so(client, tree):
    put_item(tree, "microscope")
    assert [i["state"] for i in item_cards(client())] == ["delivered · not answered yet"]


def test_a_taken_up_answer_says_which_question(client, tree):
    item = put_item(tree, "microscope", question_id="mic-20261026-c001")
    doc = {"artifact": "console_answer", "schema_version": "0.1", "answer_id": "ca-20261026-120000-aaaa",
           "item_id": item["item_id"], "question_id": item["question_id"], "outcome": "taken_up",
           "goal_card": "microscope_agent/questions/mic-20261026-001/goal.json",
           "answered_at": "2026-10-26T12:00:00Z", "answered_by": "microscope-office-20261015-1"}
    answers_of(tree, "microscope").mkdir(parents=True, exist_ok=True)
    (answers_of(tree, "microscope") / f"{doc['answer_id']}.json").write_text(json.dumps(doc), encoding="utf-8")
    assert [i["state"] for i in item_cards(client())] == ["taken up as mic-20261026-c001"]


def test_a_refusal_shows_the_reason_exactly(client, tree):
    item = put_item(tree, "simulation")
    put_answer(tree, "simulation", item, reason="  the engine cannot do this yet — μm  ")
    assert [i["state"] for i in item_cards(client())] == ["refused ·   the engine cannot do this yet — μm  "]


def test_the_latest_answer_is_the_newest_by_its_time_and_not_by_its_file_name(client, tree):
    item = put_item(tree, "microscope")
    # the file names sort one way and the times the other
    put_answer(tree, "microscope", item, answer_id="ca-20261026-130000-zzzz", name="ca-20261026-130000-zzzz.json",
               answered_at="2026-10-26T10:00:00Z", reason="the earlier answer, said first")
    put_answer(tree, "microscope", item, answer_id="ca-20261026-100000-aaaa", name="ca-20261026-100000-aaaa.json",
               answered_at="2026-10-26T14:00:00Z", reason="the later answer, said last")
    assert [i["state"] for i in item_cards(client())] == ["refused · the later answer, said last"]


def test_a_tie_in_time_is_broken_by_the_answer_id(client, tree):
    item = put_item(tree, "microscope")
    put_answer(tree, "microscope", item, answer_id="ca-20261026-120000-aaaa", reason="answer aaaa is lower")
    put_answer(tree, "microscope", item, answer_id="ca-20261026-120000-bbbb", reason="answer bbbb is higher")
    assert [i["state"] for i in item_cards(client())] == ["refused · answer bbbb is higher"]


def test_an_answer_to_another_item_does_not_count(client, tree):
    item = put_item(tree, "microscope", item_id="ci-20261026-090000-aaaa", question_id="mic-20261026-c001")
    other = put_item(tree, "microscope", item_id="ci-20261026-091000-bbbb", question_id="mic-20261026-c002",
                     asked_at="2026-10-26T09:10:00Z")
    put_answer(tree, "microscope", other, reason="for the second one only")
    got = {i["item_id"]: i["state"] for i in item_cards(client())}
    assert got == {item["item_id"]: "delivered · not answered yet", other["item_id"]: "refused · for the second one only"}


def test_an_answer_in_the_other_agents_folder_does_not_count(client, tree):
    item = put_item(tree, "microscope")
    put_answer(tree, "simulation", item)
    assert [i["state"] for i in item_cards(client())] == ["delivered · not answered yet"]


def test_an_answer_that_names_the_item_and_cannot_be_read_says_so(client, tree):
    item = put_item(tree, "microscope")
    folder = answers_of(tree, "microscope")
    folder.mkdir(parents=True)
    (folder / "ca-20261026-120000-aaaa.json").write_text('{"item_id": "%s", broken' % item["item_id"], encoding="utf-8")
    assert [i["state"] for i in item_cards(client())] == [UNREADABLE]


def test_an_answer_that_fails_its_schema_says_so(client, tree):
    item = put_item(tree, "microscope")
    put_answer(tree, "microscope", item, reason="short")  # under ten characters
    assert [i["state"] for i in item_cards(client())] == [UNREADABLE]
    put_answer(tree, "microscope", item, answer_id="ca-20261026-130000-bbbb", persons_own=True)
    assert [i["state"] for i in item_cards(client())] == [UNREADABLE]


def test_an_answer_that_names_another_question_id_says_so(client, tree):
    item = put_item(tree, "microscope", question_id="mic-20261026-c001")
    put_answer(tree, "microscope", item, question_id="mic-20261026-c002")
    assert [i["state"] for i in item_cards(client())] == [UNREADABLE]


def test_the_card_does_not_guess_past_an_answer_it_cannot_read(client, tree):
    item = put_item(tree, "microscope")
    put_answer(tree, "microscope", item, answer_id="ca-20261026-120000-aaaa", reason="a good answer, once")
    put_answer(tree, "microscope", item, answer_id="ca-20261026-130000-bbbb", answered_at="2026-10-26T13:00:00Z",
               reason="short")
    assert [i["state"] for i in item_cards(client())] == [UNREADABLE]


def test_the_cards_write_nothing(client, tree):
    item = put_item(tree, "microscope")
    put_answer(tree, "microscope", item)
    before = tree_hash(tree)
    assert client().get(CARDS).status_code == 200
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []


# -- what the mutation checks showed the first tests did not hold -------------------------------------


def raw(root: Path, agent: str, name: str, text: str) -> None:
    (inbox_of(root, agent) / name).write_text(text, encoding="utf-8")


def test_the_other_agents_question_ids_in_an_inbox_do_not_move_its_count(client, tree, clock):
    raw(tree, "microscope", "ci-20261026-090000-aaaa.json",
        json.dumps(an_item("simulation", question_id="sim-20261026-c005")))
    assert ask(client(), "microscope").json()["question_id"] == "mic-20261026-c001"


def test_another_dates_number_in_an_inbox_does_not_move_todays_count(client, tree, clock):
    put_item(tree, "microscope", question_id="mic-20261025-c007")
    assert ask(client(), "microscope").json()["question_id"] == "mic-20261026-c001"


def test_a_damaged_item_refuses_the_delivery_because_its_number_cannot_be_told(client, tree, clock):
    raw(tree, "microscope", "ci-20261026-090000-aaaa.json", '{"question_id": "mic-20261026-c004", broken')
    before = tree_hash(tree)
    assert refusal(ask(client(), "microscope")) == (409, "inbox_unreadable")
    assert tree_hash(tree) == before


def test_a_stray_json_file_still_holds_the_number_its_text_names(client, tree, clock):
    raw(tree, "microscope", "notes.json", '{"question_id": "mic-20261026-c004", broken')
    assert ask(client(), "microscope").json()["question_id"] == "mic-20261026-c005"


def test_the_nine_hundred_ninety_ninth_is_the_last_that_lands(client, tree, clock):
    put_item(tree, "microscope", question_id="mic-20261026-c998")
    r = ask(client(), "microscope")
    assert r.status_code == 201 and r.json()["question_id"] == "mic-20261026-c999"
    assert refusal(ask(client(), "microscope")) == (409, "inbox_full")


def test_with_no_schemas_to_check_against_nothing_is_written(tree, clock):
    M = inbox_items_module()
    with pytest.raises(M.InboxError):
        M.deliver(agent="microscope", words="a question", login=OPERATOR, role="operator",
                  inbox=inbox_of(tree, "microscope"), outgoing=outgoing_of(tree), schemas=None)
    assert entries(inbox_of(tree, "microscope")) == [".gitkeep"]
    assert entries(outgoing_of(tree)) == []


def test_a_file_shaped_like_an_item_but_another_artifact_is_not_shown(client, tree):
    doc = an_item()
    doc["artifact"] = "console_answer"
    raw(tree, "microscope", f"{doc['item_id']}.json", json.dumps(doc))
    assert item_cards(client()) == []


def test_an_item_with_the_other_agents_question_id_is_not_shown(client, tree):
    doc = an_item("microscope", question_id="sim-20261026-c001")
    raw(tree, "microscope", f"{doc['item_id']}.json", json.dumps(doc))
    assert item_cards(client()) == []


def test_an_item_filed_under_another_items_name_is_not_shown(client, tree):
    raw(tree, "microscope", "ci-20261026-090000-bbbb.json", json.dumps(an_item(item_id="ci-20261026-090000-aaaa")))
    assert item_cards(client()) == []


def test_an_answer_that_cannot_be_parsed_counts_against_the_item_it_names_and_no_other(client, tree):
    named = put_item(tree, "microscope", item_id="ci-20261026-090000-aaaa", question_id="mic-20261026-c001")
    other = put_item(tree, "microscope", item_id="ci-20261026-100000-bbbb", question_id="mic-20261026-c002",
                     asked_at="2026-10-26T10:00:00Z")
    folder = answers_of(tree, "microscope")
    folder.mkdir(parents=True)
    (folder / "ca-20261026-120000-aaaa.json").write_text('{"item_id": "%s", broken' % named["item_id"], encoding="utf-8")
    states = {i["item_id"]: i["state"] for i in item_cards(client())}
    assert states == {named["item_id"]: UNREADABLE, other["item_id"]: "delivered · not answered yet"}


def test_an_item_in_two_folders_is_shown_once_and_the_earlier_folder_keeps_it(engine, make_client, tmp_path):
    data = tmp_path / "sample"
    shutil.copytree(MOCK_DATA, data)
    practice = tmp_path / "practice"
    inbox_of(practice, "microscope").mkdir(parents=True)
    here = put_item(practice, "microscope", words="the practice words")
    inbox_of(data, "microscope").mkdir(parents=True, exist_ok=True)
    put_item(data, "microscope", words="the sample's words")
    c = make_client(engine, agent_store=MockStore(practice, data_dir=data))
    shown = [i for i in item_cards(c) if i["agent"] == "microscope"]  # the sample's librarian examples are not these
    assert [(i["item_id"], i["words"]) for i in shown] == [(here["item_id"], "the practice words")]
