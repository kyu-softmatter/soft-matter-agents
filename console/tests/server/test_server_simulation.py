"""server/api/simulation.py: the F6 routes over the mock runs and over soft-matter-agents files."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from dino_autofocus.agents import SmaFiles
from dino_autofocus.agents.simulation import SimulationRuns
from dino_autofocus.server.api import REFUSAL_HEADER
from dino_autofocus.server.api import simulation as sim_api

VIEWER = "vera@example.test"  # the seeded viewer of conftest.py

BASE = "/api/simulation"
MOCK_STATES = {"mock-sim-2d-done": "complete", "mock-sim-3d-fault": "fault",
               "mock-sim-2d-running": "running"}


@pytest.fixture
def client(engine, make_client):
    c = make_client(engine)
    yield c
    held = c.app.state.simulation_runs if hasattr(c.app.state, "simulation_runs") else None
    if isinstance(held, sim_api.MockSimulations):
        held.close()


def test_mock_runs_by_default(client):
    runs = client.get(f"{BASE}/runs").json()
    assert {r["run_id"]: r["progress"]["state"] for r in runs} == MOCK_STATES
    assert all(r["source"] == "mock" and r["trajectory"] == "npz:trajectory.npz" for r in runs)
    run = client.get(f"{BASE}/runs/mock-sim-2d-done").json()
    assert run["progress"]["steps_taken"] == run["progress"]["steps_total"] == 10000
    p = client.get(f"{BASE}/runs/mock-sim-2d-running/progress").json()
    assert p["state"] == "running" and 0 < p["fraction"] < 1 and p["eta"]


def test_series_and_frames(client):
    s = client.get(f"{BASE}/runs/mock-sim-2d-done/series").json()
    assert {"steps_taken", "temperature", "pressure"} <= set(s["log"])
    assert s["observable"] == "mean_squared_displacement"
    assert s["curves"][0]["path"] == "msd_curve"

    f = client.get(f"{BASE}/runs/mock-sim-3d-fault/frames/3", params={"fields": "orientation"})
    assert f.status_code == 200, f.text
    f = f.json()
    assert (f["index"], f["step"], f["n"], f["dimensions"]) == (3, 150, 128, 3)
    assert len(f["positions"]) == 3 * 128 and len(f["typeid"]) == 128
    assert len(f["box"]) == 6 and f["types"] == ["A", "B"]
    assert len(f["fields"]["orientation"]) == 128
    last = client.get(f"{BASE}/runs/mock-sim-2d-done/frames/-1").json()
    assert last["index"] == 200


@pytest.mark.parametrize("path", [
    "/runs/nope", "/runs/nope/progress", "/runs/nope/series", "/runs/nope/frames/0",
    "/runs/nope/zip", "/runs/nope/zip/entries", "/runs/nope/progress/stream",
    "/runs/mock-sim-2d-done/frames/9999", "/runs/mock-sim-2d-done/frames/0?fields=velocity",
    "/runs/.hidden/progress", "/runs/a..b%5Cc/series",
])
def test_not_found(client, path):
    r = client.get(BASE + path)
    assert r.status_code == 404, r.text
    assert r.headers[REFUSAL_HEADER] == "not_found"
    assert r.json()["detail"]["code"] == "not_found"


def test_zip(client):
    entries = client.get(f"{BASE}/runs/mock-sim-2d-done/zip/entries").json()
    by = {e["name"]: e for e in entries}
    assert by["mock-sim-2d-done/trajectory.npz"]["optional"]
    assert not by["mock-sim-2d-done/log.json"]["optional"]

    r = client.get(f"{BASE}/runs/mock-sim-2d-done/zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert 'filename="mock-sim-2d-done.zip"' in r.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "mock-sim-2d-done/log.json" in names
    assert "mock-sim-2d-done/trajectory.npz" not in names

    r = client.get(f"{BASE}/runs/mock-sim-2d-done/zip", params={"trajectory": "1"})
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert "mock-sim-2d-done/trajectory.npz" in z.namelist() and z.testzip() is None


def _events(text: str) -> list[dict]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        assert lines["event"] == "progress"
        out.append(json.loads(lines["data"]))
    return out


def test_progress_stream(client, monkeypatch):
    monkeypatch.setattr(sim_api, "STREAM_INTERVAL_S", 0.05)
    with client.stream("GET", f"{BASE}/runs/mock-sim-2d-running/progress/stream",
                       params={"limit": 3}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _events(r.read().decode())
    assert len(events) == 3
    # steps move with the log's progress events (every 1000 steps here); elapsed moves on
    elapsed = [e["elapsed_s"] for e in events]
    assert elapsed == sorted(elapsed) and elapsed[0] < elapsed[-1]
    assert all(e["state"] == "running" and e["steps_taken"] >= 3000 for e in events)

    # a finished run sends its progress once and ends
    with client.stream("GET", f"{BASE}/runs/mock-sim-2d-done/progress/stream") as r:
        (done,) = _events(r.read().decode())
    assert done["state"] == "complete"


def test_needs_a_login_and_a_remote_viewer_may_read(engine, make_client):
    anon = make_client(engine, login=None)
    assert anon.get(f"{BASE}/runs").status_code == 401
    remote = make_client(engine, remote=True, login=VIEWER)
    assert remote.get(f"{BASE}/runs").status_code == 200
    assert remote.get(f"{BASE}/runs/mock-sim-2d-done/frames/0").status_code == 200


def _real_tree(root: Path) -> None:
    run = root / "simulation_agent" / "runs" / "run-20260920-001"
    run.mkdir(parents=True)
    (run / "config.json").write_text(json.dumps({"qid": "sim-20260917-001",
                                                 "backend": "hoomd_backend"}), encoding="utf-8")
    (run / "log.json").write_text(json.dumps({
        "t0_wall": "2026-09-20T22:00:00+00:00", "finished_at": "2026-09-20T22:01:40+00:00",
        "events": [
            {"t_mono": 0, "event": "preflight", "report": {"steps_per_frame": 10,
                                                            "frames_expected": 100}},
            {"t_mono": 100, "event": "complete", "monitor": None,
             "state": {"state": "complete", "steps_taken": 1000}}]}), encoding="utf-8")
    (run / "trajectory_meta.json").write_text(json.dumps(
        {"trajectory": {"format": "gsd", "file": "trajectory.gsd", "written": True}}),
        encoding="utf-8")


def test_sma_store_means_its_runs(engine, make_client, tmp_path):
    _real_tree(tmp_path / "sma")
    c = make_client(engine, agent_store=SmaFiles(tmp_path / "sma"))
    (run,) = c.get(f"{BASE}/runs").json()
    assert run["source"] == "soft-matter-agents" and run["qid"] == "sim-20260917-001"
    assert run["progress"]["state"] == "complete" and run["progress"]["fraction"] == 1.0
    assert "not in the run folder" in run["trajectory_unavailable"]
    r = c.get(f"{BASE}/runs/run-20260920-001/frames/0")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "trajectory_unavailable"
    assert not (tmp_path / "sma" / "simulation_agent" / "runs" / "run-20260920-001"
                / "observables.json").exists()  # read only


def test_launcher_may_set_the_runs(engine, make_client, tmp_path):
    _real_tree(tmp_path / "sma")
    c = make_client(engine)
    c.app.state.simulation_runs = SimulationRuns(tmp_path / "sma" / "simulation_agent" / "runs",
                                                 trajectory_roots=[], source="launcher")
    assert [r["source"] for r in c.get(f"{BASE}/runs").json()] == ["launcher"]


def test_mock_folder_goes_with_the_app():
    m = sim_api.MockSimulations()
    folder = Path(m.sims[0].write_dir)
    assert len(m.runs.run_ids()) == 3  # syncs: the run folders are written
    assert any(folder.iterdir())
    m.close()
    assert not folder.exists()


def test_routes_are_in_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/runs", "/runs/{run_id}", "/runs/{run_id}/progress", "/runs/{run_id}/series",
              "/runs/{run_id}/frames/{index}", "/runs/{run_id}/zip", "/runs/{run_id}/zip/entries",
              "/runs/{run_id}/progress/stream"):
        assert f"{BASE}{p}" in paths and list(paths[f"{BASE}{p}"]) == ["get"]
