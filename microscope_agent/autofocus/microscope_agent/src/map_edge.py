# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/src/map_edge.py
# body-sha256: 8f9a22d29fbe6b6b420123c99f4d97189c7f0441efd0ea236fd3aeb377812a5e
"""Chamber edge detection and the hole circle fit, pure numpy (the detection half of
the engine's ``edge_trace`` operation, a port of the 2026-09-30 edge-tracking script).

Image vectors are (x, y) = (column, row) in full-resolution pixels; ``find_edge`` returns the
boundary point nearest the field centre and its normal (dark -> bright). Mapping it to the
stage (``stage + inv(M) @ (centre - p)``) and moving along it is the tracer's job, not this
file's: nothing here moves anything.

``hole_fit`` turns boundary points (stage um) into the sample.json ``hole`` fields with a
Kasa circle, refitted without outliers (``robust_circle``).

Flat file in the soft-matter-agents layout (integration-sma.md section 9): stdlib +
numpy only (``remove_small_regions`` labels regions with its own 4-neighbour run union;
scipy.ndimage.label gave the same regions). ``edge_trace`` re-exports these names.
"""

from __future__ import annotations

import math

import numpy as np


# ---------------------------------------------------------------- image helpers (ported)
def block_mean(img: np.ndarray, b: int) -> np.ndarray:
    h, w = (img.shape[0] // b) * b, (img.shape[1] // b) * b
    return img[:h, :w].reshape(h // b, b, w // b, b).mean(axis=(1, 3), dtype=np.float64)


def gaussian(a: np.ndarray, sigma: float) -> np.ndarray:
    r = max(1, int(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    p = np.pad(a, r, mode="reflect")
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 0, p)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 1, p)


def phase_shift(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, float]:
    """Shift (x, y) in pixels of b relative to a (b(x) ~ a(x - shift)), and peak sharpness."""
    win = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    fa = np.fft.rfft2((a - a.mean()) * win)
    fb = np.fft.rfft2((b - b.mean()) * win)
    r = np.conj(fa) * fb
    c = np.fft.irfft2(r / np.maximum(np.abs(r), 1e-12), s=a.shape)
    iy, ix = np.unravel_index(np.argmax(c), c.shape)

    def sub(cm: float, c0: float, cp: float) -> float:  # parabolic sub-pixel peak
        d = cm - 2 * c0 + cp
        return 0.0 if abs(d) < 1e-12 else 0.5 * (cm - cp) / d

    dy = sub(c[iy - 1, ix], c[iy, ix], c[(iy + 1) % c.shape[0], ix])
    dx = sub(c[iy, ix - 1], c[iy, ix], c[iy, (ix + 1) % c.shape[1]])
    sy = iy + dy if iy <= c.shape[0] // 2 else iy + dy - c.shape[0]
    sx = ix + dx if ix <= c.shape[1] // 2 else ix + dx - c.shape[1]
    sharp = float(c.max() / max(np.abs(c).mean(), 1e-12))
    return np.array([sx, sy]), sharp


def otsu(v: np.ndarray) -> float:
    hist, edges = np.histogram(v, bins=256)
    p = hist / max(hist.sum(), 1)
    mids = 0.5 * (edges[:-1] + edges[1:])
    w0 = np.cumsum(p)
    m0 = np.cumsum(p * mids)
    mt = m0[-1]
    between = (mt * w0 - m0) ** 2 / np.maximum(w0 * (1 - w0), 1e-12)
    return float(mids[np.argmax(between)])


def _runs(row: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Start and end (exclusive) columns of the True runs of a 1-D bool array."""
    d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def _small_region_runs(mask: np.ndarray, min_area: int) -> list[tuple[int, int, int]]:
    """(row, start, end) of the runs of the 4-connected True regions smaller than
    `min_area` pixels. Runs on neighbouring rows that share a column are one region."""
    runs: list[tuple[int, int, int]] = []
    parent: list[int] = []

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    prev: list[int] = []  # run indices on the row above
    for r in range(mask.shape[0]):
        starts, ends = _runs(mask[r])
        cur = []
        k = 0
        for s, e in zip(starts.tolist(), ends.tolist(), strict=True):
            i = len(runs)
            runs.append((r, s, e))
            parent.append(i)
            cur.append(i)
            while k < len(prev) and runs[prev[k]][2] <= s:
                k += 1  # runs above that end before this one starts
            q = k
            while q < len(prev) and runs[prev[q]][1] < e:
                a, b = root(prev[q]), root(i)
                if a != b:
                    parent[b] = a
                q += 1
        prev = cur
    area: dict[int, int] = {}
    for i, (_, s, e) in enumerate(runs):
        ri = root(i)
        area[ri] = area.get(ri, 0) + e - s
    return [runs[i] for i in range(len(runs)) if area[root(i)] < min_area]


def remove_small_regions(mask: np.ndarray, min_area: int) -> np.ndarray:
    """Flip connected regions (4-neighbour, either value) smaller than `min_area` blocks.

    Debris and bubbles are small closed blobs; the chamber's two sides are large. The script
    used a Python flood fill; this labels rows of runs and joins runs that touch (the same
    4-neighbour regions as scipy.ndimage.label, which the engine used before)."""
    mask = np.asarray(mask, bool)
    out = mask.copy()
    for value in (True, False):
        for r, s, e in _small_region_runs(mask == value, min_area):
            out[r, s:e] = not value
    return out


def find_edge(img: np.ndarray, block: int | None = None, sigma: float = 2.0,
              min_contrast: float = 8.0, prefer_n: np.ndarray | None = None,
              min_blob_px: float = 0.0) -> dict | None:
    """Nearest boundary point to the centre and its normal (dark -> bright), or None.

    Returns dict(p=(x, y) full-res px, n=unit normal (x, y), contrast): the boundary between
    the two brightness populations Otsu finds in the smoothed block-mean image, placed where
    the smoothed profile crosses the threshold. Blocks default to ~150 across the frame."""
    block = block or max(1, min(img.shape) // 150)
    m = block_mean(img, block)
    s = gaussian(m, sigma)
    noise = 1.4826 * np.median(np.abs(m - s))
    thr = otsu(s)
    hi, lo = s[s > thr], s[s <= thr]
    if hi.size < 0.03 * s.size or lo.size < 0.03 * s.size:
        return None
    contrast = (hi.mean() - lo.mean()) / max(noise / math.sqrt(2 * sigma**2 * math.pi), 1e-6)
    if contrast < min_contrast:
        return None
    mask = s > thr
    if min_blob_px > 0:  # blobs smaller than (min_blob)^2 are debris, not the chamber
        mask = remove_small_regions(mask, int((min_blob_px / block) ** 2))
    pts = []
    vy, vx = np.nonzero(mask[:-1, :] != mask[1:, :])
    f = np.clip((thr - s[vy, vx]) / (s[vy + 1, vx] - s[vy, vx] + 1e-12), 0, 1)
    pts.append(np.column_stack([vx + 0.5, vy + 0.5 + f]))
    hy, hx = np.nonzero(mask[:, :-1] != mask[:, 1:])
    f = np.clip((thr - s[hy, hx]) / (s[hy, hx + 1] - s[hy, hx] + 1e-12), 0, 1)
    pts.append(np.column_stack([hx + 0.5 + f, hy + 0.5]))
    pts = np.vstack(pts)
    if len(pts) < 5:
        return None
    c = np.array([s.shape[1] / 2, s.shape[0] / 2])
    gy, gx = np.gradient(s)
    d2 = ((pts - c) ** 2).sum(1)
    if prefer_n is not None:  # ignore boundaries facing the other way (debris, bubbles)
        iy = np.clip(pts[:, 1].astype(int), 0, s.shape[0] - 1)
        ix = np.clip(pts[:, 0].astype(int), 0, s.shape[1] - 1)
        g = np.column_stack([gx[iy, ix], gy[iy, ix]])
        cos = (g @ prefer_n) / np.maximum(np.linalg.norm(g, axis=1), 1e-12)
        d2 = np.where(cos > 0.5, d2, np.inf)
        if not np.isfinite(d2).any():
            return None
    i = int(np.argmin(d2))
    near = ((pts - pts[i]) ** 2).sum(1) <= 36  # average the normal over ~6 blocks
    iy = np.clip(pts[near, 1].astype(int), 0, s.shape[0] - 1)
    ix = np.clip(pts[near, 0].astype(int), 0, s.shape[1] - 1)
    g = np.array([gx[iy, ix].mean(), gy[iy, ix].mean()])
    if np.linalg.norm(g) < 1e-9:
        return None
    return {"p": pts[i] * block, "n": g / np.linalg.norm(g), "contrast": float(contrast)}


def kasa_circle(points: np.ndarray) -> tuple[np.ndarray, float]:
    """Least-squares circle (Kasa): centre (x, y) and radius, same units as the points."""
    b = np.asarray(points, float)
    A = np.column_stack([2 * b[:, 0], 2 * b[:, 1], np.ones(len(b))])
    (cx, cy, c0), *_ = np.linalg.lstsq(A, (b**2).sum(1), rcond=None)
    return np.array([cx, cy]), float(np.sqrt(max(c0 + cx**2 + cy**2, 0.0)))


def fixed_radius_centre(points: np.ndarray, r: float, init: np.ndarray) -> np.ndarray:
    """Centre of a circle of known radius through the points (Gauss-Newton)."""
    b = np.asarray(points, float)
    c = np.asarray(init, float).copy()
    for _ in range(30):
        v = c - b
        d = np.maximum(np.hypot(v[:, 0], v[:, 1]), 1e-9)
        J = v / d[:, None]  # d(|c - p|)/dc
        step, *_ = np.linalg.lstsq(J, -(d - r), rcond=None)
        c += step
        if np.linalg.norm(step) < 1e-3:
            break
    return c


def arc_degrees(points: np.ndarray, c: np.ndarray) -> float:
    a = np.unwrap(np.arctan2(points[:, 1] - c[1], points[:, 0] - c[0]))
    return float(np.degrees(a.max() - a.min()))


def robust_circle(points: np.ndarray, floor: float = 150.0,
                  rounds: int = 3) -> tuple[np.ndarray, float, np.ndarray]:
    """Kasa fit, then drop points off it by > max(3 MAD, floor) and refit. (centre, r, kept)."""
    b = np.asarray(points, float)
    keep = np.ones(len(b), bool)
    for _ in range(rounds):
        c, r = kasa_circle(b[keep])
        res = np.abs(np.hypot(*(b - c).T) - r)
        cut = max(3 * 1.4826 * np.median(res[keep]), floor)
        new = res <= cut
        if new.sum() < 6 or (new == keep).all():
            break
        keep = new
    c, r = kasa_circle(b[keep])
    return c, r, keep


def hole_fit(points: np.ndarray) -> dict | None:
    """sample.json `hole` from the boundary points (stage um), or None under 6 points."""
    b = np.asarray(points, float)
    if len(b) < 6:
        return None
    c, r, keep = robust_circle(b)
    kept = b[keep]
    rms = float(np.sqrt(np.mean((np.hypot(*(kept - c).T) - r) ** 2)))
    return {"centre_um": [round(float(c[0]), 1), round(float(c[1]), 1)],
            "diameter_mm": round(2 * r / 1000, 4), "fit_rms_um": round(rms, 1),
            "n_points": int(len(kept)), "arc_deg": round(arc_degrees(kept, c), 1)}
