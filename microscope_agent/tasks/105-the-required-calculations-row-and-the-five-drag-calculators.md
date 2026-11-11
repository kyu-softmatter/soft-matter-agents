# 105 — the required-calculation row, and the five drag calculators

Written by a design session (root, committing as `design`) on 2026-11-11, on
branch `calculator-skills`. You read this; you do not edit it.

**For a microscope planning session** (cwd `microscope_agent/`). Build and test
on mock and on paper only. Nothing here opens a device. If you are not a
microscope planning session, take nothing from this card and report up.

## Why

The person asked, on 2026-11-10, for each piece of code that computes a
number before a run to become a skill, with only the values actually needed
looked up. On 2026-11-11 the person said to apply it under three conditions,
on a separate branch. plan.md §4.5.2.2 is the design. In short:

1. **The calculation stays code.** A calculator is a module computing one
   inequality's bound. Its skill says when it runs and with which inputs, and
   never how to compute.
2. **A table, not a model, says what is needed.**
   - `contracts/calculations.json` declares each calculator once.
   - Its rows say, per observable and configuration, which calculators a
     question must run.
   - Every other inequality an axis owns is written as abstained, kind
     `not_requested`, with the row's reason.
3. **The run-time gates do not change.** Approvals, the safety policy, the
   configuration gate, the run lock and the orchestrator are out of scope.
   Do not touch `microscope_runtime/`.

**The pilot row.**
- **The question.** `trapped_particle_drag_coefficient` on `transmitted`, with
  the trapping composition: the drag against height above the coverslip.
- **What it names.** All 37 inequalities your seven axes own, plus five new
  calculators: 24 required and 18 not required, each with its reason.
- **Its skills.** They are generated into `.claude/skills/calc-*/SKILL.md`.
  Read them. They are what an S3 subagent follows.

## What to build, in `microscope_agent/src/`

1. **Read the table in one place.**
   - `axis_common.py` gains a reader of `contracts/calculations.json`.
   - Given a question's observable and a configuration, it returns the row,
     or `None` when no row covers them.
   - It reads by explicit path from the repository root, like the rest of
     `contracts/`.
2. **Honour the row in every axis.** When a row covers the question, for each
   inequality in the axis's `OWNED`:
   - **Required:** compute it as today, or through its calculator module (item
     3). It returns or abstains with its own kind.
   - **Named in `not_required`:** write it as abstained, kind `not_requested`,
     with that `why` as the reason.
   - **Named in neither list:** write it as abstained, kind `not_requested`,
     with the table's `default_not_requested_reason`.
   - **Gaps.** A not-requested inequality records no `kb_gaps`. Nothing was
     asked for it, so nothing was missing.
   - **No row.** When no row covers the question, the axis behaves exactly as
     it does today.
   - **The outcome entry.** It is the one `axis.schema.json` already defines:
     `state: "abstained"`, `kind: "not_requested"`, `reason`. No schema change
     is needed.
3. **The five new calculators**, one module each in `src/calculators/`. The
   path is allowed since this branch.
   - The modules:
     - `wall_correction_validity_floor.py` (A6, `bead_centre_height`);
     - `focal_shift_measured_first.py` (A6, `bead_centre_height`, a precondition);
     - `wall_effect_resolvable_ceiling.py` (A2, `bead_centre_height`);
     - `drag_record_length_floor.py` (A2, `record_duration`);
     - `camera_blur_ceiling.py` (A1, `exposure_time`).
   - **Interface.** Each module exposes one pure function. It takes the inputs
     the table's `needs` lists and the store entries its `formula_entries`
     lists, and returns one `inequalities[]` item.
   - **Inputs.** The function reads no file and opens no device. The axis
     passes it what the librarian's recorded answers hold.
   - **The formula is the entry's.** Implement the formula the entry holds,
     and cite the entry in the bound's `basis` as `kb:<entry_id>`.
   - **Refuse a changed formula.** At run time, check that the entry's formula
     text is the one the module implements. If the entry has changed, fail; do
     not compute the old formula.
   - **Missing pieces.** An entry or an input that is absent gives
     `state: "abstained"`, `kind: "no_input"`, with what is absent named in
     `missing`.
   - **No hard-coded numbers.** Never write a number into the module that
     belongs in the store: a coefficient, a validity limit, a focal-shift
     factor.
   - **The formulas do not exist yet.** The librarian's task 066 enters them.
     Until then, every new calculator abstains, kind `no_input`, naming its
     entries. That is the correct output for now, not a failure.
4. **Tests,** in `tests/`, one file per calculator, each run on synthetic
   entries:
   - a returned bound;
   - `no_input` when an entry is absent and when an input is absent;
   - a refusal when the entry's formula text differs.

   Add one test that a covered question writes every `OWNED` inequality of
   every axis, each exactly once, with no silence. Watch each test fail before
   it passes.

## What not to do

- Do not edit `contracts/`, including the table, the skills under `.claude/`,
  or this card. They are the design's.
- When a calculator is built and tested, report up. A design session then
  flips its `status` to `built` and regenerates the skills.
- When the table names an input or an entry you cannot work with, report up
  rather than renaming it in your code.
- Do not compute any bound in conversation, and do not ask the librarian for
  inputs a not-required inequality would have needed.
- Do not touch `microscope_runtime/` or any run-time gate.

## Done when

1. The tests pass on mock, and `python contracts/validate.py` (the interpreter
   your computer's line in the root `CLAUDE.md` names) ends `0 failed`.
2. **The pilot comparison is run on paper.** Write one goal for a drag
   question: one bead size, a height series, the 40x water objective.
   - Run S3 on it twice: once with the row, and once with the row ignored (a
     flag in your code, for the comparison only).
   - Report the counts both ways: inputs asked of the librarian, gaps
     recorded, and bounds returned, abstained and not requested.

   That comparison is what decides whether more rows are written.
3. Commit under `microscope`, through the tool, on branch `calculator-skills`,
   and only once the person has said to commit.
