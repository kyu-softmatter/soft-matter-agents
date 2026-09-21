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

**Reduced units do not appear here.** The mock integrates the physical
equation in SI, so there is nothing to reduce. `hoomd_backend.py` is where the
conversion on the way in and out lives, because that is where an engine with
its own unit system starts (5.7 rule 4, D7).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np

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

# k_B from the authoritative registry rather than retyped here (D7). A
# constant is not policy, so reading it does not put an envelope in the
# backend (4.6.5).
_UNITS = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "units.json").read_text())
K_B = float(_UNITS["constants"]["k_B"]["value"])


def stokes_einstein(temperature: float, viscosity: float, diameter: float) -> float:
    """Translational diffusivity of a sphere, in SI.

    **The engine derives this rather than being handed it.** The plan carries a
    `diffusivity`, and that number is what the run is checked
    against -- so feeding it in as an input would make the success criterion
    compare the run against a value the run was given. What goes in is the bath
    and the particle; what comes out is a diffusivity that can disagree.
    """
    return K_B * temperature / (3.0 * np.pi * viscosity * diameter)


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

    def mean_squared_displacement(self, max_lag_time: float) -> list[tuple[float, float]]:
        """MSD against lag, from the saved frames.

        Unwrapped positions are used on purpose: a wrapped coordinate would
        make a tracer that crossed the boundary look like it jumped a box
        width, which is the artefact A3's image bound exists to keep out of
        the physics rather than to hide in the estimator.
        """
        times = np.asarray(self.frame_times)
        coords = np.stack(self.frames)
        interval = times[1] - times[1 - 1] if len(times) > 1 else 0.0
        out = []
        # The window asks for lags the record may not have. An aborted run has
        # a short record by definition, and a diverged run is not deleted --
        # divergence is a result (4.2) -- so the curve is cut to what exists
        # rather than raising. `fit_diffusivity` then reports no value with the
        # reason attached, which is the honest output for a run that stopped
        # before the estimator's window was filled.
        wanted = int(max_lag_time / interval) if interval else 0
        max_shift = min(wanted, len(times) - 1)
        for shift in range(1, max_shift + 1):
            disp = coords[shift:] - coords[:-shift]
            out.append((float(times[shift] - times[0]), float((disp ** 2).sum(axis=2).mean())))
        return out

    def fit_diffusivity(self, max_lag_time: float) -> dict:
        """The estimator contracts/observables.json declares, and no other.

        Weighted least squares of MSD against lag, intercept free, over lags
        from one save interval up to the window, and D = slope / (2 * dims).

        **The weighting is not a refinement.** A record of length T holds about
        T/tau independent displacements at lag tau, so the variance of the MSD
        estimate grows sharply with lag; equal weights hand the slope to the
        points with the fewest samples. Measured here, equal weights over
        whole-record lags gave a 7 per cent bias at 0.16 per cent relative
        standard error -- precise-looking and wrong. That measurement is what
        put the weighting in the contract, and this is the side that has to
        honour it.

        The same estimator has to run on the microscope side before
        `comparable` may become true (vocabulary rule 4). Being pinned is the
        precondition for that flag, not the evidence: the evidence is two runs.
        """
        curve = self.mean_squared_displacement(max_lag_time)
        if len(curve) < 2:
            return {
                "diffusivity": None,
                "reason": (
                    f"the record holds {len(self.frames)} frames, which is fewer than two lags "
                    "inside the window; the run stopped before the estimator could be applied"
                ),
                "frames_saved": len(self.frames),
                "lags_used": len(curve),
            }
        lags = np.asarray([c[0] for c in curve])
        msd = np.asarray([c[1] for c in curve])
        shifts = np.arange(1, len(curve) + 1)
        n_frames = len(self.frames)
        n_particles = self.unwrapped.shape[0]

        # Independent, not overlapping: about T/tau per tracer at lag tau.
        independent = n_particles * np.maximum(n_frames // shifts, 1)
        weights = np.sqrt(independent)

        slope, intercept = np.polyfit(lags, msd, 1, w=weights)
        residual = (msd - (slope * lags + intercept)) * weights
        dof = max(len(lags) - 2, 1)
        slope_se = float(
            np.sqrt((residual ** 2).sum() / dof / ((weights * (lags - np.average(lags, weights=weights ** 2))) ** 2).sum())
        )
        # The intercept's own uncertainty, from the same weighted fit.
        #
        # It is reported because the intercept is the estimator's stated
        # diagnostic -- observables.json leaves it free "so that localisation
        # error stays out of the slope" -- and this backend has no localisation
        # error, so a free-regime fit should return an intercept consistent with
        # zero. Without its uncertainty that sentence cannot be tested: run
        # run-20260920-002's intercept is 7.3 per cent of the MSD at the
        # shortest lag and 0.07 per cent at the longest, and with no standard
        # error beside it there is no way to tell sampling noise from a
        # short-lag artifact. That is unjudgeable rather than wrong, and one
        # number closes it.
        #
        # For a weighted straight-line fit the two variances share a
        # denominator: with Sw = sum(w^2), Swx = sum(w^2 x), Swxx = sum(w^2 x^2)
        # and D = Sw*Swxx - Swx^2, var(slope) = s^2*Sw/D and
        # var(intercept) = s^2*Swxx/D. So the ratio is Swxx/Sw and the intercept
        # follows from the slope error already computed, with no second fit and
        # no second convention to drift from it.
        w2 = weights ** 2
        intercept_se = float(slope_se * np.sqrt((w2 * lags ** 2).sum() / w2.sum()))
        # BOTH STANDARD ERRORS BELOW ARE TOO SMALL, AND BY A MEASURED AMOUNT.
        #
        # The fit treats the MSD points as independent observations. They are
        # not: every lag is computed from the same trajectories, so the points
        # are strongly correlated along the curve, and a weighted least squares
        # that ignores that returns a parameter error far tighter than the
        # estimator actually achieves. The weights here account for how many
        # displacements enter each lag and not for the correlation between
        # lags.
        #
        # Measured over eight seeds of this configuration, comparing the actual
        # spread of the estimate against what the fit quotes:
        #
        #     diffusivity   true scatter / quoted SE   ~41x
        #     intercept     true scatter / quoted SE    ~8x
        #
        # The estimator itself is sound -- across those seeds the mean sits
        # -0.06 per cent from the analytic Stokes-Einstein value, and the mean
        # intercept is consistent with zero. What is wrong is only the error
        # bar, and it is wrong in the dangerous direction.
        #
        # This matters to two criteria and not to the number. Run
        # run-20260920-002's intercept reads 6.4 sigma from zero against the
        # quoted error and 0.0 sigma against the measured scatter, so a
        # free-regime test evaluated against these would fail on an artifact
        # and send someone hunting a bug that is not there. And the plan's
        # `statistics_met`, which compares relative_standard_error against a
        # target, is comparing against a number about forty times too small --
        # it passes trivially and certifies nothing.
        #
        # Reported as they are, with this note, rather than silently rescaled:
        # the honest uncertainty for this configuration comes from the spread
        # across seeds, and choosing how to report that is revision 2's, not a
        # fudge factor's.
        diffusivity = float(slope) / (2 * DIMENSIONS)
        return {
            "diffusivity": diffusivity,
            "diffusivity_standard_error": slope_se / (2 * DIMENSIONS),
            "relative_standard_error": abs(slope_se / float(slope)) if slope else None,
            "intercept": float(intercept),
            "intercept_standard_error": intercept_se,
            "intercept_over_shortest_lag_msd": float(intercept / msd[0]) if msd[0] else None,
            "lags_used": len(lags),
            "shortest_lag": float(lags[0]),
            "longest_lag": float(lags[-1]),
            "independent_displacements_at_longest_lag": int(independent[-1]),
            "weighting": "number of independent displacements at each lag, about T/tau per tracer",
            "estimator": (
                "weighted least squares of msd against lag, free intercept, "
                "slope over twice the dimensions (contracts/observables.json)"
            ),
        }
