"""Z-stack sources for the replay backend: in-memory arrays, synth shards, sample folders.

A `ZStack` is a set of mono uint16 frames with one z per frame, sorted by z. The replay
backend asks it for "the frame at the current z" with `ZStack.frame_at`. Nothing here moves
hardware or enforces limits: a request outside the stack is answered with the edge plane and
a flag, and the engine's guards decide what is allowed.

Sources (`load_stacks`):

* in memory: `ZStack.from_arrays(frames, z_um, ...)`
* `dino_autofocus.synth` shards (`shard_*.npz`, one stack per `scene_id`), a directory or one file
* a sample folder (`D:\\AutoFocus\\samples\\<id>`) or its parts:
  * `find_particle_*_fieldNN.npz` from `scripts/find_particle_z.py`: real ascending ZDrive
    stacks, 8 x 8 binned
  * `stack_*.npy` + `.json` from `scripts/mm_grab.py --n`: frames with the z read at pop time
  * `scan4x_*/scan.json` + `tile_*.npy` from `scripts/scan_4x.py`: one in-focus frame per tile,
    so each tile is a **one-plane** stack (the sweep's frames are not saved)

`scripts/focus_100x.py` saves no frames, only the sweep's numbers; those, and the per-tile
sweeps in `scan.json`, are read as `FocusCurve`s by `load_curves`.

numpy only: no torch, pymmcore or UI toolkit.
"""

from __future__ import annotations

import json
import math
import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

__all__ = ["FocusCurve", "PlaneHit", "ZStack", "load_curves", "load_stacks"]

#: cond column order written by dino_autofocus.synth when the manifest does not say
SYNTH_COND_NAMES = ("na", "wavelength_um", "pixel_size_um", "dof_um", "log10_signal")


@dataclass(frozen=True)
class PlaneHit:
    """The plane `ZStack.frame_at` chose for a requested z."""

    frame: np.ndarray  # (H, W) uint16, read-only view into the stack
    index: int
    z_um: float  # z of the returned plane
    requested_um: float
    clamped: bool  # the request was outside [z_min, z_max]; the edge plane was returned

    @property
    def offset_um(self) -> float:
        """requested - returned plane z (0 on an exact hit)."""
        return self.requested_um - self.z_um


@dataclass
class ZStack:
    """Frames `(N, H, W)` uint16 with `z_um` `(N,)` non-decreasing, plus a metadata dict.

    Metadata keys used by the loaders (all optional except `source`):
    `source` (kind of input), `path`, `pixel_um`, `z_kind` (what z_um measures),
    `best_focus_um` (in the same coordinate as z_um; then dz = z_um - best_focus_um),
    `dz_definition`. Values are kept JSON-serialisable.

    Construct with `from_arrays`, which sorts and copies. The stored arrays are read-only.
    """

    frames: np.ndarray
    z_um: np.ndarray
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        f, z = self.frames, self.z_um
        if f.ndim != 3 or f.dtype != np.uint16:
            raise ValueError(f"frames must be (N, H, W) uint16, got {f.shape} {f.dtype}")
        if z.ndim != 1 or len(z) != len(f):
            raise ValueError(f"z_um must be (N,) with N = {len(f)}, got {z.shape}")
        if len(f) == 0:
            raise ValueError("a z-stack needs at least one plane")
        if not np.all(np.isfinite(z)):
            raise ValueError("z_um has non-finite values")
        if np.any(np.diff(z) < 0):
            raise ValueError("z_um must be non-decreasing; use ZStack.from_arrays to sort")
        self.meta.setdefault("source", "arrays")

    @classmethod
    def from_arrays(cls, frames, z_um, meta: dict[str, Any] | None = None, **kw: Any) -> ZStack:
        """Copy, sort by z (stable: equal z keep their order) and convert frames to uint16.

        Float or wider-integer frames are rounded and clipped to 0..65535. Extra keyword
        arguments are added to the metadata.
        """
        f = np.asarray(frames)
        z = np.asarray(z_um, dtype=np.float64).reshape(-1)
        if f.ndim == 2:
            f = f[None]
        if f.dtype != np.uint16:
            if np.issubdtype(f.dtype, np.floating):
                f = np.rint(np.nan_to_num(f, nan=0.0))
            f = np.clip(f, 0, 65535).astype(np.uint16)
        if len(z) != len(f):
            raise ValueError(f"{len(f)} frames but {len(z)} z values")
        order = np.argsort(z, kind="stable")
        frames_c = np.ascontiguousarray(f[order])
        z_c = z[order].copy()
        frames_c.flags.writeable = False
        z_c.flags.writeable = False
        return cls(frames_c, z_c, {**(meta or {}), **kw})

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def shape(self) -> tuple[int, int]:
        return int(self.frames.shape[1]), int(self.frames.shape[2])

    @property
    def z_range_um(self) -> tuple[float, float]:
        return float(self.z_um[0]), float(self.z_um[-1])

    @property
    def best_focus_um(self) -> float | None:
        v = self.meta.get("best_focus_um")
        return None if v is None else float(v)

    def frame_at(self, z_um: float) -> PlaneHit:
        """The plane nearest to `z_um`; no interpolation.

        Rules, in order:
        1. `z_um` below the first plane -> the first plane, `clamped=True`; above the last
           plane -> the last plane, `clamped=True`. No exception: limits are the engine's.
        2. Otherwise the plane with the smallest |z - z_um|. A tie between two planes goes to
           the **lower** z (the retract side), so the choice never depends on float noise in
           the direction of approach.
        3. Several planes at the same z: the first of them in stack order.

        A non-finite `z_um` raises ValueError (a caller bug, not a position).
        """
        z = float(z_um)
        if not math.isfinite(z):
            raise ValueError(f"z_um must be finite, got {z_um!r}")
        zs = self.z_um
        lo_z, hi_z = zs[0], zs[-1]
        if z <= lo_z:
            i, clamped = 0, z < lo_z
        elif z >= hi_z:
            i, clamped = len(zs) - 1, z > hi_z
        else:
            j = int(np.searchsorted(zs, z, side="left"))  # zs[j-1] < z <= zs[j]
            i = j if (zs[j] - z) < (z - zs[j - 1]) else j - 1
            clamped = False
        i = int(np.searchsorted(zs, zs[i], side="left"))  # first of equal-z planes
        return PlaneHit(self.frames[i], i, float(zs[i]), z, bool(clamped))


