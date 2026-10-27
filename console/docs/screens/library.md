# Library screen (console card 016)

Area `library` (`web/src/features/library/`, hash `#/library/<page>`). The librarian's generated pages grouped by
the kind of data, the data map, and four request forms with an answers list. **It shows generated files and
nothing else of the store.** The console holds no `caller_id`, makes no query, keeps nothing and cites no page: a
fact is cited by its entry, never by a page. Entries, the query log and exports are not shown.

`rest` forms: `` (Pages) | `pages` | `pages/<page>` | `map` | `ask` | `add` | `withdraw` | `offer`.

Server routes (`server/api/library.py`), all reads. There is no route that sends:

| Route | What |
|---|---|
| `GET /api/library/index` | `kb/wiki/index.md` split into its groups (devices, quantities, observables, samples and configurations, unfiled), its facts, the names registered but with no entry, and its footer |
| `GET /api/library/pages/{page_id}` | one generated page as blocks of text; 404 for a name that is not a generated page |
| `GET /api/library/map` | `kb/wiki/map.json` as counts by evidence grade, or "not built yet" |
| `GET /api/library/answers` | the librarian's answers: example answers under the mock store, none from a real tree |

The one reader is `agents/library.py`. It opens `kb/wiki/*.md`, `kb/wiki/map.json` and, for the version only,
`kb/index.json`, and nothing else.

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

All four are open to every login the console allows. **Send checks the form and answers "Not sent: the librarian's
inbox is not open yet." It writes no file and sends nothing**, and the check calls no server. The shapes are the
four requests of `console_store_request.schema.json`; `shapes.fixture.json` holds one case per shape, the web tests
assert the forms build exactly those, and `tests/server/test_library_request_shapes.py` validates each against the
schema.

| Form | Builds | Note shown |
|---|---|---|
| Add a document or value | `enter_document`: a maker's document, a paper, read off the instrument, or remembered | A remembered value "enters at the lowest grade": the grade comes from the kind of source and is never chosen here |
| Withdraw a value | `withdraw_value`: entry name, reason, and evidence (none, a reading, a document, a replacing entry) | Words alone cannot refute a value |
| Offer a result | `offer_result`: the result card's path and the fact in words | |
| Ask the librarian | `ask`: the question and optional conditions | an answer carries each number's entry, grade and source and whether the entry covers the conditions |

## Answers

Under `--store mock` the list holds nine example answers, each labelled "example data", covering the seven
outcomes of a request and the two answers to a question. Under `--store sma` it says "No answers yet.", whatever
lies in the librarian's answers folder: the console reads none of the real ones until the inbox is open. Every number comes with its entry,
grade and source as recorded, and whether it covers the conditions asked. No E6 appears and the console adds no
search.
