"""Zernike polynomials on the unit pupil, with RMS-unit normalisation.

Indexing follows the ANSI Z80.28 / OSA single-index convention:

    j = (n(n + 2) + m) / 2

so j = 0 is piston, 1/2 tilt, 3/5 astigmatism, 4 defocus, 12 primary
spherical.  Coefficients are amplitudes in *waves RMS*: a wavefront built from
`coeffs` has RMS optical path error `norm(coeffs)` waves, which makes it easy to
reason about Marechal's criterion (diffraction limited below ~0.07 waves RMS).
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from scipy.special import binom


# ---------------------------------------------------------------------------
# index bookkeeping
# ---------------------------------------------------------------------------

def ansi_to_nm(j: int) -> Tuple[int, int]:
    """ANSI single index -> (radial order n, azimuthal frequency m)."""
    if j < 0:
        raise ValueError("ANSI index must be non-negative")
    n = 0
    while (n + 1) * (n + 2) // 2 <= j:
        n += 1
    m = 2 * (j - n * (n + 1) // 2) - n
    return n, m


def nm_to_ansi(n: int, m: int) -> int:
    if (n - abs(m)) % 2 != 0 or abs(m) > n:
        raise ValueError(f"invalid Zernike order (n={n}, m={m})")
    return (n * (n + 2) + m) // 2


def _noll_order(n: int) -> List[Tuple[int, int]]:
    """(n, m) pairs of radial order `n` in Noll order.

    Within an order the terms ascend in |m|, and the sign is fixed by the Noll
    parity rule: cosine terms (m > 0) take even j, sine terms (m < 0) take odd j.
    """
    first = n * (n + 1) // 2 + 1          # Noll index of the first term of order n
    pairs: List[Tuple[int, int]] = []
    for m_abs in range(n % 2, n + 1, 2):
        if m_abs == 0:
            pairs.append((n, 0))
            continue
        j_even_first = (first + len(pairs)) % 2 == 0
        pairs.append((n, m_abs if j_even_first else -m_abs))
        pairs.append((n, -m_abs if j_even_first else m_abs))
    return pairs


def noll_to_nm(j: int) -> Tuple[int, int]:
    """Noll index (1-based, as used in most optics papers) -> (n, m)."""
    if j < 1:
        raise ValueError("Noll index is 1-based")
    n = 0
    while (n + 1) * (n + 2) // 2 < j:
        n += 1
    return _noll_order(n)[j - n * (n + 1) // 2 - 1]


def nm_to_noll(n: int, m: int) -> int:
    """Inverse of :func:`noll_to_nm`."""
    try:
        return n * (n + 1) // 2 + 1 + _noll_order(n).index((n, m))
    except ValueError:
        raise ValueError(f"invalid Zernike order (n={n}, m={m})") from None


# ---------------------------------------------------------------------------
# polynomials
# ---------------------------------------------------------------------------

def radial(n: int, m: int, rho: np.ndarray) -> np.ndarray:
    """Radial Zernike polynomial R_n^{|m|}(rho), unnormalised."""
    m = abs(m)
    if (n - m) % 2:
        return np.zeros_like(rho)
    out = np.zeros_like(rho, dtype=np.float64)
    for k in range((n - m) // 2 + 1):
        c = (-1) ** k * binom(n - k, k) * binom(n - 2 * k, (n - m) // 2 - k)
        out += c * rho ** (n - 2 * k)
    return out


def zernike(j: int, rho: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """RMS-normalised Zernike term j over the unit disc.

    The normalisation is such that the mean square of the term over the unit
    disc is 1, so a coefficient in waves equals waves RMS of wavefront error.
    """
    n, m = ansi_to_nm(j)
    r = radial(n, m, rho)
    norm = np.sqrt(n + 1.0) if m == 0 else np.sqrt(2.0 * (n + 1.0))
    if m > 0:
        return norm * r * np.cos(m * theta)
    if m < 0:
        return norm * r * np.sin(-m * theta)
    return norm * r


def basis(
    n_terms: int,
    rho: np.ndarray,
    theta: np.ndarray,
    mask: np.ndarray | None = None,
) -> np.ndarray:
    """Stack of the first `n_terms` Zernike terms, shape (n_terms, *rho.shape)."""
    out = np.empty((n_terms,) + rho.shape, dtype=np.float64)
    for j in range(n_terms):
        out[j] = zernike(j, rho, theta)
    if mask is not None:
        out *= mask
    return out


def wavefront(
    coeffs: Sequence[float] | Dict[str, float],
    rho: np.ndarray,
    theta: np.ndarray,
    mask: np.ndarray | None = None,
) -> np.ndarray:
    """Wavefront in waves from ANSI coefficients or a dict of named aberrations."""
    if isinstance(coeffs, dict):
        coeffs = coeffs_from_named(coeffs)
    coeffs = np.asarray(coeffs, dtype=np.float64)
    w = np.zeros_like(rho, dtype=np.float64)
    for j, c in enumerate(coeffs):
        if c != 0.0:
            w += c * zernike(j, rho, theta)
    if mask is not None:
        w *= mask
    return w


# ---------------------------------------------------------------------------
# named aberrations -- the handful that actually matter on a microscope
# ---------------------------------------------------------------------------

NAMED: Dict[str, int] = {
    "piston": 0,
    "tilt_y": 1,
    "tilt_x": 2,
    "astig_oblique": 3,     # 45 deg astigmatism
    "defocus": 4,
    "astig_vertical": 5,    # 0/90 deg astigmatism
    "trefoil_y": 6,
    "coma_y": 7,
    "coma_x": 8,
    "trefoil_x": 9,
    "tetrafoil_y": 10,
    "astig2_oblique": 11,
    "spherical": 12,        # primary spherical
    "astig2_vertical": 13,
    "tetrafoil_x": 14,
    "spherical2": 24,       # secondary spherical
}

#: Aberrations worth randomising during training, with sane 1-sigma amplitudes
#: in waves RMS for a decently aligned but not perfect microscope.
RANDOMISATION_SIGMA: Dict[str, float] = {
    "astig_oblique": 0.035,
    "astig_vertical": 0.035,
    "coma_x": 0.030,
    "coma_y": 0.030,
    "trefoil_x": 0.020,
    "trefoil_y": 0.020,
    "spherical": 0.045,
    "tetrafoil_x": 0.012,
    "tetrafoil_y": 0.012,
    "astig2_oblique": 0.010,
    "astig2_vertical": 0.010,
    "spherical2": 0.012,
}


def coeffs_from_named(named: Dict[str, float], n_terms: int | None = None) -> np.ndarray:
    """Dict of aberration names -> dense ANSI coefficient vector (waves RMS)."""
    idx = {}
    for key, val in named.items():
        if key in NAMED:
            idx[NAMED[key]] = idx.get(NAMED[key], 0.0) + float(val)
        elif key.startswith("z") and key[1:].isdigit():
            j = int(key[1:])
            idx[j] = idx.get(j, 0.0) + float(val)
        else:
            raise KeyError(f"unknown aberration name {key!r}")
    size = (max(idx) + 1) if idx else 1
    if n_terms is not None:
        size = max(size, n_terms)
    out = np.zeros(size, dtype=np.float64)
    for j, v in idx.items():
        out[j] = v
    return out


def random_named(
    rng: np.random.Generator,
    scale: float = 1.0,
    sigma: Dict[str, float] | None = None,
    include: Iterable[str] | None = None,
) -> Dict[str, float]:
    """Draw a plausible aberration state for domain randomisation.

    `scale` multiplies every sigma, so scale=0 gives a perfect system and
    scale=2 a badly misaligned one.  Coefficients are drawn from a Student-t
    (nu=4) so that occasional large aberrations appear -- those are the cases
    where a naive sharpness-metric autofocus fails.
    """
    sigma = dict(RANDOMISATION_SIGMA if sigma is None else sigma)
    if include is not None:
        keep = set(include)
        sigma = {k: v for k, v in sigma.items() if k in keep}
    out: Dict[str, float] = {}
    for key, s in sigma.items():
        t = rng.standard_t(df=4) / np.sqrt(4 / (4 - 2))  # unit variance
        out[key] = float(scale * s * t)
    return out


def rms(coeffs: Sequence[float] | Dict[str, float]) -> float:
    """Wavefront RMS in waves, excluding piston/tilt/defocus (not real errors)."""
    if isinstance(coeffs, dict):
        coeffs = coeffs_from_named(coeffs)
    c = np.asarray(coeffs, dtype=np.float64).copy()
    for j in (0, 1, 2, 4):
        if j < c.size:
            c[j] = 0.0
    return float(np.sqrt(np.sum(c ** 2)))


def strehl(coeffs: Sequence[float] | Dict[str, float]) -> float:
    """Marechal approximation to the Strehl ratio (valid for RMS < ~0.15 waves)."""
    return float(np.exp(-((2 * np.pi * rms(coeffs)) ** 2)))


def unit_grid(size: int, radius_px: float | None = None):
    """Convenience (rho, theta, mask) on a square grid covering the unit pupil."""
    r = (size - 1) / 2.0 if radius_px is None else radius_px
    y, x = np.mgrid[0:size, 0:size].astype(np.float64)
    cy = cx = (size - 1) / 2.0
    xx = (x - cx) / r
    yy = (y - cy) / r
    rho = np.hypot(xx, yy)
    theta = np.arctan2(yy, xx)
    return rho, theta, rho <= 1.0
