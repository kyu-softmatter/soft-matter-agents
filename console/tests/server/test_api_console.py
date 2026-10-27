"""Console router (T-100, docs/screens/console.md) over the T-008 mock store: reads for every
logged-in user, local or remote; the question submit for a local operator only (D16), and only
to a writable store."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from sma_console.agents import MockStore, SmaFiles
from sma_console.agents.mock_store import MOCK_DATA
from sma_console.server.api import REFUSAL_HEADER
from sma_console.server.api.console import READ_ONLY_MESSAGE

# the seeded fake accounts of conftest.py
ADMIN, OPERATOR, VIEWER = "ada", "otto", "vera"
SIM_QID = "sim-20260923-001"
SIM_RUN = "run-20260924-001-smoke-g2k2"
MIC_RUN = "run-20260924-003"


def refusal(r) -> tuple[int, str]:
    assert r.headers[REFUSAL_HEADER] == r.json()["detail"]["code"]
    return r.status_code, r.json()["detail"]["code"]


@pytest.fixture
def fresh_store(tmp_path):
    """A MockStore of its own, so writes do not leak into the shared one."""
    return MockStore(tmp_path / "practice")


@pytest.fixture
def read_only_store():
    return SmaFiles(MOCK_DATA, source="soft-matter-agents")


# -- reads ----------------------------------------------------------------------------------


def test_store_info(engine, make_client, read_only_store):
    mock = make_client(engine).get("/api/console/store").json()
    assert mock == {"store": "mock", "writable": True}
    c = make_client(engine, agent_store=read_only_store)
    assert c.get("/api/console/store").json() == {"store": "soft-matter-agents", "writable": True}


def test_questions_both_agents_or_one(engine, make_client):
    c = make_client(engine)
    both = c.get("/api/console/questions").json()
    assert {q["agent"] for q in both} == {"microscope", "simulation"}
    created = [q["created_at"] or "" for q in both]
    assert created == sorted(created, reverse=True)
    sim = c.get("/api/console/questions", params={"agent": "simulation"}).json()
    assert sim and {q["agent"] for q in sim} == {"simulation"}
    assert {"purpose", "intent", "observable_name"} <= set(sim[0])
    assert c.get("/api/console/questions", params={"agent": "nobody"}).status_code == 422


def test_question_versions_and_cards_pass_through(engine, make_client, agent_store):
    c = make_client(engine)
    latest = c.get(f"/api/console/questions/{SIM_QID}").json()
    versions = latest["summary"]["versions"]
    assert latest["version"] == latest["summary"]["latest_version"] == max(versions)
    assert len(versions) >= 3
    first = c.get(f"/api/console/questions/{SIM_QID}", params={"version": versions[0]}).json()
    assert first["version"] == versions[0]
    # the card's own content, grades included, as the store has it
    want = agent_store.get_question(SIM_QID, versions[0]).goal.data
    assert first["goal"]["data"] == want
    grades = [n["grade"] for n in first["goal"]["data"]["numbers"]]
    assert grades == [n["grade"] for n in want["numbers"]]


def test_unknown_question_version_and_run_are_404(engine, make_client):
    c = make_client(engine)
    for path, params in [("/api/console/questions/sim-20990101-001", {}),
                         (f"/api/console/questions/{SIM_QID}", {"version": 99}),
                         ("/api/console/runs/simulation/run-nope", {})]:
        r = c.get(path, params=params)
        assert refusal(r) == (404, "not_found"), path


def test_runs_and_run_detail(engine, make_client):
    c = make_client(engine)
    runs = c.get("/api/console/runs").json()
    pairs = {(r["agent"], r["run_id"]) for r in runs}
    assert pairs >= {("simulation", SIM_RUN), ("microscope", MIC_RUN)}
    assert all("approval_kind" in r for r in runs)
    only = c.get("/api/console/runs", params={"agent": "microscope"}).json()
    assert only and {r["agent"] for r in only} == {"microscope"} and MIC_RUN in {r["run_id"] for r in only}
    sim = c.get(f"/api/console/runs/simulation/{SIM_RUN}").json()
    assert {"config.json", "log.json", "observables.json"} <= set(sim["records"])
    mic = c.get(f"/api/console/runs/microscope/{MIC_RUN}").json()
    assert "no_plan_because" in mic["records"]["log.json"]


def test_inbox(engine, make_client):
    threads = make_client(engine).get("/api/console/inbox").json()
    assert threads and threads[0]["thread"].startswith("thr-")
    assert threads[0]["messages"]


def test_reads_work_for_a_remote_viewer(engine, make_client):
    c = make_client(engine, remote=True, remote_view=True, login=VIEWER)
    for path in ("/api/console/store", "/api/console/questions", "/api/console/runs",
                 "/api/console/inbox", f"/api/console/questions/{SIM_QID}"):
        assert c.get(path).status_code == 200, path


def test_reads_need_a_login(engine, make_client):
    r = make_client(engine, login=None).get("/api/console/questions")
    assert refusal(r) == (401, "login_required")


def test_openapi_has_the_console_models(engine, make_client):
    schema = make_client(engine).get("/openapi.json").json()
    assert "/api/console/questions/{qid}" in schema["paths"]
    assert {"QuestionDetailOut", "RunDetailOut", "InboxThreadOut", "StoreOut"} \
        <= set(schema["components"]["schemas"])


# -- the old submit is gone (card 010: a question is a request, see test_question_requests.py) --------


def test_the_old_question_post_is_gone(engine, make_client, fresh_store):
    c = make_client(engine, agent_store=fresh_store)
    r = c.post("/api/console/questions", json={"text": "q", "target": "microscope"})
    assert r.status_code in (404, 405)
    assert not fresh_store.write_dir.exists() or not any(fresh_store.write_dir.rglob("*.json"))


def test_a_store_that_cannot_write_requests_refuses_in_words(engine, make_client):
    c = make_client(engine, agent_store=SimpleNamespace(writable=False))
    r = c.post("/api/console/question-requests", json={"words": "q", "addressed_to": "microscope"})
    assert refusal(r) == (409, "read_only_store")
    assert r.json()["detail"]["message"] == READ_ONLY_MESSAGE


@pytest.mark.parametrize("agent", ["microscope", "simulation", "librarian"])
def test_a_store_that_has_inboxes_but_says_it_is_not_writable_is_refused_and_nothing_is_written(
        engine, make_client, fresh_store, agent):
    """The route's own check, apart from the check that the store has an inbox to write into."""
    fresh_store.writable = False
    c = make_client(engine, agent_store=fresh_store)
    r = c.post("/api/console/question-requests", json={"words": "q", "addressed_to": agent})
    assert refusal(r) == (409, "read_only_store")
    assert not fresh_store.write_dir.exists() or not any(p.is_file() for p in fresh_store.write_dir.rglob("*"))


def test_permissions_answer_submit_question(engine, make_client):
    ops = {"ops": "submit_question"}
    local = make_client(engine).get("/api/permissions", params=ops).json()
    assert local["submit_question"]["allowed"]
    viewer = make_client(engine, login=VIEWER).get("/api/permissions", params=ops).json()
    assert viewer["submit_question"]["allowed"] is False
    assert viewer["submit_question"]["code"] == "role"
    remote_client = make_client(engine, remote=True, remote_view=True)
    remote = remote_client.get("/api/permissions", params=ops).json()
    assert remote["submit_question"]["code"] == "remote_view"
