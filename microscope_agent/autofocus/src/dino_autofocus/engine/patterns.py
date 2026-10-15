"""Motion patterns: what the piezo stage and the tweezer traps do over time (card T-20261002-2205).

A pattern is a set of **tracks**. Each track drives one target and is a list of timed points
``(t_s, x_um, y_um, z_um)``, linearly interpolated between points:

* ``piezo``: the XYZ piezo stage. Positions are offsets from where the stage is when the run
  starts, so the same pattern runs anywhere on the sample.
* ``trap:N``: tweezer trap N. Positions are in the sample plane, measured from the centre of
  the camera field. ``z_um`` is the trap's focus offset (0 when the trap has no z).

Every track starts at ``t = 0`` and its times only go up. The pattern lasts as long as its
longest track; a shorter track holds its last point. This module only describes and checks
patterns; it moves nothing. Running one is a later operation (stage 4) behind the guards and
the bench locks.

The ranges below are PROVISIONAL (no piezo or tweezer is measured yet): a pattern outside
them is refused here, and the run operation will check the measured ranges again.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

FORMAT_VERSION = 1

#: PROVISIONAL travel of the piezo stage around its start position, um (not measured)
PIEZO_RANGE_UM = {"x": (-100.0, 100.0), "y": (-100.0, 100.0), "z": (-50.0, 50.0)}
#: PROVISIONAL reach of a trap from the field centre, um (not measured)
TRAP_RANGE_UM = {"x": (-60.0, 60.0), "y": (-60.0, 60.0), "z": (-10.0, 10.0)}
MAX_TRAPS = 8
MAX_POINTS = 20_000  # per track
MAX_DURATION_S = 3600.0
MAX_NAME = 100

# \A..\Z, not ^..$: "$" also matches before a trailing newline
PATTERN_ID = re.compile(r"\A[a-z0-9][a-z0-9_-]{0,63}\Z")
_TARGET = re.compile(r"^(piezo|trap:(\d+))$")


class PatternError(ValueError):
    """A pattern that cannot be used; the message says which track and point."""


@dataclass(frozen=True)
class Point:
    t_s: float
    x_um: float = 0.0
    y_um: float = 0.0
    z_um: float = 0.0


@dataclass(frozen=True)
class Track:
    target: str  # "piezo" | "trap:N"
    points: tuple[Point, ...]

    @property
    def duration_s(self) -> float:
        return self.points[-1].t_s

    def at(self, t_s: float) -> Point:
        """The position at ``t_s`` (clamped to the track; the last point holds)."""
        pts = self.points
        if t_s <= pts[0].t_s:
            return pts[0]
        if t_s >= pts[-1].t_s:
            return pts[-1]
        lo, hi = 0, len(pts) - 1
        while hi - lo > 1:  # binary search: tracks may hold thousands of points
            mid = (lo + hi) // 2
            if pts[mid].t_s <= t_s:
                lo = mid
            else:
                hi = mid
        a, b = pts[lo], pts[hi]
        f = (t_s - a.t_s) / (b.t_s - a.t_s)
        return Point(t_s, a.x_um + f * (b.x_um - a.x_um), a.y_um + f * (b.y_um - a.y_um),
                     a.z_um + f * (b.z_um - a.z_um))


@dataclass(frozen=True)
class Pattern:
    id: str
    name: str
    tracks: tuple[Track, ...]
    loop: bool = False
    notes: str = ""
    meta: dict[str, Any] = field(default_factory=dict)  # created_at, updated_at, by

    @property
    def duration_s(self) -> float:
        return max(t.duration_s for t in self.tracks)

    def at(self, t_s: float) -> dict[str, Point]:
        """Every target's position at ``t_s``; with ``loop`` the time wraps."""
        d = self.duration_s
        if self.loop and d > 0:
            t_s = t_s % d
        return {t.target: t.at(t_s) for t in self.tracks}

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": FORMAT_VERSION, "id": self.id, "name": self.name, "loop": self.loop,
            "notes": self.notes, "meta": dict(self.meta),
            "tracks": [{"target": t.target,
                        "points": [[p.t_s, p.x_um, p.y_um, p.z_um] for p in t.points]}
                       for t in self.tracks],
        }


