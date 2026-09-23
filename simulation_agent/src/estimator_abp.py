"""The estimators for the active observables, in two dimensions, in one place.

`estimator.py` is `tracer_diffusivity`'s: three dimensions, a fit over lags
from one save interval up to the window, and the intercept as the free-regime
diagnostic. The active vocabulary registered on 2026-09-23 reads the same
trajectory differently, and each entry's estimator is part of its identity
(contracts/observables.json rule 2), so each is written here once and both
active backends -- when there are two -- will delegate to it.

* `mean_squared_displacement` -- unwrapped, averaged over particles and time
  origins, on the lag grid the save interval gives, up to `max_lag_time`.
  Two dimensions: the z column a backend pads for the trajectory writer is
  not read.
* `effective_translational_diffusivity` -- weighted least squares of MSD
  against lag over lags from `fit_lag_range_lower_bound` up to
  `max_lag_time`, slope over 2*d with d = 2. The LOWER bound is the window
  that matters; read earlier the number is D_T under this name.
* `msd_loglog_slope` -- least-squares slope of log MSD on log lag over a
  declared lag range, and on a rolling window for the crossover.
* `persistence_time` -- the decay time of the orientational autocorrelation
  <cos(theta(t+tau) - theta(t))>, fitted on a log scale over lags where the
  correlation is still positive.

Uncertainties are block-resampled over particles, never the fit's own
(task 006 measured the fit's error at 36x too small on this side). With ten
particles in an arm the blocks are single particles and the error bar is
honest about being thin.

`a*t - 1 + exp(-a*t)` is never formed here, but the same cancellation waits
in any short-lag ratio: simulation-9 saw a slope of 572 from it. Slopes are
taken on logs of measured curves, not on differences of exponentials.
"""

from __future__ import annotations

import numpy as np

DIMENSIONS = 2
UNCERTAINTY_BLOCKS = 50


