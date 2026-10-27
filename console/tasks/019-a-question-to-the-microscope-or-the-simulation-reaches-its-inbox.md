# 019 — a question to the microscope or the simulation reaches its inbox

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 018
(`341438fbb`). If you are not that seat, take nothing from this card and
report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The person opened the console inbox (`4f867773`). The three folders are in
at `0c3aa990b`, and plan.md 7.1.1 reads open. Both runners refuse, by code,
an unapproved run from another login's question, which was the condition
for opening.

The Ask form still writes every question into the console's own
`console/requests/questions/`, so nothing reaches an agent. This card
delivers a question addressed to the microscope or the simulation into that
agent's `console_inbox/`.

Writing there is the console's second write outside `console/`, beside the
signed approval. plan.md 7.1.1 rule 2 grants it: the console's server writes
the inbox and nothing else of the agent's.

The librarian's inbox is the next card. It brings the Library's four
requests, the question addressed to the librarian, attachments, and the
librarian's answers. This card leaves the librarian as it is.

## What to do

1. **Which choice delivers.**
   - "The microscope" and "The simulation" write an item into that agent's
     inbox. No request file is written beside it.
   - "The librarian" and "Let the agents decide" write a request into the
     console's own folder, as today. Each is marked "written in the console ·
     not delivered", which replaces "request written · not picked up yet".
   - Whether "Let the agents decide" stays is with the person (asked through
     intake on 2026-10-26). Leave the choice where it is until the person's
     answer comes as a card.

2. **The item** is `contracts/schemas/console_inbox_item.schema.json`'s
   `console_question`, exactly, with no other key:
   - `item_id` is `ci-<UTC yyyymmdd>-<UTC hhmmss>-<four lowercase letters or
     digits>`, and the file is `<item_id>.json`.
   - `question_id` is `mic-` or `sim-`, then the UTC date of `asked_at`, then
     `-c` and three digits. The number is the next after the highest that
     date already carries among that agent's inbox items, starting at `c001`.
     The two agents count apart.
   - After `c999`, nothing is written and the asker is told: "This agent has
     had 999 questions from the console today, which is the most a day can
     hold. Ask again after midnight UTC."
   - `words` exactly as typed: not trimmed and not rewritten.
   - `asked_by` is the login and `console_role_for(role)`.
   - `asked_at` is UTC. `asker_mark` is `{"kind": "other_login"}`, since the
     proof that an asker is the person's own is not built. `attachments` is
     `[]`.
   - **Check the item against the tree's own schema before writing it**,
     with `schema_lite` and the schemas found the way `instruments.py`
     finds them. An item that fails is refused, and nothing is written.

3. **How it is written.**
   - The folder `<tree>/<agent>_agent/console_inbox/` must already exist. If
     it does not, nothing is written, the console never creates it, and the
     asker is told: "This agent's inbox is not there, so nothing was sent."
   - Write the whole file under a temporary name in the console's own
     folder, `console/requests/outgoing/`, which is in the same tree, so the
     link works. Open that file exclusively.
   - Then link it to its final name in the inbox, and remove the temporary
     file. A link to a name that exists fails. In that case mint another
     `item_id`, up to five tries, as `write_question_request` does today.
   - Write nothing into an inbox under a temporary name. The checker fails
     any file in an inbox that is not an item, an attachment or `.gitkeep`.
   - An item is never rewritten, renamed or removed afterwards. A correction
     is a new item.
   - Write UTF-8 with no BOM and LF line endings, and end the file with one
     newline.
   - Scan the inbox, mint the `question_id` and link the file under one lock
     in the server process. One console server runs against a tree; say so in
     the module's docstring.
   - Under `--store mock`, write into the mock's `write_dir` as
     `<agent>_agent/console_inbox/`. The mock may create that folder there,
     because it is the mock's own. The shipped sample is never written.

4. **The audit entry** records the agent, the `item_id` and the
   `question_id`, and never the words.

