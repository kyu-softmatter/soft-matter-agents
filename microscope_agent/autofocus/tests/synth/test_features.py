"""Geometry-invariant focus features: ESF/MTF, cumulative profile, encircled
energy, spectral ratio."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from dino_autofocus.synth.features import edge as E
from dino_autofocus.synth.features import radial as RD
from dino_autofocus.synth.optics.psf import PSFEngine
from dino_autofocus.synth.optics.system import SampleStack, preset
from dino_autofocus.synth.sim import geometry as G
from dino_autofocus.synth.sim.render import FocalShift, Renderer


def _blurred_step(sigma_um, px=0.05, n=256):
    img = np.zeros((n, n))
    img[:, n // 2:] = 1.0
    return ndimage.gaussian_filter(img, sigma_um / px)


@pytest.mark.parametrize("sigma", [0.1, 0.2, 0.4])
def test_esf_width_matches_analytic_gaussian(sigma):
    """A step convolved with a Gaussian has a 10-90 width of 2*1.2816*sigma.
    This is the calibration that makes the extractor trustworthy at all."""
    prof = E.extract(_blurred_step(sigma), 0.05, half_width=3.0, n_samples=121)
    assert prof.valid
    assert prof.descriptors["width_10_90"] == pytest.approx(2 * 1.2816 * sigma, rel=0.12)


def test_lsf_fwhm_matches_analytic_gaussian():
    prof = E.extract(_blurred_step(0.3), 0.05, half_width=3.0, n_samples=161)
    assert prof.descriptors["lsf_fwhm"] == pytest.approx(2.3548 * 0.3, rel=0.15)


def test_esf_width_grows_monotonically_with_blur():
    widths = [E.extract(_blurred_step(s), 0.05, half_width=4.0,
                        n_samples=161).descriptors["width_10_90"]
              for s in (0.1, 0.2, 0.4, 0.8)]
    assert all(b > a for a, b in zip(widths, widths[1:]))


def test_curvature_screening_rejects_small_objects():
    """An object smaller than the profile has no usable edge: its boundary
    curves on the scale being measured, mixing curvature into the blur.  This is
    the documented limit of the method, so it must actually be enforced."""
    results = {}
    for radius in (1.0, 3.0, 10.0):
        yy, xx = np.mgrid[0:256, 0:256]
        d = np.hypot(yy - 128, xx - 128) * 0.1
        img = ndimage.gaussian_filter((d < radius).astype(float), 2.0)
        results[radius] = E.extract(img, 0.1, half_width=1.5, n_samples=61,
                                    max_curvature_um=4.0).valid
    assert results[1.0] is False
    assert results[3.0] and results[10.0]


def test_no_edge_reports_invalid_with_a_reason():
    prof = E.extract(np.zeros((64, 64)), 0.1)
    assert not prof.valid and prof.reason


def test_esf_is_not_symmetrised():
    """Overshoot either side of focus is the single-frame sign information;
    symmetrising the profile -- the obvious cleanup -- destroys it."""
    prof = E.extract(_blurred_step(0.2), 0.05, half_width=3.0, n_samples=121)
    assert "overshoot_bright" in prof.descriptors
    assert "overshoot_dark" in prof.descriptors
    assert "asymmetry" in prof.descriptors


def test_cumulative_profile_is_unnormalised_and_has_both_sides():
    prof = E.extract(_blurred_step(0.3), 0.05, half_width=3.0, n_samples=121)
    p, desc = RD.cumulative_edge_profile(prof.offsets, prof.esf)
    assert p[0] == pytest.approx(0.0)
    assert p[-1] > 1.0                      # micrometres, not a 0-1 ramp
    assert desc["leak_total"] > 0 and desc["fill_total"] > 0


def test_cumulative_fill_deficit_grows_with_blur():
    vals = []
    for sigma in (0.1, 0.3, 0.6, 1.0):
        prof = E.extract(_blurred_step(sigma), 0.05, half_width=4.0, n_samples=161)
        _, desc = RD.cumulative_edge_profile(prof.offsets, prof.esf)
        vals.append(desc["fill_deficit"])
    assert all(b > a for a, b in zip(vals, vals[1:]))


def test_encircled_energy_tightens_towards_focus():
    """Covers the regime the edge method cannot: objects smaller than the PSF,
    where the image *is* the PSF."""
    s = preset("20x_air")
    eng = PSFEngine(s, fov_px=96, pad=2, workers=1, cache_size=16)
    rend = Renderer(eng, focal_shift=FocalShift(eng, depth_max=4.0))
    rng = np.random.default_rng(1)
    em = G.build("point_emitters", rng, n=30, extent=(9.0, 9.0, 0.05))
    em = em.translate([0.0, 0.0, 0.6 - float(em.z.min())])
    best, _ = rend.best_stage(em)
    dof = s.depth_of_field
    radii = []
    for dz in (0.0, 1.0, 2.0):
        img = rend.render_flux(em, best + dz * dof)
        ee = RD.encircled_energy(img, s.pixel_size_sample, max_radius=3.0)
        assert ee.valid, f"no spots at {dz} DoF"
        radii.append(ee.descriptors["r50"])
    assert radii[0] < radii[-1]


def test_spectral_ratio_is_antisymmetric(rng):
    a = rng.random((128, 128)) + 0.5
    b = ndimage.gaussian_filter(a, 2.0)
    f, r_ab = RD.spectral_ratio(a, b, 0.1)
    _, r_ba = RD.spectral_ratio(b, a, 0.1)
    d_ab = RD.spectral_ratio_descriptors(f, r_ab)
    d_ba = RD.spectral_ratio_descriptors(f, r_ba)
    for k in d_ab:
        assert d_ab[k] == pytest.approx(-d_ba[k], rel=1e-6, abs=1e-9)


def test_spectral_ratio_cancels_the_sample_spectrum():
    """The ratio of two frames' power spectra is |OTF_a|^2/|OTF_b|^2: the
    sample's own spectrum divides out, so two unrelated geometries imaged
    through identical optics must give the same ratio.  This is the strongest
    geometry-invariance claim in the repository, so it is tested directly."""
    base = preset("20x_air")
    s = base.evolve(stack=SampleStack(
        n_sample=base.objective.n_immersion, n_glass=base.stack.n_glass,
        n_immersion=base.objective.n_immersion,
        n_glass_design=base.stack.n_glass_design,
        n_immersion_design=base.stack.n_immersion_design))
    eng = PSFEngine(s, fov_px=96, pad=2, workers=1, cache_size=16)
    rend = Renderer(eng, focal_shift=FocalShift(eng, depth_max=4.0))
    rng = np.random.default_rng(4)
    dof = s.depth_of_field
    out = {}
    for name, kw in (("thin_sheet", dict(extent=(10.0, 10.0), thickness=0.3,
                                         density=200.0)),
                     ("worm_like_chains", dict(n_chains=18, length=18.0,
                                               extent=(10.0, 10.0, 0.3),
                                               lin_density=400.0))):
        em = G.build(name, rng, **kw)
        em = em.translate([0.0, 0.0, 0.6 - float(em.z.min())])
        best, _ = rend.best_stage(em)
        i0 = rend.render_flux(em, best)
        i1 = rend.render_flux(em, best + 3.0 * dof)
        f, ratio = RD.spectral_ratio(i0, i1, s.pixel_size_sample)
        out[name] = RD.spectral_ratio_descriptors(f, ratio)
    for k in out["thin_sheet"]:
        a, b = out["thin_sheet"][k], out["worm_like_chains"][k]
        assert a == pytest.approx(b, rel=0.25), f"{k}: {a:.3f} vs {b:.3f}"


def test_find_spots_can_exclude_the_centre(rng):
    img = np.zeros((128, 128))
    for (y, x) in ((64, 64), (20, 20), (100, 30), (40, 110)):
        img[y, x] = 1e4
    img = ndimage.gaussian_filter(img, 1.5) + rng.normal(0, 1.0, (128, 128))
    all_spots = RD.find_spots(img, exclude_central=False)
    no_centre = RD.find_spots(img, exclude_central=True, central_fraction=0.2)
    assert len(all_spots) > len(no_centre)
