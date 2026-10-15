"""The `sample` area router (T-103, docs/screens/sample.md): reads through the engine's one
sample view, the sample-specific access facts, and "Open folder" with an injected opener.

The engine is the real T-011 runner, never started, with a folder records store and a copy
of a small legacy sample folder; nothing touches hardware, git or Explorer."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from dino_autofocus.engine import sample as es
from dino_autofocus.engine.operations import sample_ops
from dino_autofocus.engine.runner import Runner, RunnerConfig
from dino_autofocus.records import FolderStore, RecordsConfig
from dino_autofocus.records.session import ExperimentSession
from dino_autofocus.server.api import REFUSAL_HEADER

FIXTURES = Path(__file__).parent / "fixtures" / "sample"
LEGACY = "20260930_1849_1"
NEW = "20261001_0930_1"


@pytest.fixture(autouse=True)
def no_explorer(monkeypatch):
    """Belt and braces: if any path reached the real opener, it would fail loudly."""

    def refuse(*_a, **_k):
        raise AssertionError("a test tried to open Explorer")

    monkeypatch.setattr(os, "startfile", refuse, raising=False)


@pytest.fixture
def runner():
    return Runner(object(), config=RunnerConfig(position_interval_s=None))


@pytest.fixture
def records(tmp_path):
    return FolderStore(
        RecordsConfig(records_root=tmp_path / "records", data_root=tmp_path / "data")
    )


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "samples"
    shutil.copytree(FIXTURES, r)
    return r


@pytest.fixture
def opened():
    return []


@pytest.fixture
def client_for(make_client, runner, records, root, opened):
    def make(**kw):
        c = make_client(runner, records=records, samples_root=root, **kw)
        c.app.state.open_folder = opened.append  # the recorder: tests never open a window
        return c

    return make


@pytest.fixture
def client(client_for):
    return client_for()


def open_session(
    client, records, tmp_path, sample_id: str, user: str = "otto"
) -> ExperimentSession:
    """Open an experiment session as the sessions router would, without touching git."""
    (tmp_path / "no-repo").mkdir(exist_ok=True)
    s = ExperimentSession.open(records, user, sample_id, code_repo=tmp_path / "no-repo")
    sample_ops.ensure_sample_created(s, records)
    client.app.state.sessions.set(s)
    return s


def refusal(r, status: int, code: str) -> str:
    assert r.status_code == status, r.text
    assert r.headers[REFUSAL_HEADER] == code
    assert r.json()["detail"]["code"] == code
    return r.json()["detail"]["message"]


# -- reads ----------------------------------------------------------------------------------------


def test_geometry_fields_are_the_engine_list(client):
    got = client.get("/api/sample/geometry-fields").json()
    assert [f["key"] for f in got] == [f.key for f in es.GEOMETRY_FIELDS]
    assert [f["key"] for f in got if f["safety"]] == list(es.SAFETY_KEYS)
    size = next(f for f in got if f["key"] == "sample_size_mm")
    assert size["kind"] == "pair" and size["default"] == [24.0, 50.0]
    assert next(f for f in got if f["key"] == "orientation")["default"] is None


def test_list_has_legacy_session_and_reserved_samples_newest_first(client, records, root, tmp_path):
    open_session(client, records, tmp_path, NEW)
    reserved = es.Sample.create(root).id  # what sample_new leaves: an id and a folder, no event
    got = client.get("/api/sample/list").json()
    by_id = {s["sample_id"]: s for s in got}
    assert set(by_id) == {LEGACY, NEW, reserved}
    assert by_id[LEGACY]["created"] == "2026-09-30T18:49:12"  # from the legacy sample.json
    assert by_id[LEGACY]["objectives_used"] == ["4x", "100x"]
    assert by_id[NEW]["reserved"] is False and by_id[NEW]["last_session"]["session_id"]
    assert by_id[reserved]["reserved"] is True and by_id[reserved]["created"]  # from the folder
    assert by_id[reserved]["last_session"] is None and by_id[reserved]["objectives_used"] == []
    created = [s["created"] for s in got]
    assert created == sorted(created, reverse=True)


def test_detail_hole_status_is_the_engines_text(client, root):
    d = client.get(f"/api/sample/{LEGACY}").json()
    assert d["dir"] == str(root / LEGACY)
    assert d["hole"]["diameter_mm"] == 6.02 and d["hole"]["fitted_at"] == "2026-09-30T19:10:05"
    assert d["hole"]["status"] == "arc 352 deg >= 330 deg"  # engine.sample.hole_loop, as is
    assert d["closed_loop"] is True
    assert d["counts"] == {"flags": 0, "candidates": 0, "visits": 0, "boundary_points": 0}


def test_counts_leave_out_retired_flags(client, records, tmp_path):
    s = open_session(client, records, tmp_path, NEW)
    for fid in ("f1", "f2"):
        s.sample_event("flag_set", flag_id=fid, name=fid, note="", x_um=1.0, y_um=2.0,
                       objective="4x")
    s.sample_event("flag_remove", flag_id="f1")
    assert client.get(f"/api/sample/{NEW}").json()["counts"]["flags"] == 1


def test_geometry_sources_default_not_set_and_entered(client, records, tmp_path):
    s = open_session(client, records, tmp_path, NEW)
    g = client.get(f"/api/sample/{NEW}/geometry").json()["values"]
    assert g["coverslip_thickness_um"] == {
        "value": 170.0,
        "source": {"kind": "default", "by": None, "t": None},
    }
    assert g["sample_thickness_um"]["source"]["kind"] == "not_set"
    s.sample_event(es.GEOMETRY_SET, values={"sample_thickness_um": 120.0, "orientation": "upright"})
    g = client.get(f"/api/sample/{NEW}/geometry").json()["values"]
    assert g["sample_thickness_um"]["value"] == 120.0
    assert (
        g["orientation"]["source"]["kind"] == "entered"
        and g["orientation"]["source"]["by"] == "otto"
    )


def test_loading_state_counts_only_in_this_samples_session(client, records, tmp_path):
    empty = client.get(f"/api/sample/{LEGACY}/loading").json()
    assert empty["session_id"] is None and empty["confirmed"] is False
    assert not empty["person"]["done"] and not empty["image"]["done"]

    s = open_session(client, records, tmp_path, NEW)
    s.sample_event(es.GEOMETRY_SET, values={"sample_thickness_um": 120.0, "orientation": "upright"})
    s.sample_event(es.LOADING_STEP, step="person", ok=True)
    got = client.get(f"/api/sample/{NEW}/loading").json()
    assert got["session_id"] == s.session_id
    assert got["geometry"]["done"] and got["person"]["done"] and not got["image"]["done"]
    assert got["confirmed"] is False  # never from two steps
    s.sample_event(
        es.LOADING_STEP, step="image", ok=True, why="", result_ref="loading_check/frame_0001.npy"
    )
    got = client.get(f"/api/sample/{NEW}/loading").json()
    assert got["image"] == {
        "done": True,
        "ok": True,
        "by": "otto",
        "t": got["image"]["t"],
        "why": "",
        "result_ref": "loading_check/frame_0001.npy",
    }
    assert got["confirmed"] is True
    # another sample's view does not borrow this session's steps
    assert client.get(f"/api/sample/{LEGACY}/loading").json()["session_id"] is None


@pytest.mark.parametrize(
    "path",
    [
        "/api/sample/20991231_0000_9",
        "/api/sample/20991231_0000_9/geometry",
        "/api/sample/20991231_0000_9/loading",
        "/api/sample/bad%20id",
    ],
)
def test_unknown_sample_is_404_with_the_refusal_mark(client, path):
    refusal(client.get(path), 404, "unknown_sample")


def test_reads_need_a_login(client_for):
    refusal(client_for(login=None).get("/api/sample/list"), 401, "login_required")


def test_remote_viewer_reads(client_for):
    c = client_for(remote=True)
    assert c.get("/api/sample/list").status_code == 200
    assert c.get(f"/api/sample/{LEGACY}").status_code == 200


def test_no_sample_store_is_503(make_client, runner, tmp_path):
    c = make_client(runner)  # no records: the server installs no sample seat
    refusal(c.get("/api/sample/list"), 503, "no_sample_store")


# -- access ---------------------------------------------------------------------------------------


def test_access_local_no_session(client):
    assert client.get(f"/api/sample/access?sample_id={LEGACY}").json() == {
        "can_open_folder": True,
        "open_reason": None,
    }
    assert client.get("/api/sample/access").json() == {
        "can_open_folder": False,
        "open_reason": None,
    }


def test_access_session_open_for_another_sample(client, records, tmp_path):
    open_session(client, records, tmp_path, NEW)
    got = client.get(f"/api/sample/access?sample_id={LEGACY}").json()
    assert got["open_reason"] == (
        f"an experiment session is open for sample {NEW}; close it first (one sample per session)"
    )
    assert client.get(f"/api/sample/access?sample_id={NEW}").json()["open_reason"] is None


def test_access_remote_cannot_open_folder(client_for):
    got = client_for(remote=True).get(f"/api/sample/access?sample_id={LEGACY}").json()
    assert got["can_open_folder"] is False


def test_access_does_not_decide_role_control_or_session(client_for):
    """Only the two sample facts: the generic reasons are /api/permissions' (T-009b)."""
    got = client_for(login="vera@example.test").get(f"/api/sample/access?sample_id={LEGACY}").json()
    assert set(got) == {"can_open_folder", "open_reason"}


