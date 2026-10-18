"""agents.simulation over run folders shaped like soft-matter-agents' (written here)."""

from __future__ import annotations

import io
import json
import sys
import types
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from dino_autofocus.agents import simulation as sim
from dino_autofocus.agents import sma_files, store
from dino_autofocus.agents.simulation import (
    Frame,
    NotFoundError,
    SimulationRuns,
    TrajectoryUnavailable,
    read_progress,
    read_series,
)

T0 = datetime(2026, 9, 20, 22, 0, 0, tzinfo=UTC)


def _write(d: Path, name: str, data) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(data), encoding="utf-8")


def _progress(t: float, steps: int, state: str = "running", **more) -> dict:
    return {"t_mono": t, "time_base": "software", "event": "progress",
            "state": {"state": state, "steps_taken": steps, "simulated_time": steps * 0.002,
                      "frames_saved": steps // 10 + 1, "max_single_step_displacement": 3e-7,
                      "initialised": True, "failure": None, **more}}


def _log(events: list[dict], finished: bool = False) -> dict:
    log = {"artifact": "run_log", "t0_wall": T0.isoformat(), "backend": "mock_backend",
           "events": [
               {"t_mono": 0.0, "event": "preflight",
                "report": {"steps_per_frame": 10, "frames_expected": 1000}},
               *events]}
    if finished:
        log["finished_at"] = (T0 + timedelta(seconds=100)).isoformat()
    return log


def _config(**params) -> dict:
    return {"run_id": "r", "qid": "sim-20260917-001", "backend": "mock_backend",
            "parameters_si": {"integration_timestep": 0.002, "total_simulated_time": 20.0,
                              **params}}


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    base = tmp_path / "simulation_agent" / "runs"
    # finished by a stop criterion
    d = base / "run-20260920-001"
    _write(d, "config.json", _config())
    _write(d, "log.json", _log([
        _progress(20.0, 2000), _progress(80.0, 8000),
        {"t_mono": 100.0, "event": "complete",
         "monitor": {"id": "planned_duration_reached", "outcome": "complete"},
         "state": {"state": "complete", "steps_taken": 10000, "frames_saved": 1001}},
    ], finished=True))
    _write(d, "observables.json", {
        "observable": "tracer_diffusivity", "fit": {"diffusivity": 2.1e-13, "lags_used": 3,
                                                    "estimator": "wls"},
        "msd_curve": [[0.02, 1e-14], [0.04, 2e-14], [0.06, 3e-14]],
        "psi6_curve": {"time_si": [0, 1], "psi6_global": [1.0, 0.5], "psi6_local": [1, 0.7]},
        "hist": {"edges": [0, 1, 2], "counts": [3, 4]},
    })
    _write(d, "trajectory_meta.json", {"frames_saved": 1001, "steps_taken": 10000,
                                       "stop_outcome": "complete"})
    # still running at T0 + 50 s
    d = base / "run-20260921-001"
    _write(d, "config.json", _config())
    _write(d, "log.json", _log([_progress(25.0, 2500), _progress(50.0, 5000)]))
    # ended by itself: monitor null, outcome in the state
    d = base / "run-20260922-001"
    _write(d, "config.json", _config())
    _write(d, "log.json", _log([
        _progress(5.0, 500),
        {"t_mono": 9.0, "event": "complete", "monitor": None,
         "state": {"state": "complete", "steps_taken": 10000}},
    ]))
    # faulted
    d = base / "run-20260923-001"
    _write(d, "config.json", _config())
    _write(d, "log.json", _log([
        _progress(1.0, 100),
        {"t_mono": 2.0, "event": "abort",
         "monitor": {"id": "step_displacement_diverged", "outcome": "fault"},
         "state": {"state": "fault", "steps_taken": 300, "failure": None}},
    ]))
    # only a config: nothing says how far it is
    _write(base / "run-20260924-001", "config.json", _config())
    # a finished run whose log has no state, only trajectory_meta
    d = base / "run-20260925-001"
    _write(d, "config.json", _config())
    _write(d, "trajectory_meta.json", {"frames_saved": 11, "steps_taken": 100,
                                       "simulated_time": 0.2, "stop_outcome": "fault",
                                       "stopped_by": "step_displacement_diverged"})
    return base


# -- progress ---------------------------------------------------------------------------------


