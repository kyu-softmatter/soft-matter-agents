# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/src/focus_classical.py
# body-sha256: a1155a04c9f180ed8d257d081ff03b4e1a205d7d2d886010821e265778e9b127
"""Classical focus metrics for live frames and the sweep-curve tools built on them.

Pure numpy, no hardware. Inputs are mono camera frames (uint16). Every metric peaks at best
focus. Nothing camera- or tuning-specific is written here: the clip level (``ceiling``),
the peak metric's bin size (``bin_px``) and the block grid (``n``) are the caller's
required arguments, with no default in this file.

The metrics come from the scripts that ran on the bench on 2026-09-30 and keep their
formulas exactly, so values in old scan records stay comparable:

* ``vollath4`` and ``brenner`` -- the bench grab script (mm_grab). The frame is median-subtracted
  and divided by its mean absolute deviation, so a brighter exposure does not read as
  sharper. Vollath F4 (lag-1 minus lag-2 autocorrelation, both axes) cancels uncorrelated
  noise; Brenner (lag-2 squared differences) rises on dim, noisy frames.
* ``peak_brightness`` -- the 100x focus script's ``--metric peak``: brightest binned spot
  (``bin_px`` x ``bin_px``, the caller's) minus the binned median. For sparse particle
  fields at 100x, where a whole-frame sharpness barely moves.
* ``tenengrad`` -- Sobel gradient energy, one of the ``RELIABLE`` metrics of the vendored
  synthetic ``synth.sim.metrics`` module, here on the valid interior only and with the same
  normalisation as the two above.

``vollath4`` here sums both axes, while ``synth.sim.metrics.vollath4`` uses the x axis
only: both peak at the same plane, but their values differ.

Saturation: the metrics use the pixels as read and do **not** mask clipped pixels. A
clipped core flattens the gradient at the top of a particle, so a saturated frame
under-reads its own sharpness and can move the peak. Keep ``saturated_fraction`` next to
the score (``frame_stats`` does) and treat frames above the caller's ``max_saturated``
fraction as not readable; ``analyse_sweep`` drops them.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

# The clip level, the peak bin size, the block grid, the saturated-fraction limit, the
# dropout tolerance and the double-peak prominence are the caller's arguments
# (dino-autofocus keeps them in its bench_values module; soft-matter-agents in the plan).

Edge = Literal["interior", "top", "bottom"]


def ceiling_for_bits(bits: int) -> int:
    """Clip level of a camera read out at `bits` bits (``2**bits - 1``)."""
    # definition: a uint16 frame holds 1..16 bits, and 2**bits - 1 is the unsigned maximum
    if not 1 <= bits <= 16:
        raise ValueError(f"bit depth {bits} outside 1..16 for a uint16 frame")
    return (1 << bits) - 1


def saturated_fraction(img: np.ndarray, ceiling: int) -> float:
    """Fraction of pixels at or above the camera's clip level."""
    return float(np.mean(np.asarray(img) >= ceiling))


def _normalise(img: np.ndarray) -> np.ndarray:
    """Median-subtracted, divided by the mean absolute deviation (mm_grab.py, float32)."""
    a = np.asarray(img).astype(np.float32)
    a = a - np.median(a)
    a /= max(float(np.abs(a).mean()), 1e-6)  # numerical guard: no division by zero on a flat frame
    return a


def vollath4(img: np.ndarray) -> float:
    """Scale-invariant Vollath F4 over both axes (the bench grab script)."""
    a = _normalise(img)
    f = (a[:, :-1] * a[:, 1:]).mean() - (a[:, :-2] * a[:, 2:]).mean()
    g = (a[:-1] * a[1:]).mean() - (a[:-2] * a[2:]).mean()
    return float(f + g)


def brenner(img: np.ndarray) -> float:
    """Scale-invariant Brenner sharpness, lag 2 on both axes (the bench grab script)."""
    a = _normalise(img)
    return float(((a[:, 2:] - a[:, :-2]) ** 2).mean() + ((a[2:] - a[:-2]) ** 2).mean())


