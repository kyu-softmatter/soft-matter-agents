# 018 — the Library's Send says what is true now that the inbox is open

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 016
(`dc4a7843a`). If you are not that seat, take nothing from this card and
report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

Card 016 told you Send answers "Not sent: the librarian's inbox is not open
yet." That was true when the card was written, and it stopped being true
the same day, before 016 landed:
- the person opened the console inbox (`4f867773`);
- the three folders are in at `0c3aa990b`;
- plan.md 7.1.1 reads open at `d939df9b`;
- intake has told the person that the inbox is open in the repository and
  that the console's Send does nothing until the console's inbox writer
  lands.

So the Library now tells the person the opposite of what the person was
told. The fault is the card's wording, not your build.

The answers list has a second problem. It shows the same example note as
the pages: "a copy of recorded files kept with the console". The four wiki
pages are copies. The nine example answers are not: `mock_data/SOURCE.md`
says they were written here and that their numbers are made up. A made-up
number shown to the person is labelled as made up, so the answers list
needs its own note.

## What to do

1. **Send's answer, after the form checks**, is exactly: "Not sent: the
   console does not send to the librarian yet." It replaces `NOT_SENT`.
   The message for a form that needs fixing is unchanged.
2. **The note above the forms** reads: "The console does not send to the
   librarian yet, so Send only checks the form. Nothing you type here is
   kept or sent."
3. **The answers list under `--store mock` carries its own note**, exactly:
   "These are example answers written for the console's practice data, not
   answers from any librarian. Their names and numbers are made up."
   - The front page, the pages and the map keep the note they have.
   - Under `--store sma` nothing changes.
4. **The mock's example answers are listed newest first by `answered_at`**,
   with `answer_id` breaking a tie. The file name plays no part in the
   order. The real reader, which the inbox-writer card brings, orders the
   same way, so the mock must not teach the screen a different rule.
5. **Replace every statement that the librarian's inbox is not open**, in
   the Library's own code, comments and docstrings and in
   `console/docs/screens/library.md`. Say what is true instead: the inbox
   is open, and the console writes no item into it until the inbox-writer
   card. Leave the request-card docstrings in
   `server/api/console.py` alone; the inbox-writer card handles them.
6. **Tests, each watched failing first:**
   - Send's answer is item 1's text, and no Library text the person sees
     says the inbox is not open;
   - under the mock, the answers list's note is item 3's text and is not
     the pages' note;
   - two example answers whose file names sort one way and whose
     `answered_at` values sort the other are listed by `answered_at`.

## What not to do

- Send still writes no file, makes no request and adds no route.
- Change no other screen's text.
- Leave the copied wiki pages and the answers' contents unchanged. Only
  their order on the screen changes.
- No write outside `console/`. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest -p no:cacheprovider` passes. Without that flag a
  `.pytest_cache` is left in the shared copy, and the validator counts it as
  four failures.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
