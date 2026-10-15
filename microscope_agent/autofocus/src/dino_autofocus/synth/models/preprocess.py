"""Frame preprocessing, shared by training and inference.

Kept in one module on purpose.  A defocus regressor is unusually sensitive to
its normalisation: get it even slightly different at inference time and the
apparent blur scale changes, which is precisely the quantity being measured.
The most common way to ruin a model like this is to normalise with dataset
statistics during training and per-image statistics at deployment.

Normalisation here is strictly **per image and robust**: subtract the median,
divide by a high-percentile spread.  Two reasons:

* A real microscope's absolute brightness is not reproducible -- lamp ageing,
  filter choice, labelling density and exposure all move it by orders of
  magnitude.  Any dependence on absolute scale is a dependence on something
  that will not transfer.
* Discarding the absolute scale would also discard the SNR, which the model
  needs in order to report a calibrated uncertainty.  So the scale is not
  thrown away, it is handed over separately as a conditioning scalar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from ..sim.dataset import COND_NAMES

#: Conditioning scalars are mapped to roughly zero mean and unit spread with
#: fixed constants rather than dataset statistics, so the transform is identical
#: for any dataset and for live frames.
COND_SCALE: Dict[str, Tuple[float, float]] = {
    "na": (0.8, 0.5),
    "wavelength_um": (0.55, 0.1),
    "pixel_size_um": (0.25, 0.2),
    "dof_um": (1.5, 1.5),
    "log10_signal": (2.0, 1.5),
}


def normalise_image(img: np.ndarray, eps: float = 1e-6) -> Tuple[np.ndarray, float, float]:
    """Robust per-image normalisation.  Returns (normalised, offset, scale)."""
    a = np.asarray(img, dtype=np.float32)
    lo = float(np.median(a))
    hi = float(np.percentile(a, 99.5))
    scale = max(hi - lo, eps)
    return (a - lo) / scale, lo, scale


def normalise_cond(cond: np.ndarray, names: Sequence[str] = COND_NAMES) -> np.ndarray:
    c = np.asarray(cond, dtype=np.float32).copy()
    if c.ndim == 1:
        c = c[None, :]
    for i, n in enumerate(names):
        mu, sd = COND_SCALE.get(n, (0.0, 1.0))
        c[:, i] = (c[:, i] - mu) / sd
    return c


def cond_from_system(system, signal_photons: float) -> np.ndarray:
    """Build the conditioning vector for a live frame from known optics."""
    return normalise_cond(np.array([[
        system.objective.na,
        system.illumination.wavelength,
        system.pixel_size_sample,
        system.depth_of_field,
        np.log10(max(signal_photons, 1e-6)),
    ]], dtype=np.float32))


# ---------------------------------------------------------------------------
# augmentation
# ---------------------------------------------------------------------------

@dataclass
class AugmentConfig:
    """Augmentations that leave the defocus label untouched.

    Lateral flips and 90-degree rotations are safe: defocus is an axial
    quantity and the label is invariant under in-plane symmetries.  Note this is
    *not* true of an axial flip, which would invert the label's sign -- so it is
    deliberately absent, and it is also why the network can learn sign at all.

    ``extra_noise`` adds Poisson-like noise on top of what the camera model
    already produced.  It stands in for sample autofluorescence variability and
    stops the model from reading the exact synthetic noise spectrum as a cue.
    """

    flip: bool = True
    rot90: bool = True
    crop: float = 0.0            # fractional random crop, 0 disables
    extra_noise: float = 0.0     # relative std added to the normalised image
    intensity_jitter: float = 0.1
    gamma_jitter: float = 0.0    # simulates uncalibrated display/detector response


def augment(img: np.ndarray, rng: np.random.Generator,
            cfg: Optional[AugmentConfig] = None) -> np.ndarray:
    cfg = cfg or AugmentConfig()
    a = img
    if cfg.crop > 0:
        h, w = a.shape[-2:]
        ch, cw = int(h * (1 - cfg.crop)), int(w * (1 - cfg.crop))
        y0 = int(rng.integers(0, h - ch + 1)); x0 = int(rng.integers(0, w - cw + 1))
        a = a[..., y0:y0 + ch, x0:x0 + cw]
    if cfg.flip:
        if rng.random() < 0.5:
            a = a[..., ::-1]
        if rng.random() < 0.5:
            a = a[..., ::-1, :]
    if cfg.rot90:
        k = int(rng.integers(0, 4))
        if k:
            a = np.rot90(a, k, axes=(-2, -1))
    a = np.ascontiguousarray(a)
    if cfg.intensity_jitter > 0:
        a = a * float(np.exp(rng.normal(0.0, cfg.intensity_jitter)))
    if cfg.gamma_jitter > 0:
        g = float(np.exp(rng.normal(0.0, cfg.gamma_jitter)))
        a = np.sign(a) * np.abs(a) ** g
    if cfg.extra_noise > 0:
        a = a + rng.normal(0.0, cfg.extra_noise, size=a.shape).astype(a.dtype)
    return a


def resize(img: np.ndarray, size: int) -> np.ndarray:
    """Area-average resize to a square, used to hit the backbone's input size.

    Area averaging rather than subsampling: subsampling an undersampled PSF
    aliases the very high-frequency content that encodes focus.
    """
    h, w = img.shape[-2:]
    if h == size and w == size:
        return img
    import torch
    import torch.nn.functional as F
    t = torch.as_tensor(np.ascontiguousarray(img), dtype=torch.float32)
    while t.ndim < 4:
        t = t[None]
    mode = "area" if (h > size and w > size) else "bilinear"
    kw = {} if mode == "area" else {"align_corners": False}
    out = F.interpolate(t, size=(size, size), mode=mode, **kw)
    return out.squeeze(0).squeeze(0).numpy() if img.ndim == 2 else out.squeeze(0).numpy()
