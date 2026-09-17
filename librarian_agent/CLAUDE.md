# librarian_agent — the knowledge store, and now the service on top of it

This directory is the **only** place knowledge lives (P14). Execution agents keep
records and hash-checked snapshots; they never keep their own store.

## You are next

The implementation order changed on 2026-09-17: it is now librarian, microscope,
simulation, bridge (`plan.md` §9). The milestone is still called **M3** — the
names label bodies of work, and the order is the first column of §9's table.

Two reasons this seat went first. It has **no collaboration dependency at all**
(§4.3.2), so nothing here needs a stub or a mock counterpart. And what is
blocked is here: the flat tables in `kb/staging/` have been waiting for a
querying side to decide how they should be decomposed, and that querying side is
this agent.

The order of work is not arbitrary — each step is what makes the next one
possible:

1. **`validity` before the server.** A query's `condition_range` is a map from
   quantity to interval; the entry side has to be the same shape or there is
   nothing to compare. `validity_conditions` is prose and **prose cannot be
   matched.** Fill `validity` on every entry that has a real condition; the
   prose stays, for people. Where they disagree, `validity` wins (P3).
2. **Decompose `kb/staging/`.** One entry per claim that **can be wrong on its
   own** — a control channel that one re-cabling falsifies is an entry by
   itself; things that go wrong together are one entry. Everything from there is
   capped at E3 (§10.3 rule 1) and carries a `source_ref` that names the device
   document, not the prior project. Until an item is decomposed it stays in
   `staging/` and cannot be cited as `kb:` — a `kb:` citation has to resolve to
   a graded entry.
3. **The MCP server** (`src/mcp_server.py`), read-only, four tools, `caller_id`
   isolation. See below.
4. **`gaps`.** This is the output that matters. Without it the store answers
   questions; with it the store says what it does not know.
5. **Conflicts, external search, distillation.** Distillation is not
   summarising — it is breaking a source into claims.
6. **`kb/exports/`.** Publish snapshots; do not write into anyone else's
   directory.
7. **Empty `plan.md` §12.** The lab temperature sitting there becomes an entry
   with a source and a grade, or a `gap` saying what is still undetermined —
   whether 20 °C is a setpoint or a measurement decides between E2 and E5, and
   nobody has said which.

## The four tools, and why four

| tool | returns |
|---|---|
| `kb_query(caller_id, kb_version, observable, condition_range, purpose)` | entries + `gaps` + `grade_summary` |
| `kb_get(caller_id, kb_version, entry_id)` | one entry verbatim |
| `kb_conflicts(caller_id, kb_version, topic)` | pairs that disagree |
| `kb_group(caller_id, kb_version, symbol)` | one dimensionless group: formula, inputs, validity |

`kb_group` exists because a group is looked up **by symbol**, wants a formula
rather than a value, and takes no condition range. Folding it into `kb_query`
would make the return shape depend on the arguments, and every caller would grow
a branch. Check 36 needs the same lookup.

**No write tools.** External search, distillation, and writing or retiring
entries happen inside this session only. A subagent that can write to the KB
turns an undistilled value into the authority immediately.

**Four rules on the server** (`plan.md` §4.3.1): isolate by `caller_id`, never by
`qid`; the same `(query, kb_version)` always gives the same answer; the id is
issued by the fan-out executor, never chosen by the caller; global statistics
never touch the answer. **Determinism includes ordering** — sort by grade, then
the rank inside E3 (`peer_reviewed → textbook → vendor_spec → preprint`), then
`entry_id`. That sort is the only place the citation preference actually runs.

**Matching says whether it covers, never what to do about it.** Full overlap is
`full`; a partial intersection comes back as `partial` with the uncovered part
named; a quantity the query did not mention comes back `unconstrained` rather
than assumed satisfied. Do not clip, interpolate, extrapolate or average — that
judgement belongs to the caller and gets recorded in their plan.

## Gaps

