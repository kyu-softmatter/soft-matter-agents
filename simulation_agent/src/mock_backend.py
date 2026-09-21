"""The mock backend -- a first-class one (plan.md 4.6.5).

The whole pipeline has to run without HOOMD, because that is how it gets
validated before an engine is attached (9.2 rule 4). So this is not a stub
that returns canned numbers: it integrates the overdamped equation of motion
for free tracers and the diffusivity has to be recovered from its output the
same way it would be from a real trajectory. A mock that returned the answer
would validate nothing.

**It holds no policy** (4.6.5). It does not know what a limit is, does not
decide whether a run may proceed, and does not stop itself: the envelope and
the operator own all of that. A backend that judged conditions would put the
envelope in two places, and then the two would disagree.

The fixed interface is `preflight / apply / read / abort`. Whether those four
are enough for both HOOMD and a microscope is 11-4, still open; this file is
half of the evidence.

**The estimator is not here.** `estimator.py` holds the fit
`contracts/observables.json` declares, and this file delegates to it, because
two backends each holding their own copy would be two estimators (5.7 rule 4,
and the reason `comparable` is gated on the same one having run).

**Reduced units do not appear here.** The mock integrates the physical
equation in SI, so there is nothing to reduce. `hoomd_backend.py` is where the
conversion on the way in and out lives, because that is where an engine with
its own unit system starts (5.7 rule 4, D7).
"""

from __future__ import annotations

import threading

import numpy as np

from . import estimator as estimator_module
from . import physics

NAME = "mock_backend"
DIMENSIONS = 3

# The states `read()` may report. SUBMITTED is the one worth naming: it is
# neither running nor failed, it is nearly instant locally and real in a
# queue, and leaving the slot out now is how `read()` comes to report it as an
# error later.
SUBMITTED, RUNNING, COMPLETE, ABORTED, FAILED = (
    "submitted", "running", "complete", "aborted", "failed",
)
TERMINAL = (COMPLETE, ABORTED, FAILED)

# k_B and Stokes-Einstein live in `physics`, because the engine backend needs
# both and one formula in two files is one formula that drifts (11-11). Named
# here so the reader of this file still meets them where they are used.
K_B = physics.K_B
stokes_einstein = physics.stokes_einstein


