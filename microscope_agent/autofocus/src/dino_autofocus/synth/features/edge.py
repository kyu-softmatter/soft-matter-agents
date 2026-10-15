"""Edge spread function features -- a geometry-invariant focus cue.

The idea is the slanted-edge MTF measurement from ISO 12233, repurposed as a
focus sensor.  Across any sufficiently large, high-contrast boundary the
observed intensity profile is the true boundary profile convolved with the
system's line spread function.  Its derivative is the LSF and the modulus of
its transform is the MTF, so the profile measures the *optics*, not the sample.

Why that is worth the trouble
-----------------------------
The dominant risk in training an autofocus network on synthetic images is that
it learns the statistics of the synthetic *sample*, not the behaviour of the
optics, and then fails on real data.  An edge profile removes that axis: a
sphere, a rod and a cell boundary all produce the same ESF once the underlying
boundary shape is accounted for.  Averaging along the boundary also buys
sqrt(n_points) in SNR, which matters more than anything else on dim frames.

Where it genuinely does not work
--------------------------------
* Objects smaller than the PSF (sub-diffraction beads).  There is no edge --
  the image *is* the PSF.  ``extract`` reports ``valid=False``.
* Filament networks and fine textures.  No extended boundary to average along.
* Curved boundaries of known radius still carry a projection term: a uniformly
  labelled sphere has a column density going as sqrt(R^2 - r^2), not a step, so
  the measured ESF is that profile convolved with the LSF.  The local radius of
  curvature is therefore returned alongside the profile so a model can condition
  on it instead of confusing it with blur.

Sign of defocus
---------------
The profile is *not* symmetrised.  An aberrated system produces different
overshoot on either side of focus, and that asymmetry is the only single-frame
information about the sign of the defocus.  Symmetrising the profile -- the
obvious "cleanup" -- destroys exactly the feature worth having.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage


# ---------------------------------------------------------------------------
# result container
# ---------------------------------------------------------------------------

@dataclass
class EdgeProfile:
    """Averaged edge spread function and the descriptors derived from it."""

    valid: bool
    offsets: np.ndarray = field(default_factory=lambda: np.zeros(0))   # um from the edge
    esf: np.ndarray = field(default_factory=lambda: np.zeros(0))       # averaged, normalised
    esf_std: np.ndarray = field(default_factory=lambda: np.zeros(0))   # spread across edge points
    lsf: np.ndarray = field(default_factory=lambda: np.zeros(0))
    mtf: np.ndarray = field(default_factory=lambda: np.zeros(0))
    mtf_freq: np.ndarray = field(default_factory=lambda: np.zeros(0))  # cycles/um
    n_points: int = 0
    curvature: float = float("nan")          # mean signed curvature, 1/um
    reason: str = ""
    descriptors: Dict[str, float] = field(default_factory=dict)

    def feature_vector(self) -> np.ndarray:
        """ESF and LSF stacked into a fixed-length vector for a 1-D model."""
        return np.concatenate([self.esf, self.lsf])


# ---------------------------------------------------------------------------
# contour finding
# ---------------------------------------------------------------------------

def _normalise(img: np.ndarray) -> Tuple[np.ndarray, float, float]:
    a = np.asarray(img, dtype=np.float64)
    bg = float(np.median(a))
    hi = float(np.percentile(a, 99.5))
    scale = max(hi - bg, 1e-12)
    return (a - bg) / scale, bg, scale


def find_edges(
    img: np.ndarray,
    level: float = 0.5,
    smooth_px: float = 1.0,
    min_length: int = 24,
    max_contours: int = 40,
) -> List[np.ndarray]:
    """Sub-pixel boundary contours at a fixed fraction of the object amplitude.

    A half-amplitude level set is used rather than a gradient ridge because the
    level set moves much less with defocus: blurring a step leaves the 50% point
    in place, while the gradient maximum wanders once the PSF is asymmetric.
    """
    from skimage import measure

    norm, _, _ = _normalise(img)
    if smooth_px > 0:
        norm = ndimage.gaussian_filter(norm, smooth_px)
    if float(norm.max()) < 2.0 * level:
        return []
    contours = measure.find_contours(norm, level=level)
    contours = [c for c in contours if len(c) >= min_length]
    contours.sort(key=len, reverse=True)
    return contours[:max_contours]


def _contour_normals(c: np.ndarray, smooth: float = 2.0) -> Tuple[np.ndarray, np.ndarray]:
    """Unit normals and signed curvature along a contour (rows, cols order)."""
    closed = np.allclose(c[0], c[-1], atol=1e-6)
    mode = "wrap" if closed else "nearest"
    cy = ndimage.gaussian_filter1d(c[:, 0], smooth, mode=mode)
    cx = ndimage.gaussian_filter1d(c[:, 1], smooth, mode=mode)
    dy = np.gradient(cy); dx = np.gradient(cx)
    d2y = np.gradient(dy); d2x = np.gradient(dx)
    speed = np.hypot(dx, dy)
    speed = np.maximum(speed, 1e-9)
    # normal = tangent rotated by 90 deg
    ny, nx = dx / speed, -dy / speed
    kappa = (dx * d2y - dy * d2x) / speed ** 3
    return np.column_stack([ny, nx]), kappa


# ---------------------------------------------------------------------------
# profile extraction
# ---------------------------------------------------------------------------

def extract(
    img: np.ndarray,
    pixel_size: float,
    half_width: float = 1.6,
    n_samples: int = 65,
    level: float = 0.5,
    smooth_px: float = 1.0,
    min_points: int = 40,
    subsample: int = 1,
    min_contrast: float = 0.15,
    max_curvature_um: float = 4.0,
) -> EdgeProfile:
    """Extract an averaged edge spread function from one image.

    Parameters
    ----------
    pixel_size
        Sample-plane pixel size, um.  Profiles are returned on a physical axis
        so that frames from different objectives are directly comparable.
    half_width
        Half-length of each normal profile, um.
    n_samples
        Samples per profile; the returned feature length is ``2 * n_samples``.
    max_curvature_um
        Edge points whose radius of curvature is below this are discarded: a
        boundary that curves on the scale of the profile mixes curvature into
        the blur estimate.
    """
    norm, bg, scale = _normalise(img)
    contours = find_edges(img, level=level, smooth_px=smooth_px)
    if not contours:
        return EdgeProfile(False, reason="no boundary at the requested level")

    offsets = np.linspace(-half_width, half_width, n_samples)
    off_px = offsets / pixel_size

    profiles: List[np.ndarray] = []
    curvatures: List[float] = []
    h, w = norm.shape
    for c in contours:
        normals, kappa = _contour_normals(c)
        sel = slice(None, None, max(int(subsample), 1))
        pts, nrm, kap = c[sel], normals[sel], kappa[sel]
        if len(pts) == 0:
            continue
        # sample positions: (n_points, n_samples, 2)
        rows = pts[:, 0][:, None] + nrm[:, 0][:, None] * off_px[None, :]
        cols = pts[:, 1][:, None] + nrm[:, 1][:, None] * off_px[None, :]
        inside = (rows >= 0) & (rows <= h - 1) & (cols >= 0) & (cols <= w - 1)
        keep = inside.all(axis=1)
        # np.where would evaluate 1/kappa on the straight-edge points too
        abs_kap = np.abs(kap)
        radius = np.full(abs_kap.shape, np.inf)
        curved = abs_kap > 1e-9
        radius[curved] = pixel_size / abs_kap[curved]
        keep &= radius >= max_curvature_um
        if not keep.any():
            continue
        vals = ndimage.map_coordinates(
            norm, [rows[keep].ravel(), cols[keep].ravel()], order=1, mode="nearest"
        ).reshape(int(keep.sum()), n_samples)

        # orient each profile so the bright side is at positive offsets
        flip = vals[:, : n_samples // 2].mean(axis=1) > vals[:, n_samples // 2 + 1:].mean(axis=1)
        vals[flip] = vals[flip][:, ::-1]
        contrast = vals[:, -5:].mean(axis=1) - vals[:, :5].mean(axis=1)
        good = contrast >= min_contrast
        if good.any():
            profiles.append(vals[good])
            curvatures.extend((kap[keep][good] / pixel_size).tolist())

    if not profiles:
        return EdgeProfile(False, reason="no edge point passed contrast/curvature screening")
    stack = np.concatenate(profiles)
    if len(stack) < min_points:
        return EdgeProfile(False, n_points=len(stack),
                           reason=f"only {len(stack)} usable edge points (need {min_points})")

    esf = stack.mean(axis=0)
    esf_std = stack.std(axis=0)

    # normalise to a 0 -> 1 transition using the plateaus, not the extrema,
    # so that ringing overshoot is preserved rather than clipped away
    lo = float(np.mean(esf[:max(n_samples // 10, 2)]))
    hi = float(np.mean(esf[-max(n_samples // 10, 2):]))
    amp = max(hi - lo, 1e-12)
    esf_n = (esf - lo) / amp
    esf_std_n = esf_std / amp

    d_off = offsets[1] - offsets[0]
    lsf = np.gradient(esf_n, d_off)
    area = float(np.trapezoid(lsf, offsets)) if hasattr(np, "trapezoid") else float(np.trapz(lsf, offsets))
    lsf_n = lsf / area if abs(area) > 1e-12 else lsf

    mtf = np.abs(np.fft.rfft(lsf_n * np.hanning(len(lsf_n))))
    mtf = mtf / max(mtf[0], 1e-30)
    freq = np.fft.rfftfreq(len(lsf_n), d=d_off)

    return EdgeProfile(
        valid=True, offsets=offsets, esf=esf_n, esf_std=esf_std_n,
        lsf=lsf_n, mtf=mtf, mtf_freq=freq, n_points=len(stack),
        curvature=float(np.mean(curvatures)) if curvatures else float("nan"),
        descriptors=descriptors(offsets, esf_n, lsf_n, mtf, freq),
    )


# ---------------------------------------------------------------------------
# scalar descriptors
# ---------------------------------------------------------------------------

def descriptors(offsets: np.ndarray, esf: np.ndarray, lsf: np.ndarray,
                mtf: np.ndarray, freq: np.ndarray) -> Dict[str, float]:
    """Interpretable scalars from an ESF: width, ringing, asymmetry, MTF cut-off.

    ``asymmetry`` and ``overshoot_ratio`` are the sign-bearing ones.  A blur
    that is symmetric about focus changes ``width_10_90`` identically either
    side of focus, so width alone can never give the sign.
    """
    d: Dict[str, float] = {}

    def crossing(frac: float) -> float:
        idx = np.where(esf >= frac)[0]
        if idx.size == 0 or idx[0] == 0:
            return float("nan")
        i = idx[0]
        y0, y1 = esf[i - 1], esf[i]
        if abs(y1 - y0) < 1e-12:
            return float(offsets[i])
        return float(offsets[i - 1] + (frac - y0) / (y1 - y0) * (offsets[i] - offsets[i - 1]))

    x10, x50, x90 = crossing(0.1), crossing(0.5), crossing(0.9)
    d["width_10_90"] = float(x90 - x10) if np.isfinite(x90) and np.isfinite(x10) else float("nan")
    d["edge_centre"] = x50

    peak = float(np.max(np.abs(lsf))) if lsf.size else float("nan")
    d["lsf_peak"] = peak
    if lsf.size and peak > 0:
        half = np.where(np.abs(lsf) >= peak / 2)[0]
        d["lsf_fwhm"] = float(offsets[half[-1]] - offsets[half[0]]) if half.size > 1 else float("nan")
        m = float(np.sum(lsf))
        if abs(m) > 1e-12:
            c = float(np.sum(lsf * offsets) / m)
            var = float(np.sum(lsf * (offsets - c) ** 2) / m)
            d["lsf_rms_width"] = float(np.sqrt(abs(var)))
            d["lsf_skew"] = float(np.sum(lsf * (offsets - c) ** 3) / m / (abs(var) ** 1.5 + 1e-30))
        else:
            d["lsf_rms_width"] = float("nan"); d["lsf_skew"] = float("nan")
    else:
        d["lsf_fwhm"] = d["lsf_rms_width"] = d["lsf_skew"] = float("nan")

    # ringing: how far the ESF goes outside [0, 1] on either side
    n = len(esf)
    d["overshoot_bright"] = float(np.max(esf[n // 2:]) - 1.0)
    d["overshoot_dark"] = float(-np.min(esf[: n // 2]))
    d["overshoot_ratio"] = float(
        (d["overshoot_bright"] - d["overshoot_dark"]) /
        (abs(d["overshoot_bright"]) + abs(d["overshoot_dark"]) + 1e-6))
    # asymmetry of the ESF about its own 50% point
    mid = n // 2
    left = esf[:mid][::-1]
    right = esf[mid + 1:]
    k = min(len(left), len(right))
    d["asymmetry"] = float(np.mean((right[:k] - 1.0) + left[:k])) if k else float("nan")

    if mtf.size > 2:
        for target in (0.5, 0.2, 0.1):
            below = np.where(mtf <= target)[0]
            d[f"mtf_f{int(target * 100)}"] = float(freq[below[0]]) if below.size else float(freq[-1])
        d["mtf_area"] = float(np.trapezoid(mtf, freq)) if hasattr(np, "trapezoid") else float(np.trapz(mtf, freq))
    return d


def extract_batch(images: Sequence[np.ndarray], pixel_size: float, **kw) -> List[EdgeProfile]:
    return [extract(im, pixel_size, **kw) for im in images]
