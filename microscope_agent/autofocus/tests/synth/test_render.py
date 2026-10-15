"""Renderer: focal-shift model, flat field, wraparound, label machinery."""
from __future__ import annotations

import warnings

import numpy as np
import pytest

from dino_autofocus.synth.optics.psf import PSFEngine
from dino_autofocus.synth.optics.system import SampleStack, preset
from dino_autofocus.synth.sim import geometry as G
from dino_autofocus.synth.sim import metrics as M
from dino_autofocus.synth.sim.render import FocalShift, Renderer


def _renderer(system, fov=64, **kw):
    eng = PSFEngine(system, fov_px=fov, pad=2, workers=1, cache_size=16, **kw)
    return Renderer(eng, depth_bin=0.5,
                    focal_shift=FocalShift(eng, depth_max=8.0))


def test_analytic_focal_shift_matches_the_psf_scan():
    """The analytic model is a least-squares projection over the pupil; it has
    to agree with locating the peak-intensity plane directly, which costs
    seconds rather than a millisecond."""
    for name in ("20x_air", "40x_water"):
        eng = PSFEngine(preset(name), fov_px=48, pad=2, workers=1)
        analytic = FocalShift(eng, depth_max=6.0, mode="analytic")
        exact = eng.best_focus(2.0)
        dof = eng.system.depth_of_field
        assert (analytic(2.0) - exact) / dof == pytest.approx(0.0, abs=0.3)


def test_focal_shift_includes_the_coverglass_term():
    """The regression test for the worst bug this code had.  A coverglass
    thickness error produces a large *depth-independent* focus offset; a model
    that projects only the depth term misses it entirely, and the label search
    window then does not contain focus.  At 60x a -8 um error moves best focus
    by about +8 um."""
    base = preset("60x_oil")
    st = base.stack
    off = base.evolve(stack=SampleStack(
        n_sample=st.n_sample, n_glass=st.n_glass, n_immersion=st.n_immersion,
        n_glass_design=st.n_glass_design, n_immersion_design=st.n_immersion_design,
        t_glass=st.t_glass_design - 8.0, t_glass_design=st.t_glass_design,
        t_immersion=st.t_immersion, t_immersion_design=st.t_immersion_design))
    eng = PSFEngine(off, fov_px=48, pad=2, workers=1)
    fs = FocalShift(eng, depth_max=6.0)
    assert fs.offset > 3.0
    exact = eng.best_focus(2.0, span=8.0)
    assert (fs(2.0) - exact) / off.depth_of_field == pytest.approx(0.0, abs=0.4)


def test_index_matched_shift_is_minus_depth():
    base = preset("40x_water")
    matched = base.evolve(stack=SampleStack(
        n_sample=base.objective.n_immersion, n_glass=base.stack.n_glass,
        n_immersion=base.objective.n_immersion,
        n_glass_design=base.stack.n_glass_design,
        n_immersion_design=base.stack.n_immersion_design))
    fs = FocalShift(PSFEngine(matched, fov_px=32, pad=2, workers=1), depth_max=6.0)
    assert fs.slope == pytest.approx(-1.0, abs=0.02)
    assert fs(3.0) == pytest.approx(-3.0, abs=0.06)


def test_rendered_bead_focuses_where_the_model_predicts():
    """End-to-end: the renderer's PSF reuse, the focal-shift model and the focus
    metrics are independent pieces, and they have to agree."""
    s = preset("20x_air")
    rend = _renderer(s)
    dof = s.depth_of_field
    em = G.Emitters(np.array([[0.0, 0.0, 1.0]]), np.array([1.0]), "bead")
    predicted = float(rend.shift(1.0))
    stage = predicted + np.linspace(-3 * dof, 3 * dof, 21)
    stack = rend.render_stack(em, stage)
    for name in ("brenner", "normalised_variance", "peak_to_mean"):
        peak = M.argmax_parabolic(stage, M.focus_curve(stack, name))
        assert (peak - predicted) / dof == pytest.approx(0.0, abs=0.15)


def test_uniform_fill_renders_a_flat_field(rng):
    """Emitters covering the whole padded raster must give a flat image; any
    systematic roll-off would be a renderer artefact masquerading as vignetting."""
    s = preset("20x_air")
    rend = _renderer(s)
    half = rend.grid_um / 2
    n = 200_000
    xyz = np.column_stack([rng.uniform(-half, half, n), rng.uniform(-half, half, n),
                           np.full(n, 0.5)])
    img = rend.render_flux(G.Emitters(xyz, np.ones(n), "uniform"), 0.0)
    profile = img.mean(axis=0)
    assert profile[len(profile) // 2] / profile[1] == pytest.approx(1.0, abs=0.12)


def test_wraparound_is_negligible_for_a_full_field_sample(rng):
    """Checked against a 2x larger grid, the only honest way to bound it."""
    s = preset("20x_air")
    r2 = _renderer(s)
    eng4 = PSFEngine(s, fov_px=64, pad=4, workers=1, cache_size=8)
    r4 = Renderer(eng4, depth_bin=0.5, focal_shift=FocalShift(eng4, depth_max=8.0))
    sheet = G.build("thin_sheet", rng, extent=(12.0, 12.0), thickness=0.3,
                    density=200.0)
    sheet = sheet.translate([0.0, 0.0, 0.5 - float(sheet.z.min())])
    for dz in (0.0, 4.0):
        a, b = r2.render_flux(sheet, dz), r4.render_flux(sheet, dz)
        assert np.abs(a - b).max() / b.max() < 5e-3


def test_max_safe_defocus_is_relative_not_absolute():
    """The PSF width is set by the distance from an emitter's *own* best focus.
    Bounding the absolute stage coordinate instead declares the in-focus plane
    of a deep sample unreachable."""
    rend = _renderer(preset("60x_oil"))
    assert rend.max_safe_defocus > 0
    deep = 6.0
    rel = rend.relative_defocus([float(rend.shift(deep))], deep)
    assert abs(rel[0]) < 1e-9
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        rend.check_defocus([float(rend.shift(deep))], deep)   # must not warn


def test_check_defocus_warns_outside_the_safe_range():
    rend = _renderer(preset("60x_oil"))
    with pytest.warns(RuntimeWarning, match="wrap-free"):
        rend.check_defocus([3.0 * rend.max_safe_defocus], 0.0)


def test_best_stage_finds_the_focus_of_a_real_scene(rng):
    s = preset("20x_air")
    rend = _renderer(s)
    em = G.build("strut_network", rng, n_nodes=25, extent=(9.0, 9.0, 0.4),
                 lin_density=300.0)
    em = em.translate([0.0, 0.0, 0.8 - float(em.z.min())])
    best, info = rend.best_stage(em)
    assert np.isfinite(best)
    dof = s.depth_of_field
    here = M.focus_score(rend.render_flux(em, best), "brenner")
    for off in (-2.0, 2.0):
        assert M.focus_score(rend.render_flux(em, best + off * dof), "brenner") < here


def test_empty_scene_yields_no_label():
    rend = _renderer(preset("20x_air"))
    empty = G.Emitters(np.zeros((0, 3)), np.zeros(0), "empty")
    best, info = rend.best_stage(empty)
    assert not np.isfinite(best)
    assert "reason" in info
