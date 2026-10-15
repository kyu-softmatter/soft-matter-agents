"""Offline check of edge_track on a simulated stage and a simulated 6 mm hole.

    python scripts/sim_edge_track.py

The fake camera is rotated 90 degrees and mirrored relative to the stage, so the
calibration has something to find. Pass criteria: calibration recovers the pixel size
and the mapping, the run closes the loop, and the circle fitted to the edge points
recovers the hole's centre and diameter.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from edge_track import EdgeTracker  # noqa: E402

PX_UM, N = 6.5, 600  # 3.9 mm field like the 4x on the full sensor, at a quarter the pixels
HOLE_C, HOLE_R = np.array([1200.0, -800.0]), 3000.0
# stage (um) -> image (px): rotate 90 degrees and mirror, then scale
M_TRUE = np.array([[0.0, 1.0], [1.0, 0.0]]) / PX_UM


def random_texture(seed=1, step_um=10.0, half_um=9000.0):
    """Smooth random sample texture fixed to the stage, so calibration has no periodicity."""
    rng = np.random.default_rng(seed)
    n = int(2 * half_um / step_um)
    f = np.fft.rfft2(rng.normal(size=(n, n)))
    ky = np.fft.fftfreq(n)[:, None]
    kx = np.fft.rfftfreq(n)[None, :]
    tex = np.fft.irfft2(f * np.exp(-((kx**2 + ky**2) / (2 * 0.03**2))), s=(n, n))
    return 40 * tex / tex.std(), step_um, half_um


TEX = random_texture()
HARD = "--hard" in sys.argv  # debris near the edge and a gap in it
FADE = "--fade" in sys.argv  # edge contrast falling along the way, as seen on the real sample
EXPECT = 6000.0 if "--expect" in sys.argv else None  # pass the known diameter
DEBRIS = [HOLE_C + (HOLE_R + 250) * np.array([np.cos(a), np.sin(a)])
          for a in np.linspace(0.9, 6.0, 8)]


class FakeCore:
    def __init__(self, xy):
        self.xy = np.array(xy, float)
        self.moves = 0

    def getXYPosition(self, _dev):
        return tuple(self.xy)

    def setRelativeXYPosition(self, _dev, dx, dy):
        self.xy += (dx, dy)
        self.moves += 1

    def waitForDevice(self, _dev):
        pass

    def frame(self, rng):
        # pixel (x, y) relative to the image centre maps back to a stage offset
        yy, xx = np.mgrid[0:N, 0:N].astype(float)
        dpx = np.stack([xx - (N - 1) / 2, yy - (N - 1) / 2], axis=-1)
        # a sample point at stage s appears at pixel c + M (s - here); invert for s
        s = self.xy + dpx @ np.linalg.inv(M_TRUE).T
        rel = s - HOLE_C
        inside = np.hypot(rel[..., 0], rel[..., 1]) < HOLE_R
        tex, step, half = TEX
        iy = np.clip(((s[..., 1] + half) / step).astype(int), 0, tex.shape[0] - 1)
        ix = np.clip(((s[..., 0] + half) / step).astype(int), 0, tex.shape[1] - 1)
        texture = tex[iy, ix]
        level = 300 * inside
        if HARD:
            ang = np.arctan2(rel[..., 1], rel[..., 0])
            level = np.where(np.abs(ang - 2.5) < np.radians(10), 0, level)  # a 20-degree gap
            for dc in DEBRIS:  # bright debris just outside the edge
                level = level + 350 * (np.hypot(*(s - dc).transpose(2, 0, 1)) < 150)
        if FADE:  # the edge's contrast fades to a quarter over half the circumference
            ang = np.arctan2(rel[..., 1], rel[..., 0])
            level = level * (1 - 0.75 * np.clip((ang - 0.7) / np.pi, 0, 1))
        img = 200 + level + texture + rng.normal(0, 8, (N, N))
        return img.clip(0, 65535).astype(np.uint16)


def kasa(points):
    b = np.array(points)
    A = np.column_stack([2 * b[:, 0], 2 * b[:, 1], np.ones(len(b))])
    (cx, cy, c0), *_ = np.linalg.lstsq(A, (b**2).sum(1), rcond=None)
    return np.array([cx, cy]), float(np.sqrt(c0 + cx**2 + cy**2))


def main() -> None:
    rng = np.random.default_rng(0)
    start = HOLE_C + np.array([HOLE_R * np.cos(0.7), HOLE_R * np.sin(0.7)]) + 400  # edge in view
    core = FakeCore(start)
    events, points = [], []
    tr = EdgeTracker(core, (N, N), PX_UM, exposure_ms=0.0, log=events.append,
                     on_point=lambda x, y: points.append((x, y)), speed_um_s=1e9,
                     expect_diameter_um=EXPECT)
    t = time.perf_counter()
    for _ in range(2000):
        if tr.done:
            break
        tr._ready_at = 0.0  # simulated time: every frame is fresh
        tr.feed(core.frame(rng))
    cal = next(e for e in events if e["event"] == "cal_result")
    M = np.array(cal["M_px_per_um"])
    # moving the stage by d moves image content by -M_TRUE d in this simulator
    print(f"calibration: {cal['um_per_px']:.3f} um/px (true {PX_UM}), "
          f"angle {cal['angle_deg']:.1f} deg, max |M - (-M_true)| "
          f"{np.abs(M + M_TRUE).max():.4f} (entries are {1 / PX_UM:.3f})")
    print(f"status: {tr.status}; {core.moves} moves, {len(points)} edge points, "
          f"{time.perf_counter() - t:.0f} s")
    c, r = kasa(points)
    print(f"fitted hole: centre {c.round(1)} (true {HOLE_C}), diameter {2 * r / 1000:.3f} mm "
          f"(true {2 * HOLE_R / 1000:.3f})")
    rel = np.array(points) - HOLE_C
    resid = np.hypot(rel[:, 0], rel[:, 1]) - HOLE_R
    print(f"edge points off the true circle: median {np.median(np.abs(resid)):.1f} um, "
          f"max {np.abs(resid).max():.1f} um")


if __name__ == "__main__":
    main()
