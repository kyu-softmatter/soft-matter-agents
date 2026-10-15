"""Point spread functions for widefield fluorescence.

Three forward models share one interface, so the same renderer can trade
fidelity for speed:

``vectorial``
    Richards--Wolf / Torok vectorial diffraction, written in the back-focal-plane
    (pupil) form.  Handles high NA, dipole emission, Zernike aberrations, a
    stratified sample/coverglass/immersion stack and supercritical-angle
    (evanescent) rays.  This is the reference model.
``scalar``
    Gibson--Lanni scalar model: the same stratified-media phase but a single
    scalar pupil.  ~6x cheaper, accurate to a few percent below NA ~0.7.
``gaussian``
    Defocus-dependent Gaussian.  No out-of-focus ring structure -- useful only
    as a sanity baseline to show how much the ring structure actually matters.

Conventions
-----------
* Lengths in um, wavelengths in vacuum um, angles in rad.
* ``defocus`` is the signed axial distance from the objective's nominal focal
  plane to the emitter, positive when the emitter lies *further from the
  objective* (deeper into the sample).  A focus controller therefore drives
  ``defocus`` to zero; the sign that corresponds to "stage up" is a one-time
  hardware calibration.
* ``depth`` is the emitter's height above the inner coverglass surface.  It is
  what generates depth-dependent spherical aberration, and hence the axial
  asymmetry that lets a network recover the *sign* of the defocus from a
  single frame.
* PSFs are normalised by Parseval's identity on the pupil, so a slice integrates
  to 1 over an infinite plane.  A slice sum below 1 is genuine energy that has
  left the computed window.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Literal, Optional, Sequence, Tuple

import numpy as np
from scipy import fft as sfft

from . import zernike as Z
from .system import ImagingSystem

PSFModel = Literal["vectorial", "scalar", "gaussian"]
Dipole = Literal["free", "x", "y", "z"]


# ---------------------------------------------------------------------------
# pupil geometry
# ---------------------------------------------------------------------------

@dataclass
class PupilGrid:
    """Frequency-space grid shared by every PSF evaluated on one fine raster."""

    n: int                  # grid side, fine pixels
    dx: float               # fine pixel size in the sample plane, um
    wavelength: float
    na: float

    def __post_init__(self) -> None:
        fx = np.fft.fftfreq(self.n, d=self.dx)          # cycles / um
        self.fxx, self.fyy = np.meshgrid(fx, fx, indexing="xy")
        self.f = np.hypot(self.fxx, self.fyy)
        self.phi = np.arctan2(self.fyy, self.fxx)
        self.f_max = self.na / self.wavelength
        self.mask = self.f <= self.f_max
        # normalised pupil radius, for Zernike evaluation
        self.rho = np.where(self.mask, self.f / self.f_max, 0.0)
        self.f_nyquist = 1.0 / (2.0 * self.dx)
        self._cos_cache: Dict[float, np.ndarray] = {}

    @property
    def resolves_pupil(self) -> bool:
        """True when the grid Nyquist frequency contains the whole pupil."""
        return self.f_nyquist >= self.f_max

    @property
    def pupil_radius_px(self) -> float:
        return self.f_max / (1.0 / (self.n * self.dx))

    def propagating(self, n_medium: float) -> np.ndarray:
        """Rays that are still propagating (not evanescent) in a given medium."""
        return self.sin_theta(n_medium) <= 1.0

    def sin_theta(self, n_medium: float) -> np.ndarray:
        return self.f * self.wavelength / n_medium

    def cos_theta(self, n_medium: float) -> np.ndarray:
        """cos(theta) in a medium, complex where the wave is evanescent.

        Memoised per refractive index: a scene evaluates hundreds of PSFs on the
        same grid, and profiling showed this alone costing 2.6 s of an 18 s
        scene across 1446 identical recomputations.
        """
        key = round(float(n_medium), 9)
        hit = self._cos_cache.get(key)
        if hit is None:
            s2 = (self.sin_theta(n_medium) ** 2).astype(np.complex128)
            hit = np.sqrt(1.0 - s2)
            self._cos_cache[key] = hit
        return hit


@dataclass
class PupilTerms:
    """Everything about the pupil that does not depend on defocus or depth.

    Splitting these out is the single largest speed-up in the renderer.  The
    Zernike wavefront, the stratified-media Fresnel coefficients, the
    apodization and the dipole polarisation factors are all fixed by the grid,
    the system and the aberration state, yet a naive implementation rebuilds
    them for every one of the hundreds of PSFs a single scene evaluates.
    Profiling one scene at 18.1 s found 3.8 s in Zernike evaluation alone (1728
    calls) against 3.1 s in the FFTs that actually do the work.

    With these cached, one PSF costs the phase ramp, one ``exp``, and the FFTs.
    """

    support: np.ndarray            # pupil rays that contribute
    apodization: np.ndarray        # complex amplitude weight
    wavefront: np.ndarray          # aberration phase, radians
    depth_mode: np.ndarray         # n_sample * cos(theta_sample)
    defocus_mode: np.ndarray       # n_immersion * cos(theta_immersion)
    const_opd: np.ndarray          # coverglass/immersion mismatch OPD
    polarisation: np.ndarray       # (n_field, ny, nx) dipole -> (Ex, Ey) factors
    k0: float


def _fresnel_t(n_a: float, n_b: float, cos_a: np.ndarray, cos_b: np.ndarray):
    """Amplitude transmission coefficients (s, p) for a -> b."""
    ts = 2.0 * n_a * cos_a / (n_a * cos_a + n_b * cos_b)
    tp = 2.0 * n_a * cos_a / (n_b * cos_a + n_a * cos_b)
    return ts, tp


# ---------------------------------------------------------------------------
# main PSF engine
# ---------------------------------------------------------------------------

class PSFEngine:
    """Computes and caches defocus stacks of PSFs for one imaging system.

    Parameters
    ----------
    system
        Objective / camera / stack / illumination description.
    fov_px
        Output field of view in *camera* pixels.
    oversampling
        Fine-grid factor; defaults to whatever critically samples the intensity
        PSF for this objective (``system.oversampling()``).
    pad
        Zero-padding factor for the pupil FFT.  The PSF is computed on a
        ``pad * fov_px * oversampling`` raster and cropped, which keeps
        defocused rings from wrapping around.
    aberration
        Dict of named Zernike aberrations in waves RMS (see
        :data:`dino_autofocus.synth.optics.zernike.NAMED`).
    device
        ``"cpu"`` (numpy/scipy) or a torch device such as ``"cuda"``.  On a GPU
        the per-PSF work -- phase, ``exp``, the field FFTs and the OTF -- runs in
        torch and the OTFs stay on the device for :meth:`otf_t`; the pupil terms
        are still built once on the CPU, so both paths share one physics.
    gpu_dtype
        ``"complex128"`` matches the CPU path to rounding; ``"complex64"`` is
        faster and holds the PSF to ~1e-6 relative (the phase is always formed
        in double precision before the cast).
    """

    def __init__(
        self,
        system: ImagingSystem,
        fov_px: int = 256,
        oversampling: Optional[int] = None,
        pad: int = 2,
        model: PSFModel = "vectorial",
        dipole: Dipole = "free",
        aberration: Optional[Dict[str, float]] = None,
        apodization: bool = True,
        fresnel: bool = True,
        n_spectral: Optional[int] = None,
        saf: Literal["off", "decay"] = "off",
        clamp_saf: float = 20.0,
        workers: int = -1,
        cache_size: int = 16,
        device: str = "cpu",
        gpu_dtype: Literal["complex128", "complex64"] = "complex128",
    ) -> None:
        self.system = system
        self.device = str(device)
        self.gpu_dtype = gpu_dtype
        self.fov_px = int(fov_px)
        self.os = int(oversampling or system.oversampling())
        self.pad = int(pad)
        self.model = model
        self.dipole = dipole
        self.aberration = dict(aberration or {})
        self.apodization = apodization
        self.fresnel = fresnel
        self.saf = saf
        self.clamp_saf = float(clamp_saf)
        self.workers = int(workers)

        ill = system.illumination
        self.n_spectral = int(n_spectral if n_spectral is not None else ill.n_spectral)

        self.dx = system.pixel_size_sample / self.os      # fine pixel, um
        self.n_fine = self.fov_px * self.os               # fine pixels kept
        self.n_grid = int(sfft.next_fast_len(self.n_fine * self.pad))

        self._grids: Dict[float, PupilGrid] = {}
        self._terms: Dict[float, PupilTerms] = {}
        # Bounded LRU.  Each entry is an n_grid^2 array (4 MB complex, 2 MB real
        # at n_grid = 512), and a single scene's label search touches ~100
        # distinct (defocus, depth) keys, each exactly once.  An unbounded cache
        # therefore buys nothing and costs hundreds of megabytes per process:
        # with 9 generation workers it drove this machine into swap and slowed
        # scene rendering from 3.0 to 9.1 s/scene.  Keep it small.
        self._cache: "OrderedDict[Tuple, np.ndarray]" = OrderedDict()
        self.cache_size = max(int(cache_size), 1)
        self.cache_hits = 0
        self.cache_misses = 0
        self._terms_t: Dict[float, Dict] = {}
        self._cache_t: "OrderedDict[Tuple, object]" = OrderedDict()

        g0 = self.grid(ill.wavelength)
        if not g0.resolves_pupil:
            raise ValueError(
                f"fine grid dx={self.dx:.4f} um cannot represent NA={system.objective.na}; "
                f"increase oversampling (need dx <= "
                f"{ill.wavelength / (2 * system.objective.na):.4f} um)"
            )

    # -- grids ------------------------------------------------------------
    def grid(self, wavelength: float) -> PupilGrid:
        key = round(wavelength, 9)
        g = self._grids.get(key)
        if g is None:
            g = PupilGrid(self.n_grid, self.dx, wavelength, self.system.objective.na)
            self._grids[key] = g
        return g

    def wavelengths(self) -> Tuple[np.ndarray, np.ndarray]:
        """Emission-band sample points and weights (Gauss--Hermite over a Gaussian)."""
        ill = self.system.illumination
        if self.n_spectral <= 1 or ill.bandwidth <= 0:
            return np.array([ill.wavelength]), np.array([1.0])
        sigma = ill.bandwidth / 2.3548200450309493   # FWHM -> sigma
        nodes, weights = np.polynomial.hermite_e.hermegauss(self.n_spectral)
        lam = ill.wavelength + sigma * nodes
        return lam, weights / weights.sum()

    # -- geometry limits ---------------------------------------------------
    @property
    def tan_alpha(self) -> float:
        """tan of the marginal ray angle in the immersion medium.

        The defocus parameter multiplies ``n_immersion * cos(theta_i)`` in the
        pupil phase, so the immersion -- not the sample -- sets the geometric
        blur.  ``Objective`` guarantees NA < n_immersion, so this is finite.
        """
        sin_a = self.effective_na / self.system.stack.n_immersion
        sin_a = min(sin_a, 0.999999)
        return float(sin_a / np.sqrt(1.0 - sin_a ** 2))

    def geometric_radius(self, defocus: float) -> float:
        """Radius of the geometric defocus blur in the sample plane, um."""
        return abs(float(defocus)) * self.tan_alpha

    def max_defocus(self, fill: float = 0.35) -> float:
        """Largest |defocus| whose blur still fits inside `fill` of the FOV."""
        fov_um = self.fov_px * self.system.pixel_size_sample
        return float(fill * fov_um / self.tan_alpha)

    def terms(self, wavelength: float) -> PupilTerms:
        """Cached defocus- and depth-independent pupil quantities."""
        key = round(float(wavelength), 9)
        hit = self._terms.get(key)
        if hit is not None:
            return hit
        g = self.grid(float(wavelength))
        st = self.system.stack
        support = self.support(g)
        apod = self._apodization(g, support)
        wf = (2.0 * np.pi * Z.wavefront(self.aberration, g.rho, g.phi, support)
              if self.aberration else np.zeros_like(g.f))
        const = np.real(
            st.n_glass * st.t_glass * g.cos_theta(st.n_glass)
            + st.n_immersion * st.t_immersion * g.cos_theta(st.n_immersion)
            - st.n_glass_design * st.t_glass_design * g.cos_theta(st.n_glass_design)
            - st.n_immersion_design * st.t_immersion_design
            * g.cos_theta(st.n_immersion_design)
        ).astype(np.complex128)
        out = PupilTerms(
            support=support, apodization=apod, wavefront=wf,
            depth_mode=st.n_sample * g.cos_theta(st.n_sample),
            defocus_mode=st.n_immersion * g.cos_theta(st.n_immersion),
            const_opd=const,
            polarisation=self._polarisation(g, support),
            k0=2.0 * np.pi / float(wavelength),
        )
        self._terms[key] = out
        return out

    def _polarisation(self, g: PupilGrid, support: np.ndarray) -> np.ndarray:
        """Dipole-to-Cartesian pupil factors, including Fresnel transmission."""
        st = self.system.stack
        if self.model in ("scalar", "gaussian"):
            return np.ones((1,) + g.f.shape, dtype=np.complex128)

        cos_s = g.cos_theta(st.n_sample)
        sin_s = g.sin_theta(st.n_sample).astype(np.complex128)
        cphi, sphi = np.cos(g.phi), np.sin(g.phi)

        if self.fresnel:
            ts1, tp1 = _fresnel_t(st.n_sample, st.n_glass, cos_s,
                                  g.cos_theta(st.n_glass))
            ts2, tp2 = _fresnel_t(st.n_glass, st.n_immersion,
                                  g.cos_theta(st.n_glass),
                                  g.cos_theta(st.n_immersion))
            t_s, t_p = ts1 * ts2, tp1 * tp2
        else:
            t_s = t_p = np.ones_like(cos_s)

        dipoles = ("x", "y", "z") if self.dipole == "free" else (self.dipole,)
        fields = []
        for d in dipoles:
            if d == "x":
                e_s, e_p = -t_s * sphi, t_p * cos_s * cphi
            elif d == "y":
                e_s, e_p = t_s * cphi, t_p * cos_s * sphi
            else:                                    # z dipole: p-polarised only
                e_s, e_p = np.zeros_like(cos_s), -t_p * sin_s
            # p maps to the radial pupil direction, s to the azimuthal one
            fields.append(e_p * cphi - e_s * sphi)
            fields.append(e_p * sphi + e_s * cphi)
        return np.stack(fields)

    # -- pupil construction ------------------------------------------------
    #: Largest permitted evanescent amplitude decay, in nepers.  exp(-80) is
    #: already ~1e-35, far below any numerically meaningful contribution, and
    #: clamping here is what keeps exp() from overflowing on grid points outside
    #: the pupil where sin(theta_sample) is huge.
    MAX_DECAY = 80.0

    def _phase(self, g: PupilGrid, defocus: float, depth: float,
               support: Optional[np.ndarray] = None) -> np.ndarray:
        """Stratified-media + defocus + Zernike phase, radians.

        Only evaluated on ``support``.  Outside the pupil ``sin(theta_sample)``
        grows without bound, so ``cos(theta_sample)`` becomes large and
        imaginary and ``exp(i * phase)`` overflows -- harmless once masked, but
        it produces inf and NaN intermediates whose disposal then depends on the
        order of the masking, which is not a property worth relying on.
        """
        st = self.system.stack
        k0 = 2.0 * np.pi / g.wavelength
        if support is None:
            support = self.support(g)

        cos_i = g.cos_theta(st.n_immersion)
        cos_g = g.cos_theta(st.n_glass)
        cos_s = g.cos_theta(st.n_sample)
        cos_id = g.cos_theta(st.n_immersion_design)
        cos_gd = g.cos_theta(st.n_glass_design)

        opd = (
            st.n_sample * depth * cos_s
            + st.n_glass * st.t_glass * cos_g
            + st.n_immersion * (st.t_immersion + defocus) * cos_i
            - st.n_glass_design * st.t_glass_design * cos_gd
            - st.n_immersion_design * st.t_immersion_design * cos_id
        )
        phase = np.where(support, k0 * opd, 0.0)
        # A positive imaginary OPD is an evanescent decay; clamp its depth so
        # the later exp() cannot overflow even for a grazing supercritical ray.
        decay = np.imag(phase)
        phase = np.real(phase) + 1j * np.clip(decay, -self.MAX_DECAY, self.MAX_DECAY)
        if self.aberration:
            w = Z.wavefront(self.aberration, g.rho, g.phi, support)
            phase = phase + 2.0 * np.pi * w
        return phase

    def support(self, g: PupilGrid) -> np.ndarray:
        """Pupil rays that actually contribute.

        With an oil objective on an aqueous sample the pupil extends past the
        critical angle (NA > n_sample).  Those supercritical rays only couple to
        emitters within a fraction of a wavelength of the coverglass, so for
        ordinary widefield imaging ``saf="off"`` discards them -- which is both
        faster and more accurate than keeping a near-singular weight.  Set
        ``saf="decay"`` for TIRF / SAF work, where the evanescent term in the
        propagation phase supplies the correct depth dependence.
        """
        if self.saf == "decay":
            return g.mask
        return g.mask & g.propagating(self.system.stack.n_sample)

    @property
    def effective_na(self) -> float:
        """NA actually used, after any supercritical rays are discarded."""
        if self.saf == "decay":
            return self.system.objective.na
        return min(self.system.objective.na, self.system.stack.n_sample)

    def _apodization(self, g: PupilGrid, support: np.ndarray) -> np.ndarray:
        st = self.system.stack
        if not self.apodization:
            return support.astype(np.complex128)
        cos_i = g.cos_theta(st.n_immersion)
        cos_s = g.cos_theta(st.n_sample)
        # 1/sqrt(cos_i): aplanatic (sine-condition) objective, collection side.
        # 1/cos_s: angular-spectrum (Weyl) weight of a dipole field in the sample.
        floor = 1.0 / self.clamp_saf
        with np.errstate(divide="ignore", invalid="ignore"):
            a = 1.0 / np.sqrt(np.where(support, cos_i, 1.0))
            safe = np.where(np.abs(cos_s) > floor, cos_s, floor)
            b = 1.0 / safe
        return np.where(support, a * b, 0.0)

    def _pupils(self, g: PupilGrid, defocus: float, depth: float) -> np.ndarray:
        """Pupil fields, shape (n_field, ny, nx).

        For the vectorial model the fields are the Cartesian (x, y) components
        produced by each contributing dipole orientation; their intensities add
        incoherently, which is what a freely rotating fluorophore does.

        Only the phase depends on ``defocus`` and ``depth``; everything else
        comes from :meth:`terms`.
        """
        t = self.terms(g.wavelength)
        opd = depth * t.depth_mode + defocus * t.defocus_mode + t.const_opd
        phase = np.where(t.support, t.k0 * opd, 0.0)
        # A positive imaginary OPD is an evanescent decay; clamp its depth so
        # the exp() below cannot overflow even for a grazing supercritical ray.
        phase = np.real(phase) + 1j * np.clip(np.imag(phase),
                                              -self.MAX_DECAY, self.MAX_DECAY)
        base = np.exp(1j * (phase + t.wavefront)) * t.apodization
        return t.polarisation * base[None, ...]

    # -- PSF evaluation ----------------------------------------------------
    def _psf_fine_single(self, g: PupilGrid, defocus: float, depth: float) -> np.ndarray:
        if self.model == "gaussian":
            return self._psf_gaussian(g, defocus)
        p = self._pupils(g, defocus, depth)
        e = sfft.fft2(p, axes=(-2, -1), workers=self.workers)
        inten = np.sum(np.abs(e) ** 2, axis=0)
        inten = sfft.fftshift(inten)
        # Parseval normalisation: unit energy over an infinite plane
        norm = (g.n ** 2) * float(np.sum(np.abs(p) ** 2))
        if norm <= 0:
            raise FloatingPointError("empty pupil")
        return inten / norm

    def _psf_gaussian(self, g: PupilGrid, defocus: float) -> np.ndarray:
        """Gaussian whose width follows the geometric + diffraction blur."""
        sys_ = self.system
        sigma0 = 0.21 * sys_.illumination.wavelength / sys_.objective.na
        sigma = np.sqrt(sigma0 ** 2 + (0.5 * self.geometric_radius(defocus)) ** 2)
        n = g.n
        c = n // 2
        y, x = np.mgrid[0:n, 0:n].astype(np.float64)
        r2 = ((x - c) * self.dx) ** 2 + ((y - c) * self.dx) ** 2
        out = np.exp(-0.5 * r2 / sigma ** 2)
        return out / out.sum()

    def psf_grid(self, defocus: float, depth: float = 0.0) -> np.ndarray:
        """Full padded-grid intensity PSF with its origin at pixel (0, 0).

        This is the layout an FFT convolution wants, so the renderer can use it
        without a shift.  Use :meth:`psf_fine` for anything you intend to look at.
        """
        key = ("grid", round(float(defocus), 6), round(float(depth), 6))
        hit = self._cache_get(key)
        if hit is not None:
            return hit
        lams, ws = self.wavelengths()
        acc = None
        for lam, w in zip(lams, ws):
            g = self.grid(float(lam))
            cur = w * self._psf_fine_single(g, float(defocus), float(depth))
            acc = cur if acc is None else acc + cur
        return self._cache_put(key, sfft.ifftshift(acc).astype(np.float64))

    def otf(self, defocus: float, depth: float = 0.0) -> np.ndarray:
        """Optical transfer function on the padded grid (FFT of :meth:`psf_grid`)."""
        key = ("otf", round(float(defocus), 6), round(float(depth), 6))
        hit = self._cache_get(key)
        if hit is not None:
            return hit
        return self._cache_put(
            key, sfft.fft2(self.psf_grid(defocus, depth), workers=self.workers))

    # -- GPU path ------------------------------------------------------------
    @property
    def on_gpu(self) -> bool:
        return self.device != "cpu"

    def _torch_terms(self, wavelength: float) -> Dict:
        """:meth:`terms` moved to the device, with ``k0`` and the support folded in."""
        import torch

        key = round(float(wavelength), 9)
        hit = self._terms_t.get(key)
        if hit is not None:
            return hit
        t = self.terms(wavelength)
        sup = t.support

        def dev(a, dtype=torch.complex128):
            return torch.as_tensor(np.ascontiguousarray(a), device=self.device).to(dtype)

        cd = getattr(torch, self.gpu_dtype)
        out = {
            # phase = depth * a_depth + defocus * a_defocus + a_const, zero off-support
            "a_depth": dev(np.where(sup, t.k0 * t.depth_mode, 0.0)),
            "a_defocus": dev(np.where(sup, t.k0 * t.defocus_mode, 0.0)),
            "a_const": dev(np.where(sup, t.k0 * t.const_opd, 0.0)),
            "wavefront": dev(t.wavefront, torch.float64),
            "apodization": dev(t.apodization),
            "polarisation": dev(t.polarisation, cd),
        }
        self._terms_t[key] = out
        return out

    def _psf_grid_torch(self, defocus: float, depth: float):
        """Device version of :meth:`psf_grid` (origin at pixel (0, 0))."""
        import torch

        if self.model == "gaussian":
            return torch.as_tensor(self.psf_grid(defocus, depth), device=self.device)
        cd = getattr(torch, self.gpu_dtype)
        lams, ws = self.wavelengths()
        acc = None
        for lam, w in zip(lams, ws):
            T = self._torch_terms(float(lam))
            phase = depth * T["a_depth"] + defocus * T["a_defocus"] + T["a_const"]
            decay = phase.imag.clamp(-self.MAX_DECAY, self.MAX_DECAY)
            # exp(1j * (re + 1j * decay + wavefront)) = exp(-decay) * exp(1j * (re + wf))
            base = torch.polar(torch.exp(-decay), phase.real + T["wavefront"]) * T["apodization"]
            p = T["polarisation"] * base.to(cd)[None]
            e = torch.fft.fft2(p)
            inten = (e.real ** 2 + e.imag ** 2).sum(0)
            norm = (self.n_grid ** 2) * float((p.real ** 2 + p.imag ** 2).sum())
            if norm <= 0:
                raise FloatingPointError("empty pupil")
            cur = (float(w) / norm) * inten
            acc = cur if acc is None else acc + cur
        # the CPU path applies fftshift then ifftshift, which cancel
        return acc

    def otf_t(self, defocus: float, depth: float = 0.0):
        """:meth:`otf` as a device tensor, cached on the device."""
        import torch

        key = ("otf", round(float(defocus), 6), round(float(depth), 6))
        hit = self._cache_t.get(key)
        if hit is not None:
            self._cache_t.move_to_end(key)
            self.cache_hits += 1
            return hit
        self.cache_misses += 1
        val = torch.fft.fft2(self._psf_grid_torch(float(defocus), float(depth)))
        self._cache_t[key] = val
        while len(self._cache_t) > self.cache_size:
            self._cache_t.popitem(last=False)
        return val

    def best_focus(self, depth: float, span: Optional[float] = None,
                   coarse: int = 25, refine: int = 3) -> float:
        """Defocus value that maximises peak intensity for an emitter at `depth`.

        With an index-mismatched stack the sharpest plane is *not* at
        ``defocus = 0``: it shifts by roughly ``-1.3 * depth`` for oil-into-water.
        Labels must be referenced to this, otherwise every depth in the sample
        carries a different systematic offset.
        """
        st = self.system.stack
        # paraxial focal-shift estimate brackets the search
        guess = -depth * st.n_immersion / max(st.n_sample, 1e-6)
        if span is None:
            span = max(0.6 * abs(guess), 4.0 * self.system.depth_of_field)
        lo, hi = guess - span, guess + span
        for _ in range(refine):
            zs = np.linspace(lo, hi, coarse)
            pk = np.array([self.peak_intensity(float(z), depth) for z in zs])
            j = int(pk.argmax())
            step = zs[1] - zs[0]
            lo, hi = zs[max(j - 1, 0)], zs[min(j + 1, coarse - 1)]
            if hi - lo < 1e-4:
                break
        # parabolic interpolation on the final triple
        zs = np.linspace(lo, hi, 5)
        pk = np.array([self.peak_intensity(float(z), depth) for z in zs])
        j = int(pk.argmax())
        if 0 < j < len(zs) - 1:
            y0, y1, y2 = pk[j - 1], pk[j], pk[j + 1]
            den = y0 - 2 * y1 + y2
            if abs(den) > 1e-30:
                return float(zs[j] - 0.5 * (zs[1] - zs[0]) * (y2 - y0) / den)
        return float(zs[j])

    def _crop(self, a: np.ndarray) -> np.ndarray:
        n, m = self.n_grid, self.n_fine
        s = (n - m) // 2
        return a[s:s + m, s:s + m]

    def _cache_get(self, key: Tuple) -> Optional[np.ndarray]:
        hit = self._cache.get(key)
        if hit is None:
            self.cache_misses += 1
            return None
        self._cache.move_to_end(key)
        self.cache_hits += 1
        return hit

    def _cache_put(self, key: Tuple, value: np.ndarray) -> np.ndarray:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return value

    def psf_fine(self, defocus: float, depth: float = 0.0) -> np.ndarray:
        """Intensity PSF on the fine raster, shape (n_fine, n_fine)."""
        key = ("fine", round(float(defocus), 6), round(float(depth), 6))
        hit = self._cache_get(key)
        if hit is not None:
            return hit
        lams, ws = self.wavelengths()
        acc = None
        for lam, w in zip(lams, ws):
            g = self.grid(float(lam))
            cur = w * self._psf_fine_single(g, float(defocus), float(depth))
            acc = cur if acc is None else acc + cur
        return self._cache_put(key, self._crop(acc).astype(np.float64))

    def psf_camera(self, defocus: float, depth: float = 0.0) -> np.ndarray:
        """Intensity PSF binned onto camera pixels, shape (fov_px, fov_px)."""
        fine = self.psf_fine(defocus, depth)
        k = self.os
        return fine.reshape(self.fov_px, k, self.fov_px, k).sum(axis=(1, 3))

    def stack_fine(self, defocus: Sequence[float], depth: float = 0.0) -> np.ndarray:
        return np.stack([self.psf_fine(z, depth) for z in defocus])

    def stack_camera(self, defocus: Sequence[float], depth: float = 0.0) -> np.ndarray:
        return np.stack([self.psf_camera(z, depth) for z in defocus])

    # -- diagnostics -------------------------------------------------------
    def encircled_energy(self, defocus: float, depth: float = 0.0) -> float:
        return float(self.psf_fine(defocus, depth).sum())

    def peak_intensity(self, defocus: float, depth: float = 0.0) -> float:
        return float(self.psf_fine(defocus, depth).max())

    def clear_cache(self) -> None:
        self._cache.clear()
        self._cache_t.clear()

    def cache_bytes(self) -> int:
        return int(sum(v.nbytes for v in self._cache.values()))

    def cache_stats(self) -> Dict[str, float]:
        total = self.cache_hits + self.cache_misses
        return {"entries": len(self._cache), "megabytes": self.cache_bytes() / 1e6,
                "hits": self.cache_hits, "misses": self.cache_misses,
                "hit_rate": self.cache_hits / total if total else 0.0}

    def __repr__(self) -> str:
        return (
            f"PSFEngine(model={self.model}, na={self.system.objective.na}, "
            f"fov={self.fov_px}px, os={self.os}, grid={self.n_grid}, dx={self.dx:.4f}um)"
        )