def test_progress_finished(runs: Path) -> None:
    p = read_progress(runs / "run-20260920-001", now=T0 + timedelta(days=1))
    assert p.state == "complete" and p.source == "log"
    assert p.steps_taken == 10000 and p.steps_total == 10000 and p.fraction == 1.0
    assert p.stopped_by == "planned_duration_reached"
    assert p.elapsed_s == 100.0  # to finished_at, not to now
    assert p.eta is None and p.remaining_s is None


def test_progress_running_eta(runs: Path) -> None:
    now = T0 + timedelta(seconds=60)
    p = read_progress(runs / "run-20260921-001", now=now)
    assert p.state == "running"
    assert p.steps_taken == 5000 and p.steps_total == 10000 and p.fraction == 0.5
    assert p.elapsed_s == 60.0
    assert p.updated_at == (T0 + timedelta(seconds=50)).isoformat()
    # 5000 steps in 50 s: the rest by T0 + 100 s, 40 s after now
    assert p.eta == (T0 + timedelta(seconds=100)).isoformat()
    assert p.remaining_s == pytest.approx(40.0)


def test_progress_end_event_without_monitor(runs: Path) -> None:
    p = read_progress(runs / "run-20260922-001")
    assert p.state == "complete" and p.steps_taken == 10000 and p.stopped_by is None


def test_progress_fault(runs: Path) -> None:
    p = read_progress(runs / "run-20260923-001")
    assert p.state == "fault" and p.stopped_by == "step_displacement_diverged"
    assert p.steps_taken == 300 and p.fraction == pytest.approx(0.03)
    assert p.elapsed_s == 2.0


def test_progress_unknown_and_meta_only(runs: Path) -> None:
    p = read_progress(runs / "run-20260924-001")
    assert p.state == "unknown" and p.source == "none"
    assert p.steps_taken is None and p.fraction is None and p.elapsed_s is None
    assert p.steps_total == 10000  # from the config
    p = read_progress(runs / "run-20260925-001")
    assert p.state == "fault" and p.source == "trajectory_meta"
    assert p.steps_taken == 100 and p.stopped_by == "step_displacement_diverged"


def test_progress_half_written_log_is_unknown(tmp_path: Path) -> None:
    d = tmp_path / "run-x"
    d.mkdir()
    (d / "log.json").write_text('{"events": [', encoding="utf-8")
    assert read_progress(d).state == "unknown"


def test_progress_roundtrip(runs: Path) -> None:
    p = read_progress(runs / "run-20260921-001", now=T0)
    assert sim.RunProgress.from_dict(json.loads(json.dumps(p.to_dict()))) == p


# -- series -----------------------------------------------------------------------------------


def test_series_values_as_read(runs: Path) -> None:
    s = read_series(runs / "run-20260920-001")
    assert s.log["t_mono"] == [20.0, 80.0]
    assert s.log["steps_taken"] == [2000, 8000]
    assert "state" not in s.log and "initialised" not in s.log  # not numbers
    assert s.observable == "tracer_diffusivity"
    by = {c.path: c for c in s.curves}
    assert by["msd_curve"].x == [0.02, 0.04, 0.06] and by["msd_curve"].y == [1e-14, 2e-14, 3e-14]
    assert by["psi6_curve.psi6_global"].x_name == "time_si"
    assert by["psi6_curve.psi6_local"].y == [1, 0.7]
    h = by["hist.counts"]
    assert h.kind == "histogram" and h.x == [0, 1, 2] and h.y == [3, 4]
    assert s.scalars["fit.diffusivity"] == 2.1e-13 and "fit.estimator" not in s.scalars
    json.dumps(s.to_dict())


def test_series_empty_run(runs: Path) -> None:
    s = read_series(runs / "run-20260924-001")
    assert s.log == {} and s.curves == [] and s.observables is None


# -- trajectory -------------------------------------------------------------------------------


def _npz(path: Path, frames: int = 5, n: int = 4, dims: int = 2) -> np.ndarray:
    pos = np.random.default_rng(0).normal(size=(frames, n, 3)).astype(np.float32)
    if dims == 2:
        pos[..., 2] = 0
    np.savez(path, positions=pos, step=np.arange(frames) * 10, typeid=np.array([0, 1, 0, 1]),
             types=np.array(["A", "B"]), box=np.array([5.0, 5.0, 0, 0, 0, 0]),
             dimensions=np.array(dims), orientation=np.ones((frames, n)))
    return pos


def _meta(d: Path, name: str, fmt: str, **more) -> None:
    _write(d, "trajectory_meta.json", {"trajectory": {"file": name, "format": fmt,
                                                      "written": True, **more}})


