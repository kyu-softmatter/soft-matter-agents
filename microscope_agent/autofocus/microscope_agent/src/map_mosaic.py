# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/src/map_mosaic.py
# body-sha256: cf68b394daeabf54926cb8fac579b56c2d027ea8de85aab960e807454b4ac884
"""4x mosaic and classical particle candidates (WP-I, T-032), pure numpy.

Nothing here talks to a backend. The engine's ``sample_map`` operation calls it on
scan_4x tile outputs; the server renders the saved mosaic for the map screen.

Stage <-> image mapping is ``map_geometry`` (``stage = t + inv(M) @ (centre - p)``).

The mosaic is stored in **stage orientation**: column index grows with stage x, row index
grows with stage y, row 0 is the lowest y (draw it with origin "lower"). Each tile is binned,
then flipped and, if the camera is turned by about 90 degrees, transposed, so that only the
signs and the axis order of inv(M) are used (as the bench plot script does). The rotation
left over (about 0.1 degree on the bench) is recorded in `rotation_ignored_deg`.

Mosaic pixel (col, row) covers stage x in [x0 + col * s, x0 + (col + 1) * s) with
s = `um_per_px` of the mosaic; `stage_to_mosaic` / `mosaic_to_stage` use pixel centres.
Overlapping tiles are averaged. Pixels no tile covers are 0 (camera frames never are: the
offset is ~100 ADU).

Candidates are found on the full-resolution tiles (a 9/30 particle is ~4 px wide at 4x, gone
after 8x binning): background removed, a Laplacian-of-Gaussian blob response, local maxima
above `min_snr` times the response's robust noise, line-like maxima (the hole edge) dropped
by the Hessian eigenvalue ratio. They are candidates only (`source: "classical_candidate"`,
`grade: "computed"`); a person confirms them (PLAN F4).

The Gaussian, Laplacian-of-Gaussian and maximum filters are numpy ports of
``scipy.ndimage``'s (mode "reflect", truncate 4, the same kernels and the same order of
operations: bit-identical results); the soft-matter-agents ``mic`` environment has no scipy.

Flat file in the soft-matter-agents layout (integration-sma.md section 9): stdlib +
numpy only, siblings loaded by path. The engine's ``mosaic`` module re-exports it and adds
``mosaic_from_scan`` (which names the objective through the engine's guards).
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name: str, filename: str):
    """A sibling file by path, the soft-matter-agents idiom (no package, no relative import).
    A name already loaded is reused, so every importer shares one module object."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_geometry = _load("_mic_map_geometry", "map_geometry.py")
um_per_px = _geometry.um_per_px
tile_pixel_to_stage = _geometry.tile_pixel_to_stage
stage_to_tile_pixel = _geometry.stage_to_tile_pixel

GRADE_COMPUTED = "computed"  # the engine's records.GRADE_COMPUTED
BIN = 8  # plot_scan.py
ORIENTATION = "stage"
CANDIDATE_SOURCE = "classical_candidate"
# The bench 4x calibration a sample without one falls back to is the caller's
# (dino-autofocus keeps it in its bench_values module).


# ---------------------------------------------------------------- tile orientation
@dataclass(frozen=True)
class Orientation:
    """How a camera frame becomes stage-oriented: transpose first, then flip."""

    transpose: bool
    flip_cols: bool
    flip_rows: bool
    rotation_ignored_deg: float

    @classmethod
    def of(cls, M: Any) -> Orientation:
        A = np.linalg.inv(np.asarray(M, float))  # stage um per pixel; stage = t + A (c - p)
        # d stage / d col = -A[:, 0], d stage / d row = -A[:, 1]
        transpose = abs(A[0, 0]) < abs(A[1, 0])  # image columns run mostly along stage y
        if transpose:
            A = A[:, ::-1]  # after the transpose, columns are the old rows
        flip_cols = -A[0, 0] < 0  # mosaic columns must grow with stage x
        flip_rows = -A[1, 1] < 0  # mosaic rows must grow with stage y
        sx = -A[0, 0] * (-1 if flip_cols else 1)
        rot = math.degrees(math.atan2(-A[1, 0] * (-1 if flip_cols else 1), sx))
        return cls(bool(transpose), bool(flip_cols), bool(flip_rows), rot)

    def apply(self, img: np.ndarray) -> np.ndarray:
        if self.transpose:
            img = img.T
        if self.flip_cols:
            img = img[:, ::-1]
        if self.flip_rows:
            img = img[::-1]
        return img


