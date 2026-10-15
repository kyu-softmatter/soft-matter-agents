"""Frozen DINOv2 backbone and the mono-uint16 -> DINO input transform.

The backbone code is loaded from a local clone of facebookresearch/dinov2 so the
exact commit is fixed (``torch.hub.load(..., source="local")``); a plain
``torch.hub.load("facebookresearch/dinov2", ...)`` would pull whatever main is.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

#: Commit the results in this repo were produced with.
DINOV2_COMMIT = "7764ea0f912e53c92e82eb78a2a1631e92725fc8"
DEFAULT_REPO = Path(os.environ.get("DINOV2_REPO", Path(__file__).parents[3] / "dinov2"))
#: Backbones that may be loaded: the plain DINOv2 ViTs (Apache-2.0), with or without registers.
#: The pinned clone also exports Cell-DINO / X-Ray DINO entries under a noncommercial licence;
#: the name comes from a head file, so a head must not be able to pick those (audit L4).
ALLOWED_BACKBONES = frozenset(
    f"dinov2_vit{size}14{reg}" for size in "sblg" for reg in ("", "_reg")
)

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
PATCH = 14


def repo_commit(repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True
        )
    except OSError:
        return None
    return out.stdout.strip() or None


def robust_unit(img: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """(img - median) / (p99.5 - median), clipped to [0, 1].

    Same offset/scale as psf-autofocus ``normalise_image`` so both pipelines see
    the same frame; the clip turns it into a display-like image for DINO.
    """
    a = np.asarray(img, dtype=np.float32)
    lo = float(np.median(a))
    hi = float(np.percentile(a, 99.5))
    return np.clip((a - lo) / max(hi - lo, eps), 0.0, 1.0)


def to_dino_batch(images: np.ndarray, size: int | None = None) -> torch.Tensor:
    """(N, H, W) mono frames -> (N, 3, S, S) ImageNet-normalised float tensor.

    H and W must be multiples of the 14 px patch unless ``size`` is given, in
    which case frames are resized (bilinear) to ``size`` x ``size``.
    """
    x = torch.from_numpy(np.stack([robust_unit(im) for im in images]))[:, None]
    if size is not None and x.shape[-2:] != (size, size):
        x = torch.nn.functional.interpolate(x, size=(size, size), mode="bilinear", antialias=True)
    if x.shape[-1] % PATCH or x.shape[-2] % PATCH:
        raise ValueError(f"frame {tuple(x.shape[-2:])} is not a multiple of {PATCH} px")
    x = x.expand(-1, 3, -1, -1)
    mean = torch.tensor(IMAGENET_MEAN).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD).view(1, 3, 1, 1)
    return (x - mean) / std


@dataclass
class DinoExtractor:
    """Frozen DINOv2; returns [CLS | mean patch token] from the last ``n_layers`` blocks."""

    name: str = "dinov2_vits14"
    n_layers: int = 1
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    #: On by default for the microscope PC (RTX A4000, tensor cores); heads in
    #: models/heads were trained on fp16 features. On GPUs without tensor cores pass
    #: fp16=False: on a GTX 1650 SUPER autocast fp16 ran ~4x slower than fp32
    #: (scripts/bench_latency.py). Features differ by up to ~0.02 between the two, so
    #: extract with the same setting a head was trained with.
    fp16: bool = True
    repo: Path = DEFAULT_REPO

    def __post_init__(self) -> None:
        if self.name not in ALLOWED_BACKBONES:
            raise ValueError(f"backbone {self.name!r} is not allowed; use one of "
                             f"{sorted(ALLOWED_BACKBONES)}")
        os.environ.setdefault("XFORMERS_DISABLED", "1")
        commit = repo_commit(self.repo)
        if commit != DINOV2_COMMIT:
            raise RuntimeError(
                f"dinov2 clone at {self.repo} is at {commit}, expected {DINOV2_COMMIT}"
            )
        self.model = torch.hub.load(str(self.repo), self.name, source="local")
        self.model.to(self.device).eval().requires_grad_(False)

    @property
    def dim(self) -> int:
        return 2 * self.n_layers * self.model.embed_dim

    @torch.no_grad()
    def __call__(self, images: np.ndarray, batch: int = 32, size: int | None = None) -> np.ndarray:
        out = []
        for i in range(0, len(images), batch):
            x = to_dino_batch(images[i : i + batch], size).to(self.device)
            with torch.autocast(self.device, dtype=torch.float16, enabled=self.fp16):
                layers = self.model.get_intermediate_layers(
                    x, n=self.n_layers, return_class_token=True
                )
            feats = [torch.cat([cls, patch.mean(1)], 1) for patch, cls in layers]
            out.append(torch.cat(feats, 1).float().cpu().numpy())
        return np.concatenate(out)
