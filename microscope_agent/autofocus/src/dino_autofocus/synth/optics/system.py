"""Optical system, immersion/sample stack and camera descriptions.

All lengths are in micrometres (um) unless a name says otherwise.
Angles are in radians. Wavelengths are vacuum wavelengths.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, replace
from typing import Dict, Optional
import math


@dataclass(frozen=True)
class Objective:
    """Aplanatic (sine-condition) infinity-corrected objective."""

    na: float                       # numerical aperture
    magnification: float            # nominal lateral magnification
    n_immersion: float = 1.0        # design immersion index (air=1.0, oil=1.518, water=1.333)
    tube_length: float = 200_000.0  # nominal tube lens focal length, um (Nikon 200 mm)
    working_distance: float = 300.0

    def __post_init__(self) -> None:
        if self.na <= 0:
            raise ValueError("na must be positive")
        if self.na >= self.n_immersion + 1e-9:
            raise ValueError(
                f"na={self.na} cannot exceed n_immersion={self.n_immersion}; "
                "the objective cannot collect beyond its immersion index"
            )
        if self.magnification <= 0:
            raise ValueError("magnification must be positive")

    @property
    def alpha(self) -> float:
        """Maximum collection half-angle inside the immersion medium."""
        return math.asin(min(self.na / self.n_immersion, 1.0 - 1e-12))

    @property
    def focal_length(self) -> float:
        return self.tube_length / self.magnification

    @property
    def pupil_radius(self) -> float:
        """Back-focal-plane radius, um (sine condition: r = f * n * sin(theta))."""
        return self.focal_length * self.na


@dataclass(frozen=True)
class SampleStack:
    """Refractive-index stack between the emitter and the objective.

    Layout, emitter -> objective:
        sample medium (n_sample, thickness = emitter depth)
        coverglass    (n_glass,  t_glass)
        immersion     (n_imm,    t_imm)

    The `*_design` values are what the objective was corrected for.  Any
    deviation from them produces depth-dependent spherical aberration, which is
    the dominant real-world cause of an asymmetric axial PSF -- and therefore of
    the sign information an autofocus network can exploit.
    """

    n_sample: float = 1.33
    n_glass: float = 1.515
    n_immersion: float = 1.0

    n_glass_design: float = 1.515
    n_immersion_design: float = 1.0

    t_glass: float = 170.0           # actual coverglass thickness, um
    t_glass_design: float = 170.0
    t_immersion: float = 100.0       # actual immersion working distance, um
    t_immersion_design: float = 100.0

    def matched(self) -> bool:
        return (
            abs(self.n_glass - self.n_glass_design) < 1e-9
            and abs(self.n_immersion - self.n_immersion_design) < 1e-9
            and abs(self.t_glass - self.t_glass_design) < 1e-9
            and abs(self.t_immersion - self.t_immersion_design) < 1e-9
        )


@dataclass(frozen=True)
class Camera:
    """Scientific camera / sensor model."""

    pixel_size: float = 6.5          # physical pixel pitch, um
    qe: float = 0.72                 # quantum efficiency at the emission band
    read_noise: float = 1.6          # e- rms
    dark_current: float = 0.3        # e-/px/s
    full_well: float = 30_000.0      # e-
    bit_depth: int = 16
    gain: float = 0.48               # e- per ADU  (sensitivity)
    offset: float = 100.0            # ADU baseline
    prnu: float = 0.005              # photo-response non-uniformity, fractional rms
    hot_pixel_rate: float = 2e-5
    em_gain: float = 1.0             # >1 selects an EMCCD-style stochastic gain
    binning: int = 1

    @property
    def adu_max(self) -> float:
        return float(2 ** self.bit_depth - 1)

    @property
    def effective_pixel_size(self) -> float:
        return self.pixel_size * self.binning


@dataclass(frozen=True)
class Illumination:
    """Fluorescence emission band and photon budget."""

    wavelength: float = 0.520        # centre emission wavelength, um
    bandwidth: float = 0.040         # FWHM of the emission filter, um
    n_spectral: int = 1              # >1 averages the PSF over the band
    exposure: float = 0.050          # s
    photons_per_emitter: float = 8_000.0   # detected-photon budget per emitter per second
    background: float = 40.0         # background photons/px/s (autofluorescence + stray)


@dataclass(frozen=True)
class ImagingSystem:
    """Everything needed to render one synthetic field of view."""

    objective: Objective
    camera: Camera = field(default_factory=Camera)
    stack: SampleStack = field(default_factory=SampleStack)
    illumination: Illumination = field(default_factory=Illumination)
    name: str = "system"

    # ---- derived sampling quantities -------------------------------------
    @property
    def pixel_size_sample(self) -> float:
        """Camera pixel pitch back-projected into the sample plane, um."""
        return self.camera.effective_pixel_size / self.objective.magnification

    @property
    def abbe_resolution(self) -> float:
        """Lateral (Abbe) resolution limit, um."""
        return self.illumination.wavelength / (2.0 * self.objective.na)

    @property
    def depth_of_field(self) -> float:
        """Diffraction-limited depth of field, um (Berek/Nyquist style estimate).

        dof ~= n * lambda / NA^2 ; this is the natural scale for the autofocus
        tolerance and for choosing z-scan step sizes.
        """
        n = self.stack.n_immersion
        return n * self.illumination.wavelength / (self.objective.na ** 2)

    @property
    def nyquist_pixel_size(self) -> float:
        """Sample-plane pixel size that critically samples the *intensity* PSF."""
        return self.illumination.wavelength / (4.0 * self.objective.na)

    @property
    def sampling_ratio(self) -> float:
        """<1 means the camera oversamples the PSF, >1 means it is undersampled."""
        return self.pixel_size_sample / self.nyquist_pixel_size

    def oversampling(self, max_factor: int = 8) -> int:
        """Integer factor by which the PSF must be computed finer than the camera."""
        need = self.pixel_size_sample / self.nyquist_pixel_size
        return int(min(max(1, math.ceil(need)), max_factor))

    def describe(self) -> Dict[str, float]:
        return {
            "na": self.objective.na,
            "magnification": self.objective.magnification,
            "pixel_size_sample_um": self.pixel_size_sample,
            "abbe_resolution_um": self.abbe_resolution,
            "depth_of_field_um": self.depth_of_field,
            "nyquist_pixel_um": self.nyquist_pixel_size,
            "sampling_ratio": self.sampling_ratio,
            "oversampling": self.oversampling(),
            "ri_matched": self.stack.matched(),
        }

    def to_dict(self) -> Dict:
        return asdict(self)

    def evolve(self, **kw) -> "ImagingSystem":
        return replace(self, **kw)


# ---------------------------------------------------------------------------
# A few real-world presets.
# ---------------------------------------------------------------------------

def preset(name: str) -> ImagingSystem:
    name = name.lower()
    if name in ("10x_air", "10x"):
        return ImagingSystem(
            name="10x/0.30 air",
            objective=Objective(na=0.30, magnification=10.0, n_immersion=1.0),
            stack=SampleStack(n_sample=1.33, n_immersion=1.0, n_immersion_design=1.0),
            camera=Camera(pixel_size=6.5),
        )
    if name in ("20x_air", "20x"):
        return ImagingSystem(
            name="20x/0.75 air",
            objective=Objective(na=0.75, magnification=20.0, n_immersion=1.0),
            stack=SampleStack(n_sample=1.33, n_immersion=1.0, n_immersion_design=1.0),
            camera=Camera(pixel_size=6.5),
        )
    if name in ("40x_water", "40x"):
        return ImagingSystem(
            name="40x/1.15 water",
            objective=Objective(na=1.15, magnification=40.0, n_immersion=1.333),
            stack=SampleStack(n_sample=1.33, n_immersion=1.333, n_immersion_design=1.333),
            camera=Camera(pixel_size=6.5),
        )
    if name in ("60x_oil", "60x"):
        return ImagingSystem(
            name="60x/1.40 oil",
            objective=Objective(na=1.40, magnification=60.0, n_immersion=1.518),
            stack=SampleStack(
                n_sample=1.33, n_immersion=1.518, n_immersion_design=1.518,
                n_glass=1.515, n_glass_design=1.515,
            ),
            camera=Camera(pixel_size=6.5, qe=0.80, read_noise=1.4),
        )
    if name in ("100x_oil", "100x"):
        return ImagingSystem(
            name="100x/1.45 oil TIRF",
            objective=Objective(na=1.45, magnification=100.0, n_immersion=1.518),
            stack=SampleStack(n_sample=1.33, n_immersion=1.518, n_immersion_design=1.518),
            camera=Camera(pixel_size=11.0, qe=0.95, read_noise=1.0),
        )
    raise KeyError(f"unknown preset {name!r}")


PRESETS = ("10x_air", "20x_air", "40x_water", "60x_oil", "100x_oil")