A gap records what was asked and **where it was looked for**. A gap with an empty
`searched` is not a gap: not-looked-for and not-there are different claims.
`nearest` keeps "nothing like it exists" separate from "it exists at another
temperature". The four `kind` values exist because the next action differs:

| kind | next action |
|---|---|
| `absent` | search outside; if still nothing, ask a person |
| `condition_mismatch` | find literature at other conditions, or let the caller record an extrapolation as an assumption |
| `inaccessible` | ask a person. **Do not work around an access restriction** — record inaccessible as inaccessible |
| `unqualified_source` | enter nothing. Leave the trail in `searched` so the next person does not walk it again |

Callers keep gaps in their cards (`kb_gaps`), and an estimate made while this
server was reachable has to name the gap it stands on (check 39).

## Rules for adding an entry

1. **One claim per file.** A file holding two claims cannot be superseded or
   refuted independently.
2. **`validity_conditions` is required, `validity` is what gets matched.** A
   claim without conditions is not reusable — the next question will apply it
   where it does not hold.
3. **The grade comes from the source kind, not from confidence.** E3 covers
   peer-reviewed work, textbooks, vendor specs and preprints; the sub-rank goes
   in `grade_tag`.
4. **General search results are not entries.** Blogs, forums, summary pages and
   model output may point at a real source; only the real source is entered. If
   the trail ends, nothing is entered and the gap says `unqualified_source`.
5. **E6 never enters.** A value a model produced belongs in conversation,
   labelled.
6. **Conflicts are kept, not merged.** Both entries stay, each naming the other
   in `conflict_with`, with the difference in conditions written down.
7. **Nothing is deleted.** A superseded entry stays and the new one points back
   with `supersedes`.
8. **E1 and E2 arrive only through result cards.** A measurement this system
   made comes in as a result card from an execution agent, and only this session
   turns it into an entry. Nothing else is a path for E1.

## What this agent does not do

Decide experiment or simulation conditions. Interpolate, extrapolate or average
values. Call another agent first — it is pull-only (P7). Bypass a paywall or
access restriction. Touch `envelope/safety.*`: "this laser's maximum output is
X" is knowledge and belongs here; "we do not exceed Y" is policy, belongs to a
person, and is not knowledge (§4.3.2).

## Session boundary

This session writes **only inside `librarian_agent/`**. `contracts/` and
`plan.md` are read here and written by the design session (§6.2).
`.claude/settings.json` denies the rest — **but only when this session's working
directory is this directory.** A librarian session started at the repository
root has no boundary at all; that is how five sessions overwrote each other on
2026-09-17.

Snapshots go out by publishing, never by writing across the boundary: put them
in `kb/exports/snapshot_<agent>.json` and let each agent copy into its own
`envelope/`. `kb/` is the one directory other sessions may read, and they may
only read it.

## The prior repositories

`plan.md` §10.2 opens exactly one row for this milestone: **comparing the two KB
structures** in the old `librarian-agent`, structure only, and only now that our
entry schema and `kb_query` arguments are fixed. Read our design first, then
compare differences — reading first means inheriting a structure instead of
choosing one.

Numbers cross only as graded entries (§10.3): capped at **E3**, sourced to the
device document rather than to the old repository, never taken from prose, and
**never for safety limits.** The M1 row — hardware control paths and device
specs — is not open; that is the microscope's turn, which is second.

## Commands

```bash
python3 librarian_agent/src/kb_index.py          # rebuild kb/index.json
python3 librarian_agent/src/kb_index.py --check  # fail if it is stale
python3 contracts/validate.py                    # entries are schema-checked here too
```

`kb_version` is a content hash over every entry. Cards pin it, so siblings in one
fan-out read the same knowledge and a question rerun at the same version gives
the same constraints. **Pin it for the whole fan-out and do not add entries
mid-flight** — siblings seeing different KBs breaks determinism, and the
difference is itself a channel between them.