# -- the two session refusals the screen shows (engine side, T-027) ----------------------------


def _env(client, records, root):
    cur = client.app.state.sessions.current
    return sample_ops.SampleContext(records, root, cur, "otto")


def test_sample_open_of_another_sample_is_refused_while_a_session_is_open(
    client, records, root, tmp_path
):
    open_session(client, records, tmp_path, NEW)
    got = sample_ops.run_sample_op(
        "sample_open", _env(client, records, root), {"sample_id": LEGACY}
    )
    assert got["status"] == "refused" and f"open for sample {NEW}" in got["why"]
    # the router gives the screen the same fact before the click
    assert client.get(f"/api/sample/access?sample_id={LEGACY}").json()["open_reason"]


def test_geometry_set_without_that_samples_session_is_refused(client, records, root, tmp_path):
    got = sample_ops.run_sample_op(
        "sample_geometry_set",
        _env(client, records, root),
        {"sample_id": LEGACY, "values": {"sample_thickness_um": 120.0}},
    )
    assert got == {"status": "refused", "why": "needs an open experiment session for this sample"}
    open_session(client, records, tmp_path, NEW)
    got = sample_ops.run_sample_op(
        "sample_geometry_set",
        _env(client, records, root),
        {"sample_id": LEGACY, "values": {"sample_thickness_um": 120.0}},
    )
    assert got["status"] == "refused" and f"is for sample {NEW}" in got["why"]


