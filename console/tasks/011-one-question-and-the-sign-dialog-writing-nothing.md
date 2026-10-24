# 011 — one question, and the sign dialog, writing nothing yet

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, from 2026-10-24, after
card 010 landed at `9e151912`. If you are not that seat, take nothing from
this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

This is card 007's fourth app card. A question's detail opens from its card,
and a plan waiting for the person is signed there (Q-20261022-office-02 and
-09; plan.md 6.1, 15.1). **The part that writes an approval into
`microscope_runtime/approvals/` is part of the person's guard**, and is built
only on the person's word. That word was asked on 2026-10-24 as
Q-20261024-office-01 and has not been answered. So this card builds the
screen and the dialog, and **writes nothing**. The writer is a card of its
own, after the answer.

The canvas screens are `PQuestionDetail` and `PSign`, version 58.

## What to do

1. **The detail screen**, opened from a question's card:
   - The question verbatim, who asked, when, and the five-step progress
     from card 010.
   - **A summary put together from card fields**: the goal's purpose and
     observable, and the plan's steps. It is labelled as put together from
     the cards. Anything the assistant wrote is labelled as the assistant's.
   - **Every card made from the question, one row each**, opening on a
     click to its main fields: goal, design (axes), synthesis, each plan and
     revision, approvals, runs, results, and the bridge's rounds for the
     question's thread.
   - Each number shown keeps its word: measured, computed, guessed, read
     back, or sent.
   - **A plan waiting for a signature** shows a box with "Review and sign".
2. **Who sees the Sign button.**
   - Only the login named as the person's own in the console's settings
     file outside the tree, under a new key `person_login`.
   - Absent `person_login`, no login sees it, and the box says the
     person's login is not named yet.
   - Any other login sees "Waits for the person's signature" and no button.
   - This decides only the screen. The runtime decides from the person's
     own file, never from the console's settings (plan.md 6.1).
3. **The sign dialog**, as `PSign` draws it:
   - The plan, its revision, its steps, its light, and what cannot be
     undone.
   - **The full fingerprint**: the sha256 of the plan card with `status`
     removed, the same rule as `contracts/validate.py`'s `card_sha` and
     plan_approval's `plan_hash`.
   - A password field, typed again and never pre-filled.
   - **Sign checks the password at the server and writes nothing.** It
     answers in plain words: "Signing is not built yet: the part that
     writes your approval waits for your OK."
   - With the mock store, a practice login is shown as signed and writes
     nothing.
   - If `microscope_runtime/approvals/` is absent in the tree the console
     reads, the dialog says nothing can be signed, and offers no other
     place.
   - No password, and no hash of one, in any response, log or audit line.
     The password check uses the existing throttle.
4. **Tests, each watched failing first:**
   - the fingerprint equals `card_sha`'s for
     `contracts/examples/plan_microscope_mic-20260917-001.json`, and equals
     the `plan_hash` in `contracts/examples/plan_approval.json`;
   - the Sign button shows for `person_login` only, and for no one when it
     is absent;
   - Sign writes no file anywhere, under either store;
   - a wrong password is refused and throttled;
   - the missing-folder state;
   - the summary carries its label;
   - every row opens.

## What not to do

- **No write into `approvals/`, or anywhere outside `console/`.** No stand-in
  writer, no fake approval in the real tree.
- No retheme yet. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
