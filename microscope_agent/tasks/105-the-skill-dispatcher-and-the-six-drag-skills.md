# 105 — the skill dispatcher, and the six drag skills

Written by a design session (root, committing as `design`) on 2026-11-11, on
branch `calculator-runner`. You read this; you do not edit it. It replaces the
card of the same number on branch `calculator-skills`.

**For a microscope planning session** (cwd `microscope_agent/`). Build and test
on mock and on paper only. Nothing here opens a device. If you are not a
microscope planning session, take nothing from this card and report up.

## Why

plan.md §4.5.2.2 is the design, and read it first. In short:

- **A skill is code that does one thing for one reason.** A `bound` skill
  computes one maximum, one minimum or one value of one parameter.
- **A skill runs only through one dispatcher.** A session never runs a
  skill's script and never types a value.
- **Code decides the candidates, and the model chooses among them.**
  - `contracts/skills.json` says which skills and legacy inequalities are
    candidates for a question.
  - The session answers for every candidate, `used` or `not_applied`, with a
    reason for either. An unanswered candidate fails the run.
  - A candidate marked safety is always used, and a decision the person fixed
    stays as fixed. Neither is the session's to choose.
- **The run-time gates do not change.** Do not touch `microscope_runtime/`.

The pilot question is `trapped_particle_drag_coefficient` on `transmitted`.
The table holds six planned skills for it, 37 legacy inequalities (one of
them marked safety), and 36 suggestions that bind nobody.

## What to build, in `microscope_agent/src/`

### 1. The dispatcher, `src/run_skills.py`

- **Two calls.**
  - *List:* given a question id, its revision and a configuration, print the
    candidates, what code and the person already decided, and the
    suggestions.
  - *Run:* given the same, plus the session's answers, run and write the
    sheet.
- **The candidates.** Derive them with `candidates()` from
  `contracts/tools/skills.py`. Load that file by path, and do not copy its
  logic. The commit gate derives the same list, and two copies would drift.
- **The answers.** A file the session writes: for each candidate in
  `for_the_model`, a verdict and a reason of at least a sentence.
- **Refuse the whole run** when:
  - a candidate is unanswered;
  - an answer names something that is not a candidate;
  - an answer tries to decide a safety candidate or a fixed decision.
- **Run every candidate marked `used`**, including those code and the person
  decided.
  - Bind each manifest input to where its value comes from: the librarian's
    recorded answer (`kb:<entry_id>`), the goal (`goal:<design_input>`), or
    another skill's output (`<skill>@v<N>:<output>`).
  - Ask the librarian only for inputs that a skill in the floor names.
- **Refuse before any code runs** when an input is missing or unknown.
  Write `verdict: "refused"`, and `requires` with each missing input and its
  manifest `obtained_by`.
- **Check the outputs against the manifest.** An output the manifest does not
  name fails the run.
- **Grade each value** as the worse of E4 and its worst input.
- **Write the run sheet** into the question's folder, as
  `contracts/schemas/skill_runs.schema.json` defines it:
  - every candidate, each once, with who decided it (`model`, `person` or
    `code`), the verdict and the reason;
  - `planned_missing` for the planned skills that apply;
  - `incomplete_because` for each used skill whose run was refused or failed,
    with the parameter and side it would have bounded;
  - one record for each skill that ran.
- **A session never writes the sheet.** Only this program does. The session's
  answers file is an input, and it stays in the question's folder beside the
  sheet.

### 2. The six skills, in `src/skills/`

Each skill is two files, named for its id and version:
`<id>_v1.py` and `<id>_v1.cases.json`. The manifests are in the table's
`planned[]`, and the generated pages are in `.claude/skill-docs/`.

| skill | side | what it computes |
|---|---|---|
| `drag_parallel_to_wall` | value | bulk drag times the parallel wall correction, at a height |
| `wall_correction_validity_floor` | min | the lowest height at which the series is as accurate as its source states |
| `wall_effect_resolvable_ceiling` | max | the highest height at which the wall still changes the drag by more than the target |
| `drag_record_length_floor` | min | the shortest record from which the fitted drag reaches the target |
| `camera_blur_ceiling` | max | the longest exposure inside the range where the blur correction holds |
| `bead_height_from_nominal_focus` | value | height from nominal focus travel and the measured focal-shift factor |

Rules for each script:

- **One pure function,** the manifest's `entry.function`. It takes the inputs
  as one mapping and returns the outputs as one mapping.
- **No I/O and no device.** Import only `math`, `statistics`, `json`,
  `typing`, `dataclasses`, `collections`, `itertools`, `functools`,
  `fractions`, `decimal`, `re`, and sibling skill scripts.
- **No judgement in the code.** A target, a margin or a multiple is an input
  the manifest names. Where the source gives a validity limit, that limit is
  an input too.
- **Cases from the source.** The cases file is a list. Each case has `name`,
  `inputs`, `expect`, `tolerance` (`rel`), and `worked`, which says how the
  expected value follows from the source. A skill needs at least one case
  that runs. A case that cannot run yet carries `not_run` with its reason.
- **Where the cases come from.** They wait on the librarian's task 066,
  which enters the source records with the worked values. Do not invent a
  case from memory.

### 3. The axis modules read the sheet

- An axis no longer decides whether an inequality applies. It reads the run
  sheet.
- **A legacy inequality the sheet marks `used`:** the axis computes it as
  today.
- **A legacy inequality the sheet marks `not_applied`:** write
  `state: "abstained"`, `kind: "not_requested"`, with the sheet's reason.
  That kind is written if and only if the sheet says `not_applied`.
- **A skill's value:** the axis copies it into the card as an inequality
  entry, with the skill named in its basis.
- **A question the table does not cover:** the axis behaves exactly as today.

### 4. Tests, in `tests/`

- The dispatcher refuses on a missing input and names how it is obtained.
- It refuses a run with an unanswered candidate.
- It refuses an answer that marks a safety candidate `not_applied`, and one
  that overrules a fixed decision.
- It writes every candidate once.
- A used skill that was refused appears in `incomplete_because`.
- Each skill's cases pass.

Watch each test fail before it passes.

## What not to do

- Do not edit `contracts/`, the generated files under `.claude/`, or this card.
- **Landing a skill takes two commits, in this order.**
  1. Your commit, under `microscope`: the script and its cases.
  2. A design session's commit: the manifest moves from `planned[]` to
     `skills[]`, with the source pinned.

  Report up when the first is in.
- A landed skill is never edited. A change is `_v2`.
- Do not compute any bound in conversation.
- Do not touch `microscope_runtime/` or any run-time gate.

## Done when

1. The tests pass on mock, and `python contracts/validate.py` ends `0 failed`
   under the interpreter your computer's line in the root `CLAUDE.md` names.
2. **The pilot comparison is run on paper.** Write one goal for a drag
   question: one bead size, a height series, the 40x water objective. Run S3
   on it twice:
   - once through the dispatcher;
   - once as today.

   Report, for each run, the inputs asked of the librarian, the gaps
   recorded, and the bounds returned, refused and not applied. Include every
   reason the session gave for a `not_applied`, word for word, so the person
   can read them.
3. Commit under `microscope`, through the tool, on branch `calculator-runner`,
   and only once the person has said to commit.
