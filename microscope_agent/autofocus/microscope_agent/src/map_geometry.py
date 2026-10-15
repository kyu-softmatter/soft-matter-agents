# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/src/map_geometry.py
# body-sha256: f9d96d68d4a2c6dd53a3fa411816ed220c1b4704568fe0e9bc39fd403c000a13
"""Stage <-> camera geometry and the sample geometry values, pure (no hardware, no guards).

Camera convention (PLAN v1.2, the 2026-09-30 run): the camera image is mirrored against the
stage. M is the stage-camera calibration in px per um (``d_pixels = M @ d_stage``, as
edge_trace measures it), and the stage point imaged at pixel p = (col, row) of a frame taken
at stage t is

    stage = t + inv(M) @ (centre - p),      centre = ((w - 1) / 2, (h - 1) / 2)

Sample geometry (F3, WP-H). ``GEOMETRY_FIELDS`` is the one list of geometry fields
(the sample screen spec, section 2); the server serves it and the screen renders from it.
Values are entered as ``geometry_set`` sample events; ``geometry_view`` and ``loading_view``
project the folded events into what the screens show. Sample thickness and orientation have
no default on purpose: a guessed safety value must not look entered.

``hole_loop`` tells a closed hole trace from a partial arc (the re-trace rule and scan_4x).

Flat file in the soft-matter-agents layout (integration-sma.md section 9): stdlib +
numpy only. The engine's ``sample`` and ``mosaic`` modules re-export these names.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

GRADE_MODEL = "model"  # the engine's records.GRADE_MODEL


# ---------------------------------------------------------------- stage <-> camera
def um_per_px(M: Any) -> float:
    return 1.0 / math.sqrt(abs(float(np.linalg.det(np.asarray(M, float)))))


def calibration_of(M: np.ndarray) -> dict:
    """um/px and image angle of a px-per-um matrix (edge_track.py's cal_result fields)."""
    um_px = 1 / math.sqrt(abs(float(np.linalg.det(M))))
    angle = math.degrees(math.atan2(M[1, 0], M[0, 0]))
    return {"M_px_per_um": np.asarray(M, float).tolist(), "um_per_px": um_px,
            "angle_deg": angle}


def tile_pixel_to_stage(M: Any, tile_um: Sequence[float], col: float, row: float,
                        shape: Sequence[int]) -> tuple[float, float]:
    """Stage (x, y) um of pixel (col, row) in a tile of `shape` (rows, cols) taken at `tile_um`."""
    h, w = int(shape[0]), int(shape[1])
    centre = np.array([(w - 1) / 2, (h - 1) / 2])
    xy = np.asarray(tile_um, float) + np.linalg.solve(np.asarray(M, float),
                                                      centre - np.array([col, row], float))
    return float(xy[0]), float(xy[1])


def stage_to_tile_pixel(M: Any, tile_um: Sequence[float], x_um: float, y_um: float,
                        shape: Sequence[int]) -> tuple[float, float]:
    """Pixel (col, row) of stage (x, y) in a tile taken at `tile_um`: centre - M @ (q - t)."""
    h, w = int(shape[0]), int(shape[1])
    centre = np.array([(w - 1) / 2, (h - 1) / 2])
    p = centre - np.asarray(M, float) @ (np.array([x_um, y_um], float) - np.asarray(tile_um))
    return float(p[0]), float(p[1])


# ---------------------------------------------------------------- sample geometry
ORIENTATIONS = ("upright", "flipped")  # the sample screen spec; F3.1 not yet confirmed
CHAMBER_SHAPES = ("hole",)  # more to come (screen gap G5)

# sample event kinds (records.events.fold keeps them in .other)
GEOMETRY_SET = "geometry_set"  # payload: values {key: value}
LOADING_STEP = "loading_step"  # payload: step ("person" | "image"), ok, why, result_ref
LOADING_STEPS = ("person", "image")


@dataclass(frozen=True)
class GeometryField:
    key: str
    label: str
    kind: str  # "number" | "pair" | "choice"
    unit: str | None
    choices: tuple[str, ...] | None
    default: Any
    safety: bool  # feeds a safety limit (working distance, focus search range)


# provisional: PLAN section 10, F3.1 is not confirmed by the user
GEOMETRY_FIELDS: tuple[GeometryField, ...] = (
    GeometryField("sample_size_mm", "Sample size", "pair", "mm", None, (24.0, 50.0), False),
    GeometryField("chamber_shape", "Chamber", "choice", None, CHAMBER_SHAPES, "hole", False),
    GeometryField("hole_diameter_mm", "Hole diameter", "number", "mm", None, None, False),
    GeometryField("coverslip_thickness_um", "Coverslip thickness", "number", "um", None,
                  170.0, True),
    GeometryField("sample_thickness_um", "Sample thickness", "number", "um", None, None, True),
    GeometryField("orientation", "Orientation", "choice", None, ORIENTATIONS, None, True),
)
FIELDS_BY_KEY = {f.key: f for f in GEOMETRY_FIELDS}
SAFETY_KEYS = tuple(f.key for f in GEOMETRY_FIELDS if f.safety)


class GeometryError(ValueError):
    """A geometry value the engine refuses; the op reports it as preflight_failed."""


def _is_graded(v: Any) -> bool:
    """A graded value (the engine's ``records.Graded`` or the like): value + grade."""
    return hasattr(v, "grade") and hasattr(v, "value")


def _number(key: str, v: Any) -> float:
    if _is_graded(v):
        if v.grade == GRADE_MODEL:
            raise GeometryError(f"{key}: a model output cannot be a geometry value")
        v = v.value
    if isinstance(v, bool):
        raise GeometryError(f"{key}: {v!r} is not a number")
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise GeometryError(f"{key}: {v!r} is not a number") from None
    if not math.isfinite(f) or f <= 0:
        raise GeometryError(f"{key}: {f} must be a positive number")
    return f


def validate_geometry(values: dict[str, Any]) -> dict[str, Any]:
    """Checked, normalised copy of `values` (keys of GEOMETRY_FIELDS only)."""
    if not isinstance(values, dict) or not values:
        raise GeometryError("no geometry values given")
    out: dict[str, Any] = {}
    for key, v in values.items():
        f = FIELDS_BY_KEY.get(key)
        if f is None:
            raise GeometryError(f"unknown geometry field {key!r}; known: {list(FIELDS_BY_KEY)}")
        if f.kind == "number":
            out[key] = _number(key, v)
        elif f.kind == "pair":
            if not isinstance(v, (list, tuple)) or len(v) != 2:
                raise GeometryError(f"{key}: {v!r} is not a pair of numbers")
            out[key] = [_number(key, v[0]), _number(key, v[1])]
        else:
            if v not in (f.choices or ()):
                raise GeometryError(f"{key}: {v!r} is not one of {list(f.choices or ())}")
            out[key] = v
    return out


class SampleGeometry:
    """Geometry values keyed by GEOMETRY_FIELDS, for the sample.json derived view.

    Keys this class does not know are kept in `extra` and written back, so a file from a
    newer writer still loads. Values are not validated here; ops call validate_geometry."""

    def __init__(self, extra: dict[str, Any] | None = None, **values: Any):
        self.values = {k: v for k, v in values.items() if k in FIELDS_BY_KEY}
        self.extra = {**(extra or {}),
                      **{k: v for k, v in values.items() if k not in FIELDS_BY_KEY}}

    def get(self, key: str) -> Any:
        return self.values.get(key, FIELDS_BY_KEY[key].default)

    def to_dict(self) -> dict[str, Any]:
        return {**self.extra, **self.values}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SampleGeometry:
        d = dict(d)
        extra = d.pop("extra", None)
        return cls(extra if isinstance(extra, dict) else None, **d)

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, SampleGeometry) and self.values == other.values
                and self.extra == other.extra)

    def __repr__(self) -> str:
        return f"SampleGeometry({self.to_dict()!r})"


