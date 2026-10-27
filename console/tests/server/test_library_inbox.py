"""The Library's requests reach the librarian's inbox, and its answers are read (console card 020, plan.md 7.1.1).

An item is `contracts/schemas/console_store_request.schema.json`, written once and whole into
`<tree>/librarian_agent/console_inbox/<item_id>.json`, with at most one attached file beside it as
`<item_id>--<name>`. Answers are read from `<tree>/librarian_agent/answers/` by exact name. Every test here
runs in a `tmp_path` tree.
"""

from __future__ import annotations

import base64
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
SEND = "/api/library/requests"
QUESTION = "/api/console/question-requests"
CARDS = "/api/console/question-cards"
NOW = datetime(2026, 10, 26, 17, 45, 12, tzinfo=UTC)
NOT_ANSWERED = "delivered · not answered yet"
UNREADABLE = "an answer is on disk and cannot be read"
WORDS = "What does the spec sheet say about the nosepiece travel?"

ADD = {"kind": "enter_document", "source_kind": "spec", "read_by": "member-1", "document": "spec.pdf"}
WITHDRAW = {"kind": "withdraw_value", "entry_id": "gel_modulus", "evidence": {"kind": "none"}}
OFFER = {"kind": "offer_result", "result_card": "microscope_agent/questions/mic-20260925-002/result_a.json"}
ASK = {"kind": "ask"}
BY_KIND = {"enter_document": ADD, "withdraw_value": WITHDRAW, "offer_result": OFFER, "ask": ASK}
WORDS_FIELD = {"enter_document": "fact_wanted", "withdraw_value": "reason", "offer_result": "fact_in_words",
               "ask": "question"}
PDF = b"%PDF-1.4\n% a document\n\x00\xff\xfe"


def lib_inbox(root: Path) -> Path:
    return root / "librarian_agent" / "console_inbox"


def lib_answers(root: Path) -> Path:
    return root / "librarian_agent" / "answers"


def outgoing_of(root: Path) -> Path:
    return root / "console" / "requests" / "outgoing"


