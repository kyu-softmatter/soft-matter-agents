# Runbook: training the DINO focus head (microscope PC only)

- Target computer: **the microscope PC** (Windows, RTX A4000). Per PLAN.md §4, image synthesis and DINO training
  are done only on this PC. Do not run this runbook's commands on the development desktop (GTX 1650 SUPER).
- Who runs it: the user. Development sessions only edit this document and do not run the commands.
- Written by: AF execution 2 (T-003), 2026-10-01. The source files are listed at the end of each section.
- Outputs: `outputs/heads/head_<data>_<backbone>.npz` (the pickle-free head the live view reads), `.joblib` (the retraining
  pipeline; not put in the repository), `.json`. After review, move only `.npz` and `.json` to `models/heads/`.

The trained head's output is a **model number**. In the focus verdict (`dino_autofocus.focus.verdict`) it is recorded with grade
`"model"`, and it is not used for motion limits or safety decisions (PLAN.md §6).

## 0. Before you start

- Do not run this during hardware work. Dataset generation uses all of the CPU and memory, and feature extraction uses the
  GPU. If the live view or a scan is running on the same PC, frames lag and there is a risk of a crash.
- The working folder is the clone on the microscope PC. As of 2026-09-30, `D:\AutoFocus\dino-autofocus`.
- Disk: synthetic data and feature caches accumulate under `data/` (outside git). Free up several GB.

## 1. Environment

```
cd D:\AutoFocus\dino-autofocus
git pull
uv sync
```

`uv sync` fetches torch cu126. The DINOv2 code is read from a pinned-commit clone next to the repository.
If it is somewhere else, point to it with the `DINOV2_REPO` environment variable.

```
git clone https://github.com/facebookresearch/dinov2 ..\dinov2
git -C ..\dinov2 checkout 7764ea0f912e53c92e82eb78a2a1631e92725fc8
```

Check:

```
uv run python -c "import torch; print(torch.__version__, torch.cuda.get_device_name(0))"
uv run pytest tests/test_backbone.py -q
```

`DinoExtractor` refuses to run if the clone's HEAD is not `7764ea0`.
`tests/test_backbone.py` tests only preprocessing and does not load the model, so check the clone and the weights with §1.2.

**The DINOv2 weights are downloaded from the internet the first time they are used** (§1.1). If the microscope PC is offline, copy the files in
the §1.1 table in advance into `~/.cache/torch/hub/checkpoints` (Windows: `%USERPROFILE%\.cache\torch\hub\checkpoints`,
or `hub\checkpoints` under `TORCH_HOME` if that is set) (§1.2). The one-line check in §1.2 step 4
shows whether the files are in place.

Sources: `docs/setup-new-pc.md` §2–3, `src/dino_autofocus/backbone.py`.

### 1.1 Where the weights come from

