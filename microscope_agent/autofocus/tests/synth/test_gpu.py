"""The torch/CUDA path must reproduce the CPU path, and the new sample options behave."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from dino_autofocus.synth.optics.psf import PSFEngine
from dino_autofocus.synth.optics.system import preset
from dino_autofocus.synth.sim.dataset import DatasetConfig, render_scene
from dino_autofocus.synth.sim.scene import RandomisationConfig, draw_particles

torch = pytest.importorskip("torch")
cuda = pytest.mark.skipif(not torch.cuda.is_available(), reason="no CUDA device")

AB = {"astig_vertical": 0.05, "coma_x": 0.03, "spherical": 0.04}


@cuda
@pytest.mark.parametrize("name", ["20x_air", "60x_oil"])
@pytest.mark.parametrize("dtype,tol", [("complex128", 1e-12), ("complex64", 5e-6)])
def test_gpu_otf_matches_cpu(name, dtype, tol):
    s = preset(name)
    cpu = PSFEngine(s, fov_px=48, pad=2, workers=1, aberration=AB)
    gpu = PSFEngine(s, fov_px=48, pad=2, aberration=AB, device="cuda", gpu_dtype=dtype)
    dof = s.depth_of_field
    for dz in (0.0, 2.0 * dof, -5.0 * dof):
        for depth in (0.5, 3.0):
            a = cpu.otf(dz, depth)
            b = gpu.otf_t(dz, depth).cpu().numpy()
            assert np.abs(a - b).max() / np.abs(a).max() < tol


@cuda
def test_gpu_scene_is_identical_to_cpu():
    cfg = DatasetConfig(fov_px=32, n_planes=7, refine_planes=5, refine_passes=1,
                        global_step_dof=2.5, scan_span_dof=8.0, fft_workers=1,
                        psf_cache_size=8, ee_radii=16, esf_samples=33, focus_plane=True,
                        randomisation=RandomisationConfig(geometries=("solid_sphere",),
                                                          empty_probability=0.0))
    a = render_scene(3, cfg)
    b = render_scene(3, replace(cfg, device="cuda"))
    assert a is not None and b is not None
    np.testing.assert_array_equal(a["image"], b["image"])
    np.testing.assert_allclose(a["best_stage_um"], b["best_stage_um"], rtol=0, atol=1e-9)


def test_focus_plane_puts_one_plane_on_the_label():
    cfg = DatasetConfig(fov_px=32, n_planes=7, refine_planes=5, refine_passes=1,
                        global_step_dof=2.5, scan_span_dof=8.0, fft_workers=1,
                        psf_cache_size=8, ee_radii=16, esf_samples=33, focus_plane=True,
                        randomisation=RandomisationConfig(geometries=("solid_sphere",),
                                                          empty_probability=0.0))
    r = render_scene(5, cfg)
    assert r is not None
    assert np.sum(r["dz_dof"] == 0.0) == 1
    assert r["dz_dof"][len(r["dz_dof"]) // 2] == 0.0


def test_particles_have_areal_density_and_size():
    rc = RandomisationConfig(particle_diameter=5.0, particle_cv=0.0,
                             particle_per_mm2=(200.0, 200.0), particle_centre_probability=0.0)
    em = draw_particles(np.random.default_rng(0), rc, fov_um=400.0, grid_um=1000.0)
    # 1 mm^2 of raster at 200 per mm^2: Poisson(200), so within 4 sigma
    assert abs(em.meta["n_particles"] - 200) < 4 * np.sqrt(200)
    assert em.meta["mean_diameter_um"] == pytest.approx(5.0)
    # whole spheres resting on one layer
    assert em.z.min() >= 0.0 and em.z.max() <= 5.0 + 1e-9
    assert em.z.max() > 4.5