def tree_hash(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def entries(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def refusal(r) -> tuple[int, str]:
    assert r.headers[REFUSAL_HEADER] == r.json()["detail"]["code"]
    return r.status_code, r.json()["detail"]["code"]


def items(root: Path) -> list[Path]:
    return sorted(lib_inbox(root).glob("ci-*.json"))


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def body(request, words=WORDS, file=None) -> dict:
    out = {"words": words, "request": request}
    if file is not None:
        out["file"] = {"name": file[0], "content_base64": b64(file[1])}
    return out


def send(c, request, words=WORDS, file=None):
    return c.post(SEND, json=body(request, words, file))


def check_item(doc: dict) -> list[str]:
    return Schemas(SCHEMAS).validate(doc, "console_store_request.schema.json")


def inbox_module():
    import importlib

    return importlib.import_module("sma_console.agents.inbox_items")


def store_module():
    import importlib

    return importlib.import_module("sma_console.agents.store_requests")


@pytest.fixture
def tree(tmp_path):
    """A soft-matter-agents tree: the sample's agents without its example items and answers, the contracts'
    schemas the console reads, and an empty librarian inbox (its `.gitkeep` only)."""
    root = tmp_path / "sma"
    shutil.copytree(MOCK_DATA, root)
    shutil.rmtree(root / "console")
    shutil.rmtree(root / "microscope_runtime")
    for gone in (lib_inbox(root), lib_answers(root)):
        shutil.rmtree(gone, ignore_errors=True)
    (root / "contracts" / "schemas").mkdir(parents=True)
    for name in ("console_inbox_item.schema.json", "console_answer.schema.json",
                 "console_store_request.schema.json", "store_answer.schema.json"):
        shutil.copy(SCHEMAS / name, root / "contracts" / "schemas" / name)
    (root / "contracts" / "quantities.json").write_text(json.dumps({"quantities": []}), encoding="utf-8")
    for agent in ("microscope", "simulation", "librarian"):
        (root / f"{agent}_agent" / "console_inbox").mkdir(parents=True, exist_ok=True)
        (root / f"{agent}_agent" / "console_inbox" / ".gitkeep").write_bytes(b"")
    return root


@pytest.fixture
def client(engine, make_client, tree):
    return lambda **kw: make_client(engine, agent_store=SmaFiles(tree, source="soft-matter-agents"), **kw)


@pytest.fixture
def clock(monkeypatch):
    M = inbox_module()
    state = {"now": NOW, "suffixes": iter(f"{c}{c}{c}{c}" for c in "abcdefghijklmnopqrstuvwxyz")}
    monkeypatch.setattr(M, "utc_now", lambda: state["now"])
    monkeypatch.setattr(M, "random_suffix", lambda: next(state["suffixes"]))
    return state


def written(root: Path) -> dict:
    files = items(root)
    assert len(files) == 1
    return json.loads(files[0].read_bytes().decode("utf-8"))


# -- an item of each kind, in the schema's shape ------------------------------------------------------------


@pytest.mark.parametrize("kind", list(BY_KIND))
def test_an_item_of_each_kind_is_written_in_the_schemas_shape(client, tree, clock, kind):
    file = ("spec.pdf", PDF) if kind == "enter_document" else None
    r = send(client(), BY_KIND[kind], file=file)
    assert r.status_code == 201, r.text
    doc = written(tree)
    assert check_item(doc) == []
    assert re.fullmatch(r"ci-20261026-174512-[a-z0-9]{4}", doc["item_id"])
    assert (lib_inbox(tree) / f"{doc['item_id']}.json").is_file()
    assert doc["artifact"] == "console_store_request" and doc["asked_at"] == "2026-10-26T17:45:12Z"
    assert doc["asker_mark"] == {"kind": "other_login"} and doc["asked_by"]["login"] == OPERATOR
    assert doc["asked_by"]["console_role"]["agents"] == ["microscope", "simulation", "librarian"]
    assert set(doc) == {"artifact", "schema_version", "item_id", "words", "asked_by", "asked_at", "asker_mark",
                        "attachments", "request"}
    assert "question_id" not in doc
    assert doc["request"]["kind"] == kind
    assert r.json() == doc  # what the screen is told is what was written
    data = next(iter(items(tree))).read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf") and b"\r" not in data and data.endswith(b"}\n")
    for other in ("microscope", "simulation"):  # nothing in another agent's inbox
        assert entries(tree / f"{other}_agent" / "console_inbox") == [".gitkeep"]


@pytest.mark.parametrize("kind", list(BY_KIND))
def test_the_item_also_passes_the_repositorys_schema_under_jsonschema(client, tree, clock, kind):
    jsonschema = pytest.importorskip("jsonschema")
    file = ("spec.pdf", PDF) if kind == "enter_document" else None
    send(client(), BY_KIND[kind], file=file)
    spec = json.loads((SCHEMAS / "console_store_request.schema.json").read_text("utf-8"))
    store = {}
    for p in SCHEMAS.glob("*.schema.json"):
        s = json.loads(p.read_text("utf-8"))
        store[s.get("$id", p.name)] = s
        store[p.name] = s
    from referencing import Registry, Resource  # installed with jsonschema

    registry = Registry().with_resources((k, Resource.from_contents(v)) for k, v in store.items())
    jsonschema.Draft202012Validator(spec, registry=registry).validate(written(tree))


# -- the words: verbatim in `words`, stripped in the field of the kind ------------------------------------------

TYPED = "  Does the gel flow more easily\nafter it rests?  \n\n\"quoted\" μm — é\\  "


@pytest.mark.parametrize("kind", list(BY_KIND))
def test_the_words_are_kept_as_typed_and_the_kinds_field_is_stripped(client, tree, clock, kind):
    file = ("spec.pdf", PDF) if kind == "enter_document" else None
    send(client(), BY_KIND[kind], words=TYPED, file=file)
    doc = written(tree)
    assert doc["words"].encode("utf-8") == TYPED.encode("utf-8") and doc["words"] != TYPED.strip()
    assert doc["request"][WORDS_FIELD[kind]] == TYPED.strip()


@pytest.mark.parametrize("kind", list(BY_KIND))
def test_a_request_that_already_carries_the_words_field_is_refused_and_nothing_is_written(client, tree, clock, kind):
    before = tree_hash(tree)
    file = ("spec.pdf", PDF) if kind == "enter_document" else None
    r = send(client(), {**BY_KIND[kind], WORDS_FIELD[kind]: "typed twice"}, file=file)
    assert refusal(r) == (422, "invalid")
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []


@pytest.mark.parametrize("request_", [
    {"kind": "ask", "question": "x", "extra": 1}, {"kind": "nope"}, {"kind": "ask", "conditions": 3}, [], "ask"])
def test_a_request_the_schema_does_not_take_is_refused_and_nothing_is_written(client, tree, clock, request_):
    before = tree_hash(tree)
    r = client().post(SEND, json={"words": WORDS, "request": request_})
    assert r.status_code == 422
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []


def test_only_the_shapes_of_the_entry_and_the_result_card_are_checked_not_that_they_exist(client, tree, clock):
    assert send(client(), {**WITHDRAW, "entry_id": "no_such_entry_anywhere"}).status_code == 201
    assert send(client(), {**OFFER, "result_card": "simulation_agent/questions/sim-1/result_zz.json"}).status_code == 201
    assert refusal(send(client(), {**WITHDRAW, "entry_id": "Not A Shape"}))[0] == 422
    assert refusal(send(client(), {**OFFER, "result_card": "console/x.json"}))[0] == 422


# -- the attached file ---------------------------------------------------------------------------------------------


def test_one_file_is_written_beside_its_item_with_its_bytes_and_its_hash(client, tree, clock):
    r = send(client(), ADD, file=("spec.pdf", PDF))
    doc = written(tree)
    iid = doc["item_id"]
    assert doc["request"]["document"] == f"{iid}--spec.pdf"
    assert doc["attachments"] == [{"file": f"{iid}--spec.pdf", "sha256": hashlib.sha256(PDF).hexdigest()}]
    assert (lib_inbox(tree) / f"{iid}--spec.pdf").read_bytes() == PDF
    assert entries(lib_inbox(tree)) == sorted([".gitkeep", f"{iid}.json", f"{iid}--spec.pdf"])
    assert r.json()["attachments"] == doc["attachments"]
    assert entries(outgoing_of(tree)) == []


def test_a_withdrawals_evidence_may_carry_the_file(client, tree, clock):
    ev = {"kind": "document", "source_kind": "literature", "document": "paper.pdf"}
    assert send(client(), {**WITHDRAW, "evidence": ev}, file=("paper.pdf", PDF)).status_code == 201
    doc = written(tree)
    assert doc["request"]["evidence"]["document"] == f"{doc['item_id']}--paper.pdf"
    assert [a["file"] for a in doc["attachments"]] == [f"{doc['item_id']}--paper.pdf"]
    reading = {"kind": "reading", "read_by": "me", "value": {"value": 3, "unit": "mm"}, "document": "r.png"}
    assert send(client(), {**WITHDRAW, "evidence": reading}, file=("r.png", b"\x89PNG")).status_code == 201


def test_a_reading_without_a_file_and_a_recalled_value_carry_none(client, tree, clock):
    recall = {"kind": "enter_document", "source_kind": "operator_recall", "read_by": "me",
              "value": {"value": 3, "unit": "mm"}}
    assert send(client(), recall).status_code == 201
    assert items(tree) and all(json.loads(p.read_text("utf-8"))["attachments"] == [] for p in items(tree))


@pytest.mark.parametrize("request_,file,says", [
    (ADD, None, "names a file, but no file came"),  # names a file it does not send
    ({**ADD, "document": None}, ("spec.pdf", PDF), "A file came that the request does not name"),
    (ADD, ("other.pdf", PDF), "names one file and another came"),  # names one and sends another
    (ASK, ("spec.pdf", PDF), "takes no file"),  # a kind that takes no file
    (OFFER, ("spec.pdf", PDF), "takes no file"),
    ({**WITHDRAW, "evidence": {"kind": "none"}}, ("spec.pdf", PDF), "takes no file"),
])
def test_a_request_must_name_exactly_the_file_it_sends(client, tree, clock, request_, file, says):
    request_ = {k: v for k, v in request_.items() if v is not None}
    before = tree_hash(tree)
    r = send(client(), request_, file=file)
    assert r.status_code == 422, r.text
    assert says in r.json()["detail"]["message"]
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []


@pytest.mark.parametrize("name", ["../spec.pdf", "a/b.pdf", ".hidden", "-x.pdf", "a b.pdf", "", "é.pdf", "x" * 129])
def test_a_file_name_outside_the_inboxs_form_is_refused(client, tree, clock, name):
    before = tree_hash(tree)
    r = send(client(), {**ADD, "document": name}, file=(name, PDF))
    assert r.status_code == 422
    assert tree_hash(tree) == before


def test_the_longest_name_is_taken(client, tree, clock):
    name = "a" + "b" * 127
    assert send(client(), {**ADD, "document": name}, file=(name, PDF)).status_code == 201


def test_a_file_over_twenty_megabytes_is_refused_before_anything_is_written(client, tree, clock):
    before = tree_hash(tree)
    r = send(client(), ADD, file=("spec.pdf", b"x" * (20 * 1024 * 1024 + 1)))
    assert refusal(r) == (422, "file_refused")
    assert r.json()["detail"]["message"] == ("This file is larger than 20 MB, which the inbox does not take. "
                                              "Send a smaller copy, or the pages that hold the value.")
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []
    assert send(client(), ADD, file=("spec.pdf", b"x" * (20 * 1024 * 1024))).status_code == 201


@pytest.mark.parametrize("data", [b'{"a": 1}', b'  {"a": [1]} ', b'\xef\xbb\xbf{"a": 1}', b"[1, {\"a\": 2}]",
                                  b'{}', b'[[{}]]', pytest.param(b"[" * 100000 + b"]" * 100000, id="nested-far-past-the-parser")])
def test_a_file_that_reads_as_an_object_is_refused_and_nothing_is_written(client, tree, clock, data):
    before = tree_hash(tree)
    r = send(client(), ADD, file=("spec.pdf", data))
    assert refusal(r) == (422, "file_refused")
    assert r.json()["detail"]["message"] == (
        "This file reads as data with named fields, which the inbox cannot carry, because the store's checks "
        "would read it as a card. Attach it as CSV, text or PDF instead.")
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []


@pytest.mark.parametrize("data", [b"42", b'"text"', b"[1, 2]", b"true", b"null", b"a,b\n1,2\n", PDF,
                                  b'{"a": ', b"\xff\xfe"])
def test_a_bare_value_and_anything_that_is_not_json_is_taken(client, tree, clock, data):
    assert send(client(), ADD, file=("spec.pdf", data)).status_code == 201


def test_an_empty_file_is_refused(client, tree, clock):
    before = tree_hash(tree)
    r = send(client(), ADD, file=("spec.pdf", b""))
    assert refusal(r) == (422, "file_refused") and r.json()["detail"]["message"] == "This file is empty."
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []


def test_a_file_that_is_not_base64_is_refused(client, tree, clock):
    before = tree_hash(tree)
    r = client().post(SEND, json={"words": WORDS, "request": ADD,
                                  "file": {"name": "spec.pdf", "content_base64": "not base 64 !!"}})
    assert r.status_code == 422 and tree_hash(tree) == before


# -- a taken item id ---------------------------------------------------------------------------------------------------


def test_a_taken_item_id_with_a_file_leaves_the_first_item_and_file_as_they_were(client, tree, clock):
    c = client()
    assert send(c, ADD, file=("spec.pdf", PDF)).status_code == 201
    first = {p.name: p.read_bytes() for p in lib_inbox(tree).iterdir()}
    clock["suffixes"] = iter(["aaaa", "bbbb"])  # the same id comes up again, then a new one
    r = send(c, ADD, words="a second request", file=("spec.pdf", b"another file"))
    assert r.status_code == 201
    assert r.json()["item_id"].endswith("-bbbb")
    for name, data in first.items():
        assert (lib_inbox(tree) / name).read_bytes() == data
    doc = r.json()
    assert doc["request"]["document"] == f"{doc['item_id']}--spec.pdf"
    assert (lib_inbox(tree) / doc["request"]["document"]).read_bytes() == b"another file"
    assert len(entries(lib_inbox(tree))) == 5 and entries(outgoing_of(tree)) == []


def test_a_taken_file_name_makes_the_id_taken_and_the_request_lands_under_a_new_id(client, tree, clock):
    squatter = lib_inbox(tree) / "ci-20261026-174512-aaaa--spec.pdf"
    squatter.write_bytes(b"someone else's")
    clock["suffixes"] = iter(["aaaa", "bbbb"])
    r = send(client(), ADD, file=("spec.pdf", PDF))
    assert r.status_code == 201 and r.json()["item_id"].endswith("-bbbb")
    assert squatter.read_bytes() == b"someone else's"
    assert not (lib_inbox(tree) / "ci-20261026-174512-aaaa.json").exists()  # no item under the taken id
    assert entries(outgoing_of(tree)) == []


def test_five_taken_ids_end_in_a_refusal_and_change_nothing(client, tree, clock):
    clock["suffixes"] = iter(["aaaa"] * 5)
    c = client()
    assert send(c, ASK).status_code == 201
    before = tree_hash(tree)
    clock["suffixes"] = iter(["aaaa"] * 5)
    r = send(c, ASK)
    assert refusal(r) == (409, "item_exists")
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []


# -- a write that fails halfway -----------------------------------------------------------------------------------


def test_a_failure_between_the_files_link_and_the_items_leaves_the_inbox_as_it_was(client, tree, clock, monkeypatch):
    M = store_module()
    real = os.link
    calls = []

    def broken(src, dst, *a, **kw):
        calls.append(Path(dst).name)
        if len(calls) == 2:
            raise OSError("disk went away")
        return real(src, dst, *a, **kw)

    before = tree_hash(tree)
    monkeypatch.setattr(M.os, "link", broken)
    r = send(client(), ADD, file=("spec.pdf", PDF))
    assert r.status_code == 500 and len(calls) == 2 and calls[0].endswith("--spec.pdf")
    assert entries(lib_inbox(tree)) == [".gitkeep"] and entries(outgoing_of(tree)) == []
    assert tree_hash(tree) == before


def test_a_failure_to_write_the_file_at_all_leaves_nothing(client, tree, clock, monkeypatch):
    M = store_module()

    def broken(src, dst, *a, **kw):
        raise OSError("disk went away")

    monkeypatch.setattr(M.os, "link", broken)
    r = send(client(), ADD, file=("spec.pdf", PDF))
    assert r.status_code == 500
    assert entries(lib_inbox(tree)) == [".gitkeep"] and entries(outgoing_of(tree)) == []


def test_after_every_write_the_inbox_holds_only_items_their_files_and_the_keep_file(client, tree, clock):
    c = client()
    send(c, ADD, file=("spec.pdf", PDF))
    send(c, ASK)
    send(c, WITHDRAW)
    send(c, OFFER)
    listed = set()
    for p in items(tree):
        listed.update(a["file"] for a in json.loads(p.read_text("utf-8"))["attachments"])
    names = set(entries(lib_inbox(tree)))
    assert names == {".gitkeep"} | {p.name for p in items(tree)} | listed
    assert len(items(tree)) == 4 and entries(outgoing_of(tree)) == []


def test_nothing_else_in_the_librarians_tree_is_touched(client, tree, clock):
    before = tree_hash(tree)
    send(client(), ADD, file=("spec.pdf", PDF))
    after = tree_hash(tree)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert all(k.startswith("librarian_agent/console_inbox/") for k in changed) and len(changed) == 2


# -- who may send, and where ------------------------------------------------------------------------------------------


def test_a_viewer_cannot_send_and_nothing_is_written(client, tree, clock):
    before = tree_hash(tree)
    assert refusal(send(client(login=VIEWER), ADD, file=("spec.pdf", PDF)))[0] == 403
    assert refusal(send(client(login=VIEWER), ASK))[0] == 403
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []


def test_a_missing_librarian_inbox_says_so_and_writes_nothing(client, tree, clock):
    shutil.rmtree(lib_inbox(tree))
    before = tree_hash(tree)
    r = send(client(), ADD, file=("spec.pdf", PDF))
    assert refusal(r) == (409, "inbox_missing")
    assert r.json()["detail"]["message"] == "The librarian's inbox is not there, so nothing was sent."
    assert tree_hash(tree) == before and not lib_inbox(tree).exists() and entries(outgoing_of(tree)) == []


def test_with_no_schemas_to_check_against_nothing_is_written(tree, clock):
    M = store_module()
    with pytest.raises(M.InboxError):
        M.deliver(words=WORDS, request=ASK, attached=None, login=OPERATOR, role="operator",
                  inbox=lib_inbox(tree), outgoing=outgoing_of(tree), schemas=None)
    assert entries(lib_inbox(tree)) == [".gitkeep"] and entries(outgoing_of(tree)) == []


# -- the Questions screen: "The librarian" delivers an ask, "Let the agents decide" does not -------------------------


def test_the_librarian_on_the_questions_screen_delivers_an_ask_with_no_conditions(client, tree, clock):
    r = client().post(QUESTION, json={"words": "  Is the stage travel in the spec?  ", "addressed_to": "librarian"})
    assert r.status_code == 201, r.text
    doc = written(tree)
    assert check_item(doc) == []
    assert doc["request"] == {"kind": "ask", "question": "Is the stage travel in the spec?"}
    assert doc["words"] == "  Is the stage travel in the spec?  " and doc["attachments"] == []
    assert r.json() == doc


def test_let_the_agents_decide_writes_nothing_into_any_inbox(client, tree, clock):
    before = tree_hash(tree)
    r = client().post(QUESTION, json={"words": "something for the agents", "addressed_to": "agents_decide"})
    assert r.status_code == 201
    after = tree_hash(tree)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed and all(k.startswith("console/requests/") for k in changed)
    for agent in ("microscope", "simulation", "librarian"):
        assert entries(tree / f"{agent}_agent" / "console_inbox") == [".gitkeep"]


def test_a_viewer_cannot_ask_the_librarian(client, tree, clock):
    before = tree_hash(tree)
    r = client(login=VIEWER).post(QUESTION, json={"words": "may I?", "addressed_to": "librarian"})
    assert refusal(r)[0] == 403 and tree_hash(tree) == before


def test_a_delivered_question_to_the_librarian_shows_among_the_cards_with_its_state(client, tree, clock):
    c = client()
    iid = c.post(QUESTION, json={"words": "Is the stage travel in the spec?", "addressed_to": "librarian"}).json()["item_id"]
    cards = c.get(CARDS).json()
    card = next(i for i in cards["items"] if i["item_id"] == iid)
    assert card["agent"] == "librarian" and card["question_id"] is None
    assert card["state"] == NOT_ANSWERED and card["runs_wait_for_signature"] is False
    assert card["words"] == "Is the stage travel in the spec?" and card["latest_answer"] is None
    put_answer(tree, written(tree), "answered")
    card = next(i for i in c.get(CARDS).json()["items"] if i["item_id"] == iid)
    assert card["state"] == "Answered" and card["latest_answer"]["outcome"] == "answered"


def test_earlier_questions_offers_the_words_of_delivered_items_too(client, tree, clock):
    c = client()
    c.post(QUESTION, json={"words": "A question for the librarian about travel", "addressed_to": "librarian"})
    c.post(QUESTION, json={"words": "A question for the microscope about focus", "addressed_to": "microscope"})
    got = c.get("/api/console/suggestions").json()
    words = [s["text"] for s in got if s["kind"] == "earlier question"]
    assert "A question for the librarian about travel" in words
    assert "A question for the microscope about focus" in words


# -- the audit line ----------------------------------------------------------------------------------------------------


def test_the_audit_line_names_the_item_the_kind_and_whether_a_file_came_and_not_the_words_or_the_name(
        client, seat, clock):
    r = send(client(), {**ADD, "document": "secret-name.pdf"}, words="a private-looking sentence",
             file=("secret-name.pdf", PDF)).json()
    line = [e for e in seat.audit.entries() if e["kind"] == "question_submitted"][-1]
    assert line["user_id"] == OPERATOR and line["target"] == "librarian"
    assert line["item_id"] == r["item_id"] and line["request_kind"] == "enter_document" and line["attached"] is True
    text = json.dumps(line)
    assert "private-looking" not in text and "secret-name" not in text and "spec.pdf" not in text
    send(client(), ASK)
    line = [e for e in seat.audit.entries() if e["kind"] == "question_submitted"][-1]
    assert line["request_kind"] == "ask" and line["attached"] is False


# -- the answers ---------------------------------------------------------------------------------------------------


EXTRA = {
    "entered": {"kb_version": "kbv-37b1958fb73d", "entries_made": ["example_entry_made"]},
    "waiting_for_a_name": {"quantity_name": "example_quantity"},
    "refuted": {"kb_version": "kbv-37b1958fb73d", "entries_marked": ["a"], "other_side": ["b"]},
    "in_conflict": {"kb_version": "kbv-37b1958fb73d", "entries_marked": ["a"], "other_side": ["b"]},
    "superseded": {"kb_version": "kbv-37b1958fb73d", "entries_marked": ["a"], "other_side": ["b"]},
    "kept": {"kb_version": "kbv-37b1958fb73d"},
    "no_entry_of_that_name": {},
    "answered": {"kb_version": "kbv-37b1958fb73d", "answer": "One recorded value.", "entries_cited": ["a"]},
    "not_in_the_store": {"kb_version": "kbv-37b1958fb73d",
                         "gaps": [{"asked_for": "the quantity in water", "looked_in": "every page"}]},
}
WORDS_OF = {"entered": "Entered", "refuted": "Refuted", "in_conflict": "In conflict", "superseded": "Superseded",
            "kept": "Kept", "no_entry_of_that_name": "No entry of that name", "answered": "Answered",
            "not_in_the_store": "Not in the store"}
_n = iter(range(1, 10_000))


def put_answer(root: Path, item: dict, outcome="entered", *, answer_id=None, answered_at=None, name=None,
               sha=None, follows=None, raw: bytes | None = None, **kw) -> dict:
    n = next(_n)
    answer_id = answer_id or f"ca-20261026-18{n // 100:02d}{n % 100:02d}-{'abcdefgh'[n % 8] * 4}"
    doc = {"artifact": "store_answer", "schema_version": "0.1", "answer_id": answer_id,
           "item_id": item["item_id"],
           "request_sha256": sha or hashlib.sha256((lib_inbox(root) / f"{item['item_id']}.json").read_bytes()).hexdigest(),
           "answered_by": "seat:librarian-20261026-1", "answered_at": answered_at or "2026-10-26T18:00:00Z",
           "outcome": outcome, "reason": f"because of {outcome}", **EXTRA[outcome], **kw}
    if follows is not None:
        doc["follows"] = follows
    lib_answers(root).mkdir(parents=True, exist_ok=True)
    (lib_answers(root) / (name or f"{answer_id}.json")).write_bytes(
        raw if raw is not None else json.dumps(doc, indent=2).encode("utf-8"))
    return doc


def the_request(c, tree, clock, request=ASK, **kw) -> dict:
    r = send(c, request, **kw)
    assert r.status_code == 201, r.text
    return r.json()


def listing(c) -> dict:
    r = c.get(SEND)
    assert r.status_code == 200, r.text
    return r.json()


def view_of(c, item) -> dict:
    return next(v for v in listing(c)["requests"] if v["item_id"] == item["item_id"])


@pytest.mark.parametrize("outcome", list(WORDS_OF))
def test_a_readable_answer_of_each_outcome_is_shown_with_its_state(client, tree, clock, outcome):
    c = client()
    item = the_request(c, tree, clock)
    put_answer(tree, item, outcome)
    v = view_of(c, item)
    assert v["state"] == WORDS_OF[outcome] and v["unreadable"] == []
    assert [a["outcome"] for a in v["answers"]] == [outcome]
    assert listing(c)["orphans"] == []


def test_a_request_with_no_answer_says_so(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock)
    v = view_of(c, item)
    assert v["state"] == NOT_ANSWERED and v["answers"] == []


def test_the_requests_are_shown_with_their_kind_words_login_time_and_file_name_as_text(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock, ADD, words="Take the travel from this sheet", file=("spec.pdf", PDF))
    v = view_of(c, item)
    assert v["kind"] == "enter_document" and v["kind_words"] == "Enter a document or a value"
    assert v["words"] == "Take the travel from this sheet" and v["login"] == OPERATOR
    assert v["asked_at"] == "2026-10-26T17:45:12Z" and v["file"] == f"{item['item_id']}--spec.pdf"
    assert v["example"] is False


def test_requests_come_newest_first_by_time_with_the_id_breaking_a_tie(client, tree, clock):
    c = client()
    first = the_request(c, tree, clock)
    clock["now"] = datetime(2026, 10, 26, 17, 46, 0, tzinfo=UTC)
    second = the_request(c, tree, clock)
    third = the_request(c, tree, clock)  # the same second as the second: the id breaks the tie
    ids = [v["item_id"] for v in listing(c)["requests"]]
    assert ids == sorted([first["item_id"], second["item_id"], third["item_id"]],
                         key=lambda i: (listing(c) and {first["item_id"]: "a", second["item_id"]: "b",
                                                        third["item_id"]: "b"}[i], i), reverse=True)
    assert ids[-1] == first["item_id"] and ids[0] == max(second["item_id"], third["item_id"])


def test_an_attachment_is_never_read_as_an_item_and_a_stray_file_is_ignored(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock, ADD, file=("spec.pdf", PDF))
    (lib_inbox(tree) / "notes.json").write_text("{}", encoding="utf-8")
    (lib_inbox(tree) / "ci-20261026-000000-zzzz.json").write_text('{"artifact": "console_question"}', encoding="utf-8")
    assert [v["item_id"] for v in listing(c)["requests"]] == [item["item_id"]]


def test_answers_are_listed_newest_first_by_answered_at_whatever_their_file_names_sort_as(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock)
    put_answer(tree, item, "kept", answer_id="ca-20261026-180000-zzzz", answered_at="2026-10-26T18:00:00Z")
    put_answer(tree, item, "answered", answer_id="ca-20261026-190000-aaaa", answered_at="2026-10-26T17:55:00Z")
    v = view_of(c, item)
    assert [a["answer_id"] for a in v["answers"]] == ["ca-20261026-180000-zzzz", "ca-20261026-190000-aaaa"]
    assert v["state"] == "Kept"  # the latest by answered_at, not by name


def test_answered_at_ties_are_broken_by_answer_id_newest_first(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock)
    for aid in ("ca-20261026-180000-aaaa", "ca-20261026-180000-cccc", "ca-20261026-180000-bbbb"):
        put_answer(tree, item, "kept", answer_id=aid, answered_at="2026-10-26T18:00:00Z")
    assert [a["answer_id"] for a in view_of(c, item)["answers"]] == [
        "ca-20261026-180000-cccc", "ca-20261026-180000-bbbb", "ca-20261026-180000-aaaa"]


def test_waiting_for_a_name_is_shown_with_the_name_and_a_following_answer_continues_the_chain(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock, WITHDRAW)
    first = put_answer(tree, item, "waiting_for_a_name", answer_id="ca-20261026-180000-aaaa",
                       answered_at="2026-10-26T18:00:00Z")
    v = view_of(c, item)
    assert v["state"] == "waiting for a name · example_quantity"
    follow = put_answer(tree, item, "entered", answer_id="ca-20261026-190000-bbbb", answered_at="2026-10-26T19:00:00Z",
                        follows="librarian_agent/answers/ca-20261026-180000-aaaa.json")
    v = view_of(c, item)
    assert v["state"] == "Entered" and v["unreadable"] == []
    assert [a["answer_id"] for a in v["answers"]] == [follow["answer_id"], first["answer_id"]]


@pytest.mark.parametrize("why,make", [
    ("it does not match the request it names",
     lambda t, item: put_answer(t, item, "kept", sha="0" * 64)),
    ("it names a request that is not in the inbox",
     lambda t, item: put_answer(t, {**item, "item_id": "ci-20261026-000000-nope"}, "kept", sha="1" * 64)),
    ("it follows an answer that is not there",
     lambda t, item: put_answer(t, item, "entered", follows="librarian_agent/answers/ca-20261026-100000-gone.json")),
    ("it is not text the console can read as an answer",
     lambda t, item: put_answer(t, item, "kept", raw=b"\xff\xfe" + item["item_id"].encode() + b"\x00")),
    ("it is not text the console can read as an answer",
     lambda t, item: put_answer(t, item, "kept", raw=b'{"item_id": "' + item["item_id"].encode() + b'", ')),
])
def test_an_answer_that_cannot_be_read_makes_the_request_say_so_with_the_reason(client, tree, clock, why, make):
    c = client()
    item = the_request(c, tree, clock)
    make(tree, item)
    got = listing(c)
    named = next((v for v in got["requests"] if v["item_id"] == item["item_id"]), None)
    reasons = [u["reason"] for v in got["requests"] for u in v["unreadable"]] + [u["reason"] for u in got["orphans"]]
    assert why in reasons
    if "not in the inbox" not in why:
        assert named["state"] == UNREADABLE and any(u["reason"] == why for u in named["unreadable"])


def test_an_unreadable_answer_beats_a_readable_one_in_the_state(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock)
    put_answer(tree, item, "kept")
    put_answer(tree, item, "answered", sha="0" * 64, answered_at="2026-10-26T19:00:00Z")
    v = view_of(c, item)
    assert v["state"] == UNREADABLE and [a["outcome"] for a in v["answers"]] == ["kept"]


def test_an_answer_naming_no_request_in_the_inbox_is_listed_after_the_requests_as_unreadable(client, tree, clock):
    c = client()
    the_request(c, tree, clock)
    put_answer(tree, {"item_id": "ci-20261026-000000-nope"}, "kept", sha="1" * 64) if False else None
    ghost = {"item_id": "ci-20261026-000000-nope"}
    doc = {"artifact": "store_answer", "schema_version": "0.1", "answer_id": "ca-20261026-181000-gggg",
           "item_id": ghost["item_id"], "request_sha256": "2" * 64, "answered_by": "seat:librarian-20261026-1",
           "answered_at": "2026-10-26T18:10:00Z", "outcome": "kept", "reason": "r", "kb_version": "kbv-37b1958fb73d"}
    lib_answers(tree).mkdir(parents=True, exist_ok=True)
    (lib_answers(tree) / "ca-20261026-181000-gggg.json").write_text(json.dumps(doc), encoding="utf-8")
    got = listing(c)
    assert [(u["file"], u["reason"]) for u in got["orphans"]] == [
        ("ca-20261026-181000-gggg.json", "it names a request that is not in the inbox")]


def test_answers_are_taken_by_exact_name_only(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock)
    put_answer(tree, item, "kept", name="ca-a.json", answer_id="ca-20261026-180000-aaaa")
    put_answer(tree, item, "kept", name="ca-20261026-180000-bbbb.json.bak", answer_id="ca-20261026-180000-bbbb")
    put_answer(tree, item, "kept", name="ca-20261026-180000-cccc.json", answer_id="ca-20261026-180000-dddd")
    v = view_of(c, item)
    assert [a["answer_id"] for a in v["answers"]] == [] and len(v["unreadable"]) == 1
    assert v["unreadable"][0]["file"] == "ca-20261026-180000-cccc.json"
    assert v["unreadable"][0]["reason"] == "its name and its answer id differ"


def test_a_missing_answers_folder_means_no_answers_not_an_error(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock)
    assert not lib_answers(tree).exists()
    assert view_of(c, item)["state"] == NOT_ANSWERED and listing(c)["orphans"] == []


def test_the_real_tree_answers_route_reads_its_answers_folder(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock)
    put_answer(tree, item, "kept")
    put_answer(tree, item, "kept", sha="0" * 64, answered_at="2026-10-26T19:00:00Z")
    got = c.get("/api/library/answers").json()
    assert [a["outcome"] for a in got["answers"]] == ["kept"] and got["example"] is False


def test_the_console_changes_nothing_when_it_reads(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock, ADD, file=("spec.pdf", PDF))
    put_answer(tree, item, "kept")
    before = tree_hash(tree)
    listing(c)
    c.get("/api/library/answers")
    c.get(CARDS)
    assert tree_hash(tree) == before


# -- card 019's two readers, fixed ---------------------------------------------------------------------------------


def a_mic_item(root: Path, item_id="ci-20261026-090000-aaaa", qid="mic-20261026-c001") -> dict:
    doc = {"artifact": "console_question", "schema_version": "0.1", "item_id": item_id, "question_id": qid,
           "words": "old words", "asked_by": {"login": "member-1", "console_role": {
               "may_ask": True, "may_draft": True, "agents": ["microscope"], "may_ask_model_run": False}},
           "asked_at": "2026-10-26T09:00:00Z", "asker_mark": {"kind": "other_login"}, "attachments": []}
    (root / "microscope_agent" / "console_inbox" / f"{item_id}.json").write_text(json.dumps(doc), encoding="utf-8")
    return doc


def test_a_non_utf8_answer_naming_a_microscope_item_makes_its_state_unreadable(client, tree, clock):
    c = client()
    item = a_mic_item(tree)
    folder = tree / "microscope_agent" / "answers"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ca-20261026-120000-aaaa.json").write_bytes(
        b'{"item_id": "' + item["item_id"].encode() + b'", "reason": "\xff\xfe"}')
    card = next(i for i in c.get(CARDS).json()["items"] if i["item_id"] == item["item_id"])
    assert card["state"] == UNREADABLE


