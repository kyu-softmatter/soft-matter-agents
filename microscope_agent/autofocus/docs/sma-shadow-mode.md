# DINO shadow mode design (for soft-matter-agents 13.1·13.2) — 2026-10-07

This is the dino side's design proposal, made at the request of the SMA lead session (2026-10-07). **It is only a proposal and decides nothing.** The deciders are
the person and the SMA seats: the person sets the thresholds and the success criteria, SMA architecture changes pixi, and a microscope seat implements it
(SMA plan.md 13.3). This document writes nothing in the SMA tree.

## 0. One-line summary

DINO scores are **only recorded, beside** the classical verdict. They choose nothing, move nothing and stop nothing. The record is a separate run log
event (`focus_shadow`), and model numbers enter it only as ungraded `signals`. The person looks at the records compared against focus set by hand on
real fields of view and picks the thresholds later (13.1 item 3). Until then, only the classical verdict and the plan move the sample.

## 1. Grounds

- **SMA plan.md 13.1 (shadow mode first):** emits signals only (no abort, no permission). The output is append-only events in `log.json`, and the choice and
  the confidence are carried as signals. It enters no card's `numbers[]` (E6). It only records, in real runs, and the person picks the
  thresholds from those records. A run must say whether the watcher was on.
- **SMA plan.md 13.2 (finding focus):** the model only picks a branch, and code builds the commands from plan fields. The position found is a device reading.
  The success criteria are declared before starting: the reference is the focus a person sets by hand on the same field of view, beside it a baseline of the deterministic metric's maximum,
  the tolerance is a fraction of the depth of field from the KB, N fields of view, and right, wrong and `unsure` counted separately (`unsure` is an abstention, not a wrong answer).
- **Synthetic results — the two sources disagree. Both are written down.**
  - The user's statement (2026-10-07, relayed by the SMA lead session): the microscope PC holds about 6000 synthetic images per magnification, DINO was trained
    on them, and focus detection was about 97 %. This repository has no record of that training. Ask the person what was counted as "focus detection" (in-focus/out-of-focus classification?
    sign? choosing a plane?) and where the records are (§7).
  - This repository's records (`docs/synthetic-results.md`, 2026-09-30, 160 scenes, GTX 1650): getting the sign from one frame 0.57–0.59 (no better than
    a constant); distance (|dz|) estimation is better with DINO (1.27–1.29 DoF against classical 1.85); **for the final focus of a 17-plane scan the classical one is better**
    (tenengrad median 0.088 DoF, 86 % within 0.25 DoF; DINO 2–3 times worse). `models/heads/head_k100x_dinov2_vits14_L1.json`
    (k100x synthetic): sign accuracy 0.86 (|dz| ≥ 1), 0.36 within 1 DoF, readable-frame discrimination 0.92.
  - Either way, **these are synthetic results, not measurements, and in SMA a model number is E6**. The 97 % is written down only as a synthetic baseline.
  - The same direction as this repository's conclusion: keep the classical metric's maximum as the final step and as the comparison baseline (the last paragraph of SMA 13.2, task 026).

## 2. What shadow mode does and does not do

| Does | Does not |
|---|---|
| Computes the DINO reading (dz, sigma, number of readable tiles) for every classical sweep or live frame | Pick a branch (`in_focus` etc.) and hand it to the operator |
| Records it in the run log next to the classical verdict for the same frame | Issue any command to Z, XY, illumination or shutters |
| The run records "shadow mode on/off" | Abort, `stop_criterion_violated`, void a scope approval |
| Collects the records into grounds for the person to pick thresholds from | Set thresholds itself, or put numbers into a card's `numbers[]` |

## 3. Event shape (run log)

In SMA's `contracts/schemas/run_log.schema.json`, `$defs/event` requires only `t_mono` and `time_base` and allows other keys. The shape below is proposed
in the same way as the contract of dino's `focus_run_log.py` (D-07: verdict events carry no command keys).