def bin_image(img: np.ndarray, b: int) -> np.ndarray:
    h, w = (img.shape[0] // b) * b, (img.shape[1] // b) * b
    return img[:h, :w].reshape(h // b, b, w // b, b).mean(axis=(1, 3), dtype=np.float64)


# ---------------------------------------------------------------- the mosaic
@dataclass
class MosaicMeta:
    x0: float
    x1: float
    y0: float
    y1: float
    um_per_px: float  # of the mosaic (camera um/px x bin)
    bin: int
    M_px_per_um: list[list[float]]
    objective: str
    n_tiles: int
    tile_shape: list[int]  # camera frame (rows, cols)
    orientation: str = ORIENTATION
    transpose: bool = False
    flip_cols: bool = False
    flip_rows: bool = False
    rotation_ignored_deg: float = 0.0
    calibration_source: str = ""
    shape: list[int] = field(default_factory=list)  # mosaic (rows, cols)
    empty_value: float = 0.0
    tiles: list[dict] = field(default_factory=list)  # name, x_um, y_um, col0, row0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> MosaicMeta:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


def stage_to_mosaic(meta: MosaicMeta, x_um: float, y_um: float) -> tuple[float, float]:
    """Mosaic (col, row) of stage (x, y), in pixel-centre coordinates."""
    s = meta.um_per_px
    return (x_um - meta.x0) / s - 0.5, (y_um - meta.y0) / s - 0.5


def mosaic_to_stage(meta: MosaicMeta, col: float, row: float) -> tuple[float, float]:
    s = meta.um_per_px
    return meta.x0 + (col + 0.5) * s, meta.y0 + (row + 0.5) * s


@dataclass
class Tile:
    name: str
    x_um: float  # stage readback at the tile centre
    y_um: float
    image: np.ndarray


def build_mosaic(tiles: Sequence[Tile], M: Any, *, objective: str = "4x", bin: int = BIN,
                 calibration_source: str = "") -> tuple[np.ndarray, MosaicMeta]:
    """Bin, orient and place every tile at its stage centre; overlaps are averaged."""
    if not tiles:
        raise ValueError("no tiles to build a mosaic from")
    M = np.asarray(M, float)
    ori = Orientation.of(M)
    s = um_per_px(M) * bin
    shape = tiles[0].image.shape
    small = [ori.apply(bin_image(np.asarray(t.image, float), bin)) for t in tiles]
    hs, ws = small[0].shape
    half_x, half_y = ws * s / 2, hs * s / 2
    xs = [t.x_um for t in tiles]
    ys = [t.y_um for t in tiles]
    x0, x1 = min(xs) - half_x, max(xs) + half_x
    y0, y1 = min(ys) - half_y, max(ys) + half_y
    W, H = int(math.ceil((x1 - x0) / s)), int(math.ceil((y1 - y0) / s))
    acc = np.zeros((H, W), np.float64)
    cnt = np.zeros((H, W), np.int32)
    placed = []
    for t, img in zip(tiles, small, strict=True):
        if img.shape != (hs, ws):
            raise ValueError(f"tile {t.name} has shape {t.image.shape}, expected {shape}")
        c0 = int(round((t.x_um - x0) / s - ws / 2))
        r0 = int(round((t.y_um - y0) / s - hs / 2))
        cs, rs = max(c0, 0), max(r0, 0)
        ce, re = min(c0 + ws, W), min(r0 + hs, H)
        acc[rs:re, cs:ce] += img[rs - r0:re - r0, cs - c0:ce - c0]
        cnt[rs:re, cs:ce] += 1
        placed.append({"name": t.name, "x_um": t.x_um, "y_um": t.y_um, "col0": c0, "row0": r0})
    mosaic = np.where(cnt > 0, acc / np.maximum(cnt, 1), 0.0).astype(np.float32)
    meta = MosaicMeta(x0=x0, x1=x0 + W * s, y0=y0, y1=y0 + H * s, um_per_px=s, bin=bin,
                      M_px_per_um=M.tolist(), objective=objective, n_tiles=len(tiles),
                      tile_shape=[int(shape[0]), int(shape[1])], transpose=ori.transpose,
                      flip_cols=ori.flip_cols, flip_rows=ori.flip_rows,
                      rotation_ignored_deg=round(ori.rotation_ignored_deg, 3),
                      calibration_source=calibration_source, shape=[H, W], tiles=placed)
    return mosaic, meta


def calibration_for(sample_json: Path | None, objective: str = "4x", *,
                    fallback_m: Sequence[Sequence[float]] | None = None,
                    fallback_source: str = "caller fallback") -> tuple[list, str]:
    """M from the sample's stage_camera_calibration for this objective, else the caller's
    fallback; no fallback means no calibration (an error, never a guess)."""
    if sample_json is not None and sample_json.exists():
        cal = json.loads(sample_json.read_text(encoding="utf-8")).get("stage_camera_calibration")
        if cal and cal.get("M_px_per_um") and cal.get("objective", objective) == objective:
            return cal["M_px_per_um"], "sample stage_camera_calibration"
    if fallback_m is None:
        raise ValueError(f"no calibration for {objective!r} in the sample and no fallback given")
    return [[float(v) for v in r] for r in fallback_m], fallback_source


def load_scan_tiles(scan_dir: Path) -> tuple[dict, list[Tile]]:
    """scan.json and the tile .npy files of a scan_4x / sample_map record folder."""
    rec = json.loads((scan_dir / "scan.json").read_text(encoding="utf-8"))
    tiles = [Tile(t["name"], float(t["x_um"]), float(t["y_um"]),
                  np.load(scan_dir / f"{t['name']}.npy")) for t in rec["tiles"]]
    return rec, tiles


def save_mosaic(folder: Path, mosaic: np.ndarray, meta: MosaicMeta) -> tuple[Path, Path]:
    np.save(folder / "mosaic.npy", mosaic)
    (folder / "mosaic.json").write_text(json.dumps(meta.to_dict(), indent=1), encoding="utf-8")
    return folder / "mosaic.npy", folder / "mosaic.json"


def load_mosaic(folder: Path) -> tuple[np.ndarray, MosaicMeta]:
    meta = MosaicMeta.from_dict(json.loads((folder / "mosaic.json").read_text(encoding="utf-8")))
    return np.load(folder / "mosaic.npy"), meta


# ---------------------------------------------------------------- filters (scipy.ndimage)
TRUNCATE = 4.0  # scipy.ndimage's default: the kernel reaches 4 sigma
_CHUNK = 16  # columns per block in _correlate: keeps the block in cache


def _gaussian_kernel(sigma: float, order: int) -> np.ndarray:
    """scipy.ndimage._filters._gaussian_kernel1d at radius int(4 sigma + 0.5), line by line
    (the same float operations, so the same bits)."""
    radius = int(TRUNCATE * float(sigma) + 0.5)
    exponent_range = np.arange(order + 1)
    sigma2 = sigma * sigma
    x = np.arange(-radius, radius + 1)
    phi_x = np.exp(-0.5 / sigma2 * x ** 2)
    phi_x = phi_x / phi_x.sum()
    if order == 0:
        return phi_x
    q = np.zeros(order + 1)
    q[0] = 1
    D = np.diag(exponent_range[1:], 1)  # D @ q(x) = q'(x)
    P = np.diag(np.ones(order) / -sigma2, -1)  # P @ q(x) = q(x) * p'(x)
    Q_deriv = D + P
    for _ in range(order):
        q = Q_deriv.dot(q)
    q = (x[:, None] ** exponent_range).dot(q)
    return q * phi_x


def _correlate(a: np.ndarray, w: np.ndarray, axis: int) -> np.ndarray:
    """1-D correlation of a 2-D float64 array along `axis` with a symmetric kernel `w`, mode
    "reflect" (d c b a | a b c d | d c b a). The order of operations is ndimage's symmetric
    loop: x[i] w[0], then += (x[i - j] + x[i + j]) w[j] for j from the outermost in."""
    r = len(w) // 2
    a = np.moveaxis(np.asarray(a, np.float64), axis, 0)
    n, m = a.shape
    padded = np.pad(a, ((r, r), (0, 0)), mode="symmetric")
    out = np.empty((n, m))
    for c0 in range(0, m, _CHUNK):
        p = np.ascontiguousarray(padded[:, c0:c0 + _CHUNK])
        o = p[r:r + n] * w[r]
        t = np.empty_like(o)
        for j in range(r, 0, -1):
            np.add(p[r - j:r - j + n], p[r + j:r + j + n], out=t)
            t *= w[r - j]
            o += t
        out[:, c0:c0 + _CHUNK] = o
    return np.moveaxis(out, 0, axis)


def gaussian_filter(a: np.ndarray, sigma: float, orders: tuple[int, int] = (0, 0)) -> np.ndarray:
    """scipy.ndimage.gaussian_filter(a, sigma, orders, mode="reflect") for a 2-D array;
    orders 0 (smoothing) or 2 (second derivative) per axis."""
    out = np.asarray(a, np.float64)
    for axis, order in enumerate(orders):
        if order not in (0, 2):
            raise ValueError(f"derivative order {order} is not 0 or 2")
        out = _correlate(out, _gaussian_kernel(sigma, order)[::-1], axis)
    return out


def gaussian_laplace(a: np.ndarray, sigma: float) -> np.ndarray:
    """scipy.ndimage.gaussian_laplace(a, sigma, mode="reflect") for a 2-D array."""
    return gaussian_filter(a, sigma, (2, 0)) + gaussian_filter(a, sigma, (0, 2))


def maximum_filter(a: np.ndarray, size: int) -> np.ndarray:
    """scipy.ndimage.maximum_filter(a, size=size, mode="reflect") for a 2-D array, odd size."""
    if size % 2 != 1:
        raise ValueError(f"size {size} must be odd")
    r = size // 2
    out = np.asarray(a)
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        p = np.moveaxis(np.pad(out, pad, mode="symmetric"), axis, 0)
        n = out.shape[axis]
        m = p[0:n].copy()
        for k in range(1, size):
            np.maximum(m, p[k:k + n], out=m)
        out = np.moveaxis(m, 0, axis)
    return out


# ---------------------------------------------------------------- candidates
@dataclass(frozen=True)
class CandidateParams:
    polarity: str = "dark"  # "dark": shadows in brightfield; "bright": Aura fluorescence
    sigma_px: float = 1.5  # ~ particle radius / sqrt(2) at 4x (9/30: ~4 px FWHM)
    background_sigma_px: float = 25.0
    min_snr: float = 6.0
    min_blob_ratio: float = 0.3  # |smaller| / |larger| Hessian eigenvalue; a line is ~0
    border_px: int = 8
    max_per_tile: int = 500
    merge_um: float = 10.0  # the same particle seen in two overlapping tiles


DEFAULT_CANDIDATES = CandidateParams()


def detect_blobs(img: np.ndarray, p: CandidateParams = DEFAULT_CANDIDATES) -> list[dict]:
    """Blob maxima in one frame: [{col, row, snr, response}], strongest first."""
    if p.polarity not in ("dark", "bright"):
        raise ValueError(f"polarity {p.polarity!r} is not 'dark' or 'bright'")
    a = np.asarray(img, np.float64)
    a = a - gaussian_filter(a, p.background_sigma_px)
    if p.polarity == "dark":
        a = -a
    sm = gaussian_filter(a, p.sigma_px)
    resp = -gaussian_laplace(a, p.sigma_px) * p.sigma_px**2
    noise = 1.4826 * float(np.median(np.abs(resp - np.median(resp))))
    if noise <= 0:
        return []
    size = max(3, int(2 * round(2 * p.sigma_px) + 1))
    peaks = (resp == maximum_filter(resp, size)) & (resp > p.min_snr * noise)
    b = p.border_px
    peaks[:b], peaks[-b:], peaks[:, :b], peaks[:, -b:] = False, False, False, False
    rows, cols = np.nonzero(peaks)
    if not len(rows):
        return []
    # Hessian of the smoothed image at each peak: a blob curves both ways, a line one way
    gy, gx = np.gradient(sm)
    hyy, hyx = np.gradient(gy)
    hxy, hxx = np.gradient(gx)
    out = []
    for r, c in zip(rows, cols, strict=True):
        H = np.array([[hxx[r, c], hxy[r, c]], [hyx[r, c], hyy[r, c]]])
        ev = np.linalg.eigvalsh(0.5 * (H + H.T))
        big = max(abs(ev[0]), abs(ev[1]))
        ratio = 0.0 if big == 0 else min(abs(ev[0]), abs(ev[1])) / big
        if ratio < p.min_blob_ratio or not (ev < 0).all():
            continue
        out.append({"col": float(c), "row": float(r), "snr": float(resp[r, c] / noise),
                    "response": float(resp[r, c]), "blob_ratio": float(ratio)})
    out.sort(key=lambda d: -d["snr"])
    return out[:p.max_per_tile]


def find_candidates(tiles: Iterable[Tile], M: Any, p: CandidateParams = DEFAULT_CANDIDATES, *,
                    hole: dict | None = None, hole_margin_um: float = 100.0,
                    detect: Callable[[np.ndarray, CandidateParams], list[dict]] | None = None
                    ) -> list[dict]:
    """Candidates in stage coordinates over all tiles, merged across overlaps.

    With a `hole` fit ({centre_um, diameter_mm}) only points at least `hole_margin_um`
    inside the hole are kept, so the edge and the spacer give none. `detect(img, p)` is the
    per-tile detection (default `detect_blobs`)."""
    detect = detect_blobs if detect is None else detect
    found: list[dict] = []
    for t in tiles:
        for b in detect(t.image, p):
            x, y = tile_pixel_to_stage(M, (t.x_um, t.y_um), b["col"], b["row"], t.image.shape)
            if hole is not None:
                r = float(hole["diameter_mm"]) * 500.0 - hole_margin_um
                if math.hypot(x - hole["centre_um"][0], y - hole["centre_um"][1]) > r:
                    continue
            found.append({"x_um": round(x, 2), "y_um": round(y, 2), "score": round(b["snr"], 2),
                          "tile": t.name, "px": [b["col"], b["row"]],
                          "blob_ratio": round(b["blob_ratio"], 3)})
    found.sort(key=lambda d: -d["score"])
    kept: list[dict] = []
    for f in found:  # strongest first; a weaker twin within merge_um is the same particle
        if all(math.hypot(f["x_um"] - k["x_um"], f["y_um"] - k["y_um"]) > p.merge_um
               for k in kept):
            kept.append(f)
    method = {"detector": "LoG blob, Hessian ratio", **asdict(p)}
    return [{**k, "source": CANDIDATE_SOURCE, "grade": GRADE_COMPUTED, "method": method}
            for k in kept]