def test_a_non_utf8_answer_that_names_no_item_changes_no_state(client, tree, clock):
    c = client()
    item = a_mic_item(tree)
    folder = tree / "microscope_agent" / "answers"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ca-20261026-120000-aaaa.json").write_bytes(b"\xff\xfe nothing here")
    card = next(i for i in c.get(CARDS).json()["items"] if i["item_id"] == item["item_id"])
    assert card["state"] == "delivered · not answered yet"


@pytest.mark.parametrize("damage", [b"\xff\xfe\x00 not text", b'{"item_id": ', b'{"question_id": 5}',
                                    b'{"artifact": "console_question", "item_id": "x"}'])
def test_an_unreadable_item_in_an_inbox_refuses_the_next_delivery_and_writes_nothing(client, tree, clock, damage):
    c = client()
    (tree / "microscope_agent" / "console_inbox" / "ci-20261026-090000-aaaa.json").write_bytes(damage)
    before = tree_hash(tree)
    r = c.post(QUESTION, json={"words": "a question", "addressed_to": "microscope"})
    assert refusal(r) == (409, "inbox_unreadable")
    assert r.json()["detail"]["message"] == (
        "An item in this agent's inbox cannot be read, so the next question number cannot be told. "
        "Nothing was sent.")
    assert tree_hash(tree) == before and entries(outgoing_of(tree)) == []
    assert c.post(QUESTION, json={"words": "a question", "addressed_to": "simulation"}).status_code == 201


