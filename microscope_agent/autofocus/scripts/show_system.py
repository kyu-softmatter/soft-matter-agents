#!/usr/bin/env python3
"""Print what an imaging system implies for sampling, focus and autofocus.

Run this before generating a dataset for a specific instrument.  It is cheap and
it catches the mistakes that are expensive to find later: a camera that
undersamples the PSF, an index-matched stack that leaves no single-frame sign
information, a coverglass thickness that moves best focus by micrometres.

    uv run python scripts/show_system.py configs/mylab.yaml
    uv run python scripts/show_system.py --preset 60x_oil
"""
from __future__ import annotations

import argparse
from pathlib import Path


import numpy as np

from dino_autofocus.synth.optics.config import describe, load_system
from dino_autofocus.synth.optics.psf import PSFEngine
from dino_autofocus.synth.optics.system import PRESETS, preset
from dino_autofocus.synth.sim.render import FocalShift, Renderer


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", nargs="?", help="YAML file describing the system")
    ap.add_argument("--preset", choices=list(PRESETS), help="inspect a built-in preset")
    ap.add_argument("--fov", type=int, default=256, help="field of view, camera pixels")
    ap.add_argument("--depths", type=float, nargs="*", default=[0.0, 1.0, 3.0, 6.0],
                    help="emitter depths above the coverglass, um")
    args = ap.parse_args()

    if not args.config and not args.preset:
        ap.error("give a YAML file or --preset")
    system = preset(args.preset) if args.preset else load_system(args.config)

    print(describe(system))

    eng = PSFEngine(system, fov_px=args.fov, pad=2, workers=-1, cache_size=8)
    rend = Renderer(eng, focal_shift=FocalShift(eng, depth_max=max(args.depths) + 2.0))
    dof = system.depth_of_field

    print(f"\n  raster: {args.fov} camera px = "
          f"{args.fov * system.pixel_size_sample:.1f} um field, "
          f"{eng.n_grid} px padded ({eng.n_grid * eng.dx:.1f} um)")
    print(f"  wrap-free defocus range: +-{rend.max_safe_defocus:.2f} um "
          f"(+-{rend.max_safe_defocus / dof:.1f} DoF)")
    print(f"  focal shift: offset {rend.shift.offset:+.3f} um, "
          f"slope {rend.shift.slope:+.3f} um per um of depth")

    print(f"\n  best-focus stage position vs emitter depth:")
    print(f"    {'depth (um)':>10s} {'stage (um)':>11s} {'in DoF':>9s}")
    for d in args.depths:
        z = float(rend.shift(d))
        print(f"    {d:10.2f} {z:+11.3f} {z / dof:+9.2f}")

    if abs(rend.shift.slope) > 1e-6:
        print("\n  A depth-dependent shift means the sample's own thickness spreads")
        print("  best focus: a slab T um thick spans "
              f"{abs(rend.shift.slope):.2f} * T um of stage travel "
              f"({abs(rend.shift.slope) / dof:.2f} DoF per um of thickness).")
        t_max = 2.0 * dof / abs(rend.shift.slope)
        print(f"  For focus to be defined within 2 DoF, keep the sample thinner "
              f"than about {t_max:.2f} um.")


if __name__ == "__main__":
    main()