def _range_for(target: str) -> Mapping[str, tuple[float, float]]:
    return PIEZO_RANGE_UM if target == "piezo" else TRAP_RANGE_UM


def _point(raw: Any, where: str) -> Point:
    if isinstance(raw, Mapping):
        vals = [raw.get("t_s"), raw.get("x_um", 0.0), raw.get("y_um", 0.0), raw.get("z_um", 0.0)]
    elif isinstance(raw, Sequence) and not isinstance(raw, str) and 1 <= len(raw) <= 4:
        vals = [*raw, *([0.0] * (4 - len(raw)))]
    else:
        raise PatternError(f"{where}: a point is [t_s, x_um, y_um, z_um]")
    try:
        nums = [float(v) for v in vals]
    except (TypeError, ValueError) as e:
        raise PatternError(f"{where}: not a number") from e
    if not all(math.isfinite(v) for v in nums):
        raise PatternError(f"{where}: not a finite number")
    return Point(*nums)


def check_track(target: str, points: Sequence[Any], where: str = "track") -> Track:
    m = _TARGET.match(str(target))
    if not m:
        raise PatternError(f"{where}: target must be 'piezo' or 'trap:N', not {target!r}")
    if m.group(2) is not None and int(m.group(2)) >= MAX_TRAPS:
        raise PatternError(f"{where}: trap {m.group(2)} (traps are 0..{MAX_TRAPS - 1})")
    if not points:
        raise PatternError(f"{where}: no points")
    if len(points) > MAX_POINTS:
        raise PatternError(f"{where}: {len(points)} points (at most {MAX_POINTS})")
    pts = tuple(_point(p, f"{where} point {i}") for i, p in enumerate(points))
    if pts[0].t_s != 0.0:
        raise PatternError(f"{where}: the first point must be at t = 0 s")
    for i in range(1, len(pts)):
        if pts[i].t_s <= pts[i - 1].t_s:
            raise PatternError(f"{where} point {i}: time must go up "
                               f"({pts[i].t_s} s after {pts[i - 1].t_s} s)")
    if pts[-1].t_s > MAX_DURATION_S:
        raise PatternError(f"{where}: lasts {pts[-1].t_s} s (at most {MAX_DURATION_S:g} s)")
    for i, p in enumerate(pts):
        for axis, (lo, hi) in _range_for(target).items():
            v = getattr(p, f"{axis}_um")
            if not lo <= v <= hi:
                raise PatternError(f"{where} point {i}: {axis} {v:g} um is outside "
                                   f"{lo:g}..{hi:g} um (provisional {target} range)")
    return Track(str(target), pts)


def pattern_from_dict(raw: Mapping[str, Any], *, pattern_id: str | None = None) -> Pattern:
    """Check a pattern (from JSON) and build it. ``pattern_id`` overrides the id in ``raw``."""
    if not isinstance(raw, Mapping):
        raise PatternError("a pattern is a JSON object")
    version = raw.get("version", FORMAT_VERSION)
    if version != FORMAT_VERSION:
        raise PatternError(f"unknown pattern version {version!r}")
    pid = pattern_id if pattern_id is not None else raw.get("id")
    if not isinstance(pid, str) or not PATTERN_ID.match(pid):
        raise PatternError("id: lower-case letters, digits, '-' and '_', at most 64")
    name = " ".join(str(raw.get("name") or pid).split())
    if len(name) > MAX_NAME:
        raise PatternError(f"name is longer than {MAX_NAME} characters")
    tracks_raw = raw.get("tracks")
    if not isinstance(tracks_raw, Sequence) or isinstance(tracks_raw, str) or not tracks_raw:
        raise PatternError("a pattern needs at least one track")
    tracks = []
    for i, t in enumerate(tracks_raw):
        if not isinstance(t, Mapping):
            raise PatternError(f"track {i}: not an object")
        tracks.append(check_track(t.get("target", ""), t.get("points") or [],
                                  f"track {i} ({t.get('target', '?')})"))
    targets = [t.target for t in tracks]
    if len(set(targets)) != len(targets):
        raise PatternError("each target may have one track only")
    meta = raw.get("meta") if isinstance(raw.get("meta"), Mapping) else {}
    return Pattern(pid, name, tuple(tracks), loop=bool(raw.get("loop", False)),
                   notes=str(raw.get("notes", ""))[:2000], meta=dict(meta))