def test_a_file_that_is_not_named_like_an_item_does_not_stop_delivery(client, tree, clock):
    (tree / "microscope_agent" / "console_inbox" / "notes.json").write_bytes(b"\xff\xfe")
    assert client().post(QUESTION, json={"words": "a question", "addressed_to": "microscope"}).status_code == 201


# -- the mock store ---------------------------------------------------------------------------------------------------


def test_under_the_mock_only_the_write_dir_changes_and_the_shipped_sample_does_not(engine, make_client, tmp_path, clock):
    shipped = tree_hash(MOCK_DATA)
    write_dir = tmp_path / "practice"
    c = make_client(engine, agent_store=MockStore(write_dir, data_dir=MOCK_DATA))
    r = send(c, ADD, file=("spec.pdf", PDF))
    assert r.status_code == 201, r.text
    iid = r.json()["item_id"]
    assert (write_dir / "librarian_agent" / "console_inbox" / f"{iid}.json").is_file()
    assert (write_dir / "librarian_agent" / "console_inbox" / f"{iid}--spec.pdf").read_bytes() == PDF
    assert tree_hash(MOCK_DATA) == shipped


def test_the_sample_ships_nine_example_items_that_its_answers_name_and_everything_is_marked_example(engine, make_client, tmp_path):
    c = make_client(engine, agent_store=MockStore(tmp_path / "practice", data_dir=MOCK_DATA))
    got = listing(c)
    assert len(got["requests"]) == 9 and got["orphans"] == []
    assert all(v["example"] is True for v in got["requests"])
    assert all(v["unreadable"] == [] for v in got["requests"])
    states = {v["state"] for v in got["requests"]}
    assert "Entered" in states and "Not in the store" in states
    answers = c.get("/api/library/answers").json()["answers"]
    assert len(answers) == 10 and all(a["example"] is True for a in answers)
    waiting = next(v for v in got["requests"] if any(a["outcome"] == "waiting_for_a_name" for a in v["answers"]))
    assert [a["outcome"] for a in waiting["answers"]] == ["entered", "waiting_for_a_name"]
    assert waiting["state"] == "Entered"


