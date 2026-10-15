# Integration notes (analysis of 2026-09-30)

Findings from reading facebookresearch/dinov2 @ `7764ea0` and the three repos this package
connects to. File references are to those repos at the commits cloned on 2026-09-30.

## facebookresearch/dinov2

- Inference with a frozen backbone needs only `torch` (+ `torchvision`). Do not install
  the repo's `requirements.txt` (Linux training stack, torch 2.0 + xFormers 0.0.18 pins).
- xFormers is optional: `dinov2/layers/{attention,block,swiglu_ffn}.py` fall back to
  PyTorch SDPA. `XFORMERS_DISABLED=1` forces the fallback and is set by `DinoExtractor`.
- Python >= 3.10 in practice (`float | None` annotations evaluated at import), despite
  `setup.py` saying 3.9.
- `torch.hub.load("facebookresearch/dinov2", ...)` fetches current `main`. This package
  loads a local clone with `source="local"` and refuses to run if its HEAD is not
  `DINOV2_COMMIT` (`src/dino_autofocus/backbone.py`).
- Input H, W must be multiples of the patch (14 px); positional embeddings are
  interpolated, so non-square and non-518 sizes work.
- Licences: DINOv2 code and weights Apache-2.0. Cell-DINO weights: FAIR Noncommercial
  Research License (no commercial use of weights *or outputs*), gated behind a request
  form. Channel-adaptive DINO (`channel_adaptive_dino_vitl16`, `in_chans=1`) is the
  Cell-DINO variant that fits single-channel frames.
- Cell-DINO's recommended preprocessing standardises each channel per image, which
  removes the contrast drop that is itself a defocus signal.
- Local-path weight loading in `cell_dino/backbones.py:60` uses `torch.load` without
  `weights_only`; safe by default only on torch >= 2.6 (this package requires >= 2.6).

## psf-autofocus (training / benchmark data)

- Synthetic widefield-fluorescence z-stacks: `scripts/make_dataset.py`, shards of
  `image` uint16 (N, H, W) with `dz_um`, `dz_dof` (dz = stage - best focus), `valid`,
  `cond` (NA, wavelength, pixel size, DoF, log10 signal), `scene_id`, `family`.
- Sign of dz from one frame exists only through depth-induced spherical aberration; an
  index-matched sample needs two frames (`DualPlane`).
- Known issues found while reading (not fixed here):
  - `ModelEstimator` hardcodes 3 profile channels / 19 descriptors
    (`afocus/models/estimator.py:84-87`) while training builds 4 / ~60
    (`afocus/train.py:337-347`), so edge/hybrid checkpoints would not load.
  - `log10_signal` is computed differently at training (`sim/dataset.py:309`) and
    inference (`models/estimator.py:109`).
- Generation cost on this PC (16 logical cores, 64 GB): ~10 s/scene aggregate with 8-10
  workers at 224 px x 17 planes. 15 workers exhausted the commit charge and crashed a
  concurrent torch process (Windows 0xc000070a).

## autofocus-jev (hardware loop)

- `Microscope` protocol (`hardware/base.py`) and `PyMMCoreMicroscope`: mono uint16
  frames, relative Z moves only, `|dz| <= probe_step_um` (0.2 um default), Z within
  +-10 um, motion refused until the PFS gate is configured.
- Frame `z_um` is read at buffer-pop time, not exposure; filter frames after a move by
  `hardware_state_version`.

## soft-matter-agents (final target)

- A model-produced number is grade E6 and enters no record; the model is never in a
  safety decision. The focus seat (task 026) wants a **verdict** among declared branches
  (`in_focus | step_up | step_down | no_sample_here | unsure`), not a Z. The Z comes from
  the chosen frame's encoder read.
- Software may not move `ZDrive` today (`devices/micromanager.py` `REFUSED_CALLS`,
  `NAMED_REFUSALS`).
- Third-party imports in agent code must be declared in `pyproject.toml`
  (validator check 82), in the pixi `mic` feature for the microscope environment.
  `pyproject.toml` / `pixi.lock` belong to the architecture seat.
- **soft-matter-agents is public; this repo is private.** A dependency on
  `dino-autofocus` would break installs from a fresh clone. Decide before integrating:
  make this repo public, vendor a small inference module, or keep the dependency
  optional.
- Heavy imports (torch) go at the use site, as `devices/micromanager.py` does for
  pymmcore-plus.
- The microscope PC has an RTX A4000; the agent runs on the Windows host.
