"""Classical metrics peak at focus; sweep tools drop dropouts and find the peak."""

import numpy as np
import pytest
from scipy import ndimage

from dino_autofocus.bench_values import (
    CEILING_12BIT,
    CEILING_16BIT,
    DROPOUT_TOLERANCE,
    MAX_SATURATED_FRACTION,
    PEAK_BIN_PX,
)
from dino_autofocus.focus import classical as C
from dino_autofocus.synth.sim import metrics as synth_metrics


def spot_frame(blur_px, size=128, seed=0, n_spots=12, amp=3000.0, bg=100.0, noise=True):
    """Gaussian spots blurred by `blur_px`, total photons conserved, plus Poisson noise."""
    rng = np.random.default_rng(seed)
    img = np.zeros((size, size))
    ys, xs = rng.integers(8, size - 8, (2, n_spots))
    img[ys, xs] = amp * 20
    img = ndimage.gaussian_filter(img, 1.0 + blur_px) + bg  # photons kept, peak falls
    if noise:
        img = np.random.default_rng(seed + 1).poisson(img).astype(np.float64)
    return np.clip(img, 0, 65535).astype(np.uint16)


def stack(n=11, focus=6, step_blur=0.8, **kw):
    return [spot_frame(step_blur * abs(k - focus), **kw) for k in range(n)]


@pytest.mark.parametrize("metric", sorted(C.METRICS))
def test_every_metric_peaks_at_focus(metric):
    frames = stack()
    s = [C.score(f, metric, bin_px=PEAK_BIN_PX) for f in frames]
    assert int(np.argmax(s)) == 6


def test_unknown_metric_names_the_choices():
    with pytest.raises(KeyError, match="vollath4"):
        C.score(np.zeros((8, 8), np.uint16), "nope")


# The bench grab script's two metrics, as the 9/30 runs used them: copied verbatim from
# scripts/mm_grab.py (last changed in 0a27658), which R-05 deleted; it is in git history.
def ref_vollath4(img: np.ndarray) -> float:
    a = img.astype(np.float32)
    a = a - np.median(a)
    a /= max(float(np.abs(a).mean()), 1e-6)
    f = (a[:, :-1] * a[:, 1:]).mean() - (a[:, :-2] * a[:, 2:]).mean()
    g = (a[:-1] * a[1:]).mean() - (a[:-2] * a[2:]).mean()
    return float(f + g)


def ref_brenner(img: np.ndarray) -> float:
    a = img.astype(np.float32)
    a = a - np.median(a)
    a /= max(float(np.abs(a).mean()), 1e-6)
    return float(((a[:, 2:] - a[:, :-2]) ** 2).mean() + ((a[2:] - a[:-2]) ** 2).mean())


def test_vollath4_and_brenner_match_the_bench_scripts_exactly():
    for f in stack(n=5, focus=2):
        assert C.vollath4(f) == ref_vollath4(f)
        assert C.brenner(f) == ref_brenner(f)


def test_tenengrad_agrees_with_synth_and_is_scale_invariant():
    frames = stack()
    ours = [C.tenengrad(f) for f in frames]
    theirs = [synth_metrics.tenengrad(f) for f in frames]
    assert np.argmax(ours) == np.argmax(theirs)
    f = frames[6].astype(np.float64)
    assert C.tenengrad(f * 3) == pytest.approx(C.tenengrad(f), rel=1e-5)


def test_tenengrad_rejects_tiny_frames():
    with pytest.raises(ValueError):
        C.tenengrad(np.zeros((2, 5), np.uint16))


def test_peak_brightness_ignores_a_single_hot_pixel():
    img = np.full((64, 64), 100, np.uint16)
    img[10, 10] = 1100  # hot pixel: +1000 ADU, but 1/16 of a 4 x 4 bin
    img[40:44, 40:44] = 400  # a real 4 x 4 spot at +300 ADU
    assert C.peak_brightness(img, PEAK_BIN_PX) == pytest.approx(300.0)
    with pytest.raises(ValueError):
        C.score(img, "peak")  # the bin size is the caller's, never a default