def test_a_request_made_under_the_mock_is_not_marked_example(engine, make_client, tmp_path, clock):
    c = make_client(engine, agent_store=MockStore(tmp_path / "practice", data_dir=MOCK_DATA))
    r = send(c, ASK)
    assert r.status_code == 201
    v = next(v for v in listing(c)["requests"] if v["item_id"] == r.json()["item_id"])
    assert v["example"] is False and v["state"] == NOT_ANSWERED
    assert listing(c)["requests"][0]["item_id"] == v["item_id"]  # newest first, ahead of the 2026-10-20 examples


def test_the_server_side_outcome_words_are_the_screens(client):
    M = store_module()
    text = (Path(__file__).resolve().parents[2] / "web" / "src" / "features" / "library" / "answers.tsx").read_text("utf-8")
    web = dict(re.findall(r'^\s*(\w+):\s*"([^"]+)",?\s*$', text.split("OUTCOME_WORDS", 1)[1].split("};", 1)[0], re.M))
    assert web == M.OUTCOME_WORDS


# -- what the mutation checks found the tests above did not hold ------------------------------------------------------


@pytest.mark.parametrize("name", ["a b.pdf", "x" * 129, "ok.pdf/../x", "é.pdf", "-x.pdf", ".hidden", ""])
def test_a_file_name_is_judged_whole_not_by_its_first_characters(name):
    M = store_module()
    with pytest.raises(M.RequestError):
        M.decode_attached(name, b64(PDF))
    assert M.decode_attached("a" + "b" * 127, b64(PDF)).data == PDF


