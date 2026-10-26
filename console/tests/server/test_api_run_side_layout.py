"""The console follows the microscope's runs and approvals to microscope_runtime/ (console card 005).

Four trees: runs moved, runs not moved (a tree from before the move), runs moved and approvals not
yet (the time between card 080 and the person's step 6), and no runs folder at all. A run that
cannot be seen must never read as "nothing is running": the lock-screen stop is what that would
fail.
"""

from __future__ import annotations

import json

import pytest
from sma_fake_run import LIVE_LIST, runs_dir, sma_tree, write_live_list
from test_api_stop_all import RecordingRun, conforms

from sma_console.agents import SmaFiles

STOP_ALL = "/api/console/runs/stop"


@pytest.fixture
def clients(engine, make_client):
    """(reads, lock): one client with a login for the reads, one with none, for the stop."""

    def make(root, **kw):
        store = SmaFiles(root)
        return (make_client(engine, agent_store=store, **kw),
                make_client(engine, agent_store=store, login=None, **kw))

    return make


def stop_audit(seat):
    return [e for e in seat.audit.entries() if e.get("command") == "sma_stop_all"]


# -- runs moved, and runs not moved ------------------------------------------------------------


@pytest.mark.parametrize("layout", ["runtime", "agent"])
def test_runs_are_found_followed_and_stopped_in_either_place(tmp_path, clients, layout):
    root = sma_tree(tmp_path / "sma", layout)
    run = RecordingRun(root, layout=layout)
    try:
        reads, lock = clients(root)
        listed = reads.get("/api/console/runs", params={"agent": "microscope"}).json()
        assert [r["run_id"] for r in listed] == [run.run_id]
        stream = reads.get(f"/api/console/runs/microscope/{run.run_id}/stream").json()
        assert stream["followed"] and stream["state"] == "running" and stream["can_stop"]
        r = lock.post(STOP_ALL)
        assert r.status_code == 200, r.text
        assert [(x["run_id"], x["outcome"]) for x in r.json()["runs"]] == [(run.run_id, "begun")]
        assert len(run.raw) == 1 and conforms(run.raw[0])
        assert json.loads(run.raw[0])["stop"] == run.run_id
        assert lock.post(f"/api/console/runs/microscope/{run.run_id}/stop", json={}).status_code == 200
        assert len(run.raw) == 2 and all(conforms(x) for x in run.raw)  # the per-run stop too
    finally:
        run.end()


def test_the_mock_sample_is_in_the_current_layout(engine, make_client):
    """The mock sample's runs are copies in microscope_runtime/runs/ (card 014); they read as runs."""
    runs = make_client(engine).get("/api/console/runs", params={"agent": "microscope"}).json()
    assert [r["run_id"] for r in runs] == ["run-20261013-004", "run-20261013-001", "run-20260924-003"]


def test_when_both_places_have_runs_only_the_runtime_ones_are_read_and_stopped(tmp_path, clients):
    root = sma_tree(tmp_path / "sma", "runtime")
    new = RecordingRun(root, run_id="run-20261005-001")
    old_folder = runs_dir(root, "agent")
    old = RecordingRun(root, run_id="run-20261005-002", layout="agent")
    assert old.folder.parent == old_folder and new.folder.parent != old_folder
    try:
        reads, lock = clients(root)
        listed = reads.get("/api/console/runs", params={"agent": "microscope"}).json()
        assert [r["run_id"] for r in listed] == [new.run_id]  # read one place, never both
        r = lock.post(STOP_ALL)
        assert [x["run_id"] for x in r.json()["runs"]] == [new.run_id]
        assert old.touched == 0 and old.raw == []
    finally:
        new.end()
        old.end()


# -- approvals and the live-view lists, which move later ---------------------------------------


def test_runs_moved_and_approvals_not_yet_each_read_from_its_own_place(tmp_path, clients):
    root = sma_tree(tmp_path / "sma", "runtime")
    write_live_list(root, "live-from-the-agent-folder.json", place="microscope_agent")
    approvals = root / "microscope_agent" / "approvals"
    (approvals / "appr-mic-20261005-001-r1.json").write_text("{}", encoding="utf-8")
    run = RecordingRun(root)
    try:
        reads, lock = clients(root)
        assert [r["run_id"] for r in reads.get("/api/console/runs").json()
                if r["agent"] == "microscope"] == [run.run_id]  # the runs: from the runtime folder
        live = reads.get("/api/console/live").json()
        assert [x["name"] for x in live["lists"]] == ["live-from-the-agent-folder.json"]
        assert {a["name"] for a in reads.get("/api/console/approvals").json()} == {
            "appr-mic-20261005-001-r1.json", "live-from-the-agent-folder.json"}  # from the agent folder
        assert lock.post(STOP_ALL).status_code == 200 and len(run.raw) == 1
    finally:
        run.end()