def tenengrad(img: np.ndarray) -> float:
    """Scale-invariant Sobel gradient energy on the valid interior (no border padding)."""
    a = _normalise(img)
    if a.shape[0] < 3 or a.shape[1] < 3:  # definition: the Sobel stencil is 3 x 3
        raise ValueError(f"tenengrad needs at least 3 x 3 pixels, got {a.shape}")
    # Sobel = [1, 2, 1] smoothing across the derivative axis, [-1, 0, 1] along it
    sy = a[:-2] + 2 * a[1:-1] + a[2:]
    gx = sy[:, 2:] - sy[:, :-2]
    sx = a[:, :-2] + 2 * a[:, 1:-1] + a[:, 2:]
    gy = sx[2:] - sx[:-2]
    return float((gx**2 + gy**2).mean())


def peak_brightness(img: np.ndarray, bin_px: int) -> float:
    """Brightest `bin_px` x `bin_px`-binned spot minus the binned median, in ADU. Binning
    first means one hot pixel cannot win.

    Not scale invariant on purpose: at 100x on a sparse field it tracks how much light the
    in-focus particle concentrates. A clipped particle caps at the ceiling, so check
    ``saturated_fraction`` (the 2026-09-30 100x runs saturated at 30-50 ms).
    """
    if int(bin_px) != bin_px or bin_px < 1:
        raise ValueError(f"bin_px {bin_px!r} must be a positive whole number")
    a = np.asarray(img)
    h, w = (a.shape[0] // bin_px) * bin_px, (a.shape[1] // bin_px) * bin_px
    if h == 0 or w == 0:
        raise ValueError(f"frame {a.shape} smaller than one {bin_px} x {bin_px} bin")
    b = a[:h, :w].reshape(h // bin_px, bin_px, w // bin_px, bin_px).mean(
        axis=(1, 3), dtype=np.float32)
    return float(b.max() - np.median(b))


METRICS: dict[str, Callable[[np.ndarray], float]] = {
    "vollath4": vollath4,
    "brenner": brenner,
    "tenengrad": tenengrad,
    "peak": peak_brightness,
}


def score(img: np.ndarray, metric: str = "vollath4", *, bin_px: int | None = None) -> float:
    """Focus score of `img` by name: one of ``METRICS``. The ``peak`` metric needs the
    caller's `bin_px`; the others take no parameter."""
    try:
        fn = METRICS[metric]
    except KeyError:
        raise KeyError(f"unknown metric {metric!r}; available: {sorted(METRICS)}") from None
    if fn is peak_brightness:
        if bin_px is None:
            raise ValueError("the peak metric needs bin_px, the caller's bin size")
        return peak_brightness(img, bin_px)
    return fn(img)


@dataclass
class FrameStats:
    """Per-frame numbers a sweep keeps next to its score (the scripts' ``diagnostics``)."""

    score: float
    metric: str
    mean: float
    median: float
    p999: float
    max: int
    saturated_fraction: float


def frame_stats(img: np.ndarray, metric: str = "vollath4", *, ceiling: int,
                bin_px: int | None = None) -> FrameStats:
    """Score `img` and record the brightness numbers the sweep checks need. `ceiling` is the
    camera's clip level for this readout (``ceiling_for_bits``), always the caller's."""
    a = np.asarray(img)
    return FrameStats(score=score(a, metric, bin_px=bin_px), metric=metric,
                      mean=float(a.mean()),
                      # definition: p999 is the 99.9th percentile; its threshold is the caller's
                      median=float(np.median(a)), p999=float(np.percentile(a, 99.9)),
                      max=int(a.max()), saturated_fraction=saturated_fraction(a, ceiling))


# -- sweep curves ---------------------------------------------------------------------------

def dropout_mask(means: Sequence[float], tolerance: float) -> np.ndarray:
    """True for frames whose mean is within `tolerance` of the sweep's median mean.

    The others are light dropouts (the 2026-09-30 4x scan script) and must not pick the peak.
    """
    m = np.asarray(means, dtype=np.float64)
    if m.size == 0:
        return np.zeros(0, dtype=bool)
    med = float(np.median(m))
    return np.abs(m - med) <= tolerance * abs(med)


def _sorted_curve(z: Sequence[float], s: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    zz, ss = np.asarray(z, dtype=np.float64), np.asarray(s, dtype=np.float64)
    if zz.ndim != 1 or zz.shape != ss.shape or zz.size == 0:
        raise ValueError(f"z and score must be non-empty 1-D and the same length "
                         f"({zz.shape} vs {ss.shape})")
    o = np.argsort(zz, kind="stable")
    return zz[o], ss[o]


def parabola_vertex(z: Sequence[float], s: Sequence[float]) -> float:
    """Sub-step peak: the vertex of the parabola through the argmax and its neighbours.

    Same formula as ``synth.sim.metrics.argmax_parabolic`` (used by the synthetic
    evaluation script), after sorting by z. At either end of the span it returns
    that end's z: the curve says nothing about how far beyond the span the peak is (see
    ``peak_edge``). The vertex is clipped to the two neighbours.
    """
    zz, ss = _sorted_curve(z, s)
    j = int(np.argmax(ss))
    if j == 0 or j == len(zz) - 1:
        return float(zz[j])
    x0, x1, x2 = zz[j - 1:j + 2]
    y0, y1, y2 = ss[j - 1:j + 2]
    den = (x0 - x1) * (x0 - x2) * (x1 - x2)
    if abs(den) < 1e-30:  # numerical guard: two of the three z coincide
        return float(x1)
    a = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / den
    b = (x2**2 * (y0 - y1) + x1**2 * (y2 - y0) + x0**2 * (y1 - y2)) / den
    if abs(a) < 1e-30:  # numerical guard: collinear points, no curvature
        return float(x1)
    return float(np.clip(-b / (2 * a), x0, x2))


def peak_edge(z: Sequence[float], s: Sequence[float]) -> Edge:
    """Where the score maximum sits in the span: ``"top"`` (highest z), ``"bottom"`` or
    ``"interior"``. A span of one or two frames has no interior."""
    zz, ss = _sorted_curve(z, s)
    j = int(np.argmax(ss))
    if j == len(zz) - 1:
        return "top"
    if j == 0:
        return "bottom"
    return "interior"


@dataclass
class SweepAnalysis:
    """What the classical curve says, before it is turned into a verdict.

    Indices refer to the frames in the order passed in. ``z_um`` must be the encoder
    readback of each frame, not the commanded z.
    """

    z_um: list[float]
    scores: list[float]
    kept: list[bool]                 # False: light dropout or saturated
    dropped_z_um: list[float]        # light dropouts
    saturated_z_um: list[float]
    edge: Edge | None                # None when no frame is kept
    argmax_index: int | None         # best kept frame, original index
    z_vertex_um: float | None        # parabola vertex: computed, not any frame's z
    nearest_index: int | None        # kept frame closest to the vertex
    prominence: float | None         # (max - higher end) / |max| over kept frames
    notes: list[str] = field(default_factory=list)

    @property
    def n_kept(self) -> int:
        return sum(self.kept)


def analyse_sweep(z_um: Sequence[float], scores: Sequence[float],
                  means: Sequence[float] | None = None,
                  saturated: Sequence[float] | None = None, *,
                  dropout_tolerance: float, max_saturated: float) -> SweepAnalysis:
    """Drop light-dropout and saturated frames, then locate the peak of what is left.

    `means` (frame means) enables the dropout filter, `saturated` (clipped fractions) the
    saturation filter; both are per frame, in the order of `z_um`.
    """
    z = [float(v) for v in z_um]
    s = [float(v) for v in scores]
    n = len(z)
    if len(s) != n:
        raise ValueError(f"{n} z values but {len(s)} scores")
    keep = np.ones(n, dtype=bool)
    notes: list[str] = []
    if means is not None:
        if len(means) != n:
            raise ValueError(f"{n} z values but {len(means)} means")
        keep &= dropout_mask(means, dropout_tolerance)
    dropped = [z[i] for i in range(n) if not keep[i]]
    if dropped:
        notes.append(f"light dropout at z {dropped}")
    sat_z: list[float] = []
    if saturated is not None:
        if len(saturated) != n:
            raise ValueError(f"{n} z values but {len(saturated)} saturated fractions")
        sat = np.asarray(saturated, dtype=np.float64) > max_saturated
        sat_z = [z[i] for i in range(n) if sat[i] and keep[i]]
        keep &= ~sat
        if sat_z:
            notes.append(f"saturated (> {max_saturated:g} clipped) at z {sat_z}")
    out = SweepAnalysis(z_um=z, scores=s, kept=keep.tolist(), dropped_z_um=dropped,
                        saturated_z_um=sat_z, edge=None, argmax_index=None, z_vertex_um=None,
                        nearest_index=None, prominence=None, notes=notes)
    idx = [i for i in range(n) if keep[i]]
    if not idx:
        return out
    kz = np.array([z[i] for i in idx])
    ks = np.array([s[i] for i in idx])
    out.edge = peak_edge(kz, ks)
    out.argmax_index = idx[int(np.argmax(ks))]
    out.z_vertex_um = parabola_vertex(kz, ks)
    out.nearest_index = idx[int(np.argmin(np.abs(kz - out.z_vertex_um)))]
    o = np.argsort(kz, kind="stable")
    smax, ends = float(ks.max()), max(float(ks[o][0]), float(ks[o][-1]))
    out.prominence = (smax - ends) / max(abs(smax), 1e-12)  # numerical guard: zero curve
    return out


# -- helpers for the scan_4x and focus_100x operations (T-031)

OIL_WARNING = "check immersion oil"


def block_scores(img: np.ndarray, n: int) -> list[float]:
    """``vollath4`` of each block of the caller's ``n`` x ``n`` grid, row-major (the 4x scan
    script; one focus z per block).
    Pixels beyond a whole number of blocks on the right and bottom are not used."""
    # definition: vollath4's lag-2 stencil needs at least 3 px a side in every block
    if img.ndim != 2 or n < 1 or img.shape[0] < 3 * n or img.shape[1] < 3 * n:
        raise ValueError(f"need a 2-D frame of at least {3 * n} px a side for {n} x {n} blocks,"
                         f" got {img.shape}")
    h, w = img.shape[0] // n, img.shape[1] // n
    return [vollath4(img[i * h:(i + 1) * h, j * w:(j + 1) * w])
            for i in range(n) for j in range(n)]


def parabola_peak(z: Sequence[float], s: Sequence[float]) -> float | None:
    """``parabola_vertex``, but None when the maximum sits at either end of the span
    (the 4x scan script's ``parabola_peak``): such a curve has no peak inside it."""
    return None if peak_edge(z, s) != "interior" else parabola_vertex(z, s)


def _local_maxima(x: np.ndarray) -> list[int]:
    """Indices of local maxima, ends excluded; a flat top counts once, at its middle
    (rounded down). Same rule as ``scipy.signal.find_peaks``, which the soft-matter-agents
    microscope environment does not have."""
    peaks, i, last = [], 1, len(x) - 1
    while i < last:
        if x[i - 1] < x[i]:
            ahead = i + 1
            while ahead < last and x[ahead] == x[i]:
                ahead += 1
            if x[ahead] < x[i]:
                peaks.append((i + ahead - 1) // 2)
                i = ahead
        i += 1
    return peaks


def _prominence(x: np.ndarray, peak: int) -> float:
    """Topographic prominence of ``x[peak]`` (``scipy.signal.peak_prominences``, no window):
    the height above the higher of the two lowest points reached before a higher sample
    or the end, on each side."""
    h = x[peak]
    i, left = peak, h
    while i >= 0 and x[i] <= h:
        left = min(left, x[i])
        i -= 1
    i, right = peak, h
    while i < len(x) and x[i] <= h:
        right = min(right, x[i])
        i += 1
    return float(h - max(left, right))


def separated_peaks(z: Sequence[float], s: Sequence[float], prominence: float) -> list[float]:
    """z of each separate local maximum, highest score first.

    A maximum counts when it rises at least ``prominence`` x (max - min) of the curve above
    the deepest dip that separates it from a higher maximum (topographic prominence). The
    ends of the span count too, so a rise at the top end beside a real peak is a second
    peak. A single peak, a monotonic curve or a flat curve gives one entry or none.
    """
    zz, ss = _sorted_curve(z, s)
    span = float(ss.max() - ss.min())
    if len(ss) < 3 or span <= 0 or not np.isfinite(span):
        return []
    padded = np.concatenate([[ss.min() - span], ss, [ss.min() - span]])
    idx = [i for i in _local_maxima(padded)
           if _prominence(padded, i) >= prominence * span]
    peaks = np.asarray(idx, dtype=np.intp) - 1
    order = np.argsort(-ss[peaks], kind="stable")
    return [float(zz[peaks[k]]) for k in order]


def double_peak(z: Sequence[float], s: Sequence[float], prominence: float) -> bool:
    """Two or more separate maxima on the curve: warn with ``OIL_WARNING`` (classical)."""
    return len(separated_peaks(z, s, prominence)) >= 2
