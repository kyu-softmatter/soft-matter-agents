# 016 — the Library screen, with its request forms

Written by `manager-console-office-20261017-1`. You read this; you do not edit it.

**Assigned to `console-office-20261017-1` (Console 1)**, after card 015. If you
are not that seat, take nothing from this card and report up.

**Send questions for the person to the intake seat,
`architecture-office-20261017-2`, not to your own window.**

## Why

The person asked for the Library to be built (I-20261024-office-02,
`5f88eab4`). Every allowed login may send the librarian three requests, and
none of them waits for the person: enter this document, withdraw this value,
offer this result (`89e7cf05`, `0a387d1b`). The store's manager read the
screen at canvas version 46 (`PLibrary`).

Two things frame it:
- **plan.md 4.3.1 now lets the console show the generated wiki pages under
  `librarian_agent/kb/wiki/` as data, and nothing else of the store**
  (`527376c3`, architecture-20261007-1; the store's manager agrees). That
  means:
  - read only;
  - no `caller_id`, no query;
  - nothing shown is kept or lands on a card;
  - entries, the query log and exports are not shown;
  - the console never cites a page: a fact is cited by its entry.
- **Nothing reaches the librarian until the agents' console inbox opens**
  (plan.md 7.1.1, proposed, `527376c3`). It opens only on the person's
  approval, and only once both runners refuse unapproved runs from another
  login. The request and answer schemas are manager-librarian's, written
  after that approval.

## What to do

1. **What the library holds: the wiki pages, from `kb/wiki/` only.**
   - The pages are flat: `index.md`, `unfiled.md`, and
     `<section>_<id>.md`, where the section is device, quantity,
     observable, sample or configuration. Start at `index.md`.
   - **A page is shown as it stands**, with the provenance and grade beside
     each number as the page writes them.
   - **Its last line is the footer**, exactly: "Generated from the
     knowledge store at kbv-<12 hex>. Do not edit by hand: correct the store
     and regenerate." Check 87 holds that line. Compare that version with
     the current one in `kb/index.json`. When the index has moved past it,
     say plainly that the page was built from an older version of the
     store.
   - **Links between pages are followed. A link to an entry or a guide is
     shown as text and not followed**, because only `kb/wiki/` may be
     displayed.
   - Read nothing else under `librarian_agent/`, except the version in
     `kb/index.json`.
2. **Three tabs of forms, open to every allowed login.**
   - **Add a document or a value.**
     - The kind of source: a maker's document, a paper, read off the
       instrument, or I remember it.
     - Who read it.
     - A file, or for a remembered value, the value and its unit.
     - What to take from it, in the asker's words.
     - A remembered value is labelled as entering at the lowest grade. A
       note says the grade comes from the kind of source.
   - **Withdraw a value.**
     - The entry's name in the library, typed or pasted.
     - The reason, in the asker's words.
     - Evidence, if any: a contradicting reading, a document, or the
       replacing entry.
     - A note says words alone cannot refute a value.
   - **Offer a result.**
     - Which result.
     - The fact it shows, in the asker's words.
3. **Send checks the form and sends nothing.** It answers "Not sent: the
   librarian's inbox is not open yet." No file is written: the request
   schema is not written yet, so the console invents no shape.
4. **The answers list.**
   - Under `--store mock`, example answers from the mock sample, labelled
     "example data", covering all seven: entered, naming its entry; waiting
     for a name; refuted; in conflict; superseded; kept, with the reason; no
     entry of that name.
   - Under `--store sma`: "No answers yet."
5. **Tests, each watched failing first:**
   - the only paths read under `librarian_agent/` are `kb/wiki/*.md` and
     `kb/index.json`, for its version alone;
   - a link to an entry or a guide is shown as text and never followed;
   - a page whose footer version is behind `kb/index.json` says so;
   - Send writes nothing and makes no request beyond the console's own
     check;
   - a remembered value carries the lowest-grade label;
   - the mock's answers cover the seven outcomes, each labelled example;
   - the real store shows "No answers yet".

## What not to do

- Read nothing of the store beyond the wiki pages and the index's version.
  Call nothing of the librarian's: no `caller_id`, no query.
- Write no request file.
- No write outside `console/`. Install nothing.

## Done when

- `npm run typecheck`, `npm test` and `npm run build` pass from `web/`.
- `uv run pytest` passes.
- The validator ends `0 failed`.
- One commit through `contracts/tools/seat_commit.py`. Report the hash to
  this seat.
