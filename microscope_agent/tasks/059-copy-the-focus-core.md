# 059 — copy dino-autofocus's focus core into the operator's focus search

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`.** If you are not that seat, take
nothing from this card and report up. It re-issues card 026's first stage:
the classical metrics and the verdict that read a sweep. The rest of 026 waits
on card 055 and the bench.

## The pin

**`dino-autofocus` `5cc5057`**, on branch `merge-plan/D-03f-search-no-light`
(based on `main` `bdd64da`), named by architecture on 2026-10-05. The file
bodies are those of **`ab49787`**, which `5cc5057` contains. Three earlier
pins were superseded: `81a895b` carried the constants and the model branch;
`4de8586` still carried model grade vocabulary; and `b802837` was the first
copy's pin, **and that copy stopped correctly**. `focus_search.py` carried Aura
line and power defaults and `MAX_EXTENSIONS = 3` in code.

At this pin the `dino-autofocus` side has changed its own source so that it
can cross without edits:

- the camera ceiling, the bin size and the block count in `focus_classical`
  are now **required arguments with no module defaults**:
  `frame_stats(ceiling=)`, `peak_brightness(img, bin_px)`,
  `block_scores(img, n)`. `score()` refuses the peak metric without `bin_px`;
- the model-reading branch and the model grade vocabulary are gone from
  `focus_verdict`;
- **`aura_line` and `aura_percent` are gone from `focus_search`**: the plan
  sets the light and the search never does;
- **`max_extensions` is a required `FocusArgs` field**, a whole number of at
  least 0, with no default.

## Two gates before you start

1. **Card 055 has landed on mock.** The focus search's place exists only once
   it does (plan.md 11-24, 3ba8733), and 10.2 says no code crosses before its
   place exists.
2. **`5cc5057` is reachable on the remote.** Pushing it is the person's
   decision, and today it is not pushed. Until `git ls-remote` on
   `https://github.com/kyu-softmatter/dino-autofocus` shows it, do nothing
   here. Do not copy from a local checkout and cite the commit as if it were
   public.

## What crosses: six files, no more

| from `dino-autofocus` at `5cc5057` | to |
|---|---|
| `microscope_agent/src/focus_classical.py` | `microscope_agent/src/focus_classical.py` |
| `microscope_agent/src/focus_verdict.py` | `microscope_agent/src/focus_verdict.py` |
| `microscope_agent/src/focus_search.py` | `microscope_agent/src/focus_search.py` |
| `microscope_agent/tests/test_focus_core.py` | `microscope_agent/tests/test_focus_core.py` |
| `microscope_agent/tests/test_focus_contract.py` | `microscope_agent/tests/test_focus_contract.py` |
| `microscope_agent/tests/test_focus_search.py` | `microscope_agent/tests/test_focus_search.py` |

They run alone: `focus_verdict` loads `focus_classical` as a sibling and
nothing else, using numpy and the standard library only. **The `dino-autofocus`
side reports 15 tests run in isolation.** Run the six in isolation at
`5cc5057`, outside this tree, and then again here after the copy. **The count
must be 15 in both places.** A difference is a stop, and so is any failure.

**Explicitly out:**

- `focus_run_log` and its test: the run-log shape is this repository's
  (card 057), and the librarian discarded it;
- `focus_step_rules`: guard logic, which `_operation_gate` and card 055
  own. Two implementations of one safety comparison is what 10.2.1 exists to
  stop;
- every `map_*` file and **all model code**.

## How it crosses

- **Byte for byte, except one origin header.** If a file already carries an
  origin header naming `ab49787`, keep it as it is and add nothing. If it
  carries none, add one at the top naming the source repository, the path,
  `ab49787` as the body's commit, `5cc5057` as the pin, and the body's sha256.
  Say which case each file was. **No other edit**: no reformatting, no
  renaming, no import changes.
- **Recompute each body sha256 yourself**, from `ab49787` and again from
  `5cc5057`, with CRLF normalised to LF and excluding any origin header. The
  two must agree. Architecture relayed the values the `dino-autofocus` side
  reports, below. **Do not trust them: compare, and report any difference as
  a stop.**
  - `src/focus_classical.py`: `a1155a04c9f180ed8d257d081ff03b4e1a205d7d2d886010821e265778e9b127`
  - `src/focus_verdict.py`: `727286e55ac0f4b2b613e0bc0cc8d37b67e1c8bb7a9e8bfb18da6450b69e267c`
  - `src/focus_search.py`: `bbb8da6ff31dfa01a44fc13edb77c86fd1e60e2ab4422589bae6e7130a83e720`
  - `tests/test_focus_core.py`: `401dc7ec20c99e857db5e4a8266f8cbc1c553d6023e9d6cc3e21f912797f4d11`
  - `tests/test_focus_contract.py`: `d863c62cee1f1894ee92a7e395ac53408bd7e0aeae4902a861f48b9b5407c3d4`
  - `tests/test_focus_search.py`: `317b654a3c42dab90fef5e79fa312ef2eaa5dff48e78394577122c8afe766c20`

  **All three source files now differ from the store's `fa97903` records**
  (`2fa776fa…`, `07bc1342…` and `7ffaf28f…`), because each was changed for
  this copy. That difference is expected; report it, it is not a stop. Compare
  only against the values above and between the body commit and the pin.
