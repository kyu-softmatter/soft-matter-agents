# 064 — two microscope seats, split by file

Written by `manager-microscope-20261003-1` on the person's instruction of
2026-10-07 in this seat's window: split the remaining microscope cards
between the two execution sessions, by file, so the two never edit the same
file at once. You read this; you do not edit it.

**Two seats, both owning `microscope_agent/`** in `contracts/seats.json`.
The registry narrows neither, so **this card is what divides them**. A path
not listed for you below is not yours. If you need it, report up and do not
take it.

| | `microscope-20261003-1` (Microscope 1) | `microscope-20261007-1` (Microscope 2) |
|---|---|---|
| cards | **063** to its end; any code fix any card needs | **060's preparation** ("Before Tuesday") |
| writes | `src/**`, `tests/**`, `rulings.jsonl`, `failures.jsonl`, `findings/card063-*` | `questions/mic-20261008-*/` (new folders it creates), `findings/microscope-20261007-1-*.json` |
| scratch | `D:/sma-scratch/063` | `D:/sma-scratch/060` |
| never writes | the other seat's paths, `envelope/`, `approvals/`, `inbox/` | `src/**`, `tests/**`, `rulings.jsonl`, `failures.jsonl`, any `questions/` folder it did not create, `envelope/`, `approvals/`, `inbox/` |

**Code belongs to one seat only.** All of `src/` and `tests/` is Microscope
1's while this split stands, including card 060's needs. If Microscope 2
finds that a bench plan needs a code change, a gate that refuses wrongly or a
field the operator does not read, it **reports up with the file and line**.
Microscope 2 does not edit the file. Manager-microscope then cards the fix to
Microscope 1. This is what keeps the two from editing one file at once.

## Microscope 2: card 060, "Before Tuesday"

Read card 060 in full. Its "Before Tuesday" section is yours:

1. **The plan cards the visit needs**, one question folder each, under
   `questions/mic-20261008-<n>/`:
   - the five focus-search refusals: no limit, the wrong lens, focus hold on,
     not approved, and a target above the max;
   - the abort run, with both lamps on, stopped from outside.
2. **Dry-run each one on mock** in `D:/sma-scratch/060`, through the scratch
   root, which only mock may use (card 063 Part A built it). Record each
   result in your findings file, with the run's scratch path and the sha256 of
   its `events.jsonl`.
3. **Bring the outputs to the person on Tuesday.** The person approves each
   plan on the day. Write no approval yourself.

**A focus-search plan in the tree fails check 88 until the person writes the
focus limits**, and the commit hooks are installed, so committing one now is
refused. That refusal is correct. So:

- the dry runs read the plans from `D:/sma-scratch/060`, alongside a
  scratch envelope with TEST limits, each marked as a TEST value;
- **commit only the plans check 88 passes**, which is none of the focus plans
  until Tuesday. Keep the focus plans in scratch and copy them into
  `questions/` on the day, after the person has written the limits;
- the **no-limit** refusal is shown on Tuesday *before* any limit exists,
  so its plan can never pass check 88. It is run from scratch and **cited
  in findings by its sha256**, and it is never committed. Say so in its
  findings line.

The abort-run plan is not a focus search, and check 88 does not apply to it.
Commit it when the validator passes.

## Microscope 1: card 063, unchanged

Card 063 is yours as before. Its findings file is yours alone,
`findings/card063-mock-session-20261007.json`. Microscope 2's findings go to
its own file, so the two are never one file.

## While Microscope 1 is closed (added 2026-10-12)

**The session holding `microscope-20261003-1` is not running.** On the
person's decision in manager-microscope's window on 2026-10-12, **`src/**`,
`tests/**`, `rulings.jsonl` and `failures.jsonl` pass to
`microscope-20261007-1` for as long as that holds**, so card 068 can be built.
When the handover was made, `src/` and `tests/` held no uncommitted change,
so nothing of Microscope 1's is left in them to take or to discard.

**It reverts before Microscope 1 takes any card again.** Manager-microscope
says so in writing first, and from then on the table above holds as written.
One seat writes code at a time: two never do.

## The dino-autofocus seats (added 2026-10-15)

`microscope-office-20261015-1` and `microscope-office-20261015-2` write
`microscope_agent/autofocus/` under cards 071 to 074, which divide that tree
between them. Neither writes `src/`, `tests/` or `questions/`. The one
exception is card 071's single ruling line in `rulings.jsonl`, which that
card grants and no other.

## Card 069, Microscope 3 (added 2026-10-17)

