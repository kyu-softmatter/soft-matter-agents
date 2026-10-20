# 083 — remove the six real-policy skips now the person's files have moved

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-office-20261017-1`, the runtime seat.** It is
small and touches only `microscope_runtime/tests/test_operation_plan.py`, so
it may be done between two commits of card 076, as its own commit, as long
as 076 has no uncommitted edit in that file. If you are not that seat, take
nothing from this card and report up.

## Why

Card 080 (`a36e49d0`) skipped six tests in `test_operation_plan.py`. They
read the person's real policy, which had not yet moved, and the skip was
conditioned on `microscope_runtime/envelope/safety.json` being absent. It was
temporary by ruling: left in place, a skip on absence would also hide a
policy that later goes missing.

The person has now moved the files, plan.md 15 step 6, at `135e62ea`, merged
here at `e3b61de9`. This seat checked that commit: all eight files are
100% renames, `safety.json`'s blob is identical before and after, the
snapshot stayed in `microscope_agent/envelope/`, and the validator ends 0
failed.

## What to do

1. **Remove the skip** and its condition from the six tests (the Exemption,
   ReadBack and Derivation cases card 080 named). Change nothing else in
   them.
2. **Run them against the real policy** at its new path. They must pass. A
   failure now is a finding about the policy or the code: report it with the
   test and the line, and do not re-add a skip.
3. **Absence is a failure again.** Show it on a scratch copy of the tree:
   with `microscope_runtime/envelope/safety.json` absent, the six fail. Do
   not delete the real file.
4. Re-run the runtime suite: 206 ran, now with 0 skipped among these six.

## Boundaries

- Write `microscope_runtime/tests/test_operation_plan.py` only.
- **Never `envelope/safety.json` or `approvals/`.** Read them, never write.
- Commit and push through `contracts/tools/seat_commit.py`. Never
  `--no-verify`, `--amend` or force.

## What comes back

To this seat, 3 lines: the commit, the six tests' results against the real
policy, and the scratch check that absence now fails them.
