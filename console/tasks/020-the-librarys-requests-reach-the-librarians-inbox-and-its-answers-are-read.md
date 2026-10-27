# 020 — the Library's requests reach the librarian's inbox, and its answers are read

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 021. If
you are not that seat, take nothing from this card and report up.

Build to the HEAD you start from. It must hold card 019 (`ca09d290`) and
the store-answer check (`a7ad1b7c`).

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

Card 019 delivers a question to the microscope or the simulation. The
librarian's inbox, `librarian_agent/console_inbox/`, has been open since the
same day, and `librarian_agent/CLAUDE.md` names it, so the librarian reads it
and answers in `librarian_agent/answers/`. The console still writes nothing
there:
- the Library's four forms build a request, check it, and say "Not sent";
- a question addressed to the librarian on the Questions screen is written
  into the console's own folder and marked not delivered;
- the Library's answers are examples under the mock and none from a real tree.

This card delivers all of them, with the one attached file a request may
carry, and reads the librarian's answers.

Writing there is the console's second write outside `console/`, the one
plan.md 7.1.1 rule 2 grants: the console's server writes an agent's inbox
and nothing else of the agent's. An attachment is part of the item it sits
beside (rule 4), so it is written into the same folder.

## What to do

1. **What delivers.**
   - The Library's Send, for each of the four forms, writes a
     `console_store_request` into `librarian_agent/console_inbox/`.
   - On the Questions screen, "The librarian" writes a `console_store_request`
     of kind `ask` into the same inbox. Its `question` is the words, and it
     carries no `conditions`.
   - "Let the agents decide" stays as card 019 left it: written into the
     console's own folder, not delivered. The person's answer on that choice
     will come as a card.
   - The Library's route returns what was written: the item, with its
     `item_id` and the attachment's name. The form then says "Sent to the
     librarian." and the request appears in item 6's list.
   - A viewer login is refused and nothing is written, as in card 019.

2. **The item** is `contracts/schemas/console_store_request.schema.json`,
   exactly, with no other key.
   - The envelope is card 019's: the same `item_id` form and file name, the
     same `asked_by`, `asked_at` and `asker_mark`. A store request has no
     `question_id`.
   - **`words` is the text of one field, exactly as typed**, not trimmed and
     not rewritten. The field is fixed by kind:

     | kind | `words` is the text of | and the request field holding it |
     |---|---|---|
     | `enter_document` | the fact wanted | `fact_wanted` |
     | `withdraw_value` | the reason | `reason` |
     | `offer_result` | the fact in words | `fact_in_words` |
     | `ask` | the question | `question` |

   - The web sends that field's text once, as `words`, and leaves the field
     out of the request it sends. The server sets the field to
     `words.strip()`. A request that arrives already carrying the field is
     refused, so the two copies can never disagree.
   - Every other field is as the form builds it today. `requests.check_asker`
     applies to `words` as it does to a question.
   - **Check the item against the tree's own schema before writing it**,
     with `schema_lite`, as card 019 does. An item that fails is refused and
     nothing is written.
   - The console checks the shapes of `entry_id` and `result_card` and
     nothing more. Whether that entry or that result card exists is the
     librarian's to say (`no_entry_of_that_name`, `kept`).

