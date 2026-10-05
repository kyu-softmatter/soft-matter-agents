# 059 — copy dino-autofocus's focus core into the operator's focus search

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`.** If you are not that seat, take
nothing from this card and report up. It re-issues card 026's first stage:
the classical metrics and the verdict that read a sweep. The rest of 026 waits
on card 055 and the bench.

## The pin

**`dino-autofocus` `b802837`**, the tip of branch
`merge-plan/D-03c-no-constants-no-model`, named by architecture on 2026-10-04.
The file bodies are those of **`399be77`**, which `b802837` contains. Two
earlier pins were superseded before use: `81a895b` carried the constants and
the model branch, and `4de8586` still carried model grade vocabulary.

At this pin the `dino-autofocus` side has changed its own source so that it
can cross without edits:

- the camera ceiling, the bin size and the block count in `focus_classical`
  are now **required arguments with no module defaults**:
  `frame_stats(ceiling=)`, `peak_brightness(img, bin_px)`,
  `block_scores(img, n)`. `score()` refuses the peak metric without `bin_px`;
- the model-reading branch and the model grade vocabulary are gone from
  `focus_verdict`.

## Two gates before you start

1. **Card 055 has landed on mock.** The focus search's place exists only once
   it does (plan.md 11-24, 3ba8733), and 10.2 says no code crosses before its
   place exists.
2. **`b802837` is reachable on the remote.** Pushing it is the person's
   decision, and today it is not pushed. Until `git ls-remote` on
   `https://github.com/kyu-softmatter/dino-autofocus` shows it, do nothing
   here. Do not copy from a local checkout and cite the commit as if it were
   public.

## What crosses: six files, no more

| from `dino-autofocus` at `b802837` | to |
|---|---|
| `microscope_agent/src/focus_classical.py` | `microscope_agent/src/focus_classical.py` |
| `microscope_agent/src/focus_verdict.py` | `microscope_agent/src/focus_verdict.py` |
| `microscope_agent/src/focus_search.py` | `microscope_agent/src/focus_search.py` |
| `microscope_agent/tests/test_focus_core.py` | `microscope_agent/tests/test_focus_core.py` |
| `microscope_agent/tests/test_focus_contract.py` | `microscope_agent/tests/test_focus_contract.py` |
| `microscope_agent/tests/test_focus_search.py` | `microscope_agent/tests/test_focus_search.py` |

They run alone: `focus_verdict` loads `focus_classical` as a sibling and
nothing else, using numpy and the standard library only. **No count was given
with this pin**, so run the six in isolation at `b802837`, outside this tree,
and then again here after the copy. **Report the count, and it must be the
same in both places.** A difference is a stop, and so is any failure.

**Explicitly out:**

- `focus_run_log` and its test: the run-log shape is this repository's
  (card 057), and the librarian discarded it;
- `focus_step_rules`: guard logic, which `_operation_gate` and card 055
  own. Two implementations of one safety comparison is what 10.2.1 exists to
  stop;
- every `map_*` file and **all model code**.

## How it crosses

- **Byte for byte, except one origin header.** If a file already carries an
  origin header naming `399be77`, keep it as it is and add nothing. If it
  carries none, add one at the top naming the source repository, the path,
  `399be77` as the body's commit, `b802837` as the pin, and the body's sha256.
  Say which case each file was. **No other edit**: no reformatting, no
  renaming, no import changes.
- **Recompute each body sha256 yourself**, from `399be77` and again from
  `b802837`, with CRLF normalised to LF and excluding any origin header. The
  two must agree. Architecture relayed the values the `dino-autofocus` side
  reports, below. **Do not trust them: compare, and report any difference as
  a stop.**
  - `src/focus_classical.py`: `a1155a04c9f180ed8d257d081ff03b4e1a205d7d2d886010821e265778e9b127`
  - `src/focus_verdict.py`: `727286e55ac0f4b2b613e0bc0cc8d37b67e1c8bb7a9e8bfb18da6450b69e267c`
  - `src/focus_search.py`: `7ffaf28f014ffdd87587f803f2481e3d9eff47219fde15432d97932483655bc6`
  - `tests/test_focus_core.py`: `401dc7ec20c99e857db5e4a8266f8cbc1c553d6023e9d6cc3e21f912797f4d11`
  - `tests/test_focus_contract.py`: `d863c62cee1f1894ee92a7e395ac53408bd7e0aeae4902a861f48b9b5407c3d4`
  - `tests/test_focus_search.py`: `34ccbf778fd70d3ab5220fc7234d85117d6692a91046585066d2a236554cef72`

  `focus_search.py`'s value equals the store's record at `fa97903`. That file
  was not changed, and that is the check that it was not.
  `focus_classical.py` and `focus_verdict.py` differ from the store's
  `fa97903` records (`2fa776fa…` and `07bc1342…`) because they were changed for
  this copy. That difference is expected; report it, it is not a stop.
- **One line per file in `microscope_agent/rulings.jsonl`**, in the shape the
  file already uses: `ruling` (`transfer` for a file that crosses whole),
  `item` (the path and what it is), `slot`: *the operator's focus search
  (plan.md 11-24)*, `rule`: *10.3*, plus `by`, `at` and `recorded_from`. The
  last names `b802837`, `399be77` and the body sha256.

## What is already ruled at this pin (architecture, 2026-10-04)

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
- **The three new arguments sort as follows:**
  - `ceiling` is **a fact about the camera**: the full-scale count for this
    camera in this readout mode. It needs a `kb:` source, and **today the store
    holds no such entry**. The adapter's self-reported `BitDepth 16` is not one,
    and the store records the camera misreporting its own bit depth. So it is a
    gap, never a default;
  - `bin_px` and `n` are **the plan's choices of method**. They carry no
    source and no grade.

## Stop and report up, and copy nothing, if any of these is true

**The card cannot both forbid edits and let a forbidden thing through.** If a
file can cross only by being edited, it does not cross under this card.

1. **Model code in any of the six.** The model-reading branch is meant to be
   gone. If any function, branch or import in the six still takes a model
   reading, stop.
2. **A figure written into code beyond the four ruled above**: a clip level,
   a grid or bin size, any threshold or default about this instrument or a
   camera. Also a default value left on `ceiling`, `bin_px` or `n`. 10.3 says a
   number crosses only through the librarian, never pasted into code.
3. **A test that needs an import or path change** to run here.
4. **A body sha256 you compute differs** from the relayed value, or between
   `399be77` and `b802837`; or the test count differs between there and here.

In each case, report up which file, which line, and why. The decision on how
it may cross is architecture's and the person's, not this card's.

**The copy creates a need on this side, and it is not yours to meet.** The
plan has to supply `ceiling`, `bin_px` and `n`, and `focus_search` in
`plan.schema.json` has no field for them yet. That is a manager's to add. Wire
no value into code meanwhile, and report each argument's unit as the code
uses it.

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