@dataclass
class FocusCurve:
    """A focus sweep's numbers without frames: z and one array per recorded column."""

    z_um: np.ndarray
    columns: dict[str, np.ndarray]
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_rows(cls, rows: list[dict[str, Any]], z_key: str = "z", **meta: Any) -> FocusCurve:
        rows = sorted(rows, key=lambda r: float(r[z_key]))
        z = np.array([float(r[z_key]) for r in rows])
        names = [k for k in (rows[0] if rows else {}) if k != z_key]
        cols = {k: np.array([np.nan if r.get(k) is None else float(r[k]) for r in rows])
                for k in names}
        return cls(z, cols, meta)


# ---------------------------------------------------------------- dispatch


def load_stacks(source) -> list[ZStack]:
    """Every z-stack in `source`, by kind of source.

    `source` is a `ZStack`, an iterable of sources, or a path to: a synth shard directory or
    `shard_*.npz`; a `find_particle_*_fieldNN.npz`; a `stack_*.npy` (with its `.json`); a
    `scan.json` or a `scan4x_*` directory; or a sample folder holding any of these.
    Raises FileNotFoundError when the path is missing or holds no stack, and ValueError for a
    file that is not a stack (e.g. `focus100x_*.json`: use `load_curves`).
    """
    if isinstance(source, ZStack):
        return [source]
    if isinstance(source, str | Path):
        return _load_path(Path(source))
    if isinstance(source, Iterable):
        return [s for item in source for s in load_stacks(item)]
    raise TypeError(f"cannot load z-stacks from {type(source).__name__}")


