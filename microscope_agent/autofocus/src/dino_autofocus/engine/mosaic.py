"""4x mosaic, stage <-> image mapping and classical particle candidates (WP-I, T-032).

The pure part lives in the flat files `microscope_agent/src/map_mosaic.py` and
`map_geometry.py` (the soft-matter-agents layout, docs/integration-sma.md section 9; numpy
only, the image filters are numpy ports of scipy.ndimage's) and is re-exported here, so
`engine.mosaic.<name>` keeps working. This module adds `mosaic_from_scan`, which names the
objective through the engine's guards (`registry_key`).

Nothing here talks to a backend. `operations/sample_map.py` calls it on scan_4x tile
outputs; the server renders the saved mosaic for the map screen. The conventions (stage
orientation, `stage = t + inv(M) @ (centre - p)`, candidates are `classical_candidate` /
`computed`) are documented in map_mosaic.py.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from .._flat import load
from ..bench_values import BENCH_M_4X_SOURCE, M_PX_PER_UM_4X

load("map_mosaic", f"{__package__}._map_mosaic")
from ._map_mosaic import (  # noqa: E402
    BIN,
    CANDIDATE_SOURCE,
    DEFAULT_CANDIDATES,
    ORIENTATION,
    CandidateParams,
    MosaicMeta,
    Orientation,
    Tile,
    bin_image,
    build_mosaic,
    detect_blobs,
    load_mosaic,
    load_scan_tiles,
    mosaic_to_stage,
    save_mosaic,
    stage_to_mosaic,
    stage_to_tile_pixel,
    tile_pixel_to_stage,
    um_per_px,
)
from ._map_mosaic import calibration_for as _calibration_for  # noqa: E402
from ._map_mosaic import find_candidates as _find_candidates  # noqa: E402

#: The 2026-09-30 bench 4x M (bench_values), the fallback for a sample with no calibration.
BENCH_M_4X = [list(r) for r in M_PX_PER_UM_4X]

__all__ = [
    "BENCH_M_4X", "BIN", "CANDIDATE_SOURCE", "DEFAULT_CANDIDATES", "ORIENTATION",
    "CandidateParams", "MosaicMeta", "Orientation", "Tile", "bin_image", "build_mosaic",
    "calibration_for", "detect_blobs", "find_candidates", "load_mosaic", "load_scan_tiles",
    "mosaic_from_scan", "mosaic_to_stage", "save_mosaic", "stage_to_mosaic",
    "stage_to_tile_pixel", "tile_pixel_to_stage", "um_per_px",
]


def calibration_for(sample_json: Path | None, objective: str = "4x") -> tuple[list, str]:
    """map_mosaic.calibration_for with this repository's fallback: the bench 4x M for the 4x,
    an error for any other objective without a sample calibration (as before D-02)."""
    return _calibration_for(sample_json, objective,
                            fallback_m=BENCH_M_4X if objective == "4x" else None,
                            fallback_source=BENCH_M_4X_SOURCE)


def find_candidates(tiles: Iterable[Tile], M: Any, p: CandidateParams = DEFAULT_CANDIDATES, *,
                    hole: dict | None = None, hole_margin_um: float = 100.0) -> list[dict]:
    """map_mosaic.find_candidates with this module's `detect_blobs`, looked up at each call,
    so a caller that swaps `engine.mosaic.detect_blobs` (scripts/retune_candidates.py runs the
    detection once per tile that way) is heard."""
    return _find_candidates(tiles, M, p, hole=hole, hole_margin_um=hole_margin_um,
                            detect=lambda img, q: detect_blobs(img, q))


def mosaic_from_scan(scan_dir: Path, M: Any | None = None, *, bin: int = BIN,
                     save: bool = True) -> tuple[np.ndarray, MosaicMeta]:
    """Build (and by default save) the mosaic of one scan folder. M defaults to the sample's
    calibration (`<scan_dir>/../sample.json`), else the 2026-09-30 bench 4x M."""
    rec, tiles = load_scan_tiles(scan_dir)
    source = "given"
    if M is None:
        M, source = calibration_for(scan_dir.parent / "sample.json")
    from .guards import GuardError, registry_key

    try:
        objective = registry_key(str(rec.get("objective", "4x")))
    except GuardError:
        objective = str(rec.get("objective", "4x"))
    mosaic, meta = build_mosaic(tiles, M, objective=objective, bin=bin,
                                calibration_source=source)
    if save:
        save_mosaic(scan_dir, mosaic, meta)
    return mosaic, meta
