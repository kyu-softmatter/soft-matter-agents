# 081 — the four judgements of plan.md 13.5, record-only

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat. Start after
card 076 lands.** It builds on 076's backend interface and renderer, and all
three cards (069, 076 and this one) edit the same files, so they go one at a
time. If you are not that seat, take nothing from this card and report up.

## Why

On 2026-10-19 the person took an outside handoff document as the
implementation specification, with every part that conflicts with our
safety rules asked first (`a1f3feca`). The person then answered this
section's two conflicts (`04e3985f`):

- every judgement records only first, and acts only after the person
  chooses its threshold from the record;
- the two judgements made before measuring are added record-only, and wait
  for the XY design before they can lead to a move.

plan.md 13.5 (`1cb437d5`) is the specification. **Read it whole before
starting.**

| | Question | Asked |
|---|---|---|
| DM-1 | are the particles the fixed code detected suitable? | after detection, before a field is measured |
| DM-2 | is this field of view suitable? | before a measurement starts |
| DM-3 | is an anomaly visible that the fixed checks cannot settle? | during a run. **This is card 076's watcher, not a second one** |
| DM-4 | can the failure's cause be identified, and as what? | after a stop, on the saved evidence |

## What is already in `contracts/` (this card's commit)

- **`judgement.schema.json`**, one shape for all four. It is named
  "judgement", not "decision", because a `decision` event already records
  the person's own decisions in bench logs.
  - `request`: `judgement` (DM-1, DM-2 or DM-4), `seq`, `point`,
    `prompt_version`, `allowed_answers` (YES, NO), `allowed_codes` (the
    plan's list), `images`, `context_sha256`, `context_path`,
    `asked_t_mono`.
  - `response`: `status` (OK, ABSTAIN or ERROR); `answer` (YES or NO),
    present only when OK; `score`, only if the model gives one; then
    `reason_codes` for DM-1 and DM-2, or `cause_label` for DM-4, plus
    `error` when ERROR, `model`, `prompt_version` and `answered_t_mono`.
  - DM-4's `unknown` is a NO, never a cause, and a DM-4 YES names its cause
    label.
  - `dm3`: how a watcher answer reads as DM-3. NO is `as_planned`, YES
    carries the plan's other option as `class`, ABSTAIN is `unsure`, and
    ERROR is `watcher_unanswered`, not a flag.
- **The plan's `judgements` block**, with `dm1`, `dm2` and `dm4`. Each has
  `points`, `prompt_version` and `frames` (the watcher's shape: whether
  reduced images are given, and how they are made), plus `reason_codes`, or
  for DM-4 `cause_labels`, with `unknown` always present. **There is no
  threshold field, by design.** A fixture shows a threshold refused.
- **The run log**:
  - events `judgement_asked` and `judgement_answered`, with the payload
    under `judgement`, `from` set to `judgements.dm1`, `.dm2` or `.dm4`,
    and none of a command's keys;
  - `watcher_flag` now also carries `judgement` (its DM-3 reading) and
    `prompt_version`.

## What to build

All of it goes in flat files in `microscope_runtime/src/`, behind card 076's
backend interface, and none of it imports `devices/`.

1. **DM-3 on the watcher.** Every `watcher_flag` writes its `judgement`
   reading and its `prompt_version`, mapped exactly as above. No second
   watcher.
2. **DM-1, DM-2 and DM-4**, each asked at **every** point the plan names,
   normal points included, so a false-alarm rate can later be counted.
   - Each request is written as `judgement_asked` with its context text
     kept whole in the run folder as `judgement_<seq, 6 digits>_context.txt`,
     with its sha256.
   - Each answer is written as `judgement_answered`; an ERROR carries
     `error`.
   - DM-1 and DM-2 may also be given the fixed code's detections as
     context.
   - DM-4's input is the rolling pre-stop buffer of reduced frames the
     person chose for a stop (Q5, in plan.md 4.6 at `300a44f9`), asked after
     the abort has finished, never during it.
3. **Prompt versions**, keyed by judgement and plan, logged with the model's
   name and version, so each answer replays.
4. **Record only.** No code path runs from any answer to a move, a skip, a
   retry, a recovery, the stop channel or a prompt to the person. **DM-2
   leads to no move**, and none can exist until the XY design does.
   Recovery after DM-4 (Q1, Q2) is not this card's.
5. **Backends.** `none` asks nobody. The test double answers all four and is
   refused off mock. Images go only as card 076's reduced copies; the raw
   frame never leaves.

## Tests, each watched failing first

1. Every `watcher_flag` carries a DM-3 reading that matches its choice.
2. DM-1, DM-2 and DM-4 are each asked at every point the plan names, and an
   omitted point fails the test.
3. No path from any answer to the stop channel, a device call or a prompt to
   the person. Card 058's style of test fits.
4. DM-4 is asked only after the abort completes, and its images are the
   pre-stop buffer's reduced copies.
5. Every logged request and answer validates against `judgement.schema.json`.
6. The test double is refused off mock.

## Boundaries

- Write `microscope_runtime/src/` and `tests/` only.
- No `contracts/`, and no `envelope/` or `approvals/`. Mock only.
- Commit and push through `contracts/tools/seat_commit.py`, naming each
  path. Never `--no-verify`, `--amend` or force.

## What comes back

To this seat, 5 lines at most:

- the commits;
- the points each judgement was asked at on one mock run, with counts;
- each test, watched failing, then passing;
- the suite's counts;
- every place the schema did not fit, with the field.
