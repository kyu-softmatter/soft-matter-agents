"""Scene assembly and domain randomisation.

A *scene* is one field of view: a sample placed at a physical depth, an optical
system with its own aberrations, an illumination field and a camera.  Every
quantity that would differ between a simulation and a real microscope is drawn
randomly here, because the sim-to-real gap -- not the network -- is the binding
constraint on this kind of autofocus model.

What gets randomised, and why it matters for focus specifically:

* **Aberrations** (Zernike, waves RMS).  Astigmatism and coma break the axial
  symmetry of the PSF; spherical aberration is what makes the axial response
  asymmetric and therefore makes the *sign* of defocus recoverable at all.
  Training on a single aberration state teaches the sign of that state only.
* **Index mismatch and coverglass thickness.**  Sets the depth-dependent focal
  shift, i.e. the mapping from stage position to label.
* **Emitter depth.**  Both an aberration source and a per-object label offset.
* **Photon budget, background, exposure.**  Gradient focus metrics track noise
  as much as sharpness on dim frames; the model must see that regime.
* **Illumination field.**  A smooth multiplicative field with vignetting and
  tilt.  It does not move with the stage, so it is a shortcut feature a network
  will happily latch onto if it is constant across the dataset.
* **Stage error.**  Real piezo/stepper motion has hysteresis and backlash, so
  the commanded position is not the achieved one.  Reported separately from the
  true position, because a search policy only ever knows the command.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..optics import zernike as Z
from ..optics.system import Camera, Illumination, ImagingSystem, Objective, SampleStack, preset
from . import geometry as G


# ---------------------------------------------------------------------------
# randomisation ranges
# ---------------------------------------------------------------------------

@dataclass
class RandomisationConfig:
    """Ranges for domain randomisation.  Every pair is (low, high), uniform."""

    # --- optics ---
    systems: Tuple[str, ...] = ("20x_air", "40x_water", "60x_oil")
    #: A specific instrument to model instead of sampling the presets.  Set this
    #: from a YAML file via :func:`dino_autofocus.synth.optics.config.load_system` when the
    #: dataset is meant for one microscope.
    custom_system: Optional[ImagingSystem] = None
    #: With ``custom_system`` set, whether to hold its optics fixed.  Jittering
    #: NA, wavelength and the refractive indices is right when training a model
    #: that must work on *any* microscope; it is wrong when the instrument is
    #: known, because it widens the distribution the model has to cover for no
    #: benefit.  Aberrations, photon budget, illumination field and stage error
    #: stay randomised either way -- those genuinely vary day to day on one
    #: instrument.
    lock_optics: bool = True
    na_jitter: Tuple[float, float] = (0.97, 1.0)        # multiplies nominal NA
    wavelength: Tuple[float, float] = (0.46, 0.68)
    aberration_scale: Tuple[float, float] = (0.0, 2.0)  # multiplies RANDOMISATION_SIGMA
    n_sample: Tuple[float, float] = (1.33, 1.40)
    coverglass_error: Tuple[float, float] = (-8.0, 8.0)     # um from design
    immersion_index_error: Tuple[float, float] = (-0.006, 0.006)

    # --- sample ---
    geometries: Optional[Tuple[str, ...]] = None        # None -> all
    base_depth: Tuple[float, float] = (0.3, 6.0)        # um above the coverglass
    n_objects: Tuple[int, int] = (1, 14)
    label_density: Tuple[float, float] = (400.0, 6000.0)
    empty_probability: float = 0.04                     # frames with no sample at all
    slab_thickness: Tuple[float, float] = (0.2, 8.0)    # axial extent actually kept, um
    max_emitters: int = 300_000                         # cost cap; excess is subsampled
    #: Particle mode: when set (um), the sample is uniformly dyed spheres of this
    #: mean diameter on one layer, at a number per area drawn from
    #: ``particle_per_mm2`` (log-uniform), instead of the geometry families.  A
    #: fixed areal density is what a real sample has, so a 4x field holds many
    #: particles and a 100x field few.  Spheres are kept whole (no slab clip).
    particle_diameter: Optional[float] = None
    particle_cv: float = 0.05                           # diameter spread, fraction
    particle_per_mm2: Tuple[float, float] = (30.0, 500.0)
    #: probability of one extra particle near the field centre, so most fields
    #: hold something even at high magnification
    particle_centre_probability: float = 0.9

    # --- photons ---
    photons_per_emitter: Tuple[float, float] = (200.0, 20000.0)
    background: Tuple[float, float] = (2.0, 400.0)
    target_fill: Tuple[float, float] = (0.05, 0.75)     # fraction of full well
    bleach_per_frame: Tuple[float, float] = (0.0, 0.02)

    # --- field ---
    vignetting: Tuple[float, float] = (0.0, 0.35)
    illum_tilt: Tuple[float, float] = (0.0, 0.25)
    illum_blobs: Tuple[int, int] = (0, 3)

    # --- stage ---
    stage_jitter: Tuple[float, float] = (0.0, 0.03)     # um rms, random per move
    stage_backlash: Tuple[float, float] = (0.0, 0.08)   # um, direction dependent


# ---------------------------------------------------------------------------
# a drawn scene
# ---------------------------------------------------------------------------

@dataclass
class Scene:
    system: ImagingSystem
    emitters: G.Emitters
    aberration: Dict[str, float]
    illumination_field: Optional[np.ndarray]
    exposure_fill: float
    bleach_per_frame: float
    stage_jitter: float
    stage_backlash: float
    params: Dict = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return len(self.emitters) == 0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _u(rng: np.random.Generator, rng_pair: Tuple[float, float]) -> float:
    lo, hi = rng_pair
    return float(rng.uniform(lo, hi))


def _loguniform(rng: np.random.Generator, rng_pair: Tuple[float, float]) -> float:
    lo, hi = rng_pair
    return float(np.exp(rng.uniform(np.log(max(lo, 1e-12)), np.log(max(hi, 1e-12)))))


def illumination_field(shape: Tuple[int, int], rng: np.random.Generator,
                       vignetting: float = 0.2, tilt: float = 0.1,
                       n_blobs: int = 1) -> np.ndarray:
    """Smooth multiplicative field: vignetting + linear tilt + a few soft blobs."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    rn = np.hypot((yy - cy) / max(cy, 1), (xx - cx) / max(cx, 1))
    fld = 1.0 - vignetting * np.clip(rn, 0, 1.4) ** 2
    ang = rng.uniform(0, 2 * np.pi)
    fld *= 1.0 + tilt * (np.cos(ang) * (xx - cx) / max(cx, 1) + np.sin(ang) * (yy - cy) / max(cy, 1))
    for _ in range(max(int(n_blobs), 0)):
        by, bx = rng.uniform(0, h), rng.uniform(0, w)
        sd = rng.uniform(0.2, 0.6) * max(h, w)
        amp = rng.uniform(-0.15, 0.15)
        fld *= 1.0 + amp * np.exp(-((yy - by) ** 2 + (xx - bx) ** 2) / (2 * sd ** 2))
    return np.clip(fld, 0.05, None)