def test_base64_with_stray_characters_is_refused_and_not_cleaned_up(client, tree, clock):
    before = tree_hash(tree)
    r = client().post(SEND, json={"words": WORDS, "request": ADD,
                                  "file": {"name": "spec.pdf", "content_base64": b64(PDF) + "!!"}})
    assert r.status_code == 422 and tree_hash(tree) == before


def test_a_taken_item_name_after_the_files_link_removes_that_file_and_only_that_file(client, tree, clock):
    c = client()
    first = the_request(c, tree, clock)
    clock["suffixes"] = iter(["aaaa", "bbbb"])  # the first id comes up again, in the same second
    before = entries(lib_inbox(tree))
    r = send(c, ADD, file=("spec.pdf", PDF))
    assert r.status_code == 201 and r.json()["item_id"].endswith("-bbbb")
    assert not (lib_inbox(tree) / f"{first['item_id']}--spec.pdf").exists()
    iid = r.json()["item_id"]
    assert entries(lib_inbox(tree)) == sorted(before + [f"{iid}.json", f"{iid}--spec.pdf"])
    assert entries(outgoing_of(tree)) == []


def test_the_file_and_the_item_are_linked_while_the_lock_is_held(client, tree, clock, monkeypatch):
    M, I = store_module(), inbox_module()
    held = {"n": 0}

    class Lock:
        def __enter__(self):
            held["n"] += 1

        def __exit__(self, *exc):
            held["n"] -= 1

    monkeypatch.setattr(I, "_LOCK", Lock())
    real, seen = os.link, []

    def spy(src, dst, *a, **kw):
        seen.append(held["n"])
        return real(src, dst, *a, **kw)

    monkeypatch.setattr(M.os, "link", spy)
    assert send(client(), ADD, file=("spec.pdf", PDF)).status_code == 201
    assert len(seen) == 2 and all(n >= 1 for n in seen)


