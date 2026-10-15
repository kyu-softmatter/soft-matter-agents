"""A deterministic virtual microscope: sample, objectives, stage, lights and image formation.

This is the world behind the `mock` backend (PLAN.md v0.2, "mock first"). It knows nothing
about the engine's Backend protocol; `engine/backends/mock.py` (a later task) wraps it. It
is the *hardware*: it refuses moves outside its own travel like a real stage would, but it
applies none of the engine's guards (Z window, ascending sweeps, XY box).

Numbers come from the 2026-09-30 bench run (`docs/runs/2026-09-30_substrate-scan.md`) and
`configs/ti2_*.yaml`. Values marked "estimate" or "not measured" are placeholders, kept in
one place so a measurement replaces them.

Coordinates are the bench's: stage x/y and ZDrive z in um, increasing z = toward the sample.
ZDrive increasing = toward the sample, 0 = fully retracted (PLAN v1.2). The camera image is
mirrored against the stage (PLAN v1.2, seen 2026-09-30): the stage point imaged at sensor
pixel p = (col, row) is stage + inv(M) @ (centre - p), with M the 2026-09-30 4x calibration
in px per um (`Camera.m_4x_px_per_um`), scaled by magnification for the other lenses.

Image model (`MockWorld.render`):

* in focus means ZDrive = the feature's 4x focus z + the objective's parfocal offset;
  dz = z - that. Blur is Gaussian, sigma^2 = sigma0^2 + sigma_psf^2 + (0.5 * dz * NA / n)^2
  (sigma0: the feature's own width, sigma_psf = 0.21 lambda / NA, the last term about half the
  paraxial marginal-ray blur). Blurring keeps the integrated signal: peaks drop as 1/sigma^2.
* DiaLamp (transmitted light): the hole edge is a dark line between the spacer (darker) and
  the chamber, particles are dark shadows. Aura (fluorescence): particles bright on a dim
  chamber background. Both off: the camera offset (~102 ADU) and read noise only.
* signal is proportional to exposure and light intensity; shot noise (Gaussian of Poisson
  variance, exact Poisson optional: `Camera.poisson_below_e`) + read noise; clipped at the
  12-bit ceiling 4095.
* speed on the development desktop: a 512 x 512 ROI takes ~10-40 ms, the full 2400 x 2400
  sensor ~0.4 s (~0.2 s binned 4 x 4). Use `roi` and `binning` for live rates.

Same inputs -> same frame: the noise generator is seeded from the world seed and every
render argument, including `frame_index` (the `snap()` counter).

numpy + scipy only; no torch, pymmcore or UI toolkit.
"""

from __future__ import annotations

import math
import zlib
from dataclasses import asdict, dataclass, field, replace
from typing import Any

import numpy as np

__all__ = [
    "OBJECTIVES",
    "Camera",
    "Faults",
    "Light",
    "MockWorld",
    "Objective",
    "SampleSpec",
    "StageLimitError",
    "StageLimits",
    "VirtualSample",
    "objective_at",
]

EMISSION_UM = 0.605  # configs/ti2_*.yaml illumination.wavelength
CAMERA_PITCH_UM = 6.5  # Kinetix22


# ---------------------------------------------------------------- optics


@dataclass(frozen=True)
class Objective:
    """One nosepiece position. NA, magnification, immersion and WD from configs/ti2_*.yaml."""

    position: int
    key: str  # lens key as used by FocusAxis / registry_key: "4x", "100x-Oil", ...
    label: str  # Nosepiece Label as the Ti2 reports it
    magnification: float
    na: float
    n_immersion: float
    working_distance_um: float
    parfocal_um: float  # in-focus ZDrive minus the 4x in-focus ZDrive, same sample point
    measured: tuple[str, ...] = ()  # which of label / parfocal_um were read off the bench
    #: fluorescence peak of an in-focus particle, ADU per ms per per-mille of Aura intensity
    fluor_adu_per_ms_permille: float = 0.0

    @property
    def pixel_um(self) -> float:
        return CAMERA_PITCH_UM / self.magnification

    @property
    def dof_um(self) -> float:
        """n * lambda / NA^2, the definition dino_autofocus.synth uses."""
        return self.n_immersion * EMISSION_UM / self.na**2

    @property
    def psf_sigma_um(self) -> float:
        return 0.21 * EMISSION_UM / self.na

    @property
    def blur_per_um(self) -> float:
        """Defocus blur sigma per um of |dz|."""
        return 0.5 * self.na / self.n_immersion