def draw_system(rng: np.random.Generator, cfg: RandomisationConfig,
                system_name: Optional[str] = None) -> Tuple[ImagingSystem, Dict[str, float]]:
    """Draw a jittered optical system plus its aberration state."""
    if cfg.custom_system is not None:
        base = cfg.custom_system
        name = base.name
    else:
        name = system_name or str(rng.choice(cfg.systems))
        base = preset(name)

    if cfg.custom_system is not None and cfg.lock_optics:
        # Keep the instrument exactly as specified, but still vary what varies
        # on a real instrument from session to session.
        ill = Illumination(
            wavelength=base.illumination.wavelength,
            bandwidth=base.illumination.bandwidth,
            n_spectral=base.illumination.n_spectral,
            exposure=base.illumination.exposure,
            photons_per_emitter=_loguniform(rng, cfg.photons_per_emitter),
            background=_loguniform(rng, cfg.background),
        )
        sysm = ImagingSystem(objective=base.objective, camera=base.camera,
                             stack=base.stack, illumination=ill, name=name)
        return sysm, Z.random_named(rng, scale=_u(rng, cfg.aberration_scale))

    na = base.objective.na * _u(rng, cfg.na_jitter)
    obj = Objective(na=na, magnification=base.objective.magnification,
                    n_immersion=base.objective.n_immersion,
                    tube_length=base.objective.tube_length,
                    working_distance=base.objective.working_distance)

    n_imm = base.stack.n_immersion + (
        _u(rng, cfg.immersion_index_error) if base.objective.n_immersion > 1.05 else 0.0)
    n_sample = _u(rng, cfg.n_sample)
    stack = SampleStack(
        n_sample=n_sample,
        n_glass=base.stack.n_glass,
        n_immersion=n_imm,
        n_glass_design=base.stack.n_glass_design,
        n_immersion_design=base.stack.n_immersion_design,
        t_glass=base.stack.t_glass_design + _u(rng, cfg.coverglass_error),
        t_glass_design=base.stack.t_glass_design,
        t_immersion=base.stack.t_immersion,
        t_immersion_design=base.stack.t_immersion_design,
    )

    ill = Illumination(
        wavelength=_u(rng, cfg.wavelength),
        bandwidth=base.illumination.bandwidth,
        n_spectral=base.illumination.n_spectral,
        exposure=base.illumination.exposure,
        photons_per_emitter=_loguniform(rng, cfg.photons_per_emitter),
        background=_loguniform(rng, cfg.background),
    )

    sysm = ImagingSystem(objective=obj, camera=base.camera, stack=stack,
                         illumination=ill, name=name)
    ab = Z.random_named(rng, scale=_u(rng, cfg.aberration_scale))
    return sysm, ab


