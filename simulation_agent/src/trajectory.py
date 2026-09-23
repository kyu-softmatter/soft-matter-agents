"""One writer for the trajectory, used for both backends (013).

The positions were computed frame by frame, consumed by the estimator and
discarded; `trajectory_meta.json` was 314 bytes of summary and there was no
trajectory on disk, ever. Raw data is this agent's record (4.3.2, Record row),
so it goes in `runs/<id>/` beside the four files already there -- and not in
the KB, where an entry needs a grade and a grade attaches to a claim, which a
trajectory is not.

**One format, one module, for both backends.** HOOMD writes GSD natively and
the mock does not; if each wrote its own, a mock-versus-engine comparison would
read two formats and the first thing to diverge would be how a frame is
indexed. `cc3adaa` made this choice once for the estimator; this is the same
choice one level down. Both backends hand over the same thing -- a list of
(N, 3) unwrapped positions in SI metres and the simulated time of each -- and
this module writes it, so by the time a frame is on disk the difference
between the backends is gone.

**GSD, and why.** It is the format the engine's own tools and every viewer of
HOOMD output read (ovito, freud, gsd itself), the person asked for it, and it
holds per-frame positions with a step counter and a box. What is stored is
unwrapped SI metres as float32 -- GSD's position dtype -- with the box given
in the same unit, so a viewer shows the box and a reader needs no backend to
know the unit: `trajectory_meta.json` says it.
float32 keeps seven digits; a 5 um tracer in a 300 um box moves ~0.3 um per
frame, so the rounding (~1e-11 m) is four decades under the smallest
displacement recorded. The estimator does NOT read this file back -- it runs
on the float64 frames in memory, as before -- so nothing this file's precision
touches enters an observable.

**When gsd is not importable, nothing is written and the record says so.** A
reduced path is legitimate and never silent (4.6.5 as amended): the meta file
carries `trajectory: {written: false, reason}` and the run is still a valid
run. This module imports gsd inside the function, so a machine without it
still runs the pipeline.

**This does not hold policy.** Whether a trajectory is kept, and the deletion
that a fired criterion may later trigger (run_log `deletion` event, check 77),
are the operator's and the plan's. This writes; the meta stays a summary that
outlives the data.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

FORMAT = "gsd"
FILENAME = "trajectory.gsd"
DTYPE = "float32"


def describe(frames_saved: int, n_particles: int, box_length_si: float) -> dict:
    """What a frame is, for `trajectory_meta.json` -- the two lines a reader
    a month later needs without opening the backend."""
    return {
        "format": FORMAT,
        "file": FILENAME,
        "units": "metres (SI), unwrapped: a tracer that crossed the periodic boundary keeps going, so displacements are physical and no image flag is needed",
        "ordering": f"frame i is particles.position of GSD frame i, shape ({n_particles}, 3), row = tracer index, fixed across frames",
        "index_0": "the initial configuration at simulated time 0, before any step",
        "step_counter": "configuration.step is the integer step count at that frame; simulated time is step * integration_timestep (derived, never accumulated)",
        "box": f"configuration.box = [{box_length_si!r}]*3 + [0,0,0], in metres, the same unit as the positions",
        "dtype": DTYPE,
        "frames": frames_saved,
    }


def write(out_dir: Path, frames: list[np.ndarray], steps: list[int], box_length_si: float) -> dict:
    """Write the frames; return the `trajectory` block for the meta file.

    `steps[i]` is the integer step count at frame i (derived by the caller from
    frame time / dt, never accumulated). Returns written=False with a reason
    rather than raising when gsd is absent: the run happened either way.
    """
    if not frames:
        return {"written": False, "reason": "no frames were saved"}
    try:
        import gsd.hoomd                               # noqa: PLC0415
    except ImportError as exc:
        return {
            "written": False,
            "reason": f"gsd is not importable in this interpreter ({exc}); the positions were computed and "
                      "consumed by the estimator and not kept. It is on conda-forge and PyPI as `gsd`.",
        }
    path = out_dir / FILENAME
    n = int(frames[0].shape[0])
    try:
        _write_gsd(gsd, path, frames, steps, n, box_length_si)
    except Exception as exc:                           # noqa: BLE001
        # The run happened and the summary is still written; a writer fault
        # is recorded, not raised into the record step. The first attempt at
        # this file died here on a per-frame unit label GSD's log refuses,
        # and a raise would have left a run directory with config.json and
        # no meta -- a run "in flight" to check 15 that had in fact finished.
        return {"written": False, "reason": f"gsd writer failed: {type(exc).__name__}: {exc}"}
    block = describe(len(frames), n, box_length_si)
    block.update({"written": True, "bytes": os.path.getsize(path), "gsd_version": gsd.version.version})
    return block


def _write_gsd(gsd, path, frames, steps, n, box_length_si) -> None:
    with gsd.hoomd.open(str(path), mode="w") as fh:
        for i, pos in enumerate(frames):
            frame = gsd.hoomd.Frame()
            frame.configuration.step = int(steps[i])
            frame.configuration.box = [box_length_si] * 3 + [0.0, 0.0, 0.0]
            frame.particles.N = n
            frame.particles.types = ["tracer"]
            frame.particles.typeid = np.zeros(n, dtype=np.uint32)
            frame.particles.position = np.asarray(pos, dtype=np.float32)
            fh.append(frame)


def read_positions(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """(frames, N, 3) float32 positions and the step counter per frame. For
    checks and viewers; the estimator does not use it."""
    import gsd.hoomd                                   # noqa: PLC0415
    with gsd.hoomd.open(str(path), mode="r") as fh:
        pos = np.stack([f.particles.position for f in fh])
        steps = np.array([f.configuration.step for f in fh])
    return pos, steps