```json
{
  "t_mono": 12.5,
  "time_base": "software",
  "event": "focus_shadow",
  "frame_index": 7,
  "z": {"value": 3010.0, "unit": "um", "grade": "E1", "read_from": "z_drive"},
  "classical": {"event_ref": "focus_verdict", "frame_index": 7},
  "signals": [
    {"name": "dz", "value": 0.4, "unit": "DoF"},
    {"name": "sigma", "value": 0.9, "unit": "DoF"},
    {"name": "n_used", "value": 3},
    {"name": "p_valid", "value": 0.97},
    {"name": "model_branch", "value": "in_focus"}
  ],
  "model": {"backbone": "dinov2_vits14_L1", "repo_commit": "7764ea0", "head_sha256": "<hex>"}
}
```

- `event` is `focus_shadow`: it is a different kind from the classical verdict (`focus_verdict`), so a noisy signal is not read as a stop criterion
  (the same reason as the `watcher_flag` in 13.1 item 1).
- Every model number goes under `signals`, **without a grade**. The branch the model picked is also a signal (`model_branch`), not a choice.
- `z` is the encoder reading for that frame (E1), not a model value.
- There are no command keys (`params`, `channel`, `action`, `from`, `verification`, `deletion`). A shadow event is not a command.
- `model` lets what produced the score be reconstructed: the backbone name, the dinov2 clone commit, and the sha256 of the head file.
- The run start event carries `shadow: {on: true|false, model: {...}}` (13.1 item 4: a run says whether the watcher was on).

## 4. File locations — split the torch side from the numpy side

dino's DINO path is currently split into three.

| Part | Where it is in dino now | Depends on | Proposed place in SMA |
|---|---|---|---|
| frame → tile selection | `live.select_tiles` | numpy | a flat file (stdlib + numpy) |
| tile → DINO features | `backbone.DinoExtractor` | **torch** + the dinov2 clone | a separate feature extractor, not in `devices/` (the only place that uses torch) |
| features → dz·sigma·p_valid | `focus/head.py` `NpzHead` (arrays only, no pickle) | numpy | a flat file |
| reading → verdict signal | `microscope_agent/src/focus_verdict_model.py` | stdlib | a flat file (already in dino, outside the copy until 13.1) |
| signal → run log event | (new) building the `focus_shadow` event | stdlib | a flat file |

- The only place that needs torch is **feature extraction**. The rest is numpy, so it passes SMA's `mic` environment and check 82 (import declarations) as they
  stand today. So the copy can be split in two: the numpy side first (tiles, head, verdict signal, event), and torch after the pixi decision.
- `focus_verdict_model.py` does not cross into SMA until 13.1 opens (D-03c). When it crosses, it carries dino's provenance header and body
  sha256 unchanged (D-03).
- The head file (`.npz`) is an artifact, not code. It is a number crossing over from another repository, so it is handled under SMA 10.3 (the head goes
  with its training record's run_id, and the grade is that side's to set).

## 5. How torch enters SMA's `mic` environment (input for architecture's pixi spec)

- Package: `torch>=2.6` (the `ml` optional dependency in dino's `pyproject.toml`). torchvision is not used for feature extraction (`backbone.py`
  imports only torch) — the recommendation is to ask SMA for torch only.
- Build: the microscope PC (RTX A4000) takes the CUDA wheel (dino uses the `pytorch-cu126` index); the development desktop also runs on CPU. How to hold both cases
  in one pixi environment is architecture's decision. The size is several GB.
- Model code: dinov2 is loaded from **a local clone at the pinned commit `7764ea0`** with `torch.hub.load(<clone>, "dinov2_vits14", source="local")`.
  It does not fetch main from the internet (the `backbone.py` header, `docs/runbooks/train-focus-head.md`).
