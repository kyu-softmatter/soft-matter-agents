# librarian_agent

The librarian owns every fact the other three agents use, and — this is the
part only it can do — **it records what it could not answer.**

That second half is not bookkeeping. When a plan states a diffusivity, the
number is worth what its evidence is worth, and the question "did anyone look
this up, or did someone estimate it?" has to be answerable months later by
someone reading the file. So an answer comes back in two halves: `kb_refs`, what the store
supplied, and `kb_gaps`, what was asked for and did not come back **together
with where it was looked for**. A gap with an empty `searched` is not a gap —
*nobody checked* and *checked and it is not there* are different claims, and
only one of them means go and find it.

The service answered for the first time on 2026-09-19. Most of those first
answers were gaps. That is not a poor start; it is the store telling callers
which of their questions it cannot yet stand behind, which is the thing
reading the files yourself can never tell you.

## Two layers, and they are not the same thing

`plan.md` §4.3.0 splits this directory in a way that is easy to miss, because
both halves are just files on disk:

- **The store** — `kb/`. Entries a person curated, one claim per file, each
  with the conditions it holds under. This has existed since M0. You can read
  it with `cat`.
- **The service over it** — `src/`. A read-only MCP server with four tools,
  gap detection, distillation, external search, snapshot publishing.

Seeing `kb/` full of files does not mean the service is running, and reading
those files is **not** the service answering (§0.3). The difference shows up
in `queries/log.jsonl`: a call through the service leaves a line there, and
opening the file by hand leaves nothing. That log lives **outside `kb/`** on
purpose — it is a record of who asked what, not knowledge, and mixing the two
would put the store's own traffic into the store's own content hash.

| | |
|---|---|
| `kb/entries/` | the citable claims |
| `kb/staging/` | tables that are the discovery surface, not the citable anchor |
| `kb/exports/` | snapshots published for each agent to copy into its `envelope/` |
| `queries/` | who asked what, and what came back |
| `src/` | the server, the index, the snapshot publisher |
| `tasks/` | work issued to this seat, one file per task |

## The four tools, and why exactly four

`kb_query` (an observable and a condition range), `kb_get` (one entry
verbatim), `kb_conflicts` (entries that disagree, both kept), `kb_group` (a
symbol's formula). There are no write tools: entering and retiring knowledge
happens in the librarian's own session, because a subagent that can write to
the store turns an undistilled value into the authority the moment it runs.

Matching says whether an entry **covers** the conditions asked about. It never
decides what to do about a shortfall — clipping, interpolating and
extrapolating are the caller's judgement and get recorded in the caller's plan,
where an auditor can see them. §4.3.1 has the rules.

## What works today, and what does not

Do not trust this section's tense. Run it:

```bash
python3 contracts/validate.py          # the repository, from the root
python3 librarian_agent/src/kb_index.py --check   # is the index stale?
```

Working: the store, the index, the four tools, gap detection, snapshot
publishing with the commit it was built from, and the query log. A caller with
an issued `caller_id` gets an answer pinned to the `kb_version` it named,
served from that version rather than from wherever the store has since moved.

Not yet: distillation and external search are the librarian session's own work
rather than anything automated, and nothing has been promoted from E3 to E1 by
re-measuring it here. The per-plan E5 cap is **undecided**, not satisfied —
choosing it needs plans that were made while gap detection was running, and
there have not been many yet (§11-2).

Counts of entries, checks or gaps are deliberately absent from this file. Three
such counts were written into `CLAUDE.md` and all three were wrong within a
day. Read them off a run.

## Where to look

| | |
|---|---|
| §4.3 | what this agent does and does not do |
| §4.3.0 | the store and the service, and why they are separate |
| §4.3.1 | the four tools, the four server rules, gap kinds |
| §4.3.2 | why knowledge lives in exactly one place (P14) |
| §5.3 | evidence grades, and why a grade is derived from its source |
| §12 | facts that are waiting for a KB to put them in |
| `CLAUDE.md` | the rules this seat works under, including how to add an entry |

Grades are the one thing worth knowing before reading any of it: a number
carries `{value, unit, source, grade}`, the grade **follows from the source
rather than being claimed**, and E6 — a value a model produced — may not enter
the store at all.
