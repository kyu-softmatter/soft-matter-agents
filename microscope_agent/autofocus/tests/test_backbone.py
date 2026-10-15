import numpy as np
import pytest

# the ml extra (T-035d): a core-only environment skips this module instead of failing at
# collection; the backbone itself imports torch, so the skip comes before it
torch = pytest.importorskip("torch")

from dino_autofocus.backbone import (  # noqa: E402
    ALLOWED_BACKBONES,
    IMAGENET_MEAN,
    IMAGENET_STD,
    DinoExtractor,
    robust_unit,
    to_dino_batch,
)


def test_robust_unit_maps_median_to_0_and_p995_to_1():
    rng = np.random.default_rng(0)
    img = rng.integers(100, 4000, size=(64, 64)).astype(np.uint16)
    u = robust_unit(img)
    assert u.dtype == np.float32
    assert u.min() == 0.0 and u.max() == 1.0
    assert np.isclose(np.mean(u == 0.0), 0.5, atol=0.02)


def test_robust_unit_flat_frame_is_finite():
    assert np.all(robust_unit(np.full((28, 28), 500, np.uint16)) == 0.0)


def test_batch_shape_and_imagenet_normalisation():
    frames = np.zeros((2, 28, 42), np.uint16)
    x = to_dino_batch(frames)
    assert x.shape == (2, 3, 28, 42)
    expected = -torch.tensor(IMAGENET_MEAN) / torch.tensor(IMAGENET_STD)
    assert torch.allclose(x[0, :, 0, 0], expected)


def test_non_multiple_of_patch_is_refused_unless_resized():
    frames = np.zeros((1, 30, 30), np.uint16)
    with pytest.raises(ValueError, match="multiple of 14"):
        to_dino_batch(frames)
    assert to_dino_batch(frames, size=28).shape == (1, 3, 28, 28)


def test_only_plain_dinov2_backbones_load(tmp_path):
    """Refused before the clone is even looked at (audit L4: no noncommercial Cell-DINO)."""
    assert {"dinov2_vits14", "dinov2_vitb14", "dinov2_vits14_reg"} <= ALLOWED_BACKBONES
    for name in ("cell_dino_vitl14", "xray_dino_vitl16", "dinov2_vits14_lc", "../evil"):
        with pytest.raises(ValueError, match="not allowed"):
            DinoExtractor(name, repo=tmp_path)
