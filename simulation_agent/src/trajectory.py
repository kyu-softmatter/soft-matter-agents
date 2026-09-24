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



# --------------------------------------------------------------------------- #
# the text form (021): one file, read back instead of re-run
# --------------------------------------------------------------------------- #
#
# The person asked on 2026-09-23 that a run keep its trajectory as ONE TEXT
# FILE, so that analysis reads the file instead of running the simulation
# again, and that they delete it by hand when they need the space. They chose
# it knowing text is several times larger than GSD. So the text file replaces
# the GSD rather than sitting beside it: two copies of one trajectory are one
# fact in two places.

TEXT_FILENAME = "trajectory.txt"
SIG_FIGS = {"float32": 9, "float64": 17}      # each round-trips its dtype exactly


class TrajectoryUnavailable(Exception):
    """The file analysis needs is gone or no longer the file that was written.

    Raised rather than recovered from: the reader does not re-run the
    simulation and does not read another file in its place. Re-running is the
    person's decision once they have been told the file is gone.
    """


def coords_sha256(coords: np.ndarray) -> str:
    """SHA-256 over the coordinate array itself, C order, in its own dtype.

    Not over the text: the text moves with digits, separators and line endings
    and so cannot say whether two runs produced the same positions. The array
    can, and that is what shows which engine ran.
    """
    import hashlib
    return hashlib.sha256(np.ascontiguousarray(coords).tobytes()).hexdigest()


def write_text(out_dir: Path, frames: list, steps: list[int], box_length_si: float, *,
               dimensions: int, run_id: str, plan_hash: str, engine: str, engine_version: str,
               seed: int, save_interval_steps: int, orientations: list | None = None,
               reduced_units: dict | None = None) -> dict:
    """Write the trajectory as text; return the meta's `trajectory` block.

    Rows are one particle at one saved frame: the integer step, the particle
    id, the UNWRAPPED position components in metres, and the in-plane
    orientation in radians where the model has one. The values are written at
    the digits their dtype carries and no more.
    """
    if not frames:
        return {"written": False, "reason": "no frames were saved"}
    coords = np.stack([np.asarray(f)[:, :dimensions] for f in frames])      # (frames, N, d)
    dtype = str(coords.dtype)
    if dtype not in SIG_FIGS:
        return {"written": False, "reason": f"coordinates are {dtype}, which the text form does not declare a digit count for"}
    digits = SIG_FIGS[dtype]
    n_frames, n = coords.shape[0], coords.shape[1]
    theta = np.stack([np.asarray(o, dtype=coords.dtype) for o in orientations]) if orientations else None
    axes = "xyz"[:dimensions]
    columns = [{"name": "step", "unit": "1", "meaning": "integer integration-step index of the frame; time is step * integration_timestep, never an accumulated float"},
               {"name": "particle", "unit": "1", "meaning": "particle index, fixed across frames"}]
    columns += [{"name": a, "unit": "m", "meaning": f"UNWRAPPED {a} position: a particle that crossed the periodic boundary keeps going"} for a in axes]
    if theta is not None:
        columns.append({"name": "theta", "unit": "rad", "meaning": "in-plane orientation angle of the self-propulsion direction"})
    path = out_dir / TEXT_FILENAME
    header = [
        f"run_id {run_id}", f"plan_hash {plan_hash}", f"engine {engine} {engine_version}", f"seed {seed}",
        f"box {box_length_si!r} m per side, periodic, {dimensions}D", f"save_interval_steps {save_interval_steps}",
        f"particles {n}", f"frames {n_frames}", f"dtype {dtype}, written at {digits} significant figures",
        "units SI: metres and radians; the engine ran in reduced units and converted on the way out"
        + (f" (length scale {reduced_units['length_si']!r} m, time scale {reduced_units['time_si']!r} s)" if reduced_units else ""),
        "columns " + " ".join(c["name"] for c in columns),
    ] + [f"column {c['name']} [{c['unit']}]: {c['meaning']}" for c in columns]
    fmt = " ".join(["%d", "%d"] + [f"%.{digits - 1}e"] * (dimensions + (1 if theta is not None else 0)))
    with open(path, "w", newline="\n") as fh:
        for line in header:
            fh.write(f"# {line}\n")
        pid = np.arange(n)
        for i in range(n_frames):
            cols = [np.full(n, int(steps[i])), pid] + [coords[i, :, k] for k in range(dimensions)]
            if theta is not None:
                cols.append(theta[i])
            np.savetxt(fh, np.column_stack(cols), fmt=fmt)
    import hashlib
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "written": True, "format": "txt", "file": TEXT_FILENAME,
        "sha256": file_hash, "coords_sha256": coords_sha256(coords),
        "dtype": dtype, "sig_figs": digits, "time_base": "step_index",
        "save_interval_steps": int(save_interval_steps), "frames": int(n_frames), "particles": int(n),
        "engine": engine, "engine_version": engine_version, "seed": int(seed), "plan_hash": plan_hash,
        "box": {"length_m": box_length_si, "dimensions": dimensions, "periodic": True},
        "units": "SI: metres and radians, converted from the engine's reduced units at the backend boundary",
        "columns": columns, "bytes": path.stat().st_size,
    }


def read_text(run_dir: Path) -> dict:
    """The trajectory of a run, read back from its text file, or a refusal.

    Refuses when the meta says nothing was written, when the file is gone, or
    when its bytes or its coordinates no longer hash to what the meta
    recorded. It never re-runs anything and never reads another file.
    """
    import hashlib, json
    meta_path = run_dir / "trajectory_meta.json"
    if not meta_path.exists():
        raise TrajectoryUnavailable(f"{run_dir.name} has no trajectory_meta.json, so nothing says what its trajectory was")
    t = (json.loads(meta_path.read_text()).get("trajectory") or {})
    if not t.get("written"):
        raise TrajectoryUnavailable(f"{run_dir.name} wrote no trajectory: {t.get('reason', 'no reason recorded')}")
    if t.get("format") != "txt":
        raise TrajectoryUnavailable(f"{run_dir.name} kept its trajectory as {t.get('format')!r}, not as the text file this reader reads")
    path = run_dir / t["file"]
    if not path.exists():
        raise TrajectoryUnavailable(
            f"{run_dir.name}/{t['file']} is gone. It was written and has since been removed, so the positions "
            f"cannot be read. Regenerating them means running the simulation again -- engine {t.get('engine')} "
            f"{t.get('engine_version')}, seed {t.get('seed')}, plan {t.get('plan_hash')} -- and the regenerated "
            f"coordinates must hash to {t.get('coords_sha256')}. That is the person's decision; this reader does not rerun")
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != t["sha256"]:
        raise TrajectoryUnavailable(f"{run_dir.name}/{t['file']} no longer matches what was written (file sha256 {got}, recorded {t['sha256']}); it is not read")
    data = np.loadtxt(path, comments="#", dtype=np.float64)
    n, f = t["particles"], t["frames"]
    d = t["box"]["dimensions"]
    coords = data[:, 2:2 + d].reshape(f, n, d).astype(t["dtype"])
    if coords_sha256(coords) != t["coords_sha256"]:
        raise TrajectoryUnavailable(f"{run_dir.name}/{t['file']}: the coordinates read back do not hash to the recorded array; the text does not reproduce the positions")
    out = {"steps": data[::n, 0].astype(int), "coords": coords, "meta": t}
    if len(t["columns"]) > 2 + d:
        out["theta"] = data[:, 2 + d].reshape(f, n).astype(t["dtype"])
    return out
