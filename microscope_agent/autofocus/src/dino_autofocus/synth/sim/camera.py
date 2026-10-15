"""Sensor model: photons in, ADU out.

The chain is the usual one for a scientific camera, in the order the physics
happens:

    photoelectrons  = Poisson(signal + background) * QE   (shot noise)
    + dark current  = Poisson(dark_rate * exposure)
    * PRNU          (pixel-to-pixel response non-uniformity, fixed pattern)
    * EM gain       (optional, stochastic -- EMCCD excess noise)
    + read noise    (Gaussian in electrons)
    -> ADU          = electrons / gain + offset, quantised and clipped

Two details matter for autofocus specifically and are easy to get wrong:

*Saturation*.  An in-focus image concentrates the same photons into fewer
pixels, so the sharpest plane is the one most likely to clip.  A clipped peak
destroys exactly the high-frequency content a focus metric is looking for, and a
model trained without clipping will confidently mis-rank the in-focus frame.

*Fixed-pattern noise*.  PRNU and hot pixels do not move when the stage does, so
a network can learn them as landmarks if every training image shares one
pattern.  The pattern is therefore re-drawn per field of view unless a fixed
seed is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from ..optics.system import Camera


@dataclass
class SensorPattern:
    """Fixed-pattern artefacts that stay put while the stage moves."""

    prnu: np.ndarray            # multiplicative gain map, mean 1
    hot: np.ndarray             # boolean hot-pixel mask
    hot_rate: np.ndarray        # extra dark current at hot pixels, e-/s

    @staticmethod
    def draw(cam: Camera, shape: Tuple[int, int], rng: np.random.Generator) -> "SensorPattern":
        prnu = 1.0 + cam.prnu * rng.standard_normal(shape)
        hot = rng.random(shape) < cam.hot_pixel_rate
        rate = np.zeros(shape)
        if hot.any():
            rate[hot] = rng.exponential(scale=200.0, size=int(hot.sum()))
        return SensorPattern(prnu.astype(np.float32), hot, rate.astype(np.float32))


class Sensor:
    """Applies a camera model to noiseless photon-flux images."""

    def __init__(self, cam: Camera, shape: Tuple[int, int],
                 rng: Optional[np.random.Generator] = None,
                 pattern: Optional[SensorPattern] = None) -> None:
        self.cam = cam
        self.shape = tuple(shape)
        self.rng = rng if rng is not None else np.random.default_rng()
        self.pattern = pattern if pattern is not None else SensorPattern.draw(cam, self.shape, self.rng)

    # -- forward model -----------------------------------------------------
    def expose(
        self,
        photons: np.ndarray,
        exposure: float,
        background: float = 0.0,
        return_electrons: bool = False,
    ) -> np.ndarray:
        """Expose one frame.

        Parameters
        ----------
        photons
            Incident photon *rate* per pixel, photons/s, noiseless.
        exposure
            Integration time, s.
        background
            Additional uniform photon rate per pixel, photons/s.
        """
        cam = self.cam
        rng = self.rng
        if photons.shape != self.shape:
            raise ValueError(f"photons shape {photons.shape} != sensor shape {self.shape}")

        incident = np.clip(photons + background, 0.0, None) * exposure
        # Shot noise is on the photons; QE then converts to photoelectrons.
        # Binomial detection of Poisson photons is itself Poisson(QE * mean),
        # so one Poisson draw at the detected rate is exact, not an approximation.
        e = rng.poisson(incident * cam.qe).astype(np.float64)

        dark_rate = cam.dark_current + self.pattern.hot_rate
        e += rng.poisson(dark_rate * exposure)

        e *= self.pattern.prnu

        if cam.em_gain > 1.0:
            e = self._em_register(e, cam.em_gain)

        if cam.read_noise > 0.0:
            e += rng.normal(0.0, cam.read_noise, size=self.shape)

        # Well saturation happens in electrons, before the ADC.
        e = np.clip(e, None, cam.full_well)

        if return_electrons:
            return e

        adu = e / cam.gain + cam.offset
        adu = np.clip(np.floor(adu), 0.0, cam.adu_max)
        return adu.astype(np.uint16 if cam.bit_depth <= 16 else np.uint32)

    def _em_register(self, e: np.ndarray, gain: float) -> np.ndarray:
        """EMCCD multiplication register: Gamma-distributed output per input e-.

        For n input electrons the output is Gamma(shape=n, scale=gain), which is
        the standard high-gain limit and reproduces the factor-of-sqrt(2) excess
        noise that makes EMCCD images look grainier than their photon count.
        """
        out = np.zeros_like(e)
        m = e > 0
        if m.any():
            out[m] = self.rng.gamma(shape=e[m], scale=gain)
        return out

    # -- inverse / calibration --------------------------------------------
    def to_photoelectrons(self, adu: np.ndarray) -> np.ndarray:
        """Convert ADU back to electrons using the nominal calibration."""
        return (np.asarray(adu, dtype=np.float64) - self.cam.offset) * self.cam.gain

    def saturated_fraction(self, adu: np.ndarray) -> float:
        return float(np.mean(np.asarray(adu) >= self.cam.adu_max - 0.5))

    def clipped_in_well(self, photons: np.ndarray, exposure: float,
                        background: float = 0.0) -> float:
        """Fraction of pixels that would saturate the well, noise-free."""
        e = (photons + background) * exposure * self.cam.qe
        return float(np.mean(e >= self.cam.full_well))

    # -- signal quality ----------------------------------------------------
    def snr(self, photons: np.ndarray, exposure: float, background: float = 0.0) -> float:
        """Peak-pixel SNR of the noiseless flux under this camera."""
        cam = self.cam
        sig = float(np.max(photons)) * exposure * cam.qe
        bg = background * exposure * cam.qe + cam.dark_current * exposure
        noise = np.sqrt(max(sig + bg, 1e-12) + cam.read_noise ** 2)
        return float(sig / noise)


def auto_exposure(
    photons: np.ndarray,
    cam: Camera,
    target_fill: float = 0.5,
    max_exposure: float = 1.0,
    min_exposure: float = 1e-4,
) -> float:
    """Exposure that puts the bright tail of the image at `target_fill` of full well.

    Uses the 99.9th percentile rather than the maximum so a single hot emitter
    does not force the whole frame into the noise.
    """
    ref = float(np.percentile(photons, 99.9))
    if ref <= 0:
        return max_exposure
    t = target_fill * cam.full_well / (ref * cam.qe)
    return float(np.clip(t, min_exposure, max_exposure))
