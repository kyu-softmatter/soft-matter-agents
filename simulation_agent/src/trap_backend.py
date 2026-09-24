"""The trap backend: one sphere in a harmonic trap under uniform flow, in NumPy.

For `bd_overdamped_trapped_uniform_flow`. Same four-call interface as
`mock_backend` and `hoomd_backend` (4.6.5) -- `preflight / apply / read /
abort`, a handle that returns before the run ends, the same five states -- so
the operator sees nothing new and drives it with the monitors the plan
declares.

**This is the mock-class backend for this configuration, and it is not HOOMD.**
`contracts/capabilities/simulation.json` declares `devices: [hoomd_backend]` and
`executed_by: hoomd_backend` for it. This agent's standing order is that the
pipeline is verified on a mock first and HOOMD attaches after (4.6.5, 9), so
the run this file makes records `trap_backend` as its engine and the
capability's `executed_by` is now a record that has to move after the fact --
a field no code reads, which is why it moves after and not before (7.2).

The equation, in SI throughout, trap centre at the origin, flow along +x:

    dx = [ -(k_t/gamma) * x + v * e_x ] dt + sqrt(2*D*dt) * xi
    gamma = 3*pi*eta*d ,  D = k_B*T/gamma

**Uniform flow and a constant force are the same thing here, and that is why
there is no fluid.** In the overdamped limit a particle's velocity relative to
the fluid is its force over gamma, so a fluid moving at v past a fixed trap
and a force gamma*v in a still fluid produce the identical update. Nothing in
this model represents the fluid except the drift term. Near a wall the two
would part -- the drag is no longer Stokes and the flow is no longer uniform
-- which is the A7 limit this configuration does not declare.

**Euler-Maruyama and not the exact Ornstein-Uhlenbeck update, on purpose.** The
coordinate here IS an OU process and has an exact discrete propagator that is
correct at any step, which would make A1's timestep bounds vacuous. That is
the wrong thing to run: the plan's A1 card bounds the step for the scheme an
engine actually uses, and HOOMD's Brownian method is Euler-Maruyama. A smoke
run on the exact update would pass a check it never exercised. So the scheme
is the one A1 was written for, and the estimator reports the one quantity it
biases (the variance, by dt/(2*tau)) beside the one it does not (the mean).

**The trajectory starts at the trap centre with the flow switched on.** The
displaced mean is approached as exp(-t/tau), which is what the plan's
`startup_discard` is sized against; the estimator discards it and reads only
what follows. The backend does not decide when steady state has arrived --
that criterion is declared in the plan before the run (this agent's hardest
discipline) and evaluated by the estimator on the plan's number.

The backend holds no policy. Limits belong to the envelope and the operator.
"""

from __future__ import annotations

import math
import threading
import time

import numpy as np

from . import estimator_trap, physics
from .mock_backend import ABORTED, COMPLETE, FAILED, RUNNING, SUBMITTED, TERMINAL

NAME = "trap_backend"
SPATIAL_COMPONENTS = 3
DIMENSIONS = SPATIAL_COMPONENTS
N_PARTICLES = 1          # the configuration is one sphere; it is not a parameter

REQUIRED = (
    "integration_timestep", "save_interval", "record_length", "box_length",
    "temperature", "viscosity", "bead_diameter", "trap_stiffness", "flow_speed",
    "startup_discard",
)


def engine_build() -> dict:
    return {"engine": "numpy", "numpy": np.__version__, "scheme": "euler_maruyama",
            "note": "not HOOMD: the mock-class backend for this configuration (4.6.5)"}


