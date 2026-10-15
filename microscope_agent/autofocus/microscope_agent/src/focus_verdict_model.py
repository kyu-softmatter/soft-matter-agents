# origin: dino-autofocus, public since 2026-10-03:
#   https://github.com/kyu-softmatter/dino-autofocus/blob/ab4978710228bb7f392a1f9050b95dfb10b42a92/microscope_agent/src/focus_verdict_model.py
# body-sha256: f666a8e696ad91f1426355a8e216eecf15f2900f507a64b3490d15fced4e627f
"""The model-reading focus verdict: one frame's signed DINO reading -> a ``FocusVerdict``.

Kept apart from ``focus_verdict.py`` because its inputs are model numbers (E6 in
soft-matter-agents, which may enter no card): the classical verdict can be copied there
without it, and this file waits for a place for model output (that repository's plan.md
13.1, shadow mode).

``from_reading`` -- one frame's signed reading (the live module's ``FocusReading``), in DoF
units with dz = stage - best focus (positive: the stage is above focus): no tile with sample
signal -> ``no_sample_here``; tiles but none readable, or sigma above ``max_sigma_dof`` ->
``unsure``; ``|dz| <= in_focus_dof`` -> ``in_focus``; sign known (``|dz| > sigma``) ->
``step_down`` for dz > 0, ``step_up`` for dz < 0; else ``unsure``.

Inputs: an object with ``score``, ``sigma``, ``n_used``, ``tiles`` and ``sign_known``, the
frame's encoder ``z_um`` (or None) and its ``frame_index``, plus both DoF thresholds by
keyword (no default). Output: a ``FocusVerdict`` with source ``"dino"`` whose z is the
encoder readback the caller passed, never a model value; dz and sigma are evidence graded
``"model"``.

Flat file in the soft-matter-agents layout: stdlib only, its sibling loaded by path.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
from typing import Any, Protocol

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name: str, filename: str):
    """A sibling file by path (no package, no relative import); one module object per file."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_verdict = _load("_mic_focus_verdict", "focus_verdict.py")

#: This file's own source and origin kind, added to the sibling's vocabularies only here.
SOURCE = "dino"
MODEL = "model"  # a number a learned model produced (E6 in soft-matter-agents)


def has_model_numbers(v: Any) -> bool:
    """True when any evidence item of verdict `v` is a model number."""
    return any(e.grade == MODEL for e in v.evidence)


def _num(x: float | None) -> float | None:
    return None if x is None or not math.isfinite(x) else float(x)


# -- one signed model reading ----------------------------------------------------

class ReadingLike(Protocol):
    """What the live module's ``FocusReading`` provides (no import of live here)."""

    score: float | None
    sigma: float | None
    n_used: int
    tiles: list[Any]

    @property
    def sign_known(self) -> bool: ...


def from_reading(reading: ReadingLike, z_um: float | None, frame_index: int | None = None, *,
                 in_focus_dof: float, max_sigma_dof: float) -> _verdict.FocusVerdict:
    """Verdict from one frame's signed reading; `z_um` is that frame's encoder readback.

    dz (``reading.score``) is in DoF, dz = stage - best focus: dz > 0 means the stage is
    above focus, so the drive should step down.
    """
    dz, sigma = reading.score, reading.sigma
    ev = [_verdict.Evidence("dz", _num(dz), MODEL, "DoF"),
          _verdict.Evidence("sigma", _num(sigma), MODEL, "DoF"),
          _verdict.Evidence("n_tiles", len(reading.tiles), "computed"),
          _verdict.Evidence("n_used", reading.n_used, MODEL)]

    def v(verdict: Any, reason: str) -> _verdict.FocusVerdict:
        return _verdict.FocusVerdict(verdict, SOURCE, reason, frame_index=frame_index,
                            z_um=None if z_um is None else float(z_um), evidence=ev)

    if not reading.tiles:
        return v(_verdict.Verdict.NO_SAMPLE_HERE, "no tile with sample signal in the frame")
    if dz is None or not math.isfinite(dz):
        return v(_verdict.Verdict.UNSURE, f"{len(reading.tiles)} tiles, none readable")
    if sigma is None or not math.isfinite(sigma) or sigma > max_sigma_dof:
        return v(_verdict.Verdict.UNSURE, f"model sigma {sigma} DoF above {max_sigma_dof:g}")
    if abs(dz) <= in_focus_dof:
        return v(_verdict.Verdict.IN_FOCUS, f"|dz| {abs(dz):.2f} <= {in_focus_dof:g} DoF (model)")
    if reading.sign_known:
        if dz > 0:
            return v(_verdict.Verdict.STEP_DOWN, f"dz {dz:+.2f} DoF: stage above focus (model)")
        return v(_verdict.Verdict.STEP_UP, f"dz {dz:+.2f} DoF: stage below focus (model)")
    return v(_verdict.Verdict.UNSURE,
             f"dz {dz:+.2f} DoF but |dz| <= sigma {sigma:.2f}: sign unknown")
