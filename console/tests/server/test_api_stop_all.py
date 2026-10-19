"""`POST /api/console/runs/stop`: a stop on the lock screen that needs no login (console card 004,
the person at cee4f8c1: "a stop button on the console's lock screen that stops this project's runs
without logging in").

The words ask for a way to stop and for nothing else. These tests hold the route to three things
(section 15's holder, 2026-10-18): it sends only the pinned `stop_request`; it answers without a
login only on loopback; and it does one thing, so nothing else a request carries reaches a run.
And one guard on the person's words: no other write the app mounts works without a login.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import re
from pathlib import Path

import pytest
from server_fakes import OPERATOR, VIEWER
from sma_fake_run import FakeSmaRun, runs_dir, sma_tree

import sma_console.server.app as app_module
from sma_console.agents import SmaFiles, sma_run
from sma_console.agents.sma_files import repository_root
from sma_console.server.api import REFUSAL_HEADER
from sma_console.server.app import (
    AUTH_OPEN_PATHS,
    SETUP_ADMIN_PATH,
    SHUTDOWN_PATH,
    SMA_STOP_PATH,
    STOP_ALL_PATH,
)

SCHEMA = json.loads((repository_root() / "contracts" / "schemas" / "run_interface.schema.json")
                    .read_text(encoding="utf-8-sig"))["$defs"]


def conforms(raw: bytes, name: str = "stop_request") -> bool:
    """Whether `raw` is one line that the pinned schema `name` accepts. The console's
    environment has no jsonschema (its lock is resolved offline), so this reads the keywords
    this schema uses: one line within `x_max_bytes`, an object, `required`, `properties` with
    `type` and `pattern`, and `additionalProperties: false`."""
    spec = SCHEMA[name]
    if len(raw) > spec["x_max_bytes"] or not raw.endswith(b"\n") or b"\n" in raw[:-1]:
        return False
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        return False
    if not isinstance(data, dict) or not set(spec["required"]) <= set(data):
        return False
    if spec.get("additionalProperties") is False and set(data) - set(spec["properties"]):
        return False
    for key, rule in spec["properties"].items():
        if key in data:
            if rule.get("type") == "string" and not isinstance(data[key], str):
                return False
            if "pattern" in rule and not re.search(rule["pattern"], str(data[key])):
                return False
    return True


class RecordingRun(FakeSmaRun):
    """A fake followed run that keeps the raw bytes of every message its stop channel got."""

    def __init__(self, *args, **kwargs) -> None:
        self.raw: list[bytes] = []
        super().__init__(*args, **kwargs)

    def _stop(self, raw: bytes) -> bytes | None:
        self.raw.append(raw)
        return super()._stop(raw)

    @property
    def touched(self) -> int:
        """Connections its stop channel has accepted: 0 means nothing reached it."""
        return self.stop_server.connections


def refusal(r) -> tuple[int, str]:
    assert r.headers[REFUSAL_HEADER] == r.json()["detail"]["code"]
    return r.status_code, r.json()["detail"]["code"]


@pytest.fixture
def root(tmp_path):
    return sma_tree(tmp_path / "sma")


@pytest.fixture
def runs(root):
    """Two running runs and one that has ended."""
    a = RecordingRun(root, run_id="run-20261005-001")
    b = RecordingRun(root, run_id="run-20261005-002")
    done = RecordingRun(root, run_id="run-20261005-003")
    done.end("completed")
    yield a, b, done
    for r in (a, b, done):
        r.end()


@pytest.fixture
def client(engine, make_client, root):
    return lambda **kw: make_client(engine, agent_store=SmaFiles(root), **kw)


# -- what it sends ----------------------------------------------------------------------------


def test_the_checker_reads_the_pinned_schema():
    for example in SCHEMA["stop_request"]["examples"]:
        assert conforms(json.dumps(example).encode() + b"\n")
    for bad in SCHEMA["stop_request"]["x_refused"]:
        assert not conforms(json.dumps(bad).encode() + b"\n")
    good = {"stop": "run-20261005-001", "reason": "x"}
    assert conforms(json.dumps(good).encode() + b"\n")
    assert not conforms(json.dumps(good).encode())  # no newline
    assert not conforms(json.dumps({**good, "stop": "run-live-001"}).encode() + b"\n")  # the pattern
    assert not conforms(json.dumps({**good, "reason": "x" * 2000}).encode() + b"\n")  # too long


def test_without_a_login_on_loopback_each_running_run_gets_one_valid_stop(client, runs, seat):
    a, b, done = runs
    r = client(login=None).post(STOP_ALL_PATH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert sorted((x["run_id"], x["outcome"]) for x in body["runs"]) == [
        (a.run_id, "begun"), (b.run_id, "begun")]
    assert body["audited"] is True and "2 running runs found: 2 began to abort" in body["message"]
    for run in (a, b):
        assert len(run.raw) == 1 and conforms(run.raw[0])
        line = json.loads(run.raw[0])
        assert line["stop"] == run.run_id and set(line) == {"stop", "reason"}
        assert line["reason"] == ("the dino console: Stop all runs pressed "
                                  "(by the microscope PC (no login))")
        assert run.refused == [] and len(run.stops) == 1
    assert done.touched == 0 and done.raw == []  # the ended run's channel is closed and untouched
    audit = [e for e in seat.audit.entries() if e.get("command") == "sma_stop_all"]
    assert sorted(e["run_id"] for e in audit) == [a.run_id, b.run_id]
    assert all(e["outcome"] == "begun" and e["local"] is True
               and e["who"] == "the microscope PC (no login)" for e in audit)


def test_a_logged_in_operator_is_named_in_the_stop_and_the_audit(client, runs, seat):
    a, b, _ = runs
    r = client().post(STOP_ALL_PATH)
    assert r.status_code == 200 and len(r.json()["runs"]) == 2
    assert json.loads(a.raw[0])["reason"] == f"the dino console: Stop all runs pressed (by {OPERATOR})"
    audit = [e for e in seat.audit.entries() if e.get("command") == "sma_stop_all"]
    assert {e["who"] for e in audit} == {OPERATOR}


def test_nothing_running_says_so_and_sends_nothing(client, root, seat):
    gone = RecordingRun(root)
    gone.end("completed")
    r = client(login=None).post(STOP_ALL_PATH)
    assert r.status_code == 200
    assert r.json() == {"message": "No run is running. Nothing was sent.", "runs": [],
                        "audited": True}
    assert gone.touched == 0
    audit = [e for e in seat.audit.entries() if e.get("command") == "sma_stop_all"]
    assert [e["outcome"] for e in audit] == ["none_running"]


def test_a_crashed_run_is_reported_and_does_not_hold_up_a_live_one(client, root):
    live = RecordingRun(root, run_id="run-20261005-002")
    crashed = RecordingRun(root, run_id="run-20261005-001")
    crashed.stop_server.close()  # nobody listens, and the file never says run_ended
    try:
        r = client(login=None).post(STOP_ALL_PATH)
        assert r.status_code == 200
        outcomes = {x["run_id"]: x["outcome"] for x in r.json()["runs"]}
        assert outcomes == {live.run_id: "begun", crashed.run_id: "unreachable"}
        assert len(live.raw) == 1
    finally:
        live.end()
        crashed.end()


def test_the_stops_go_out_together_not_one_after_another(client, root):
    """Each run answers after 1.5 s (its abort turns lights off and reads them back), so sent
    one by one the second would wait 3 s for its stop. A stop that waits is a slower stop."""
    import time

    slow = [RecordingRun(root, run_id=f"run-20261005-00{n}", stop_reply_delay_s=1.5)
            for n in (1, 2)]
    try:
        began = time.monotonic()
        r = client(login=None).post(STOP_ALL_PATH)
        took = time.monotonic() - began
        assert r.status_code == 200 and [x["outcome"] for x in r.json()["runs"]] == ["begun"] * 2
        assert all(len(run.raw) == 1 for run in slow)
        assert took < 2.6, f"the two stops took {took:.1f} s: they were sent one after the other"
    finally:
        for run in slow:
            run.end()


def test_a_run_that_announced_no_stop_channel_is_named_and_nothing_is_sent(client, root):
    folder = runs_dir(root) / "run-20261005-009"
    folder.mkdir()
    (folder / "events.jsonl").write_text(json.dumps(
        {"event": "run_started", "run_id": "run-20261005-009", "plan_id": "p", "revision": 1,
         "t0_wall": "2026-10-05T10:00:00-07:00", "stop_channel": None, "frame_tap": None}) + "\n",
        encoding="utf-8")
    r = client(login=None).post(STOP_ALL_PATH)
    assert r.status_code == 200
    (only,) = r.json()["runs"]
    assert only["outcome"] == "no_channel" and "announced no stop channel" in only["message"]


def test_the_mock_store_says_it_is_not_connected(engine, make_client):
    r = make_client(engine, login=None).post(STOP_ALL_PATH)
    assert refusal(r) == (409, "not_connected")
    assert "--store sma" in r.json()["detail"]["message"]


def test_a_stop_is_not_held_back_by_the_audit_log(client, runs, seat, monkeypatch):
    a, b, _ = runs

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(seat.audit, "append", broken)
    r = client(login=None).post(STOP_ALL_PATH)
    assert r.status_code == 200 and r.json()["audited"] is False
    assert len(a.raw) == 1 and len(b.raw) == 1


# -- who may ask ------------------------------------------------------------------------------


def test_from_a_remote_address_without_a_login_it_is_refused(client, runs):
    a, b, _ = runs
    r = client(remote=True, remote_view=True, login=None).post(STOP_ALL_PATH)
    assert refusal(r) == (401, "login_required")
    assert a.touched == b.touched == 0


def test_a_logged_in_remote_viewer_may_stop_only_when_remote_abort_is_on(client, runs):
    a, b, _ = runs
    off = client(remote=True, remote_view=True, remote_abort=False, login=VIEWER)
    assert refusal(off.post(STOP_ALL_PATH)) == (403, "remote_view")
    assert a.touched == b.touched == 0
    on = client(remote=True, remote_view=True, remote_abort=True, login=VIEWER)
    r = on.post(STOP_ALL_PATH)
    assert r.status_code == 200 and len(r.json()["runs"]) == 2
    assert json.loads(a.raw[0])["reason"].endswith(f"(by {VIEWER})")


def test_a_page_from_another_origin_is_refused_before_anything_is_sent(client, runs):
    a, b, _ = runs
    r = client(login=None).post(STOP_ALL_PATH, headers={"Origin": "http://evil.example"})
    assert refusal(r) == (403, "foreign_origin")
    assert a.touched == b.touched == 0


# -- the route does one thing -----------------------------------------------------------------


@pytest.mark.parametrize("login", [None, OPERATOR], ids=["no-login", "logged-in"])
@pytest.mark.parametrize("kwargs", [
    {"json": {"run_id": "run-20261005-001"}},
    {"json": {"reason": "anything the server did not compose"}},
    {"json": {"stop": "run-20261005-001", "reason": "x"}},
    {"json": {"pause": True}},
    {"json": {}},
    {"json": []},
    {"content": b"x"},
    {"content": b"\n"},
    {"params": {"run_id": "run-20261005-001"}},
    {"params": {"reason": "x"}},
    {"params": {"x": "1"}, "json": {}},
], ids=["run_id", "reason", "the_pinned_line", "pause", "empty_object", "empty_list", "bytes",
        "newline", "query_run_id", "query_reason", "query_and_body"])
def test_anything_but_the_bare_stop_is_refused_and_reaches_no_run(client, runs, login, kwargs):
    a, b, _ = runs
    r = client(login=login).post(STOP_ALL_PATH, **kwargs)
    assert refusal(r) == (400, "stop_takes_nothing")
    assert a.touched == b.touched == 0 and a.raw == b.raw == []


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "DELETE"])
def test_another_method_without_a_login_is_refused_and_reaches_no_run(client, runs, method):
    a, b, _ = runs
    r = client(login=None).request(method, STOP_ALL_PATH)
    assert r.status_code == 401
    assert a.touched == b.touched == 0


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_another_method_with_a_login_finds_no_route(client, runs, method):
    a, b, _ = runs
    assert client().request(method, STOP_ALL_PATH).status_code == 405
    assert a.touched == b.touched == 0


def test_the_route_is_one_post_and_the_per_run_stop_is_unchanged(client, runs):
    """The new path does not capture the per-run stop, and the per-run stop does not capture it."""
    a, b, _ = runs
    mounted = [w for w in mounted_writes(client().app) if w[1].endswith("/runs/stop")]
    assert mounted == [("POST", STOP_ALL_PATH)]
    assert not SMA_STOP_PATH.match(STOP_ALL_PATH)
    r = client(login=None).post(f"/api/console/runs/microscope/{a.run_id}/stop", json={})
    assert r.status_code == 200 and len(a.raw) == 1 and b.raw == []


# -- the guard on the person's words ----------------------------------------------------------

#: The writes that work without a login today, as the person's words allow: the login and
#: setup paths, the shutdown from this PC, and the two stops. Taken here, once, from the
#: server's own tables, so a table that later grows does not quietly widen this list.
OPEN_WRITES = frozenset(AUTH_OPEN_PATHS) | {SETUP_ADMIN_PATH, SHUTDOWN_PATH, STOP_ALL_PATH}
WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def mounted_writes(app) -> list[tuple[str, str]]:
    """Every write the app mounts, from three sources that do not depend on FastAPI's internals:
    the app's own routes, each area router `include_area_routers` mounts, and the OpenAPI the app
    publishes. (This FastAPI keeps an included router lazy, so `app.routes` alone lists only the
    app's own writes.)"""
    found: set[tuple[str, str]] = set()

    def add(methods, path: str) -> None:
        for method in methods or ():
            if method.upper() in WRITE_METHODS:
                found.add((method.upper(), re.sub(r"\{[^}]+\}", "x", path)))

    for route in app.routes:
        add(getattr(route, "methods", None), getattr(route, "path", ""))
    api = importlib.import_module("sma_console.server.api")
    for info in pkgutil.iter_modules(api.__path__):
        if info.name.startswith("_") or info.ispkg:
            continue
        router = importlib.import_module(f"sma_console.server.api.{info.name}").router
        for route in router.routes:
            add(getattr(route, "methods", None), f"/api/{info.name}{route.path}")
    for path, operations in app.openapi()["paths"].items():
        add(operations, path)
    return sorted(found)


def open_writes(client) -> list[tuple[str, str]]:
    """Every mounted write that did NOT refuse a loopback request with no login."""
    opened = []
    for method, path in mounted_writes(client.app):
        if path in OPEN_WRITES or SMA_STOP_PATH.match(path):
            continue
        r = client.request(method, path, json={})
        if r.status_code not in (401, 403, 423):
            opened.append((method, path, r.status_code))  # type: ignore[arg-type]
    return opened


def test_no_other_write_the_app_mounts_works_without_a_login(client):
    c = client(login=None)
    writes = mounted_writes(c.app)
    assert len(writes) > 20 and ("POST", STOP_ALL_PATH) in writes
    assert open_writes(c) == []


def test_the_guard_fires_on_a_write_that_does_work_without_a_login(client, monkeypatch):
    c = client(login=None)

    @c.app.post("/api/zz/open")
    def open_write() -> dict:
        return {"ok": True}

    assert open_writes(c) == []  # the edge refuses a new write by default
    monkeypatch.setattr(app_module, "AUTH_OPEN_PATHS", frozenset({"/api/zz/open"}))
    assert open_writes(c) == [("POST", "/api/zz/open", 200)]


# -- the store's side -------------------------------------------------------------------------


def test_the_store_lists_only_running_runs_from_the_head_and_tail_of_the_file(root):
    a = RecordingRun(root, run_id="run-20261005-001")
    done = RecordingRun(root, run_id="run-20261005-002")
    done.end("failed")
    (runs_dir(root) / "run-20261005-005").mkdir()  # no events.jsonl
    try:
        found = SmaFiles(root).running_microscope_runs()
        assert [s.run_id for s in found] == [a.run_id]
    finally:
        a.end()


def test_edges_find_a_run_whose_file_is_too_big_to_open_whole(tmp_path):
    folder = tmp_path / "run-20261005-001"
    folder.mkdir()
    head = {"event": "run_started", "run_id": folder.name, "plan_id": "p", "revision": 1,
            "t0_wall": "2026-10-05T10:00:00-07:00",
            "stop_channel": {"host": "127.0.0.1", "port": 4242}, "frame_tap": None}
    rows = [head] + [{"event": "dispatch", "n": i, "pad": "x" * 40} for i in range(500)]
    path = folder / "events.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    with pytest.raises(sma_run.SmaRunError):
        sma_run.read_stream(folder, max_bytes=1000)  # over the cap: not opened whole
    running = sma_run.read_stream_edges(folder, tail_bytes=400)
    assert running.running and running.stop_channel == sma_run.Address("127.0.0.1", 4242)
    assert 0 < len(running.events) < 500  # the tail's complete lines only
    path.write_text(path.read_text(encoding="utf-8")
                    + json.dumps({"event": "run_ended", "how": "completed"}) + "\n", encoding="utf-8")
    ended = sma_run.read_stream_edges(folder, tail_bytes=400)
    assert not ended.running and ended.ended_how == "completed"


def test_edges_refuse_a_file_that_does_not_begin_with_run_started(tmp_path):
    folder = tmp_path / "run-x"
    folder.mkdir()
    (folder / "events.jsonl").write_text('{"event": "dispatch"}\n', encoding="utf-8")
    with pytest.raises(sma_run.NotFollowedError):
        sma_run.read_stream_edges(folder)
    with pytest.raises(sma_run.NotFollowedError):
        sma_run.read_stream_edges(tmp_path / "no-such-run")


def test_the_repository_root_used_here_is_this_repository():
    assert (Path(repository_root()) / "contracts" / "schemas" / "run_interface.schema.json").is_file()
