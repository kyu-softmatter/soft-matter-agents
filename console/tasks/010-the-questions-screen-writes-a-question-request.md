# 010 — the questions screen writes a question request

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, from 2026-10-24, after
card 009 landed at `40310aa4`. If you are not that seat, take nothing from
this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

This is card 007's third app card, and the console's first screen. What the
question window writes is defined in plan.md 4.5: a question request, never
an `ask`. Its shape landed at `2f359866` as
`contracts/schemas/question_request.schema.json`, with an example and four
rejected fixtures. Its place is
`console/requests/questions/<id>.json`, in `ALLOWED_PATHS` and plan.md 7
(`2deeadef`). Nothing reads a request until the agents' new inbox, designed
on its own and approved by the person, opens (Q-20261022-office-04,
`5444c688`). So this card writes requests and shows them, and **nothing
reaches an agent**.

The canvas screen is `PQuestions`, version 58.

## What to do

1. **The field.**
   - One text field for the question, and an "Ask" choice: let the agents
     decide, the microscope, the simulation, or the librarian. Send.
   - The old form's purpose and observable fields go. The agents settle
     those.
   - Who may send stays the server's present rule. Hide nothing as a check;
     the server refuses.
2. **Autocomplete offers only strings already on disk.**
   - The `words` of earlier question requests, and the quantity names in
     `contracts/quantities.json`. Each suggestion is labelled "earlier
     question" or "registered name".
   - Never a model's completion, and never the store's contents.
   - Choosing a suggestion inserts its text. It registers nothing.
3. **Send writes one question request**, exactly in the schema's shape:
   - `id` is `qr-<UTC yyyymmdd>-<UTC hhmmss>-<4 random lowercase
     letters or digits>`, and the file is named `<id>.json`.
   - `words` is the text exactly as typed: no trimming beyond what the field
     shows, and no rewriting.
   - `asked_by.login` is the session's login. `asked_by.console_role` is
     the login's console role as of sending.
   - Until the admin card brings console-side roles, derive the role from
     today's role: admin and operator get may_ask, may_draft, all three
     agents and may_ask_model_run; viewer gets none, and cannot send.
   - `asked_at` is UTC. `addressed_to` is the choice.
   - **No other key.** There is no person's-own claim; the schema has none.
   - Written atomically: write a temporary file, then rename. **Never
     rewritten**: an existing id is refused.
   - Where it is written depends on the store:
     - `--store sma`: `<root>/console/requests/questions/`;
     - `--store mock`: the mock data's own `console/requests/questions/`,
       the practice copy.
   - The screen answers "Request written · <time> · as <login>". It says
     plainly that nothing reaches an agent until the agents' new inbox
     opens.
4. **The cards below the field**, one per question.
   - **Requests written in the console.** The words, who asked, when, and
     the state "request written · not picked up yet", because the inbox is
     not open.
   - **The agents' questions already on disk**, as today's screen reads
     them, each with the five-step bar: asked, designed, signed by the
     person's own login only, run, result.
     - asked: a goal card exists;
     - designed: a plan exists;
     - signed: an approval for that plan's hash exists;
     - run: a run log for it exists;
     - result: a result card exists.
   - A card asked through the console says every run from it waits for the
     person's signature.
   - A card opens its detail on a click. The detail itself is card 011, so
     until then the click may lead to today's view of that question.
5. **Tests, each watched failing first:**
   - A written request validates against
     `contracts/schemas/question_request.schema.json`, read from the
     repository, not a copy.
   - The words are byte-equal to what was typed.
   - An existing id is never overwritten.
   - No request carries a key outside the schema.
   - A viewer, and a remote browser, cannot send: the server refuses, in
     words.
   - Autocomplete offers only earlier requests' words and registered names,
     each labelled. An empty disk offers nothing.
   - Under the mock store, nothing is written into the real tree.
   - The five steps read the right files.

## What not to do

- Nothing reaches an agent: no write into any agent's folder, no inbox, no
  bridge.
- No call to the librarian's service, and no store contents shown.
- No retheme yet. Install nothing. Write nothing outside `console/`.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
