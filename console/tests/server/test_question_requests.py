"""The question request (console card 010, plan.md 4.5), as the console reads it since card 022.

A request is `contracts/schemas/question_request.schema.json`, read from the repository and never a
copy. Nothing writes one any more: a question goes to the microscope, the simulation or the librarian
as an inbox item (`test_console_inbox.py`), and anything else is refused with nothing written. A
request an earlier console left in `console/requests/questions/` is still read: it shows as a card
"written in the console · not delivered", its words are still offered by autocomplete, and an addressee
the schema still allows (`agents_decide`) never makes the reader fail. Every test here runs in a
`tmp_path` tree.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from schema_check import SCHEMA_PATH, conforms, problems, read, schema
from server_fakes import ADMIN, OPERATOR, VIEWER

from sma_console.agents import MockStore, SmaFiles
from sma_console.agents.mock_store import MOCK_DATA
from sma_console.agents.sma_files import repository_root
from sma_console.server.api import REFUSAL_HEADER

REPO = repository_root()
EXAMPLES = REPO / "contracts" / "examples"
SCHEMAS = REPO / "contracts" / "schemas"
POST = "/api/console/question-requests"
CARDS = "/api/console/question-cards"
SUGGEST = "/api/console/suggestions"
NOT_DELIVERED = "written in the console · not delivered"
AGENTS = ("microscope", "simulation", "librarian")


def requests_module():
    import importlib

    return importlib.import_module("sma_console.agents.requests")


def tree_hash(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def written(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def refusal(r) -> tuple[int, str]:
    assert r.headers[REFUSAL_HEADER] == r.json()["detail"]["code"]
    return r.status_code, r.json()["detail"]["code"]


def audit_lines(seat) -> int:
    return len(list(seat.audit.entries()))


@pytest.fixture
def sma_root(tmp_path):
    """A copy of the sample as a soft-matter-agents tree, with its own contracts/quantities.json, the inbox
    schemas and an empty inbox for each of the three agents (so a delivery that should not happen would show)."""
    root = tmp_path / "sma"
    shutil.copytree(MOCK_DATA, root)
    shutil.rmtree(root / "console")  # the sample's practice requests: these tests start from none
    shutil.rmtree(root / "microscope_runtime")  # its runs and approvals: these tests write their own
    shutil.rmtree(root / "librarian_agent" / "console_inbox")  # its example requests and their answers
    shutil.rmtree(root / "librarian_agent" / "answers")
    (root / "contracts" / "schemas").mkdir(parents=True)
    for name in ("console_inbox_item.schema.json", "console_answer.schema.json",
                 "console_store_request.schema.json", "store_answer.schema.json"):
        shutil.copy(SCHEMAS / name, root / "contracts" / "schemas" / name)
    (root / "contracts" / "quantities.json").write_text(
        json.dumps({"quantities": [{"id": "pixel_size"}, {"id": "refractive_index"}]}), encoding="utf-8")
    for agent in AGENTS:
        inbox = root / f"{agent}_agent" / "console_inbox"
        inbox.mkdir(parents=True)
        (inbox / ".gitkeep").write_bytes(b"")
    return root


@pytest.fixture
def sma_client(engine, make_client, sma_root):
    """A console over `--store sma` on that copy, logged in as the operator."""
    return lambda **kw: make_client(engine, agent_store=SmaFiles(sma_root, source="soft-matter-agents"), **kw)


def folder_of(root: Path) -> Path:
    return root / "console" / "requests" / "questions"


def nothing_changed(root: Path, before: dict[str, str]) -> bool:
    """No file anywhere is new or different: no inbox item, nothing in the console's folder."""
    return tree_hash(root) == before and not (root / "console").exists()


def ask(c, agent: str = "microscope", words: str = "q"):
    return c.post(POST, json={"words": words, "addressed_to": agent})


# -- the checker itself is watched to accept and to reject --------------------------------------------


def test_the_checker_accepts_the_repositorys_example_and_rejects_its_four_fixtures():
    assert SCHEMA_PATH == REPO / "contracts" / "schemas" / "question_request.schema.json"
    assert conforms(read(EXAMPLES / "question_request.json"))
    rejected = sorted((EXAMPLES / "rejected").glob("check01_question_request_*/question_request.json"))
    assert len(rejected) == 4
    for path in rejected:
        assert not conforms(read(path)), path.parent.name


def test_a_request_with_an_extra_key_would_not_pass():
    doc = read(EXAMPLES / "question_request.json")
    assert problems(doc) == []
    assert problems({**doc, "persons_own": True})  # the checker would catch it
    assert problems({**doc, "asked_by": {**doc["asked_by"], "email": "a@b"}})


