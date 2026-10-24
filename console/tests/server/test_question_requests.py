"""The question request (console card 010, plan.md 4.5): what the question window writes.

A request is `contracts/schemas/question_request.schema.json`, read from the repository and never a
copy. It is written into the console's own folder, `console/requests/questions/<id>.json`, and nothing
reaches an agent: no agent's folder, no inbox, no bridge is touched.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
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
POST = "/api/console/question-requests"
CARDS = "/api/console/question-cards"
SUGGEST = "/api/console/suggestions"
NOT_PICKED_UP = "request written · not picked up yet"


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


@pytest.fixture
def sma_root(tmp_path):
    """A copy of the sample as a soft-matter-agents tree, with its own contracts/quantities.json."""
    root = tmp_path / "sma"
    shutil.copytree(MOCK_DATA, root)
    shutil.rmtree(root / "console")  # the sample's practice requests: these tests start from none
    (root / "contracts").mkdir()
    (root / "contracts" / "quantities.json").write_text(
        json.dumps({"quantities": [{"id": "pixel_size"}, {"id": "refractive_index"}]}), encoding="utf-8")
    return root


@pytest.fixture
def sma_client(engine, make_client, sma_root):
    """A console over `--store sma` on that copy, logged in as the operator."""
    return lambda **kw: make_client(engine, agent_store=SmaFiles(sma_root, source="soft-matter-agents"), **kw)


def folder_of(root: Path) -> Path:
    return root / "console" / "requests" / "questions"


# -- the checker itself is watched to accept and to reject --------------------------------------------


def test_the_checker_accepts_the_repositorys_example_and_rejects_its_four_fixtures():
    assert SCHEMA_PATH == REPO / "contracts" / "schemas" / "question_request.schema.json"
    assert conforms(read(EXAMPLES / "question_request.json"))
    rejected = sorted((EXAMPLES / "rejected").glob("check01_question_request_*/question_request.json"))
    assert len(rejected) == 4
    for path in rejected:
        assert not conforms(read(path)), path.parent.name


# -- a written request ------------------------------------------------------------------------------


TYPED = "  Does the gel flow more easily\nafter it rests?  \n\n\"quoted\" μm — é\\  "


def test_a_request_is_written_exactly_in_the_schemas_shape(sma_client, sma_root):
    c = sma_client()
    r = c.post(POST, json={"words": TYPED, "addressed_to": "agents_decide"})
    assert r.status_code == 201, r.text
    files = written(folder_of(sma_root))
    assert len(files) == 1
    doc = json.loads(files[0].read_bytes().decode("utf-8"))
    assert problems(doc) == []  # against the repository's own schema
    assert files[0].name == doc["id"] + ".json"
    assert re.fullmatch(r"qr-\d{8}-\d{6}-[a-z0-9]{4}", doc["id"])
    assert r.json() == doc  # what the screen is told is what was written
    assert not files[0].read_bytes().startswith(b"\xef\xbb\xbf")


def test_the_words_are_byte_equal_to_what_was_typed(sma_client, sma_root):
    c = sma_client()
    c.post(POST, json={"words": TYPED, "addressed_to": "agents_decide"})
    doc = json.loads(written(folder_of(sma_root))[0].read_bytes().decode("utf-8"))
    assert doc["words"].encode("utf-8") == TYPED.encode("utf-8")
    assert doc["words"] != TYPED.strip()  # nothing trimmed, nothing rewritten


def test_no_key_outside_the_schema_and_no_claim_of_the_persons_own(sma_client, sma_root):
    sma_client().post(POST, json={"words": "q", "addressed_to": "librarian"})
    doc = json.loads(written(folder_of(sma_root))[0].read_text(encoding="utf-8"))
    spec = schema()
    assert set(doc) == set(spec["properties"])
    assert set(doc["asked_by"]) == {"login", "console_role"}
    assert set(doc["asked_by"]["console_role"]) == {"may_ask", "may_draft", "agents", "may_ask_model_run"}
    flat = json.dumps(doc).lower()
    assert "own" not in set(re.findall(r"[a-z_]+", flat)) and "person" not in flat


def test_a_request_with_an_extra_key_would_not_pass(sma_client, sma_root):
    sma_client().post(POST, json={"words": "q", "addressed_to": "microscope"})
    doc = json.loads(written(folder_of(sma_root))[0].read_text(encoding="utf-8"))
    assert problems({**doc, "persons_own": True})  # the checker would catch it
    assert problems({**doc, "asked_by": {**doc["asked_by"], "email": "a@b"}})


@pytest.mark.parametrize("target", ["agents_decide", "microscope", "simulation", "librarian"])
def test_the_ask_choice_is_addressed_to(sma_client, sma_root, target):
    r = sma_client().post(POST, json={"words": "q", "addressed_to": target})
    assert r.status_code == 201 and r.json()["addressed_to"] == target


@pytest.mark.parametrize("login", [OPERATOR, ADMIN])
def test_the_login_and_the_role_are_the_sessions_and_the_roles(sma_client, sma_root, login):
    r = sma_client(login=login).post(POST, json={"words": "q", "addressed_to": "agents_decide"})
    doc = r.json()
    assert doc["asked_by"]["login"] == login
    assert doc["asked_by"]["console_role"] == {
        "may_ask": True, "may_draft": True, "agents": ["microscope", "simulation", "librarian"],
        "may_ask_model_run": True}


def test_asked_at_is_utc_and_the_id_comes_from_the_same_instant(sma_client, monkeypatch):
    R = requests_module()
    monkeypatch.setattr(R, "utc_now", lambda: datetime(2026, 10, 24, 17, 45, 12, tzinfo=UTC))
    monkeypatch.setattr(R, "random_suffix", lambda: "k3p9")
    doc = sma_client().post(POST, json={"words": "q", "addressed_to": "agents_decide"}).json()
    assert doc["id"] == "qr-20261024-174512-k3p9" and doc["asked_at"] == "2026-10-24T17:45:12Z"


@pytest.mark.parametrize("body", [
    {"words": "", "addressed_to": "agents_decide"},
    {"words": "   \n ", "addressed_to": "agents_decide"},
    {"words": "x" * 4001, "addressed_to": "agents_decide"},
    {"words": "q", "addressed_to": "bridge"},
    {"words": "q"},
    {"addressed_to": "agents_decide"},
    {"words": "q", "addressed_to": "agents_decide", "purpose": "screen"},
    {"words": "q", "addressed_to": "agents_decide", "observable": "pixel_size"},
    {"words": "q", "addressed_to": "agents_decide", "persons_own": True},
])
def test_a_bad_body_is_refused_and_writes_nothing(sma_client, sma_root, body):
    r = sma_client().post(POST, json=body)
    assert r.status_code == 422, r.text
    assert written(folder_of(sma_root)) == []


def test_the_longest_allowed_words_are_written(sma_client, sma_root):
    r = sma_client().post(POST, json={"words": "x" * 4000, "addressed_to": "agents_decide"})
    assert r.status_code == 201 and problems(r.json()) == []


def test_a_lone_surrogate_is_refused_not_a_server_error(sma_client, sma_root):
    r = sma_client().post(POST, content='{"words": "a\\ud800b", "addressed_to": "agents_decide"}',
                          headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert written(folder_of(sma_root)) == []


# -- never rewritten, written atomically --------------------------------------------------------------


def test_an_existing_id_is_never_overwritten(sma_client, sma_root, monkeypatch):
    R = requests_module()
    monkeypatch.setattr(R, "utc_now", lambda: datetime(2026, 10, 24, 17, 45, 12, tzinfo=UTC))
    monkeypatch.setattr(R, "random_suffix", lambda: "k3p9")
    c = sma_client()
    assert c.post(POST, json={"words": "first", "addressed_to": "agents_decide"}).status_code == 201
    path = folder_of(sma_root) / "qr-20261024-174512-k3p9.json"
    before = path.read_bytes()
    r = c.post(POST, json={"words": "second", "addressed_to": "agents_decide"})
    assert refusal(r) == (409, "request_exists")
    assert path.read_bytes() == before
    assert written(folder_of(sma_root)) == [path]
    assert list(folder_of(sma_root).glob("*.tmp*")) == []


def test_a_taken_id_is_retried_with_another_suffix(sma_client, sma_root, monkeypatch):
    R = requests_module()
    monkeypatch.setattr(R, "utc_now", lambda: datetime(2026, 10, 24, 17, 45, 12, tzinfo=UTC))
    suffixes = iter(["aaaa", "aaaa", "bbbb"])
    monkeypatch.setattr(R, "random_suffix", lambda: next(suffixes))
    c = sma_client()
    first = c.post(POST, json={"words": "first", "addressed_to": "agents_decide"}).json()
    second = c.post(POST, json={"words": "second", "addressed_to": "agents_decide"}).json()
    assert (first["id"], second["id"]) == ("qr-20261024-174512-aaaa", "qr-20261024-174512-bbbb")
    assert {p.name for p in written(folder_of(sma_root))} == {first["id"] + ".json", second["id"] + ".json"}
    assert json.loads((folder_of(sma_root) / (first["id"] + ".json")).read_text("utf-8"))["words"] == "first"


def test_a_failed_write_leaves_no_file_and_no_temporary(sma_client, sma_root, monkeypatch):
    R = requests_module()

    def broken(*a, **k):
        raise OSError("disk says no")

    monkeypatch.setattr(R.os, "link", broken, raising=False)
    monkeypatch.setattr(R.os, "replace", broken, raising=False)
    r = sma_client().post(POST, json={"words": "q", "addressed_to": "agents_decide"})
    assert r.status_code == 500
    leftovers = [p for p in folder_of(sma_root).glob("*")] if folder_of(sma_root).is_dir() else []
    assert leftovers == []


def test_a_request_appears_whole_or_not_at_all(sma_client, sma_root, monkeypatch):
    """The final name is reached only by a link or rename of a finished file, never by writing to it."""
    R = requests_module()
    seen: list[bytes] = []
    real = R.os.link

    def link(src, dst, *a, **k):
        seen.append(Path(src).read_bytes())
        assert not Path(dst).exists()
        return real(src, dst, *a, **k)

    monkeypatch.setattr(R.os, "link", link)
    sma_client().post(POST, json={"words": "q", "addressed_to": "agents_decide"})
    assert len(seen) == 1 and problems(json.loads(seen[0])) == []


def test_the_writer_refuses_an_existing_file_by_itself(tmp_path):
    R = requests_module()
    folder = tmp_path / "console" / "requests" / "questions"
    doc = {"artifact": "question_request", "schema_version": "0.1", "id": "qr-20261024-174512-k3p9",
           "words": "w", "asked_by": {"login": "otto", "console_role": {
               "may_ask": True, "may_draft": True, "agents": [], "may_ask_model_run": False}},
           "asked_at": "2026-10-24T17:45:12Z", "addressed_to": "agents_decide"}
    path = R.write_request(folder, doc)
    assert path.name == "qr-20261024-174512-k3p9.json" and problems(json.loads(path.read_text("utf-8"))) == []
    before = path.read_bytes()
    with pytest.raises(R.RequestIdTaken):
        R.write_request(folder, {**doc, "words": "other"})
    assert path.read_bytes() == before


def test_the_builder_refuses_a_viewer_an_email_a_bad_choice_and_words_that_cannot_be_written():
    R = requests_module()
    now = datetime(2026, 10, 24, 17, 45, 12, tzinfo=UTC)
    base = dict(words="q", login="otto", role="operator", addressed_to="agents_decide", now=now, suffix="abcd")
    assert R.console_role_for("viewer") is None and R.console_role_for("operator") is not None
    assert problems(R.build_request(**base)) == []
    for bad in ({"role": "viewer"}, {"login": "otto@example.test"}, {"addressed_to": "bridge"}, {"words": " "},
                {"words": "x" * 4001}, {"words": "a" + chr(0xD800) + "b"}):
        with pytest.raises(R.RequestError):
            R.build_request(**{**base, **bad})


# -- who may send ------------------------------------------------------------------------------------


def test_a_viewer_cannot_send_and_is_told_in_words(sma_client, sma_root):
    r = sma_client(login=VIEWER).post(POST, json={"words": "q", "addressed_to": "agents_decide"})
    assert refusal(r) == (403, "role")
    assert "only look" in r.json()["detail"]["message"].lower() or "may not" in r.json()["detail"]["message"].lower()
    assert "submit_question" not in r.json()["detail"]["message"]
    assert written(folder_of(sma_root)) == []


def test_a_remote_browser_cannot_send_and_is_told_in_words(sma_client, sma_root):
    r = sma_client(remote=True).post(POST, json={"words": "q", "addressed_to": "agents_decide"})
    assert refusal(r) == (403, "remote_view")
    message = r.json()["detail"]["message"]
    # the access middleware answers first, in its own words; either way it names the microscope PC
    assert ("microscope PC" in message or "microscope computer" in message) and "submit_question" not in message
    assert written(folder_of(sma_root)) == []


def test_no_login_and_a_locked_login_cannot_send(sma_client, sma_root, seat):
    assert sma_client(login=None).post(POST, json={"words": "q", "addressed_to": "agents_decide"}).status_code == 401
    c = sma_client()
    seat.logins.lock(c.login_token)
    assert c.post(POST, json={"words": "q", "addressed_to": "agents_decide"}).status_code == 423
    assert written(folder_of(sma_root)) == []


def test_a_foreign_origin_cannot_send(sma_client, sma_root):
    r = sma_client().post(POST, json={"words": "q", "addressed_to": "agents_decide"},
                          headers={"origin": "https://example.com"})
    assert r.status_code == 403 and written(folder_of(sma_root)) == []


# -- the mock store: a practice copy, never the real tree ---------------------------------------------


def test_under_the_mock_store_nothing_is_written_into_the_real_tree(engine, make_client, tmp_path):
    store = MockStore(tmp_path / "practice")
    repo_before = {p: (p.stat().st_size, p.stat().st_mtime_ns)
                   for p in (REPO / "console" / "requests").rglob("*")} if (REPO / "console" / "requests").exists() else None
    sample_before = tree_hash(MOCK_DATA)
    c = make_client(engine, agent_store=store)
    r = c.post(POST, json={"words": "practice", "addressed_to": "agents_decide"})
    assert r.status_code == 201
    mine = folder_of(tmp_path / "practice")
    assert [p.name for p in written(mine)] == [r.json()["id"] + ".json"]
    assert tree_hash(MOCK_DATA) == sample_before  # the shipped sample is not written
    if repo_before is None:
        assert not (REPO / "console" / "requests").exists()
    else:
        assert {p: (p.stat().st_size, p.stat().st_mtime_ns)
                for p in (REPO / "console" / "requests").rglob("*")} == repo_before


def test_the_mock_store_without_a_folder_of_its_own_writes_into_a_temporary_one(engine, make_client):
    store = MockStore()
    try:
        r = make_client(engine, agent_store=store).post(POST, json={"words": "q", "addressed_to": "agents_decide"})
        assert r.status_code == 201
        assert store.write_dir.resolve() not in REPO.resolve().parents and REPO.resolve() not in store.write_dir.resolve().parents
        assert [p.name for p in written(folder_of(store.write_dir))] == [r.json()["id"] + ".json"]
    finally:
        store.close()


# -- nothing reaches an agent ----------------------------------------------------------------------


def test_no_agent_folder_inbox_or_bridge_is_touched(sma_client, sma_root):
    before = tree_hash(sma_root)
    r = sma_client().post(POST, json={"words": "q", "addressed_to": "microscope"})
    assert r.status_code == 201
    after = tree_hash(sma_root)
    new = set(after) - set(before)
    assert new == {f"console/requests/questions/{r.json()['id']}.json"}
    assert {k: v for k, v in after.items() if k in before} == before  # nothing else changed
    assert not any(p.startswith(("microscope_agent", "simulation_agent", "bridge", "librarian_agent")) for p in new)


def test_the_audit_line_names_the_request_and_not_its_words(sma_client, seat):
    r = sma_client().post(POST, json={"words": "a private-looking sentence", "addressed_to": "microscope"})
    line = [e for e in seat.audit.entries() if e["kind"] == "question_submitted"][-1]
    assert line["user_id"] == OPERATOR and line["request"] == r.json()["id"] and line["target"] == "microscope"
    assert "private-looking" not in json.dumps(line)


# -- autocomplete: only strings already on disk ------------------------------------------------------


def seed_request(root: Path, rid: str, words: str, at: str = "2026-10-20T09:00:00Z") -> None:
    folder_of(root).mkdir(parents=True, exist_ok=True)
    doc = {"artifact": "question_request", "schema_version": "0.1", "id": rid, "words": words,
           "asked_by": {"login": "member-1", "console_role": {
               "may_ask": True, "may_draft": True, "agents": ["microscope"], "may_ask_model_run": False}},
           "asked_at": at, "addressed_to": "agents_decide"}
    assert problems(doc) == []
    (folder_of(root) / f"{rid}.json").write_text(json.dumps(doc), encoding="utf-8")


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


def test_a_written_request_is_offered_afterwards_once(sma_client):
    c = sma_client()
    c.post(POST, json={"words": "Does it rest?", "addressed_to": "agents_decide"})
    c.post(POST, json={"words": "Does it rest?", "addressed_to": "agents_decide"})
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
    c = make_client(engine, agent_store=MockStore(tmp_path / "p"))
    offered = [s["text"] for s in c.get(SUGGEST).json() if s["kind"] == "earlier question"]
    assert offered == [read(f)["words"] for f in sorted(files, reverse=True)]
    shown = c.get(CARDS).json()["requests"]
    assert [r["id"] for r in shown] == [read(f)["id"] for f in sorted(files, reverse=True)]


def test_suggestions_need_a_login(sma_client):
    assert sma_client(login=None).get(SUGGEST).status_code == 401


# -- the cards below the field ------------------------------------------------------------------------


def test_requests_are_cards_not_picked_up_and_say_runs_wait_for_the_person(sma_client, sma_root):
    seed_request(sma_root, "qr-20261020-090000-aaaa", "older words", "2026-10-20T09:00:00Z")
    c = sma_client()
    mine = c.post(POST, json={"words": "newer words", "addressed_to": "simulation"}).json()
    got = c.get(CARDS).json()
    reqs = got["requests"]
    assert [r["words"] for r in reqs] == ["newer words", "older words"]
    assert reqs[0] == {
        "id": mine["id"], "words": "newer words", "login": OPERATOR, "asked_at": mine["asked_at"],
        "addressed_to": "simulation", "state": NOT_PICKED_UP, "runs_wait_for_signature": True}
    assert reqs[1]["login"] == "member-1" and reqs[1]["state"] == NOT_PICKED_UP


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
