"""The `bleach_recovery_diffusivity` estimator, as registered (contracts/observables.json).

One implementation of the registered steps, applied to particle positions
from the engine. Read the entry whole before changing anything here: the
entry is the contract and this file is one reading of it.

**Why bleaching is applied here and not in the engine.** In `bd_overdamped`
the beads do not interact, so whether a bead is bright or dark changes
nothing about how it moves. Bleaching is a label on a trajectory, not a force
on it, so the engine's job ends at positions. This module labels them, the
way the light would, and then samples a camera. One engine run can therefore
be bleached and read out several ways, and none of those ways can disturb
the dynamics. That holds for this configuration only. With interactions,
or any configuration whose dynamics depend on the label, it stops being true.

The steps, in the entry's order:

1. **Geometry.** A uniform disc of radius `w_nominal`, bleached as a column.
   The signal is the depth-projected count, so only x and y enter. z is
   carried by the engine and dropped here.
2. **Bleach.** It lasts `bleach_duration`, and during it each bead inside
   the disc goes dark with probability `1 - exp(-k*dt)` per engine sample.
   t = 0 is the end of the bleach.
3. **Camera.** Frames are taken at `frame_interval`, each one the mean of
   the bright count over its exposure. Exposure equals the frame interval
   (an integrating camera), which is an assumption of this reading and
   is recorded where it is used.
4. **Normalisation.** Background B = 0 and the reference ratio = 1. Both are
   identities in the engine and are still applied, as the entry asks.
   The disc signal is divided by its mean over the pre-bleach frames.
5. **w.** The radius at half the bleach contrast of the azimuthally averaged
   profile in the first post-bleach frame. If it differs from the nominal
   radius by more than 2x, nothing is reported.
6. **Fit.** Soumpasis, with F0, Finf and tau free and w not fitted. The fit
   is unweighted least squares over every frame from the first post-bleach
   frame to `max_recovery_time`. D = w^2 / (4 tau).
7. **Validity**, tested on the fitted tau: bleach <= tau/10, frame
   interval <= tau/5, max_recovery_time >= 10 tau. A curve outside any of
   these yields a one-sided bound and no value.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import curve_fit
from scipy.special import i0e, i1e

BLEACH_MAX = 0.1     # bleach duration <= tau/10
FRAME_MAX = 0.2      # frame interval <= tau/5
WINDOW_MIN = 10.0    # max_recovery_time >= 10 tau
RADIUS_RATIO_MAX = 2.0


def soumpasis(t: np.ndarray, tau: float) -> np.ndarray:
    """exp(-2 tau/t) [I0(2 tau/t) + I1(2 tau/t)], 0 at t <= 0."""
    t = np.asarray(t, dtype=float)
    x = 2.0 * tau / np.maximum(t, 1e-300)
    return np.where(t > 0, i0e(x) + i1e(x), 0.0)


def fit(t: np.ndarray, F: np.ndarray, tau_guess: float) -> dict:
    """Step 6: unweighted least squares, F0, Finf, tau free."""
    model = lambda tt, tau, F0, Finf: F0 + (Finf - F0) * soumpasis(tt, tau)
    p0 = (tau_guess, float(F[0]), float(np.mean(F[-max(3, len(F) // 10):])))
    try:
        popt, _ = curve_fit(model, t, F, p0=p0, bounds=([1e-12, -1.0, -1.0], [np.inf, 2.0, 3.0]),
                            maxfev=20000)
    except RuntimeError as exc:
        return {"converged": False, "why": str(exc)}
    tau, F0, Finf = (float(x) for x in popt)
    resid = F - model(t, *popt)
    return {"converged": True, "tau": tau, "F0": F0, "Finf": Finf,
            "rms_residual": float(np.sqrt(np.mean(resid**2)))}


def half_contrast_radius(r: np.ndarray, bright_frac_profile: np.ndarray) -> float | None:
    """Step 5. `bright_frac_profile` is the first post-bleach frame's bright
    density divided by the pre-bleach density, azimuthally averaged in radial
    bins centred at `r`. Contrast = 1 - profile. The centre contrast is the
    mean over bins inside half the nominal radius, which the caller sets by
    choosing `r` in units of it.

    Returns None when the contrast never falls to half inside the bins,
    which happens when a curve has so few beads that the profile is noise."""
    c = 1.0 - bright_frac_profile
    centre = float(np.mean(c[r < 0.5])) if np.any(r < 0.5) else float(c[0])
    if centre <= 0:
        return None
    half = 0.5 * centre
    for i in range(1, len(r)):
        if r[i] >= 0.5 and c[i] <= half:
            c0, c1 = c[i - 1], c[i]
            if c0 == c1:
                return float(r[i])
            return float(r[i - 1] + (half - c0) * (r[i] - r[i - 1]) / (c1 - c0))
    return None


def estimate(frames_t: np.ndarray, F: np.ndarray, w_measured: float | None, w_nominal: float,
             bleach_duration: float, frame_interval: float, max_recovery_time: float) -> dict:
    """Steps 5-7 on one normalised curve. `frames_t` are frame mid-times
    measured from the end of the bleach, post-bleach frames only, already
    clipped to max_recovery_time. Lengths in the caller's unit (um), times
    in s; D comes back in um^2/s."""
    out = {"w_nominal": w_nominal, "w_measured": w_measured}
    if w_measured is None:
        out.update(reported=False, refusal="no half-contrast radius: the first post-bleach profile never "
                                          "falls to half its centre contrast")
        return out
    ratio = w_measured / w_nominal
    if ratio > RADIUS_RATIO_MAX or ratio < 1.0 / RADIUS_RATIO_MAX:
        out.update(reported=False, refusal=f"measured radius is {ratio:.2f} of the nominal: the column "
                                          "assumption has failed")
        return out
    f = fit(frames_t, F, tau_guess=w_nominal**2 / 4.0)
    out["fit"] = f
    if not f["converged"]:
        out.update(reported=False, refusal="fit did not converge")
        return out
    tau = f["tau"]
    D = w_measured**2 / (4.0 * tau)
    bounds = []
    if bleach_duration > BLEACH_MAX * tau:
        bounds.append("bleach longer than tau/10")
    if frame_interval > FRAME_MAX * tau:
        bounds.append("frame interval longer than tau/5")
    if max_recovery_time < WINDOW_MIN * tau:
        bounds.append("record shorter than 10 tau")
    out.update(tau=tau, D=D, mobile_fraction=f["Finf"])
    if bounds:
        # A curve outside a bound constrains D from one side only. A bleach
        # or frame too long for tau means the recovery was too fast to
        # resolve, so the curve says only that D exceeds the value read.
        # A record too short means it was too slow, so D is below the value.
        side = "upper" if "record shorter than 10 tau" in bounds else "lower"
        out.update(reported=False, refusal="; ".join(bounds), bound_side=side)
        return out
    out["reported"] = True
    return out


class Bleacher:
    """Steps 2-4, streamed. Feed it xy positions (N, 2) at every engine
    sample in time order; it keeps only counts, never the positions, so
    memory is independent of the run's length (task 023's lesson).

    Times are measured from the start of the record. The schedule:
    `n_pre` frames before the bleach, then the bleach of `bleach_duration`,
    then frames until `max_recovery_time` after its end. Every engine
    sample falls inside exactly one of those, so `sample_dt` must divide
    the frame interval and the bleach duration (checked)."""

    def __init__(self, *, w_nominal: float, box: float, k: float, bleach_duration: float,
                 frame_interval: float, max_recovery_time: float, n_pre: int, sample_dt: float,
                 rng: np.random.Generator, profile_bins: int = 40, profile_rmax: float = 3.0):
        self.w = w_nominal
        self.box = box
        self.k = k
        self.tb = bleach_duration
        self.fi = frame_interval
        self.T = max_recovery_time
        self.n_pre = n_pre
        self.dt = sample_dt
        self.rng = rng
        for name, span in (("frame interval", frame_interval), ("bleach duration", bleach_duration)):
            m = span / sample_dt
            if abs(m - round(m)) > 1e-6 or round(m) < 1:
                raise ValueError(f"the engine's sample interval {sample_dt} does not divide the {name} {span}")
        self.per_frame = int(round(frame_interval / sample_dt))
        self.per_bleach = int(round(bleach_duration / sample_dt))
        self.pre_samples = n_pre * self.per_frame
        self.post_frames = int(math.floor(max_recovery_time / frame_interval + 1e-9))
        self.total = self.pre_samples + self.per_bleach + self.post_frames * self.per_frame
        self.edges = np.linspace(0.0, profile_rmax, profile_bins + 1)
        self.r_mid = 0.5 * (self.edges[1:] + self.edges[:-1])
        self.i = 0
        self.dark = None
        self.acc = 0.0
        self.frames: list[float] = []
        self.first_profile = None
        self._prof_acc = None
        self._pre_profile_acc = np.zeros(profile_bins)
        self._pre_profile_n = 0

    @property
    def done(self) -> bool:
        return self.i >= self.total

    def _r(self, xy: np.ndarray) -> np.ndarray:
        # minimum image about the disc centre at the box origin
        d = xy - self.box * np.round(xy / self.box)
        return np.hypot(d[:, 0], d[:, 1]) / self.w

    def feed(self, xy: np.ndarray) -> None:
        if self.done:
            return
        if self.dark is None:
            self.dark = np.zeros(len(xy), dtype=bool)
        r = self._r(xy)
        inside = r < 1.0
        phase_bleach = self.pre_samples <= self.i < self.pre_samples + self.per_bleach
        if phase_bleach:
            p = 1.0 - math.exp(-self.k * self.dt)
            hit = inside & ~self.dark & (self.rng.random(len(xy)) < p)
            self.dark |= hit
        else:
            bright_in = float(np.count_nonzero(inside & ~self.dark))
            self.acc += bright_in
            before = self.i < self.pre_samples
            post_index = (self.i - self.pre_samples - self.per_bleach) // self.per_frame
            if before or post_index == 0:
                h, _ = np.histogram(r[~self.dark], bins=self.edges)
                if before:
                    self._pre_profile_acc += h
                    self._pre_profile_n += 1
                else:
                    self._prof_acc = h if self._prof_acc is None else self._prof_acc + h
            end_of_frame = ((self.i + 1) % self.per_frame == 0) if before else \
                ((self.i - self.pre_samples - self.per_bleach + 1) % self.per_frame == 0)
            if end_of_frame:
                self.frames.append(self.acc / self.per_frame)
                self.acc = 0.0
        self.i += 1

    def curve(self) -> dict:
        """Steps 4-5: the normalised post-bleach curve and the measured w."""
        frames = np.array(self.frames)
        pre, post = frames[: self.n_pre], frames[self.n_pre:]
        B, ref_ratio = 0.0, 1.0           # identities in the engine, applied anyway
        pre_mean = float(np.mean(pre - B))
        F = ((post - B) / pre_mean) / ref_ratio if pre_mean > 0 else np.full(len(post), np.nan)
        t = (np.arange(len(post)) + 0.5) * self.fi
        # The reference density is the pre-bleach mean over the whole profiled
        # area, not bin by bin: the suspension is uniform, and with tens of
        # beads a per-bin pre-bleach density is mostly zeros. The experiment
        # divides by a pre-bleach image under flat illumination, which is the
        # same reference. Bin areas in units of w^2 (pi omitted on both sides).
        area = self.edges[1:] ** 2 - self.edges[:-1] ** 2
        pre_density = float(np.sum(self._pre_profile_acc)) / max(self._pre_profile_n, 1) / float(np.sum(area))
        w_meas = None
        if self._prof_acc is not None and pre_density > 0:
            post_density = self._prof_acc / self.per_frame / area
            w_meas_units = half_contrast_radius(self.r_mid, post_density / pre_density)
            w_meas = None if w_meas_units is None else w_meas_units * self.w
        return {"t": t, "F": F, "w_measured": w_meas, "pre_mean_count": pre_mean,
                "dark_count": int(np.count_nonzero(self.dark))}
