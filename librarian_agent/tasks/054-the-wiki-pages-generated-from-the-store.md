# 054 — the wiki: one generated page per subject, read and never cited

status: closed · **verified on disk 2026-10-18** by manager-librarian-20261007-1. librarian-20261007-1 committed and pushed it at `3d167ea1`: 87 pages and `wiki.py` together, flat as ruled at `e275ab39`. The pages are device 28, quantity 37, observable 17, sample 2, configuration 1, plus index and unfiled. `wiki.py --check`: 87 of 87 current. Check 87: 87 wiki pages at `kbv-37b1958fb73d`. Every footer is the fixed last line; no page holds raw HTML (the `<` seen is `kb:<entry_id>` in code spans and escaped `\<`); and every link stays inside `kb/`. The self-test was watched failing on eleven one-rule mutants. The ALLOWED_PATHS and check 87 halves are this seat's, at `44b5f24b` and `e275ab39`. **One gap in this card's own layout, carried to 055**: the values table shows `validity` and not `identifiers`, so a reader of the pixel-size page cannot tell which objective a row belongs to. · issued 2026-10-18 by manager-librarian-20261007-1. **The
person's go**: "사서 위키·온톨로지 작업을 권한 순서대로 시작해" ("start the
librarian wiki and ontology work in the recommended order"), said in the
intake seat's window and committed verbatim at `42e66bad`
(`docs/ideas/20261017.md`, I-20261017-02). Routed by architecture-20261007-1.
The order the person was offered and approved is **wiki, then ontology,
then source search**. `plan.md` 11-28's own text recommends the ontology
schema first; architecture has been told the two differ. **For
librarian-20261007-1**: the generator is your code. The page set and layout
below are this seat's, as 11-28 leaves them to manager-librarian.

## GOAL

The store answers a seat that knows what to ask. It does not let anyone
read what it knows about a thing. Today the only pages are ten safety
guides. The wiki widens that pattern. **Pages are generated from entries by
code**, one per subject, each number shown with its provenance. Each page is
footed with the `kb_version` it was rendered from and regenerated at every
publish. A page is **read and never cited**: `kb:` cites entries and nothing
else, so no page becomes a second authority. A hand edit is drift that the
next render overwrites (P3).

## THE PAGE SET (settled here)

At `kbv-37b1958fb73d` the store has 339 entries. 28 devices, 43 quantities,
2 samples and 1 configuration are named as subjects, and 55 entries name no
subject. Re-derive the counts; do not trust these.

| page | path | one per |
|---|---|---|
| index | `kb/wiki/index.md` | the store: its version, counts, and every page by section |
| device | `kb/wiki/device_<id>.md` | device id named as a subject in any entry |
| quantity | `kb/wiki/quantity_<id>.md` | id in `contracts/quantities.json` that any entry names, as subject or in `numbers[].name` |
| observable | `kb/wiki/observable_<id>.md` | **every** id in `contracts/observables.json`, with or without entries |
| sample | `kb/wiki/sample_<id>.md` | sample id named as a subject |
| configuration | `kb/wiki/configuration_<id>.md` | configuration id named as a subject |
| unfiled | `kb/wiki/unfiled.md` | the entries with no subject, so that nothing is invisible |

- **Flat, with the section as a prefix** (changed 2026-10-18, before any page
  was committed). A folder per section put every page at depth 5, which
  `plan.md` 7.1 rule 6 refuses inside an agent tree (check 13, the 85
  failures librarian-20261007-1 hit on the first render). The prefix also keeps
  a quantity and an observable with the same id apart.
- **An observable gets a page even with no entries.** That a registered
  observable has no value in the store is worth reading.
- **A quantity gets a page only when something uses it.** A registered name
  with no entry is listed on the index, not given an empty page.
- An entry naming several subjects appears on each of their pages. That is
  repetition by design; the entry is still one file.
- **Nothing else**: no topic pages, no pages for papers (the distillation
  notes already exist and are linked as reading), and no page tree from
  the ontology. That waits for the ontology, which 11-28 leaves open.

## THE LAYOUT (settled here)

Every page has the same sections in this order. A section with nothing in
it says "None." rather than disappearing, as the safety guides do.

1. **Title and one line**: what the page is about, then the fixed sentence
   *"Generated from the store; cite the entries, as `kb:<entry_id>`, not
   this page."*
2. **What it is**: the registry's own text, verbatim and labelled with
   where it comes from. For a quantity or observable that is its
   definition and unit from `contracts/`, labelled "the managers'
   registry". For a device it is its row in `kb/staging/devices.v0.json`.
   For a sample it is its row in `kb/staging/samples.v0.json`. If there is
   no registry text, say so.
