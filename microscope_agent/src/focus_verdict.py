# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/src/focus_verdict.py
# body-sha256: 727286e55ac0f4b2b613e0bc0cc8d37b67e1c8bb7a9e8bfb18da6450b69e267c
"""Focus verdicts in the soft-matter-agents focus-seat vocabulary (task 026).

A verdict is **for display and for the record only**. It never sets a motion limit, never
opens a gate and never takes part in a safety decision: those are decided by the engine's
guards from encoder readbacks and fixed limits (PLAN design rules 2 and 3).

Vocabulary: ``in_focus | step_up | step_down | no_sample_here | unsure``.

* ``step_up`` means best focus lies *above* the current stage z: the focus drive should
  move up (larger ZDrive um). ``step_down`` the opposite. At 100x a step up is the
  operator's call (2026-09-30 rule); the verdict only reports it.
* The z of a verdict is the **encoder readback of a real frame** that was taken. It is never
  a model output and never an interpolated z. Computed numbers (a parabola vertex) are kept
  as evidence labelled with their origin kind.

The mapping here, ``from_sweep`` -- a classical z sweep (scores of frames at known encoder z):
  no frame with more than dark-level dynamic range -> ``no_sample_here``;
  too few readable frames or a flat curve -> ``unsure``;
  peak at the top of the span -> ``step_up``; at the bottom -> ``step_down``;
  peak inside -> ``in_focus`` at the real frame nearest the parabola vertex.

The model-reading mapping (``from_reading``, a signed DINO reading) lives in the sibling
``focus_verdict_model.py``: its inputs are model numbers (E6 in soft-matter-agents), so it
is kept apart and out of a copy until a place for model output exists there (plan.md 13.1).

Contract (D-07; ``test_focus_contract.py`` pins it, soft-matter-agents' card for the copy
cites it):

* Inputs of ``from_sweep``: ``z_um`` -- the encoder readback of each frame, floats, one per
  frame, in sweep order; ``stats`` -- one ``FrameStats`` per frame (``score``, ``metric``,
  ``mean``, ``median``, ``p999``, ``max``, ``saturated_fraction``), same order; and every
  threshold as a keyword argument with no default.
* Output: a ``FocusVerdict`` whose ``as_record()`` is JSON-native and has exactly the keys
  ``RECORD_KEYS``: ``verdict`` (one of ``VERDICTS``), ``source`` (one of ``SOURCES``),
  ``reason`` (a sentence), ``frame_index`` (an index into ``z_um`` or None), ``z_um`` (the
  readback at that index or None -- never a model value, never interpolated), ``evidence``
  (a list of ``{name, value, grade, unit}`` with ``grade`` in ``GRADES``) and ``z_grade``
  (``"measured"`` when ``z_um`` is set, else None).
* A verdict can refuse and cannot permit: it carries no limit, no target and no command.
* Each evidence item's ``grade`` field holds an origin kind (``GRADES``), not an evidence
  grade; a caller derives its own grade from it. Model output is not produced here: the
  model-reading verdict, its ``"dino"`` source and ``"model"`` kind live in
  ``focus_verdict_model.py``.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Literal

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


_classical = _load("_mic_focus_classical", "focus_classical.py")
FrameStats = _classical.FrameStats
analyse_sweep = _classical.analyse_sweep

# The thresholds (dynamic range floor in ADU, curve contrast, readable frames, in-focus
# band and model sigma ceiling in DoF, dropout tolerance, saturated fraction) are the
# caller's arguments: dino-autofocus keeps its provisional values in its bench_values
# module; soft-matter-agents carries them in the plan.

#: Origin kind of a number in a verdict record. "measured": read from the hardware (encoder
#: z, pixel statistics); "computed": deterministic from measured values (a classical metric,
#: a parabola vertex).
Grade = Literal["measured", "computed"]


class Verdict(StrEnum):
    IN_FOCUS = "in_focus"
    STEP_UP = "step_up"
    STEP_DOWN = "step_down"
    NO_SAMPLE_HERE = "no_sample_here"
    UNSURE = "unsure"


#: The contract's fixed vocabularies (soft-matter-agents plan.md 13.2 branches; what this
#: module produces) and the exact key set of ``FocusVerdict.as_record()``.
VERDICTS = tuple(str(v) for v in Verdict)
SOURCES = ("sweep",)
#: Origin kind of each number, not an evidence grade. A caller derives its own grade from
#: this; nothing here assigns one.
GRADES = ("measured", "computed")
RECORD_KEYS = ("verdict", "source", "reason", "frame_index", "z_um", "evidence", "z_grade")


@dataclass
class Evidence:
    name: str
    value: float | int | str | None
    grade: str  # an origin kind: one of GRADES here; a sibling file may add its own
    unit: str = ""


@dataclass
class FocusVerdict:
    verdict: Verdict
    source: str  # "sweep" here (SOURCES); a sibling file may name its own
    reason: str
    frame_index: int | None = None   # the real frame the verdict points at
    z_um: float | None = None        # that frame's encoder readback, never a model value
    evidence: list[Evidence] = field(default_factory=list)

    def as_record(self) -> dict[str, Any]:
        """JSON-ready dict (``json.dumps`` works on it as is)."""
        d = asdict(self)
        d["verdict"] = str(self.verdict)
        d["z_grade"] = None if self.z_um is None else "measured"
        return d


def _num(x: float | None) -> float | None:
    return None if x is None or not math.isfinite(x) else float(x)


# -- mapping 1: classical sweep -------------------------------------------------------------

def from_sweep(z_um: Sequence[float], stats: Sequence[FrameStats], *,
               min_dynamic_range_adu: float, min_contrast: float, min_frames: int,
               dropout_tolerance: float, max_saturated: float) -> FocusVerdict:
    """Verdict from a classical sweep. Every threshold is the caller's (no defaults).

    `z_um` is the encoder readback of each frame (not the commanded z), `stats` the
    ``classical.frame_stats`` of the same frames, in the same order.
    """
    if len(z_um) != len(stats):
        raise ValueError(f"{len(z_um)} z values but {len(stats)} frame stats")
    if not stats:
        return FocusVerdict(Verdict.UNSURE, "sweep", "empty sweep")
    metric = stats[0].metric
    ev = [Evidence("metric", metric, "computed"), Evidence("n_frames", len(stats), "measured")]
    dyn = max(s.p999 - s.median for s in stats)
    ev.append(Evidence("max_dynamic_range", dyn, "measured", "ADU"))
    if dyn < min_dynamic_range_adu:
        return FocusVerdict(Verdict.NO_SAMPLE_HERE, "sweep",
                            f"no frame has more than {dyn:.1f} ADU above its median "
                            f"(dark level < {min_dynamic_range_adu:g} ADU)", evidence=ev)

    a = analyse_sweep(z_um, [s.score for s in stats], means=[s.mean for s in stats],
                      saturated=[s.saturated_fraction for s in stats],
                      dropout_tolerance=dropout_tolerance, max_saturated=max_saturated)
    ev += [Evidence("n_kept", a.n_kept, "computed"),
           Evidence("dropout_z_um", str(a.dropped_z_um), "measured", "um"),
           Evidence("saturated_z_um", str(a.saturated_z_um), "measured", "um")]
    notes = "; ".join(a.notes)
    if a.n_kept < min_frames:
        return FocusVerdict(Verdict.UNSURE, "sweep",
                            f"only {a.n_kept} readable frames of {len(stats)}"
                            + (f" ({notes})" if notes else ""), evidence=ev)
    kept = [s.score for s, k in zip(stats, a.kept, strict=True) if k]
    hi, lo = max(kept), min(kept)
    contrast = (hi - lo) / max(abs(hi), abs(lo), 1e-12)  # numerical guard: an all-zero curve
    ev += [Evidence("curve_contrast", contrast, "computed"),
           Evidence("peak_edge", a.edge, "computed"),
           Evidence("z_vertex_um", _num(a.z_vertex_um), "computed", "um")]
    if contrast < min_contrast:
        return FocusVerdict(Verdict.UNSURE, "sweep",
                            f"flat curve: contrast {contrast:.3f} < {min_contrast:g}", evidence=ev)

    i = a.argmax_index
    assert i is not None  # n_kept >= min_frames >= 1
    if a.edge == "top":
        return FocusVerdict(Verdict.STEP_UP, "sweep",
                            "peak at the top of the span: focus may be higher",
                            frame_index=i, z_um=float(z_um[i]), evidence=ev)
    if a.edge == "bottom":
        return FocusVerdict(Verdict.STEP_DOWN, "sweep",
                            "peak at the bottom of the span: focus may be lower",
                            frame_index=i, z_um=float(z_um[i]), evidence=ev)
    j = a.nearest_index
    assert j is not None
    ev.append(Evidence("score_at_frame", stats[j].score, "computed"))
    return FocusVerdict(Verdict.IN_FOCUS, "sweep",
                        f"peak inside the span; nearest real frame to the vertex "
                        f"{a.z_vertex_um:.2f} um" + (f" ({notes})" if notes else ""),
                        frame_index=j, z_um=float(z_um[j]), evidence=ev)
