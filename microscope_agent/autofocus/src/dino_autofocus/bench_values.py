"""Bench and tuning numbers that left the flat soft-matter-agents-shaped files (D-02).

The files under ``microscope_agent/src/`` are copied into soft-matter-agents, whose rules let no
number from another repository cross as code: values travel through the librarian as graded
entries (at most E3), and safety limits are written by the person into that repository's
envelope (its plan.md 10.3). So every bench measurement and tuning default the focus and map
cores used to carry sits here, in dino-autofocus only, and the cores take them as arguments.

Each value is ``unmeasured provisional`` unless its comment says otherwise. The question cards
in ``docs/librarian-handoff.md`` (L-031..L-033, L-057, L-077..L-089) ask the person about each
one; the provisional focus thresholds stay as they are until bench data decides (Q5 in
``docs/integration-sma.md``). Nothing here is imported by ``microscope_agent/``, and
``tests/test_sma_shape.py`` fails when a number like these reappears in a flat file.
"""

from __future__ import annotations

PROVISIONAL = "unmeasured provisional"

# -- classical frame rules (docs/librarian-handoff.md L-082, L-083) --------------------------
#: A frame with a larger clipped fraction is not used for focus (same limit as the tile
#: picker in ``dino_autofocus.live.select_tiles``).
MAX_SATURATED_FRACTION = 0.001
#: A sweep frame whose mean is more than this fraction off the sweep's median is a light
#: dropout, not a focus change: on 2026-09-30 one Aura frame at -23 % read 2.7x sharper than
#: the rest and became the "peak".
DROPOUT_TOLERANCE = 0.02
#: A local maximum counts as a separate peak when it stands this fraction of the curve's
#: (max - min) above the dip between it and any higher one; too little oil gave such a false
#: rise beside the real peak on 2026-09-30 (focus100x -202226).
DOUBLE_PEAK_PROMINENCE = 0.2

# -- camera and grid structure (D-03c: these left focus_classical too) ---------------------
#: Camera clip levels: 12-bit readout (the Kinetix_red on 2026-09-30) and 16-bit (2026-10-02).
CEILING_12BIT = 4095
CEILING_16BIT = 65535
#: Peak metric: bin x bin binning first, so one hot pixel cannot win (the 100x script).
PEAK_BIN_PX = 4
#: scan_4x: a tile is split into an n x n grid, one focus z per block (the 4x script).
SCAN_BLOCKS_PER_SIDE = 6

# -- focus verdict thresholds (Q5: provisional until bench data; L-077..L-081) --------------
#: Frames whose 99.9th percentile is less than this many ADU above their median hold no
#: sample: a 30 ms 100x Vollath run on 2026-09-30 read only the dark offset (~102 ADU).
VERDICT_MIN_DYNAMIC_RANGE_ADU = 20.0
#: A curve whose (max - min) / max(|max|, |min|) is below this is flat: no peak to trust.
VERDICT_MIN_CURVE_CONTRAST = 0.05
#: Fewer readable sweep frames than this cannot place a peak.
VERDICT_MIN_SWEEP_FRAMES = 3
#: |dz| at or under this many DoF reads as in focus (the live view's green band).
VERDICT_IN_FOCUS_DOF = 1.0
#: A model reading with a larger sigma (DoF) is ``unsure``.
VERDICT_MAX_SIGMA_DOF = 3.0
#: The keyword arguments ``focus_verdict.from_sweep`` takes, with this repository's values.
VERDICT_SWEEP_THRESHOLDS = {
    "min_dynamic_range_adu": VERDICT_MIN_DYNAMIC_RANGE_ADU,
    "min_contrast": VERDICT_MIN_CURVE_CONTRAST,
    "min_frames": VERDICT_MIN_SWEEP_FRAMES,
    "dropout_tolerance": DROPOUT_TOLERANCE,
    "max_saturated": MAX_SATURATED_FRACTION,
}

# -- focus_100x (L-086): the 2026-09-30 100x oil run, one sample ----------------------------
FOCUS_DEFAULT_CENTRE_UM = 2930.0  # the script's sweep centre when no 4x plane is known
FOCUS_PARFOCAL_4X_TO_100X_UM = -60.0  # 4x focus plane -> 100x focus; one sample, re-measure
FOCUS_DARK_OFFSET_ADU = 102.0  # Kinetix_red dark offset read on 2026-09-30
FOCUS_SIGNAL_MIN_ADU = 50.0  # a first frame whose max is within this of the dark offset: no signal
FOCUS_DEFAULT_EXPOSURE_MS = 20.0  # 20 ms gave a clean peak without saturation (script: 30)
#: Defaults ``focus_search.parse`` fills in for a ``focus_100x`` start without these arguments.
FOCUS_ARG_DEFAULTS = {
    "half_um": 40.0,
    "step_um": 2.0,
    "fine_half_um": 3.0,
    "fine_step_um": 0.2,
    "exposure_ms": FOCUS_DEFAULT_EXPOSURE_MS,
    "max_extensions": 3,  # times a top-end peak may be followed upward (the 100x script)
}
#: The light focus_100x switches on before the search (the flat search sets none): Aura
#: GREEN at 1 % on 2026-09-30.
FOCUS_LIGHT_DEFAULTS = {"aura_line": "GREEN", "aura_percent": 1.0}

# -- 4x stage <-> camera calibration of 2026-09-30 (L-031, L-032, L-033) ---------------------
#: docs/runs/2026-09-30_substrate-scan.yaml; d_px = M @ d_stage, mirrored in y, ~0.1 degree
UM_PER_PX_4X = 1.625
M_PX_PER_UM_4X = ((0.61602, 0.00236), (0.00126, -0.61456))
CALIBRATION_4X_SOURCE = "2026-09-30 4x calibration"
BENCH_M_4X_SOURCE = "2026-09-30 bench 4x (docs/runs/2026-09-30_substrate-scan.yaml)"
