"""agents.simulation.GsdTrajectory against a real GSD file written with the gsd package.
Skipped where gsd is not installed (it is in the server group)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from dino_autofocus.agents.simulation import (
    GsdTrajectory,
    NotFoundError,
    SimulationRuns,
    open_trajectory,
)

hoomd = pytest.importorskip("gsd.hoomd")

L = 5e-4  # m, as the real runs' trajectory_meta records the box


def _write(path: Path, frames: int = 4, n: int = 5, dims: int = 3) -> np.ndarray:
    rng = np.random.default_rng(0)
    pos = rng.uniform(-L / 2, L / 2, size=(frames, n, 3)).astype(np.float32)
    if dims == 2:
        pos[..., 2] = 0
    with hoomd.open(str(path), "w") as f:
        for i in range(frames):
            fr = hoomd.Frame()
            fr.configuration.step = i * 100
            fr.configuration.box = [L, L, L if dims == 3 else 0, 0, 0, 0]
            fr.configuration.dimensions = dims
            fr.particles.N = n
            fr.particles.types = ["A", "B"]
            fr.particles.typeid = np.arange(n) % 2
            fr.particles.position = pos[i]
            fr.particles.diameter = np.full(n, 2e-6, dtype=np.float32)
            f.append(fr)
    return pos


def _run(tmp_path: Path, name: str = "run-20260923-041-max-min-s1") -> Path:
    d = tmp_path / "runs" / name
    d.mkdir(parents=True)
    (d / "trajectory_meta.json").write_text(json.dumps({"trajectory": {
        "format": "gsd", "file": "trajectory.gsd", "written": True, "frames": 4}}),
        encoding="utf-8")
    return d


def test_reads_a_real_gsd_file(tmp_path: Path) -> None:
    d = _run(tmp_path)
    pos = _write(d / "trajectory.gsd")
    t = open_trajectory(d)
    try:
        assert isinstance(t, GsdTrajectory) and len(t) == 4
        f = t.frame(2, fields=["diameter"])
        assert (f.index, f.step, f.n, f.dimensions) == (2, 200, 5, 3)
        np.testing.assert_array_equal(f.positions, pos[2])
        assert f.types == ["A", "B"] and f.typeid.tolist() == [0, 1, 0, 1, 0]
        np.testing.assert_allclose(f.box, [L, L, L, 0, 0, 0], rtol=1e-6)
        np.testing.assert_allclose(f.fields["diameter"], 2e-6, rtol=1e-6)
        assert t.frame(-1).step == 300
        d2 = f.to_dict()
        assert len(d2["positions"]) == 15 and d2["fields"]["diameter"][0] == pytest.approx(2e-6)
        with pytest.raises(NotFoundError):
            t.frame(4)
        with pytest.raises(NotFoundError):
            t.frame(0, fields=["position"])
    finally:
        t.close()


def test_2d_gsd_and_a_trajectory_root(tmp_path: Path) -> None:
    d = _run(tmp_path)
    wsl = tmp_path / "wsl" / d.name
    wsl.mkdir(parents=True)
    _write(wsl / "trajectory.gsd", dims=2)
    runs = SimulationRuns(tmp_path / "runs", trajectory_roots=[tmp_path / "wsl"])
    assert runs.info(d.name).trajectory == "gsd:trajectory.gsd"
    t = runs.trajectory(d.name)
    try:
        f = t.frame(0)
        assert f.dimensions == 2 and f.box[2] == 0 and not f.positions[:, 2].any()
    finally:
        t.close()