def test_npz_frames(tmp_path: Path) -> None:
    d = tmp_path / "runs" / "run-a"
    d.mkdir(parents=True)
    pos = _npz(d / "trajectory.npz")
    _meta(d, "trajectory.npz", "npz")
    r = SimulationRuns(tmp_path / "runs", trajectory_roots=[])
    t = r.trajectory("run-a")
    assert len(t) == 5
    f = t.frame(-1, fields=["orientation"])
    assert f.index == 4 and f.step == 40 and f.n == 4 and f.dimensions == 2
    np.testing.assert_array_equal(f.positions, pos[4])
    assert f.types == ["A", "B"] and f.typeid.tolist() == [0, 1, 0, 1]
    assert f.box == [5.0, 5.0, 0, 0, 0, 0]
    assert f.fields["orientation"].shape == (4,)
    d2 = f.to_dict()
    assert set(d2) == {"index", "step", "n", "dimensions", "units", "box", "types", "typeid",
                       "positions", "fields"}
    assert len(d2["positions"]) == 12  # flat x, y, z
    back = Frame.from_dict(json.loads(json.dumps(d2)))
    np.testing.assert_array_equal(back.positions, f.positions)
    assert "orientation" not in t.frame(0).fields  # only when asked for
    with pytest.raises(NotFoundError):
        t.frame(5)
    with pytest.raises(NotFoundError):
        t.frame(0, fields=["velocity"])


def test_trajectory_in_a_root(tmp_path: Path) -> None:
    d = tmp_path / "runs" / "run-a"
    d.mkdir(parents=True)
    _meta(d, "trajectory.npz", "npz")
    with pytest.raises(TrajectoryUnavailable, match="not in the run folder"):
        SimulationRuns(tmp_path / "runs", trajectory_roots=[]).trajectory("run-a")
    (tmp_path / "wsl" / "run-a").mkdir(parents=True)
    _npz(tmp_path / "wsl" / "run-a" / "trajectory.npz")
    r = SimulationRuns(tmp_path / "runs", trajectory_roots=[tmp_path / "wsl"])
    assert len(r.trajectory("run-a")) == 5
    assert r.info("run-a").trajectory == "npz:trajectory.npz"


def test_trajectory_unavailable_reasons(tmp_path: Path, runs: Path) -> None:
    r = SimulationRuns(runs, trajectory_roots=[])
    info = r.info("run-20260920-001")
    assert info.trajectory is None and "names no trajectory" in info.trajectory_unavailable
    d = runs / "run-20260921-001"
    _meta(d, "../escape.npz", "npz")
    with pytest.raises(TrajectoryUnavailable, match="plain name"):
        r.trajectory("run-20260921-001")
    _meta(d, "trajectory.xyz", "xyz")
    (d / "trajectory.xyz").write_text("1\n\nA 0 0 0\n", encoding="utf-8")
    with pytest.raises(TrajectoryUnavailable, match="no reader"):
        r.trajectory("run-20260921-001")
    assert "no reader" in r.info("run-20260921-001").trajectory_unavailable


def test_gsd_without_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "gsd", None)  # import fails
    d = tmp_path / "run-a"
    d.mkdir()
    (d / "trajectory.gsd").write_bytes(b"")
    _meta(d, "trajectory.gsd", "gsd")
    with pytest.raises(TrajectoryUnavailable, match="gsd package"):
        sim.open_trajectory(d)


