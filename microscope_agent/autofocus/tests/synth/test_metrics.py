"""Focus metrics: scale invariance, peak location, and the documented failures."""
from __future__ import annotations

import numpy as np
import pytest

from dino_autofocus.synth.sim import metrics as M


@pytest.mark.parametrize("name", sorted(M.METRICS))
def test_scale_invariance(name, rng):
    """Without normalisation 'brighter' reads as 'sharper', and the metric peak
    drifts with exposure instead of with focus."""
    img = rng.random((64, 64)) + 0.2
    base = M.focus_score(img, name)
    if abs(base) < 1e-12:
        pytest.skip("metric is degenerate on white noise")
    assert M.focus_score(3.7 * img, name) / base == pytest.approx(1.0, rel=1e-6)


def test_argmax_parabolic_is_exact_on_a_parabola():
    x = np.array([-1.0, 0.0, 1.0])
    y = -(x - 0.3) ** 2 + 5.0
    assert M.argmax_parabolic(x, y) == pytest.approx(0.3, abs=1e-9)


def test_argmax_parabolic_clamps_to_the_bracket():
    x = np.array([0.0, 1.0, 2.0])
    y = np.array([0.0, 1.0, 5.0])          # peak is outside
    assert 0.0 <= M.argmax_parabolic(x, y) <= 2.0


def test_reliable_metrics_peak_at_focus():
    """The regression test that matters.  `dct_entropy` once had an inverted
    sign and peaked at the edge of every scan: blur concentrates DCT energy at
    low frequency, so spectral entropy *falls* with blur and sharper means
    higher entropy.  A test at this level catches that immediately."""
    from dino_autofocus.synth.optics.psf import PSFEngine
    from dino_autofocus.synth.optics.system import preset
    from dino_autofocus.synth.sim import geometry as G
    from dino_autofocus.synth.sim.render import FocalShift, Renderer

    s = preset("20x_air")
    eng = PSFEngine(s, fov_px=64, pad=2, workers=1, cache_size=24)
    rend = Renderer(eng, focal_shift=FocalShift(eng, depth_max=4.0))
    rng = np.random.default_rng(0)
    em = G.build("thin_sheet", rng, extent=(9.0, 9.0), thickness=0.3, density=200.0)
    em = em.translate([0.0, 0.0, 1.0 - float(em.z.min())])
    dof = s.depth_of_field
    # Centre the scan on where focus actually is.  The sample sits 1 um above the
    # coverglass and the stack is index-mismatched, so best focus is ~0.7 um from
    # the nominal plane, not at zero -- scanning around zero measures the focal
    # shift, not the metrics.
    best, _ = rend.best_stage(em)
    stage = best + np.linspace(-5 * dof, 5 * dof, 21)
    stack = rend.render_stack(em, stage)

    for name in M.RELIABLE:
        curve = M.focus_curve(stack, name)
        offset = (M.argmax_parabolic(stage, curve) - best) / dof
        assert abs(offset) < 0.6, f"{name} peaked {offset:+.2f} DoF from the label"


def test_caveats_cover_every_unreliable_metric():
    """Anything not in RELIABLE must carry a documented reason, so a failure
    mode is recorded rather than rediscovered."""
    unreliable = set(M.METRICS) - set(M.RELIABLE)
    assert unreliable <= set(M.CAVEATS)
    assert all(M.CAVEATS[k] for k in unreliable)