# -- nothing writes a request any more -----------------------------------------------------------------


def test_the_route_no_longer_has_a_request_to_write():
    R = requests_module()
    for gone in ("build_request", "write_request", "request_id", "RequestIdTaken"):
        assert not hasattr(R, gone), gone
    store = MockStore()
    try:
        assert not hasattr(store, "request_write_folder")
    finally:
        store.close()
    assert not hasattr(SmaFiles(Path(".")), "request_write_folder")


@pytest.mark.parametrize("agent", AGENTS)
def test_a_question_is_delivered_and_the_consoles_folder_is_not_touched(sma_client, sma_root, agent):
    before = tree_hash(sma_root)
    r = ask(sma_client(), agent)
    assert r.status_code == 201, r.text
    assert r.json()["artifact"] != "question_request"
    new = set(tree_hash(sma_root)) - set(before)
    assert len(new) == 1 and next(iter(new)).startswith(f"{agent}_agent/console_inbox/ci-")
    # the delivery's own temporary folder may stay, empty; no file and no request folder is made there
    assert not (sma_root / "console" / "requests" / "questions").exists()
    assert [f for f in (sma_root / "console").rglob("*") if f.is_file()] == []


@pytest.mark.parametrize("login", [OPERATOR, ADMIN])
def test_the_login_and_the_role_are_the_sessions_and_the_roles(sma_client, sma_root, login):
    r = ask(sma_client(login=login))
    assert r.status_code == 201, r.text
    asked_by = r.json()["asked_by"]
    assert asked_by["login"] == login
    assert asked_by["console_role"]["may_ask"] is True and asked_by["console_role"]["may_draft"] is True


def test_the_checker_of_the_asker_refuses_a_viewer_an_email_and_words_that_cannot_be_written():
    R = requests_module()
    base = dict(words="q", login="otto", role="operator")
    assert R.console_role_for("viewer") is None and R.console_role_for("operator") is not None
    assert R.check_asker(**base)["may_ask"] is True
    for bad in ({"role": "viewer"}, {"login": "otto@example.test"}, {"words": " "},
                {"words": "x" * 4001}, {"words": "a" + chr(0xD800) + "b"}):
        with pytest.raises(R.RequestError):
            R.check_asker(**{**base, **bad})


@pytest.mark.parametrize("body", [
    {"words": "", "addressed_to": "microscope"},
    {"words": "   \n ", "addressed_to": "microscope"},
    {"words": "x" * 4001, "addressed_to": "microscope"},
    {"words": "q", "addressed_to": "agents_decide"},
    {"words": "q", "addressed_to": "bridge"},
    {"words": "q", "addressed_to": ""},
    {"words": "q"},
    {"addressed_to": "microscope"},
    {"words": "q", "addressed_to": "microscope", "purpose": "screen"},
    {"words": "q", "addressed_to": "microscope", "observable": "pixel_size"},
    {"words": "q", "addressed_to": "microscope", "persons_own": True},
])
def test_a_bad_body_is_refused_and_writes_nothing(sma_client, sma_root, seat, body):
    c = sma_client()  # logging in is itself an audit line; the baseline is taken after it
    before, lines = tree_hash(sma_root), audit_lines(seat)
    r = c.post(POST, json=body)
    assert r.status_code == 422, r.text
    assert nothing_changed(sma_root, before) and audit_lines(seat) == lines


def test_the_longest_allowed_words_are_delivered(sma_client, sma_root):
    r = ask(sma_client(), "microscope", "x" * 4000)
    assert r.status_code == 201 and r.json()["words"] == "x" * 4000


