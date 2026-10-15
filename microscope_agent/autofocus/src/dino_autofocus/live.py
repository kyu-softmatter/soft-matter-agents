"""Live focus score: bright 224-px tiles of a full frame -> frozen DINO -> trained heads.

The heads (scripts/train_head.py) were trained on 224 x 224 synthetic frames at the
instrument's own pixel size, so a live frame is cut into 224-px tiles at native resolution
rather than resized -- resizing would change the apparent blur, which is the measurement.

Tiles are chosen by background-subtracted *integrated* intensity, not peak brightness:
defocus spreads photons but (in fluorescence) does not remove them, so the integral picks
where the sample is without preferring tiles that already happen to be in focus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .backbone import DinoExtractor
from .focus.head import NpzHead


@dataclass
class Tile:
    y0: int
    x0: int
    signal: float
    dz: float = float("nan")
    sigma: float = float("nan")
    p_valid: float = float("nan")


@dataclass
class FocusReading:
    score: float | None  # DoF, dz = stage - best focus; None when nothing is readable
    sigma: float | None
    n_used: int
    tiles: list[Tile] = field(default_factory=list)
    where: str = "frame"  # "box": read inside the preferred region; "frame": whole frame

    @property
    def sign_known(self) -> bool:
        return self.score is not None and self.sigma is not None and abs(self.score) > self.sigma


BLOCK = 16  # tile (224) and stride (112) are multiples of it


def select_tiles(img: np.ndarray, k: int = 4, tile: int = 224, stride: int = 112,
                 saturated: int = 65535, min_snr: float = 3.0,
                 region: tuple[int, int, int] | None = None) -> list[Tile]:
    """Up to k non-overlapping tiles with the most background-subtracted signal.

    Works on 16 x 16 block means (150 x 150 for the full sensor): window sums need only
    block resolution, and float64 sums over 1e4 blocks stay exact where a float32 integral
    image over 5.8e6 pixels does not. A window counts as sample only if its excess over the
    background is `min_snr` times what block-mean noise alone would give.

    `region=(y0, x0, size)` keeps only windows lying wholly inside that square, searched on
    a one-block stride so that, e.g., 2 x 2 tiles fit a 518-px box.
    """
    b = BLOCK
    h, w = (img.shape[0] // b) * b, (img.shape[1] // b) * b
    blocks = img[:h, :w].reshape(h // b, b, w // b, b)
    m = blocks.mean(axis=(1, 3), dtype=np.float64)
    sat = (blocks >= saturated).mean(axis=(1, 3))
    bg = np.median(m)
    noise = 1.4826 * np.median(np.abs(m - bg))  # robust spread of block means
    a = np.clip(m - bg, 0, None)
    tb, sb = tile // b, stride // b
    ii = np.pad(a, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    si = np.pad(sat, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    if region is None:
        ys = np.arange(0, a.shape[0] - tb + 1, sb)
        xs = np.arange(0, a.shape[1] - tb + 1, sb)
    else:
        ry, rx, rs = region
        ys = np.arange(-(-ry // b), (ry + rs) // b - tb + 1)  # wholly inside, 1-block stride
        xs = np.arange(-(-rx // b), (rx + rs) // b - tb + 1)
        if ys.size == 0 or xs.size == 0:
            return []
    Y, X = np.meshgrid(ys, xs, indexing="ij")

    def wsum(q):
        return q[Y + tb, X + tb] - q[Y, X + tb] - q[Y + tb, X] + q[Y, X]

    s, sat_frac = wsum(ii), wsum(si) / (tb * tb)
    floor = min_snr * max(noise, 1e-3) * tb  # ~ sqrt(n_blocks) * noise per block, n = tb^2
    s[(sat_frac > 0.001) | (s < floor)] = -1  # clipped or empty windows: nothing to read
    order = np.argsort(s, axis=None)[::-1]
    chosen: list[Tile] = []
    for idx in order:
        if len(chosen) == k or s.flat[idx] <= 0:
            break
        y0, x0 = int(Y.flat[idx]) * b, int(X.flat[idx]) * b
        if all(abs(y0 - t.y0) >= tile or abs(x0 - t.x0) >= tile for t in chosen):
            chosen.append(Tile(y0, x0, float(s.flat[idx]) * b * b))
    return chosen


class FocusScorer:
    def __init__(self, head_path: str | Path, k_tiles: int = 4, saturated: int = 65535):
        self.saturated = saturated  # the camera's own clip level: 4095 in a 12-bit readout
        head_path = Path(head_path)
        if not head_path.is_file():
            raise FileNotFoundError(head_path)
        if head_path.suffix != ".npz":  # a joblib pickle runs code when loaded
            raise ValueError(f"{head_path}: heads load from .npz only; convert a head you "
                             f"trained with scripts/export_head_npz.py")
        self.head = NpzHead.load(head_path)
        if self.head["uses_signal"]:
            raise NotImplementedError("head needs the photon-signal scalar; camera gain unmeasured")
        self.tile = int(self.head["tile_px"])
        self.k = k_tiles
        self.dino = DinoExtractor(self.head["backbone"], self.head["n_layers"])

    def __call__(self, img: np.ndarray, region: tuple[int, int, int] | None = None) -> FocusReading:
        """Score `img`; with `region`, read inside it first and use the whole frame only if
        nothing in the region is readable."""
        if region is not None:
            r = self._read(img, select_tiles(img, self.k, self.tile, saturated=self.saturated,
                                             region=region))
            if r.score is not None:
                r.where = "box"
                return r
            r2 = self._read(img, select_tiles(img, self.k, self.tile, saturated=self.saturated))
            r2.where = "frame (box empty)"
            return r2
        return self._read(img, select_tiles(img, self.k, self.tile, saturated=self.saturated))

    def _read(self, img: np.ndarray, tiles: list[Tile]) -> FocusReading:
        if not tiles:
            return FocusReading(None, None, 0, [])
        crops = np.stack([img[t.y0:t.y0 + self.tile, t.x0:t.x0 + self.tile] for t in tiles])
        X = self.dino(crops, batch=len(crops))
        h = self.head
        dz = h.dz(X)
        sigma = h["sigma_scale"] * np.exp(h.log_err(X))
        pv = h.p_valid(X)
        for t, a, b, c in zip(tiles, dz, sigma, pv, strict=True):  # one prediction per tile
            t.dz, t.sigma, t.p_valid = float(a), float(b), float(c)
        use = [t for t in tiles if t.p_valid >= 0.5]
        if not use:
            return FocusReading(None, None, 0, tiles)
        w = np.array([t.p_valid / t.sigma**2 for t in use])
        v = np.array([t.dz for t in use])
        o = np.argsort(v)
        cw = np.cumsum(w[o]) / w.sum()
        score = float(v[o][np.searchsorted(cw, 0.5)])  # weighted median: one odd tile can't drag it
        # tiles share optics: don't divide by sqrt(n)
        sig = float(np.median([t.sigma for t in use]))
        return FocusReading(score, sig, len(use), tiles)
