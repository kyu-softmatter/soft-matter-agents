"""PSF forward model: energy conservation, resolution, focal shift, robustness."""
from __future__ import annotations

import numpy as np
import pytest

from dino_autofocus.synth.optics.psf import PSFEngine
from dino_autofocus.synth.optics.system import Objective, SampleStack, preset


def _fwhm(profile, dx):
    idx = np.where(profile >= profile.max() / 2)[0]
    return (idx[-1] - idx[0]) * dx


def test_parseval_normalisation(eng_20x):
    """An in-focus PSF integrates to 1 over an infinite plane, so on the padded
    grid it must be within a fraction of a percent of unity."""
    grid = eng_20x.psf_grid(0.0, 0.5)
    assert grid.sum() == pytest.approx(1.0, abs=2e-3)
    assert eng_20x.otf(0.0, 0.5)[0, 0].real == pytest.approx(grid.sum(), rel=1e-9)


def test_energy_conservation_through_focus(eng_20x):
    """Defocus is a pure pupil phase, so it cannot destroy energy; any loss is
    energy leaving the computed window."""
    sums = [eng_20x.psf_grid(z, 0.5).sum() for z in (0.0, 1.0, 3.0)]
    assert all(s == pytest.approx(1.0, abs=5e-3) for s in sums)


def test_lateral_resolution_matches_abbe(eng_20x, sys_20x):
    p = eng_20x.psf_fine(0.0, 0.5)
    c = p.shape[0] // 2
    fwhm = _fwhm(p[c], eng_20x.dx)
    theory = 0.51 * sys_20x.illumination.wavelength / sys_20x.objective.na
    assert fwhm == pytest.approx(theory, rel=0.25)


def test_otf_is_hermitian(eng_20x):
    o = eng_20x.otf(0.5, 0.5)
    n = o.shape[0]
    flip = (-np.arange(n)) % n
    assert np.allclose(o, np.conj(o[np.ix_(flip, flip)]), atol=1e-8)


def test_index_matched_focal_shift_is_minus_depth(eng_matched):
    """With n_sample == n_immersion the depth and defocus terms are the same
    function of pupil angle, so best focus sits at exactly -depth.  Matched
    indices remove the depth-induced *aberration*, not the focal shift -- the
    emitter has physically moved.  An earlier version of FocalShift returned
    zero here and mis-centred the label search by the whole sample depth."""
    assert eng_matched.best_focus(0.0) == pytest.approx(0.0, abs=0.02)
    assert eng_matched.best_focus(2.0) == pytest.approx(-2.0, abs=0.05)


def test_best_focus_shifts_with_depth_for_mismatched_index():
    """Oil objective into water: best focus moves away from the objective, by
    more than the paraxial n_i/n_s ratio because high-NA marginal rays dominate."""
    eng = PSFEngine(preset("60x_oil"), fov_px=48, pad=2, workers=1, cache_size=8)
    shifts = [eng.best_focus(d) for d in (1.0, 2.0)]
    assert all(s < 0 for s in shifts)
    ratio = abs(shifts[0]) / 1.0
    assert 1.1 < ratio < 1.8
    assert abs(shifts[1]) > abs(shifts[0])


def test_no_overflow_at_extreme_defocus(eng_20x):
    """The pupil phase must be evaluated only on its support: outside it,
    sin(theta_sample) is unbounded and exp() overflows."""
    with np.errstate(all="raise"):
        for z in (-40.0, 40.0):
            p = eng_20x.psf_grid(z, 0.5)
            assert np.isfinite(p).all()


def test_cache_is_bounded():
    eng = PSFEngine(preset("20x_air"), fov_px=32, pad=2, workers=1, cache_size=4)
    for z in np.linspace(-5, 5, 30):
        eng.psf_grid(float(z), 0.5)
    assert len(eng._cache) <= 4
    assert eng.cache_stats()["entries"] <= 4