3. **Values**: one table row per number in the entries on this page. The
   columns are quantity, value, unit, **how it is known**, conditions,
   subject, and entry id.
   - **How it is known is the grade in words**, never the bare code,
     because the person reads these pages:
     - E1: measured on this instrument
     - E2: calibrated on this instrument
     - E3: from a document, a reading off the instrument, or another project's record
     - E4: computed
     - E5: recalled or assumed
   - Then the source kind in words, for example "manufacturer's
     specification" or "the person read it off the instrument".
   - **Beside it, in its own column, the grade code and source exactly as
     the entry records them** (for example `E3 · spec:Kinetix22`). The
     console's rule is that a number it shows carries its source and grade
     as the entry gives them, and adds nothing the page does not say. So
     the words are for the person, and this column is the record.
4. **Claims**: the entries with no numbers, with each claim sentence
   verbatim. Each entry's `validity_conditions` follows it in full, verbatim
   and never shortened, as a Markdown blockquote. **No raw HTML**: no
   `<details>`, no `<sub>`, no inline tags anywhere on a page.
5. **Disputed and withdrawn**: every entry on the page whose status is
   refuted, superseded or in conflict, with the entry on the other side
   named and linked. **Both sides are shown and neither is preferred.** A
   page never says which value to use.
6. **Reading**: the distillation notes in `kb/distilled/` that name this id,
   as links. A link is reading, not a source.
7. **Related**: the other pages that share entries with this one, and for
   a device its safety guide in `kb/guides/` if one exists.
8. **Footer**: the last line of every page, in exactly one fixed,
   machine-readable form and nothing else on that line:
   `Generated from the knowledge store at kbv-<12 hex>. Do not edit by hand: correct the store and regenerate.`
   It is the guides' sentence **without their `<sub>` tag**, so the
   console can read which version a page shows and notice when
   `kb/index.json` has moved past it.

Rules that bind the generator:

- **Only fields, no prose of its own.** No summary, no "best value", no
  average, no ranking beyond the store's own sort (grade, then rank inside
  E3, then `entry_id`, the server's order). The only sentences on a page
  are the fixed ones above and text quoted from entries and registries.
- **Deterministic.** The same store version gives byte-identical pages. No
  timestamps, no dict-order dependence, and LF line endings.
- **Status as the server reports it** (048): refuted, superseded, in
  conflict or current.
- **Links are relative paths inside `kb/wiki/`**, plus the entry and guide
  files, so the pages read the same in the repository and in the console.
  Nothing links outside `kb/`. The console shows such a link as text and
  does not follow it.
- **Plain Markdown, ASCII filenames, stable ids in paths.** The filename is
  the id, which is already lowercase snake case.
- These four rules (provenance as recorded, one footer form, no HTML,
  links inside `kb/`) are **the console manager's constraints of
  2026-10-18**, given so a page can be shown as it stands, without
  rewriting, if store display is ever allowed. The console shows no store
  content today, and that permission is open in `plan.md` 4.3.1.

## TASK

1. `librarian_agent/src/wiki.py`, standard library only, in the shape of
   `safety_guides.py`: rendering writes the pages, and `--check` renders
   and compares, failing on any difference. The pages are generated, never
   written by hand.
2. Run it at every publish, in the same commit as the guides. Add
   it to the publish steps in `librarian_agent/CLAUDE.md`. Tell me the
   wording and I add it, because that file is mine.
3. A self-test: one entry per status renders on the right pages, an entry
   with two subjects appears on both, and an observable with no entries
   still gets its page. Watch it fail on a renderer missing each rule before
   it passes.
4. Render once at the current version and commit the pages with the
   generator.

## CONTRACT

- **`kb/wiki/` is a new path.** Before your first commit of pages:
  architecture adds it to `plan.md` 7, and I add it to the validator's
  `ALLOWED_PATHS` and extend **check 87** so a wiki page whose footer
  names neither the store's version nor the published one fails, the way a
  guide does. Check 87 and its fixture land in one commit, watched failing
  first. **Do not commit pages until I tell you both have landed.** The
  generator and its self-test can commit before that.
- No entry changes, so `kb_version` does not move. Rendering is not
  publishing.
- The console reads `kb/` as data (11-25). I tell its manager that the
  pages exist before they land, as 11-25 asks of any change to what it
  reads.

## CONSTRAINTS

Commit through `contracts/tools/seat_commit.py` under your row, and
validate with the uv form. Dead ends go in `failures.jsonl` naming
`task: 054`.

## REPORT

Page counts per section, and the `--check` result. The self-test failures
you watched. The publish-step wording for `CLAUDE.md`. The commits. One
sentence on what is still not on disk.