def test_after_the_person_moves_approvals_those_are_read_and_the_old_ones_are_not(tmp_path, clients):
    root = sma_tree(tmp_path / "sma", "runtime")
    write_live_list(root, "old-list.json", place="microscope_agent")
    sha_new = write_live_list(root, "new-list.json", place="microscope_runtime")
    (root / "microscope_runtime" / "approvals" / "appr-mic-20261005-002-r1.json").write_text(
        "{}", encoding="utf-8")
    reads, _ = clients(root)
    live = reads.get("/api/console/live").json()
    assert [(x["name"], x["sha256"]) for x in live["lists"]] == [("new-list.json", sha_new)]
    assert {a["name"] for a in reads.get("/api/console/approvals").json()} == {
        "appr-mic-20261005-002-r1.json", "new-list.json"}  # old-list.json is not read


def test_a_live_list_is_named_from_whichever_place_holds_it(tmp_path, clients):
    """The sha256 the console may send is checked against the same place it was listed from."""
    root = sma_tree(tmp_path / "sma", "runtime")
    sha_old = write_live_list(root, "old-list.json", place="microscope_agent")
    reads, _ = clients(root)
    assert [x["sha256"] for x in reads.get("/api/console/live").json()["lists"]] == [sha_old]
    sha_new = write_live_list(root, "new-list.json", {**LIVE_LIST, "label": "the moved list"},
                              place="microscope_runtime")
    assert sha_new != sha_old
    after = reads.get("/api/console/live").json()["lists"]
    assert [x["sha256"] for x in after] == [sha_new] and sha_old not in {x["sha256"] for x in after}


# -- no runs folder: the runs cannot be seen ---------------------------------------------------


@pytest.fixture
def blind(tmp_path):
    """A tree with the seats' folders and no runs folder for the microscope, in either place."""
    root = tmp_path / "sma"
    (root / "microscope_agent").mkdir(parents=True)
    (root / "simulation_agent" / "runs").mkdir(parents=True)
    return root


def test_with_no_runs_folder_the_stop_says_so_and_never_says_nothing_is_running(clients, blind, seat):
    reads, lock = clients(blind)
    r = lock.post(STOP_ALL)
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["code"] == "runs_not_found" and r.headers["X-DinoAF-Refusal"] == "runs_not_found"
    assert "runs folder was not found" in detail["message"]
    assert "nothing was sent" in detail["message"] and "not known whether a run is running" in detail["message"]
    assert "No run is running" not in r.text
    assert [e["outcome"] for e in stop_audit(seat)] == ["runs_folder_not_found"]  # the press is written down


def test_with_no_runs_folder_every_screen_that_lists_runs_says_so(clients, blind):
    reads, _ = clients(blind)
    for params in ({}, {"agent": "microscope"}):
        r = reads.get("/api/console/runs", params=params)
        assert r.status_code == 404 and r.json()["detail"]["code"] == "runs_not_found"
        assert "not the same as there being none" in r.json()["detail"]["message"]
    one = reads.get("/api/console/runs/microscope/run-20261005-001")
    assert one.status_code == 404 and "runs folder was not found" in one.json()["detail"]["message"]
    # the simulation seat keeps its own folder and its own meaning
    assert reads.get("/api/console/runs", params={"agent": "simulation"}).json() == []


def test_an_empty_runs_folder_is_still_nothing_running(tmp_path, clients, seat):
    root = sma_tree(tmp_path / "sma", "runtime")  # the folder is there, with no run in it
    reads, lock = clients(root)
    r = lock.post(STOP_ALL)
    assert r.status_code == 200 and r.json()["message"] == "No run is running. Nothing was sent."
    assert reads.get("/api/console/runs", params={"agent": "microscope"}).json() == []
    assert [e["outcome"] for e in stop_audit(seat)] == ["none_running"]
