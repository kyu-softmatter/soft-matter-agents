"""Focus helpers for scan_4x and focus_100x: block scores, end-aware parabola, double peak."""

import numpy as np
import pytest

from dino_autofocus.bench_values import DOUBLE_PEAK_PROMINENCE as P
from dino_autofocus.focus import classical as C


def gauss(z, centre, width=4.0, height=10.0):
    return height * np.exp(-((np.asarray(z) - centre) ** 2) / (2 * width**2))


def test_block_scores_grid_and_order():
    rng = np.random.default_rng(0)
    img = np.full((120, 120), 100, np.uint16)
    img[:20, 100:] = rng.integers(0, 4000, (20, 20))  # texture only in block (0, 5)
    s = C.block_scores(img, 6)
    assert len(s) == 36
    assert int(np.argmax(np.abs(s))) == 5  # row-major: row 0, column 5
    assert C.block_scores(img, n=2)[1] == pytest.approx(C.vollath4(img[:60, 60:]))


def test_block_scores_ignores_remainder_and_rejects_small():
    img = np.random.default_rng(1).integers(0, 4000, (125, 127)).astype(np.uint16)
    assert C.block_scores(img, 6)[0] == pytest.approx(C.vollath4(img[:20, :21]))
    with pytest.raises(ValueError):
        C.block_scores(np.zeros((10, 10), np.uint16), 6)
    with pytest.raises(ValueError):
        C.block_scores(np.zeros((3, 60, 60), np.uint16), 6)


def test_parabola_peak_none_at_either_end():
    z = np.arange(2950.0, 3011.0, 5.0)
    assert C.parabola_peak(z, gauss(z, 2982.0)) == pytest.approx(2982.0, abs=0.5)
    assert C.parabola_peak(z, gauss(z, 3030.0)) is None  # still rising at the top
    assert C.parabola_peak(z, gauss(z, 2900.0)) is None  # falling from the bottom
    assert C.parabola_peak(z[::-1], gauss(z, 2982.0)[::-1]) == pytest.approx(2982.0, abs=0.5)


def test_parabola_peak_matches_vertex_inside():
    z = [3000.0, 3002.0, 3004.0, 3006.0]
    s = [1.0, 3.0, 2.5, 0.5]
    assert C.parabola_peak(z, s) == C.parabola_vertex(z, s)


def test_single_peak_is_not_double():
    z = np.arange(2955.0, 3016.0, 2.0)
    rng = np.random.default_rng(2)
    s = gauss(z, 2988.0) + rng.normal(0, 0.05, z.size)  # small noise in the tails
    assert C.separated_peaks(z, s, P) == [pytest.approx(2988.0, abs=2.0)]
    assert not C.double_peak(z, s, P)


def test_monotonic_and_flat_curves():
    z = np.arange(10.0)
    assert C.separated_peaks(z, z, P) == [9.0]  # rising to the top end: one peak, at the end
    assert not C.double_peak(z, z, P)
    assert C.separated_peaks(z, np.ones(10), P) == []
    assert C.separated_peaks([1.0, 2.0], [1.0, 2.0], P) == []


def test_oil_false_rise_at_the_top_end_is_double():
    # focus100x -202226 on 2026-09-30: peak at 2982 and a false rise towards 3005
    z = np.arange(2965.0, 3006.0, 1.0)
    s = gauss(z, 2982.0) + gauss(z, 3010.0, width=5.0, height=6.0)
    peaks = C.separated_peaks(z, s, P)
    assert len(peaks) == 2 and peaks[0] == pytest.approx(2982.0, abs=1.0)
    assert peaks[1] == 3005.0
    assert C.double_peak(z, s, P) and C.OIL_WARNING == "check immersion oil"


def test_two_interior_peaks_and_threshold():
    z = np.arange(0.0, 60.0, 1.0)
    s = gauss(z, 15.0) + gauss(z, 45.0, height=4.0)
    assert C.double_peak(z, s, P)
    assert not C.double_peak(z, s, prominence=0.5)  # the smaller one is ~0.4 of the span