def _fluor_scale(mag: float) -> float:
    """Measured at 4x and 100x on 2026-09-30, power law in magnification between (estimate).

    4x: p99.9 2043 ADU at 994 ms, Aura GREEN 10 per-mille -> (2043 - 102) / 994 / 10.
    100x: in-focus particle max 3435 ADU at 20 ms, same light -> (3435 - 102) / 20 / 10.
    """
    a4, a100 = (2043 - 102) / 994 / 10, (3435 - 102) / 20 / 10
    p = math.log(a100 / a4) / math.log(100 / 4)
    return a4 * (mag / 4) ** p


def _parfocal(mag: float) -> float:
    """100x focus ~ 4x focus - 60 um (2026-09-30); others interpolated in log M (estimate)."""
    return -60.0 * math.log(mag / 4) / math.log(100 / 4)


def _objective(pos, key, label, mag, na, n, wd, measured=()) -> Objective:
    parfocal = 0.0 if key == "4x" else -60.0 if key == "100x-Oil" else _parfocal(mag)
    return Objective(pos, key, label, mag, na, n, wd, round(parfocal, 1), measured,
                     _fluor_scale(mag))


#: Nosepiece positions 0-5. Labels of positions 0 and 5 are the ones read on 2026-09-30;
#: the others follow the same pattern but were not read off the stand.
OBJECTIVES: tuple[Objective, ...] = (
    _objective(0, "4x", "1-Plan Apo LmbdD20 4x", 4, 0.2, 1.0, 20000.0,
               ("label", "parfocal_um")),
    _objective(1, "10x", "2-Plan Apo LmbdD 10x", 10, 0.45, 1.0, 4000.0),
    _objective(2, "20x", "3-Plan Apo LmbdD 20x", 20.0785, 0.8, 1.0, 800.0),
    _objective(3, "40x-WI", "4-Apo LmbdS 40xC WI", 40, 1.25, 1.333, 160.0),
    _objective(4, "60x-Oil", "5-Plan Apo LmbdD 60x Oil", 60, 1.42, 1.518, 150.0),
    _objective(5, "100x-Oil", "6-Plan Apo LmbdD0.13 100x Oil", 100, 1.45, 1.518, 130.0,
               ("label", "parfocal_um")),
)


def objective_at(position: int) -> Objective:
    for o in OBJECTIVES:
        if o.position == position:
            return o
    raise ValueError(f"no objective at nosepiece position {position}")


# ---------------------------------------------------------------- hardware descriptions


@dataclass(frozen=True)
class Camera:
    """Kinetix_red in the 100 MHz 12-bit readout used on 2026-09-30."""

    sensor: tuple[int, int] = (2400, 2400)
    bit_depth: int = 12
    offset_adu: float = 102.0  # dark offset seen on 2026-09-30
    gain_e_per_adu: float = 1.25  # not measured (configs placeholder)
    read_noise_e: float = 1.6
    #: exact Poisson shot noise where 0 < expected e- < this; elsewhere a Gaussian of the same
    #: variance. With 1.6 e- read noise and 1.25 e-/ADU the two differ by under one ADU, and
    #: Poisson sampling costs ~15 ms per 512 x 512 frame, so the default is 0 (Gaussian).
    poisson_below_e: float = 0.0
    #: stage um -> sensor px at 4x, 2026-09-30 edge-tracker calibration (1.6252 um/px, 0.117 deg)
    m_4x_px_per_um: tuple[tuple[float, float], tuple[float, float]] = (
        (0.61602, 0.00236), (0.00126, -0.61456))

    @property
    def ceiling(self) -> int:
        return 2**self.bit_depth - 1


@dataclass(frozen=True)
class StageLimits:
    """Travel of the motorised stage and ZDrive. Not measured: placeholders."""

    x_um: tuple[float, float] = (-57000.0, 57000.0)
    y_um: tuple[float, float] = (-37500.0, 37500.0)
    z_um: tuple[float, float] = (0.0, 9000.0)
    xy_speed_um_s: float = 5000.0
    z_speed_um_s: float = 1000.0
    settle_s: float = 0.05


