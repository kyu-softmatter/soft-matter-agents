"""Classical focus metrics -- the baseline the learned model has to beat.

Every metric here maps an image to a scalar that (ideally) peaks at best focus.
They are the standard z-scan autofocus toolbox, and they are also what defines
the ground-truth label for a rendered scene.

All metrics are normalised so that scaling an image by a constant does not
change the score.  Without that, "brighter" reads as "sharper": the in-focus
plane concentrates the same photons into fewer pixels, so an unnormalised
gradient metric partly measures exposure rather than sharpness, and the peak
drifts as soon as the illumination or the emitter count changes.

The families behave differently and fail differently, which is the point of
keeping several:

* **gradient** (``brenner``, ``tenengrad``, ``sq_gradient``) -- cheap, sharp
  peak, but very noise-sensitive: shot noise is high-frequency and reads as
  sharpness, so on dim frames these peak *away* from focus.
* **Laplacian** (``laplacian``) -- sharper still, correspondingly noisier.
* **variance** (``normalised_variance``) -- robust to noise, broad peak, so
  poor precision near focus.
* **spectral** (``hf_ratio``, ``dct_entropy``) -- explicitly band-limited, and
  the only family that can be made noise-aware by excluding the band where the
  noise floor dominates.
* **correlation** (``vollath4``, ``vollath5``) -- built for periodic/textured
  samples; nearly useless on sparse point-like ones.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

import numpy as np
from scipy import ndimage


def _prep(img: np.ndarray, background: Optional[float] = None) -> np.ndarray:
    a = np.asarray(img, dtype=np.float64)
    if background is None:
        background = float(np.median(a))
    a = a - background
    s = float(np.abs(a).mean())
    return a / s if s > 1e-12 else a


# ---------------------------------------------------------------------------
# gradient family
# ---------------------------------------------------------------------------

def brenner(img: np.ndarray, step: int = 2) -> float:
    """Sum of squared differences at a fixed lag -- Brenner (1976)."""
    a = _prep(img)
    dx = a[:, step:] - a[:, :-step]
    dy = a[step:, :] - a[:-step, :]
    return float((dx ** 2).sum() + (dy ** 2).sum()) / a.size


def tenengrad(img: np.ndarray) -> float:
    """Sobel gradient energy."""
    a = _prep(img)
    gx = ndimage.sobel(a, axis=1)
    gy = ndimage.sobel(a, axis=0)
    return float((gx ** 2 + gy ** 2).mean())


def sq_gradient(img: np.ndarray) -> float:
    a = _prep(img)
    gy, gx = np.gradient(a)
    return float((gx ** 2 + gy ** 2).mean())


def laplacian(img: np.ndarray) -> float:
    a = _prep(img)
    return float((ndimage.laplace(a) ** 2).mean())


# ---------------------------------------------------------------------------
# variance family
# ---------------------------------------------------------------------------

def normalised_variance(img: np.ndarray) -> float:
    """Variance divided by mean squared -- scale invariant."""
    a = np.asarray(img, dtype=np.float64)
    m = float(a.mean())
    return float(a.var() / (m ** 2)) if abs(m) > 1e-12 else 0.0


def peak_to_mean(img: np.ndarray) -> float:
    a = np.asarray(img, dtype=np.float64)
    m = float(a.mean())
    return float(np.percentile(a, 99.99) / m) if abs(m) > 1e-12 else 0.0


# ---------------------------------------------------------------------------
# spectral family
# ---------------------------------------------------------------------------

def _radial_power(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    a = _prep(img)
    a = a * np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    P = np.abs(np.fft.fftshift(np.fft.fft2(a))) ** 2
    ny, nx = P.shape
    y, x = np.mgrid[0:ny, 0:nx]
    r = np.hypot(y - ny / 2, x - nx / 2)
    nb = int(min(ny, nx) // 2)
    idx = np.clip(r.astype(int), 0, nb - 1)
    prof = np.bincount(idx.ravel(), weights=P.ravel(), minlength=nb)
    cnt = np.bincount(idx.ravel(), minlength=nb)
    return prof / np.maximum(cnt, 1), np.arange(nb) / nb


def hf_ratio(img: np.ndarray, low: float = 0.15, high: float = 0.7) -> float:
    """Fraction of spectral power in a mid/high band, relative to the total.

    ``high`` stops short of the Nyquist edge on purpose: the top of the band is
    where read and shot noise dominate, and including it turns the metric into a
    noise meter.
    """
    prof, f = _radial_power(img)
    band = (f >= low) & (f <= high)
    tot = float(prof.sum())
    return float(prof[band].sum() / tot) if tot > 1e-30 else 0.0


def dct_entropy(img: np.ndarray) -> float:
    """Shannon entropy of the normalised DCT coefficient distribution.

    An in-focus image has broad spectral content, so its DCT energy is spread
    over many coefficients and the entropy is *high*.  Blurring concentrates
    energy into the low-frequency corner and the entropy falls, so larger is
    sharper -- the same direction as every other metric here.

    Note this runs the opposite way to the "minimum entropy" focus criterion
    used for phase retrieval, which measures entropy of the *image*, not of its
    spectrum.  Shot noise also raises spectral entropy, so on dim frames this
    metric drifts towards the noisiest plane.
    """
    from scipy.fft import dctn
    a = _prep(img)
    c = np.abs(dctn(a, norm="ortho"))
    p = c / max(c.sum(), 1e-30)
    p = p[p > 0]
    return float(-np.sum(p * np.log(p)))


# ---------------------------------------------------------------------------
# correlation family
# ---------------------------------------------------------------------------

def vollath4(img: np.ndarray) -> float:
    a = _prep(img)
    return float((a[:, :-1] * a[:, 1:]).mean() - (a[:, :-2] * a[:, 2:]).mean())


def vollath5(img: np.ndarray) -> float:
    """Vollath F5: lag-1 autocorrelation minus the squared mean.

    Kept for completeness, but **do not use it as a focus metric here**.  Blur
    raises the lag-1 correlation while lowering the variance, and which effect
    wins depends on the sample.  Measured on this simulator at 20x/0.75, the
    peak lands at the edge of a +-6 DoF scan for an extended thin sheet (both
    with median- and exact-mean subtraction) and at +6 DoF for a spinodal
    texture with exact-mean subtraction, while behaving correctly (+0.01 DoF)
    on a compact sphere.  It is excluded from :data:`RELIABLE`.

    Vollath F4 (:func:`vollath4`) is the difference of two lags and does not
    have this failure mode.
    """
    a = _prep(img)
    return float((a[:, :-1] * a[:, 1:]).mean() - a.mean() ** 2)


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

METRICS: Dict[str, Callable[[np.ndarray], float]] = {
    "brenner": brenner,
    "tenengrad": tenengrad,
    "sq_gradient": sq_gradient,
    "laplacian": laplacian,
    "normalised_variance": normalised_variance,
    "peak_to_mean": peak_to_mean,
    "hf_ratio": hf_ratio,
    "dct_entropy": dct_entropy,
    "vollath4": vollath4,
    "vollath5": vollath5,
}

FAMILY: Dict[str, str] = {
    "brenner": "gradient", "tenengrad": "gradient", "sq_gradient": "gradient",
    "laplacian": "laplacian",
    "normalised_variance": "variance", "peak_to_mean": "variance",
    "hf_ratio": "spectral", "dct_entropy": "spectral",
    "vollath4": "correlation", "vollath5": "correlation",
}


#: Metrics that peaked within 0.1 DoF of the label on every geometry in
#: psf-autofocus ``scripts/demo_geometry.py``.  Use these for labelling and for baselines;
#: the others are kept so their failure modes can be demonstrated rather than
#: rediscovered.
RELIABLE: Tuple[str, ...] = (
    "brenner", "tenengrad", "sq_gradient", "laplacian",
    "normalised_variance", "dct_entropy", "vollath4",
)

#: Measured caveats, per metric.
CAVEATS: Dict[str, str] = {
    "hf_ratio": "peaked +0.7 DoF off on a spinodal texture; band limits are sample dependent",
    "laplacian": "peaked -0.36 DoF off on an axially oriented rod; most noise sensitive",
    "vollath5": "peaks at the scan edge on extended textures -- see the docstring",
    "peak_to_mean": "broad peak; poor precision near focus",
}


def focus_score(img: np.ndarray, metric: str = "brenner", **kw) -> float:
    try:
        fn = METRICS[metric]
    except KeyError:
        raise KeyError(f"unknown metric {metric!r}; available: {sorted(METRICS)}") from None
    return fn(img, **kw) if kw else fn(img)


def focus_curve(stack: np.ndarray, metric: str = "brenner", **kw) -> np.ndarray:
    """Focus score for every plane of a z-stack."""
    return np.array([focus_score(p, metric, **kw) for p in stack])


def argmax_parabolic(stage: np.ndarray, score: np.ndarray) -> float:
    """Sub-step focus estimate: parabola through the peak and its neighbours."""
    stage = np.asarray(stage, float); score = np.asarray(score, float)
    j = int(np.argmax(score))
    if j == 0 or j == len(stage) - 1:
        return float(stage[j])
    x0, x1, x2 = stage[j - 1], stage[j], stage[j + 1]
    y0, y1, y2 = score[j - 1], score[j], score[j + 1]
    den = (x0 - x1) * (x0 - x2) * (x1 - x2)
    if abs(den) < 1e-30:
        return float(x1)
    a = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / den
    b = (x2 ** 2 * (y0 - y1) + x1 ** 2 * (y2 - y0) + x0 ** 2 * (y1 - y2)) / den
    if abs(a) < 1e-30:
        return float(x1)
    peak = -b / (2 * a)
    lo, hi = min(x0, x2), max(x0, x2)
    return float(np.clip(peak, lo, hi))
