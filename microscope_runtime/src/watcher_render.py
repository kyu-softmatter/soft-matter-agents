"""The run-time watcher's renderer (card 076 part A, plan.md 13.4 items 4 and 5).

ONE PURE FUNCTION WITH A VERSION. It turns a frame, the latest hardware
snapshot and the recent log into text, and the same inputs give the same
bytes. Standard library and numpy only; it imports no device module and
holds no core. Frames never leave it: what goes out is text, and, when the
plan gives images, two 8-bit conversions made here.

What it renders, by name (an option's `about` must be one of these):

    focus_score, mean, median, p999, max, saturated_fraction
        every statistic the copied focus_classical.frame_stats returns, with
        the plan's metric, bin_px and camera ceiling. With the ceiling a gap
        the saturated fraction is absent and the absence names the gap.
    intensity_normalised
        the whole-frame total over the SETTLED level. Never read through a
        mask fixed at frame 0, never normalised to frame 0.
    drift_px, drift_dy_px, drift_dx_px
        the whole-frame shift against the plan's reference frame.
    particle_count
        from a deterministic detector whose arguments are the plan's.

A value with no input is None with `absent_because`, and is rendered as
absent. It is never zero. No argument has a default: a plan block that lacks
one is refused, and the run goes on without a watcher.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
import zlib
from pathlib import Path

import numpy as np

#: Bump on any change to the text a state renders to, or to a value's meaning.
RENDERER_VERSION = "watcher-render-1"
#: Bump on any change to the image conversion.
CONVERSION_VERSION = "watcher-image-1"

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)                             # type: ignore[union-attr]
    return module


fc = _load("_focus_classical_for_watcher_render", _HERE / "focus_classical.py")

FRAME_VALUES = ("focus_score", "mean", "median", "p999", "max", "saturated_fraction")
DERIVED_VALUES = ("intensity_normalised", "drift_px", "drift_dy_px", "drift_dx_px", "particle_count")
RENDERED_NAMES = frozenset(FRAME_VALUES + DERIVED_VALUES)

DRIFT_METHOD = "phase_correlation"
PARTICLE_DETECTOR = "log_blob"
DOWNSCALE_METHOD = "area_mean"
STRETCH_METHOD = "percentile"
SATURATED_MARK = "red"


class RenderRefused(ValueError):
    """The plan asks for something this renderer does not render, or an input is missing."""


# --------------------------------------------------------------------------- #
# What the plan may ask for
# --------------------------------------------------------------------------- #

def _whole_number(value, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _positive_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def check_plan_block(block: dict) -> None:
    """Refuse a watcher block this renderer cannot render, naming what and why.

    The run then records `watcher_off`, `did_not_start`, and goes on: a watcher
    that cannot be built is not a gate on the run.
    """
    for option in block.get("options") or []:
        about = option.get("about")
        if about is not None and about not in RENDERED_NAMES:
            raise RenderRefused(
                f"option {option.get('id')!r} is about {about!r}, which renderer {RENDERER_VERSION} "
                f"does not render; it renders {sorted(RENDERED_NAMES)}")
    image = block.get("image") or {}
    stats = image.get("frame_stats") or {}
    if stats.get("metric") not in fc.METRICS:
        raise RenderRefused(f"frame_stats metric {stats.get('metric')!r} is not one of {sorted(fc.METRICS)}")
    drift = image.get("drift")
    if drift is not None:
        if drift.get("method") != DRIFT_METHOD:
            raise RenderRefused(f"drift method {drift.get('method')!r} is not rendered; "
                                f"only {DRIFT_METHOD!r} is")
        args = drift.get("arguments") or {}
        if set(args) != {"upsample"} or not _whole_number(args.get("upsample"), 1):
            raise RenderRefused("drift arguments must be exactly {'upsample': a whole number >= 1}, "
                                f"and the plan gives {args!r}")
    particles = image.get("particles")
    if particles is not None:
        if particles.get("detector") != PARTICLE_DETECTOR:
            raise RenderRefused(f"particle detector {particles.get('detector')!r} is not rendered; "
                                f"only {PARTICLE_DETECTOR!r} is")
        args = particles.get("arguments") or {}
        if (set(args) != {"sigma_px", "threshold", "min_separation_px"}
                or not _positive_number(args.get("sigma_px"))
                or not _positive_number(args.get("threshold"))
                or not _whole_number(args.get("min_separation_px"), 1)):
            raise RenderRefused(
                "log_blob arguments must be exactly sigma_px > 0, threshold > 0 and a whole "
                f"min_separation_px >= 1, and the plan gives {args!r}")
    frames = image.get("frames")
    if frames is None or not isinstance(frames.get("given"), bool):
        raise RenderRefused("image.frames.given is not stated, and whether images leave the "
                            "building is not a thing to guess")
    if frames["given"]:
        check_conversion(frames.get("conversion"))


def check_conversion(conversion) -> None:
    if not isinstance(conversion, dict):
        raise RenderRefused("frames.given is true and the plan gives no conversion")
    down, stretch, sat = (conversion.get("downscale") or {}, conversion.get("stretch") or {},
                          conversion.get("saturated") or {})
    if down.get("method") != DOWNSCALE_METHOD or not _whole_number(down.get("longest_side_px"), 1):
        raise RenderRefused(f"downscale must be {DOWNSCALE_METHOD!r} with a whole longest_side_px "
                            f">= 1, and the plan gives {down!r}")
    low, high = stretch.get("low_percentile"), stretch.get("high_percentile")
    if (stretch.get("method") != STRETCH_METHOD or not isinstance(low, (int, float))
            or not isinstance(high, (int, float)) or not 0 <= low < high <= 100):
        raise RenderRefused(f"stretch must be {STRETCH_METHOD!r} with 0 <= low < high <= 100, "
                            f"and the plan gives {stretch!r}")
    if sat.get("marked_as") != SATURATED_MARK:
        raise RenderRefused(f"saturated pixels can be marked only as {SATURATED_MARK!r}, "
                            f"and the plan gives {sat!r}")


def resolve_ceiling(block: dict, plan: dict) -> tuple[int | None, str | None]:
    """The camera ceiling in ADU and None, or None and the gap's name. Never a guess."""
    spec = block["image"]["frame_stats"]["camera_ceiling"]
    if "gap" in spec:
        return None, spec["gap"]
    for number in plan.get("numbers") or []:
        if number.get("name") == spec["number"]:
            value = number.get("value")
            if _positive_number(value) and float(value) == int(value):
                return int(value), None
            raise RenderRefused(f"camera ceiling {spec['number']!r} is {value!r}, not a count in ADU")
    raise RenderRefused(f"camera ceiling names {spec['number']!r}, which is not in the plan's numbers")


