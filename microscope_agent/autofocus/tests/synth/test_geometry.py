"""Sample geometries, checked against what they claim to be."""
from __future__ import annotations

import warnings

import numpy as np
import pytest

from dino_autofocus.synth.sim import geometry as G


def _sigmas(em):
    c = em.xyz - em.centroid()
    return np.sqrt(np.linalg.eigvalsh(np.cov(c.T)))[::-1]


@pytest.mark.parametrize("name", sorted(G.GENERATORS))
def test_every_generator_produces_a_valid_cloud(name, rng):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        em = G.build(name, rng)
    assert len(em) > 0
    assert em.xyz.shape == (len(em), 3)
    assert em.weight.shape == (len(em),)
    assert np.isfinite(em.xyz).all() and np.isfinite(em.weight).all()
    assert (em.weight > 0).all()
    assert G.family_of(name) in G.FAMILIES


def test_solid_sphere_labelling_density(rng):
    """Emitter count must follow 4/3 pi rho R^3: the density argument has to
    mean fluorophores per cubic micrometre, or brightness stops being physical."""
    density = 3000.0
    for r in (0.4, 0.8, 1.6):
        em = G.build("solid_sphere", rng, radius=r, density=density)
        expected = 4.0 / 3.0 * np.pi * r ** 3 * density
        assert len(em) == pytest.approx(expected, rel=0.12)


def test_hollow_shell_is_hollow(rng):
    em = G.build("hollow_shell", rng, radius=2.0, thickness=0.2, density=3000.0)
    r = np.linalg.norm(em.xyz, axis=1)
    assert r.min() > 1.7
    assert r.max() <= 2.01


def test_ellipsoid_recovers_its_aspect_ratio(rng):
    em = G.build("ellipsoid", rng, semi_axes=(2.0, 0.5, 0.5),
                 density=3000.0, orient=False)
    s = _sigmas(em)
    assert s[0] / s[2] == pytest.approx(4.0, rel=0.15)


def test_superellipsoid_at_low_exponent_is_a_cube(rng):
    """A uniform cube of half-side a has sigma = a/sqrt(3) = 0.577a along every
    axis; a uniform sphere of radius a gives 0.447a.  The distinction is the
    whole point of the exponent knob."""
    em = G.build("superellipsoid", rng, semi_axes=(1.0, 1.0, 1.0),
                 e1=0.1, e2=0.1, density=3000.0, orient=False)
    s = _sigmas(em)
    assert s.mean() == pytest.approx(1.0 / np.sqrt(3.0), rel=0.06)
    assert s[0] / s[2] == pytest.approx(1.0, rel=0.08)


def test_rod_is_elongated(rng):
    em = G.build("rod", rng, length=4.0, radius=0.2, density=3000.0, orient=False)
    s = _sigmas(em)
    assert s[0] / s[2] > 5.0


def test_chain_aggregate_is_more_open_than_ballistic(rng):
    """Same monomer count and size: the self-avoiding chain must have the larger
    radius of gyration, i.e. the lower mass-fractal dimension."""
    kw = dict(n_sub=90, r_sub=0.25, density=200.0)
    b = G.build("fractal_aggregate", rng, mode="ballistic", **kw).meta
    c = G.build("fractal_aggregate", rng, mode="chain", **kw).meta
    assert c["radius_gyration"] > b["radius_gyration"]
    assert c["fractal_dimension"] < b["fractal_dimension"]
    assert 1.6 < c["fractal_dimension"] < 2.3


def test_filaments_stay_inside_their_slab(rng):
    """A free 3-D worm-like chain would diffuse far out of the thin slab such a
    sample occupies, so the walk is confined."""
    ext_z = 1.5
    em = G.build("worm_like_chains", rng, n_chains=20, length=30.0,
                 extent=(20.0, 20.0, ext_z), lin_density=200.0)
    assert np.ptp(em.z) < 2.6 * ext_z


def test_thin_sheet_is_laterally_uniform(rng):
    """Blending each emitter's uniform position towards a uniform cluster centre
    sums two uniforms into a triangular distribution and piles the sample into
    the middle of the field, where it reads as vignetting in the render."""
    em = G.build("thin_sheet", rng, extent=(16.0, 16.0), thickness=0.3,
                 density=200.0, clumping=0.6)
    h, _, _ = np.histogram2d(em.x, em.y, bins=16, range=[[-16, 16], [-16, 16]])
    centre = h[6:10, 6:10].mean()
    border = np.concatenate([h[0], h[-1], h[:, 0], h[:, -1]]).mean()
    assert centre / border == pytest.approx(1.0, rel=0.35)
    assert h.std() / h.mean() > 0.1        # but still textured, not white noise


def test_tilted_sheet_has_a_depth_gradient(rng):
    flat = G.build("thin_sheet", rng, extent=(16.0, 16.0), tilt=0.0, density=100.0)
    tilted = G.build("thin_sheet", rng, extent=(16.0, 16.0), tilt=8.0, density=100.0)
    assert np.ptp(tilted.z) > 3.0 * np.ptp(flat.z)
    assert abs(np.corrcoef(tilted.x, tilted.z)[0, 1]) > 0.7


def test_emitters_transform_and_concat(rng):
    a = G.build("solid_sphere", rng, radius=0.5, density=2000.0)
    b = a.translate([5.0, 0.0, 1.0])
    assert b.centroid()[0] == pytest.approx(a.centroid()[0] + 5.0, abs=1e-9)
    both = G.Emitters.concat([a, b])
    assert len(both) == 2 * len(a)
    assert both.total_weight == pytest.approx(2 * a.total_weight)
    clipped = both.clip_to(1.0, 1.0)
    assert len(clipped) < len(both)


def test_density_cap_warns_rather_than_silently_truncating(rng):
    with pytest.warns(RuntimeWarning, match="capping"):
        G.build("solid_sphere", rng, radius=6.0, density=10000.0)
