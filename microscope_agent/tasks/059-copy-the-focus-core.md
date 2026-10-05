# 059 — copy dino-autofocus's focus core into the operator's focus search

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261003-1`.** If you are not that seat, take
nothing from this card and report up. It re-issues card 026's first stage:
the classical metrics and the verdict that read a sweep. The rest of 026 waits
on card 055 and the bench.

## Three gates before you start

1. **Card 055 has landed on mock.** The focus search's place exists only once
   it does (plan.md 11-24, 3ba8733), and 10.2 says no code crosses before its
   place exists.
2. **A new pin exists.** `81a895b` was the first pin, and **it is
   superseded before use** (architecture, 2026-10-04). The `dino-autofocus`
   side is changing the source so that it can cross without edits:
   - the camera clip levels, the bin size and the block grid in
     `focus_classical` become **required arguments with no module defaults**,
     which the plan supplies;
   - **the model-reading branch leaves `focus_verdict`**.

   A new commit is pinned after that. **Architecture names it**; this card
   does not guess it.
   Until architecture has named the new commit to this seat, do nothing here.
3. **The new pin is reachable on the remote.** Pushing it is the person's
   decision. Until `git ls-remote` on
   `https://github.com/kyu-softmatter/dino-autofocus` shows that commit, do
   nothing here. Do not copy from a local checkout and cite the commit as if
   it were public.

## What crosses: six files, no more

| from `dino-autofocus` at the new pin | to |
|---|---|
| `microscope_agent/src/focus_classical.py` | `microscope_agent/src/focus_classical.py` |
| `microscope_agent/src/focus_verdict.py` | `microscope_agent/src/focus_verdict.py` |
| `microscope_agent/src/focus_search.py` | `microscope_agent/src/focus_search.py` |
| `microscope_agent/tests/test_focus_core.py` | `microscope_agent/tests/test_focus_core.py` |
| `microscope_agent/tests/test_focus_contract.py` | `microscope_agent/tests/test_focus_contract.py` |
| `microscope_agent/tests/test_focus_search.py` | `microscope_agent/tests/test_focus_search.py` |

They run alone. `focus_verdict` loads `focus_classical` as a sibling and
nothing else, using numpy and the standard library only. There were 18 tests
at `81a895b`; architecture names the count at the new pin. **Run them here
and see that many pass**; a different count is a stop.

**Explicitly out:**

- `focus_run_log` and its test: the run-log shape is this repository's
  (card 057), and the librarian discarded it;
- `focus_step_rules`: guard logic, which `_operation_gate` and card 055
  own. Two implementations of one safety comparison is what 10.2.1 exists to
  stop;
- every `map_*` file and **all model code**.

## How it crosses

- **Byte for byte, except one origin header** added at the top of each file,
  naming the source repository, the path, the new pin's commit, and the body's
  sha256 (the file at the commit, CRLF normalised to LF, before the header).
  **No other edit**: no reformatting, no renaming, no import changes.
- **Recompute each body sha256 from the new pin** and cite what you compute.
  The store's records at `fa97903` give the values below, and they are what
  the librarian ruled.
  - `focus_classical.py`: `2fa776faeb2b366f5dd1892345715d087e63a702cc168e179e81cb0bfd3f2af3`
  - `focus_verdict.py`: `07bc1342a4c868e5856b549bc8bc6a8c3a5af8fd8bd6dd83cc6c6970d01be099`
  - `focus_search.py`: `7ffaf28f014ffdd87587f803f2481e3d9eff47219fde15432d97932483655bc6`

  **`focus_classical` and `focus_verdict` will differ at the new pin, and
  that is expected**: their sources are being changed for this copy. Report
  both hashes, old and new; that difference is not a stop. `focus_search` is
  not being changed, so a difference there is a stop. So is a test count other
  than the one architecture names with the new pin.
- **One line per file in `microscope_agent/rulings.jsonl`**, in the shape the
  file already uses: `ruling` (`transfer` for a file that crosses whole),
  `item` (the path and what it is), `slot`: *the operator's focus search
  (plan.md 11-24)*, `rule`: *10.3*, plus `by`, `at` and `recorded_from`, which
  names the new pin and the body sha256.

## Stop and report up, and copy nothing, if any of these is true

**The card cannot both forbid edits and let a forbidden thing through.** If a
file can cross only by being edited, it does not cross under this card.

1. **Model code in any of the six.** The store's record of
   `focus_verdict.py` discarded *a verdict from one signed model reading*. If
   that is a function in the file and not just prose, the file carries model
   code. Copying it whole brings it in, and cutting it out is an edit.
2. **A figure written into code that 10.3 does not let cross that way.** The
   store's record of `focus_classical.py` discarded *the camera clip levels,
   the bin size and the block grid written as constants in the file*. 10.3
   says a number crosses only through the librarian, never pasted into code.
   For each numeric constant in each file, say which it is:
   - **a definition**: part of the algorithm, like a kernel, or the sum over
     both axes;
   - **a figure about this instrument or a camera**: clip level, grid size,
     bin size, any threshold.

   One figure in a file stops that file.
3. **A test that needs an import or path change** to run here.
4. `focus_search`'s body sha256 differs from the store's, or the test count
   differs from the one architecture names with the new pin.

These stay in force at the new pin. The source change is meant to clear 1
and 2. If it does not, for instance if a default value is left behind or the
model branch still lives in the file, stop.

**What clears 2 here creates a need on this side.** The plan has to supply
the clip levels, the bin size and the block grid, and `focus_search` in
`plan.schema.json` has no field for them yet. Adding one is a manager's.
Report the new arguments' names and units, and do not wire a value into code
meanwhile. **Sort each argument into one of two kinds**, because the schema
treats them differently:
- **the plan's choice of method**, like the block grid and the bin size. It
  carries no source and no grade, as a target or a tolerance does not;
- **a fact about the camera**, like the clip levels. It needs a `kb:` source
  from the store, and a missing entry is a gap, never a default.

If an argument does not plainly fall in one kind, say so and do not decide
it.

In each case, report up which file, which line, and why. The decision on how
it may cross is architecture's and the person's, not this card's.

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

To this seat, 8 lines at most: the commit; the six body sha256 values and
how each compares with the store's; the tests passing here, with their count; your call on every
numeric constant, by file; and any stop, with its file and line.
