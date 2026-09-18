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
from pathlib import Path

import numpy as np

NAME = "mock_backend"
DIMENSIONS = 3

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
        """Take the commanded number of steps. The first call initialises."""
        if self.aborted:
            raise RuntimeError(f"backend aborted: {self.aborted}")
        if self.params is None:
            self.params = dict(params)
            n = int(params["n_particles"])
            box = float(params["box_length"])
            self.unwrapped = self.rng.uniform(0.0, box, size=(n, DIMENSIONS))
            self.wrapped = self.unwrapped.copy()
            self.frames = [self.unwrapped.copy()]
            self.frame_times = [0.0]

        dt = float(self.params["integration_timestep"])
        diffusivity = stokes_einstein(
            float(self.params["temperature"]),
            float(self.params["viscosity"]),
            float(self.params["bead_diameter"]),
        )
        box = float(self.params["box_length"])
        steps = int(params["steps"])
        step_scale = float(np.sqrt(2.0 * diffusivity * dt))

        for _ in range(steps):
            kick = self.rng.normal(0.0, step_scale, size=self.unwrapped.shape)
            self.unwrapped = self.unwrapped + kick
            self.steps_taken += 1

        # Derived from the integer step count, never accumulated. Adding dt ten
        # thousand times drifts downward -- it landed 2e-13 short of a 20 s
        # planned end, and the completion criterion `simulated_time >= planned`
        # then never fired on a run that had finished exactly as planned. The
        # step count is the integer truth and the time is a coordinate read off
        # it, which is the same reason this side's log keeps simulated time out
        # of its time base: it is declared, not measured.
        #
        # The fix belongs here and not in the criterion. Widening a declared
        # threshold by an epsilon would be the operator loosening a limit the
        # plan fixed, which is the one thing it may not do.
        self.simulated_time = self.steps_taken * dt
        self.wrapped = np.mod(self.unwrapped, box)
        self.frames.append(self.unwrapped.copy())
        self.frame_times.append(self.simulated_time)
        return {"steps_taken": self.steps_taken, "simulated_time": self.simulated_time}

    def read(self) -> dict:
        """Current state. The monitor's input; no judgement attached."""
        if self.unwrapped is None:
            return {"initialised": False}
        last = self.frames[-1] - self.frames[-2] if len(self.frames) > 1 else np.zeros(1)
        return {
            "initialised": True,
            "steps_taken": self.steps_taken,
            "simulated_time": self.simulated_time,
            "frames_saved": len(self.frames),
            "max_single_step_displacement": float(np.abs(last).max()),
            "max_absolute_coordinate": float(np.abs(self.unwrapped).max()),
        }

    def abort(self, reason: str) -> dict:
        self.aborted = reason
        return {"aborted": True, "reason": reason, "steps_taken": self.steps_taken}

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
        diffusivity = float(slope) / (2 * DIMENSIONS)
        return {
            "diffusivity": diffusivity,
            "diffusivity_standard_error": slope_se / (2 * DIMENSIONS),
            "relative_standard_error": abs(slope_se / float(slope)) if slope else None,
            "intercept": float(intercept),
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