def test_ceilings_and_saturation():
    assert C.ceiling_for_bits(12) == CEILING_12BIT == 4095
    assert C.ceiling_for_bits(16) == CEILING_16BIT == 65535
    with pytest.raises(ValueError):
        C.ceiling_for_bits(17)
    img = np.full((10, 10), 1000, np.uint16)
    img[0, :5] = 4095
    assert C.saturated_fraction(img, 4095) == pytest.approx(0.05)
    assert C.saturated_fraction(img, 65535) == 0.0
    st = C.frame_stats(img, "brenner", ceiling=4095)
    assert st.metric == "brenner" and st.max == 4095
    assert st.saturated_fraction == pytest.approx(0.05) and st.median == 1000.0


RULES = {"dropout_tolerance": DROPOUT_TOLERANCE, "max_saturated": MAX_SATURATED_FRACTION}


def test_dropout_mask_drops_a_dim_frame():
    means = [1000, 1003, 998, 770, 1001]  # -23 %, as on 2026-09-30
    assert C.dropout_mask(means, DROPOUT_TOLERANCE).tolist() == [True, True, True, False, True]
    assert C.dropout_mask([], DROPOUT_TOLERANCE).size == 0


def test_parabola_vertex_is_exact_on_a_parabola_and_sorts_input():
    z = np.array([3040.0, 3042.0, 3044.0, 3046.0, 3048.0])
    s = -((z - 3044.7) ** 2)
    assert C.parabola_vertex(z, s) == pytest.approx(3044.7)
    o = [3, 0, 4, 1, 2]
    assert C.parabola_vertex(z[o], s[o]) == pytest.approx(3044.7)


def test_parabola_vertex_matches_synth_argmax_parabolic():
    rng = np.random.default_rng(3)
    for _ in range(50):
        z = np.sort(rng.uniform(0, 100, 9))
        s = rng.normal(size=9)
        assert C.parabola_vertex(z, s) == pytest.approx(synth_metrics.argmax_parabolic(z, s))


def test_parabola_vertex_at_an_end_returns_that_end():
    z = [1.0, 2.0, 3.0]
    assert C.parabola_vertex(z, [1, 2, 3]) == 3.0
    assert C.parabola_vertex(z, [3, 2, 1]) == 1.0
    with pytest.raises(ValueError):
        C.parabola_vertex([1.0, 2.0], [1.0])


def test_peak_edge():
    z = [10.0, 12.0, 14.0, 16.0]
    assert C.peak_edge(z, [1, 2, 3, 4]) == "top"
    assert C.peak_edge(z, [4, 3, 2, 1]) == "bottom"
    assert C.peak_edge(z, [1, 3, 2, 1]) == "interior"
    assert C.peak_edge(z[::-1], [1, 2, 3, 4]) == "bottom"  # z order, not list order


def test_analyse_sweep_removes_a_dropout_that_reads_sharpest():
    z = [3040.0 + 2 * k for k in range(7)]
    s = [1.0, 2.0, 3.0, 4.0, 3.0, 2.0, 1.0]
    means = [1000.0] * 7
    s[5], means[5] = 9.0, 770.0  # the dim frame reads sharpest
    a = C.analyse_sweep(z, s, means=means, **RULES)
    assert a.kept[5] is False and a.dropped_z_um == [3050.0]
    assert a.argmax_index == 3 and a.edge == "interior"
    assert a.nearest_index == 3 and a.z_vertex_um == pytest.approx(3046.0)
    assert any("dropout" in n for n in a.notes)


def test_analyse_sweep_drops_saturated_frames_and_handles_none_left():
    z = [1.0, 2.0, 3.0]
    a = C.analyse_sweep(z, [1, 5, 1], saturated=[0.0, 0.01, 0.0], **RULES)
    assert a.kept == [True, False, True] and a.saturated_z_um == [2.0]
    b = C.analyse_sweep(z, [1, 5, 1], saturated=[0.5, 0.5, 0.5], **RULES)
    assert b.n_kept == 0 and b.edge is None and b.argmax_index is None
    with pytest.raises(ValueError):
        C.analyse_sweep(z, [1, 2], **RULES)
