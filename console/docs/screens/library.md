# Library screen (console card 016)

Area `library` (`web/src/features/library/`, hash `#/library/<page>`). The librarian's generated pages grouped by
the kind of data, the data map, and four request forms with the list of requests and answers. **It shows generated files
and the requests and answers of the inbox, and nothing else of the store.** The console holds no `caller_id`, makes no query, keeps nothing and cites no page: a
fact is cited by its entry, never by a page. Entries, the query log and exports are not shown.

`rest` forms: `` (Pages) | `pages` | `pages/<page>` | `map` | `ask` | `add` | `withdraw` | `offer`.

Server routes (`server/api/library.py`). The one that sends is `POST /api/library/requests`:

| Route | What |
|---|---|
| `GET /api/library/index` | `kb/wiki/index.md` split into its groups (devices, quantities, observables, samples and configurations, unfiled), its facts, the names registered but with no entry, and its footer |
| `GET /api/library/pages/{page_id}` | one generated page as blocks of text; 404 for a name that is not a generated page |
| `GET /api/library/map` | `kb/wiki/map.json` as counts by evidence grade, or "not built yet" |
| `GET /api/library/answers` | the librarian's answers read from `librarian_agent/answers/`: example answers under the mock store |
| `GET /api/library/requests` | every request in the librarian's inbox, newest first, each with its answers and its state, and the answers that name no request |
| `POST /api/library/requests` | writes one request into the librarian's inbox (and the one file it names beside it) and returns the item written, with its `item_id` and the attachment's name; a viewer login is refused (403) and nothing is written |

The readers are `agents/library.py` (it opens `kb/wiki/*.md`, `kb/wiki/map.json` and, for the version only,
`kb/index.json`) and `agents/store_requests.py` (it reads `console_inbox/` and `answers/` of the librarian's folder,
and writes one request and its one file). Nothing else of the store is read or written.

## Pages

- A wiki page is shown as it stands. Its footer is "Generated from the knowledge store at kbv-<12 hex>. Do not
  edit by hand: correct the store and regenerate." and is shown unchanged.
- If the footer's version is behind the version in `kb/index.json`, the screen says plainly that the page was built
  from an older version of the store.
- A link to another wiki page is followed. A link to an entry or a guide is **text and never followed**.

## Data map

Only `map.json` (and the evidence page) are shown. Until they exist the screen says "Not built yet". Coverage is
**counts only**: entries per evidence grade E1 to E5 and how many are disputed, per subject. There is no score, no
rank and no single number. A map whose version is behind the store says so.

## The four forms

All four are open to every login the console allows except a viewer. **Send checks the form and then delivers it:
the request is written as one `console_store_request` item into `librarian_agent/console_inbox/`, and the form says
"Sent to the librarian."** A form that fails its check says what to fix and sends nothing. The words are sent once,
exactly as typed, as `words`; the server sets the request's own field (`fact_wanted`, `reason`, `fact_in_words` or
`question`) to the same words trimmed, and a request that already carries that field is refused. The item is the
`console_store_request.schema.json` item and has no other key; the server checks it against the tree's schema before
writing and writes nothing when it fails. Only the shapes of an entry name and a result card path are checked, never
whether they exist.

**The one file.** A form that names a file (`document` of an added document, or a withdrawal's `evidence`) sends it
inside the request, as base64, under its cleaned name, and the request names exactly the file it sends. The server
writes it beside the item as `<item_id>--<name>` and records `{file, sha256}` under `attachments`. A file over 20 MB,
an empty file, and a file whose bytes parse as JSON holding an object are refused in words and nothing is written (a
bare number or string is taken). The file is never opened, served or read back by the console.

**How it is written.** The attachment first, then the item, each under a temporary name in
`console/requests/outgoing/` and linked to its final name in the inbox, under one lock from the first link to the
last. A taken name gets another `item_id`, up to five times. If the item's link fails after the attachment's
succeeded, only the attachment this call linked is removed. The folder must already exist: if not, nothing is written
and the asker is told "The librarian's inbox is not there, so nothing was sent." Under `--store mock` the item goes
into the mock's own write folder as `librarian_agent/console_inbox/`; the shipped sample is never written. The audit
line `question_submitted` carries the `item_id`, the kind and whether a file was attached; never the words and never
the file's name. The console commits nothing.

The shapes are the four requests of `console_store_request.schema.json`; `shapes.fixture.json` holds one case per
shape, the web tests assert the forms build exactly those, and `tests/server/test_library_request_shapes.py` delivers
each through the server's writer and validates the item against the schema.

| Form | Builds | Note shown |
|---|---|---|
| Add a document or value | `enter_document`: a maker's document, a paper, read off the instrument, or remembered | A remembered value "enters at the lowest grade": the grade comes from the kind of source and is never chosen here |
| Withdraw a value | `withdraw_value`: entry name, reason, and evidence (none, a reading, a document, a replacing entry) | Words alone cannot refute a value |
| Offer a result | `offer_result`: the result card's path and the fact in words | |
| Ask the librarian | `ask`: the question and optional conditions | an answer carries each number's entry, grade and source and whether the entry covers the conditions |

## Requests and answers

Under every form the screen lists the requests in the librarian's inbox, read by exact item name (an attached file is
never read as an item), newest first by `asked_at` (`item_id` breaks a tie). Each shows its kind in words, its words,
the login and the time, and its attached file's name as text, never a link. Its answers are listed under it, newest
first by `answered_at` (`answer_id` breaks a tie). The state is the latest answer's outcome in words: "delivered · not
answered yet" when none has come; "waiting for a name" (with the quantity name) while the librarian waits, continued
by the answer that `follows` it; and "an answer is on disk and cannot be read", with the reason, whenever any answer
naming the request cannot be read. An answer that names no request in the inbox is listed after the requests, under
"Answers that name no request in the inbox", as unreadable.

An answer is read from `librarian_agent/answers/` only by its exact name `ca-<yyyymmdd>-<hhmmss>-<four>.json`, and is
readable only when it passes `store_answer.schema.json`, its item is in the inbox, its `request_sha256` equals the
sha256 of that item's bytes as they lie on disk, and the answer it `follows`, if any, is there and names the same
item. The files are read as bytes, so a file that is not UTF-8 is unreadable and not skipped. Every number comes with
its entry, grade and source as recorded, and whether it covers the conditions asked. No E6 appears and the console
adds no search.

Under `--store mock` the sample holds nine example requests and ten example answers (the seven outcomes of a request,
two answers to a question, and one that follows the waiting-for-a-name example and enters it), each labelled
"example data". The list carries its own note, not the pages': "These are example answers written for the console's
practice data, not answers from any librarian. Their names and numbers are made up." Under `--store sma` the lists
are what lies in the librarian's folders, and "No requests yet." / "No answers yet." when there is nothing.