@dataclass(frozen=True)
class Faults:
    """Injected faults for guard and robustness tests.

    `dropout_frames`: `snap()` counter values whose light is scaled by `dropout_factor`
    (2026-09-30: one Aura frame at -23 %). Readback errors are added to what `read_z` /
    `read_xy` report, not to where the stage is (2026-09-30: commanded 3037.0, read 3036.0).
    """

    dropout_frames: tuple[int, ...] = ()
    dropout_factor: float = 0.77
    z_readback_error_um: float = 0.0
    xy_readback_error_um: tuple[float, float] = (0.0, 0.0)


@dataclass
class Light:
    """DiaLamp (transmitted) and Aura (fluorescence) settings, as the devices hold them."""

    dia_on: bool = False
    dia_intensity: int = 608  # of 2100, set at the stand on 2026-09-30
    aura_on: bool = False  # Aura master State
    aura_lines: dict[str, bool] = field(default_factory=dict)  # line -> on
    aura_permille: dict[str, int] = field(default_factory=dict)  # line -> intensity, per-mille

    @property
    def any_on(self) -> bool:
        return self.dia_on or self.fluor_permille > 0

    @property
    def fluor_permille(self) -> float:
        """Effective excitation, per-mille: lines that are on, GREEN-weighted (estimate)."""
        if not self.aura_on:
            return 0.0
        eff = {"GREEN": 1.0}
        return float(sum(self.aura_permille.get(k, 0) * eff.get(k, 0.25)
                         for k, on in self.aura_lines.items() if on))


#: transmitted light inside the chamber, ADU/ms per DiaLamp unit: 4x, 10 ms -> median 2766
#: ADU at intensity 608 (2026-09-30). Same for every objective (estimate: condenser-dependent).
DIA_ADU_PER_MS_PER_UNIT = (2766 - 102) / 10 / 608 / 0.9


# ---------------------------------------------------------------- sample


@dataclass(frozen=True)
class SampleSpec:
    """A sample on the stage: slide, chamber hole, particles, focus plane. Seeded."""

    seed: int = 0
    size_mm: tuple[float, float] = (24.0, 50.0)  # x, y; centred on the hole
    hole_centre_um: tuple[float, float] = (8026.0, 571.6)  # 2026-09-30 edge fit
    hole_diameter_mm: float = 6.144
    coverslip_um: float = 170.0  # recorded; no optical effect in this model yet
    flipped: bool = False  # True: particles settle on the far wall, chamber_um up
    chamber_um: float = 120.0  # spacer thickness (not measured)
    focus_z_um: float = 3048.7  # 4x focus of the settled layer at the hole centre
    tilt_um_per_mm: tuple[float, float] = (-1.66, -3.62)
    particle_diameter_um: tuple[float, float] = (5.0, 6.7)
    particles_per_mm2: float = 200.0  # a few per 100x field (156 um), as seen
    upper_fraction: float = 0.01
    upper_height_um: tuple[float, float] = (15.0, 25.0)


class VirtualSample:
    """Particle positions and geometry drawn once from `SampleSpec.seed`."""

    def __init__(self, spec: SampleSpec):
        self.spec = spec
        rng = np.random.default_rng(spec.seed)
        r = spec.hole_diameter_mm * 500.0
        n = int(rng.poisson(spec.particles_per_mm2 * math.pi * (r / 1000) ** 2))
        rr = (r - 10.0) * np.sqrt(rng.random(n))  # uniform in the disc, off the wall
        th = 2 * math.pi * rng.random(n)
        cx, cy = spec.hole_centre_um
        self.px, self.py = cx + rr * np.cos(th), cy + rr * np.sin(th)
        self.diameter = rng.uniform(*spec.particle_diameter_um, n)
        upper = rng.random(n) < spec.upper_fraction
        h = np.where(upper, rng.uniform(*spec.upper_height_um, n), 0.0)
        self.height = -h if spec.flipped else h  # from the layer they settled on
        self.upper = upper
        self.radius_um = r

    def focus_z(self, x, y):
        """4x in-focus ZDrive of the settled layer at stage (x, y): the tilted plane."""
        s = self.spec
        cx, cy = s.hole_centre_um
        z = s.focus_z_um + s.tilt_um_per_mm[0] * (np.asarray(x) - cx) / 1000 \
            + s.tilt_um_per_mm[1] * (np.asarray(y) - cy) / 1000
        return z + (s.chamber_um if s.flipped else 0.0)

    def particles(self, box: tuple[float, float, float, float]) -> np.ndarray:
        """Indices of particles with centres inside (x0, x1, y0, y1)."""
        x0, x1, y0, y1 = box
        return np.flatnonzero((self.px >= x0) & (self.px <= x1)
                              & (self.py >= y0) & (self.py <= y1))

    def particle_z(self, i) -> np.ndarray:
        """4x in-focus ZDrive of particle(s) i."""
        return self.focus_z(self.px[i], self.py[i]) + self.height[i]


