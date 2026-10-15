"""agents.mock_sim: a fake run that grows with a clock, read back by agents.simulation."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from dino_autofocus.agents import mock_sim, sma_files
from dino_autofocus.agents.mock_sim import MockSimulation, MockTicker, make_mock_runs
from dino_autofocus.agents.simulation import SimulationRuns, read_progress, read_series

T0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


def _sim(tmp_path: Path, **kw) -> MockSimulation:
    kw = {"frames": 20, "steps_per_frame": 10, "steps_per_second": 10.0, "n_particles": 4,
          "progress_every_frames": 2, "started_at": T0, **kw}
    return MockSimulation(tmp_path / "runs", "mock-a", **kw)


def test_grows_with_time(tmp_path: Path) -> None:
    s = _sim(tmp_path)  # 200 steps at 10 steps/s: done at T0 + 20 s
    runs = SimulationRuns(tmp_path / "runs", trajectory_roots=[], source="mock")

    s.sync(T0)
    p = runs.progress("mock-a", now=T0)
    assert p.state == "running" and p.steps_taken == 0 and p.steps_total == 200
    assert len(runs.trajectory("mock-a")) == 1

    now = T0 + timedelta(seconds=8)
    s.sync(now)
    p = runs.progress("mock-a", now=now)
    assert p.state == "running" and p.steps_taken == 80 and p.fraction == pytest.approx(0.4)
    assert p.eta == (T0 + timedelta(seconds=20)).isoformat()
    assert p.remaining_s == pytest.approx(12.0)
    assert len(runs.trajectory("mock-a")) == 9  # frame 0 and one per 10 steps
    assert not (s.run_dir / "observables.json").exists()
    early = read_series(s.run_dir).log["steps_taken"]

    end = T0 + timedelta(seconds=30)
    s.sync(end)
    p = runs.progress("mock-a", now=end)
    assert p.state == "complete" and p.steps_taken == 200 and p.fraction == 1.0
    assert p.stopped_by == "planned_duration_reached" and p.elapsed_s == 20.0
    assert len(runs.trajectory("mock-a")) == 21
    series = read_series(s.run_dir)
    assert len(series.log["steps_taken"]) > len(early)
    assert {"temperature", "potential_energy", "pressure"} <= set(series.log)
    assert series.observable == "mean_squared_displacement"
    assert series.curves and series.curves[0].path == "msd_curve"


def test_frames_are_the_drawn_trajectory(tmp_path: Path) -> None:
    s = _sim(tmp_path, dimensions=3)
    s.sync(T0 + timedelta(seconds=100))
    t = SimulationRuns(tmp_path / "runs", trajectory_roots=[]).trajectory("mock-a")
    f = t.frame(7, fields=["orientation"])
    np.testing.assert_array_equal(f.positions, s.positions[7])
    assert f.step == 70 and f.dimensions == 3 and f.box[2] > 0
    assert f.types == ["A", "B"] and f.typeid.tolist() == [0, 1, 0, 1]
    assert f.fields["orientation"].shape == (4,)


def test_2d_has_flat_z(tmp_path: Path) -> None:
    s = _sim(tmp_path)
    s.sync(T0 + timedelta(seconds=100))
    f = SimulationRuns(tmp_path / "runs", trajectory_roots=[]).trajectory("mock-a").frame(-1)
    assert f.dimensions == 2 and f.box[2] == 0 and not f.positions[:, 2].any()


def test_fault(tmp_path: Path) -> None:
    s = _sim(tmp_path, fault_at_step=55)
    s.sync(T0 + timedelta(seconds=100))
    p = read_progress(s.run_dir)
    assert p.state == "fault" and p.steps_taken == 55
    assert p.stopped_by == "step_displacement_diverged"
    meta = json.loads((s.run_dir / "trajectory_meta.json").read_text(encoding="utf-8"))
    assert meta["stop_outcome"] == "fault" and meta["stopped_early"] is True


def test_files_do_not_depend_on_sync_count(tmp_path: Path) -> None:
    a = MockSimulation(tmp_path / "a", "mock-a", frames=20, steps_per_frame=10,
                       steps_per_second=10.0, started_at=T0, seed=4)
    b = MockSimulation(tmp_path / "b", "mock-a", frames=20, steps_per_frame=10,
                       steps_per_second=10.0, started_at=T0, seed=4)
    for k in range(0, 13):
        a.sync(T0 + timedelta(seconds=k))
    b.sync(T0 + timedelta(seconds=12))
    for name in ("log.json", "trajectory_meta.json", "config.json"):
        assert (a.run_dir / name).read_bytes() == (b.run_dir / name).read_bytes(), name
    with np.load(a.run_dir / "trajectory.npz") as za, np.load(b.run_dir / "trajectory.npz") as zb:
        assert za.files == zb.files
        for k in za.files:
            np.testing.assert_array_equal(za[k], zb[k])


def test_clock_drives_sync(tmp_path: Path) -> None:
    now = [T0]
    s = _sim(tmp_path, clock=lambda: now[0])
    assert s.sync() == 0
    now[0] = T0 + timedelta(seconds=3)
    assert s.sync() == 30


def test_writes_only_under_write_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="does not write inside"):
        MockSimulation(mock_sim.PACKAGE_DIR / "agents" / "x")
    sma = tmp_path / "sma"
    monkeypatch.setenv(sma_files.ROOT_ENV, str(sma))
    with pytest.raises(ValueError, match="does not write inside"):
        MockSimulation(sma / "simulation_agent" / "runs")
    s = _sim(tmp_path)
    s.sync(T0 + timedelta(seconds=100))
    written = {p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file()}
    assert all(p.parts[:2] == ("runs", "mock-a") for p in written)
    assert not any(p.name.endswith(".tmp") for p in written)


@pytest.mark.parametrize("bad", [{"run_id": "../x"}, {"dimensions": 4}, {"frames": 0},
                                 {"n_particles": 10**6, "frames": 10**3}])
def test_bad_arguments(tmp_path: Path, bad: dict) -> None:
    with pytest.raises(ValueError):
        MockSimulation(tmp_path, **bad)


def test_make_mock_runs(tmp_path: Path) -> None:
    sims = make_mock_runs(tmp_path, clock=lambda: T0)
    for s in sims:
        s.sync(T0)
    runs = SimulationRuns(tmp_path, trajectory_roots=[], source="mock")
    states = {r.run_id: r.progress.state for r in runs.list_runs(now=T0)}
    assert states == {"mock-sim-2d-done": "complete", "mock-sim-3d-fault": "fault",
                      "mock-sim-2d-running": "running"}
    assert all(r.trajectory == "npz:trajectory.npz" for r in runs.list_runs(now=T0))


def test_ticker_advances_and_stops(tmp_path: Path) -> None:
    s = MockSimulation(tmp_path, "mock-a", frames=10_000, steps_per_frame=1,
                       steps_per_second=100.0, n_particles=2)
    with MockTicker([s], interval=0.02) as ticker:
        first = read_progress(s.run_dir).steps_taken or 0
        deadline = time.monotonic() + 5
        while (read_progress(s.run_dir).steps_taken or 0) <= first:
            assert time.monotonic() < deadline, "the ticker did not advance the run"
            time.sleep(0.02)
    assert ticker._thread is not None and not ticker._thread.is_alive()