- **One line per file in `microscope_agent/rulings.jsonl`**, in the shape the
  file already uses: `ruling` (`transfer` for a file that crosses whole),
  `item` (the path and what it is), `slot`: *the operator's focus search
  (plan.md 11-24)*, `rule`: *10.3*, plus `by`, `at` and `recorded_from`. The
  last names `5cc5057`, `ab49787` and the body sha256.

## What is already ruled at this pin (architecture, 2026-10-04 and 2026-10-05)

Put these in the rulings lines, and check each against the code rather than
taking it on trust.

- **Four numbers stay in the code, as definitions and guards, and transfer:**
  `2**bits - 1`, the 3 px minimum block, the 99.9th percentile (`p999`), and
  the epsilons that guard divisions. If you find any other numeric literal,
  stop rule 2 below applies to it.
- **`focus_verdict`'s `GRADES` (`"measured"`, `"computed"`) are origin kinds,
  not this repository's E-grades.** This repository's logger derives E1 or E4
  from them, and **nothing here copies that field as a grade**. A grade is
  derived from a source, never self-reported, so a field named "grade" that
  carries a self-description would be exactly the thing that rule forbids.
  The copy brings the vocabulary in unchanged. The code that reads it later,
  in this repository, has to derive the grade, and your report must say so.
- **`GRADE_COMPUTED` in `focus_search` is the same kind of thing**: an origin
  kind, which carries a line saying so, and never an E-grade.
- **The four new arguments sort as follows:**
  - `ceiling` is **a fact about the camera**, an integer in ADU: the full-scale count for this
    camera in this readout mode. It needs a `kb:` source, and **today the store
    holds no such entry**. The adapter's self-reported `BitDepth 16` is not one,
    and the store records the camera misreporting its own bit depth. So it is a
    gap, never a default;
  - `bin_px` (integer px), `n` (integer blocks per side) and
    `max_extensions` (a whole number of at least 0) are **the plan's choices
    of method**. They carry no source and no grade.
  - The plan supplies all four from `focus_search` in `plan.schema.json`,
    added at the same time as this repin. Read them from there; never wire a
    value into code.

## Stop and report up, and copy nothing, if any of these is true

**The card cannot both forbid edits and let a forbidden thing through.** If a
file can cross only by being edited, it does not cross under this card.

1. **Model code in any of the six.** The model-reading branch is meant to be
   gone. If any function, branch or import in the six still takes a model
   reading, stop.
2. **A figure written into code beyond the four ruled above**: a clip level,
   a grid or bin size, any threshold or default about this instrument or a
   camera, and any light setting. Also a default value left on `ceiling`,
   `bin_px`, `n` or `max_extensions`. 10.3 says a
   number crosses only through the librarian, never pasted into code.
3. **A test that needs an import or path change** to run here.
4. **A body sha256 you compute differs** from the relayed value, or between
   `ab49787` and `5cc5057`; or the test count is not 15 in both places.

In each case, report up which file, which line, and why. The decision on how
it may cross is architecture's and the person's, not this card's.

**Where the four values come from in a plan.** `focus_search` in
`plan.schema.json` carries them, and check 88 checks them:
`metric_arguments.bin_px`, `metric_arguments.blocks_per_side`, `max_extensions`,
and `camera_ceiling`. The ceiling names either a `numbers[]` entry in ADU with
a `kb:` source, or a `kb_gaps` entry. **Today it is a gap, so a plan can be
written and approved but cannot run**: the code that reads it must refuse a
gap and never substitute a value. If the arguments in the code do not match
these fields one for one, stop and report.

## Boundaries

Write in `microscope_agent/src/`, `microscope_agent/tests/` and
`microscope_agent/rulings.jsonl` only. Never write `envelope/` or
`approvals/`. **No safety limit crosses**: the Z limits are the person's to
write after the bench, never carried from `dino-autofocus`'s guard tables. No
change to `SOFTWARE_MAY_COMMAND` or `NAMED_REFUSALS`. **Open no device.** The
copied code commands nothing.

Run the validator to `0 failed` under the interpreter `CLAUDE.md` names for
this computer, and read its `tree:` line. Then `git diff HEAD -- <paths>`,
then `git commit -F <file> -- <paths>` under your seat, naming all six files
and the rulings file. Confirm with `git log -1`, and push with
`git -c credential.helper=manager push origin feature/autofocus-ui`. Never
force, never amend.

## What comes back

To this seat, 8 lines at most:

- the commit;
- the six body sha256 values you computed, and whether each matches;
- the test count, there and here;
- which files had an origin header already;
- any numeric literal beyond the four ruled ones;
- each new argument's unit;
- any stop, with its file and line.