class _Field:
    """Stage coordinates of every pixel of one (ROI, binned) frame, and the inverse map."""

    def __init__(self, m, stage, sensor, origin, nh, nw, b):
        self.m, self.b, self.nh, self.nw = m, b, nh, nw
        self.stage = np.asarray(stage, float)
        self.centre_px = np.array([(sensor[1] - 1) / 2, (sensor[0] - 1) / 2])  # (col, row)
        self.origin = np.asarray(origin, float)  # ROI (x0, y0) in sensor px
        cols = origin[0] + (np.arange(nw) + 0.5) * b - 0.5  # sensor px of binned centres
        rows = origin[1] + (np.arange(nh) + 0.5) * b - 0.5
        a = np.linalg.inv(m)  # um per px
        dc = self.centre_px[0] - cols  # (nw,)
        dr = self.centre_px[1] - rows  # (nh,)
        self.sx = self.stage[0] + a[0, 0] * dc[None, :] + a[0, 1] * dr[:, None]
        self.sy = self.stage[1] + a[1, 0] * dc[None, :] + a[1, 1] * dr[:, None]
        cx, cy = self.sx[[0, 0, -1, -1], [0, -1, 0, -1]], self.sy[[0, 0, -1, -1], [0, -1, 0, -1]]
        self.box = (float(cx.min()), float(cx.max()), float(cy.min()), float(cy.max()))
        self.centre = (float(self.sx.mean()), float(self.sy.mean()))
        self.px_per_um = math.sqrt(abs(np.linalg.det(m))) / b

    def to_image(self, x, y):
        """Binned-image (col, row) of stage points: centre - M @ (q - stage), then ROI/bin."""
        dx, dy = np.asarray(x) - self.stage[0], np.asarray(y) - self.stage[1]
        col = self.centre_px[0] - (self.m[0, 0] * dx + self.m[0, 1] * dy)
        row = self.centre_px[1] - (self.m[1, 0] * dx + self.m[1, 1] * dy)
        return ((col - self.origin[0] + 0.5) / self.b - 0.5,
                (row - self.origin[1] + 0.5) / self.b - 0.5)


class StageLimitError(ValueError):
    """A move outside the stage's own travel (the hardware refuses it)."""


# ---------------------------------------------------------------- the world


