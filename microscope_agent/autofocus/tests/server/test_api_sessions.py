"""`/api/sessions` (T-106) over T-019 stores in tmp_path: open, close, continue, refusals."""

from __future__ import annotations

import threading
from typing import Any

import pytest

from dino_autofocus.records import (
    AutoCommitter,
    CodeVersion,
    FolderStore,
    GitFolderStore,
    RecordsConfig,
    sample_state,
)

# the seeded fake accounts of tests/server/conftest.py (example.test only)
ADMIN, OPERATOR, OPERATOR2, VIEWER = (
    "admin@example.test", "otto@example.test", "olga@example.test", "vera@example.test")

SAMPLE = "20260930_1849_1"
STUB_CODE = CodeVersion("stub", "c" * 40, True)


class SessionEngine:
    """A minimal engine for the server: the runner's snapshot, session and sample hooks (T-011),
    and an always-yes `check()` (session actions are decided by the server, not the engine)."""

    def __init__(self, sample: str | None = SAMPLE, profile: str | None = None) -> None:
        self.sample = sample
        self.profile = profile
        self.session: dict | None = None
        self.session_calls: list[tuple[str | None, float | None]] = []
        self.picked: list[tuple[str, bool]] = []

    def submit(self, cmd: Any) -> str:
        return cmd.op_id or "op1"

    def subscribe(self, sink: Any):
        return lambda: None

    def shutdown(self, reason: str) -> None:
        pass

    def check(self, ops=None, context=None) -> dict:
        return {op: {"allowed": True, "reason": None} for op in ops or []}

    def set_local_viewers(self, count: int) -> None:
        pass

    def snapshot(self) -> dict[str, Any]:
        return {"positions": {"x_um": 1.0, "y_um": 2.0, "z_um": 3000.0}, "running": [],
                "backend_info": {"kind": "mock", "bench": False},
                "session": self.session,
                "sample": {"sample_id": self.sample, "reserved": False,
                           "session_id": (self.session or {}).get("session_id")},
                "hardware": {"profile": None, "profile_path": self.profile, "gates": {}}}

    def set_experiment_session(self, session_id, started_at=None) -> None:
        self.session_calls.append((session_id, started_at))
        self.session = {"session_id": session_id, "started_at": started_at} if session_id else None

    def set_current_sample(self, sample_id, *, reserved=False) -> None:
        self.picked.append((sample_id, reserved))
        self.sample = sample_id


@pytest.fixture
def store(tmp_path):
    return FolderStore(RecordsConfig(records_root=tmp_path / "records",
                                     data_root=tmp_path / "data"))


@pytest.fixture
def client(make_client, store):
    """`client(engine=None, **make_client_kwargs)`: the code version is preset (no git)."""

    def make(engine: SessionEngine | None = None, **kw):
        c = make_client(engine or SessionEngine(), records=kw.pop("records", store), **kw)
        c.app.state.records_code_version = STUB_CODE
        return c

    return make


def refusal(r) -> tuple[int, str]:
    return r.status_code, r.json()["detail"]["code"]


def test_open_for_the_current_sample(client, store, tmp_path):
    profile = tmp_path / "hardware_profile.json"
    profile.write_text('{"camera": "Kinetix_red"}')
    eng = SessionEngine(profile=str(profile))
    c = client(eng)
    r = c.post("/api/sessions")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["sample_id"] == SAMPLE and d["status"] == "open" and d["user_id"] == OPERATOR
    assert d["user_name"] == "Otto Operator"
    assert d["code"] == {"repo": "stub", "commit": "c" * 40, "dirty": True, "error": None}
    assert d["hardware_profile"]["path"] == str(profile)
    assert (d["backend_kind"], d["bench"]) == ("mock", False)  # T-106b, from the snapshot
    sid = d["session_id"]
    assert eng.session_calls[-1][0] == sid and isinstance(eng.session_calls[-1][1], float)
    assert c.app.state.sessions.session_for(sid) is not None
    assert sample_state(store, SAMPLE).n_events == 1  # sample_created, written once
    assert c.get("/api/sessions/current").json()["session_id"] == sid


