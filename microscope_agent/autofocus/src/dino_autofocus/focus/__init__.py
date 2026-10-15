"""Focus metrics and verdicts. Classical metrics are the default and the final judge; the
DINO reading is an aid (docs/PLAN.md). Importing this package does not import torch:
``focus.dino`` loads the model only in ``DinoVerdict.from_head``.

``classical``, ``verdict`` and ``sma_event`` live in ``microscope_agent/src/`` as the flat
files ``focus_classical``, ``focus_verdict`` and ``focus_run_log`` (the soft-matter-agents
layout, docs/integration-sma.md section 9); they are registered here under their old names.
"""

from .._flat import load

classical = load("focus_classical", f"{__name__}.classical")
verdict = load("focus_verdict", f"{__name__}.verdict")
sma_event = load("focus_run_log", f"{__name__}.sma_event")
verdict_model = load("focus_verdict_model", f"{__name__}.verdict_model")

from ..bench_values import (  # noqa: E402
    CEILING_12BIT,
    CEILING_16BIT,
    VERDICT_IN_FOCUS_DOF,
    VERDICT_MAX_SIGMA_DOF,
    VERDICT_SWEEP_THRESHOLDS,
)
from .classical import (  # noqa: E402
    METRICS,
    FrameStats,
    SweepAnalysis,
    analyse_sweep,
    brenner,
    ceiling_for_bits,
    dropout_mask,
    frame_stats,
    parabola_vertex,
    peak_brightness,
    peak_edge,
    saturated_fraction,
    score,
    tenengrad,
    vollath4,
)
from .dino import DinoVerdict  # noqa: E402
from .verdict import Evidence, FocusVerdict, Verdict  # noqa: E402
from .verdict import from_sweep as _from_sweep  # noqa: E402
from .verdict_model import from_reading as _from_reading  # noqa: E402


def from_sweep(z_um, stats, **thresholds):
    """``focus_verdict.from_sweep`` with this repository's provisional thresholds
    (``bench_values.VERDICT_SWEEP_THRESHOLDS``) unless the caller names its own (D-02)."""
    return _from_sweep(z_um, stats, **{**VERDICT_SWEEP_THRESHOLDS, **thresholds})


def from_reading(reading, z_um, frame_index=None, *, in_focus_dof=VERDICT_IN_FOCUS_DOF,
                 max_sigma_dof=VERDICT_MAX_SIGMA_DOF):
    """``focus_verdict_model.from_reading`` with this repository's provisional DoF thresholds."""
    return _from_reading(reading, z_um, frame_index, in_focus_dof=in_focus_dof,
                         max_sigma_dof=max_sigma_dof)

__all__ = [
    "CEILING_12BIT",
    "CEILING_16BIT",
    "METRICS",
    "DinoVerdict",
    "Evidence",
    "FocusVerdict",
    "FrameStats",
    "SweepAnalysis",
    "Verdict",
    "analyse_sweep",
    "brenner",
    "ceiling_for_bits",
    "dropout_mask",
    "frame_stats",
    "from_reading",
    "from_sweep",
    "parabola_vertex",
    "peak_brightness",
    "peak_edge",
    "saturated_fraction",
    "score",
    "tenengrad",
    "vollath4",
]