`DinoExtractor` reads the model code from the clone with `torch.hub.load(<clone>, "dinov2_vits14", source="local")`.
The code does not go to the internet, but **the pretrained weights are downloaded from the internet the first time the model is built**
(the clone's `dinov2/hub/backbones.py`, `dinov2/hub/utils.py`, as of commit `7764ea0`):

- URL: `https://dl.fbaipublicfiles.com/dinov2/<model>/<model>_pretrain.pth`
- Download function: `torch.hub.load_state_dict_from_url`. Hash checking is off (`check_hash=False`).
  The file name carries no hash, so torch does not notice a truncated file or a different file.
- Save folder: `<TORCH_HOME>\hub\checkpoints\`. If the file is already there, it is not downloaded.
  - If `TORCH_HOME` is not set, `%XDG_CACHE_HOME%\torch`; if that is not set either, `%USERPROFILE%\.cache\torch`.
  - See the actual folder on the microscope PC with this command (it downloads nothing):

    ```
    uv run python -c "import torch; print(torch.hub.get_dir())"
    ```

    The weights folder is the output with `\checkpoints` appended.

Files this repository uses:

| Model | Used by | File name | Size (bytes) | SHA-256 |
|---|---|---|---|---|
| `dinov2_vits14` | training, evaluation, the live view head (default) | `dinov2_vits14_pretrain.pth` | 88,283,115 | `b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9` |
| `dinov2_vitb14` | `bench_latency.py` only | `dinov2_vitb14_pretrain.pth` | 346,378,731 | `0b8b82f85de91b424aded121c7e1dcc2b7bc6d0adeea651bf73a13307fad8c73` |

The sizes and hashes were measured on the files in the development desktop's cache (`%USERPROFILE%\.cache\torch\hub\checkpoints`, downloaded 2026-09-30).
They are not values the distributor published; they are the values of the files that produced this repository's results.

### 1.2 When the microscope PC is offline

On a PC with internet access (for example the development desktop), move the two things below over by USB or similar. Development sessions
do not do this copy on the user's behalf. The user does it.

**Weights files**

1. Copy the files in the §1.1 table from the cache folder of the PC with internet access. The desktop already has them.
   If it does not, download them directly from the URL on that PC.
2. On the microscope PC, create a `checkpoints` folder under the `torch.hub.get_dir()` output and put the files in it.
   Do not rename the files. torch finds the cache by the file name at the end of the URL.
3. Compare the size and hash with the table (PowerShell):

   ```
   Get-Item <checkpoints folder>\dinov2_*_pretrain.pth | Select-Object Name, Length
   Get-FileHash -Algorithm SHA256 <checkpoints folder>\dinov2_*_pretrain.pth
   ```

   If even one differs, do not use it; copy it again.

4. Check only the weights, with one line. It works without network, clone or GPU, downloads nothing, and only reads the folder:

   ```
   uv run python -c "import torch, pathlib; d = pathlib.Path(torch.hub.get_dir(), 'checkpoints'); print(d); [print(n, (d / n).stat().st_size if (d / n).exists() else 'MISSING') for n in ('dinov2_vits14_pretrain.pth', 'dinov2_vitb14_pretrain.pth')]"
   ```

   The folder path is printed, followed by the two files and their sizes. If a size matches the §1.1 table, the file is in place; `MISSING`
   means that file is absent. `dinov2_vitb14_pretrain.pth` is needed only for `bench_latency.py`.
   Run on the development desktop on 2026-10-02, it printed `%USERPROFILE%\.cache\torch\hub\checkpoints` and
   the two sizes in the table (88283115, 346378731).

   The file names are set by the code. `_make_dinov2_model_name` in the clone's `dinov2/hub/utils.py`
   builds `dinov2_<first 4 characters of arch><patch>`, and `dinov2/hub/backbones.py` appends `_pretrain.pth` to it.
   This repository's default model is `dinov2_vits14`, in `src/dino_autofocus/backbone.py`.

**DINOv2 clone** (commit `7764ea0`)

1. On the PC with internet access, do the `git clone` and `git checkout` from §1 (the desktop already has it,
   at `D:\codes\github\dinov2`).
2. Copy the folder **whole, `.git` included,** to next to the repository on the microscope PC (`D:\AutoFocus\dinov2`).
   `DinoExtractor` checks the commit with `git rev-parse HEAD`, so it refuses to run if `.git` is missing or the microscope PC
   has no `git`. If you put it somewhere else, point to it with `DINOV2_REPO`.
3. Check:

   ```
   git -C ..\dinov2 rev-parse HEAD
   ```

   It must be `7764ea0f912e53c92e82eb78a2a1631e92725fc8`.

**Check both together** (with the network off. If the weights are missing it tries to download them and fails, so what is missing shows up):

```
uv run python -c "from dino_autofocus.backbone import DinoExtractor; print(DinoExtractor().dim)"
```

If it prints `768` (ViT-S/14, CLS + mean patch of the last 1 block), the clone and the weights are both in place.
If you plan to run `bench_latency.py`, `dinov2_vitb14_pretrain.pth` must also be in the same folder.

Downloading packages in `uv sync` also needs the internet. This section covers only the weights and the clone.

Sources: `src/dino_autofocus/backbone.py`, the clone's `hubconf.py`, `dinov2/hub/backbones.py`,
`dinov2/hub/utils.py`, `scripts/bench_latency.py`.

## 2. Generating the synthetic dataset

The current head (`models/heads/head_k100x_dinov2_vits14_L1.npz`) was trained on the 100x oil fluorescence synthetic set
`k100x`. To rebuild it under the same conditions, or to add scenes:

```
uv run python scripts/make_dataset.py --out data/k100x --system-config configs/kinetix_100x_oil.yaml --fov 224 --planes 17 --workers 8
```

Main arguments:

| Argument | Meaning | Note |
|---|---|---|
| `--scenes` | number of scenes (default 400) | one z stack per scene |
| `--seed0` | seed of the first scene | change it when extending a set, so the scenes do not overlap |
| `--fov 224` | field of view in pixels | matches the head's tile size of 224 |
| `--planes` | planes per scene | `synthetic-results.md` uses 17 |
| `--workers` | number of processes, one scene each | see the memory caution below |
| `--device cuda --gpu-dtype complex64` | PSF computation on the GPU | each process takes a CUDA context, so use fewer workers |

**Memory caution**: on the development desktop (16 logical cores, 64 GB), 15 workers went over the commit limit and killed a torch
process running alongside (Windows `0xc000070a`). At 8–10 workers it took about 10 s per scene
(combined). On the microscope PC, **start with 8 workers** and raise it while watching commit usage in Task Manager.

To build the 5 µm particle set with all six Ti2 objectives, use `farm_p5.py`. It works in chunks, so it can be
stopped and resumed, and creating a `data/p5_farm.STOP` file makes it stop once the current chunk is finished.

```
uv run python scripts/farm_p5.py --scenes 3000 --dry-run
uv run python scripts/farm_p5.py --scenes 3000
```

The defaults of `farm_p5.py` (`--gpu-procs 3`, `--cpu-workers 30`) assume a large PC. Start with them reduced to fit the
microscope PC's core count and memory.

Sources: `scripts/make_dataset.py`, `scripts/farm_p5.py`, `src/dino_autofocus/synth/__init__.py`,
`docs/integration-notes.md` (the psf-autofocus section), `docs/synthetic-results.md`.

## 3. Feature extraction and evaluation

```
uv run python scripts/eval_synthetic.py --data data/k100x
```

- Caches the DINO features in `data/k100x/feat_dinov2_vits14_L1.npz`, and writes the comparison with the classical metrics to
  `outputs/eval_k100x_dinov2_vits14_L1.json`.
- On the A4000, use **the fp16 default as it is** (it has tensor cores). `--no-fp16` is for GPUs without tensor
  cores; its features are saved separately as `*_fp32.npz`, and `train_head.py` does not read them. The features used for
  training are fp16 only.
- If a cache exists, it is not recomputed. If you changed the backbone or the precision, delete the cache file and run again.

Sources: `scripts/eval_synthetic.py`, `docs/synthetic-results.md`.

## 4. Training the head

```
uv run python scripts/train_head.py --data data/k100x
```

- The fp16 feature cache from §3 must exist first.
- It builds a set of heads: `dz` (signed defocus, DoF, dz = stage − best focus), `err` (per-frame
  sigma), `valid` (whether the frame is readable). Performance is measured by scene-level 5-fold cross-validation, and the saved
  head is refit on all of the data.
- The photon-signal scalar is used only when it lowers the MAE by more than 0.25 DoF, because the camera gain (e-/ADU) has not been
  measured yet. If it does get used, `FocusScorer` refuses it, so tell the user.
- Output: `outputs/heads/head_k100x_dinov2_vits14_L1.npz`, `.joblib`, `.json`.
- `train_head.py` reads only the `shard_*.npz` directly under the `--data` folder. It does not read the chunk folder layout of
  `farm_p5.py`, so for now the p5 set is only evaluated, with `learning_curve_p5.py`.

Sources: `scripts/train_head.py`, `scripts/learning_curve_p5.py`.

## 5. Checks

Wiring check (these are scenes used in training, so it checks tiling, preprocessing, fusion and timing, not generalisation performance):

```
uv run python scripts/check_scorer.py --head outputs/heads/head_k100x_dinov2_vits14_L1.npz --data data/k100x
```

How many scenes are needed:

```
uv run python scripts/learning_curve.py --data data/k100x
uv run python scripts/learning_curve_p5.py
```

## 6. Latency measurement

```
uv run python scripts/bench_latency.py
```

Measures ViT-S/14 and ViT-B/14 at 224, 448 and 518 px, batch 1 and 8, in fp32 and fp16. On the GTX 1650
SUPER, fp16 was about 4 times slower. The A4000 has not been measured yet (open in PLAN.md §10). This table is
the basis for keeping or dropping the fp16 default.

## 7. Adopting a head

1. Compare the metrics in `outputs/heads/*.json` with the current head (`models/heads/head_k100x_dinov2_vits14_L1.json`).
   What to look at: `mae_dof`, `sign_acc_|dz|>=1`, `near_focus_mae_dof`,
   `sigma.coverage_1sigma` (near 0.68), `valid_head.accuracy`.
2. If it is better, copy the `.npz` and `.json` to `models/heads/` (the `.joblib` is a pickle and is not added). Getting it into the repository follows the development flow
   (the manager assigns, an execution session commits, a review session merges). Do not commit to `main` directly from the
   microscope PC.
3. Pass it to the live view as `--head models/heads/<file>.npz`. If you only have an old `.joblib`,
   convert it with `uv run python scripts/export_head_npz.py <file>.joblib` (open only files you trained yourself).

## 8. What to record

For every run, write down the following as text and pass it to the manager. The same result must be reproducible.

- Repository commit hash (`git rev-parse HEAD`), DINOv2 commit (confirm `7764ea0`)
- Weights file SHA-256 (whether it matches the §1.1 table)
- GPU name, driver, `torch.__version__`, CUDA version
- The full dataset command (arguments, `--seed0`, `--workers`), time taken, peak commit memory, whether it crashed
- Frame count, scene count, `valid` ratio (first line of the `eval_synthetic.py` output)
- Feature precision (fp16 / fp32)
- `eval_*.json` and the head `.json`, in full
- The `bench_latency.py` table, in full
- Whether it was adopted, and why

## 9. Do not

- Run §2–6 on the development desktop.
- Run at the same time as hardware scripts.
- Train on a mix of fp32 and fp16 features.
- Set Z limits, motion permission or gates from the head output.
- Open dataset shards (`shard_*.npz`) received from elsewhere with the training or evaluation scripts. `scene_params` is an object
  array, so `train_head.py`, `eval_synthetic.py` and others read them with `np.load(..., allow_pickle=True)`, and a pickle can run
  code when it is opened. Use only shards made on this PC with `make_dataset.py` / `farm_p5.py` (pre-release check S10).
  The engine and server side use `allow_pickle=False`, and the head reads only `.npz`.