def test_a_lone_surrogate_is_refused_not_a_server_error(sma_client, sma_root):
    before = tree_hash(sma_root)
    r = sma_client().post(POST, content='{"words": "a\\ud800b", "addressed_to": "microscope"}',
                          headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert nothing_changed(sma_root, before)


# -- who may send ------------------------------------------------------------------------------------


def test_a_viewer_cannot_send_and_is_told_in_words(sma_client, sma_root):
    before = tree_hash(sma_root)
    r = ask(sma_client(login=VIEWER))
    assert refusal(r) == (403, "role")
    assert "only look" in r.json()["detail"]["message"].lower() or "may not" in r.json()["detail"]["message"].lower()
    assert "submit_question" not in r.json()["detail"]["message"]
    assert nothing_changed(sma_root, before)


def test_a_remote_browser_cannot_send_and_is_told_in_words(sma_client, sma_root):
    before = tree_hash(sma_root)
    r = ask(sma_client(remote=True))
    assert refusal(r) == (403, "remote_view")
    message = r.json()["detail"]["message"]
    # the access middleware answers first, in its own words; either way it names the microscope PC
    assert ("microscope PC" in message or "microscope computer" in message) and "submit_question" not in message
    assert nothing_changed(sma_root, before)


def test_no_login_and_a_locked_login_cannot_send(sma_client, sma_root, seat):
    before = tree_hash(sma_root)
    assert ask(sma_client(login=None)).status_code == 401
    c = sma_client()
    seat.logins.lock(c.login_token)
    assert ask(c).status_code == 423
    assert nothing_changed(sma_root, before)


def test_a_foreign_origin_cannot_send(sma_client, sma_root):
    before = tree_hash(sma_root)
    r = sma_client().post(POST, json={"words": "q", "addressed_to": "microscope"},
                          headers={"origin": "https://example.com"})
    assert r.status_code == 403 and nothing_changed(sma_root, before)


# -- the mock store: it reads the shipped sample's requests and has nowhere to write one -----------------


def test_the_mock_store_reads_only_the_sample_for_requests(tmp_path):
    store = MockStore(tmp_path / "practice")
    assert store.request_folders() == [MOCK_DATA / "console" / "requests" / "questions"]
    assert not (tmp_path / "practice" / "console").exists()


def test_a_question_under_the_mock_store_writes_no_request_into_the_real_tree(engine, make_client, tmp_path):
    store = MockStore(tmp_path / "practice")
    repo_before = {p: (p.stat().st_size, p.stat().st_mtime_ns)
                   for p in (REPO / "console" / "requests").rglob("*")} if (REPO / "console" / "requests").exists() else None
    sample_before = tree_hash(MOCK_DATA)
    r = ask(make_client(engine, agent_store=store), "microscope", "practice")
    assert r.status_code == 201
    # the delivery's own temporary folder may stay, empty; no request is written there
    assert [f for f in (tmp_path / "practice" / "console").rglob("*") if f.is_file()] == []
    assert not (tmp_path / "practice" / "console" / "requests" / "questions").exists()
    assert tree_hash(MOCK_DATA) == sample_before  # the shipped sample is not written
    if repo_before is None:
        assert not (REPO / "console" / "requests").exists()
    else:
        assert {p: (p.stat().st_size, p.stat().st_mtime_ns)
                for p in (REPO / "console" / "requests").rglob("*")} == repo_before


# -- autocomplete: only strings already on disk ------------------------------------------------------


def seed_request(root: Path, rid: str, words: str, at: str = "2026-10-20T09:00:00Z",
                 addressed_to: str = "agents_decide") -> None:
    """A request an earlier console left in its own folder (nothing writes one now)."""
    folder_of(root).mkdir(parents=True, exist_ok=True)
    doc = {"artifact": "question_request", "schema_version": "0.1", "id": rid, "words": words,
           "asked_by": {"login": "member-1", "console_role": {
               "may_ask": True, "may_draft": True, "agents": ["microscope"], "may_ask_model_run": False}},
           "asked_at": at, "addressed_to": addressed_to}
    assert problems(doc) == []
    (folder_of(root) / f"{rid}.json").write_text(json.dumps(doc), encoding="utf-8")


def schema_addressees() -> list[str]:
    return list(schema()["properties"]["addressed_to"]["enum"])


def test_an_empty_disk_offers_nothing(engine, make_client, tmp_path):
    root = tmp_path / "empty"
    (root / "microscope_agent").mkdir(parents=True)
    c = make_client(engine, agent_store=SmaFiles(root, source="soft-matter-agents"))
    r = c.get(SUGGEST)
    assert r.status_code == 200 and r.json() == []


def test_it_offers_earlier_words_and_registered_names_each_labelled(sma_client, sma_root):
    seed_request(sma_root, "qr-20261020-090000-aaaa", "How long does the gel keep flowing?", "2026-10-20T09:00:00Z")
    seed_request(sma_root, "qr-20261021-090000-bbbb", "Is the bead stuck?", "2026-10-21T09:00:00Z")
    got = sma_client().get(SUGGEST).json()
    assert got == [
        {"text": "Is the bead stuck?", "kind": "earlier question"},
        {"text": "How long does the gel keep flowing?", "kind": "earlier question"},
        {"text": "pixel_size", "kind": "registered name"},
        {"text": "refractive_index", "kind": "registered name"},
    ]


def test_it_offers_nothing_else_not_the_stores_titles_or_contents(sma_client, sma_root):
    got = sma_client().get(SUGGEST).json()
    texts = " ".join(s["text"] for s in got)
    store = SmaFiles(sma_root, source="soft-matter-agents")
    for q in store.list_questions("simulation") + store.list_questions("microscope"):
        assert q.title not in texts and q.qid not in texts
    assert {s["kind"] for s in got} <= {"earlier question", "registered name"}


def test_a_delivered_question_is_offered_afterwards_once(sma_client):
    c = sma_client()
    ask(c, "microscope", "Does it rest?")
    ask(c, "microscope", "Does it rest?")
    got = [s for s in c.get(SUGGEST).json() if s["kind"] == "earlier question"]
    assert got == [{"text": "Does it rest?", "kind": "earlier question"}]


def test_a_file_that_is_not_a_request_is_not_offered(sma_client, sma_root):
    folder_of(sma_root).mkdir(parents=True)
    (folder_of(sma_root) / "notes.json").write_text(json.dumps({"words": "sneaky"}), encoding="utf-8")
    (folder_of(sma_root) / "broken.json").write_text("{not json", encoding="utf-8")
    (folder_of(sma_root) / "qr-20261020-090000-zzzz.json").write_text(
        json.dumps({"artifact": "something_else", "words": "also sneaky"}), encoding="utf-8")
    texts = [s["text"] for s in sma_client().get(SUGGEST).json()]
    assert "sneaky" not in texts and "also sneaky" not in texts


def test_the_mock_store_offers_the_repositorys_registered_names(engine, make_client, tmp_path):
    names = [q["id"] for q in json.loads((REPO / "contracts" / "quantities.json").read_text("utf-8"))["quantities"]]
    got = make_client(engine, agent_store=MockStore(tmp_path / "p")).get(SUGGEST).json()
    assert [s["text"] for s in got if s["kind"] == "registered name"] == names


def test_the_mock_sample_has_valid_practice_requests_that_are_offered_and_shown(engine, make_client, tmp_path):
    sample = MOCK_DATA / "console" / "requests" / "questions"
    files = sorted(sample.glob("*.json"))
    assert len(files) == 2
    for f in files:
        assert problems(read(f)) == [] and f.stem == read(f)["id"]
    assert "agents_decide" in {read(f)["addressed_to"] for f in files}  # the sample keeps an earlier console's request
    c = make_client(engine, agent_store=MockStore(tmp_path / "p"))
    offered = [s["text"] for s in c.get(SUGGEST).json() if s["kind"] == "earlier question"]
    assert {read(f)["words"] for f in files} <= set(offered)  # and the words of the sample's delivered examples
    shown = c.get(CARDS).json()["requests"]
    assert [r["id"] for r in shown] == [read(f)["id"] for f in sorted(files, reverse=True)]


def test_suggestions_need_a_login(sma_client):
    assert sma_client(login=None).get(SUGGEST).status_code == 401


# -- earlier requests are still read, whatever addressee the schema allows ------------------------------


def test_the_schema_still_allows_an_addressee_the_console_no_longer_offers():
    assert "agents_decide" in schema_addressees() and set(schema_addressees()) >= set(AGENTS)


@pytest.mark.parametrize("addressee", schema_addressees())
def test_an_earlier_request_to_any_addressee_the_schema_allows_is_still_a_card(sma_client, sma_root, addressee):
    seed_request(sma_root, "qr-20261020-090000-aaaa", "older words for the agents", addressed_to=addressee)
    c = sma_client()
    r = c.get(CARDS)
    assert r.status_code == 200, r.text
    (card,) = r.json()["requests"]
    assert card["state"] == NOT_DELIVERED and card["addressed_to"] == addressee
    assert card["runs_wait_for_signature"] is True and card["words"] == "older words for the agents"
    offered = [s["text"] for s in c.get(SUGGEST).json() if s["kind"] == "earlier question"]
    assert offered == ["older words for the agents"]


# -- the cards below the field ------------------------------------------------------------------------


def test_requests_are_cards_not_delivered_and_say_runs_wait_for_the_person(sma_client, sma_root):
    seed_request(sma_root, "qr-20261020-090000-aaaa", "older words", "2026-10-20T09:00:00Z")
    seed_request(sma_root, "qr-20261022-090000-bbbb", "newer words", "2026-10-22T09:00:00Z", "microscope")
    got = sma_client().get(CARDS).json()
    reqs = got["requests"]
    assert [r["words"] for r in reqs] == ["newer words", "older words"]
    assert reqs[0] == {
        "id": "qr-20261022-090000-bbbb", "words": "newer words", "login": "member-1",
        "asked_at": "2026-10-22T09:00:00Z", "addressed_to": "microscope", "state": NOT_DELIVERED,
        "runs_wait_for_signature": True}
    assert reqs[1]["addressed_to"] == "agents_decide" and reqs[1]["state"] == NOT_DELIVERED


def steps(c, qid):
    q = next(q for q in c.get(CARDS).json()["questions"] if q["qid"] == qid)
    return [q["steps"][k] for k in ("asked", "designed", "signed", "run", "result")], q


def test_the_five_steps_read_the_right_files(sma_client, sma_root):
    c = sma_client()
    mic = "mic-20260925-001"
    qdir = sma_root / "microscope_agent" / "questions" / mic
    # the sample: a goal card and a result card, no plan
    got, q = steps(c, mic)
    assert got == [True, False, False, False, True]
    assert q["agent"] == "microscope" and q["title"]
    # no result card -> not done
    result = qdir / "result_well_occupancy.json"
    saved = result.read_bytes()
    result.unlink()
    assert steps(c, mic)[0] == [True, False, False, False, False]
    result.write_bytes(saved)
    # no goal card -> not asked
    goal = qdir / "goal.json"
    saved_goal = goal.read_bytes()
    goal.unlink()
    assert steps(c, mic)[0][0] is False
    goal.write_bytes(saved_goal)
    # a plan card -> designed
    plan = json.loads((sma_root / "microscope_agent/questions/mic-20260925-002/plan_microscope_mic-20260925-002.json")
                      .read_text("utf-8"))
    plan["qid"] = mic
    (qdir / f"plan_microscope_{mic}.json").write_text(json.dumps(plan), encoding="utf-8")
    assert steps(c, mic)[0] == [True, True, False, False, True]
    # an approval for another plan's hash -> not signed; for this plan's hash -> signed
    from sma_console.agents.sma_files import plan_hash

    appr = sma_root / "microscope_agent" / "approvals"
    appr.mkdir()

    def approval(h, status="APPROVED"):
        (appr / f"appr-{mic}-r1.json").write_text(json.dumps({
            "card": "plan_approval", "id": f"appr-{mic}-r1", "qid": mic, "revision": 1, "status": status,
            "plan_id": f"plan-{mic}-r1", "plan_revision": 1, "plan_hash": h, "approved_by": "someone",
            "approved_at": "2026-10-24T10:00:00Z"}), encoding="utf-8")

    approval("sha256:" + "0" * 64)
    assert steps(c, mic)[0][2] is False
    approval(plan_hash(plan), status="DRAFT")  # a card that is not an approval of it
    assert steps(c, mic)[0][2] is False
    approval(plan_hash(plan))
    assert steps(c, mic)[0] == [True, True, True, False, True]
    # a run log for it -> run
    run = sma_root / "microscope_agent" / "runs" / "run-20261024-001"
    run.mkdir(parents=True)
    (run / "log.json").write_text(json.dumps({"run_id": "run-20261024-001", "qid": mic}), encoding="utf-8")
    assert steps(c, mic)[0] == [True, True, True, True, True]


def test_a_run_of_another_question_does_not_count(sma_client, sma_root):
    c = sma_client()
    run = sma_root / "microscope_agent" / "runs" / "run-20261024-001"
    run.mkdir(parents=True)
    (run / "log.json").write_text(json.dumps({"run_id": "run-20261024-001", "qid": "mic-20260925-002"}), encoding="utf-8")
    assert steps(c, "mic-20260925-001")[0][3] is False
    assert steps(c, "mic-20260925-002")[0][3] is True


def test_a_question_with_a_plan_and_no_goal_is_designed_but_not_asked(sma_client):
    got, _ = steps(sma_client(), "mic-20260925-002")
    assert got[:2] == [False, True]


def test_the_cards_need_a_login_and_write_nothing(sma_client, sma_root):
    before = tree_hash(sma_root)
    assert sma_client(login=None).get(CARDS).status_code == 401
    assert sma_client().get(CARDS).status_code == 200
    assert tree_hash(sma_root) == before


def test_a_runs_folder_that_is_not_there_does_not_hide_the_questions(engine, make_client, tmp_path):
    root = tmp_path / "tree"
    q = root / "microscope_agent" / "questions" / "mic-20261024-001"
    q.mkdir(parents=True)
    (q / "goal.json").write_text(json.dumps({"card": "goal", "qid": "mic-20261024-001"}), encoding="utf-8")
    c = make_client(engine, agent_store=SmaFiles(root, source="soft-matter-agents"))
    r = c.get(CARDS)
    assert r.status_code == 200
    q = r.json()["questions"][0]
    assert q["steps"]["asked"] is True and q["steps"]["run"] is False
    assert q["steps"]["run_known"] is False  # the runs could not be seen: not "no run"
