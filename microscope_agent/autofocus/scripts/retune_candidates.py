"""Re-run the T-032 particle-candidate detection over a range of thresholds (offline).

    uv run python scripts/retune_candidates.py D:/AutoFocus/samples/<id>/scan4x_<stamp>
    uv run python scripts/retune_candidates.py <scan4x_dir> --thresholds 3:12:1 --out D:/tmp/retune
    uv run python scripts/retune_candidates.py <folder>/mosaic.npy --sigma 1.0

The threshold is `min_snr` of `engine.mosaic.CandidateParams`: a blob is kept when its
Laplacian-of-Gaussian response is over min_snr times the response's robust noise. For each
threshold this prints how many candidates `find_candidates` returns (merged across tile
overlaps, as the sample map does), so the default (6) can be checked on a real bench scan.

Input, read only:
- a scan_4x / sample_map record folder (scan.json + tile .npy files): detection runs on the
  full-resolution tiles, as in the sample map. M is the sample's stage_camera_calibration
  (`<scan>/../sample.json`), else the 2026-09-30 bench 4x M.
- a saved `mosaic.npy` (or a folder holding one and no scan.json): detection runs on the
  binned mosaic itself. A 4x particle (~4 px) is under one mosaic pixel after 8x binning, so
  these counts are not the sample map's; use the scan folder for those.

With `--out DIR` it also writes counts.csv, candidates.csv and contact_sheet.png (the
mosaic with each threshold's candidates) into DIR, which must not be inside the input or
the sample folder. Nothing is shown on screen. No hardware.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from dino_autofocus.engine import mosaic as mz

DEFAULT_THRESHOLDS = (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0)
MAX_PANELS = 12


# ---------------------------------------------------------------- input
@dataclass
class Source:
    kind: str  # "scan" | "mosaic"
    path: Path  # the scan folder, or the mosaic .npy file
    folder: Path  # folder the input lives in (never written)
    tiles: list[mz.Tile] | None = None
    M: list | None = None
    calibration: str = ""
    mosaic: np.ndarray | None = None  # given, or built in memory for the contact sheet
    meta: mz.MosaicMeta | None = None


def load_source(path: Path) -> Source:
    path = Path(path)
    if path.is_dir() and (path / "scan.json").is_file():
        _, tiles = mz.load_scan_tiles(path)
        if not tiles:
            raise SystemExit(f"{path / 'scan.json'} lists no tiles")
        M, cal = mz.calibration_for(path.parent / "sample.json")
        return Source("scan", path, path, tiles=tiles, M=M, calibration=cal)
    npy = path / "mosaic.npy" if path.is_dir() else path
    if npy.suffix == ".npy" and npy.is_file():
        img = np.load(npy, mmap_mode="r", allow_pickle=False)
        if img.ndim != 2:
            raise SystemExit(f"{npy} is not a 2D image (shape {img.shape})")
        meta_path = npy.with_suffix(".json")
        meta = None
        if meta_path.is_file():
            meta = mz.MosaicMeta.from_dict(json.loads(meta_path.read_text(encoding="utf-8")))
        return Source("mosaic", npy, npy.parent, mosaic=np.asarray(img), meta=meta)
    raise SystemExit(f"{path} is neither a scan folder (scan.json) nor a mosaic .npy")


# ---------------------------------------------------------------- detection
@contextlib.contextmanager
def detect_once(lowest: float) -> Iterator[None]:
    """Run each tile's blob detection once, at the lowest threshold, while this is open.

    `find_candidates` calls `mosaic.detect_blobs` per tile; the stand-in returns the blobs a
    direct call at `p.min_snr` would (SNR over the threshold, strongest first, at most
    `max_per_tile`), taken from one uncapped detection at `lowest`. Merging, the stage
    mapping and the hole filter stay T-032's. The original function is put back on exit.
    """
    original = mz.detect_blobs
    cache: dict[tuple[int, mz.CandidateParams], list[dict]] = {}

    def cached(img: np.ndarray, p: mz.CandidateParams = mz.DEFAULT_CANDIDATES) -> list[dict]:
        if p.min_snr < lowest:
            return original(img, p)
        key = (id(img), replace(p, min_snr=lowest, max_per_tile=sys.maxsize))
        if key not in cache:
            cache[key] = original(img, key[1])
        return [b for b in cache[key] if b["snr"] > p.min_snr][:p.max_per_tile]

    mz.detect_blobs = cached
    try:
        yield
    finally:
        mz.detect_blobs = original


def candidates_by_threshold(src: Source, params: mz.CandidateParams,
                            thresholds: Sequence[float], *, hole: dict | None = None,
                            hole_margin_um: float = 100.0) -> dict[float, list[dict]]:
    out: dict[float, list[dict]] = {}
    with detect_once(min(thresholds)):
        for t in thresholds:
            p = replace(params, min_snr=t)
            if src.kind == "scan":
                out[t] = mz.find_candidates(src.tiles, src.M, p, hole=hole,
                                            hole_margin_um=hole_margin_um)
            else:
                out[t] = [_mosaic_candidate(src, b) for b in mz.detect_blobs(src.mosaic, p)]
    return out


def _mosaic_candidate(src: Source, b: dict) -> dict:
    c = {"score": round(b["snr"], 2), "px": [b["col"], b["row"]], "tile": "mosaic"}
    if src.meta is not None:
        x, y = mz.mosaic_to_stage(src.meta, b["col"], b["row"])
        c.update(x_um=round(x, 2), y_um=round(y, 2))
    return c


# ---------------------------------------------------------------- output
def print_table(src: Source, params: mz.CandidateParams, found: dict[float, list[dict]]) -> None:
    print(f"input: {src.path} ({src.kind}"
          + (f", {len(src.tiles)} tiles, M from {src.calibration})" if src.kind == "scan" else ")"))
    if src.kind == "mosaic":
        b = src.meta.bin if src.meta else "?"
        print(f"note: detection on the binned mosaic (bin {b}); not the sample map's counts")
    fixed = {k: v for k, v in vars(params).items() if k != "min_snr"}
    print("params: " + ", ".join(f"{k}={v}" for k, v in fixed.items()))
    print(f"{'min_snr':>8}  {'candidates':>10}  {'median score':>12}")
    for t, cands in found.items():
        med = f"{np.median([c['score'] for c in cands]):.1f}" if cands else "-"
        mark = "  (default)" if t == mz.DEFAULT_CANDIDATES.min_snr else ""
        print(f"{t:>8g}  {len(cands):>10d}  {med:>12}{mark}")


def check_out_dir(out: Path, src: Source) -> Path:
    """`out`, resolved; refused when inside the input folder or a sample folder above it."""
    out = Path(out).resolve()
    guarded = [src.folder.resolve()]
    for parent in src.folder.resolve().parents:
        if (parent / "sample.json").is_file():
            guarded.append(parent)
    for g in guarded:
        if out == g or g in out.parents:
            raise SystemExit(f"--out {out} is inside {g}; write somewhere outside the sample")
    return out


def write_outputs(out: Path, src: Source, found: dict[float, list[dict]]) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    counts = out / "counts.csv"
    with counts.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["min_snr", "candidates"])
        for t, cands in found.items():
            w.writerow([t, len(cands)])
    cand = out / "candidates.csv"
    with cand.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["min_snr", "x_um", "y_um", "score", "tile", "col", "row"])
        for t, cands in found.items():
            for c in cands:
                w.writerow([t, c.get("x_um", ""), c.get("y_um", ""), c["score"], c["tile"],
                            c["px"][0], c["px"][1]])
    sheet = out / "contact_sheet.png"
    contact_sheet(sheet, src, found)
    return [counts, cand, sheet]


def contact_sheet(path: Path, src: Source, found: dict[float, list[dict]]) -> None:
    """One panel per threshold: the mosaic in stage orientation with that threshold's
    candidates. Drawn with the Agg canvas only, so no window opens."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    if src.mosaic is None:  # scan input: build the mosaic in memory, never saved
        src.mosaic, src.meta = mz.build_mosaic(src.tiles, src.M, calibration_source=src.calibration)
    img = np.asarray(src.mosaic, float)
    shown = img[img != 0] if src.kind == "scan" else img.ravel()
    lo, hi = np.percentile(shown, [1, 99]) if shown.size else (0.0, 1.0)

    items = list(found.items())[:MAX_PANELS]
    ncol = min(4, len(items))
    nrow = -(-len(items) // ncol)
    aspect = img.shape[0] / max(img.shape[1], 1)
    fig = Figure(figsize=(4 * ncol, 4 * nrow * aspect + 0.6 * nrow), dpi=100)
    FigureCanvasAgg(fig)
    for k, (t, cands) in enumerate(items):
        ax = fig.add_subplot(nrow, ncol, k + 1)
        ax.imshow(img, cmap="gray", vmin=lo, vmax=hi, origin="lower", interpolation="nearest")
        cols, rows = _panel_points(src, cands)
        ax.scatter(cols, rows, s=30, facecolors="none", edgecolors="#ff3b30", linewidths=0.8)
        ax.set_title(f"min_snr {t:g}: {len(cands)}", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(f"{src.path.name} candidates", fontsize=11)
    fig.tight_layout()
    fig.savefig(path)


def _panel_points(src: Source, cands: list[dict]) -> tuple[list[float], list[float]]:
    if src.kind == "mosaic":  # detected on the mosaic: its own pixels
        return [c["px"][0] for c in cands], [c["px"][1] for c in cands]
    pts = [mz.stage_to_mosaic(src.meta, c["x_um"], c["y_um"]) for c in cands]
    return [p[0] for p in pts], [p[1] for p in pts]


# ---------------------------------------------------------------- CLI
def parse_thresholds(text: str) -> list[float]:
    """"4,5,6" or "start:stop[:step]" (stop included). Sorted, without repeats."""
    try:
        if ":" in text:
            parts = [float(s) for s in text.split(":")]
            if len(parts) not in (2, 3):
                raise ValueError
            start, stop = parts[0], parts[1]
            step = parts[2] if len(parts) == 3 else 1.0
            if step <= 0 or stop < start:
                raise ValueError
            n = int(np.floor((stop - start) / step + 1e-9)) + 1
            values = [round(start + i * step, 6) for i in range(n)]
        else:
            values = [float(s) for s in text.split(",") if s.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"thresholds {text!r}: use '4,5,6' or 'start:stop[:step]'") from None
    if not values or any(v <= 0 for v in values):
        raise argparse.ArgumentTypeError(f"thresholds {text!r}: need positive numbers")
    return sorted(set(values))


def parse_hole(text: str) -> dict:
    try:
        x, y, d = (float(s) for s in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("hole: use 'x_um,y_um,diameter_mm'") from None
    return {"centre_um": [x, y], "diameter_mm": d}


def build_parser() -> argparse.ArgumentParser:
    d = mz.DEFAULT_CANDIDATES
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="scan_4x folder (scan.json) or mosaic .npy")
    ap.add_argument("--thresholds", type=parse_thresholds,
                    default=list(DEFAULT_THRESHOLDS),
                    help="min_snr values: '4,5,6' or 'start:stop[:step]' (default "
                         + ",".join(f"{t:g}" for t in DEFAULT_THRESHOLDS) + ")")
    ap.add_argument("--polarity", choices=("dark", "bright"), default=d.polarity)
    ap.add_argument("--sigma", type=float, default=d.sigma_px, help="sigma_px")
    ap.add_argument("--background-sigma", type=float, default=d.background_sigma_px)
    ap.add_argument("--min-blob-ratio", type=float, default=d.min_blob_ratio)
    ap.add_argument("--border", type=int, default=d.border_px, help="border_px")
    ap.add_argument("--max-per-tile", type=int, default=d.max_per_tile)
    ap.add_argument("--merge-um", type=float, default=d.merge_um)
    ap.add_argument("--hole", type=parse_hole, default=None,
                    help="keep only points inside this hole: 'x_um,y_um,diameter_mm'")
    ap.add_argument("--hole-margin-um", type=float, default=100.0)
    ap.add_argument("--out", type=Path, default=None,
                    help="folder for counts.csv, candidates.csv, contact_sheet.png")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    src = load_source(args.input)
    out = check_out_dir(args.out, src) if args.out is not None else None
    params = replace(mz.DEFAULT_CANDIDATES, polarity=args.polarity, sigma_px=args.sigma,
                     background_sigma_px=args.background_sigma,
                     min_blob_ratio=args.min_blob_ratio, border_px=args.border,
                     max_per_tile=args.max_per_tile, merge_um=args.merge_um)
    if args.hole is not None and src.kind == "mosaic":
        print("note: --hole applies to scan folders only; ignored for a mosaic")
    found = candidates_by_threshold(src, params, args.thresholds, hole=args.hole,
                                    hole_margin_um=args.hole_margin_um)
    print_table(src, params, found)
    if out is not None:
        for p in write_outputs(out, src, found):
            print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