# --------------------------------------------------------------------------- #
# The image-side values
# --------------------------------------------------------------------------- #

def _value(value, unit, method, arguments, frame_index, absent_because=None) -> dict:
    out = {"value": value, "unit": unit, "method": method, "arguments": arguments,
           "frame_index": frame_index}
    if value is None:
        out["absent_because"] = absent_because or "no input"
    return out


def phase_correlation(reference: np.ndarray, moving: np.ndarray, upsample: int) -> tuple[float, float]:
    """The whole-frame shift (dy, dx) of `moving` against `reference`, to 1/upsample pixel.

    The frames are mean-subtracted, cross-correlated in phase, and the peak is
    refined by a parabola through its neighbours and rounded to 1/upsample.
    Positive dy means the content moved toward larger row numbers.
    """
    a = np.asarray(reference, dtype=np.float64)
    b = np.asarray(moving, dtype=np.float64)
    if a.shape != b.shape:
        raise RenderRefused(f"drift: frame {b.shape} and reference {a.shape} differ in shape")
    a = a - a.mean()
    b = b - b.mean()
    cross = np.conj(np.fft.fft2(a)) * np.fft.fft2(b)
    magnitude = np.abs(cross)
    magnitude[magnitude == 0] = 1.0
    corr = np.abs(np.fft.ifft2(cross / magnitude))
    peak = np.unravel_index(int(np.argmax(corr)), corr.shape)
    shift = []
    for axis in (0, 1):
        n = corr.shape[axis]
        i = int(peak[axis])
        lo = corr[tuple(((i - 1) % n if k == axis else peak[k]) for k in (0, 1))]
        mid = corr[tuple(peak)]
        hi = corr[tuple(((i + 1) % n if k == axis else peak[k]) for k in (0, 1))]
        denom = lo - 2 * mid + hi
        delta = 0.5 * (lo - hi) / denom if denom != 0 else 0.0
        position = i + delta
        if position > n / 2:
            position -= n
        shift.append(round(position * upsample) / upsample)
    return float(shift[0]), float(shift[1])


