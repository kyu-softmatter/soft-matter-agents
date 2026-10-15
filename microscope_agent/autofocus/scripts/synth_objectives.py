"""One synthetic focal series per Ti2 objective, rendered with dino_autofocus.synth.

    uv run python scripts/synth_objectives.py --out outputs/synth_objectives
    uv run python scripts/synth_objectives.py --sample particle --particle-um 5

Configs are configs/ti2_<obj>.yaml (NA and pixel size from the
soft-matter-agents KB). Writes a montage (rows = objectives, columns = defocus in
DoF; the dz = 0 column is the exact best-focus plane) and the raw 16-bit frames
of every rendered scene as .npz.

--sample mixed draws the simulator's own sample families. --sample particle
replaces them with uniformly dyed spheres of one size, kept whole and resting on
the coverslip, at a fixed number per area (so a 4x field holds many and a 100x
field few), plus one near the centre so every field shows a particle.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from dino_autofocus.synth.optics.config import load_system
from dino_autofocus.synth.sim import geometry as G
from dino_autofocus.synth.sim import scene as S
from dino_autofocus.synth.sim.dataset import DatasetConfig, render_scene
from dino_autofocus.synth.sim.scene import RandomisationConfig

CONFIGS = Path(__file__).parents[1] / "configs"

# objective: (raster pad, slab thickness range um) -- same as the dataset runs
OBJECTIVES = {
    "4x": (2, (0.2, 8.0)),
    "10x": (2, (0.2, 8.0)),
    "20x": (2, (0.35, 2.81)),
    "40x": (3, (0.13, 1.03)),
    "60x": (3, (0.08, 0.65)),
    "100x": (3, (0.08, 0.62)),
}
SHOW_DOF = (-6.0, -3.0, -1.5, 0.0, 1.5, 3.0, 6.0)
MAX_EMITTERS = 300_000


def particle_sampler(diameter_um: float, per_mm2: float):
    """A draw_sample replacement: equal spheres at a fixed areal number density."""
    radius = diameter_um / 2.0

    def draw(rng, cfg, fov_um, grid_um):
        half = grid_um / 2.0
        n = int(rng.poisson(per_mm2 * 1e-6 * grid_um ** 2))
        xy = rng.uniform(-half, half, size=(n, 2))
        centre = rng.uniform(-fov_um / 6, fov_um / 6, size=(1, 2))
        xy = np.vstack([centre, xy])
        per = int(min(60_000, MAX_EMITTERS // len(xy)))     # equal brightness per sphere
        parts = []
        for x, y in xy:
            d = rng.normal(size=(per, 3))
            d *= (radius * rng.uniform(size=per) ** (1 / 3) / np.linalg.norm(d, axis=1))[:, None]
            parts.append(G.Emitters(d + [x, y, radius], np.ones(per), "solid_sphere",
                                    {"radius": radius}))
        return G.Emitters.concat(parts, "solid_sphere")

    return draw


def first_valid(obj: str, pad: int, slab, seed0: int, tries: int, sample: dict | None):
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    system = load_system(CONFIGS / f"ti2_{obj}.yaml")
    kw, gates = {}, {}
    if sample is not None:
        # A whole sphere many DoF deep has a broad focus peak, which lifts the median of
        # the coarse scan and so the prominence; the rival-peak, edge and label-residual
        # gates still apply.
        gates = dict(min_peak_prominence=2.0)
        S.draw_sample = particle_sampler(**sample)          # this worker process only
        d = sample["diameter_um"]
        slab = (d + 1.0, d + 1.0)                           # keep the whole sphere
        kw = dict(base_depth=(0.05, 0.3), max_emitters=MAX_EMITTERS)
    rc = RandomisationConfig(custom_system=system, lock_optics=True, slab_thickness=slab,
                             empty_probability=0.0, **kw)
    cfg = DatasetConfig(fov_px=224, n_planes=17, pad=pad, scan_span_dof=12.0, randomisation=rc,
                        focus_plane=True, **gates)
    for seed in range(seed0, seed0 + tries):
        r = render_scene(seed, cfg)
        if r is not None and np.all(r["valid"]):
            return system, seed, r
        print(f"  {obj}: seed {seed} rejected", flush=True)
    raise RuntimeError(f"{obj}: no valid scene in {tries} seeds")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs/synth_objectives"))
    ap.add_argument("--seed0", type=int, default=100)
    ap.add_argument("--tries", type=int, default=12)
    ap.add_argument("--sample", choices=("mixed", "particle"), default="mixed")
    ap.add_argument("--particle-um", type=float, default=5.0, help="sphere diameter")
    ap.add_argument("--per-mm2", type=float, default=120.0,
                    help="spheres per mm^2; 120 ~ a few per 156 um field, as on 2026-09-30")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    sample = (None if args.sample == "mixed"
              else {"diameter_um": args.particle_um, "per_mm2": args.per_mm2})
    tag = "mixed" if sample is None else f"particle{args.particle_um:g}um"
    fig, axes = plt.subplots(len(OBJECTIVES), len(SHOW_DOF),
                             figsize=(2.1 * len(SHOW_DOF), 2.25 * len(OBJECTIVES)))
    with ProcessPoolExecutor(len(OBJECTIVES)) as pool:
        jobs = [pool.submit(first_valid, obj, pad, slab, args.seed0 + 1000 * i, args.tries,
                            sample)
                for i, (obj, (pad, slab)) in enumerate(OBJECTIVES.items())]
        scenes = [j.result() for j in jobs]
    for row, (obj, (system, seed, r)) in enumerate(zip(OBJECTIVES, scenes)):
        img, dz = r["image"], r["dz_dof"]
        np.savez_compressed(args.out / f"ti2_{obj}_{tag}_seed{seed}.npz", image=img, dz_dof=dz,
                            stage_um=r["stage_um"], best_stage_um=r["best_stage_um"],
                            dof_um=r["dof_um"], family=r["family"])
        d = system.describe()
        fov_um = img.shape[-1] * d["pixel_size_sample_um"]
        print(f"{obj}: seed {seed}, {r['family'][0]}, DoF {d['depth_of_field_um']:.2f} um, "
              f"FOV {fov_um:.0f} um, max {img.max():.0f} ADU")
        for col, target in enumerate(SHOW_DOF):
            k = int(np.argmin(np.abs(dz - target)))
            assert target != 0 or dz[k] == 0.0, "no exact-focus plane"
            ax = axes[row, col]
            lo, hi = np.percentile(img[k], (0.5, 99.8))
            ax.imshow(img[k], cmap="gray", vmin=lo, vmax=max(hi, lo + 1))
            ax.set_xticks([]), ax.set_yticks([])
            ax.text(3, 14, f"{dz[k]:+.1f} DoF", color="yellow", fontsize=8)
            if row == 0:
                ax.set_title("in focus (dz = 0)" if target == 0 else f"dz ≈ {target:+g} DoF",
                             fontsize=9, fontweight="bold" if target == 0 else None)
            if col == 0:
                ax.set_ylabel(f"{obj}  NA {d['na']:g}\n{d['pixel_size_sample_um']:.3g} µm/px, "
                              f"FOV {fov_um:.0f} µm\nDoF {d['depth_of_field_um']:.2g} µm",
                              fontsize=8)
    what = ("mixed sample families" if sample is None else
            f"{args.particle_um:g} µm dyed spheres, {args.per_mm2:g} per mm²")
    fig.suptitle(f"Synthetic widefield fluorescence, {what}; Ti2 objectives, 605 nm, "
                 "Kinetix 16-bit DR (per-frame contrast)", fontsize=10)
    fig.tight_layout()
    out = args.out / f"montage_{tag}.png"
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
