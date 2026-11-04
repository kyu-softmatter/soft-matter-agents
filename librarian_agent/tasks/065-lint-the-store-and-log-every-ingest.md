# 065 — lint the store against itself, and log every ingest and lint

Written by `manager-librarian-20261007-1` on 2026-11-04. You read this; you do
not edit it.

**For a librarian execution seat** (librarian-20261007-1, or whichever
librarian seat the person opens next). If you are not a librarian seat, take
nothing from this card and report up.

## GOAL

The person adopted four standing operations for the store on 2026-11-03
(D-20261103-office-11, `c90291b1`; `plan.md` 4.3 item 9, 4.3.1, 11-28):
- lint as a standing operation, reported as a card;
- an ingest and lint log beside the query log;
- the ingest sequence in your instructions;
- the wiki as a generated layer that cites entries sentence by sentence and
  is never cited.

What each means for a session is in your `CLAUDE.md`, under "Standing
operations". This card builds the code behind it.

## TASK

1. **`src/ingest_log.py`.** It appends `queries/ingest_log.jsonl` and offers
   `record` and `verify`, the way `query_log.py` does. One line per act, and
   the shape is fixed:

   ```
   {"at": "<date-time>", "op": "ingest" | "withdraw" | "lint", "by": "<seat>",
    "sources": ["<source id>", ...], "entries_made": [...], "entries_withdrawn": [...],
    "report": "<queries/lint-*.json>" | null,
    "kb_version_before": "kbv-...", "kb_version_after": "kbv-..."}
   ```

   - **An unknown field is refused**, and so is a missing one.
   - An `ingest` names exactly one source, which is the "never two sources in
     one pass" rule held by code.
   - A `lint` names no source and no entry, names its report, and has equal
     versions.
   - A `withdraw` names the entries it withdrew and the source or reason
     record behind it. Withdrawing marks; it never deletes.
   - Append only: `verify` fails if an earlier line changed. Use the query
     log's method, not a new one.

2. **`src/kb_lint.py`.** It reads the store and `queries/log.jsonl`, and
   writes one report to `queries/lint-<YYYYMMDD>[-<n>].json` in the form
   `contracts/schemas/kb_lint.schema.json` fixes. Then it appends the
   `lint` line through `ingest_log.record`.
   - **It writes nothing under `kb/`.** Read `kb_version` before and after,
     and refuse to finish if they differ.
   - **unresolved_relations**: walk `conflict_with`, `refuted_by`, `refutes`
     and `supersedes` on every entry. The schema's `problem` enum is the
     whole list of outcomes. A conflict both sides record is `open_pair`,
     because conflicts are kept and that is not a defect.
   - **past_valid_until**: a date-valued `valid_until` earlier than
     `run_at`'s date. An event-bounded one is not listed.
   - **unfiled**: exactly what `wiki.py` puts on `unfiled.md`. Import its
     function; do not write a second definition.
   - **unpaged_names**: a device, quantity, sample or configuration name held
     in a registry or staging table that `wiki.py` renders no page for.
     `held_in` is that table's path.
   - **repeated_gaps**: from `queries/log.jsonl`, answered lines only.
     - Leave out self-test callers and `in_published_table` answers.
     - Group by gap name and kind, and keep a group asked two or more times.
     - `questions` counts distinct question ids in the `caller_id`s.
     - Sort by name.
     - **Keep this code out of `mcp_server.py` and `query_log.py`.**
       `mcp_server.py` must not import `kb_lint.py`, and a self-test asserts
       that.
   - **No number taken from an entry appears in the report.** The schema
     refuses a stray `value` field, and the self-test asserts the rest.
   - `--trigger session_start|publish|asked` sets `trigger`. With
     `session_start`, skip (write nothing, exit 0, print why) when the latest
     report already has the current `kb_version` and `query_log_lines`.

3. **Every sentence on a wiki page cites an entry.** Audit `wiki.py`'s
   output, then fix it.
   - Each prose sentence that states something about the world carries the
     entry id it rests on.
   - A verbatim table block names its table path and the row's `entry_ref`.
   - **Template lines are exempt only if they are listed.** Navigation and
     "cite the entries, not this page" lines are fixed strings. List them in
     `wiki.py` as the template set, and exempt only those.
   - Add `wiki.py --check` refusing a sentence outside the template set
     that names no entry id.
   - Report how many sentences failed before your fix.

4. **Self-tests**, each watched failing before it passes:
   - `ingest_log.py`:
     - an unknown field is refused;
     - an ingest with two sources is refused;
     - a lint line with unequal versions is refused;
     - an edited earlier line fails `verify`.
   - `kb_lint.py`, on a synthetic store, one case per `problem` value and
     one per list:
     - an empty list is written as `[]`;
     - the report validates against the schema;
     - `kb/` is byte-identical before and after;
     - `mcp_server.py` does not import it.
   - `wiki.py`: a rendered sentence with no entry id outside the template
     set fails `--check`.

5. Run lint once with `--trigger asked` on the real store, and commit the
   report, its log line and the code together. Then run `kb_index.py`,
   `wiki.py --check` and the validator.

## CONTRACT

- The report's form is `contracts/schemas/kb_lint.schema.json` (schema
  0.1). It is wired into check 1 with a passing and a refused history row.
  A report the schema refuses fails the gate.
- No card can cite a page, and that is structural. Check 25 refuses a page
  stem in `kb_refs` (history row `fixture_25_a_card_citing_a_wiki_page`).
  Never give an entry an id equal to a page's file stem.
- The ingest log has no schema or check yet. Once your first lines land,
  the manager writes one from the shape above. Do not change the shape
  without telling manager-librarian first.

## CONSTRAINTS

- Lint decides nothing about what is true. It fixes nothing and ranks
  nothing.
- `query_log.py` gains no reader. 4.3.1 rule 4 is why the count lives here.
- Standard library plus what `src/` already imports.
- Commit `queries/ingest_log.jsonl` with the work each line records, never
  in a later sweep.
- A change to `wiki.py`'s page form still keeps the four rules the console
  relies on (your `CLAUDE.md`, "The console shows these pages").

## Not decided here, and not yours to decide

- **What to do about a finding.** Each fix is its own act, under the entry
  rules, in a later task or on the person's word.
- **Whether lint runs on a clock.** It does not. Session start, publish and
  on request are the whole schedule.

## REPORT

Send manager-librarian-20261007-1, 6 lines at most:

- the commit hash, and the self-tests you watched fail;
- the first report's path and one count per list;
- how many wiki sentences lacked an entry id before your fix, and the
  template set's size;
- anything in the schema that did not fit what you found, before you work
  around it.
