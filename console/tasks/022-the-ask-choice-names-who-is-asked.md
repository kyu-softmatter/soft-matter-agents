# 022 — the Ask choice names who is asked, and "Let the agents decide" is gone

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 020. If
you are not that seat, take nothing from this card and report up.

Build to the HEAD you start from. It must hold card 020 and the person's
decision (`c5cea87e`).

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The person decided on 2026-10-27 that "Let the agents decide" is removed
from the Ask form (`docs/ideas/20261027.md`, D-20261027-office-04,
`c5cea87e`; in English, "remove it"). Card 019 left the choice in place
until this answer came as a card, and card 020 did the same. This is that
card.

After card 020, the microscope, the simulation and the librarian each
receive what is sent to them. "Let the agents decide" is the one choice
left that delivers nothing: the question is written into the console's own
folder, and no agent reads that folder. The person chose to remove it
rather than keep it as "not delivered" until an agent is given the job of
routing such questions. No such agent is planned, and none is to be built.

This card revises card 006's "Ask" line and item 1 of card 010. The choice
is no longer optional, and it has three entries.

## What to do

1. **The Ask choice.**
   - The choices are "The microscope", "The simulation" and "The
     librarian", in that order, and nothing else.
   - The form opens with none picked. The select shows "Choose who to ask"
     in place of a choice, and that placeholder cannot be sent.
   - Send stays disabled until a choice is picked and the words are not
     blank. Picking a choice sends nothing.
   - After a Send, the choice goes back to none, the same as the words, so
     that each question is addressed on purpose.

2. **The server takes three addressees.**
   - `addressed_to` is required and must be `microscope`, `simulation` or
     `librarian`.
   - `agents_decide`, a missing `addressed_to` and any other value are
     refused with 422. Nothing is written anywhere, and no audit line is
     added.
   - The route's 422 description says "an addressee that is not one of
     three".

3. **Nothing writes a question request any more.**
   - Every Send either delivers, as cards 019 and 020 say, or is refused.
   - Remove the route's branch that writes a `question_request` into the
     console's folder, and any code whose only use was that write. The
     route keeps its path, `/question-requests`. It now returns only the
     delivered item.
   - The form's "Not delivered: ..." answers after Send go, along with the
     audit line's "request id" case.
   - Keep everything that reads requests already in the console's folder.

4. **Earlier requests are still read.**
   - A request in the console's folder addressed to `agents_decide` keeps
     its card, in the state "written in the console · not delivered". This
     covers the mock's sample `qr-20261024-174512-k3p9` and any request on
     a real tree.
   - Its addressee is shown as "Left to the agents · no longer offered",
     never as the raw value.
   - The reader's model accepts every addressee that
     `contracts/schemas/question_request.schema.json` allows, so an earlier
     request never becomes a server error. Card 021 had the same kind of
     defect: a field narrower than what was on disk answered 500.
   - "Earlier questions" in the autocomplete still offers their words.
   - The request schema stays as it is. It records what the console wrote,
     and requests already written stay valid against it.

5. **Replace every statement that there are four choices, or that "Let the
   agents decide" exists**, and say what is true instead:
   - `console/docs/screens/console.md`, the question window section;
   - the module docstring of `web/src/features/questions/ask.tsx`, and
     `ADDRESSEES` and `afterSend` in `web/src/features/questions/api.ts`;
   - the docstrings of `write_question_request` and `RequestCardOut` in
     `server/api/console.py`, and the module docstring of
     `agents/requests.py`;
   - the module docstrings of the server tests that name the choice;
   - the mock's `SOURCE.md`, where it describes the sample request;
   - the generated `web/src/api/schema.ts`, regenerated and not hand-edited.

6. **Tests, each watched failing first**, all in `tmp_path` trees:
   - `agents_decide` is refused with 422. Afterwards no inbox and no part of
     the console's folder holds a new file, and the audit has no new line.
     A request with no `addressed_to` is refused the same way;
   - an earlier request on disk addressed to `agents_decide`: the question
     cards answer 200, its card carries the not-delivered state, and the
     autocomplete still offers its words;
   - some tests used `agents_decide` only as a convenient addressee: a
     viewer, a remote view, no login, a locked store, blank or too-long
     words, an unknown key, a lone surrogate. Each keeps its assertion and
     uses an addressee that delivers, in a tree where that inbox exists.
     None is dropped because it used the choice. A test whose point was the
     write into the console's folder goes with that write. Name each test
     you remove in your report;
   - the web:
     - the select opens with none picked, and Send is disabled even with
       words typed;
     - picking a choice enables Send;
     - after Send, both the words and the choice are empty;
     - the select offers exactly the three choices, in order;
     - an earlier request left to the agents shows its addressee in words.

## What not to do

- Do not change `contracts/schemas/question_request.schema.json`, its
  example or its rejected fixtures. They are not this seat's, and earlier
  requests stay valid against them.
- Do not rewrite, move or remove a request already on disk, including the
  mock's shipped sample.
- Add no "choose for me", no routing of questions, and no default
  addressee.
- Make no change to the Library and none to how an item is written.
- **The server runs no git, and you commit no item.** Your commit carries
  `console/` only.
- No test writes into a real tree. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest -p no:cacheprovider` passes.
- After the tests, `git status` shows no new file under any `console_inbox/`
  and nothing under `console/requests/`.
- `git grep -n agents_decide -- console/` finds the value only where an
  earlier request is read, or where its refusal is tested: the reader's
  model and the schema generated from it, the label of item 4, the mock's
  sample, and the tests of items 2 and 4. Nothing that writes or offers it
  remains.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