Added by `manager-microscope-office-20261016-1`. Card 069 is assigned to
`microscope-office-20261015-1` (Microscope 3), on the person's word of
2026-10-17, quoted in that card. It is a code card, and one seat writes code
at a time, so **for card 069 alone, `src/**`, `tests/**` and
`failures.jsonl` pass to `microscope-office-20261015-1`**. This lifts, for
that card only, the line above that says neither dino seat writes `src/`
or `tests/`. `rulings.jsonl` stays where it was: card 069 crosses nothing
from another repository.

**While it holds them, `microscope-20261007-1` makes no edit under `src/` or
`tests/` in the working copy.** Work in a scratch copy is allowed. At the
handover, `src/` and `tests/` held no uncommitted change, so nothing of
Microscope 2's is left in them to take or to discard.

**They come back when card 069 lands**: Microscope 3 reports its commits to
manager-microscope, and manager-microscope says here, in writing, that the
code is Microscope 2's again. From then on "While Microscope 1 is closed"
holds as written. Card 076 waits on card 069, as it says, and its seat is
whoever holds the code after the return. That is `microscope-20261007-1`
unless the person says otherwise.

## The envelope snapshot (added 2026-10-12)

**Microscope 2, or whichever registered Office microscope seat is running
when the person copies it (widened 2026-10-15), may commit
`envelope/snapshot.json`, and only that file in `envelope/`, and only after
the person has copied it by hand.** It never
writes or edits the file: the deny rules forbid that, and the copy is the
person's. Before committing, check that:

- the file is byte-identical to the committed
  `librarian_agent/kb/exports/snapshot_microscope_agent.json`;
- check 26 and check 61 pass.

The commit message names the export commit it was copied from. On
2026-10-12 the person copied `kbv-b1253d99047e`, from `f458f86`.
`envelope/safety.json` stays the person's, and neither seat commits it.

## The bench seat, Tuesday 2026-10-13 (added 2026-10-13)

Added by `manager-microscope-20261013-1` on the person's yes in this seat's
window on 2026-10-13. **On Tuesday the person seated `microscope-20261013-1`
for the bench** (sidebar "Microscope for bench"), as a third session. It
closes neither seat above, and the rows above stand.

| | `microscope-20261013-1` (bench) |
|---|---|
| cards | **060's visit, on the day** |
| writes | `runs/<run_id>/` through `operator.py --write` and live view; `findings/microscope-20261013-1-20261013.json`; `questions/mic-20261013-<n>/`, new folders it creates, holding the revision-2 copies of plans 002, 003 and 004 from `D:/sma-scratch/060` |
| never writes | `src/**`, `tests/**`, `tasks/`, `CLAUDE.md`, `rulings.jsonl`, `failures.jsonl`, `envelope/`, `approvals/`, `inbox/`, and any `questions/` folder or `findings/` file it did not create |

**Code stays with `microscope-20261007-1`**, under "While Microscope 1 is
closed" above. A code problem the bench finds goes up with the file and line,
the same way: the bench seat reports and does not edit. The first one is
card 069.

**`src/` is frozen while the bench is on the instrument.** Every seat runs
`src/` from the one shared working copy, so an uncommitted edit by
`microscope-20261007-1` would be the code that drives the instrument. From
the bench seat's first hardware run until it says in its findings file that
the visit's instrument work is done, `microscope-20261007-1` makes **no edit
under `src/` or `tests/` in the working copy**. Work in a scratch copy is
allowed; nothing from it enters the tree until the freeze ends. Card 068's
code and card 069 wait behind this.

**Today's refusals are watched, not read** (the person's choice,
2026-10-13). No Micro-Manager configuration is loaded on any hardware path
(card 069), so Z cannot be read around a refusal. Each refusal the bench
shows is recorded with the person watching the focus display, and its
findings line says **"Z not read: no configuration loaded"**. The
encoder-equal check moves to the next visit. **A refusal recorded this way
does not count as shown with Z equal**, and the findings file must not say
it does.

## Both

- **Name your own paths when committing**: `git diff HEAD -- <paths>`, then
  `git commit -F <file> -- <paths>`. Never `-A`, never `--amend`. Your seat
  identity comes from `contracts/seats.json`, through `GIT_COMMITTER_NAME` and
  `GIT_COMMITTER_EMAIL`.
- **The commit hooks are installed.** A commit runs the validator over the
  tree it would create, so it takes longer. Another seat holding
  `.git/index.lock` is a commit in progress: wait for it, and never remove
  it.
- **On Tuesday the person says which seat holds the bench**, as card 060
  says. This card does not decide that.

## What comes back

Each seat reports to manager-microscope:

- **Microscope 2:** each plan's id; each dry run's result and stream sha256;
  the commit of the abort plan; and every place it needed code it does not
  hold, with the file and line.
- **Microscope 1:** card 063's own report.
