"""`/api/patterns` (card T-20261002-2205 stage 2): designs stored as files; nothing moves."""

from __future__ import annotations

import json

import pytest
from server_fakes import OPERATOR, VIEWER

BODY = {"name": "Circle", "loop": True, "tracks": [
    {"target": "piezo", "points": [[0, 0, 0, 0], [1, 5, 0, 0], [2, 0, 5, 0]]},
    {"target": "trap:0", "points": [[0, 1, 1, 0], [2, -1, -1, 0]]}]}


def refusal(r) -> tuple[int, str]:
    return r.status_code, r.json()["detail"]["code"]


@pytest.fixture
def client(engine, make_client, tmp_path):
    def make(**kw):
        kw.setdefault("patterns_root", tmp_path / "patterns")
        return make_client(engine, **kw)
    return make


def test_save_list_read_and_delete(client, tmp_path):
    c = client()
    r = c.post("/api/patterns/circle-1", json=BODY)
    assert r.status_code == 200, r.text
    got = r.json()
    assert (got["id"], got["duration_s"], got["meta"]["by"]) == ("circle-1", 2.0, OPERATOR)
    assert json.loads((tmp_path / "patterns" / "circle-1.json").read_text())["version"] == 1
    listed = c.get("/api/patterns").json()
    assert [(p["id"], p["targets"]) for p in listed] == [("circle-1", ["piezo", "trap:0"])]
    assert c.get("/api/patterns/circle-1").json()["tracks"][1]["points"][1] == [2, -1, -1, 0]
    again = c.post("/api/patterns/circle-1", json={**BODY, "name": "Renamed"}).json()
    assert again["meta"]["created_at"] == got["meta"]["created_at"]
    assert c.post("/api/patterns/circle-1/delete").status_code == 204
    assert refusal(c.get("/api/patterns/circle-1")) == (404, "not_found")
    assert refusal(c.post("/api/patterns/circle-1/delete")) == (404, "not_found")


def test_a_bad_pattern_is_refused_with_the_reason(client):
    bad = {"tracks": [{"target": "piezo", "points": [[0], [1, 500, 0, 0]]}]}
    r = client().post("/api/patterns/far", json=bad)
    assert refusal(r) == (422, "invalid_pattern")
    assert "provisional piezo" in r.json()["detail"]["message"]
    assert refusal(client().post("/api/patterns/Bad%20Id", json=BODY)) == (422, "invalid_pattern")
    assert refusal(client().post("/api/patterns/abc%0A", json=BODY)) == (422, "invalid_pattern")


def test_who_may_write(client):
    remote = client(remote=True)
    assert refusal(remote.post("/api/patterns/x", json=BODY)) == (403, "remote_view")
    assert remote.get("/api/patterns").status_code == 200  # remote viewers read
    assert refusal(client(login=VIEWER).post("/api/patterns/x", json=BODY)) == (403, "role")
    r = client(login=VIEWER).post("/api/patterns/x/delete")
    assert refusal(r) == (403, "role") and "pattern_delete" in r.json()["detail"]["message"]
    assert client(login=None).post("/api/patterns/x", json=BODY).status_code == 401
    r = client().post("/api/patterns/x", json=BODY, headers={"Origin": "http://evil.example"})
    assert refusal(r) == (403, "foreign_origin")


def test_without_a_pattern_folder_the_router_says_so(engine, make_client):
    assert refusal(make_client(engine).get("/api/patterns")) == (503, "no_patterns")