class TrapBackend:
    """One overdamped sphere, a harmonic trap at the origin, uniform flow along +x."""

    NAME = NAME

    def __init__(self, seed: int = 0) -> None:
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.params: dict | None = None
        self.position: np.ndarray | None = None
        self.frames: list[np.ndarray] = []
        self.frame_times: list[float] = []
        self.simulated_time = 0.0
        self.steps_taken = 0
        self.state = None
        self.failure: str | None = None
        self.handle: str | None = None
        self.integration_wall_s: float | None = None
        self.steps_planned: int | None = None
        # The largest displacement in ONE integration step over the run so far.
        # This backend reported the frame-to-frame displacement under the name
        # max_single_step_displacement until the HOOMD build measured a true
        # single step beside it: 0.0185 um here against 0.0078 um there, at the
        # same cell, because a frame is twenty steps. It was the pattern
        # mock_backend uses, and it was safe -- the divergence criterion saw a
        # LARGER number than the step -- but the name was false, and two
        # backends reporting different quantities under one name is exactly
        # what makes a mock-against-engine comparison unreadable.
        # run-20260923-201-smoke-s1 carries the frame-level figure and stays so.
        self.largest_single_step: float | None = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # -- the fixed interface ------------------------------------------------

    def preflight(self, params: dict) -> dict:
        """Report what would happen. Touches nothing and decides nothing."""
        missing = [k for k in REQUIRED if k not in params]
        out = {"backend": NAME, "engine_build": engine_build(),
               "missing_parameters": missing, "seed": self.seed, "n_particles": N_PARTICLES}
        if missing:
            out.update(steps_per_frame=None, frames_expected=None, save_interval_divides_step=False)
            return out
        dt, save = float(params["integration_timestep"]), float(params["save_interval"])
        per_frame = round(save / dt)
        # The plan declares the WINDOW (record_length, the observable's
        # registered window parameter) and the startup; the duration is their
        # sum, derived here. Summed in the plan and rounded to one figure, the
        # startup was lost into the record -- 0.2 + 6 = 6.2 rounds to 6.
        total = float(params["startup_discard"]) + float(params["record_length"])
        gamma = 3.0 * math.pi * float(params["viscosity"]) * float(params["bead_diameter"])
        tau = gamma / float(params["trap_stiffness"])
        out.update(
            steps_per_frame=per_frame,
            frames_expected=round(total / save),
            total_simulated_time_si=total,
            save_interval_divides_step=abs(per_frame * dt - save) < 1e-12 * max(1.0, save),
            relaxation_time_si=tau,
            timestep_over_relaxation_time=dt / tau,
            # Euler-Maruyama on this drift is stable for dt < 2*tau and oscillates
            # for dt > tau. Reported and not enforced: the bound is A1's, in the
            # plan, and a backend that refused on its own would hold policy.
            euler_maruyama_stable=dt < 2.0 * tau,
            predicted_offset_si=gamma * float(params["flow_speed"]) / float(params["trap_stiffness"]),
        )
        # The plan's sweep axis is the offset in thermal widths and the speed is
        # derived from it at one significant figure, so the offset actually
        # realised differs from the level's label. Reported, not corrected: the
        # speed is what is integrated and the label is what the grid is named by.
        sigma = math.sqrt(physics.K_B * float(params["temperature"]) / float(params["trap_stiffness"]))
        out["realised_offset_over_sigma"] = out["predicted_offset_si"] / sigma
        if "offset_over_sigma" in params:
            out["declared_offset_over_sigma"] = float(params["offset_over_sigma"])
        return out

    def apply(self, params: dict) -> dict:
        """Submit the run and return. Does not block until it finishes."""
        if self._worker is not None:
            raise RuntimeError("this backend has already been given a run")
        pre = self.preflight(params)
        if pre["missing_parameters"]:
            raise ValueError(f"missing {pre['missing_parameters']}")
        self.params = dict(params)
        self.position = np.zeros((N_PARTICLES, DIMENSIONS))      # at the trap centre
        self.frames = [self.position.copy()]
        self.frame_times = [0.0]
        self.state = SUBMITTED
        self.handle = f"{NAME}:{self.seed}:{id(self):x}"
        self._worker = threading.Thread(target=self._integrate, name=self.handle, daemon=True)
        submitted_as = self.state
        self._worker.start()
        return {"handle": self.handle, "state": submitted_as}

    def _integrate(self) -> None:
        """The run itself. The stop flag is read, never interpreted."""
        try:
            p = self.params
            dt = float(p["integration_timestep"])
            gamma = 3.0 * math.pi * float(p["viscosity"]) * float(p["bead_diameter"])
            D = physics.K_B * float(p["temperature"]) / gamma
            relax = float(p["trap_stiffness"]) / gamma                # 1/tau
            drift = np.array([float(p["flow_speed"]), 0.0, 0.0])      # v along +x
            noise = math.sqrt(2.0 * D * dt)
            pre = self.preflight(p)
            per_frame, frames = int(pre["steps_per_frame"]), int(pre["frames_expected"])
            with self._lock:
                self.steps_planned = per_frame * frames
                self.state = RUNNING
            x = self.position.copy()
            largest = 0.0
            started = time.perf_counter()
            for _ in range(frames):
                if self._stop.is_set():
                    with self._lock:
                        self.state = ABORTED
                    return
                xi = self.rng.normal(0.0, 1.0, size=(per_frame, N_PARTICLES, DIMENSIONS))
                for j in range(per_frame):
                    step = (drift - relax * x) * dt + noise * xi[j]
                    largest = max(largest, float(np.abs(step).max()))
                    x = x + step
                with self._lock:
                    self.largest_single_step = largest
                    self.position = x
                    self.steps_taken += per_frame
                    # Derived from an integer step count, never accumulated
                    # (this agent's CLAUDE.md: the 19.999999999999794 incident).
                    self.simulated_time = self.steps_taken * dt
                    self.frames.append(x.copy())
                    self.frame_times.append(self.simulated_time)
            with self._lock:
                self.integration_wall_s = time.perf_counter() - started
                self.state = COMPLETE
        except Exception as exc:                       # noqa: BLE001
            with self._lock:
                self.failure = f"{type(exc).__name__}: {exc}"
                self.state = FAILED

    def read(self) -> dict:
        """Poll the submitted run. The monitor's input; no judgement attached."""
        with self._lock:
            if self.state is None:
                return {"state": None, "initialised": False}
            return {
                "state": self.state,
                "initialised": True,
                "handle": self.handle,
                "steps_taken": self.steps_taken,
                "simulated_time": self.simulated_time,
                "frames_saved": len(self.frames),
                # A RATIO OF TWO INTEGERS, so it reads exactly 1.0 at the end.
                # The completion criterion compares against it, and a criterion
                # comparing a running float sum against a planned end is the
                # 19.999999999999794 incident this agent's CLAUDE.md records.
                "fraction_of_planned_steps": (self.steps_taken / self.steps_planned
                                              if self.steps_planned else 0.0),
                "max_single_step_displacement": float(self.largest_single_step or 0.0),
                "max_absolute_coordinate": float(np.abs(self.position).max()),
                "failure": self.failure,
            }

    def abort(self, reason: str) -> dict:
        """Interrupt and wait: the trajectory is read after, so the worker must be done."""
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=30)
        with self._lock:
            if self.state not in TERMINAL:
                self.state = ABORTED
            return {"aborted": True, "reason": reason, "state": self.state,
                    "steps_taken": self.steps_taken}

    # -- the reading, delegated -------------------------------------------

    def estimator(self) -> estimator_trap.TrapEstimator:
        with self._lock:
            return estimator_trap.TrapEstimator(list(self.frame_times), list(self.frames), self.params)

    def observables(self, params: dict) -> dict:
        """What O4 writes to observables.json for this configuration.

        The operator's record step was written for `tracer_diffusivity` and
        calls `fit_diffusivity(max_lag_time)`. This backend does not grow a
        method by that name: its observable is a mean offset, and a method
        called fit_diffusivity returning one would be a label that lies. The
        operator asks for this instead when the backend has it.
        """
        est = self.estimator()
        steps = max(1, self.steps_taken)
        return {
            "window_parameter": "record_length",
            "window_si": est.record_length,
            "drag_offset": est.drag_offset(),
            "recovered_stiffness": est.recovered_stiffness(),
            "relaxation_time": est.relaxation_time(),
            "transverse": est.transverse(),
            # The smoke run's second purpose (A5): the cost per step on THIS
            # backend at N=1, measured over the integration loop only, so it
            # excludes process start and polling the way the earlier
            # 1000-particle figure did not.
            "cost": {
                "integration_wall_s": self.integration_wall_s,
                "steps": self.steps_taken,
                "wall_s_per_step": (self.integration_wall_s / steps) if self.integration_wall_s else None,
                "n_particles": N_PARTICLES,
                "backend": NAME,
                "note": ("measured on the integration loop alone. It calibrates THIS backend; it "
                         "is not HOOMD's per-step cost and replaces the a5 bracket only for runs "
                         "made here"),
            },
        }