def test_supercritical_rays_discarded_by_default():
    """With NA above the sample index the pupil extends past the critical angle;
    keeping those rays is a TIRF/SAF choice, not a widefield default."""
    eng = PSFEngine(preset("60x_oil"), fov_px=32, pad=2, workers=1)
    assert eng.effective_na == pytest.approx(min(1.4, eng.system.stack.n_sample))
    eng_saf = PSFEngine(preset("60x_oil"), fov_px=32, pad=2, workers=1, saf="decay")
    assert eng_saf.effective_na == pytest.approx(1.4)


def test_geometric_blur_uses_the_immersion_medium(eng_20x):
    """The defocus term multiplies n_immersion*cos(theta_i), so the immersion --
    not the sample -- sets the blur, and NA < n_immersion keeps it finite."""
    assert np.isfinite(eng_20x.tan_alpha)
    assert eng_20x.geometric_radius(2.0) == pytest.approx(2.0 * eng_20x.tan_alpha)
    assert eng_20x.geometric_radius(0.0) == 0.0


def test_objective_rejects_na_above_immersion():
    with pytest.raises(ValueError):
        Objective(na=1.6, magnification=60.0, n_immersion=1.518)


def test_alternative_models_run_and_conserve_energy(sys_matched):
    for model in ("scalar", "gaussian"):
        eng = PSFEngine(sys_matched, fov_px=32, pad=2, model=model, workers=1)
        p = eng.psf_grid(0.0, 0.5)
        assert np.isfinite(p).all() and p.sum() > 0.5


def test_gaussian_model_has_no_rings(sys_matched):
    """The Gaussian approximation is monotone in radius by construction; the
    vectorial model is not.  This is what the approximation costs."""
    dof = sys_matched.depth_of_field
    prof = {}
    for model in ("gaussian", "vectorial"):
        eng = PSFEngine(sys_matched, fov_px=64, pad=2, model=model, workers=1)
        p = eng.psf_fine(3.0 * dof, 0.5)
        c = p.shape[0] // 2
        prof[model] = p[c, c:]
    g = prof["gaussian"]
    assert np.all(np.diff(g[:len(g) // 2]) <= 1e-12)
    v = prof["vectorial"][: len(prof["vectorial"]) // 2]
    assert (np.diff(v) > 0).any()


def test_aberration_lowers_the_strehl_ratio(sys_matched):
    """Compared at each system's own best focus -- depth 0 for a matched stack,
    where the focal shift is zero."""
    a = PSFEngine(sys_matched, fov_px=48, pad=2, workers=1).psf_fine(0.0, 0.0)
    b = PSFEngine(sys_matched, fov_px=48, pad=2, workers=1,
                  aberration={"astig_vertical": 0.15}).psf_fine(0.0, 0.0)
    assert np.abs(a - b).max() / a.max() > 0.05
    assert b.max() < a.max()          # aberration lowers the Strehl ratio


def test_astigmatism_elongates_orthogonally_either_side_of_focus(sys_matched):
    """At best focus an astigmatic PSF is the circle of least confusion, so it
    is *symmetric* there; the two line foci sit either side and are orthogonal.
    That swap is what makes deliberate astigmatism a way to read the sign of
    defocus from a single frame, and it is the property worth testing -- not
    asymmetry at focus, which does not exist.
    """
    eng = PSFEngine(sys_matched, fov_px=64, pad=2, workers=1,
                    aberration={"astig_vertical": 0.25})
    dof = sys_matched.depth_of_field
    ratios = {}
    for sign in (-1.0, +1.0):
        p = eng.psf_fine(sign * 2.0 * dof, 0.0)
        c = p.shape[0] // 2
        ratios[sign] = _fwhm(p[c], eng.dx) / _fwhm(p[:, c], eng.dx)
    # elongated along x on one side and along y on the other
    assert ratios[-1.0] > 1.15
    assert ratios[+1.0] < 1.0 / 1.15
    # and symmetric in between
    p0 = eng.psf_fine(0.0, 0.0)
    c = p0.shape[0] // 2
    assert _fwhm(p0[c], eng.dx) == pytest.approx(_fwhm(p0[:, c], eng.dx), rel=0.12)