5. **The route and the answer after Send.**
   - `POST /question-requests` returns what was written, told apart by
     `artifact`: `console_question` when delivered, `question_request` when
     not.
   - When delivered, the form says: "Sent to the microscope as question
     mic-20261026-c001." (or the simulation, with its id).
   - For the librarian: "Not delivered: the console does not send to the
     librarian yet."
   - For "Let the agents decide": "Not delivered: no agent takes a question
     left to the agents yet."

6. **The cards below the question field** show every item in the two
   inboxes beside the requests in the console's folder.
   - Newest first by `asked_at`, with `item_id` breaking a tie. The file
     name plays no part in the order.
   - Each item's card shows the words, the login, the time, the agent and
     the `question_id`.
   - Its answers are the `console_answer` files in that agent's `answers/`
     that name its `item_id`. The latest is the newest by `answered_at`, with
     `answer_id` breaking a tie. The state shown is exactly one of:
     - no answer: "delivered · not answered yet";
     - latest `taken_up`: "taken up as mic-20261026-c001". The agents'
       question with that id keeps its own card with its five steps, as today;
     - latest `refused`: "refused · " followed by the `reason` exactly;
     - an answer naming the item that cannot be read, fails its schema, or
       names another `question_id`: "an answer is on disk and cannot be
       read". The card does not guess past it.
   - `runs_wait_for_signature` stays true for every item: each is another
     login's, and its runs wait for the person's signature.
   - Requests in the console's folder keep their cards, marked as in item 1.

7. **Replace every statement that the inbox is not open or that nothing
   reaches an agent**, and say what is true instead. Where the request
   cards are concerned, that includes:
   - `RequestCardOut`'s docstring and the `question_cards` and
     `write_question_request` docstrings in `server/api/console.py`;
   - the module docstring of `agents/requests.py`;
   - `web/src/features/questions/cards.tsx`;
   - `console/docs/screens/console.md` (its "Nothing reaches an agent" bullets);
   - the generated `web/src/api/schema.ts`, regenerated and not hand-edited.

   The Library's wording stays as card 018 left it.

8. **Tests, each watched failing first**, all in `tmp_path` trees:
   - an item for each agent passes `console_inbox_item.schema.json`, checked
     by `schema_lite` and, in the test, by `jsonschema` against the
     repository's file;
   - numbering: `c001`, then `c002`; the two agents count apart; a new UTC
     date starts again at `c001`; the 1000th of a day is refused and writes
     nothing;
   - an absent inbox folder is refused and is not created;
   - a taken `item_id` is never rewritten: the first file is byte-identical
     afterwards, and the second write lands under a new id;
   - after a write, and after a write made to fail between the temporary
     file and the link, the inbox holds only items and `.gitkeep`, and
     `console/requests/outgoing/` holds nothing;
   - the librarian and "Let the agents decide" write nothing into any inbox;
   - a viewer login is refused and nothing is written;
   - under the mock, only `write_dir` changes, and the shipped sample's files
     hash the same before and after;
   - the audit entry carries the ids and not the words;
   - the cards: each of the four states; two answers whose file names sort
     one way and whose `answered_at` values sort the other; an unreadable
     answer.

## What not to do

- Write nothing into an agent's tree except `console_inbox/<item_id>.json`:
  never `answers/`, `questions/`, `runs/` or another agent's folder. The
  answer is the agent's to write.
- No attachment on a question, and no change to the Library.
- **The server runs no git, and you commit no item.**
  - plan.md 7.1.1 rule 10 (`25ba90c2`) settles the order: the console side
    commits an item alone and promptly, and the agent commits its answer
    after.
  - The checker's half of that rule is in at `f3ca6dce`: an item with no
    answer yet is pending, not a failure.
  - Which console seat commits items, and when, is a later card.
  - Your commit carries `console/` only.
- No test writes into a real tree. Pointing the server at the microscope
  computer's own working copy stays the person's act.
- Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest -p no:cacheprovider` passes.
- After the tests, `git status` shows no new file under any `console_inbox/`
  and nothing under `console/requests/`.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
