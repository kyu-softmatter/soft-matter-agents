# librarian_agent — the knowledge store

This directory is the **only** place knowledge lives (P14). Execution agents keep
records and snapshots; they never keep their own store.

## Right now it is a store, not an agent

`plan.md` §4.3.0 splits the two. The store exists from M1; the agent — MCP
server, context-scoped queries, `gaps`, distillation, external search, conflict
detection — arrives at M3.

So until M3:

- **A person curates the entries by hand.** Every entry records `curated_by`.
- **Agents read the files directly** and cite `kb:<entry_id>` in their cards.
- **The validator checks those citations against this store**: a card claiming
  to have inherited E3 from an entry the store grades E3 passes; a card that
  promotes it to E1 fails (checks 21 and 25).

What is missing is not values but **the discovery of gaps**: nothing here can
yet tell an agent what the store does not have, which claims disagree, or
whether the answer exists outside. That is why cards carry
`degraded: ["librarian_agent"]` — it means "we do not know what we missed", not
"we had no literature".

## Layout

```
kb/entries/     one atomic claim per file, machine-read. Authoritative.
kb/sources/     identifiers only: DOI, URL, local path, access date, licence note.
                No reproduced text (§4.3).
kb/distilled/   human-readable notes: what is claimed, under what conditions,
                and what it does not cover.
kb/index.json   generated. Do not hand-edit.
kb/lessons/     empty until M5 (§8.2).
```

## Rules for adding an entry

1. **One claim per file.** A file holding two claims cannot be superseded or
   refuted independently.
2. **`validity_conditions` is required.** A claim without them is not reusable —
   the next question will apply it where it does not hold.
3. **The grade comes from the source kind, not from confidence.** E3 covers
   peer-reviewed work, textbooks, vendor specs and preprints; the sub-rank is in
   `grade_tag`, and citation preference runs peer_reviewed → textbook →
   vendor_spec → preprint.
4. **General search results are not entries.** Blogs, forums, summary pages and
   model output may point at a real source; only the real source is entered. If
   the trail ends, nothing is entered.
5. **E6 never enters.** A value a model produced belongs in conversation, labelled.
6. **Conflicts are kept, not merged.** Two entries that disagree both stay, each
   naming the other in `conflict_with`, with the difference in conditions written
   down.
7. **Nothing is deleted.** A superseded entry stays and the new one points back
   with `supersedes`.

## After editing entries

```bash
python3 librarian_agent/src/kb_index.py          # rebuild the index
python3 librarian_agent/src/kb_index.py --check  # fail if it is stale
python3 contracts/validate.py                    # entries are schema-checked here too
```

`kb_version` is a content hash over every entry. Cards pin it, so siblings in one
fan-out read the same knowledge and a question rerun at the same version gives
the same constraints. Changing an entry changes the version, which is the point:
a card pinned to an older version is flagged rather than silently re-interpreted.