def test_open_needs_a_current_sample_and_the_same_one(client):
    assert refusal(client(SessionEngine(sample=None)).post("/api/sessions")) == (409, "no_sample")
    r = client().post("/api/sessions", json={"sample_id": "other_sample"})
    assert refusal(r) == (409, "other_sample")
    msg = f"The current sample is {SAMPLE}; open other_sample first"
    assert r.json()["detail"]["message"] == msg
    assert client().post("/api/sessions", json={"sample_id": SAMPLE}).status_code == 201


def test_one_open_session_at_a_time(client):
    c = client()
    sid = c.post("/api/sessions").json()["session_id"]
    r = c.post("/api/sessions")
    assert refusal(r) == (409, "session_open") and sid in r.json()["detail"]["message"]


def test_list_filters_and_detail(client, store):
    eng = SessionEngine()
    c = client(eng)
    a = c.post("/api/sessions").json()["session_id"]
    c.app.state.sessions.current.record("scan_4x", {"tile": "r0c0"})
    c.post(f"/api/sessions/{a}/close", json={"note": "done"})
    eng.sample = "other"
    b = c.post("/api/sessions").json()["session_id"]
    assert [s["session_id"] for s in c.get("/api/sessions").json()] == [a, b]
    assert [s["session_id"] for s in c.get("/api/sessions?status=closed").json()] == [a]
    assert [s["session_id"] for s in c.get("/api/sessions?sample=other").json()] == [b]
    assert c.get(f"/api/sessions?user={OPERATOR2}").json() == []
    d = c.get(f"/api/sessions/{a}?log_tail=2").json()
    assert d["status"] == "closed" and d["close_note"] == "done" and len(d["log_tail"]) == 2
    assert d["records"] == [{"name": "sample_events.jsonl", "lines": 1},  # sample_created
                            {"name": "scan_4x.jsonl", "lines": 1}]
    assert d["manifest"] == {"files": 0, "bytes": 0, "by_where": {}, "entries": []}
    assert d["reflected"] is None  # no librarian ledger yet
    assert refusal(c.get("/api/sessions/nope")) == (404, "not_found")
    assert c.get("/api/sessions/..%2Fx").status_code == 404  # never reaches a folder


def test_close_owner_admin_and_read_only_after(client, make_client, log_in_as):
    eng = SessionEngine()
    c = client(eng)
    sid = c.post("/api/sessions").json()["session_id"]
    log_in_as(c, OPERATOR2)
    r = c.post(f"/api/sessions/{sid}/close")
    assert refusal(r) == (403, "not_owner")
    assert r.headers["X-DinoAF-Refusal"] == "not_owner"  # a plain 403, never remote_view
    log_in_as(c, ADMIN)
    r = c.post(f"/api/sessions/{sid}/close", json={"note": "admin closed it"})
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert eng.session_calls[-1] == (None, None)  # the engine hears the close
    assert c.app.state.sessions.current is None
    assert refusal(c.post(f"/api/sessions/{sid}/close")) == (409, "closed")
    assert c.get("/api/sessions/current").json() is None


def test_continue_reopens_the_same_sample(client):
    eng = SessionEngine()
    c = client(eng)
    a = c.post("/api/sessions").json()["session_id"]
    assert refusal(c.post(f"/api/sessions/{a}/continue")) == (409, "session_open")
    c.post(f"/api/sessions/{a}/close")
    eng.sample = "something_else"
    r = c.post(f"/api/sessions/{a}/continue")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["continues"] == a and d["sample_id"] == SAMPLE and d["status"] == "open"
    assert eng.picked == [(SAMPLE, True)]  # the sample is picked again; nothing moves


