#!/usr/bin/env python3
"""Generate a synthetic autofocus dataset.

Each scene contributes one focal series; every plane is one record.  Scenes are
independent, so this parallelises cleanly over cores.

Examples
--------
    uv run python scripts/make_dataset.py --out data/train --scenes 800
    uv run python scripts/make_dataset.py --out data/spheres --scenes 200 \
        --geometries solid_sphere hollow_shell sphere_size_series
    uv run python scripts/make_dataset.py --out data/60x --scenes 200 --system 60x_oil
"""
from __future__ import annotations

import argparse
from pathlib import Path


from dino_autofocus.synth.sim.dataset import DatasetConfig, generate
from dino_autofocus.synth.sim.geometry import FAMILIES, GENERATORS
from dino_autofocus.synth.sim.scene import RandomisationConfig
from dino_autofocus.synth.optics.system import PRESETS


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scenes", type=int, default=400)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--fov", type=int, default=128, help="field of view, camera pixels")
    ap.add_argument("--planes", type=int, default=11, help="training planes per scene")
    ap.add_argument("--span", type=float, default=14.0, help="scan half-range, in DoF")
    ap.add_argument("--pad", type=int, default=2,
                    help="raster padding factor; the wrap-free defocus range grows with "
                         "it (run scripts/show_system.py), at a quadratic cost in FFT size")
    ap.add_argument("--workers", type=int, default=None, help="scene-level processes")
    ap.add_argument("--fft-threads", type=int, default=1,
                    help="FFT threads per scene; keep at 1 when workers > 1")
    ap.add_argument("--shard-size", type=int, default=32, help="scenes per shard")
    ap.add_argument("--device", default="cpu",
                    help="cpu, or cuda to run the PSF/convolution work on the GPU; with cuda "
                         "use a few --workers (each holds its own CUDA context)")
    ap.add_argument("--gpu-dtype", choices=("complex128", "complex64"), default="complex128",
                    help="complex128 reproduces the CPU images exactly; complex64 is ~20%% "
                         "faster and changes the noise draws")
    ap.add_argument("--particle-um", type=float, default=None,
                    help="particle mode: uniformly dyed spheres of this diameter on one "
                         "layer, kept whole, instead of the geometry families")
    ap.add_argument("--particle-per-mm2", type=float, nargs=2, default=(30.0, 500.0),
                    metavar=("LOW", "HIGH"), help="particles per mm^2 (log-uniform)")
    ap.add_argument("--base-depth", type=float, nargs=2, default=None, metavar=("LOW", "HIGH"),
                    help="height of the sample bottom above the coverglass, um")
    ap.add_argument("--min-prominence", type=float, default=None,
                    help="focus-peak prominence gate (default 4.0); a whole particle many "
                         "DoF deep has a broad peak, use ~2 in particle mode")
    ap.add_argument("--depth-bin", type=float, default=None,
                    help="emitter depth quantisation for PSF reuse, um (default 0.5); "
                         "a fraction of the DoF is enough, so low-NA lenses can use more")
    ap.add_argument("--psf-cache", type=int, default=None,
                    help="OTFs kept per worker (default 16); each is n_grid^2 complex128")
    ap.add_argument("--focus-plane", action="store_true",
                    help="put the middle plane of every stack exactly on best focus (dz = 0)")
    ap.add_argument("--system", default=None, choices=list(PRESETS),
                    help="fix the objective instead of randomising over presets")
    ap.add_argument("--system-config", default=None, metavar="YAML",
                    help="model one specific instrument; see configs/lab_template.yaml")
    ap.add_argument("--jitter-optics", action="store_true",
                    help="with --system-config, also randomise NA, wavelength and "
                         "refractive indices around the given values")
    ap.add_argument("--geometries", nargs="*", default=None,
                    help=f"restrict geometries; any of: {' '.join(sorted(GENERATORS))}")
    ap.add_argument("--families", nargs="*", default=None,
                    help=f"restrict to families: {' '.join(FAMILIES)}")
    ap.add_argument("--aberration-scale", type=float, nargs=2, default=None,
                    metavar=("LOW", "HIGH"), help="range multiplying the Zernike sigmas")
    ap.add_argument("--slab-thickness", type=float, nargs=2, default=None,
                    metavar=("LOW", "HIGH"),
                    help="axial extent of sample kept, um (log-uniform). Focus is "
                         "only well defined for a slab thin enough that the focal "
                         "shift does not spread it over several depths of field; "
                         "run scripts/show_system.py for the limit")
    args = ap.parse_args()

    geoms = args.geometries
    if args.families:
        unknown = set(args.families) - set(FAMILIES)
        if unknown:
            ap.error(f"unknown families: {sorted(unknown)}")
        from_fams = [g for f in args.families for g in FAMILIES[f]]
        geoms = sorted(set(geoms or []) | set(from_fams))
    if geoms:
        unknown = set(geoms) - set(GENERATORS)
        if unknown:
            ap.error(f"unknown geometries: {sorted(unknown)}")

    custom = None
    if args.system_config:
        from dino_autofocus.synth.optics.config import describe, load_system
        custom = load_system(args.system_config)
        print(describe(custom))
        print()

    kw = {"geometries": tuple(geoms) if geoms else None,
          "custom_system": custom, "lock_optics": not args.jitter_optics}
    if args.aberration_scale:
        kw["aberration_scale"] = tuple(args.aberration_scale)
    if args.slab_thickness:
        kw["slab_thickness"] = tuple(args.slab_thickness)
    if args.particle_um:
        kw["particle_diameter"] = args.particle_um
        kw["particle_per_mm2"] = tuple(args.particle_per_mm2)
    if args.base_depth:
        kw["base_depth"] = tuple(args.base_depth)
    rc = RandomisationConfig(**kw)

    # A sample thicker than the focal shift can hold in one depth of field has
    # no single best-focus plane, and the label gates will reject it.  Rejection
    # is correct but it is paid for in rendering time, so say so up front.
    if custom is not None and not args.particle_um:
        from dino_autofocus.synth.optics.psf import PSFEngine
        from dino_autofocus.synth.sim.render import FocalShift
        probe = PSFEngine(custom, fov_px=args.fov, pad=args.pad, workers=1, cache_size=2)
        slope = abs(FocalShift(probe, depth_max=10.0).slope)
        if slope > 1e-6:
            limit = 2.0 * custom.depth_of_field / slope
            if rc.slab_thickness[1] > limit:
                print(f"NOTE: sample slabs up to {rc.slab_thickness[1]:.1f} um are being "
                      f"drawn, but on this instrument focus stays defined within "
                      f"2 DoF only up to about {limit:.2f} um "
                      f"(focal-shift slope {slope:.2f} um/um, DoF "
                      f"{custom.depth_of_field * 1000:.0f} nm).")
                print(f"      Thicker scenes will be rejected by the label gates as "
                      f"ambiguous, which costs rendering time. Consider "
                      f"--slab-thickness {max(0.1, limit / 8):.2f} {limit:.2f}")
                print()

    cfg = DatasetConfig(fov_px=args.fov, n_planes=args.planes, pad=args.pad,
                        scan_span_dof=args.span, randomisation=rc,
                        fft_workers=args.fft_threads, device=args.device,
                        gpu_dtype=args.gpu_dtype, focus_plane=args.focus_plane,
                        **({} if args.depth_bin is None else {"depth_bin": args.depth_bin}),
                        **({} if args.psf_cache is None else {"psf_cache_size": args.psf_cache}),
                        **({} if args.min_prominence is None
                           else {"min_peak_prominence": args.min_prominence}))

    print(f"generating {args.scenes} scenes -> {args.out}")
    print(f"  fov={args.fov}px  planes/scene={args.planes}  span=+-{args.span} DoF")
    print(f"  system={custom.name if custom else (args.system or 'randomised')}"
          f"{'' if custom is None else (' (optics locked)' if not args.jitter_optics else ' (optics jittered)')}"
          f"  geometries={geoms or 'all'}")
    generate(args.out, args.scenes, cfg, seed0=args.seed0,
             shard_size=args.shard_size, workers=args.workers,
             system_name=args.system)


if __name__ == "__main__":
    main()