def _load_path(p: Path) -> list[ZStack]:
    if not p.exists():
        raise FileNotFoundError(p)
    if p.is_file():
        if p.suffix == ".npz":
            keys = _npz_keys(p)
            if {"image", "scene_id"} <= keys:
                return _synth_shards([p], _manifest(p.parent))
            if {"stack", "z_um"} <= keys:
                return [_particle_field(p)]
            raise ValueError(f"{p.name}: npz with keys {sorted(keys)} is not a known z-stack")
        if p.suffix == ".npy" and p.name.startswith("stack_"):
            return [_mm_grab_stack(p)]
        if p.name == "scan.json":
            return _scan_tiles(p)
        if p.name.startswith("focus100x_"):
            raise ValueError(f"{p.name} holds a focus curve, not frames; use load_curves")
        raise ValueError(f"{p.name}: not a known z-stack file")
    shards = sorted(p.glob("shard_*.npz"))
    if shards:
        return _synth_shards(shards, _manifest(p))
    if (p / "scan.json").exists():
        return _scan_tiles(p / "scan.json")
    out: list[ZStack] = []
    for scan in sorted(p.glob("scan4x_*/scan.json")):
        out += _scan_tiles(scan)
    out += [_particle_field(f) for f in sorted(p.glob("find_particle_*_field*.npz"))]
    out += [_mm_grab_stack(f) for f in sorted(p.glob("stack_*.npy"))]
    if not out:
        raise FileNotFoundError(f"no z-stack sources in {p}")
    return out


def _npz_keys(p: Path) -> set[str]:
    with np.load(p, allow_pickle=False) as z:
        return set(z.files)


def _read_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- synth shards


def _manifest(d: Path) -> dict[str, Any]:
    m = d / "manifest.json"
    return _read_json(m) if m.exists() else {}


def _synth_shards(paths: list[Path], manifest: dict[str, Any]) -> list[ZStack]:
    """One stack per scene_id per shard (the writer keeps a scene inside one shard).

    z: `stage_um` (the simulator's stage coordinate, not bench ZDrive) when the shard has
    it, with `best_stage_um` as best focus; otherwise `dz_um` with best focus 0. Either way
    dz = z_um - best_focus_um = stage - best focus, the shard's own definition.
    `scene_params` (a pickled object array) is not read, so no pickle is loaded.
    """
    cond_names = list(manifest.get("cond_names") or SYNTH_COND_NAMES)
    out = []
    for path in paths:
        with np.load(path, allow_pickle=False) as d:
            keys = set(d.files)
            a = {k: d[k] for k in keys if k != "scene_params"}
        sid = a["scene_id"]
        for s in sorted(np.unique(sid).tolist()):
            i = np.flatnonzero(sid == s)
            if "stage_um" in a:
                z = a["stage_um"][i]
                best = float(a["best_stage_um"][i][0]) if "best_stage_um" in a else None
                z_kind = "synth stage_um (simulator coordinate, not ZDrive)"
            else:
                z, best, z_kind = a["dz_um"][i], 0.0, "dz_um (no absolute z in the shard)"
            meta: dict[str, Any] = {
                "source": "synth_shard", "path": str(path), "scene_id": int(s),
                "z_kind": z_kind, "best_focus_um": best,
                "dz_definition": "dz = z_um - best_focus_um (stage - best focus)",
            }
            if "cond" in a:
                cond = dict(zip(cond_names, a["cond"][i][0].tolist(), strict=False))
                meta["cond"] = cond
                if "pixel_size_um" in cond:
                    meta["pixel_um"] = float(cond["pixel_size_um"])
            for k in ("family", "geometry", "system"):
                if k in a:
                    meta[k] = str(a[k][i][0])
            order = np.argsort(z, kind="stable")
            for k in ("valid", "dz_dof"):  # per plane, in z order
                if k in a:
                    meta[k] = a[k][i][order].tolist()
            out.append(ZStack.from_arrays(a["image"][i], z, meta))
    return out


# ---------------------------------------------------------------- sample-folder files


def _particle_field(p: Path) -> ZStack:
    """find_particle_z.py field stack: `stack` float32 (N, h, w) 8 x 8 binned means of uint16
    frames, `z_um` ZDrive readback, `xy_um`, `bin`. Pixel size from the run's json if there."""
    with np.load(p, allow_pickle=False) as d:
        stack, z = d["stack"], d["z_um"]
        xy = d["xy_um"].tolist() if "xy_um" in d.files else None
        b = int(d["bin"]) if "bin" in d.files else None
    meta: dict[str, Any] = {"source": "find_particle_field", "path": str(p), "xy_um": xy,
                            "bin": b, "z_kind": "ZDrive readback (um)", "best_focus_um": None}
    run = p.with_name(p.stem.rsplit("_field", 1)[0] + ".json")
    if run.exists():
        px = _read_json(run).get("pixel_um")
        if px is not None:
            meta["pixel_um"] = float(px) * (b or 1)
    return ZStack.from_arrays(stack, z, meta)