def test_sample_created_only_for_the_first_session(client, store):
    c = client()
    a = c.post("/api/sessions").json()["session_id"]
    c.post(f"/api/sessions/{a}/close")
    c.post(f"/api/sessions/{a}/continue")
    st = sample_state(store, SAMPLE)
    assert st.n_events == 1 and st.sessions == [a]


def test_who_may_write(client):
    c = client(remote=True)
    for path in ("/api/sessions", "/api/sessions/x/close", "/api/sessions/x/continue"):
        assert refusal(c.post(path)) == (403, "remote_view")
    assert c.get("/api/sessions").status_code == 200  # remote viewers read
    assert refusal(client(login=VIEWER).post("/api/sessions")) == (403, "role")
    assert client(login=None).post("/api/sessions").status_code == 401
    r = client().post("/api/sessions", headers={"Origin": "http://evil.example"})
    assert refusal(r) == (403, "foreign_origin")


def test_permissions_answer_the_session_ops(client):
    got = client(login=VIEWER).get(
        "/api/permissions?ops=session_open,session_close,session_continue").json()
    assert {v["allowed"] for v in got.values()} == {False}
    got = client().get("/api/permissions?ops=session_open").json()
    assert got["session_open"]["allowed"] is True


def test_no_records_store_is_503(make_client):
    c = make_client(SessionEngine())
    assert refusal(c.get("/api/sessions")) == (503, "no_records")


class GatedStore(GitFolderStore):
    def __init__(self, cfg, gate):
        super().__init__(cfg)
        self.gate = gate

    def commit(self, session_id, message, author):
        self.gate.wait(60)
        return super().commit(session_id, message, author)


def test_the_router_never_waits_on_git(client, tmp_path):
    gate = threading.Event()
    store = GatedStore(RecordsConfig(records_root=tmp_path / "git-records",
                                     data_root=tmp_path / "git-data"), gate)
    committer = AutoCommitter(store)
    c = client(records=store, committer=committer)  # create_app's committer (T-009e)
    try:
        r = c.post("/api/sessions")  # returns although every commit is blocked
        assert r.status_code == 201
        sid = r.json()["session_id"]
        assert c.post(f"/api/sessions/{sid}/close").status_code == 200
        assert not committer.flush(0.2)
        gate.set()
        assert committer.flush(60) and not committer.failures
        assert not store.uncommitted(f"microscope/sessions/{sid}")
    finally:
        gate.set()
        committer.stop()


def test_sessions_commit_through_the_app_committer(client, store):
    shared = AutoCommitter(store)
    c = client(committer=shared)
    try:
        sid = c.post("/api/sessions").json()["session_id"]
        assert c.app.state.sessions.session_for(sid).committer is shared
        assert c.post(f"/api/sessions/{sid}/close").status_code == 200
        assert shared.flush(30) and not shared.failures
    finally:
        shared.stop()


def test_without_an_app_committer_sessions_commit_inline(client):
    c = client()  # create_app(committer=None)
    sid = c.post("/api/sessions").json()["session_id"]
    assert c.app.state.sessions.session_for(sid).committer is None
    assert not hasattr(c.app.state, "records_committer")


def test_a_session_closed_by_a_restart_can_be_continued(client, store):
    from dino_autofocus.records import ExperimentSession

    left = ExperimentSession.open(store, OPERATOR, SAMPLE, code=STUB_CODE)  # crash: never closed
    eng = SessionEngine(sample=None)
    with client(eng) as c:  # the lifespan closes it at start-up (T-009e)
        d = c.get(f"/api/sessions/{left.session_id}").json()
        assert d["status"] == "closed" and d["close_note"] == "interrupted: server restart"
        assert c.get("/api/sessions/current").json() is None
        r = c.post(f"/api/sessions/{left.session_id}/continue")
        assert r.status_code == 201, r.text
        assert r.json()["continues"] == left.session_id and r.json()["sample_id"] == SAMPLE
