"""A fake simulation run that moves forward with the clock, for F6 without WSL or HOOMD.

`MockSimulation` writes a run folder shaped like soft-matter-agents'
`simulation_agent/runs/<run_id>/` (config.json, log.json, trajectory_meta.json,
observables.json) plus a numpy trajectory `trajectory.npz`, so `agents.simulation` reads it
the same way it reads a real run. Each `sync()` writes what the run would have reached by
then: the step count grows, the log gets more progress events, the trajectory more frames,
and observables.json appears when the run ends.

The run is fixed by its arguments and seed: the whole trajectory is drawn at construction
and `sync` only reveals more of it, so the files at a given time do not depend on how often
`sync` was called.

Writes go only under the `write_dir` given, never into the package or the soft-matter-agents
tree. The thermodynamic columns of the progress events (temperature, potential energy,
pressure) are made up for the graphs; the particles are free Brownian walkers.
"""

from __future__ import annotations

import io
import json
import os
import threading
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from .simulation import _RUN_ID_RE
from .sma_files import default_root

PACKAGE_DIR = Path(__file__).resolve().parents[1]
BACKEND = "mock_sim"
MAX_VALUES = 20_000_000  # frames x particles x 3 drawn at construction


class MockSimulation:
    """One fake run in `write_dir/<run_id>/`.

    Time runs at `steps_per_second` from `started_at`. Frame 0 is the start; one frame is
    saved every `steps_per_frame` steps, so a finished run has `frames + 1` frames.
    `fault_at_step` stops the run there with outcome "fault", like a diverged monitor.
    """

    def __init__(
        self,
        write_dir: str | os.PathLike[str],
        run_id: str = "mock-sim-001",
        *,
        n_particles: int = 64,
        dimensions: int = 2,
        frames: int = 200,
        steps_per_frame: int = 50,
        timestep: float = 0.002,
        steps_per_second: float = 2000.0,
        box_length: float = 20e-6,
        diffusivity: float = 2e-13,
        progress_every_frames: int = 10,
        fault_at_step: int | None = None,
        seed: int = 0,
        started_at: datetime | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not _RUN_ID_RE.match(run_id):
            raise ValueError(f"not a run id: {run_id!r}")
        if dimensions not in (2, 3):
            raise ValueError("dimensions must be 2 or 3")
        if frames < 1 or steps_per_frame < 1 or n_particles < 1 or steps_per_second <= 0:
            raise ValueError("frames, steps_per_frame, n_particles and the rate must be > 0")
        if (frames + 1) * n_particles * 3 > MAX_VALUES:
            raise ValueError("trajectory too large for a mock")
        self.write_dir = checked_write_dir(write_dir)
        self.run_id = run_id
        self.run_dir = self.write_dir / run_id
        self.n = n_particles
        self.dimensions = dimensions
        self.frames = frames
        self.steps_per_frame = steps_per_frame
        self.timestep = timestep
        self.steps_per_second = steps_per_second
        self.box_length = box_length
        self.diffusivity = diffusivity
        self.progress_every = max(1, progress_every_frames) * steps_per_frame
        self.steps_total = frames * steps_per_frame
        self.fault_at_step = fault_at_step
        self.seed = seed
        self.clock = clock or (lambda: datetime.now(UTC))
        self.started_at = started_at or self.clock()
        self._last_steps: int | None = None
        self._draw()

    def __repr__(self) -> str:
        return f"MockSimulation({str(self.run_dir)!r})"

    # -- the run, fixed at construction ----------------------------------------------------

    def _draw(self) -> None:
        rng = np.random.default_rng(self.seed)
        n, f = self.n, self.frames
        self.typeid = (np.arange(n) % 2).astype(np.int32)  # A and B alternate
        d_scale = np.where(self.typeid == 0, 1.0, 0.4)[:, None]  # B diffuses slower
        dt_frame = self.timestep * self.steps_per_frame
        sigma = np.sqrt(2 * self.diffusivity * dt_frame) * np.sqrt(d_scale)
        steps = rng.normal(size=(f, n, 3)) * sigma
        start = rng.uniform(0, self.box_length, size=(n, 3)) - self.box_length / 2
        if self.dimensions == 2:
            steps[..., 2] = 0
            start[:, 2] = 0
        pos = np.concatenate([start[None], start[None] + np.cumsum(steps, axis=0)])
        self.positions = pos.astype(np.float32)  # unwrapped, as the real runs record
        self.orientation = np.cumsum(rng.normal(scale=0.1, size=(f + 1, n)), axis=0)
        self.orientation[0] = rng.uniform(-np.pi, np.pi, size=n)
        self.thermo = {  # one row per frame
            "temperature": 293.0 + rng.normal(scale=1.5, size=f + 1),
            "potential_energy": -1e-19 * (1 - np.exp(-np.arange(f + 1) / (f / 5 + 1)))
            + rng.normal(scale=2e-22, size=f + 1),
            "pressure": 1.0e3 + rng.normal(scale=20.0, size=f + 1),
        }

    @property
    def last_step(self) -> int:
        """Where the run stops: the plan's end, or the fault."""
        if self.fault_at_step is not None:
            return min(self.fault_at_step, self.steps_total)
        return self.steps_total

    @property
    def finished_at(self) -> datetime:
        return self.started_at + timedelta(seconds=self.last_step / self.steps_per_second)

    def steps_at(self, now: datetime) -> int:
        dt = (now - self.started_at).total_seconds()
        return int(min(max(dt, 0.0) * self.steps_per_second, self.last_step))

    def done_at(self, now: datetime) -> bool:
        return self.steps_at(now) >= self.last_step

    # -- writing ---------------------------------------------------------------------------

    def sync(self, now: datetime | None = None) -> int:
        """Write the run as it stands at `now` (default: the clock). Returns the step."""
        now = now or self.clock()
        steps = self.steps_at(now)
        if steps == self._last_steps:
            return steps
        self.run_dir.mkdir(parents=True, exist_ok=True)
        done = steps >= self.last_step
        frames_saved = steps // self.steps_per_frame + 1
        if self._last_steps is None:
            _write_json(self.run_dir / "config.json", self._config())
        self._write_trajectory(frames_saved)
        _write_json(self.run_dir / "trajectory_meta.json", self._meta(steps, frames_saved, done))
        if done:
            _write_json(self.run_dir / "observables.json", self._observables(frames_saved))
        _write_json(self.run_dir / "log.json", self._log(steps, done))
        self._last_steps = steps
        return steps

    def _config(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "qid": None,
            "plan_id": None,
            "backend": BACKEND,
            "seed": self.seed,
            "parameters_si": {
                "integration_timestep": self.timestep,
                "total_simulated_time": self.steps_total * self.timestep,
                "save_interval": self.steps_per_frame * self.timestep,
                "box_length": self.box_length,
                "n_particles": float(self.n),
                "temperature": 293.0,
                "translational_diffusivity": self.diffusivity,
            },
            "mock": "written by dino_autofocus.agents.mock_sim; not a soft-matter-agents run",
        }

    def _state(self, steps: int, state: str) -> dict[str, Any]:
        frame = steps // self.steps_per_frame
        return {
            "state": state,
            "initialised": True,
            "handle": f"{BACKEND}:{self.seed}",
            "steps_taken": steps,
            "simulated_time": steps * self.timestep,
            "frames_saved": frame + 1,
            "fraction_of_planned_steps": steps / self.steps_total,
            "max_single_step_displacement": float(
                np.abs(np.diff(self.positions[max(frame - 1, 0): frame + 1], axis=0)).max(
                    initial=0.0)),
            "temperature": float(self.thermo["temperature"][frame]),
            "potential_energy": float(self.thermo["potential_energy"][frame]),
            "pressure": float(self.thermo["pressure"][frame]),
            "failure": None,
        }

    def _log(self, steps: int, done: bool) -> dict[str, Any]:
        def t(step: int) -> float:
            return step / self.steps_per_second

        events: list[dict[str, Any]] = [
            {"t_mono": 0.0, "time_base": "software", "event": "preflight", "report": {
                "backend": BACKEND, "steps_per_frame": self.steps_per_frame,
                "frames_expected": self.frames, "seed": self.seed, "n_particles": self.n}},
            {"t_mono": 0.0, "time_base": "software", "event": "dispatch",
             "action": "integrate", "state": "submitted"},
        ]
        marks = list(range(0, steps + 1, self.progress_every))
        if done and marks and marks[-1] == steps:
            marks.pop()  # the end event carries the last state
        for s in marks:
            events.append({"t_mono": t(s), "time_base": "software", "event": "progress",
                           "state": self._state(s, "running")})
        log: dict[str, Any] = {
            "artifact": "run_log",
            "run_id": self.run_id,
            "backend": BACKEND,
            "t0_wall": self.started_at.astimezone(UTC).isoformat(),
            "events": events,
        }
        if done:
            fault = self.fault_at_step is not None and self.last_step < self.steps_total
            outcome = "fault" if fault else "complete"
            monitor = "step_displacement_diverged" if fault else "planned_duration_reached"
            events.append({
                "t_mono": t(steps), "time_base": "software",
                "event": "abort" if fault else "complete",
                "monitor": {"id": monitor, "met": True, "outcome": outcome},
                "state": self._state(steps, outcome),
            })
            log["finished_at"] = self.finished_at.astimezone(UTC).isoformat()
        return log

    def _meta(self, steps: int, frames_saved: int, done: bool) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "run_id": self.run_id,
            "trajectory": {
                "format": "npz",
                "file": "trajectory.npz",
                "units": "metres (SI), unwrapped",
                "dtype": "float32",
                "frames": frames_saved,
                "written": True,
            },
            "frames_saved": frames_saved,
            "simulated_time": steps * self.timestep,
            "steps_taken": steps,
        }
        if done:
            fault = self.last_step < self.steps_total
            meta |= {
                "stopped_by": "step_displacement_diverged" if fault
                else "planned_duration_reached",
                "stop_outcome": "fault" if fault else "complete",
                "stopped_early": fault,
                "completed_planned_duration": not fault,
            }
        return meta

    def _write_trajectory(self, frames_saved: int) -> None:
        lz = self.box_length if self.dimensions == 3 else 0.0
        buf = io.BytesIO()
        np.savez(
            buf,
            positions=self.positions[:frames_saved],
            step=np.arange(frames_saved, dtype=np.int64) * self.steps_per_frame,
            typeid=self.typeid,
            types=np.array(["A", "B"]),
            box=np.array([self.box_length, self.box_length, lz, 0, 0, 0], dtype=np.float64),
            dimensions=np.array(self.dimensions),
            orientation=self.orientation[:frames_saved].astype(np.float32),
        )
        _write_bytes(self.run_dir / "trajectory.npz", buf.getvalue())

    def _observables(self, frames_saved: int) -> dict[str, Any]:
        """Mean squared displacement of the mock's own trajectory, against lag."""
        pos = self.positions[:frames_saved].astype(np.float64)
        dt_frame = self.timestep * self.steps_per_frame
        lags = range(1, max(2, frames_saved // 4))
        curve = []
        for k in lags:
            if k >= frames_saved:
                break
            d = pos[k:] - pos[:-k]
            curve.append([k * dt_frame, float((d ** 2).sum(axis=-1).mean())])
        return {
            "run_id": self.run_id,
            "observable": "mean_squared_displacement",
            "window_parameter": "max_lag_time",
            "window_si": curve[-1][0] if curve else 0.0,
            "msd_curve": curve,
            "fit": {"diffusivity_declared": self.diffusivity, "lags_used": len(curve)},
        }


def make_mock_runs(write_dir: str | os.PathLike[str], *,
                   clock: Callable[[], datetime] | None = None) -> list[MockSimulation]:
    """A small set for the screen: two finished runs (2D, and 3D that faulted) and one that
    is running for about ten minutes from now."""
    clock = clock or (lambda: datetime.now(UTC))
    now = clock()
    return [
        MockSimulation(write_dir, "mock-sim-2d-done", seed=1, clock=clock,
                       started_at=now - timedelta(hours=2)),
        MockSimulation(write_dir, "mock-sim-3d-fault", dimensions=3, n_particles=128,
                       fault_at_step=6_000, seed=2, clock=clock,
                       started_at=now - timedelta(hours=1)),
        MockSimulation(write_dir, "mock-sim-2d-running", n_particles=200, frames=600,
                       steps_per_frame=100, steps_per_second=100.0, seed=3, clock=clock,
                       started_at=now - timedelta(seconds=30)),
    ]


class MockTicker:
    """Calls `sync` on the runs every `interval` seconds in a daemon thread until stopped."""

    def __init__(self, sims: Iterable[MockSimulation], interval: float = 1.0) -> None:
        self.sims = list(sims)
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> MockTicker:
        for s in self.sims:
            s.sync()
        self._thread = threading.Thread(target=self._run, name="mock-sim-ticker", daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            for s in self.sims:
                s.sync()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def __enter__(self) -> MockTicker:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()


def checked_write_dir(write_dir: str | os.PathLike[str]) -> Path:
    """`write_dir`, refused when it lies in the package or the soft-matter-agents tree."""
    p = Path(write_dir).resolve()
    for guarded in (PACKAGE_DIR, default_root().resolve()):
        if p == guarded or guarded in p.parents:
            raise ValueError(f"the mock simulation does not write inside {guarded}: {p}")
    return p


def _write_json(path: Path, data: Any) -> None:
    _write_bytes(path, json.dumps(data, indent=2).encode("utf-8"))


def _write_bytes(path: Path, data: bytes) -> None:
    """Write beside, then replace, so a reader never sees half a file. Windows refuses the
    replace while a reader has the target open, so it is retried for a moment."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(data)
    for attempt in range(50):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(0.02)
