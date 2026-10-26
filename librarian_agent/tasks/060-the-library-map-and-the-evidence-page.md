# 060 — the library's map, and a page by kind of evidence

status: open · issued 2026-10-25 by manager-librarian-20261007-1 · **for
librarian-20261007-1**: two more outputs of `wiki.py`, and a re-render.
**The person's word**: the Library holds "1. 질문을 작성할 수 있는 창 2.
데이터 종류 별 구분 3. 데이터 맵 (관계도, 전문성 등) - 인사이트를 얻으려
함." ("a window for writing a question; a division by data type; a data map
of relationships, expertise and the like, for insight"), committed verbatim
at `1641323a` (`docs/ideas/20261025.md`, I-20261025-office-01). Part 2 and
part 3 are this card. Part 1 waits on the person.
**The display rule**: architecture-20261007-1 agreed on 2026-10-25 to widen
`plan.md` 4.3.1 from "the generated wiki pages" to "the generated files under
`kb/wiki/`", with the same promises. It writes the widening once the person
has answered its question on the data map. **Build and commit meanwhile. The
console shows the map only after the widening lands.**

## GOAL

The wiki answers "what does the store know about this one thing". It cannot
yet answer how the things relate, or how much of the store rests on
measurement and how much on documents or memory. Both are wanted for insight,
and both are already in the entries' own fields. This card generates them, by
code, from the store alone, in the same sitting as the pages, under the same
footer version.

## PART A — `kb/wiki/evidence.md`, the store by kind of evidence

One more generated page, linked from `index.md`. It has the same fixed first
lines and footer as every page (054).

- One section per grade, in the order E1, E2, E3, E4, E5, titled with
  054's words: measured on this instrument; calibrated on this instrument;
  from a document, a reading off the instrument, or another project's record;
  computed; recalled or assumed. A grade with no entries says "None."
- Inside a section, one row per entry, in the server's order (grade, then
  the rank inside E3, then `entry_id`). The columns are: entry id (linked to
  the entry file), the source kind in words, grade and source exactly as
  recorded, status as the server reports it, and the subject pages it
  appears on (linked).
- The section heading carries the entry count, and nothing else is counted.
  No percentages, no totals across grades beyond what `index.md` already
  states, and no ranking.

## PART B — `kb/wiki/map.json`, the relationships, for the console to draw

One generated JSON file. The console draws it and computes nothing.
**Nothing on the map is a number taken from an entry.** Values stay on the
pages, beside their provenance. The map carries ids, kinds, grades, sources
and statuses, as the entries record them.

```json
{
  "artifact": "kb_map",
  "schema_version": "0.1",
  "kb_version": "kbv-<12 hex>",
  "footer": "Generated from the knowledge store at kbv-<12 hex>. Do not edit by hand: correct the store and regenerate.",
  "nodes": [
    {"id": "page:device_camera_red", "kind": "device", "page": "device_camera_red.md"},
    {"id": "entry:<entry_id>", "kind": "entry", "grade": "E3", "source": "spec:...", "status": "current"}
  ],
  "edges": [
    {"type": "about", "from": "entry:<entry_id>", "to": "page:device_camera_red", "stated_by": "<entry_id>"}
  ]
}
```

- **Nodes**:
  - one per wiki page that is a subject (the five sections, using the page's
    file name as id after `page:`);
  - one per entry. The entry carries `grade` and `source` exactly as
    recorded, and `status` as the server reports it.
- **Edges**. Every edge names the entry whose own field states it, in
  `stated_by`. The edge types are the store's fields and nothing invented:
  - `about`: an entry to each subject page it appears on (054's rule for
    which pages an entry lands on);
  - `conflict_with`, `refutes`, `supersedes`: entry to entry, as the
    fields hold them. Write each relation once, in the direction its field
    states it;
  - `supports`: entry to entry, for supports that name an entry;
  - `input_of`: for a computed entry, each input entry to it, when its
    `inputs` name entries.
  - A field naming an entry the store does not hold is not drawn. List it
    under a top-level `"dangling"` array as `{stated_by, field, names}`.
- **Deterministic**: nodes sorted by id; edges sorted by (type, from, to,
  stated_by); `json.dumps(..., indent=1, sort_keys=True, ensure_ascii=True)`
  plus one LF. The same store version gives the same bytes.
- **Expertise** waits on the person. If the person says it means how well
  the store knows each subject, a later card adds per-page counts by grade to
  the subject nodes. If it means who knows what, nothing is added, because
  that concerns logins, not the store. **Add nothing for it now.**
- The ontology's relations (alias, is-a, part-of, read-back-label-of,
  measured-by) join as new edge types when the ontology lands. The format
  leaves room by having `type` be an open string here; the check pins the
  current set, and that set grows with the ontology card.

## TASK

1. `wiki.py` renders both, and `--check` compares both, failing on any
   difference, as for pages.
2. Self-test, each case watched failing first:
   - an entry with a conflict draws one `conflict_with` edge, not two;
   - an edge to a missing entry goes to `dangling` and is not drawn;
   - `evidence.md` puts an E2 entry under the calibrated section and shows
     its status;
   - the map holds no key named `value` or `values` anywhere.
3. Re-render at the current version and commit `wiki.py`, `evidence.md`,
   `map.json` and the re-rendered `index.md` together. No `kb_version` move.

## CONTRACT

- **`kb/wiki/evidence.md` and `kb/wiki/map.json` are new paths.** Before your
  commit of them I add both to the validator's `ALLOWED_PATHS` and extend
  check 87, which judges the map's `kb_version`, and its `footer`, as it
  judges a page's footer line. The check and its fixture land in one commit,
  watched failing first. **Do not commit the two files until I tell you
  that has landed.** The generator and its self-test can commit before.
- I tell manager-console the file's shape before it lands, as 11-25 asks of
  any change to what the console reads.

## CONSTRAINTS

Commit through `contracts/tools/seat_commit.py` under your row, and
validate with the uv form. Dead ends go in `failures.jsonl` naming
`task: 060`.

## REPORT

The commit. `--check`'s result. The node and edge counts by type, and the
`dangling` list if any. The four self-test failures you watched. One section
heading of `evidence.md` as it reads.