class MockBackend:
    """Free overdamped Brownian motion, integrated in SI units."""

    def __init__(self, seed: int = 0) -> None:
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.params: dict | None = None
        self.unwrapped: np.ndarray | None = None
        self.wrapped: np.ndarray | None = None
        self.frames: list[np.ndarray] = []
        self.frame_times: list[float] = []
        self.simulated_time = 0.0
        self.steps_taken = 0
        self.aborted: str | None = None
        self.state = None
        self.failure: str | None = None
        self.handle: str | None = None
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # -- the fixed interface ------------------------------------------------

    def preflight(self, params: dict) -> dict:
        """Report what would happen. Touches nothing and decides nothing."""
        required = (
            "n_particles",
            "integration_timestep",
            "save_interval",
            "total_simulated_time",
            "box_length",
            "temperature",
            "viscosity",
            "bead_diameter",
        )
        missing = [k for k in required if k not in params]
        steps_per_frame = (
            round(params["save_interval"] / params["integration_timestep"])
            if not missing
            else None
        )
        return {
            "backend": NAME,
            "missing_parameters": missing,
            "steps_per_frame": steps_per_frame,
            "frames_expected": (
                round(params["total_simulated_time"] / params["save_interval"])
                if not missing
                else None
            ),
            "save_interval_divides_step": (
                bool(missing) is False
                and abs(steps_per_frame * params["integration_timestep"] - params["save_interval"])
                < 1e-12
            ),
            "diffusivity_si": (
                None
                if missing
                else stokes_einstein(
                    params["temperature"], params["viscosity"], params["bead_diameter"]
                )
            ),
            "seed": self.seed,
        }

    def apply(self, params: dict) -> dict:
        """Submit the run and return. **Does not block until it finishes.**

        The reason is not a scheduler someday: a run that blocks inside
        `apply()` can be neither aborted nor observed while it lasts, so the
        monitors compiled from the plan would have nothing to watch and the
        stop criteria could only be evaluated after the fact. `read()` polls,
        `abort()` interrupts, and a later scheduler replaces this file rather
        than the operator.

        Returns a handle and the state `submitted`. Locally the worker starts
        at once, so the first `read()` may already say `running` -- both are
        correct answers, and that is the point of the state existing.
        """
        if self._worker is not None:
            raise RuntimeError("this backend has already been given a run")
        required = self.preflight(params)
        if required["missing_parameters"]:
            raise ValueError(f"missing {required['missing_parameters']}")

        self.params = dict(params)
        n = int(params["n_particles"])
        box = float(params["box_length"])
        self.unwrapped = self.rng.uniform(0.0, box, size=(n, DIMENSIONS))
        self.wrapped = self.unwrapped.copy()
        self.frames = [self.unwrapped.copy()]
        self.frame_times = [0.0]
        self.state = SUBMITTED
        self.handle = f"{NAME}:{self.seed}:{id(self):x}"

        self._worker = threading.Thread(target=self._integrate, name=self.handle, daemon=True)
        # The state reported is the state it was submitted in, captured before
        # the worker can move it. Reading `self.state` after starting the
        # thread would report whatever happened in the microseconds since,
        # which is how a real state becomes one nobody ever observes.
        submitted_as = self.state
        self._worker.start()
        return {"handle": self.handle, "state": submitted_as}

    def _integrate(self) -> None:
        """The run itself. Nothing here decides whether it may continue.

        The stop flag is read but not interpreted: the operator sets it, on a
        comparison the plan declared. A backend that judged its own conditions
        would put the envelope in two places (4.6.5).
        """
        try:
            dt = float(self.params["integration_timestep"])
            diffusivity = stokes_einstein(
                float(self.params["temperature"]),
                float(self.params["viscosity"]),
                float(self.params["bead_diameter"]),
            )
            box = float(self.params["box_length"])
            step_scale = float(np.sqrt(2.0 * diffusivity * dt))
            pre = self.preflight(self.params)
            per_frame, frames = int(pre["steps_per_frame"]), int(pre["frames_expected"])
            with self._lock:
                self.state = RUNNING

            for _ in range(frames):
                if self._stop.is_set():
                    with self._lock:
                        self.state = ABORTED
                    return
                positions = self.unwrapped
                for _ in range(per_frame):
                    positions = positions + self.rng.normal(
                        0.0, step_scale, size=positions.shape
                    )
                with self._lock:
                    self.unwrapped = positions
                    self.steps_taken += per_frame
                    # Derived from the integer step count, never accumulated:
                    # summing dt ten thousand times landed 2e-13 below a 20 s
                    # planned end, and the completion criterion was then false
                    # on a run that finished exactly as planned. The drift also
                    # moves with dt, so whether the criterion worked depended on
                    # where in A1's interval the plan landed.
                    self.simulated_time = self.steps_taken * dt
                    self.wrapped = np.mod(self.unwrapped, box)
                    self.frames.append(self.unwrapped.copy())
                    self.frame_times.append(self.simulated_time)
            with self._lock:
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
            last = (
                self.frames[-1] - self.frames[-2] if len(self.frames) > 1 else np.zeros(1)
            )
            return {
                "state": self.state,
                "initialised": True,
                "handle": self.handle,
                "steps_taken": self.steps_taken,
                "simulated_time": self.simulated_time,
                "frames_saved": len(self.frames),
                "max_single_step_displacement": float(np.abs(last).max()),
                "max_absolute_coordinate": float(np.abs(self.unwrapped).max()),
                "failure": self.failure,
            }

    def abort(self, reason: str) -> dict:
        """Interrupt a submitted or running job and wait for it to stop.

        Waiting matters: the trajectory is read after the abort, and reading it
        while the worker is still appending would report a record nobody ran.
        """
        self.aborted = reason
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=30)
        with self._lock:
            if self.state not in TERMINAL:
                self.state = ABORTED
            return {
                "aborted": True,
                "reason": reason,
                "state": self.state,
                "steps_taken": self.steps_taken,
            }

    # -- trajectory output -------------------------------------------------
    #
    # **The reading is not this file's.** `estimator.Estimator` holds the fit
    # the vocabulary declares, and both backends delegate to it: two copies of
    # one estimator are two estimators, and the first thing to drift would be
    # the weighting, which was measured into the contract rather than argued
    # into it. What stays here is the physics -- integrating the equation of
    # motion and keeping the frames.
    #
    # Built fresh per call over the record as it stands, so a read during a run
    # sees what has been saved so far and a read after it sees all of it. The
    # worker appends under a lock and these only read, which is the same
    # arrangement as before the estimator moved out.

    def estimator(self) -> estimator_module.Estimator:
        return estimator_module.Estimator(self.frame_times, self.frames)

    def mean_squared_displacement(self, max_lag_time: float,
                                  tracers: "np.ndarray | None" = None) -> list[tuple[float, float]]:
        return self.estimator().mean_squared_displacement(max_lag_time, tracers=tracers)

    def fit_diffusivity(self, max_lag_time: float) -> dict:
        return self.estimator().fit_diffusivity(max_lag_time)

    def block_uncertainty(self, max_lag_time: float) -> dict:
        return self.estimator().block_uncertainty(max_lag_time)

    def window_halves(self, max_lag_time: float) -> dict:
        return self.estimator().window_halves(max_lag_time)