def reasons_of(c, item) -> list[str]:
    return [u["reason"] for u in view_of(c, item)["unreadable"]]


@pytest.mark.parametrize("kw", [{"kb_version": "not-a-version"}, {"unexpected": "x"}])
def test_an_answer_that_does_not_pass_the_answer_schema_is_unreadable(client, tree, clock, kw):
    c = client()
    item = the_request(c, tree, clock)
    put_answer(tree, item, "entered", **kw)
    v = view_of(c, item)
    assert v["answers"] == [] and v["state"] == UNREADABLE
    assert reasons_of(c, item) == ["it does not follow the form an answer takes"]


def test_an_answer_that_follows_an_answer_of_another_request_is_unreadable(client, tree, clock):
    c = client()
    one = the_request(c, tree, clock)
    two = the_request(c, tree, clock, words="another question")
    earlier = put_answer(tree, one, "waiting_for_a_name", answer_id="ca-20261026-180000-aaaa")
    put_answer(tree, two, "entered", answer_id="ca-20261026-190000-bbbb",
               follows=f"librarian_agent/answers/{earlier['answer_id']}.json")
    assert reasons_of(c, two) == ["it follows an answer that does not name the same request"]
    assert [a["answer_id"] for a in view_of(c, one)["answers"]] == [earlier["answer_id"]]


