"""select_tiles picks the sample, not the background, and avoids saturated windows."""

import numpy as np
import pytest

pytest.importorskip("torch")  # the ml extra (T-035d): live imports the backbone

from dino_autofocus.live import select_tiles  # noqa: E402


def frame_with_patches(where, size=2400, seed=0):
    rng = np.random.default_rng(seed)
    img = rng.normal(100, 2, (size, size)).clip(0, 65535)
    for y, x, amp in where:
        img[y : y + 150, x : x + 150] += amp
    return img.astype(np.uint16)


def test_picks_the_bright_regions_and_does_not_overlap():
    img = frame_with_patches([(300, 400, 500), (1500, 1800, 800), (2000, 200, 300)])
    tiles = select_tiles(img, k=3)
    assert len(tiles) == 3
    expected = [(1500, 1800), (300, 400), (2000, 200)]  # brightest first
    for (y, x), t in zip(expected, tiles, strict=True):
        oy = max(0, min(y + 150, t.y0 + 224) - max(y, t.y0))
        ox = max(0, min(x + 150, t.x0 + 224) - max(x, t.x0))
        assert oy * ox >= 0.5 * 150 * 150  # the tile holds most of its patch
    for a in tiles:
        for b in tiles:
            if a is not b:
                assert abs(a.y0 - b.y0) >= 224 or abs(a.x0 - b.x0) >= 224


def test_saturated_window_is_skipped():
    img = frame_with_patches([(300, 400, 500)])
    img[1000:1100, 1000:1100] = 65535
    tiles = select_tiles(img, k=1)
    assert abs(tiles[0].y0 - 300) < 224 and abs(tiles[0].x0 - 400) < 224


def test_blank_frame_gives_no_tiles():
    img = np.full((2400, 2400), 100, np.uint16)
    assert select_tiles(img, k=4) == []