def _source(kind: str, by: str | None = None, t: str | None = None) -> dict[str, Any]:
    return {"kind": kind, "by": by, "t": t}


def geometry_view(entries: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """{key: GeometryValue} from folded sample events in fold order (records.events.fold's
    `.other`): the last entered value wins; else the default; else not_set."""
    view = {f.key: ({"value": None, "source": _source("not_set")} if f.default is None else
                    {"value": list(f.default) if f.kind == "pair" else f.default,
                     "source": _source("default")})
            for f in GEOMETRY_FIELDS}
    for e in entries:
        if e.get("kind") != GEOMETRY_SET:
            continue
        for key, v in (e.get("values") or {}).items():
            if key in view:
                view[key] = {"value": v, "source": _source("entered", e.get("user_id"),
                                                           e.get("t"))}
    return view


def loading_view(entries: Iterable[dict[str, Any]], session_id: str | None) -> dict[str, Any]:
    """LoadingState for the open session (the sample screen spec, sections 3 and 6).

    Step 1 is done when every safety field has an entered or default value. Steps 2 and 3
    count only in `session_id`, and a change of a safety value after them clears them
    (screen decision G6). `confirmed` needs all three, with the image check ok."""
    entries = list(entries)
    geo: dict[str, Any] = {}
    person: dict[str, Any] | None = None
    image: dict[str, Any] | None = None
    last_geo: dict[str, Any] | None = None
    for e in entries:
        if e.get("kind") == GEOMETRY_SET:
            values = e.get("values") or {}
            changed = [k for k in SAFETY_KEYS if k in values and geo.get(k) != values[k]]
            geo.update(values)
            if changed:
                last_geo = e
                person = image = None  # G6: a safety change after confirmation clears 2-3
        elif e.get("kind") == LOADING_STEP and session_id and e.get("session_id") == session_id:
            if e.get("step") == "person":
                person = e
            elif e.get("step") == "image":
                image = e
    gview = geometry_view(entries)
    geo_done = all(gview[k]["source"]["kind"] in ("entered", "default") for k in SAFETY_KEYS)
    out = {
        "session_id": session_id,
        "geometry": {"done": geo_done, "by": (last_geo or {}).get("user_id"),
                     "t": (last_geo or {}).get("t")},
        "person": {"done": person is not None, "by": (person or {}).get("user_id"),
                   "t": (person or {}).get("t")},
        "image": {"done": image is not None, "ok": bool((image or {}).get("ok")),
                  "by": (image or {}).get("user_id"), "t": (image or {}).get("t"),
                  "why": (image or {}).get("why"), "result_ref": (image or {}).get("result_ref")},
    }
    out["confirmed"] = geo_done and person is not None and image is not None and out["image"]["ok"]
    return out


# ---------------------------------------------------------------- the hole fit
# A hole fit counts as a closed loop when edge_trace stopped on its full-loop condition,
# or (fits without trace_stop, e.g. 2026-09-30's 352 deg) when the arc covers at least
# this much. Unmeasured provisional.
FULL_LOOP_ARC_DEG = 330.0
FULL_LOOP_STOP = "full loop"  # edge_trace: "back where the edge was first seen: full loop"


def hole_loop(hole: dict[str, Any] | None) -> dict[str, Any]:
    """{closed, why, fitted_at, trace_stop, arc_deg} for a hole fit, next to fitted_at, so
    the re-trace rule and scan_4x can tell a partial arc from a full fit.

    edge_trace's boolean `closed_loop` flag decides when the fit has it; the trace_stop
    text and FULL_LOOP_ARC_DEG are kept only for older fits without the flag."""
    if not hole:
        return {"closed": False, "why": "no hole fit", "fitted_at": None, "trace_stop": None,
                "arc_deg": None}
    stop, arc = hole.get("trace_stop"), hole.get("arc_deg")
    try:
        arc_f = None if arc is None else float(arc)
    except (TypeError, ValueError):
        arc_f = None
    flag = hole.get("closed_loop")  # edge_trace's own flag (T-032)
    if isinstance(flag, bool):
        closed = flag
        why = "edge_trace: closed loop" if flag else f"edge_trace: partial trace ({stop})"
    elif stop is not None and FULL_LOOP_STOP in str(stop):
        closed, why = True, f"trace stopped on a full loop ({stop})"
    elif stop is not None:
        closed, why = False, f"partial trace: {stop}"
    elif arc_f is not None and arc_f >= FULL_LOOP_ARC_DEG:
        closed, why = True, f"arc {arc_f:.0f} deg >= {FULL_LOOP_ARC_DEG:.0f} deg"
    else:
        closed = False
        why = ("no arc recorded" if arc_f is None else
               f"arc {arc_f:.0f} deg < {FULL_LOOP_ARC_DEG:.0f} deg")
    return {"closed": closed, "why": why, "fitted_at": hole.get("fitted_at"),
            "trace_stop": stop, "arc_deg": arc_f}