def _shift_filter(padded: np.ndarray, kernel: np.ndarray, axis: int) -> np.ndarray:
    windows = np.lib.stride_tricks.sliding_window_view(padded, len(kernel), axis=axis)
    return windows @ kernel


def _filter(img: np.ndarray, kernel: np.ndarray, axis: int) -> np.ndarray:
    r = len(kernel) // 2
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r, r)
    return _shift_filter(np.pad(img, pad, mode="reflect"), kernel, axis)


def log_blob_count(frame: np.ndarray, sigma_px: float, threshold: float, min_separation_px: int) -> int:
    """Bright blobs by a scale-normalised Laplacian of Gaussian on the frame's own range.

    The frame is shifted to its median and divided by (max - median), so the
    plan's `threshold` is a fraction of the frame's own bright range. A
    detection is a local maximum of the response within `min_separation_px`
    that reaches the threshold. Deterministic: no random numbers, no tie-break
    by order beyond the maximum filter.
    """
    a = np.asarray(frame, dtype=np.float64)
    med = float(np.median(a))
    top = float(a.max())
    if not top > med:
        return 0
    n = (a - med) / (top - med)
    r = int(np.ceil(4 * sigma_px))
    x = np.arange(-r, r + 1, dtype=np.float64)
    g = np.exp(-x ** 2 / (2 * sigma_px ** 2)) / (sigma_px * np.sqrt(2 * np.pi))
    g2 = (x ** 2 / sigma_px ** 4 - 1 / sigma_px ** 2) * g
    lap = _filter(_filter(n, g2, 1), g, 0) + _filter(_filter(n, g, 1), g2, 0)
    response = -(sigma_px ** 2) * lap
    w = int(min_separation_px)
    biggest = response.copy()
    for axis in (0, 1):
        stacked = biggest                      # the second pass filters the first pass's result
        best = stacked.copy()
        for shift in range(1, w + 1):
            for sign in (-1, 1):
                moved = np.roll(stacked, sign * shift, axis=axis)
                np.maximum(best, moved, out=best)
        biggest = best
    peaks = (response >= biggest) & (response >= threshold)
    return int(peaks.sum())


def image_values(inp: dict) -> dict:
    """Every image-side value by name, each with unit, method, arguments and frame."""
    block_image = inp["block"]["image"]
    stats_args = block_image["frame_stats"]
    frame, index = inp.get("frame"), inp.get("frame_index")
    ceiling, gap = inp.get("ceiling"), inp.get("ceiling_gap")
    names = {}
    no_frame = "no frame has arrived in this run yet"
    stat_args = {"metric": stats_args["metric"], "bin_px": stats_args["bin_px"], "ceiling": ceiling}
    if frame is None:
        for name in FRAME_VALUES:
            names[name] = _value(None, "ADU" if name in ("mean", "median", "p999", "max") else "1",
                                 "frame_stats", stat_args, None, no_frame)
    else:
        a = np.asarray(frame)
        if ceiling is None:
            # frame_stats wants a ceiling for the saturated fraction; with a gap there is none, so
            # it is called with one no pixel can reach and that fraction is thrown away unread.
            s = fc.frame_stats(a.astype(np.float64), stats_args["metric"],
                               ceiling=float(a.max()) + 1.0, bin_px=stats_args["bin_px"])
        else:
            s = fc.frame_stats(a, stats_args["metric"], ceiling=ceiling, bin_px=stats_args["bin_px"])
        names["focus_score"] = _value(s.score, "1", "frame_stats", stat_args, index)
        names["mean"] = _value(s.mean, "ADU", "frame_stats", stat_args, index)
        names["median"] = _value(s.median, "ADU", "frame_stats", stat_args, index)
        names["p999"] = _value(s.p999, "ADU", "frame_stats", stat_args, index)
        names["max"] = _value(float(s.max), "ADU", "frame_stats", stat_args, index)
        if ceiling is None:
            names["saturated_fraction"] = _value(
                None, "1", "frame_stats", stat_args, index,
                f"the camera ceiling is the gap {gap!r}, so there is no count to compare against")
        else:
            names["saturated_fraction"] = _value(s.saturated_fraction, "1", "frame_stats", stat_args, index)
    # intensity
    settle = block_image["intensity"]["settle_after_s"]
    arg = {"settle_after_s": settle}
    if frame is None:
        names["intensity_normalised"] = _value(None, "1", "whole_frame_total", arg, None, no_frame)
    elif inp.get("level") is None:
        names["intensity_normalised"] = _value(
            None, "1", "whole_frame_total", arg, index,
            inp.get("level_absent_because") or "settling: no settled level yet")
    else:
        total = float(np.asarray(frame, dtype=np.float64).sum())
        names["intensity_normalised"] = _value(total / float(inp["level"]), "1", "whole_frame_total",
                                               arg, index)
    # drift
    drift = block_image.get("drift")
    if drift is not None:
        up = drift["arguments"]["upsample"]
        d_arg = {"upsample": up, "reference_frame": drift["reference_frame"]}
        why = None
        if frame is None:
            why = no_frame
        elif inp.get("reference") is None:
            why = f"reference frame {drift['reference_frame']} has not been seen in this run"
        if why is not None:
            for name in ("drift_px", "drift_dy_px", "drift_dx_px"):
                names[name] = _value(None, "px", DRIFT_METHOD, d_arg, index, why)
        else:
            dy, dx = phase_correlation(inp["reference"], frame, up)
            names["drift_px"] = _value(float(np.hypot(dy, dx)), "px", DRIFT_METHOD, d_arg, index)
            names["drift_dy_px"] = _value(dy, "px", DRIFT_METHOD, d_arg, index)
            names["drift_dx_px"] = _value(dx, "px", DRIFT_METHOD, d_arg, index)
    # particles
    particles = block_image.get("particles")
    if particles is not None:
        p = particles["arguments"]
        if frame is None:
            names["particle_count"] = _value(None, "1", PARTICLE_DETECTOR, p, None, no_frame)
        else:
            count = log_blob_count(frame, p["sigma_px"], p["threshold"], p["min_separation_px"])
            names["particle_count"] = _value(count, "1", PARTICLE_DETECTOR, p, index)
    return names