# -- Open folder ----------------------------------------------------------------------------------


def test_open_folder_calls_the_injected_opener(client, root, opened):
    r = client.post(f"/api/sample/{LEGACY}/open-folder")
    assert r.status_code == 204, r.text
    assert opened == [root / LEGACY]


def test_open_folder_is_refused_remotely(client_for, opened):
    refusal(client_for(remote=True).post(f"/api/sample/{LEGACY}/open-folder"), 403, "remote_view")
    assert opened == []


def test_open_folder_needs_a_login(client_for, opened):
    refusal(client_for(login=None).post(f"/api/sample/{LEGACY}/open-folder"), 401, "login_required")
    assert opened == []


def test_open_folder_unknown_or_bad_sample(client, opened):
    refusal(client.post("/api/sample/20991231_0000_9/open-folder"), 404, "no_folder")
    refusal(client.post("/api/sample/bad%20id/open-folder"), 404, "unknown_sample")
    assert opened == []


def test_open_folder_failure_is_reported(client):
    def broken(_path):
        raise OSError("no shell")

    client.app.state.open_folder = broken
    assert "no shell" in refusal(
        client.post(f"/api/sample/{LEGACY}/open-folder"), 500, "open_failed"
    )


def test_routes_are_mounted_under_the_area(client):
    paths = {p for p in client.app.openapi()["paths"] if p.startswith("/api/sample")}
    assert paths == {
        "/api/sample/list",
        "/api/sample/geometry-fields",
        "/api/sample/access",
        "/api/sample/{sample_id}",
        "/api/sample/{sample_id}/geometry",
        "/api/sample/{sample_id}/loading",
        "/api/sample/{sample_id}/open-folder",
    }
