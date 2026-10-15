"""Integrated radial features: encircled energy and spectral ratios.

Three cues live here, all of them integrals.  That is the point: differentiating
an image (the gradient and Laplacian focus metrics, and the LSF) amplifies
noise, so those metrics degrade exactly where autofocus is hardest -- on dim,
sparse frames.  Integrating does the opposite.

``encircled_energy``
    ``E(r) = int_0^r I(rho) 2 pi rho drho`` around a detected object, normalised
    by the total.  This is the classical radial energy distribution used to
    specify lens quality, and it covers the regime the edge-profile method
    cannot: a sub-diffraction bead has no resolvable boundary, so its image *is*
    the PSF, and the encircled energy measures that PSF directly.  Edge profiles
    and encircled energy are therefore complementary rather than competing --
    one needs objects much larger than the PSF, the other much smaller.

``cumulative_edge_profile``
    ``P(r) = int_0^r I(r') dr'`` across a boundary: the running integral of the
    edge spread function.  One more integration than the LSF, hence markedly
    quieter, and that is the measured payoff: on a thin sheet at 20x/0.75 the
    descriptors computed from a noisy camera frame matched the noiseless render
    to within 2% (``leak_total`` 0.4153 vs 0.4180 in focus, 0.9285 vs 0.9227 at
    3 DoF), where a gradient metric on the same frames is noise-dominated.

    Which descriptor to use, measured over 0 to 6 DoF on that sheet:

    * ``fill_deficit`` -- light *missing* from the bright side -- is monotone
      across the whole range (0.065, 0.066, 0.131, 0.179, 0.287, 0.472).  Use
      this one.
    * ``leak_total`` -- light gained on the dark side -- rises to 3 DoF (0.418,
      0.504, 0.800, 0.923) and then turns over (0.859, 0.749), because past
      that the boundary is too blurred for the contour finder and the profile is
      no longer centred on the same edge.  Useful near focus, misleading far
      from it.
    * A half-radius of ``P`` normalised by its endpoint -- the obvious thing to
      reach for -- does not work at all: normalising turns ``P`` into a shape
      measure of an already-normalised ramp and the half-radius barely moves
      (1.25, 1.25, 1.18, 1.11 um, not even monotone).  Hence ``P`` is returned
      in physical units, unnormalised.

``spectral_ratio``
    An image's power spectrum is ``|O(f)|^2 |OTF(f)|^2``: the sample's own
    spectrum multiplies the optics', so a single frame's spectrum is not a
    property of the optics.  The *ratio* of two frames' spectra cancels
    ``|O(f)|^2`` exactly, leaving ``|OTF_1|^2 / |OTF_2|^2``.  That makes it the
    natural partner to a two-plane acquisition, and unlike the edge methods it
    needs no resolvable boundary at all -- only that the sample does not move
    between the frames.

None of these break the sign degeneracy on their own.  For an unaberrated,
index-matched system every one of them is symmetric about focus, so they give
magnitude only.  Two planes, or a genuinely asymmetric pupil, are what supply
the sign.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage


# ---------------------------------------------------------------------------
# encircled energy
# ---------------------------------------------------------------------------

@dataclass
class EncircledEnergy:
    valid: bool
    radii: np.ndarray = field(default_factory=lambda: np.zeros(0))   # um
    energy: np.ndarray = field(default_factory=lambda: np.zeros(0))  # normalised, 0..1
    profile: np.ndarray = field(default_factory=lambda: np.zeros(0)) # radial mean intensity
    n_objects: int = 0
    reason: str = ""
    descriptors: Dict[str, float] = field(default_factory=dict)


def find_spots(img: np.ndarray, min_distance: int = 5, threshold_sigma: float = 5.0,
               max_spots: int = 60, exclude_central: bool = False,
               central_fraction: float = 0.12) -> np.ndarray:
    """Local maxima well above the background, as (row, col) integer positions.

    ``exclude_central`` drops detections near the frame centre.  That is worth
    having because the brightest, most central object is the one most likely to
    be saturated, and a clipped peak makes its radial profile meaningless while
    still dominating any average.
    """
    a = np.asarray(img, dtype=np.float64)
    bg = float(np.median(a))
    mad = float(np.median(np.abs(a - bg)))
    sigma = 1.4826 * mad if mad > 0 else float(a.std())
    if sigma <= 0:
        return np.zeros((0, 2), dtype=int)
    thresh = bg + threshold_sigma * sigma

    smooth = ndimage.gaussian_filter(a, 1.0)
    footprint = np.ones((2 * min_distance + 1,) * 2, dtype=bool)
    peaks = (smooth == ndimage.maximum_filter(smooth, footprint=footprint)) & (a > thresh)
    rows, cols = np.nonzero(peaks)
    if rows.size == 0:
        return np.zeros((0, 2), dtype=int)

    if exclude_central:
        h, w = a.shape
        cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
        rn = np.hypot((rows - cy) / max(cy, 1), (cols - cx) / max(cx, 1))
        keep = rn > central_fraction
        rows, cols = rows[keep], cols[keep]
        if rows.size == 0:
            return np.zeros((0, 2), dtype=int)

    order = np.argsort(a[rows, cols])[::-1][:max_spots]
    return np.column_stack([rows[order], cols[order]])


def encircled_energy(
    img: np.ndarray,
    pixel_size: float,
    max_radius: float = 3.0,
    n_radii: int = 48,
    spots: Optional[np.ndarray] = None,
    exclude_central: bool = True,
    min_objects: int = 1,
    **spot_kw,
) -> EncircledEnergy:
    """Radially integrated energy around detected objects, averaged over them.

    Parameters
    ----------
    max_radius
        Outer radius in um.  Should comfortably exceed the defocused blur;
        anything the aperture sends outside it is simply not counted, which
        biases ``E`` upwards at large defocus.
    """
    a = np.asarray(img, dtype=np.float64)
    bg = float(np.median(a))
    if spots is None:
        spots = find_spots(a, exclude_central=exclude_central, **spot_kw)
    if len(spots) < min_objects:
        return EncircledEnergy(False, n_objects=len(spots),
                               reason=f"found {len(spots)} objects, need {min_objects}")

    radii = np.linspace(0.0, max_radius, n_radii)
    r_px = radii / pixel_size
    half = int(np.ceil(r_px[-1])) + 1
    h, w = a.shape
    yy, xx = np.mgrid[-half:half + 1, -half:half + 1].astype(np.float64)
    rad = np.hypot(yy, xx)

    profiles: List[np.ndarray] = []
    for (ry, rx) in spots:
        if ry - half < 0 or ry + half >= h or rx - half < 0 or rx + half >= w:
            continue                    # a clipped stamp would bias the integral
        patch = a[ry - half:ry + half + 1, rx - half:rx + half + 1] - bg
        prof = np.empty(n_radii)
        for k, rr in enumerate(r_px):
            prof[k] = patch[rad <= max(rr, 0.5)].sum()
        profiles.append(prof)

    if not profiles:
        return EncircledEnergy(False, n_objects=len(spots),
                               reason="every detected object was too close to an edge")

    cum = np.mean(profiles, axis=0)
    total = float(cum[-1])
    if total <= 0:
        return EncircledEnergy(False, n_objects=len(profiles), reason="non-positive total energy")
    e = cum / total
    prof = np.gradient(cum, radii)
    with np.errstate(divide="ignore", invalid="ignore"):
        prof = np.where(radii > 0, prof / (2 * np.pi * np.maximum(radii, 1e-9)), prof[1] if prof.size > 1 else 0.0)

    return EncircledEnergy(True, radii=radii, energy=e, profile=np.nan_to_num(prof),
                           n_objects=len(profiles),
                           descriptors=_ee_descriptors(radii, e))


def _ee_descriptors(radii: np.ndarray, e: np.ndarray) -> Dict[str, float]:
    d: Dict[str, float] = {}
    for frac in (0.5, 0.8, 0.9):
        idx = np.where(e >= frac)[0]
        if idx.size and idx[0] > 0:
            i = idx[0]
            y0, y1 = e[i - 1], e[i]
            t = (frac - y0) / max(y1 - y0, 1e-12)
            d[f"r{int(frac * 100)}"] = float(radii[i - 1] + t * (radii[i] - radii[i - 1]))
        else:
            d[f"r{int(frac * 100)}"] = float(radii[-1])
    # energy inside a few fixed radii: the directly usable defocus signal
    for frac in (0.1, 0.2, 0.35):
        k = int(frac * (len(radii) - 1))
        d[f"e_at_{frac:g}R"] = float(e[k])
    d["r80_over_r50"] = float(d["r80"] / max(d["r50"], 1e-9))
    return d


# ---------------------------------------------------------------------------
# cumulative edge profile
# ---------------------------------------------------------------------------

def cumulative_edge_profile(offsets: np.ndarray, esf: np.ndarray
                            ) -> Tuple[np.ndarray, Dict[str, float]]:
    """``P(r) = int_0^r ESF(r') dr'``, integrated outward from the dark side.

    ``esf`` is expected already scaled so its plateaus sit at 0 (dark) and 1
    (bright), as :func:`dino_autofocus.synth.features.edge.extract` returns it, and ``P`` is
    left in physical units (um) rather than normalised -- see the module
    docstring for why normalising by the endpoint destroys the signal.

    The descriptors split into two kinds.  ``leak_*`` integrate the dark side,
    where light that defocus has pushed past the boundary accumulates, and grow
    with defocus.  ``fill_*`` integrate the bright side, where the same effect
    removes light, and shrink.  Their ratio is brightness-independent without
    needing any normalisation of ``P`` itself.
    """
    offsets = np.asarray(offsets, dtype=np.float64)
    esf = np.asarray(esf, dtype=np.float64)
    trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    n = esf.size
    d_off = float(offsets[1] - offsets[0]) if n > 1 else 1.0

    p = np.cumsum(esf) * d_off
    p = p - p[0]

    mid = n // 2
    desc: Dict[str, float] = {}
    # dark-side leakage at a few fractions of the half-width
    for frac in (0.25, 0.5, 0.75):
        k = int(round(frac * mid))
        desc[f"leak_{frac:g}"] = float(p[k])
    desc["leak_total"] = float(p[mid])
    # bright-side deficit: how much of the ideal step is missing
    ideal = float(offsets[-1] - offsets[mid])
    desc["fill_total"] = float(p[-1] - p[mid])
    desc["fill_deficit"] = float(ideal - desc["fill_total"])
    desc["leak_fill_ratio"] = float(desc["leak_total"] / max(desc["fill_total"], 1e-9))
    desc["p_area"] = float(trapz(p, offsets))
    if n >= 5:
        desc["p_curvature"] = float(
            (p[min(mid + 2, n - 1)] - 2 * p[mid] + p[max(mid - 2, 0)]) / (2 * d_off) ** 2)
    return p, desc


# ---------------------------------------------------------------------------
# spectral ratio
# ---------------------------------------------------------------------------

def radial_power(img: np.ndarray, pixel_size: float,
                 n_bins: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
    """Radially averaged power spectrum.  Returns (frequency in cyc/um, power)."""
    a = np.asarray(img, dtype=np.float64)
    a = a - a.mean()
    a = a * np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    P = np.abs(np.fft.fftshift(np.fft.fft2(a))) ** 2
    ny, nx = P.shape
    y, x = np.mgrid[0:ny, 0:nx]
    r = np.hypot(y - ny / 2, x - nx / 2)
    nb = n_bins or int(min(ny, nx) // 2)
    idx = np.clip((r * nb / (min(ny, nx) / 2)).astype(int), 0, nb - 1)
    power = np.bincount(idx.ravel(), weights=P.ravel(), minlength=nb)
    count = np.bincount(idx.ravel(), minlength=nb)
    f_nyq = 1.0 / (2.0 * pixel_size)
    freq = np.linspace(0.0, f_nyq, nb, endpoint=False)
    return freq, power / np.maximum(count, 1)


def spectral_ratio(img_a: np.ndarray, img_b: np.ndarray, pixel_size: float,
                   n_bins: Optional[int] = None,
                   floor: float = 1e-12) -> Tuple[np.ndarray, np.ndarray]:
    """``|OTF_a|^2 / |OTF_b|^2`` from two frames of the same, unmoved sample.

    The sample's own spectrum cancels, so this is a property of the optics only.
    It requires the sample to be identical in both frames -- any drift, motion
    or bleaching between them leaks straight into the ratio.
    """
    f, pa = radial_power(img_a, pixel_size, n_bins)
    _, pb = radial_power(img_b, pixel_size, n_bins)
    return f, pa / np.maximum(pb, floor)


def spectral_ratio_descriptors(freq: np.ndarray, ratio: np.ndarray,
                               bands: Sequence[Tuple[float, float]] = (
                                   (0.05, 0.2), (0.2, 0.4), (0.4, 0.7))) -> Dict[str, float]:
    """Band-averaged log ratios.

    The log is signed and roughly antisymmetric in the two frames' defocus, so
    for a two-plane acquisition its sign tells which of the pair is closer to
    focus -- the sign information a single frame cannot supply.
    """
    f_max = float(freq[-1]) if freq.size else 1.0
    out: Dict[str, float] = {}
    for lo, hi in bands:
        m = (freq >= lo * f_max) & (freq <= hi * f_max)
        out[f"log_ratio_{lo:g}_{hi:g}"] = (
            float(np.mean(np.log(np.maximum(ratio[m], 1e-12)))) if m.any() else 0.0)
    return out
