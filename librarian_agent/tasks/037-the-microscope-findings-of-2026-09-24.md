# 037 — the microscope findings of 2026-09-24, into the store

status: **open** · issued 2026-09-24 by manager-librarian, at
librarian-20260924-2's request so the intake survives a clear. It records
work already under way, not work begun here · **assigned to
librarian-20260924-2** · **reported done before this file was first
committed**: `8a00537` (14 entries, 6 sources, 2 gaps) and `a14ec7a` (25
entries, 5 sources, 6 gaps), store at `kbv-a1bb4a5acf25`. Both commits exist
and the librarian tree was clean when this line was written; per-file
accounting is in their messages. Not yet verified item by item by this seat.

## GOAL

The person asked for the day's findings from the microscope seats to be
harvested into the store (plan.md §7, `findings/`; the person's instruction
reached this seat through librarian-20260924-2 and is recorded here as
relayed, not heard). The two librarian sessions split the files between
themselves:

| findings file | commit | taken by |
|---|---|---|
| `microscope_agent/findings/microscope-20260924-1-20260924.json` | not yet delivered | librarian-20260924-2 |
| `microscope_agent/findings/microscope-20260924-2-20260924.json` | `a0fda99` | librarian-20260924-2 |
| `microscope_agent/findings/microscope-20260924-3-20260924.json` | `a5e7647` | librarian-20260924-2 |
| `microscope_agent/findings/microscope-20260924-4-20260924.json` | on disk | **librarian-20260924-1**, by agreement between the two; outside this task |

## The rules this intake runs under, verified on disk at filing

- **What may be read.** §7's `findings/` line as widened at **`0e06fb2`**
  (architecture, minutes before this file): this folder, and **exactly the
  paths a committed findings item cites, at the commit that item names**, read
  with `git show <commit>:<path>`. Nothing else of `microscope_agent/`. An item
  whose source is not committed is not checkable and **is not entered**; a
  verbatim copy inside the findings file does not substitute.
  That line was "this folder and nothing else" at `f391010`. librarian-20260924-2
  found the gap and held 46 items on it, which was right. **Those 46 are now
  checkable under `0e06fb2` and are this task's to decide one at a time**, not
  in bulk (rule 10).
- **What may enter.** §11-21 condition 4 as narrowed at `20a688b`: it bars
  *measurements*, not what a device reports about itself. An observable's value
  in a findings file is always `for_store: false` and stays out.
- **The gate.** Check 85, which lists every entry citing a preparatory run
  (one with no plan). **This bullet first said such a self-report enters "not
  as a measurement this system made" and that only a result card is a path for
  E1. That was wrong**, and librarian-20260924-2 caught it: §11-21 as narrowed
  at `20a688b` enters a device's report of itself citing the run's log, with
  `run_id` and event, **"graded as an observation by this system"**. The seat
  followed `plan.md`, which outranks this file, and 22 entries cite
  run-20260924-002 or -004 as `measured:` at E1. That stands. What still
  cannot enter this way is a registered observable's value. This seat's
  `CLAUDE.md` rule 9 said the same wrong thing and is corrected in the same
  commit as this line.
- Prior-repository items go through §10.2.1 (transfer / downgrade / discard,
  slot and §10.3 rule named) and cap at E3; §10.3 rule 3 excludes timing and
  anything a safety limit stands on.

## State as reported by librarian-20260924-2 at filing (not re-counted here)

- **-3's file** (`a5e7647`): checked; 3 source records written; 11 entries
  drafted **outside the tree**, waiting for librarian-20260924-1's pending
  commit to land before any goes in.
- **-2's file** (`a0fda99`): 3 prior/vendor items drafted; 46 held on the read
  boundary (40 self-reports sourced to `runs/run-20260924-004/log.json`, 6
  person statements in that agent's `tasks/`, `envelope/`, `runs/`,
  `questions/`); 3 excluded as policy or session state; the prior timing item
  discarded under §10.3 rule 3.
- **-1's file**: not yet delivered.

**The drafts outside the tree are the P1 risk in this list.** They vanish
with a clear. Land them, or record them in `failures.jsonl` as pending, before
this session clears.

## CONSTRAINTS

- **Two librarian sessions are moving the store today** (this task and 036).
  Every entry moves `kb_version`. Agree one publish between you, at the end,
  and check the query log for in-flight pins first.
- Commit order: librarian-20260924-1's pending work first, as already agreed.
  Name files, never `librarian_agent/`. That tree holds the other session's
  uncommitted edits.
- A person statement found in the microscope tree is a `person_ruling` or
  `operator_*` source only if the file it sits in records it as the person's.
  A seat's paraphrase of the person is the seat's word.

## REPORT

Per findings file: entered / held / excluded / discarded, with the reason for
each non-entry; the commits; the publish. Then the one sentence: what is not
yet on disk.
