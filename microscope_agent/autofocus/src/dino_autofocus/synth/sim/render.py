"""Render an emitter cloud into a camera z-stack.

The rendering identity is

    flux(stage) = sum_over_depths  density_d  *conv*  psf(stage, depth_d)

which is exact for incoherent fluorescence.  Two things make it tractable:

**Depth handling.**  ``psf`` depends on the emitter depth as well as the stage
position, and with an index-mismatched stack the depth dependence is dominated
by a *shift* of best focus -- about -1.3 um of stage travel per um of depth for
oil into water.  Quantising depth coarsely would therefore blur focus by more
than a depth of field.  Instead the shift is removed analytically via
:meth:`PSFEngine.best_focus` (fitted once per system and interpolated) and only
the slowly-varying residual aberration is quantised into depth bins.  A depth
bin of 0.5 um then costs a small aberration error instead of a large focus error.

**Convolution.**  Emitters are splatted onto the padded PSF grid, transformed
once per depth bin, and multiplied by a cached OTF per (stage, depth bin).
Emitters outside the cropped field still contribute their out-of-focus haze,
which is the correct behaviour and a real background term that a model trained
on isolated crops never learns to ignore.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import fft as sfft

from ..optics.psf import PSFEngine
from ..optics.system import ImagingSystem
from .camera import Sensor, SensorPattern, auto_exposure
from .geometry import Emitters


# ---------------------------------------------------------------------------
# focal-shift model
# ---------------------------------------------------------------------------

class FocalShift:
    """Best-focus defocus as a function of emitter depth.

    Two ways to get it:

    ``mode="analytic"`` (default, free)
        The depth term enters the pupil phase as ``k0 * n_s * depth * cos(th_s)``
        and the stage term as ``k0 * n_i * defocus * cos(th_i)``.  The stage
        position that best cancels the depth term is therefore the least-squares
        projection of one onto the other over the pupil::

            shift(depth) = -depth * <n_s cos_s, n_i cos_i> / <n_i cos_i, n_i cos_i>

        This minimises residual wavefront RMS, which is the standard definition
        of "nominal focus", costs one array reduction, and is exactly linear in
        depth.  The leftover (spherical aberration) is what genuinely cannot be
        removed by refocusing.

    ``mode="psf"`` (slow, reference)
        Scans :meth:`PSFEngine.best_focus`, i.e. locates the true peak-intensity
        plane, at a few knots and interpolates.  This differs from the analytic
        value because peak intensity weights the marginal rays more heavily than
        a least-squares wavefront fit does; use it to check the approximation,
        not in a data-generation loop, where it costs seconds per scene.

    Either way the *label* comes from :meth:`Renderer.best_stage` on the actual
    render, so this class only has to remove the bulk of the depth dependence --
    a residual here costs accuracy in the PSF-reuse approximation, not a biased
    label.
    """

    def __init__(self, engine: PSFEngine, depth_max: float = 10.0, n_knots: int = 6,
                 mode: str = "analytic") -> None:
        self.engine = engine
        self.mode = mode
        st = engine.system.stack

        self.offset = 0.0
        # No short-circuit for the index-matched case.  An earlier version
        # returned a zero shift whenever n_sample == n_immersion, reasoning that
        # a matched stack induces no aberration.  It induces no *aberration*,
        # but it certainly induces a focal *shift*: with n_s = n_i the depth and
        # defocus terms are the same function of pupil angle, so best focus sits
        # at exactly -depth -- the emitter has physically moved.  The analytic
        # projection below returns a slope of -1 in that case, which is right;
        # the special case overrode it with 0 and mis-centred the label search
        # by the full sample depth.
        if mode == "analytic":
            self.slope, self.offset = self._analytic_terms()
            self.depths = np.array([0.0, max(depth_max, 1e-3)])
            self.shifts = self.offset + self.slope * self.depths
        elif mode == "psf":
            self.depths = np.linspace(0.0, max(depth_max, 1e-3), n_knots)
            self.shifts = np.array([engine.best_focus(float(d)) for d in self.depths])
            self.slope = float((self.shifts[-1] - self.shifts[-2]) /
                               (self.depths[-1] - self.depths[-2]))
            self.offset = float(self.shifts[0])
        else:
            raise ValueError(f"mode must be 'analytic' or 'psf', got {mode!r}")

    def _analytic_terms(self) -> Tuple[float, float]:
        """(slope, offset) of the least-squares best-focus stage position."""
        eng = self.engine
        st = eng.system.stack
        g = eng.grid(eng.system.illumination.wavelength)
        sup = eng.support(g)
        if not sup.any():
            return 0.0, 0.0

        def mode(arr: np.ndarray) -> np.ndarray:
            # piston carries no focus information: refocusing cannot change the
            # pupil mean, so projecting onto it would invent a shift
            v = np.real(arr)[sup]
            return v - v.mean()

        depth_mode = mode(st.n_sample * g.cos_theta(st.n_sample))
        defocus_mode = mode(st.n_immersion * g.cos_theta(st.n_immersion))
        mismatch = mode(
            st.n_glass * st.t_glass * g.cos_theta(st.n_glass)
            + st.n_immersion * st.t_immersion * g.cos_theta(st.n_immersion)
            - st.n_glass_design * st.t_glass_design * g.cos_theta(st.n_glass_design)
            - st.n_immersion_design * st.t_immersion_design
            * g.cos_theta(st.n_immersion_design)
        )
        denom = float(np.dot(defocus_mode, defocus_mode))
        if denom <= 1e-30:
            return 0.0, 0.0
        slope = -float(np.dot(depth_mode, defocus_mode)) / denom
        offset = -float(np.dot(mismatch, defocus_mode)) / denom
        return slope, offset

    def __call__(self, depth) -> np.ndarray:
        d = np.abs(np.atleast_1d(np.asarray(depth, dtype=np.float64)))
        out = np.interp(d, self.depths, self.shifts)
        if self.depths[-1] > self.depths[0]:
            far = d > self.depths[-1]
            out = np.where(far, self.shifts[-1] + self.slope * (d - self.depths[-1]), out)
        return out if np.ndim(depth) else float(out[0])


# ---------------------------------------------------------------------------
# render result
# ---------------------------------------------------------------------------

@dataclass
class ZStack:
    """A rendered focal series."""

    stage: np.ndarray                  # (Nz,) stage/defocus parameter, um
    flux: np.ndarray                   # (Nz, H, W) noiseless photon rate, photons/s/px
    adu: Optional[np.ndarray] = None   # (Nz, H, W) camera output
    exposure: float = 0.0
    best_stage: float = float("nan")   # label: stage position of best focus
    meta: Dict = field(default_factory=dict)

    @property
    def defocus(self) -> np.ndarray:
        """Signed defocus label for each plane, um (0 = in focus)."""
        return self.stage - self.best_stage

    def __len__(self) -> int:
        return int(self.stage.size)


# ---------------------------------------------------------------------------
# renderer
# ---------------------------------------------------------------------------

class Renderer:
    def __init__(
        self,
        engine: PSFEngine,
        depth_bin: float = 0.5,
        defocus_quant: float = 0.01,
        focal_shift: Optional[FocalShift] = None,
        depth_max: float = 10.0,
        illumination_field: Optional[np.ndarray] = None,
    ) -> None:
        self.engine = engine
        self.system: ImagingSystem = engine.system
        self.depth_bin = float(depth_bin)
        self.defocus_quant = float(defocus_quant)
        self.shift = focal_shift if focal_shift is not None else FocalShift(engine, depth_max)
        self.illumination_field = illumination_field

    # -- geometry of the raster -------------------------------------------
    @property
    def n_grid(self) -> int:
        return self.engine.n_grid

    @property
    def dx(self) -> float:
        return self.engine.dx

    @property
    def fov_um(self) -> float:
        return self.engine.fov_px * self.system.pixel_size_sample

    @property
    def grid_um(self) -> float:
        """Extent of the padded raster -- emitters out to here still contribute."""
        return self.n_grid * self.dx

    @property
    def margin_um(self) -> float:
        """Zero-padding margin between the crop and the raster edge, um."""
        return 0.5 * (self.grid_um - self.fov_um)

    @property
    def max_safe_defocus(self) -> float:
        """Largest defocus *relative to an emitter's own best focus* that stays
        wrap-free, in um.

        The PSF looked up for an emitter at depth ``d`` and stage ``z`` has the
        width set by ``z - shift(d)`` -- its distance from that emitter's own
        best-focus plane -- not by ``z`` itself.  So this bounds the relative
        quantity.  Bounding the absolute stage position instead (an earlier
        version of this code) is both wrong and badly restrictive: with an oil
        objective on a sample 3 um deep, best focus already sits about 4 um from
        ``z = 0``, so an absolute bound would declare the in-focus plane itself
        unreachable and clip the label search to a window not containing focus.

        Measured against a 2x larger grid, the relative error on a realistic
        full-field sample stays below 1e-3 up to this limit and reaches ~5% only
        for an isolated emitter one micrometre from the crop edge at 20 um
        defocus (blur radius 22.7 um against a 20.8 um margin).  Raise
        ``PSFEngine(pad=...)`` to extend it.
        """
        return float(self.margin_um / max(self.engine.tan_alpha, 1e-9))

    def relative_defocus(self, stage: Sequence[float], depth: float) -> np.ndarray:
        """Stage positions expressed as defocus from best focus at one depth."""
        return np.asarray(stage, dtype=np.float64) - float(self.shift(depth))

    def check_defocus(self, stage: Sequence[float],
                      depth: Optional[float] = None) -> None:
        """Warn if a scan strays outside the wrap-free *relative* defocus range."""
        z = np.asarray(stage, dtype=np.float64)
        if z.size == 0:
            return
        rel = z if depth is None else self.relative_defocus(z, depth)
        worst = float(np.max(np.abs(rel)))
        if worst > self.max_safe_defocus:
            import warnings
            warnings.warn(
                f"requested relative defocus up to {worst:.2f} um exceeds the "
                f"wrap-free limit {self.max_safe_defocus:.2f} um for this grid "
                f"(pad={self.engine.pad}, margin={self.margin_um:.1f} um). "
                f"Expect a few percent error in the defocused tails; increase "
                f"PSFEngine(pad=...) or shrink the scan range.",
                RuntimeWarning, stacklevel=2,
            )

    # -- splatting ---------------------------------------------------------
    def _splat(self, em: Emitters) -> List[Tuple[float, np.ndarray]]:
        """Bin emitters by depth and splat each bin onto the padded raster.

        Returns a list of ``(depth_bin_centre, density)``.  Bilinear splatting
        keeps sub-pixel emitter positions, which matters because a
        nearest-pixel round-off of half a fine pixel is a real (and avoidable)
        blur of the PSF.
        """
        n = self.n_grid
        if len(em) == 0:
            return []
        c = n / 2.0
        gx = em.x / self.dx + c
        gy = em.y / self.dx + c
        inside = (gx >= 0) & (gx <= n - 1) & (gy >= 0) & (gy <= n - 1)
        gx, gy, w, z = gx[inside], gy[inside], em.weight[inside], em.z[inside]
        if gx.size == 0:
            return []

        bins = np.round(z / self.depth_bin).astype(np.int64)
        out: List[Tuple[float, np.ndarray]] = []
        x0 = np.floor(gx).astype(np.int64); y0 = np.floor(gy).astype(np.int64)
        fx = gx - x0; fy = gy - y0
        x1 = np.minimum(x0 + 1, n - 1); y1 = np.minimum(y0 + 1, n - 1)

        for b in np.unique(bins):
            m = bins == b
            d = np.zeros((n, n), dtype=np.float64)
            np.add.at(d, (y0[m], x0[m]), w[m] * (1 - fx[m]) * (1 - fy[m]))
            np.add.at(d, (y0[m], x1[m]), w[m] * fx[m] * (1 - fy[m]))
            np.add.at(d, (y1[m], x0[m]), w[m] * (1 - fx[m]) * fy[m])
            np.add.at(d, (y1[m], x1[m]), w[m] * fx[m] * fy[m])
            # mean depth of the bin, not the bin centre: closer to the truth
            out.append((float(np.average(z[m], weights=np.maximum(w[m], 1e-12))), d))
        return out

    # -- PSF lookup --------------------------------------------------------
    def _effective_defocus(self, stage: float, depth: float, depth_ref: float) -> float:
        """Defocus to evaluate the cached PSF at, preserving relative focus.

        ``stage - shift(depth)`` is the true distance from best focus.  Reusing
        a PSF computed at ``depth_ref`` requires the same relative distance,
        hence the ``+ shift(depth_ref)``.
        """
        eff = stage - float(self.shift(depth)) + float(self.shift(depth_ref))
        return float(np.round(eff / self.defocus_quant) * self.defocus_quant)

    def _depth_ref(self, depth: float) -> float:
        return float(np.round(depth / self.depth_bin) * self.depth_bin)

    # -- rendering ---------------------------------------------------------
    def render_flux(self, em: Emitters, stage: float,
                    splats: Optional[List[Tuple[float, np.ndarray]]] = None,
                    spectra: Optional[Dict] = None) -> np.ndarray:
        """Noiseless photon rate per camera pixel at one stage position."""
        splats = self._splat(em) if splats is None else splats
        if not splats:
            return np.zeros((self.engine.fov_px, self.engine.fov_px))
        if self.engine.on_gpu:
            return self._finish(self._render_fine_torch(stage, splats))
        n = self.n_grid
        acc = np.zeros((n, n), dtype=np.complex128)
        for depth, dens in splats:
            d_ref = self._depth_ref(depth)
            eff = self._effective_defocus(stage, depth, d_ref)
            acc += sfft.fft2(dens, workers=self.engine.workers) * self.engine.otf(eff, d_ref)
        img = np.real(sfft.ifft2(acc, workers=self.engine.workers))
        img = np.clip(img, 0.0, None)
        return self._finish(self.engine._crop(img))

    def _finish(self, fine: np.ndarray) -> np.ndarray:
        """Bin the cropped fine raster onto camera pixels and apply the illumination."""
        k = self.engine.os
        cam_img = fine.reshape(self.engine.fov_px, k, self.engine.fov_px, k).sum(axis=(1, 3))

        cam_img = cam_img * self.system.illumination.photons_per_emitter
        if self.illumination_field is not None:
            cam_img = cam_img * self.illumination_field
        return cam_img

    def _render_fine_torch(self, stage: float, splats) -> np.ndarray:
        """GPU version of the convolution in :meth:`render_flux`, cropped fine raster.

        The splat FFTs depend only on the sample, so they are computed once per
        splat list and reused for every stage position of the scene (the CPU path
        recomputes them per plane).
        """
        import torch

        eng = self.engine
        if getattr(self, "_splat_src", None) is not splats:
            rd = torch.float64 if eng.gpu_dtype == "complex128" else torch.float32
            self._splat_fft = [torch.fft.fft2(torch.as_tensor(d, device=eng.device).to(rd))
                               for _, d in splats]
            self._splat_src = splats
        acc = None
        for (depth, _), dk in zip(splats, self._splat_fft):
            d_ref = self._depth_ref(depth)
            term = dk * eng.otf_t(self._effective_defocus(stage, depth, d_ref), d_ref)
            acc = term if acc is None else acc + term
        img = torch.fft.ifft2(acc).real.clamp_min(0.0)
        n, m = eng.n_grid, eng.n_fine
        s = (n - m) // 2
        return img[s:s + m, s:s + m].to(torch.float64).cpu().numpy()

    def render_stack(self, em: Emitters, stage: Sequence[float]) -> np.ndarray:
        """Noiseless flux for a whole focal series -- splats computed once."""
        self.check_defocus(stage, float(np.median(em.z)) if len(em) else None)
        splats = self._splat(em)
        return np.stack([self.render_flux(em, float(s), splats=splats) for s in stage])

    # -- labelling ---------------------------------------------------------
    def best_stage(self, em: Emitters, metric: str = "brenner",
                   span: Optional[float] = None, coarse: int = 21,
                   refine_passes: int = 2) -> Tuple[float, Dict]:
        """Stage position that maximises a noiseless focus functional.

        This is the ground-truth label.  Defining it on the *noiseless* render
        of the actual scene is the only self-consistent choice: a 3D sample has
        no single in-focus plane, so "in focus" has to mean "the plane a perfect
        focus metric would pick", and the metric is evaluated without noise so
        the label does not inherit shot noise.
        """
        from .metrics import focus_score

        splats = self._splat(em)
        if not splats:
            return float("nan"), {"reason": "no emitters in field"}

        depths = np.array([d for d, _ in splats])
        weights = np.array([float(x.sum()) for _, x in splats])
        centre = float(self.shift(np.average(depths, weights=np.maximum(weights, 1e-12))))
        if span is None:
            span = max(8.0 * self.system.depth_of_field, 1.5 * float(np.ptp(self.shift(depths))) + 1e-6)

        lo, hi = centre - span, centre + span
        trace: List[Tuple[float, float]] = []
        for _ in range(refine_passes + 1):
            zs = np.linspace(lo, hi, coarse)
            sc = np.array([focus_score(self.render_flux(em, float(z), splats=splats), metric)
                           for z in zs])
            trace.extend(zip(zs.tolist(), sc.tolist()))
            j = int(sc.argmax())
            half = (zs[1] - zs[0])
            lo, hi = zs[max(j - 1, 0)], zs[min(j + 1, coarse - 1)]
            if hi - lo < 1e-3:
                break

        zs = np.linspace(lo, hi, 5)
        sc = np.array([focus_score(self.render_flux(em, float(z), splats=splats), metric) for z in zs])
        j = int(sc.argmax())
        best = float(zs[j])
        if 0 < j < len(zs) - 1:
            y0, y1, y2 = sc[j - 1], sc[j], sc[j + 1]
            den = y0 - 2 * y1 + y2
            if abs(den) > 1e-30:
                best = float(zs[j] - 0.5 * (zs[1] - zs[0]) * (y2 - y0) / den)
        trace.extend(zip(zs.tolist(), sc.tolist()))
        return best, {"metric": metric, "trace": sorted(trace), "centre_guess": centre}

    # -- full acquisition --------------------------------------------------
    def acquire(
        self,
        em: Emitters,
        stage: Sequence[float],
        rng: np.random.Generator,
        exposure: Optional[float] = None,
        target_fill: float = 0.4,
        sensor: Optional[Sensor] = None,
        label_metric: str = "brenner",
        compute_label: bool = True,
    ) -> ZStack:
        """Render a focal series and pass it through the camera."""
        stage = np.asarray(stage, dtype=np.float64)
        splats = self._splat(em)
        flux = np.stack([self.render_flux(em, float(s), splats=splats) for s in stage])

        cam = self.system.camera
        if exposure is None:
            # set exposure from the sharpest plane, so it is the one at risk of
            # clipping -- matching how an operator would set it up
            ref = flux[int(np.argmax(flux.max(axis=(1, 2))))]
            exposure = auto_exposure(ref, cam, target_fill=target_fill,
                                     max_exposure=self.system.illumination.exposure * 20)

        if sensor is None:
            sensor = Sensor(cam, flux.shape[1:], rng)
        bg = self.system.illumination.background
        adu = np.stack([sensor.expose(f, exposure, background=bg) for f in flux])

        best = float("nan")
        label_meta: Dict = {}
        if compute_label:
            best, label_meta = self.best_stage(em, metric=label_metric)

        return ZStack(
            stage=stage, flux=flux, adu=adu, exposure=float(exposure), best_stage=best,
            meta={
                "kind": em.kind, "n_emitters": len(em), "geometry": em.meta,
                "system": self.system.name, "label": label_meta,
                "saturated_fraction": float(np.mean(adu >= cam.adu_max - 0.5)),
                "background_photons_s": bg,
            },
        )