# --------------------------------------------------------------------------- #
# The reduced images (plan.md 13.4 item 4, since 2026-10-19)
# --------------------------------------------------------------------------- #

def _png_rgb8(arr: np.ndarray) -> bytes:
    """A PNG of an HxWx3 uint8 array. Fixed filter, fixed compression, no clock: same bytes."""
    h, w, _ = arr.shape
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def convert_frame(frame, conversion: dict, ceiling: int | None, limits: dict | None = None):
    """One 8-bit image from a raw frame: PNG bytes and what was done, or RenderRefused.

    Downscale by block mean to at most `longest_side_px`, stretch between the
    two percentiles of the RAW frame (their values, in raw ADU, are returned so
    the image can be rebuilt from the raw frame), and mark every block holding
    a pixel at or above the camera ceiling in red. With the ceiling a gap it
    refuses: saturated pixels are never marked against an assumed count. The
    raw frame is not returned and not referenced by anything returned.
    """
    if ceiling is None:
        raise RenderRefused("the camera ceiling is a gap, so saturated pixels cannot be marked, and "
                            "an image is not made against an assumed count")
    check_conversion(conversion)
    a = np.asarray(frame)
    if a.ndim != 2:
        raise RenderRefused(f"a frame of shape {a.shape} is not a 2-D image")
    longest = conversion["downscale"]["longest_side_px"]
    factor = max(1, -(-max(a.shape) // longest))
    h, w = a.shape[0] // factor, a.shape[1] // factor
    if h < 1 or w < 1:
        raise RenderRefused(f"a frame of {a.shape} is smaller than one {factor} x {factor} block")
    cut = a[:h * factor, :w * factor]
    small = cut.astype(np.float64).reshape(h, factor, w, factor).mean(axis=(1, 3))
    marked = (cut >= ceiling).reshape(h, factor, w, factor).any(axis=(1, 3))
    if limits is None:
        s = conversion["stretch"]
        low = float(np.percentile(a, s["low_percentile"]))
        high = float(np.percentile(a, s["high_percentile"]))
    else:
        low, high = float(limits["low"]), float(limits["high"])
    if not high > low:
        raise RenderRefused(f"the stretch limits are {low} and {high}: a flat frame has no contrast to stretch")
    gray = np.rint(np.clip((small - low) / (high - low), 0.0, 1.0) * 255.0).astype(np.uint8)
    rgb = np.stack([gray, gray, gray], axis=-1)
    rgb[marked] = (255, 0, 0)
    data = _png_rgb8(rgb)
    # The run log records an image's shape as [height, width].
    return data, {"shape": [int(h), int(w)], "stretch_limits": {"low": low, "high": high},
                  "saturated_pixels": int((a >= ceiling).sum()),
                  "conversion_version": CONVERSION_VERSION,
                  "sha256": hashlib.sha256(data).hexdigest()}


# --------------------------------------------------------------------------- #
# The text
# --------------------------------------------------------------------------- #

def _num(x) -> str:
    if isinstance(x, bool) or x is None:
        return str(x)
    if isinstance(x, int):
        return str(x)
    return format(float(x), ".6g")


def _compact(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


#: The keys of a log event a state shows, in this order. Everything else stays in the log.
EVENT_KEYS = ("channel", "element", "action", "verification", "criterion", "target", "id", "how", "error")
#: Events a state never lists: the watcher's own, and the snapshots it is already given whole.
EVENT_SKIP = frozenset({"snapshot", "watcher_started", "watcher_off", "watcher_state", "watcher_flag",
                        "watcher_unanswered", "run_started"})


def render(inp: dict) -> tuple[str, dict]:
    """The state text, and the image-side values it was made from. Pure and versioned."""
    values = image_values(inp)
    lines = [f"WATCHER STATE (renderer {RENDERER_VERSION})",
             f"seq {inp['seq']}; tick at t_mono {_num(inp['tick_t_mono'])} s"]
    frame_index = inp.get("frame_index")
    frame_t = inp.get("frame_t_mono")
    lines.append("frame: none yet" if frame_index is None
                 else f"frame: index {frame_index}, arrived at t_mono {_num(frame_t)} s "
                      f"(age {_num(inp['tick_t_mono'] - frame_t)} s)")
    snap = inp.get("snapshot")
    lines.append("snapshot: none yet" if snap is None
                 else f"snapshot: t_mono {_num(snap['t_mono'])} s (age {_num(inp['tick_t_mono'] - snap['t_mono'])} s)")
    lines.append("")
    lines.append("IMAGE VALUES")
    for name in FRAME_VALUES + DERIVED_VALUES:
        if name not in values:
            continue
        v = values[name]
        src = "no frame" if v["frame_index"] is None else f"frame {v['frame_index']}"
        if v["value"] is None:
            lines.append(f"{name}: absent ({v['absent_because']}) [{v['method']}, {_compact(v['arguments'])}]")
        else:
            lines.append(f"{name} = {_num(v['value'])} {v['unit']} [{v['method']}, "
                         f"{_compact(v['arguments'])}, {src}]")
    lines.append("")
    lines.append("HARDWARE")
    channels = inp.get("channels") or {}
    states = (snap or {}).get("states") or {}
    if snap is None:
        lines.append("no snapshot has been taken yet")
    for cid in sorted(states):
        state = states[cid]
        meta = channels.get(cid) or {}
        if isinstance(state, dict) and state.get("not_open"):
            lines.append(f"{cid}: not open in this run ({state.get('why')})")
        elif isinstance(state, dict) and state.get("not_read"):
            lines.append(f"{cid}: not read at this tick ({state.get('why')})")
        elif meta.get("read_back") is False:
            commanded = state.get("commanded") if isinstance(state, dict) else None
            lines.append(f"{cid}: unreadable, no read-back exists; last commanded "
                         f"{_compact(commanded) if commanded is not None else 'nothing'} (commanded, not read)")
        else:
            lines.append(f"{cid}: {_compact(state)} (read at snapshot t_mono {_num(snap['t_mono'])} s)")
    lines.append("")
    lines.append("RECENT EVENTS (since the previous tick)")
    shown = 0
    for event in inp.get("events") or []:
        if event.get("event") in EVENT_SKIP:
            continue
        parts = [f"t_mono {_num(event.get('t_mono'))}", str(event.get("event"))]
        for key in EVENT_KEYS:
            if event.get(key) is not None:
                parts.append(f"{key}={event[key]}")
        if event.get("params") is not None:
            parts.append(f"params={_compact(event['params'])}")
        lines.append("; ".join(parts))
        shown += 1
    if not shown:
        lines.append("none")
    return "\n".join(lines) + "\n", values