class ActiveEstimator:
    def __init__(self, frame_times: list, frames: list, orientations: list | None = None) -> None:
        self.frame_times = np.asarray(list(frame_times), dtype=float)
        self.frames = [np.asarray(f)[:, :DIMENSIONS] for f in frames]
        self.orientations = [np.asarray(o, dtype=float) for o in (orientations or [])]

    @property
    def n_frames(self) -> int:
        return len(self.frames)

    @property
    def n_particles(self) -> int:
        return int(self.frames[0].shape[0]) if self.frames else 0

    def _interval(self) -> float:
        return float(self.frame_times[1] - self.frame_times[0]) if len(self.frame_times) > 1 else 0.0

    # -- the curve ---------------------------------------------------------- #

    def mean_squared_displacement(self, max_lag_time: float, tracers=None) -> list[tuple[float, float]]:
        interval = self._interval()
        if not interval or self.n_frames < 2:
            return []
        coords = np.stack(self.frames)
        if tracers is not None:
            coords = coords[:, tracers, :]
        max_shift = min(int(max_lag_time / interval), self.n_frames - 1)
        out = []
        for shift in range(1, max_shift + 1):
            disp = coords[shift:] - coords[:-shift]
            out.append((float(shift * interval), float((disp ** 2).sum(axis=2).mean())))
        return out

    # -- the long-time slope ----------------------------------------------- #

    def _fit(self, curve, lower: float, upper: float, n_particles: int):
        lags = np.asarray([c[0] for c in curve]); msd = np.asarray([c[1] for c in curve])
        keep = (lags >= lower) & (lags <= upper)
        if keep.sum() < 2:
            return None
        lags, msd = lags[keep], msd[keep]
        shifts = np.round(lags / self._interval()).astype(int)
        independent = n_particles * np.maximum(self.n_frames // shifts, 1)
        w = np.sqrt(independent)
        slope, intercept = np.polyfit(lags, msd, 1, w=w)
        return float(slope) / (2 * DIMENSIONS), float(intercept), int(keep.sum()), float(lags.min()), float(lags.max())

    def fit_effective_diffusivity(self, lower: float, max_lag_time: float) -> dict:
        curve = self.mean_squared_displacement(max_lag_time)
        fit = self._fit(curve, lower, max_lag_time, self.n_particles) if curve else None
        if fit is None:
            return {"quantity": "effective_translational_diffusivity", "diffusivity": None,
                    "reason": f"the record holds {self.n_frames} frames and fewer than two lags fall between "
                              f"{lower} s and {max_lag_time} s; the run stopped before the fit range was filled",
                    "frames_saved": self.n_frames, "lags_used": 0}
        d, b, n, lo, hi = fit
        return {"quantity": "effective_translational_diffusivity", "diffusivity": d, "intercept": b,
                "lags_used": n, "shortest_lag": lo, "longest_lag": hi, "fit_lag_range_lower_bound": lower,
                "max_lag_time": max_lag_time, "dimensions": DIMENSIONS,
                "estimator": "contracts/observables.json: effective_translational_diffusivity -- weighted least squares of MSD on lag over lags at or above the declared lower bound, slope over 2*d, weights sqrt of independent displacements per lag"}

    def block_uncertainty(self, lower: float, max_lag_time: float) -> dict:
        n = self.n_particles
        blocks = min(UNCERTAINTY_BLOCKS, n)
        if blocks < 2:
            return {"standard_error": None, "reason": f"{n} particle(s) give fewer than two blocks"}
        idx = np.array_split(np.arange(n), blocks)
        values = []
        for block in idx:
            curve = self.mean_squared_displacement(max_lag_time, tracers=block)
            fit = self._fit(curve, lower, max_lag_time, len(block)) if curve else None
            if fit is not None:
                values.append(fit[0])
        if len(values) < 2:
            return {"standard_error": None, "reason": "fewer than two blocks produced a fit"}
        values = np.asarray(values)
        return {"standard_error": float(values.std(ddof=1) / np.sqrt(len(values))), "blocks": len(values),
                "block_values": [float(v) for v in values],
                "note": "block-resampled over particles, the honest error bar; single-particle blocks when the arm holds fewer particles than blocks"}

    def window_halves(self, lower: float, max_lag_time: float) -> dict:
        curve = self.mean_squared_displacement(max_lag_time)
        mid = 0.5 * (lower + max_lag_time)
        first = self._fit(curve, lower, mid, self.n_particles) if curve else None
        second = self._fit(curve, mid, max_lag_time, self.n_particles) if curve else None
        if first is None or second is None or first[0] <= 0 or second[0] <= 0:
            return {"log10_ratio": None, "reason": "one half of the fit range has fewer than two lags or a non-positive slope"}
        return {"first_half": first[0], "second_half": second[0],
                "log10_ratio": float(abs(np.log10(first[0] / second[0]))), "split_at": mid}

    # -- the crossover and the orientation --------------------------------- #

    def loglog_slope(self, max_lag_time: float, window_decades: float = 0.5) -> list[tuple[float, float]]:
        curve = self.mean_squared_displacement(max_lag_time)
        if len(curve) < 3:
            return []
        lags = np.log10([c[0] for c in curve]); msd = np.log10(np.maximum([c[1] for c in curve], 1e-300))
        out = []
        for i, centre in enumerate(lags):
            keep = np.abs(lags - centre) <= window_decades / 2
            if keep.sum() >= 3:
                out.append((float(10 ** centre), float(np.polyfit(lags[keep], msd[keep], 1)[0])))
        return out

    def orientation_autocorrelation(self, max_lag_time: float) -> list[tuple[float, float]]:
        interval = self._interval()
        if not self.orientations or not interval:
            return []
        theta = np.stack(self.orientations)
        max_shift = min(int(max_lag_time / interval), len(theta) - 1)
        return [(float(s * interval), float(np.cos(theta[s:] - theta[:-s]).mean())) for s in range(1, max_shift + 1)]

    def fit_persistence_time(self, max_lag_time: float, floor: float = 0.05) -> dict:
        curve = self.orientation_autocorrelation(max_lag_time)
        pts = [(t, c) for t, c in curve if c > floor]
        if len(pts) < 3:
            return {"persistence_time": None, "reason": "fewer than three lags with a positive orientational autocorrelation"}
        t = np.asarray([p[0] for p in pts]); c = np.asarray([p[1] for p in pts])
        slope, _ = np.polyfit(t, np.log(c), 1)
        if slope >= 0:
            return {"persistence_time": None, "reason": "the autocorrelation does not decay over the window"}
        return {"persistence_time": float(-1.0 / slope), "lags_used": len(pts), "longest_lag": float(t.max()),
                "floor": floor, "estimator": "contracts/observables.json: persistence_time -- exponential fit to the orientational autocorrelation over the declared lag window"}
