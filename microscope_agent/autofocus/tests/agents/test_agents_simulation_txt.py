"""agents.simulation.TxtTrajectory: the guessed text layout, and its refusal when a file
does not fit trajectory_meta.json. No real sample has been checked yet (a user item)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from dino_autofocus.agents.simulation import (
    NotFoundError,
    SimulationRuns,
    TrajectoryUnavailable,
    TxtTrajectory,
    open_trajectory,
)

COLS_2D_ABP = ["step", "particle", "x", "y", "theta"]
COLS_3D = ["step", "particle", "x", "y", "z"]


def _run(tmp_path: Path, cols: list[str], frames: int, particles: int, text: str,
         dims: int = 2, length: float = 5e-5) -> Path:
    d = tmp_path / "runs" / "run-20260923-042-small-s2"
    d.mkdir(parents=True)
    (d / "trajectory_meta.json").write_text(json.dumps({"trajectory": {
        "written": True, "format": "txt", "file": "trajectory.txt", "frames": frames,
        "particles": particles, "box": {"length_m": length, "dimensions": dims,
                                        "periodic": True},
        "columns": [{"name": c, "unit": "m"} for c in cols]}}), encoding="utf-8")
    (d / "trajectory.txt").write_text(text, encoding="utf-8")
    return d


def _rows(frames: int, particles: int, ncols: int, sep: str = " ", shuffle: bool = False) -> str:
    lines = []
    for f in range(frames):
        order = list(range(particles))[::-1] if shuffle else range(particles)
        for p in order:
            vals = [f * 200, p] + [f + p / 10 + k for k in range(ncols - 2)]
            lines.append(sep.join(f"{v:.17g}" for v in vals))
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("header", ["", "# step particle x y theta\n", "step particle x y theta\n"])
@pytest.mark.parametrize("sep", [" ", "\t", ","])
def test_reads_the_guessed_layout(tmp_path: Path, header: str, sep: str) -> None:
    d = _run(tmp_path, COLS_2D_ABP, 3, 4, header + _rows(3, 4, 5, sep))
    t = open_trajectory(d)
    assert isinstance(t, TxtTrajectory) and not t.verified
    assert len(t) == 3 and t.n == 4
    f = t.frame(2, fields=["theta"])
    assert (f.index, f.step, f.n, f.dimensions) == (2, 400, 4, 2)
    assert f.box == [5e-5, 5e-5, 0.0, 0.0, 0.0, 0.0]
    np.testing.assert_allclose(f.positions[:, 0], [2, 2.1, 2.2, 2.3], rtol=1e-6)
    np.testing.assert_allclose(f.positions[:, 1], [3, 3.1, 3.2, 3.3], rtol=1e-6)
    assert not f.positions[:, 2].any()
    np.testing.assert_allclose(f.fields["theta"], [4, 4.1, 4.2, 4.3])
    assert f.types == ["A"] and not f.typeid.any()
    assert t.frame(-1).index == 2


def test_3d_rows_in_any_particle_order(tmp_path: Path) -> None:
    d = _run(tmp_path, COLS_3D, 2, 3, _rows(2, 3, 5, shuffle=True), dims=3, length=1e-5)
    f = open_trajectory(d).frame(1)
    assert f.dimensions == 3 and f.box[:3] == [1e-5, 1e-5, 1e-5]
    np.testing.assert_allclose(f.positions[:, 2], [3, 3.1, 3.2], rtol=1e-6)  # sorted by particle


@pytest.mark.parametrize(("frames", "particles", "text", "why"), [
    (3, 4, _rows(3, 4, 4), "line 1 has 4 values"),  # one column short of the meta
    (2, 4, _rows(3, 4, 5), "3 frames, trajectory_meta says 2"),
    (3, 5, _rows(3, 4, 5), "4 rows per frame, trajectory_meta says 5 particles"),
    (3, 4, "", "no data rows"),
    (3, 4, _rows(1, 4, 5) + _rows(1, 3, 5).replace("0 ", "200 ", 1), "different row counts"),
])
def test_a_file_that_does_not_fit_is_refused_as_unverified(tmp_path, frames, particles, text,
                                                           why) -> None:
    d = _run(tmp_path, COLS_2D_ABP, frames, particles, text)
    with pytest.raises(TrajectoryUnavailable, match="unverified txt layout") as e:
        open_trajectory(d)
    assert why in str(e.value) and "no sample file has been checked yet" in str(e.value)


def test_meta_without_columns_is_refused(tmp_path: Path) -> None:
    d = _run(tmp_path, [], 1, 1, "0 0 1 2\n")
    with pytest.raises(TrajectoryUnavailable, match="no column names"):
        open_trajectory(d)


def test_unknown_field_and_frame(tmp_path: Path) -> None:
    t = open_trajectory(_run(tmp_path, COLS_2D_ABP, 3, 4, _rows(3, 4, 5)))
    with pytest.raises(NotFoundError):
        t.frame(0, fields=["velocity"])
    with pytest.raises(NotFoundError):
        t.frame(0, fields=["x"])
    with pytest.raises(NotFoundError):
        t.frame(3)


def test_found_in_a_trajectory_root_like_the_samples_folder(tmp_path: Path) -> None:
    """The samples go to e.g. D:\\AutoFocus\\sim_samples\\<run_id>\\trajectory.txt."""
    d = _run(tmp_path, COLS_2D_ABP, 3, 4, _rows(3, 4, 5))
    samples = tmp_path / "sim_samples" / d.name
    samples.mkdir(parents=True)
    (d / "trajectory.txt").replace(samples / "trajectory.txt")
    runs = SimulationRuns(tmp_path / "runs", trajectory_roots=[tmp_path / "sim_samples"])
    assert runs.info(d.name).trajectory == "txt:trajectory.txt"
    assert len(runs.trajectory(d.name)) == 3