def _mm_grab_stack(p: Path) -> ZStack:
    """mm_grab.py --n: `stack_<stamp>.npy` (N, H, W) uint16 + `.json` with per-frame positions.

    The z of each frame was read when it left the buffer (hand-driven sweeps), so frames are
    sorted by that z. Frames without a z reading are dropped and counted in meta.
    """
    frames = np.load(p, allow_pickle=False)
    info = _read_json(p.with_suffix(".json"))
    zs = [fr.get("z_um") for fr in info.get("frames", [])][: len(frames)]
    keep = [k for k, z in enumerate(zs) if z is not None]
    meta = {"source": "mm_grab_stack", "path": str(p), "z_kind": "ZDrive read at pop (um)",
            "best_focus_um": None, "pixel_um": info.get("pixel_um"),
            "objective": info.get("objective"), "exposure_ms": info.get("exposure_ms"),
            "dropped_no_z": len(frames) - len(keep)}
    if not keep:
        raise ValueError(f"{p.name}: no frame has a z reading")
    return ZStack.from_arrays(frames[keep], [zs[k] for k in keep], meta)


def _scan_tiles(scan_json: Path) -> list[ZStack]:
    """scan_4x.py: each tile's saved in-focus frame as a one-plane stack at `z_image_um`.

    `best_focus_um` is the tile's `z_focus_um` (None when the tile found no focus). A tile
    whose .npy is missing is skipped with a warning (e.g. a partial copy of the folder).
    """
    rec = _read_json(scan_json)
    d = scan_json.parent
    out = []
    for t in rec.get("tiles", []):
        f = d / f"{t['name']}.npy"
        if not f.exists():
            warnings.warn(f"{f} missing; tile skipped", stacklevel=3)
            continue
        meta = {"source": "scan4x_tile", "path": str(f), "sample": rec.get("sample"),
                "tile": t["name"], "x_um": t.get("x_um"), "y_um": t.get("y_um"),
                "z_kind": "ZDrive (um)", "best_focus_um": t.get("z_focus_um"),
                "focus_note": t.get("focus_note"), "pixel_um": rec.get("um_per_px"),
                "objective": rec.get("objective"), "exposure_ms": rec.get("exposure_ms")}
        out.append(ZStack.from_arrays(np.load(f, allow_pickle=False), [t["z_image_um"]], meta))
    return out


# ---------------------------------------------------------------- curves


def load_curves(source) -> list[FocusCurve]:
    """Focus sweeps without frames: `focus100x_*.json` (coarse and fine) and the per-tile
    curves of `scan.json`, from a file, a `scan4x_*` directory or a sample folder."""
    p = Path(source)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.is_file():
        if p.name.startswith("focus100x_"):
            return _focus100x(p)
        if p.name == "scan.json":
            return _scan_curves(p)
        raise ValueError(f"{p.name}: not a known focus-curve file")
    if (p / "scan.json").exists():
        return _scan_curves(p / "scan.json")
    out: list[FocusCurve] = []
    for f in sorted(p.glob("focus100x_*.json")):
        out += _focus100x(f)
    for f in sorted(p.glob("scan4x_*/scan.json")):
        out += _scan_curves(f)
    return out


def _focus100x(p: Path) -> list[FocusCurve]:
    """focus_100x.py rows are (z_readback_um, score, mean, max); the metric name is not saved."""
    rec = _read_json(p)
    out = []
    for stage in ("coarse", "fine"):
        rows = rec.get(stage)
        if not rows:
            continue
        rows = [dict(zip(("z", "score", "mean", "max"), r, strict=False)) for r in rows]
        out.append(FocusCurve.from_rows(
            rows, source="focus100x", path=str(p), stage=stage, z_kind="ZDrive readback (um)",
            z_focus_um=rec.get("z_focus_um"), why=rec.get("why"),
            z_parked_um=rec.get("z_parked_um")))
    return out


def _scan_curves(scan_json: Path) -> list[FocusCurve]:
    rec = _read_json(scan_json)
    return [FocusCurve.from_rows(t["curve"], source="scan4x_tile", path=str(scan_json),
                                 tile=t["name"], z_kind="ZDrive readback (um)",
                                 z_focus_um=t.get("z_focus_um"), x_um=t.get("x_um"),
                                 y_um=t.get("y_um"))
            for t in rec.get("tiles", []) if t.get("curve")]
