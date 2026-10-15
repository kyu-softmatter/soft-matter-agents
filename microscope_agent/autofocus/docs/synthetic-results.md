# First synthetic check (2026-09-30)

Frozen `dinov2_vits14` (CLS + mean patch token, last block) against classical focus
metrics on psf-autofocus synthetic widefield-fluorescence z-stacks. Run on the GTX 1650
SUPER desktop with fp32 features (`--no-fp16`), not on the microscope PC.

- Data: `make_dataset.py --scenes 160 --seed0 1000 --fov 224 --planes 17` (randomised
  objective presets and geometries, +-14 DoF span). 2720 frames, 72 % `valid`; 106 of
  160 stacks have every plane valid and are used for the plane-pick test.
- Protocol: 5-fold CV grouped by scene. Heads are ridge and a 256-128 MLP (sklearn).
  "classical" = 7 `RELIABLE` metrics (signed log) + 19 edge descriptors + 5 `cond`.
- Reproduce: `uv run python scripts/eval_synthetic.py --data data/synth160 --no-fp16`
  (features cached as `feat_dinov2_vits14_L1_fp32.npz`). The psf-autofocus generator
  used here is now vendored as `dino_autofocus.synth` / `scripts/make_dataset.py`.

## Single frame, valid frames, DoF units (dz = stage - best focus)

| features / head          | signed MAE | sign acc (\|dz\| >= 1) | \|dz\| MAE |
|--------------------------|-----------:|-----------------------:|-----------:|
| predict 0 / predict mean |       6.60 |                      - |       3.41 |
| classical / ridge        |       6.43 |                   0.57 |       2.08 |
| classical / MLP          |       6.21 |                   0.58 |       1.85 |
| DINO + cond / ridge      |       6.22 |                   0.58 |       1.44 |
| DINO + cond / MLP        |       6.72 |                   0.57 |       1.29 |
| DINO + classical / MLP   |       6.55 |                   0.59 |       1.27 |

## 17-plane z-scan, error of the chosen focus in DoF (106 stacks)

| method                                  | median |   p90 | < 0.25 DoF |
|-----------------------------------------|-------:|------:|-----------:|
| argmax tenengrad + parabola             |  0.088 | 0.298 |       0.86 |
| argmax vollath4 + parabola              |  0.087 | 0.386 |       0.80 |
| argmax brenner + parabola               |  0.093 | 0.354 |       0.83 |
| min predicted \|dz\|, classical / MLP   |  0.155 | 0.867 |       0.66 |
| min predicted \|dz\|, DINO + cond / MLP |  0.228 | 1.263 |       0.51 |

## Reading

1. **Signed z-error from one frame: no feature set does it.** Sign accuracy is 0.57-0.59
   and MAE is no better than predicting 0. Expected: in this simulator the sign is only
   carried by depth-induced spherical aberration. Direction needs two frames (dual plane
   or a probe step), which also matches the soft-matter-agents step_up/step_down verdict.
2. **Defocus magnitude from one frame: DINO is better.** |dz| MAE 1.27-1.29 DoF vs 1.85
   for the classical set, against 3.41 for a constant. Useful for a coarse "how far out"
   estimate and step sizing.
3. **Final focus from a z-scan: classical wins.** Tenengrad/vollath4 argmax reaches
   0.09 DoF median, 86 % within 0.25 DoF; DINO-based plane picks are 2-3x worse.
   Keep a deterministic sharpness maximum as the fine stage and as the fallback
   (soft-matter-agents task 026 already requires one).

## Latency on the GTX 1650 SUPER (`scripts/bench_latency.py`)

| model     |  px | batch | fp32 ms | fp16 ms |
|-----------|----:|------:|--------:|--------:|
| ViT-S/14  | 224 |     1 |     9.2 |    32.7 |
| ViT-S/14  | 518 |     1 |    45.9 |   179.2 |
| ViT-B/14  | 224 |     1 |    27.7 |   121.9 |
| ViT-B/14  | 518 |     1 |   144.7 |   585.5 |

fp16 autocast is ~4x *slower* than fp32 on this card (no tensor cores). `DinoExtractor`
still defaults to fp16 because the microscope PC (RTX A4000, tensor cores) is the
reference machine and the heads in `models/heads` were trained on fp16 features; pass
`fp16=False` / `--no-fp16` on GPUs like this one. A4000 latency not measured yet.

## Limits of this check

- 160 scenes; one backbone (ViT-S/14), last block only, CLS + mean patch.
- Widefield fluorescence only. The soft-matter-agents first-focus target (glass/water
  interface in transmitted brightfield) is not simulated by psf-autofocus.
- Not tested: empty-field / no-sample detection, real frames, Cell-DINO.