class MockWorld:
    """Stage, nosepiece, lights, PFS and camera over one `VirtualSample`.

    State changes go through the methods (as device commands would). Moves are instant and
    return the seconds a real move would take, so a caller can simulate time without sleeping.
    """

    def __init__(self, sample: SampleSpec | None = None, faults: Faults | None = None,
                 camera: Camera | None = None, limits: StageLimits | None = None,
                 seed: int = 0):
        self.spec = sample or SampleSpec(seed=seed)
        self.sample = VirtualSample(self.spec)
        self.faults = faults or Faults()
        self.camera = camera or Camera()
        self.limits = limits or StageLimits()
        # start where the 2026-09-30 session started: 4x, retracted-ish, lights off
        self.x_um, self.y_um = self.spec.hole_centre_um
        self.z_um = 62.9
        self.nosepiece = 0
        self.light = Light()
        self.exposure_ms = 10.0
        self.roi: tuple[int, int, int, int] | None = None
        self.binning = 1
        self.pfs_enabled = False
        self.pfs_in_range = "Out of Range"
        self.frame_index = 0

    # -- devices
    @property
    def objective(self) -> Objective:
        return objective_at(self.nosepiece)

    def move_xy(self, x_um: float, y_um: float) -> float:
        lim = self.limits
        if not (lim.x_um[0] <= x_um <= lim.x_um[1] and lim.y_um[0] <= y_um <= lim.y_um[1]):
            raise StageLimitError(f"XY ({x_um:.1f}, {y_um:.1f}) outside the stage travel")
        d = math.hypot(x_um - self.x_um, y_um - self.y_um)
        self.x_um, self.y_um = float(x_um), float(y_um)
        return d / lim.xy_speed_um_s + lim.settle_s

    def move_z(self, z_um: float) -> float:
        lo, hi = self.limits.z_um
        if not lo <= z_um <= hi:
            raise StageLimitError(f"ZDrive {z_um:.3f} outside the travel {lo}..{hi}")
        d = abs(z_um - self.z_um)
        self.z_um = float(z_um)
        return d / self.limits.z_speed_um_s + self.limits.settle_s

    def read_xy(self) -> tuple[float, float]:
        ex, ey = self.faults.xy_readback_error_um
        return self.x_um + ex, self.y_um + ey

    def read_z(self) -> float:
        return self.z_um + self.faults.z_readback_error_um

    def set_nosepiece(self, position: int) -> None:
        objective_at(position)  # raises on an empty position
        self.nosepiece = int(position)

    def set_dialamp(self, on: bool, intensity: int | None = None) -> None:
        self.light.dia_on = bool(on)
        if intensity is not None:
            self.light.dia_intensity = int(intensity)

    def set_aura_line(self, line: str, on: bool, permille: int | None = None) -> None:
        line = line.upper()
        self.light.aura_lines[line] = bool(on)
        if permille is not None:
            if not 0 <= permille <= 1000:
                raise ValueError(f"Aura intensity is per-mille 0..1000, got {permille}")
            self.light.aura_permille[line] = int(permille)

    def set_aura(self, on: bool) -> None:
        self.light.aura_on = bool(on)

    def all_off(self) -> None:
        self.light.dia_on = False
        self.light.aura_on = False

    def pfs_disable(self) -> None:
        """PFS is only ever switched off by software; nothing here switches it on."""
        self.pfs_enabled = False

    def set_exposure(self, ms: float) -> None:
        if not ms > 0:
            raise ValueError(f"exposure must be > 0 ms, got {ms}")
        self.exposure_ms = float(ms)

    def set_roi(self, roi: int | tuple[int, int, int, int] | None) -> None:
        self.roi = None if roi is None else self._roi_box(roi)

    # -- camera
    def snap(self) -> np.ndarray:
        """Render the current state; each call is a new frame (new noise, `frame_index`+1)."""
        img = self.render(self.x_um, self.y_um, self.z_um, self.objective, self.light,
                          self.exposure_ms, self.roi, self.binning, self.frame_index)
        self.frame_index += 1
        return img

    def _roi_box(self, roi) -> tuple[int, int, int, int]:
        h, w = self.camera.sensor
        if isinstance(roi, int | np.integer):
            s = int(roi)
            if not 0 < s <= min(h, w):
                raise ValueError(f"ROI size {s} outside 1..{min(h, w)}")
            return (w - s) // 2, (h - s) // 2, s, s
        x0, y0, rw, rh = (int(v) for v in roi)
        if x0 < 0 or y0 < 0 or rw <= 0 or rh <= 0 or x0 + rw > w or y0 + rh > h:
            raise ValueError(f"ROI {roi} outside the {w} x {h} sensor")
        return x0, y0, rw, rh

    def render(self, x_um: float, y_um: float, z_um: float, objective: Objective,
               light: Light, exposure_ms: float, roi=None, binning: int = 1,
               frame_index: int = 0) -> np.ndarray:
        """One uint16 frame (rows, cols) for the given stage position, lens and light.

        `roi` is None (full sensor), a square size centred on the sensor, or
        (x0, y0, width, height) in sensor pixels. `binning` b sums b x b pixels (the frame is
        height // b x width // b). Pure: depends only on the arguments and the world seed.
        """
        cam, b = self.camera, int(binning)
        if b < 1:
            raise ValueError("binning must be >= 1")
        x0, y0, rw, rh = self._roi_box(roi) if roi is not None else (0, 0, *cam.sensor[::-1])
        fld = _Field(self.pixel_matrix(objective), (x_um, y_um), cam.sensor, (x0, y0),
                     rh // b, rw // b, b)

        scale = exposure_ms * b * b  # light per binned pixel per unit rate
        if frame_index in self.faults.dropout_frames:
            scale *= self.faults.dropout_factor
        signal = np.zeros((fld.nh, fld.nw), np.float32)
        dia = light.dia_on and light.dia_intensity > 0
        fl = light.fluor_permille
        if dia or fl > 0:
            hx, hy = self.spec.hole_centre_um  # signed distance to the hole edge, > 0 outside
            d = (np.hypot(fld.sx - hx, fld.sy - hy) - self.sample.radius_um).astype(np.float32)
            if dia:
                signal += self._transmitted(fld, d, z_um, objective) * np.float32(
                    DIA_ADU_PER_MS_PER_UNIT * light.dia_intensity * scale)
            if fl > 0:
                signal += self._fluorescence(fld, d, z_um, objective) * np.float32(
                    objective.fluor_adu_per_ms_permille * fl * scale)

        key = repr((self.spec.seed, round(x_um, 4), round(y_um, 4), round(z_um, 4),
                    objective.position, asdict(light), round(exposure_ms, 6),
                    (x0, y0, rw, rh), b, int(frame_index))).encode()
        rng = np.random.default_rng(zlib.crc32(key))
        g = cam.gain_e_per_adu
        lam = np.clip(signal, 0, None) * np.float32(g)  # expected photo-electrons
        # Shot + read noise as one Gaussian of variance lam + read^2 (the Poisson limit); exact
        # Poisson below Camera.poisson_below_e. Binned read noise adds in quadrature over the
        # b x b pixels; the offset stays one offset.
        r = np.float32(cam.read_noise_e * b)
        n = rng.standard_normal((fld.nh, fld.nw), dtype=np.float32)
        e = lam + np.sqrt(lam + r * r) * n
        if cam.poisson_below_e > 0:
            low = (lam > 0) & (lam < cam.poisson_below_e)
            if low.any():
                e[low] = rng.poisson(lam[low]) + r * n[low]
        adu = e / np.float32(g) + np.float32(cam.offset_adu)
        return np.clip(np.rint(adu), 0, cam.ceiling).astype(np.uint16)

    # -- image geometry (PLAN v1.2: stage of pixel p = stage + inv(M) @ (centre - p))
    def pixel_matrix(self, objective: Objective | None = None) -> np.ndarray:
        """M (sensor px per stage um) for `objective`: the 4x calibration scaled by
        magnification. Rotation and mirror are the camera's, so they are shared by all lenses."""
        o = objective or self.objective
        return np.asarray(self.camera.m_4x_px_per_um, float) * (o.magnification / 4.0)

    def stage_of_pixel(self, col: float, row: float, objective: Objective | None = None,
                       stage: tuple[float, float] | None = None) -> tuple[float, float]:
        """Stage coordinates (um) of sensor pixel (col, row): stage + inv(M) @ (centre - p)."""
        st = np.array(stage if stage is not None else (self.x_um, self.y_um), float)
        h, w = self.camera.sensor
        centre = np.array([(w - 1) / 2, (h - 1) / 2])
        xy = st + np.linalg.solve(self.pixel_matrix(objective), centre - np.array([col, row]))
        return float(xy[0]), float(xy[1])

    def pixel_of_stage(self, x_um: float, y_um: float, objective: Objective | None = None,
                       stage: tuple[float, float] | None = None) -> tuple[float, float]:
        """Sensor pixel (col, row) where stage point (x, y) is imaged: centre - M @ (q - stage)."""
        st = np.array(stage if stage is not None else (self.x_um, self.y_um), float)
        h, w = self.camera.sensor
        centre = np.array([(w - 1) / 2, (h - 1) / 2])
        p = centre - self.pixel_matrix(objective) @ (np.array([x_um, y_um]) - st)
        return float(p[0]), float(p[1])

    # -- image terms (unit rates; multiplied by intensity and exposure in render)
    def _blur(self, objective: Objective, dz, sigma0) -> np.ndarray:
        return np.sqrt(sigma0**2 + objective.psf_sigma_um**2
                       + (objective.blur_per_um * np.asarray(dz)) ** 2)

    def _view_particles(self, fld: _Field, z_um, objective, transmitted: bool):
        """(index, blur sigma um, relative peak) of the particles that may reach the field."""
        s = self.sample
        x0, x1, y0, y1 = fld.box
        # widest blur a particle near the field can have: field-centre defocus, plus the
        # tilt across the field, plus the highest particle layer
        dz_c = z_um - (float(s.focus_z(*fld.centre)) + objective.parfocal_um)
        reach = abs(dz_c) + 0.004 * max(x1 - x0, y1 - y0) + max(s.spec.upper_height_um)
        sig_max = float(self._blur(objective, reach, s.spec.particle_diameter_um[1]))
        margin = min(4 * sig_max, 400.0)
        idx = s.particles((x0 - margin, x1 + margin, y0 - margin, y1 + margin))
        sigma0 = s.diameter[idx] / 2.355  # FWHM = diameter (~6.7 um seen at 100x)
        dz = z_um - (s.particle_z(idx) + objective.parfocal_um)
        sig = self._blur(objective, dz, sigma0)
        amp = (sigma0 / sig) ** 2
        return idx, sig, amp * (0.45 if transmitted else 1.0)

    def _splat(self, out, fld: _Field, idx, sig_um, amp, sign: float) -> None:
        """Add sign * amp * Gaussian for each particle, drawn in image pixels.

        M is close to a scaled mirror with a 0.1 degree rotation, so an isotropic Gaussian in
        the sample stays one in the image, with sigma_px = sigma_um * sqrt(|det M|) / binning.
        Particles that stay below 1e-4 of full scale over the field are dropped. Up to a size
        limit all are summed in one matrix product of separable factors; beyond it, compact
        ones go on 4-sigma patches.
        """
        if len(idx) == 0:
            return
        s = self.sample
        c, r = fld.to_image(s.px[idx], s.py[idx])
        sig = sig_um * fld.px_per_um
        nh, nw = out.shape
        ec = np.maximum(0.0, np.maximum(-c, c - (nw - 1)))
        er = np.maximum(0.0, np.maximum(-r, r - (nh - 1)))
        keep = amp * np.exp(-0.5 * (ec**2 + er**2) / sig**2) > 1e-4
        c, r, sig, amp = c[keep], r[keep], sig[keep], amp[keep]
        if len(c) * nh * nw <= 6e7:  # one BLAS product beats a Python loop up to here
            wide = np.ones(len(c), bool)
        else:
            wide = np.minimum(8 * sig + 2, nw) * np.minimum(8 * sig + 2, nh) > 0.1 * nh * nw
        if wide.any():
            sg = sig[wide][:, None].astype(np.float32)
            jc = np.arange(nw, dtype=np.float32)[None, :]
            jr = np.arange(nh, dtype=np.float32)[None, :]
            gx = np.exp(-0.5 * ((jc - c[wide][:, None].astype(np.float32)) / sg) ** 2)
            gy = np.exp(-0.5 * ((jr - r[wide][:, None].astype(np.float32)) / sg) ** 2)
            out += (gy * (sign * amp[wide][:, None]).astype(np.float32)).T @ gx
        for cc, rr, sg, a in zip(c[~wide], r[~wide], sig[~wide], amp[~wide], strict=True):
            c0, c1 = max(int(cc - 4 * sg), 0), min(int(cc + 4 * sg) + 2, nw)
            r0, r1 = max(int(rr - 4 * sg), 0), min(int(rr + 4 * sg) + 2, nh)
            if c0 >= c1 or r0 >= r1:
                continue
            gx = np.exp(-0.5 * ((np.arange(c0, c1) - cc) / sg) ** 2)
            gy = np.exp(-0.5 * ((np.arange(r0, r1) - rr) / sg) ** 2)
            out[r0:r1, c0:c1] += sign * a * np.outer(gy, gx)

    def _transmitted(self, fld: _Field, d, z_um, objective) -> np.ndarray:
        """Transmission 0..1: open glass 1.0, spacer 0.55, chamber 0.9, dark edge line, dark
        particle shadows. The edge is blurred by the substrate's defocus at the field centre
        (the tilt across one field is ignored for the edge; particles use their own z)."""
        s, spec = self.sample, self.spec
        dz = z_um - (float(s.focus_z(*fld.centre)) + objective.parfocal_um)
        sig = max(float(self._blur(objective, dz, 0.0)), 1e-3)
        t_in, t_spacer = 0.9, 0.55
        w0, depth = 4.0, 0.5  # edge line width (sigma, um) and depth
        ws = math.hypot(w0, sig)
        t = np.where(d < 0, np.float32(t_in), np.float32(t_spacer))
        near = np.abs(d) < 6 * ws + 20  # erfc / exp only where the edge reaches
        if near.any():
            from scipy.special import erfc  # lazy: importing the mock costs no scipy (T-035b)

            dn = d[near].astype(np.float64)
            t[near] = (t_spacer + (t_in - t_spacer) * 0.5 * erfc(dn / (math.sqrt(2) * sig))
                       - depth * (w0 / ws) * np.exp(-0.5 * (dn / ws) ** 2))
        hx, hy = spec.hole_centre_um
        half_w = 500.0 * np.array(spec.size_mm)
        x0, x1, y0, y1 = fld.box
        if x0 < hx - half_w[0] or x1 > hx + half_w[0] or y0 < hy - half_w[1] or y1 > hy + half_w[1]:
            off = (np.abs(fld.sx - hx) > half_w[0]) | (np.abs(fld.sy - hy) > half_w[1])
            t[off] = 1.0  # off the slide: open light
        idx, psig, amp = self._view_particles(fld, z_um, objective, transmitted=True)
        self._splat(t, fld, idx, psig, amp, -1.0)
        return np.clip(t, 0.0, None)

    def _fluorescence(self, fld: _Field, d, z_um, objective) -> np.ndarray:
        """Particle peaks of 1.0 when in focus, on a 0.02 chamber background (estimate)."""
        f = np.where(d < 0, np.float32(0.02), np.float32(0.0))
        idx, psig, amp = self._view_particles(fld, z_um, objective, transmitted=False)
        self._splat(f, fld, idx, psig, amp, 1.0)
        return f

    # -- truth helpers (tests and the mock backend's "where is focus" answers)
    def in_focus_z(self, x_um: float | None = None, y_um: float | None = None,
                   objective: Objective | None = None) -> float:
        """ZDrive at which the settled layer under (x, y) is in focus with `objective`."""
        x = self.x_um if x_um is None else x_um
        y = self.y_um if y_um is None else y_um
        o = objective or self.objective
        return float(self.sample.focus_z(x, y)) + o.parfocal_um

    # -- state
    def state_dict(self) -> dict[str, Any]:
        """Position, lens, light, camera settings, PFS and frame counter; JSON-serialisable."""
        return {"x_um": self.x_um, "y_um": self.y_um, "z_um": self.z_um,
                "nosepiece": self.nosepiece, "objective": self.objective.label,
                "light": asdict(self.light), "exposure_ms": self.exposure_ms,
                "roi": None if self.roi is None else list(self.roi), "binning": self.binning,
                "pfs_enabled": self.pfs_enabled, "pfs_in_range": self.pfs_in_range,
                "frame_index": self.frame_index}

    def load_state(self, d: dict[str, Any]) -> None:
        self.x_um, self.y_um, self.z_um = float(d["x_um"]), float(d["y_um"]), float(d["z_um"])
        self.set_nosepiece(int(d["nosepiece"]))
        self.light = Light(**d["light"])
        self.exposure_ms = float(d["exposure_ms"])
        self.roi = None if d.get("roi") is None else tuple(d["roi"])
        self.binning = int(d.get("binning", 1))
        self.pfs_enabled = bool(d.get("pfs_enabled", False))
        self.pfs_in_range = str(d.get("pfs_in_range", "Out of Range"))
        self.frame_index = int(d.get("frame_index", 0))

    def to_dict(self) -> dict[str, Any]:
        """Everything needed to rebuild this world: sample, faults, camera, limits, state."""
        return {"sample": asdict(self.spec), "faults": asdict(self.faults),
                "camera": asdict(self.camera), "limits": asdict(self.limits),
                "state": self.state_dict()}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MockWorld:
        def tup(v):
            return tuple(tup(x) for x in v) if isinstance(v, list) else v

        def build(kind, values):
            return kind(**{k: tup(v) for k, v in values.items()})

        w = cls(build(SampleSpec, d["sample"]), build(Faults, d["faults"]),
                build(Camera, d["camera"]), build(StageLimits, d["limits"]))
        w.load_state(d["state"])
        return w

    def with_faults(self, **kw: Any) -> MockWorld:
        """A copy of this world (same state) with some fault fields replaced."""
        w = MockWorld(self.spec, replace(self.faults, **kw), self.camera, self.limits)
        w.load_state(self.state_dict())
        return w
