"""Run when src/trajectory.py changes: does the text form still round-trip?

Whether a written trajectory reads back to the same array is a property of the
writer's format -- 9 figures for float32 and 17 for float64 are exact by
construction -- so it is proved once per change to the writer, not once per
run (manager-simulation, 2026-09-24). This writes synthetic frames in both
dtypes, with and without orientations and in two and three dimensions, reads
them back through the reuse path, and requires the coordinate hash to match,
then deletes and alters the file and requires the reader to refuse.

    pixi run -e sim python -m src.check_trajectory_roundtrip      # from simulation_agent/

Exit 0 when every case holds. It writes only to a temporary directory.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

from . import trajectory


def one(tmp: Path, dtype: str, dims: int, with_theta: bool) -> str:
    rng = np.random.default_rng(7)
    frames = [rng.normal(scale=1e-5, size=(5, 3)).astype(dtype) for _ in range(4)]
    theta = [rng.uniform(-np.pi, np.pi, 5).astype(dtype) for _ in range(4)] if with_theta else None
    d = tmp / f"{dtype}_{dims}d_{'theta' if with_theta else 'pos'}"
    d.mkdir()
    block = trajectory.write_text(d, frames, [0, 10, 20, 30], 1e-4, dimensions=dims, run_id=d.name,
                                  plan_hash="sha256:" + "0" * 64, engine="synthetic", engine_version="0",
                                  seed=0, save_interval_steps=10, orientations=theta)
    (d / "trajectory_meta.json").write_text(json.dumps({"trajectory": block}))
    back = trajectory.read_text(d)
    want = np.stack([f[:, :dims] for f in frames])
    assert np.array_equal(back["coords"], want), "coordinates changed in the round trip"
    if with_theta:
        assert np.array_equal(back["theta"], np.stack(theta)), "orientations changed in the round trip"
    (d / trajectory.TEXT_FILENAME).write_text((d / trajectory.TEXT_FILENAME).read_text() + "# appended\n")
    try:
        trajectory.read_text(d); raise AssertionError("an altered file was read")
    except trajectory.TrajectoryUnavailable:
        pass
    (d / trajectory.TEXT_FILENAME).unlink()
    try:
        trajectory.read_text(d); raise AssertionError("a deleted file was read")
    except trajectory.TrajectoryUnavailable:
        pass
    return f"{d.name}: round trip exact, altered and deleted both refused"


def main() -> int:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        for dtype in ("float32", "float64"):
            for dims in (2, 3):
                for th in (False, True):
                    print(one(tmp, dtype, dims, th))
    return 0


if __name__ == "__main__":
    sys.exit(main())