def draw_sample(rng: np.random.Generator, cfg: RandomisationConfig,
                fov_um: float, grid_um: float) -> G.Emitters:
    """Populate a field of view with randomly chosen, randomly placed objects.

    Objects are scattered over the *padded* raster, not just the cropped field,
    so out-of-field material contributes its defocused haze the way it does on a
    real microscope.
    """
    if rng.random() < cfg.empty_probability:
        return G.Emitters(np.zeros((0, 3)), np.zeros(0), "empty", {"empty": True})
    if cfg.particle_diameter:
        return draw_particles(rng, cfg, fov_um, grid_um)

    names = cfg.geometries or tuple(G.GENERATORS)
    kind = str(rng.choice(names))
    density = _loguniform(rng, cfg.label_density)
    half = grid_um / 2.0

    # Extended geometries already fill a field; compact ones get scattered.
    extended = kind in ("worm_like_chains", "strut_network", "spinodal_texture",
                        "thin_sheet", "point_emitters", "sphere_size_series")
    if extended:
        ext = (half * 0.9, half * 0.9, float(rng.uniform(0.2, 2.0)))
        params: Dict = {"density": density}
        if kind == "worm_like_chains":
            params |= dict(n_chains=int(rng.integers(5, 60)), length=float(rng.uniform(8, 40)),
                           persistence=float(rng.uniform(1.0, 15.0)),
                           radius=float(rng.uniform(0.02, 0.15)),
                           extent=ext, lin_density=density)
        elif kind == "strut_network":
            params |= dict(n_nodes=int(rng.integers(20, 140)),
                           k_neighbours=int(rng.integers(2, 5)),
                           radius=float(rng.uniform(0.04, 0.25)),
                           extent=ext, lin_density=density)
        elif kind == "spinodal_texture":
            params |= dict(extent=ext, correlation=float(rng.uniform(0.4, 3.0)),
                           fill=float(rng.uniform(0.2, 0.6)), density=density)
        elif kind == "thin_sheet":
            params |= dict(extent=ext[:2], tilt=float(rng.uniform(0, 8)),
                           thickness=float(rng.uniform(0.05, 1.0)),
                           correlation=float(rng.uniform(0.3, 3.0)), density=density)
        elif kind == "point_emitters":
            params = dict(n=int(rng.integers(3, 300)), extent=ext)
        elif kind == "sphere_size_series":
            params |= dict(radii=tuple(np.round(np.geomspace(
                rng.uniform(0.08, 0.3), rng.uniform(0.8, 2.5), int(rng.integers(3, 6))), 3)),
                spacing=float(rng.uniform(3.0, 10.0)), shell=bool(rng.random() < 0.3))
        obj = G.build(kind, rng, **params)
        return obj

    n_obj = int(rng.integers(cfg.n_objects[0], cfg.n_objects[1] + 1))
    parts: List[G.Emitters] = []
    for _ in range(n_obj):
        params = {"density": density}
        if kind == "solid_sphere":
            params |= dict(radius=_loguniform(rng, (0.08, 2.5)))
        elif kind == "hollow_shell":
            r = _loguniform(rng, (0.4, 4.0))
            params |= dict(radius=r, thickness=float(rng.uniform(0.02, 0.25) * r))
        elif kind == "ellipsoid":
            a = _loguniform(rng, (0.2, 2.5))
            params |= dict(semi_axes=(a, a * rng.uniform(0.2, 1.0), a * rng.uniform(0.2, 1.0)))
        elif kind == "superellipsoid":
            a = _loguniform(rng, (0.2, 2.0))
            params |= dict(semi_axes=(a, a * rng.uniform(0.6, 1.0), a * rng.uniform(0.6, 1.0)),
                           e1=float(rng.uniform(0.1, 1.6)), e2=float(rng.uniform(0.1, 1.6)))
        elif kind == "rod":
            params |= dict(length=_loguniform(rng, (0.5, 8.0)),
                           radius=_loguniform(rng, (0.05, 0.6)))
        elif kind == "lumpy_particle":
            params |= dict(radius=_loguniform(rng, (0.3, 2.5)),
                           roughness=float(rng.uniform(0.05, 0.5)),
                           n_modes=int(rng.integers(3, 10)),
                           surface=bool(rng.random() < 0.4))
        elif kind == "raspberry_cluster":
            params |= dict(n_sub=int(rng.integers(4, 24)),
                           r_sub=_loguniform(rng, (0.1, 0.6)),
                           r_core=_loguniform(rng, (0.4, 2.0)))
        elif kind == "fractal_aggregate":
            params |= dict(n_sub=int(rng.integers(8, 90)),
                           r_sub=_loguniform(rng, (0.08, 0.5)),
                           mode=str(rng.choice(["ballistic", "chain"])),
                           wander=float(rng.uniform(0.0, 2.0)))
        obj = G.build(kind, rng, **params)
        pos = np.array([rng.uniform(-half, half), rng.uniform(-half, half), 0.0])
        parts.append(obj.translate(pos))
    return G.Emitters.concat(parts, kind)


