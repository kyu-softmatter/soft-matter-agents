"""The estimator, in one place, because two copies of it are two estimators.

`contracts/observables.json` pins how `tracer_diffusivity` is extracted from a
trajectory, and **`comparable` means the same estimator demonstrably ran on
both sides**. That is the cross-side rule; this file exists for the same reason
one level in. Two backends on THIS side -- the mock and the engine -- each
holding their own fit would be the same defect with the two copies closer
together and harder to notice, and the first thing to drift would be the
weighting, which is the part that was measured into the contract rather than
argued into it.

So a backend owns the physics and this owns the reading. Nothing here knows
what produced the frames: it takes the saved times and positions and applies
the declared fit. `mock_backend` integrates the overdamped equation in SI and
`hoomd_backend` will run an engine in reduced units and convert on the way
out; by the time either of them reaches this file the difference is gone.

Moved out of `mock_backend.py` unchanged. The test that it is unchanged is
that both result cards on disk rebuild byte-identical, which is what they are
for -- a refactor of an estimator that nobody can show to be a refactor is a
new estimator.
"""

from __future__ import annotations

import numpy as np

DIMENSIONS = 3


class Estimator:
    """The declared estimator over one run's saved record.

    Built from the frames a backend kept, not from the backend: `frame_times`
    in seconds and `frames` as a list of (n_particles, DIMENSIONS) arrays of
    UNWRAPPED positions in metres. Unwrapped is not a preference -- a wrapped
    coordinate makes a tracer that crossed the boundary look like it jumped a
    box width, which is the artefact A3's image bound exists to keep out of the
    physics rather than to hide in the estimator.
    """

    def __init__(self, frame_times: list, frames: list) -> None:
        self.frame_times = list(frame_times)
        self.frames = list(frames)

    @property
    def n_frames(self) -> int:
        return len(self.frames)

    @property
    def n_particles(self) -> int:
        return int(self.frames[0].shape[0]) if self.frames else 0

    def mean_squared_displacement(self, max_lag_time: float,
                                  tracers: "np.ndarray | None" = None) -> list[tuple[float, float]]:
        """MSD against lag, from the saved frames.

        Unwrapped positions are used on purpose: a wrapped coordinate would
        make a tracer that crossed the boundary look like it jumped a box
        width, which is the artefact A3's image bound exists to keep out of
        the physics rather than to hide in the estimator.

        `tracers` restricts the average to a subset, which is what lets the
        uncertainty be estimated by refitting blocks of tracers. It changes
        nothing when omitted: the default is every tracer, which is the curve
        the estimator has always returned.
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
        if tracers is not None:
            coords = coords[:, tracers, :]
        for shift in range(1, max_shift + 1):
            disp = coords[shift:] - coords[:-shift]
            out.append((float(times[shift] - times[0]), float((disp ** 2).sum(axis=2).mean())))
        return out

    # Number of independent tracer blocks the uncertainty is estimated over.
    #
    # Chosen by measuring it rather than by argument. Against the across-seed
    # scatter over 32 seeds of this configuration, which is what this number
    # has to reproduce:
    #
    #     10 blocks   truth/block  1.25x
    #     20 blocks                1.16x
    #     50 blocks                1.11x
    #    100 blocks                1.11x
    #
    # It flattens at 50 and 100 buys nothing, so 50. The shape of the
    # trade-off is the expected one -- the scatter of the block estimates is
    # itself uncertain by about 1/sqrt(2*(B-1)), so too few blocks give a noisy
    # error bar, while too many leave each block with too few tracers for its
    # own fit to behave -- but the flattening point is a fact about this
    # ensemble size and not something the argument predicts.
    UNCERTAINTY_BLOCKS = 50

    def fit_over(self, max_lag_time: float, tracers: "np.ndarray") -> "tuple[float, float] | None":
        """The same estimator, run over one block of tracers.

        Returns (diffusivity, intercept). Both are needed because both are
        compared against a criterion: the diffusivity is the answer and the
        intercept is the free-regime diagnostic, and an honest error bar on one
        says nothing about the other.

        Used only to estimate uncertainty. It must stay the same estimator -- a
        block fitted differently from the whole would measure the difference
        between two estimators and report it as noise.
        """
        curve = self.mean_squared_displacement(max_lag_time, tracers=tracers)
        if len(curve) < 2:
            return None
        lags = np.asarray([c[0] for c in curve])
        msd = np.asarray([c[1] for c in curve])
        shifts = np.arange(1, len(curve) + 1)
        independent = len(tracers) * np.maximum(self.n_frames // shifts, 1)
        slope, intercept = np.polyfit(lags, msd, 1, w=np.sqrt(independent))
        return float(slope) / (2 * DIMENSIONS), float(intercept)

    def window_halves(self, max_lag_time: float) -> dict:
        """The same estimator over each half of the lag range, and the gap.

        **This is what separates converged from precise, and no error bar
        reports it.** A fit that reaches past the free regime disagrees with
        itself across the window while each half stays tight: the first half
        sees the free slope, the second sees whatever hindrance has set in, and
        a standard error computed over the whole range describes neither. The
        block estimate cannot see it either -- every block spans the same lags,
        so they agree with each other about the same wrong slope.

        Revision 2's `window_insensitive` compares
        `log10(D_first_half / D_second_half)` against the decade target. Nothing
        recorded it, so the criterion could not be evaluated at all; this is the
        measurement it names.

        The same estimator over both halves, restricted to a slice of the lag
        range rather than refitted differently -- a half fitted another way
        would measure the difference between two estimators and report it as
        physics, which is the mistake `fit_over` carries the same warning
        about.
        """
        curve = self.mean_squared_displacement(max_lag_time)
        if len(curve) < 4:
            return {
                "method": "lag_range_halves",
                "log10_ratio": None,
                "reason": (f"the window holds {len(curve)} lags and a split needs at least two "
                           "fittable points on each side"),
            }
        mid = len(curve) // 2
        first = self.fit_lag_slice(curve, 0, mid)
        second = self.fit_lag_slice(curve, mid, len(curve))
        if first is None or second is None or second[0] == 0:
            return {
                "method": "lag_range_halves",
                "log10_ratio": None,
                "reason": "one half of the window did not yield a fittable slope",
            }
        return {
            "method": "lag_range_halves",
            "split_lag": float(curve[mid][0]),
            "first_half": {"diffusivity": first[0], "lags": [curve[0][0], curve[mid - 1][0]]},
            "second_half": {"diffusivity": second[0], "lags": [curve[mid][0], curve[-1][0]]},
            "log10_ratio": float(abs(np.log10(first[0] / second[0]))) if first[0] > 0 and second[0] > 0 else None,
            "note": (
                "the declared estimator run over each half of the lag range. A fit reaching past "
                "the free regime disagrees with itself here while each half stays tight, and "
                "neither the fit's own error nor the block estimate can report that -- every "
                "block spans the same lags"
            ),
        }

    def fit_lag_slice(self, curve: list, lo: int, hi: int) -> "tuple[float, float] | None":
        """The estimator over `curve[lo:hi]`, weighted by that slice's own shifts.

        The shift indices are the slice's real ones and not `1..n`: the weight
        is how many independent displacements entered each lag, about
        `n_frames // shift`, so renumbering a slice from one would weight the
        second half as if it were the first and quietly change the estimator.
        """
        part = curve[lo:hi]
        if len(part) < 2:
            return None
        lags = np.asarray([c[0] for c in part])
        msd = np.asarray([c[1] for c in part])
        shifts = np.arange(lo + 1, hi + 1)
        independent = self.n_particles * np.maximum(self.n_frames // shifts, 1)
        slope, intercept = np.polyfit(lags, msd, 1, w=np.sqrt(independent))
        return float(slope) / (2 * DIMENSIONS), float(intercept)

    def block_uncertainty(self, max_lag_time: float) -> dict:
        """An honest standard error, from tracers that really are independent.

        **Why the fit's own error bar is not usable here.** The weighted least
        squares treats the MSD points as independent observations, and they are
        not: every lag is computed from the same trajectories, so the points are
        strongly correlated along the curve. Measured over 32 seeds of this
        configuration, the actual spread of the estimate was about 36 times the
        error the fit quoted, and the intercept's about 7 times. The estimate
        itself was unbiased -- the mean sat 0.06 per cent from the analytic
        value -- so what was wrong was only the error bar, in the direction
        that makes a run look better than it is.

        **What this returns was checked against what it replaces.** The
        across-seed scatter is the quantity a standard error is supposed to
        predict, and measuring it costs a run per seed, so it is the right
        validation and the wrong routine method. Over those 32 seeds the block
        estimate lands at 1.11x the across-seed scatter, inside the 13 per cent
        uncertainty 32 seeds put on the scatter itself. The fit's own error is
        35.5x out over the same runs.

        **Why blocks of tracers are the right replacement.** This configuration
        is non-interacting, so the tracers are independent by construction, not
        by assumption. Splitting them into blocks and refitting each gives a
        scatter of genuinely independent estimates of the same quantity, and
        the standard error of their mean is what the whole-ensemble fit should
        have reported. It needs no second run: the ensemble is already there,
        which is what makes this evaluable on runs that have already happened.

        The alternative -- running more seeds -- measures the same thing and
        costs a run each time. That is the right check on this method and the
        wrong way to use it routinely, so it is what this was validated
        against rather than what it does.
        """
        n_particles = self.n_particles
        blocks = min(self.UNCERTAINTY_BLOCKS, n_particles)
        if blocks < 2:
            return {
                "method": "tracer_blocks",
                "blocks": blocks,
                "standard_error": None,
                "reason": "fewer than two tracer blocks; a scatter needs at least two estimates",
            }
        # Contiguous blocks, not a random partition: the tracers are
        # exchangeable here, so a shuffle would add a second seed to a number
        # whose whole point is to be reproducible from the saved record.
        edges = np.array_split(np.arange(n_particles), blocks)
        fits = [self.fit_over(max_lag_time, idx) for idx in edges]
        fits = [f for f in fits if f is not None]
        if len(fits) < 2:
            return {
                "method": "tracer_blocks",
                "blocks": len(fits),
                "standard_error": None,
                "intercept_standard_error": None,
                "reason": "the window left fewer than two blocks with a fittable curve",
            }
        ds = np.asarray([f[0] for f in fits])
        bs = np.asarray([f[1] for f in fits])
        # Scatter of the block estimates, divided down to the mean of all of
        # them. The fit is linear in the MSD values and the blocks are equal
        # in size, so the whole-ensemble estimate IS the mean of the blocks --
        # which is what makes this the standard error of the reported number
        # and not of something adjacent to it.
        se = float(ds.std(ddof=1) / np.sqrt(len(ds)))
        b_se = float(bs.std(ddof=1) / np.sqrt(len(bs)))
        return {
            "method": "tracer_blocks",
            "blocks": len(ds),
            "tracers_per_block": int(n_particles // blocks),
            "standard_error": se,
            "block_scatter": float(ds.std(ddof=1)),
            "relative_standard_error": float(se / ds.mean()) if ds.mean() else None,
            "intercept_standard_error": b_se,
            "intercept_in_sigma": float(bs.mean() / b_se) if b_se else None,
            "note": (
                "tracers are non-interacting here, so the blocks are independent by "
                "construction rather than by assumption. These are the error bars to "
                "compare a criterion against; the fit's own are optimistic because it "
                "treats correlated MSD points as independent observations. The intercept "
                "is carried because it is the free-regime diagnostic, and an honest error "
                "on the slope says nothing about it"
            ),
        }

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
                    f"the record holds {self.n_frames} frames, which is fewer than two lags "
                    "inside the window; the run stopped before the estimator could be applied"
                ),
                "frames_saved": self.n_frames,
                "lags_used": len(curve),
            }
        lags = np.asarray([c[0] for c in curve])
        msd = np.asarray([c[1] for c in curve])
        shifts = np.arange(1, len(curve) + 1)
        n_frames = self.n_frames
        n_particles = self.n_particles

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
        # Measured over 32 seeds of this configuration, comparing the actual
        # spread of the estimate against what the fit quotes:
        #
        #     diffusivity   true scatter / quoted SE   ~36x
        #     intercept     true scatter / quoted SE    ~7x
        #
        # These figures were first written here as ~41x and ~8x, from eight
        # seeds. Eight puts about 27 per cent uncertainty on the scatter it is
        # measuring, and the first draw came in high; 32 puts it at 13 per cent
        # and gives 35.5x and 7.0x. The conclusion did not move -- both are
        # orders of magnitude, and P15 calls anything under 10x a tie -- but an
        # error bar is the wrong thing to quote off a sample too small to pin
        # it, which is the mistake this whole comment is about.
        #
        # The estimator itself is sound -- across those seeds the mean sits
        # -0.06 per cent from the analytic Stokes-Einstein value, and the mean
        # intercept is 0.15 sigma from zero against the true scatter. What is
        # wrong is only the error bar, and it is wrong in the dangerous
        # direction.
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
