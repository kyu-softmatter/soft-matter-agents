"""Thin wrapper: frozen-DINO focus reading -> ``FocusVerdict``.

``dino_autofocus.live`` (and with it torch) is imported only when a scorer is built from a
head file, so importing ``dino_autofocus.focus`` stays torch-free. The model's dz and sigma
end up in the verdict's evidence with grade ``"model"``; the verdict's z is the encoder
readback the caller passes for the frame.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from ..bench_values import VERDICT_IN_FOCUS_DOF as IN_FOCUS_DOF
from ..bench_values import VERDICT_MAX_SIGMA_DOF as MAX_SIGMA_DOF
from .verdict import FocusVerdict
from .verdict_model import ReadingLike, from_reading

Scorer = Callable[..., ReadingLike]


class DinoVerdict:
    """Score a frame with a trained head and map the reading to a verdict.

    `scorer` is anything called as ``scorer(img, region=...)`` that returns a
    ``live.FocusReading``-like object; ``from_head`` builds the real one.
    """

    def __init__(self, scorer: Scorer, in_focus_dof: float = IN_FOCUS_DOF,
                 max_sigma_dof: float = MAX_SIGMA_DOF):
        self.scorer = scorer
        self.in_focus_dof = in_focus_dof
        self.max_sigma_dof = max_sigma_dof

    @classmethod
    def from_head(cls, head_path: str | Path, k_tiles: int = 4, saturated: int = 65535,
                  **thresholds: Any) -> DinoVerdict:
        """Load ``live.FocusScorer`` (imports torch). `saturated` is the camera ceiling:
        4095 for a 12-bit readout."""
        from ..live import FocusScorer

        return cls(FocusScorer(head_path, k_tiles=k_tiles, saturated=saturated), **thresholds)

    def __call__(self, img: np.ndarray, z_um: float | None, frame_index: int | None = None,
                 region: tuple[int, int, int] | None = None) -> FocusVerdict:
        """`z_um`: encoder readback of the frame `img` was read from."""
        reading = self.scorer(img, region=region)
        out = from_reading(reading, z_um, frame_index, in_focus_dof=self.in_focus_dof,
                           max_sigma_dof=self.max_sigma_dof)
        where = getattr(reading, "where", None)
        if where:
            out.reason += f" [{where}]"
        return out