def a_file_in_the_inbox(tree, name: str, doc: dict) -> str:
    raw = json.dumps(doc, indent=2).encode("utf-8")
    (lib_inbox(tree) / name).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_an_answer_naming_a_file_that_is_not_a_request_is_not_a_request_in_the_inbox(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock)
    stem = "ci-20261026-190000-zzzz"
    sha = a_file_in_the_inbox(tree, f"{stem}.json", {**item, "artifact": "console_inbox_item", "item_id": stem})
    put_answer(tree, {"item_id": stem}, "kept", sha=sha)
    got = listing(c)
    assert [(u["reason"]) for u in got["orphans"]] == ["it names a request that is not in the inbox"]
    assert [r["item_id"] for r in got["requests"]] == [item["item_id"]]


def test_an_answer_naming_a_file_whose_item_id_is_another_name_is_not_a_request_in_the_inbox(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock)
    stem = "ci-20261026-190000-zzzz"
    sha = a_file_in_the_inbox(tree, f"{stem}.json", {**item, "item_id": "ci-20261026-190000-yyyy"})
    put_answer(tree, {"item_id": stem}, "kept", sha=sha)
    got = listing(c)
    assert [(u["reason"]) for u in got["orphans"]] == ["it names a request that is not in the inbox"]
    assert [r["item_id"] for r in got["requests"]] == [item["item_id"]]


def test_an_answer_with_a_byte_that_is_not_utf8_is_unreadable_even_where_the_byte_could_be_dropped(client, tree, clock):
    c = client()
    item = the_request(c, tree, clock)
    doc = put_answer(tree, item, "kept")
    path = lib_answers(tree) / f"{doc['answer_id']}.json"
    data = path.read_bytes()
    path.write_bytes(data[:1] + bytes([0xFF]) + data[1:])  # outside every string: dropping it would leave an answer
    v = view_of(c, item)
    assert v["answers"] == [] and v["state"] == UNREADABLE
    assert reasons_of(c, item) == ["it is not text the console can read as an answer"]


def test_an_outcome_the_console_has_no_words_for_is_shown_as_it_is_and_not_as_unanswered():
    assert store_module().state_of([{"outcome": "some_new_outcome"}], False) == "some_new_outcome"


def test_a_folder_named_earlier_keeps_its_item_over_a_later_ones(client, tree, clock, tmp_path):
    item = the_request(client(), tree, clock)
    other = tmp_path / "other"
    other.mkdir()
    (other / f"{item['item_id']}.json").write_text(
        json.dumps({**item, "words": "the later folder's words"}), encoding="utf-8")
    got = store_module().read_items([lib_inbox(tree), other])
    assert [r.doc["words"] for r in got] == [WORDS]