3. **The attached file.**
   - A request carries at most one file. It is named by `document` in
     `enter_document`, or in a withdrawal's `evidence`. That is the only place
     a file is named, and the request must name exactly the file it sends.
   - **The file travels inside the JSON body, base64-encoded**, as
     `{name, content_base64}`. The console's environment has no multipart
     parser, and nothing is installed for this.
   - The web cleans the picked name as `attachedName` does today, without
     the item id, and sends that plain name both as the file's `name` and in
     `document`. The server checks it against the tail of the schema's
     `file_name` pattern, `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. After minting
     the `item_id`, it writes `document` as `<item_id>--<name>`. A retry under
     a new id rewrites it.
   - `attachments` lists that one file as `{file, sha256}`, where `sha256`
     is of the bytes written. With no file, `attachments` is `[]`.
   - **A file over 20 MB is refused** before anything is written: "This file
     is larger than 20 MB, which the inbox does not take. Send a smaller copy,
     or the pages that hold the value."
   - **A file whose bytes parse as JSON and hold any object is refused.**
     Parse the bytes as the validator does, with `json.loads` on the bytes
     themselves. The asker is told:
     "This file reads as data with named fields, which the inbox cannot carry,
     because the store's checks would read it as a card. Attach it as CSV,
     text or PDF instead." The validator reads inside every attachment that
     parses as JSON and fails a forbidden key at any depth. Refusing every
     object means the console never has to copy that key list. A file that
     parses as a bare number or string holds no key and is taken.
   - An empty file is refused: "This file is empty."

4. **How it is written.** Card 019's rules hold, with these additions:
   - The attachment is written first. Write it under a temporary name in
     `console/requests/outgoing/`, open that file exclusively, and link it to
     `<item_id>--<name>` in the inbox. The item is linked last.
   - The attachment's link failing because the name exists means the
     `item_id` is taken. So does the item's link failing. In either case,
     mint another `item_id`, up to five tries.
   - If the item's link fails after the attachment's link succeeded, remove
     the attachment this call linked, and only that one. The checker fails
     a file in the inbox that is not an item, an item's attachment, or
     `.gitkeep`, so an attachment whose item never landed must not stay. It
     is the only removal the console makes in an inbox. A landed item and
     its attachment are never removed.
   - The temporary files in `outgoing/` are removed whatever happens.
   - Use the same lock as card 019, held from the first link to the last.
   - The folder must already exist, as in card 019. If it does not, nothing
     is written and the asker is told: "The librarian's inbox is not there,
     so nothing was sent."
   - Under `--store mock`, write into `write_dir` as
     `librarian_agent/console_inbox/`. The shipped sample is never written.

5. **The answers.** Replace `SmaFilesStore.library_answers()`'s empty list
   with a reader of `librarian_agent/answers/`.
   - Take an answer by exact name: `ca-<yyyymmdd>-<hhmmss>-<four>.json`, whose
     stem is its `answer_id`.
   - **An answer is readable only when all of these hold:**
     - it passes `store_answer.schema.json`, checked with `schema_lite`;
     - its item, `librarian_agent/console_inbox/<item_id>.json`, is there and
       is a `console_store_request` carrying that `item_id`;
     - its `request_sha256` equals the sha256 of that item file's bytes as
       they are on disk;
     - when it carries `follows`, the answer it names is there and answers
       the same `item_id`.

     Check 95 branch e (`19d1a07e`) compares `request_sha256` with the
     item's bytes at commit. The console compares again when it reads,
     because the working copy it reads can hold an answer no commit has
     judged yet.
   - An answer failing any of these is shown as "an answer is on disk and
     cannot be read", with the reason in words. Examples: "it names a request
     that is not in the inbox", "it does not match the request it names", or
     "it follows an answer that is not there". The console does not guess
     past it.
   - Read bytes, as item 8 below says, so an answer that is not UTF-8 is
     unreadable and not skipped.
   - An absent `answers/` folder means no answers. It is not an error: the
     folder does not exist in the tree today.
   - The mock store reads its sample's answers with this same reader, so a
     sample answer that would be unreadable from a real tree is unreadable
     there too. The example answers stay examples and say so.

6. **The Library shows the requests.**
   - A list of every `console_store_request` in the librarian's inbox, read
     by exact item name, so an attachment is never read as an item.
   - Newest first by `asked_at`, with `item_id` breaking a tie.
   - Each request shows its kind in words, the words, the login and the time.
     Show the attached file's name as text, never as a link. The file is not
     opened or served.
   - Its answers are listed under it, newest first by `answered_at` with
     `answer_id` breaking a tie, each shown as the Answers section shows one
     today.
   - **The state is the latest answer's outcome**, using `OUTCOME_WORDS`,
     with these exceptions:
     - no answer: "delivered · not answered yet";
     - latest `waiting_for_a_name`: "waiting for a name", with
       `quantity_name`. An answer carrying `follows` that names it continues
       the chain, and both are shown, the later one first;
     - any unreadable answer naming the request: "an answer is on disk and
       cannot be read", whatever else is there.
   - An answer that names no request the console can find is listed after
     the requests, under "Answers that name no request in the inbox", as
     unreadable.
   - Under the mock store, the sample gains the nine example items that its
     nine example answers name. They have one item per answer, of the kind
     that answer's outcome fits. Set each answer's `request_sha256` to the
     sha256 of its item's bytes, so the mock passes item 5's test.
   - Add one example answer that `follows` the `waiting_for_a_name` example
     and enters it, so the chain is shown. Everything in the sample stays
     labelled example.

7. **The Questions screen.**
   - A question sent to the librarian is delivered (item 1). The form says:
     "Sent to the librarian."
   - Its card shows below the question field with the other delivered items,
     in card 019's order, with the state of item 6 and the latest answer as
     the Library shows it.
   - `runs_wait_for_signature` does not apply: an `ask` runs nothing.
   - **"Earlier questions" offers the words of delivered items too**: card
     019's questions to the microscope and the simulation, and the questions
     sent to the librarian. Today it reads only the console's own folder.

8. **Card 019's readers, fixed.**
   - `inbox_items._read_answers` reads a file's bytes and decodes them as
     UTF-8, allowing a BOM. A file that does not decode or parse counts
     against the item when the item's id occurs in its bytes, and makes that
     item's state "an answer is on disk and cannot be read". Today such a
     file is skipped.
   - `inbox_items._highest_number`: an inbox file named like an item that
     cannot be opened, decoded or parsed, or whose `question_id` cannot be
     read, refuses delivery to that agent. The asker is told: "An item in
     this agent's inbox cannot be read, so the next question number cannot
     be told. Nothing was sent." Today it is skipped, and the number it holds
     could be given twice.

9. **The audit entry** records the `item_id`, the kind and whether a file
   was attached. It never records the words, and never the file's name,
   which is the asker's text too.

10. **Replace every statement that the console does not send to the
    librarian**, and say what is true instead:
    - `NOT_SENT` and the forms' note in `web/src/features/library/`;
    - the module docstring of `request.ts`, and `ask.test.tsx`'s expectation;
    - `console/docs/screens/library.md` and `console/docs/screens/console.md`;
    - every docstring in `server/api/` and `agents/` that says so;
    - the generated `web/src/api/schema.ts`, regenerated and not hand-edited.

11. **Card 016's test of what the console reads** gains
    `librarian_agent/console_inbox/` and `librarian_agent/answers/`, and
    nothing else.

12. **Tests, each watched failing first**, all in `tmp_path` trees:
    - an item of each of the four kinds passes
      `console_store_request.schema.json`, checked by `schema_lite` and, in
      the test, by `jsonschema` against the repository's file. Run the
      `jsonschema` half with `uv run --with jsonschema` and say in your
      report that you did, since the console's environment skips it;
    - `words` is verbatim and the mapped field is `words.strip()`, for each
      kind. A request already carrying the mapped field is refused and
      writes nothing;
    - one file: its bytes and sha256 match the item's `attachments`, its name
      is `<item_id>--<name>` and equals `document`. A request naming a file
      it does not send, or sending a file it does not name, is refused;
    - the 20 MB, JSON-object and empty-file refusals each write nothing;
    - a taken `item_id`, with a file: the first item and its attachment are
      byte-identical afterwards, and the request lands under a new id;
    - a write made to fail between the attachment's link and the item's: the
      inbox holds only what it held before, plus `.gitkeep`, and `outgoing/`
      holds nothing;
    - after every write, the inbox holds only items, their listed
      attachments and `.gitkeep`;
    - "The librarian" on the Questions screen delivers an `ask`; "Let the
      agents decide" writes nothing into any inbox;
    - a viewer login is refused and nothing is written;
    - the answers: one readable answer of each outcome; an answer whose
      `request_sha256` does not match, one naming an absent item, one whose
      `follows` names a missing answer, and one that is not UTF-8, each shown
      as unreadable with its reason; two answers whose file names sort one
      way and whose `answered_at` values sort the other; an absent
      `answers/` folder;
    - item 8's two fixes: a non-UTF-8 answer naming a microscope item makes
      that item's state unreadable, and an unreadable microscope item
      refuses the next delivery and writes nothing;
    - under the mock, only `write_dir` changes, and the shipped sample's
      files hash the same before and after;
    - the audit entry carries neither the words nor the file's name;
    - the web: each form's Send delivers and says so; a refused file says
      why in the form; the requests list in each state; "Earlier questions"
      offers a delivered question.

## What not to do

- Write nothing into the librarian's tree except
  `console_inbox/<item_id>.json` and its one `<item_id>--<name>`. Never
  `answers/`, `kb/` or anything else. The answer is the librarian's to write.
- Do not open, serve or preview an attached file anywhere in the console,
  and do not read one back after writing it.
- Do not call the librarian's service or hold a `caller_id`. An `ask` is
  answered from the inbox, not by the console querying the store.
- Check no entry and no result card for existence.
- **The server runs no git, and you commit no item.** Which console seat
  commits items, and when, is a later card. Your commit carries `console/`
  only.
- No test writes into a real tree. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest -p no:cacheprovider` passes, and the `jsonschema` half
  passes under `uv run --with jsonschema`.
- After the tests, `git status` shows no new file under any `console_inbox/`
  or `answers/`, and nothing under `console/requests/`.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
