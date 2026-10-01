# 052 — `synthesis.py --write` emits a card check 1 rejects

Written by `manager-microscope-kyuhwan-macbook-20260930-2`. You read this; you
do not edit it.

**Assigned to `microscope-kyuhwan-macbook-20260930-2`**, the same seat as card
051. If you are not that seat, take nothing from this card and report up.

## What was found

You reported this while working card 051, on 2026-09-30: `src/synthesis.py
--write` writes a card that the validator's schema check rejects. `from_axes`
and `axis` are required and missing, and `origin` is not an allowed field. It
also writes an operating point with 17 significant digits. You deleted your
copy without committing it, which was right.

This blocks 051. The plan for `mic-20260930-001` is emitted through this step
once the person has made the decisions it is waiting on, so fix it before
then. 051's design does not wait for this fix: carry on with it.

## What to do

1. Reproduce it on `mic-20260930-001`'s axis cards, or on a copy under a
   scratch directory. Record which schema and which fields failed.
2. Fix the writer so that its output passes the validator. **The schema is
   right and the writer is wrong**: change `synthesis.py`, not anything in
   `contracts/`. If you conclude the schema is what's wrong, stop and report
   to this seat with the reason. Do not route around it.
3. **Precision.** An operating point carries no more digits than its worst
   input supports. In explore mode that is a decade, so a 17-digit number
   claims precision nothing behind it has. Round where the value is written
   out, not inside the computation.
4. **Watch it fail first.** Add a test under `tests/` that runs the writer
   and validates its output. Run it against the old code and see it fail,
   then against the fix and see it pass. Say in the commit message that you
   saw both.
5. Check whether any committed card was written by `--write` with these
   fields. If one was, list it. Do not rewrite it.

## Boundaries

`microscope_agent/` only: `src/synthesis.py` and `tests/`. Open no device.
Commit with `git commit -F <file> -- <paths>`, after `git diff HEAD --
<paths>`. Name new files individually. Use committer name
`seat:microscope-kyuhwan-macbook-20260930-2` and the email from
`contracts/seats.json`. Run the validator and read its tree line.

## What comes back

To this seat, at most 5 lines: the cause, the commit, the test that failed and
then passed, and any committed card that is affected.

**Re-read this card immediately before committing.**
