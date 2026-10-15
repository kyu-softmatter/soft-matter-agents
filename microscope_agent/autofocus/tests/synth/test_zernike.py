"""Zernike polynomials: normalisation, orthogonality, index conventions."""
from __future__ import annotations

import numpy as np
import pytest

from dino_autofocus.synth.optics import zernike as Z


def test_rms_normalisation():
    """Each term has unit mean square over the unit disc, so a coefficient in
    waves is waves RMS of wavefront error."""
    rho, theta, mask = Z.unit_grid(256)
    for j in (0, 1, 3, 4, 5, 8, 12, 24):
        zj = Z.zernike(j, rho, theta)[mask]
        assert np.sqrt((zj ** 2).mean()) == pytest.approx(1.0, abs=5e-3)


def test_orthogonality():
    rho, theta, mask = Z.unit_grid(256)
    b = np.stack([Z.zernike(j, rho, theta)[mask] for j in range(15)])
    gram = (b @ b.T) / mask.sum()
    assert np.abs(gram - np.eye(15)).max() < 0.02


def test_ansi_roundtrip():
    assert all(Z.nm_to_ansi(*Z.ansi_to_nm(j)) == j for j in range(45))


def test_noll_table():
    """Against Noll (1976); the sign convention is the part that is easy to
    get wrong, so every term of the first six orders is checked."""
    expect = {1: (0, 0), 2: (1, 1), 3: (1, -1), 4: (2, 0), 5: (2, -2), 6: (2, 2),
              7: (3, -1), 8: (3, 1), 9: (3, -3), 10: (3, 3), 11: (4, 0),
              12: (4, 2), 13: (4, -2), 14: (4, 4), 15: (4, -4), 16: (5, 1),
              17: (5, -1), 18: (5, 3), 19: (5, -3), 20: (5, 5), 21: (5, -5),
              22: (6, 0)}
    for j, nm in expect.items():
        assert Z.noll_to_nm(j) == nm
    assert all(Z.nm_to_noll(*Z.noll_to_nm(j)) == j for j in range(1, 40))


def test_named_aberrations_are_the_expected_terms():
    assert Z.NAMED["defocus"] == 4
    assert Z.NAMED["spherical"] == 12
    assert Z.ansi_to_nm(Z.NAMED["astig_vertical"]) == (2, 2)
    assert Z.ansi_to_nm(Z.NAMED["coma_x"]) == (3, 1)


def test_rms_excludes_piston_tilt_defocus():
    """Piston, tilt and defocus are not wavefront *errors* -- refocusing and
    re-centring remove them -- so they must not count towards the RMS."""
    assert Z.rms({"defocus": 1.0, "tilt_x": 1.0, "piston": 1.0}) == pytest.approx(0.0)
    assert Z.rms({"spherical": 0.1}) == pytest.approx(0.1)


def test_strehl_marechal():
    assert Z.strehl({}) == pytest.approx(1.0)
    rms = 0.05
    assert Z.strehl({"spherical": rms}) == pytest.approx(
        np.exp(-(2 * np.pi * rms) ** 2), rel=1e-9)


def test_random_named_scales_with_the_scale_argument(rng):
    a = [Z.rms(Z.random_named(rng, scale=1.0)) for _ in range(60)]
    b = [Z.rms(Z.random_named(rng, scale=3.0)) for _ in range(60)]
    assert np.median(b) > 2.0 * np.median(a)
    assert Z.rms(Z.random_named(rng, scale=0.0)) == pytest.approx(0.0)