- Weights: put `dinov2_vits14_pretrain.pth` in `<TORCH_HOME>\hub\checkpoints\` in advance (offline). Record its sha256.
- Precision: the head was trained on fp16 features. fp16 on the A4000, fp32 on cards without tensor cores (fp16 was 4 times slower on that card).
- SMA check 82: a torch import passes only after torch is declared in pixi. Until then, no file that uses torch enters SMA.

## 6. Success test (SMA 13.2 item 6, declared before starting)

- **Reference:** the encoder z of the focus a person set by hand on the same field of view.
- **The three compared:** the classical metric's maximum (+ parabola), the DINO shadow signal (`model_branch`, the plane with the smallest |dz|), and the person.
- **Tolerance:** a fraction of the depth of field. The value is the sourced depth of field in the KB; the fraction is the person's to set (this document does not set it).
- **Number of fields of view N, objectives:** the person sets them. The first target is 100x oil (the OD-21 recommendation).
- **How to count:** right, wrong and `unsure` (abstention) are counted separately. An abstention is not a wrong answer.
- **Synthetic baseline:** the user's statement "약 97 %" (about 97 %) and the numbers in this repository's `synthetic-results.md` are written side by side. The records from real fields of view
  take their place. During shadow mode this test **only records** its results and changes nothing. The thresholds are picked by the person who has looked at those records.

## 7. Thursday (10-08) bench evaluation procedure — with no SMA motion

Purpose: to record, for the **first** time, how well the classical metric and DINO agree with a person's hand focus on real fields of view. Only the person handles the instrument. The software
only reads camera frames and moves nothing (dino `mm_real`'s `BENCH_MOTION` stays LOCKED). Scores are not computed at the
bench but **later**, on the development desktop, from the saved frames (this cuts the risk and the time at the bench).

| Step | What the person does | What is recorded |
|---|---|---|
| 1 | Choose an objective (100x oil first); the person sets the illumination by hand (B-01 is a visit without a plan) | objective, illumination settings, exposure, readout mode |
| 2 | Pick one field of view and focus it by hand | the ZDrive reading at that moment (z0), the field of view's XY reading |
| 3 | Pass through several planes around z0 in turn with the focus knob, taking a frame at each | the ZDrive reading and the frame file for each plane |
| 4 | Repeat 2–3 on other fields of view | the same entries for each field of view |
| 5 | (optional) one field of view with no sample in it | frames for `no_sample_here` |

- **Entries the person sets (no proposed values):** the number of fields of view N, the spacing and number of planes around z0, the list of objectives. This document proposes no numbers
  — bench numbers are set by the person (the D-02 principle).
- The record form is made by adding these entries to `docs/runs/templates/bench-visit-1.template.*` of the dino bench session ("AF bench · B-01 awaiting record (10-08)")
  (that session owns the form).
- Later analysis: for each saved frame, compute the `focus_classical` metrics, `focus_verdict.from_sweep` and the DINO reading (`live.FocusScorer`), and count them into the §6
  table. The result files go in dino `docs/runs/`, and only de-identified records go to SMA (the R-03 rule).

## 8. What to ask the person

**The person's answers (2026-10-07, in the dino merge-planning session's window):** 1 — "인식률이 97 %" (the recognition rate is 97 %) (what was counted as a hit is not written down yet);
2 — asked for an explanation of the word "헤드" (head) (the head = the small model that turns DINO features into the focus distance dz, the uncertainty sigma and readability p_valid;
asked in turn whether one was trained separately for each magnification, and the person's answer: "배율마다 따로 만들었을 것" (I would have made one per magnification) — an answer from memory, so the head files and
their location must be checked on the microscope PC. This repository has only the 100x head); 3 — **fluorescence**; 4 — the number of fields of view, plane spacing and objectives **will be decided next Monday (10-12)**;
5 — "0.1 DoF?" (a proposal and a question at once; see §6: in this repository's synthetic records the classical metric's median error is about 0.09 DoF, so at 0.1 DoF
the classical one also misses about half the time. At 0.25 DoF the classical one was at 86 %. The recommendation is to count with both tolerances together — the person decides). Then the person's further answer: **the depth of field (tolerance) is decided on site** — at the bench, by looking at real fields of view.


1. What does "focus detection about 97 %" count (in-focus/out-of-focus classification, sign, choosing a plane), and where are its training and evaluation records (the path on the microscope PC)?
2. Is there a separate head for each magnification? This repository has only `head_k100x_dinov2_vits14_L1`.
3. Are the synthetic images fluorescence or brightfield? This repository's synthesis is fluorescence, and it did not imitate SMA's first focus target (a glass/water interface, brightfield).
4. For Thursday's evaluation: the number of fields of view, the plane spacing and count, and the list of objectives.
5. The tolerance fraction for the success test (how many times the depth of field).