def test_gsd_reader_maps_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Against a stand-in for gsd.hoomd with the attributes the reader uses."""
    snap = types.SimpleNamespace(
        particles=types.SimpleNamespace(
            N=2, position=np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32),
            typeid=np.array([0, 1]), types=["A", "B"], orientation=np.ones((2, 4))),
        configuration=types.SimpleNamespace(step=300, box=[1, 1, 1, 0, 0, 0], dimensions=3))

    class FakeFile(list):
        def close(self) -> None:
            self.closed = True

    hoomd = types.ModuleType("gsd.hoomd")
    hoomd.open = lambda name, mode: FakeFile([snap, snap])
    pkg = types.ModuleType("gsd")
    pkg.hoomd = hoomd
    monkeypatch.setitem(sys.modules, "gsd", pkg)
    monkeypatch.setitem(sys.modules, "gsd.hoomd", hoomd)
    d = tmp_path / "run-a"
    d.mkdir()
    (d / "trajectory.gsd").write_bytes(b"")
    _meta(d, "trajectory.gsd", "gsd")
    t = sim.open_trajectory(d)
    f = t.frame(1, fields=["orientation"])
    assert len(t) == 2 and f.step == 300 and f.dimensions == 3 and f.types == ["A", "B"]
    assert f.positions.dtype == np.float32 and f.positions[1].tolist() == [4, 5, 6]
    assert f.fields["orientation"].shape == (2, 4)
    t.close()


# -- zip --------------------------------------------------------------------------------------


def _unzip(chunks) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(b"".join(chunks)))


def test_zip_streams_records_and_optional_trajectory(tmp_path: Path) -> None:
    d = tmp_path / "runs" / "run-a"
    d.mkdir(parents=True)
    _write(d, "log.json", {"events": []})
    _meta(d, "trajectory.npz", "npz")
    (tmp_path / "wsl").mkdir()
    big = np.random.default_rng(1).bytes(300_000)
    (tmp_path / "wsl" / "trajectory.npz").write_bytes(big)
    r = SimulationRuns(tmp_path / "runs", trajectory_roots=[tmp_path / "wsl"])
    entries = {e.name: e for e in r.zip_entries("run-a")}
    assert entries["run-a/trajectory.npz"].optional
    assert not entries["run-a/log.json"].optional

    z = _unzip(r.iter_zip("run-a"))
    assert sorted(z.namelist()) == ["run-a/log.json", "run-a/trajectory_meta.json"]
    assert json.loads(z.read("run-a/log.json")) == {"events": []}

    chunks = list(r.iter_zip("run-a", include_optional=["trajectory.npz"], chunk_size=65536))
    assert len(chunks) > 3  # streamed, not built whole
    z = _unzip(chunks)
    assert z.read("run-a/trajectory.npz") == big
    assert z.testzip() is None
    assert (d / "log.json").read_text(encoding="utf-8") == '{"events": []}'  # untouched


# -- runs folder ------------------------------------------------------------------------------


def test_errors_are_the_stores(runs: Path) -> None:
    """One `except store.NotFoundError` covers the agent store and the simulation runs."""
    assert sim.NotFoundError is store.NotFoundError and sim.FileInfo is store.FileInfo
    assert issubclass(sim.SimulationError, store.StoreError)
    with pytest.raises(store.NotFoundError):
        SimulationRuns(runs, trajectory_roots=[]).info("run-29990101-001")


def test_list_and_ids(runs: Path) -> None:
    r = SimulationRuns(runs, trajectory_roots=[], source="test")
    ids = r.run_ids()
    assert set(ids) == {p.name for p in runs.iterdir()}
    rows = r.list_runs(now=T0)
    assert all(x.source == "test" for x in rows)
    first = r.info("run-20260920-001")
    assert first.qid == "sim-20260917-001" and first.backend == "mock_backend"
    assert {f.name for f in first.files} >= {"config.json", "log.json"}
    json.dumps(first.to_dict())
    assert set(r.records("run-20260920-001")) == set(sim.RECORD_FILES)


@pytest.mark.parametrize("bad", ["", ".", "..", "../x", "a/b", "a\\b", ".hidden", "nope"])
def test_bad_run_ids(runs: Path, bad: str) -> None:
    with pytest.raises(NotFoundError):
        SimulationRuns(runs, trajectory_roots=[]).run_dir(bad)


def test_missing_runs_dir(tmp_path: Path) -> None:
    assert SimulationRuns(tmp_path / "none", trajectory_roots=[]).list_runs() == []


def test_default_dirs_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(sma_files.ROOT_ENV, str(tmp_path))
    monkeypatch.setenv(sim.TRAJECTORY_ROOTS_ENV, f"{tmp_path / 'a'}{sim.os.pathsep}{tmp_path}")
    r = SimulationRuns()
    assert r.runs_dir == tmp_path / "simulation_agent" / "runs"
    assert r.roots == [tmp_path / "a", tmp_path]


_REAL = sim.default_runs_dir()


@pytest.mark.skipif(not _REAL.is_dir(), reason="no soft-matter-agents checkout here")
def test_reads_every_real_run_without_error() -> None:
    """The real tree is read, never written: every run gives a progress and a series."""
    r = SimulationRuns(_REAL, trajectory_roots=[])
    before = {p: p.stat().st_mtime_ns for p in _REAL.rglob("*") if p.is_file()}
    rows = r.list_runs()
    assert rows
    for row in rows:
        assert row.progress.state in ("running", "complete", "fault", "aborted", "unknown")
        json.dumps(r.series(row.run_id).to_dict())
    assert {p: p.stat().st_mtime_ns for p in _REAL.rglob("*") if p.is_file()} == before