def draw_particles(rng: np.random.Generator, cfg: RandomisationConfig,
                   fov_um: float, grid_um: float) -> G.Emitters:
    """Uniformly dyed spheres resting on one layer, at a fixed number per area.

    Scattered over the padded raster like the other samples.  Every sphere gets
    the same emitter count per unit volume, so brightness scales with volume, and
    the total stays under ``max_emitters`` without the subsampling pass.
    """
    half = grid_um / 2.0
    per_mm2 = _loguniform(rng, cfg.particle_per_mm2)
    n = int(rng.poisson(per_mm2 * 1e-6 * grid_um ** 2))
    xy = rng.uniform(-half, half, size=(n, 2))
    if rng.random() < cfg.particle_centre_probability:
        xy = np.vstack([rng.uniform(-fov_um / 6, fov_um / 6, size=(1, 2)), xy])
    if len(xy) == 0:
        return G.Emitters(np.zeros((0, 3)), np.zeros(0), "solid_sphere", {"per_mm2": per_mm2})
    d = cfg.particle_diameter * np.clip(1 + cfg.particle_cv * rng.standard_normal(len(xy)), 0.5, 1.5)
    vol = d ** 3
    per = np.maximum((min(60_000, cfg.max_emitters // len(xy)) * vol / vol.max()).astype(int), 50)
    parts = []
    for (x, y), di, k in zip(xy, d, per):
        u = rng.normal(size=(k, 3))
        u *= (di / 2 * rng.uniform(size=k) ** (1 / 3) / np.linalg.norm(u, axis=1))[:, None]
        parts.append(G.Emitters(u + [x, y, di / 2], np.ones(k), "solid_sphere", {}))
    em = G.Emitters.concat(parts, "solid_sphere")
    em.meta = {"per_mm2": per_mm2, "n_particles": len(xy), "mean_diameter_um": float(d.mean())}
    return em


def cap_emitters(em: G.Emitters, max_n: int, rng: np.random.Generator) -> G.Emitters:
    """Bound the emitter count without changing the sample's brightness.

    A uniform subsample with weights scaled by ``N/max_n`` keeps the expected
    image identical and only adds a little extra granularity, which is a far
    better trade than silently truncating a dense sample.
    """
    n = len(em)
    if n <= max_n or n == 0:
        return em
    idx = rng.choice(n, size=max_n, replace=False)
    out = G.Emitters(em.xyz[idx], em.weight[idx] * (n / max_n), em.kind, dict(em.meta))
    out.meta["subsampled_from"] = n
    return out


def draw_scene(
    rng: np.random.Generator,
    cfg: RandomisationConfig,
    fov_px: int,
    grid_um: float,
    fov_um: float,
    shape: Tuple[int, int],
    system_name: Optional[str] = None,
) -> Scene:
    """Draw one complete field of view."""
    sysm, ab = draw_system(rng, cfg, system_name)
    em = draw_sample(rng, cfg, fov_um, grid_um)

    # Keep only an axial slab: a real acquisition images a section, and an
    # object thicker than the scan range has no single best-focus plane at all.
    slab = _loguniform(rng, cfg.slab_thickness)
    if len(em) and not cfg.particle_diameter:
        z_mid = float(np.median(em.z))
        em = em.clip_to(np.inf, np.inf, (z_mid - slab / 2.0, z_mid + slab / 2.0))

    # lift the sample to a physical depth above the coverglass
    base_depth = _loguniform(rng, cfg.base_depth)
    if len(em):
        em = em.translate([0.0, 0.0, base_depth - float(em.z.min())])
    em = cap_emitters(em, cfg.max_emitters, rng)

    fld = illumination_field(shape, rng,
                             vignetting=_u(rng, cfg.vignetting),
                             tilt=_u(rng, cfg.illum_tilt),
                             n_blobs=int(rng.integers(cfg.illum_blobs[0], cfg.illum_blobs[1] + 1)))

    return Scene(
        system=sysm, emitters=em, aberration=ab, illumination_field=fld,
        exposure_fill=_u(rng, cfg.target_fill),
        bleach_per_frame=_u(rng, cfg.bleach_per_frame),
        stage_jitter=_u(rng, cfg.stage_jitter),
        stage_backlash=_u(rng, cfg.stage_backlash),
        params={
            "geometry": em.kind, "base_depth_um": base_depth,
            "depth_span_um": float(np.ptp(em.z)) if len(em) else 0.0,
            "slab_thickness_um": slab,
            "subsampled_from": em.meta.get("subsampled_from"),
            "n_emitters": len(em), "aberration_rms_waves": Z.rms(ab),
            "strehl": Z.strehl(ab), "system": sysm.name, "na": sysm.objective.na,
            "wavelength_um": sysm.illumination.wavelength,
            "n_sample": sysm.stack.n_sample, "n_immersion": sysm.stack.n_immersion,
            "photons_per_emitter": sysm.illumination.photons_per_emitter,
            "background_photons_s": sysm.illumination.background,
        },
    )


# ---------------------------------------------------------------------------
# stage model
# ---------------------------------------------------------------------------

class Stage:
    """Commanded-vs-achieved axial position, with backlash and jitter.

    A focus controller only ever knows what it commanded.  Keeping the achieved
    position separate is what makes a reported focus error honest: part of it is
    the model's, part of it is the stage's, and conflating them flatters the model.
    """

    def __init__(self, rng: np.random.Generator, jitter: float = 0.01,
                 backlash: float = 0.0, position: float = 0.0) -> None:
        self.rng = rng
        self.jitter = float(jitter)
        self.backlash = float(backlash)
        self.commanded = float(position)
        self.achieved = float(position)
        self._last_direction = 0

    def move_to(self, target: float) -> float:
        target = float(target)
        direction = int(np.sign(target - self.commanded))
        err = 0.0
        if direction != 0 and self._last_direction != 0 and direction != self._last_direction:
            err -= direction * self.backlash          # lost motion on reversal
        if direction != 0:
            self._last_direction = direction
        err += self.rng.normal(0.0, self.jitter) if self.jitter > 0 else 0.0
        self.commanded = target
        self.achieved = target + err
        return self.achieved
