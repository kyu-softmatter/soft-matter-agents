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
| cards | **063** to its end; any code fix any card needs | **060's preparation** ("Before Monday") |
| writes | `src/**`, `tests/**`, `rulings.jsonl`, `failures.jsonl`, `findings/card063-*` | `questions/mic-20261008-*/` (new folders it creates), `findings/microscope-20261007-1-*.json` |
| scratch | `D:/sma-scratch/063` | `D:/sma-scratch/060` |
| never writes | the other seat's paths, `envelope/`, `approvals/`, `inbox/` | `src/**`, `tests/**`, `rulings.jsonl`, `failures.jsonl`, any `questions/` folder it did not create, `envelope/`, `approvals/`, `inbox/` |

**Code belongs to one seat only.** All of `src/` and `tests/` is Microscope
1's while this split stands, including card 060's needs. If Microscope 2
finds that a bench plan needs a code change, a gate that refuses wrongly or a
field the operator does not read, it **reports up with the file and line**.
Microscope 2 does not edit the file. Manager-microscope then cards the fix to
Microscope 1. This is what keeps the two from editing one file at once.

## Microscope 2: card 060, "Before Monday"

Read card 060 in full. Its "Before Monday" section is yours:

1. **The plan cards the visit needs**, one question folder each, under
   `questions/mic-20261008-<n>/`:
   - the five focus-search refusals: no limit, the wrong lens, focus hold on,
     not approved, and a target above the max;
   - the abort run, with both lamps on, stopped from outside.
2. **Dry-run each one on mock** in `D:/sma-scratch/060`, through the scratch
   root, which only mock may use (card 063 Part A built it). Record each
   result in your findings file, with the run's scratch path and the sha256 of
   its `events.jsonl`.
3. **Bring the outputs to the person on Monday.** The person approves each
   plan on the day. Write no approval yourself.

**A focus-search plan in the tree fails check 88 until the person writes the
focus limits**, and the commit hooks are installed, so committing one now is
refused. That refusal is correct. So:

- the dry runs read the plans from `D:/sma-scratch/060`, alongside a
  scratch envelope with TEST limits, each marked as a TEST value;
- **commit only the plans check 88 passes**, which is none of the focus plans
  until Monday. Keep the focus plans in scratch and copy them into
  `questions/` on the day, after the person has written the limits;
- the **no-limit** refusal is shown on Monday *before* any limit exists,
  so its plan can never pass check 88. It is run from scratch and **cited
  in findings by its sha256**, and it is never committed. Say so in its
  findings line.

The abort-run plan is not a focus search, and check 88 does not apply to it.
Commit it when the validator passes.

## Microscope 1: card 063, unchanged

Card 063 is yours as before. Its findings file is yours alone,
`findings/card063-mock-session-20261007.json`. Microscope 2's findings go to
its own file, so the two are never one file.

## Both

- **Name your own paths when committing**: `git diff HEAD -- <paths>`, then
  `git commit -F <file> -- <paths>`. Never `-A`, never `--amend`. Your seat
  identity comes from `contracts/seats.json`, through `GIT_COMMITTER_NAME` and
  `GIT_COMMITTER_EMAIL`.
- **The commit hooks are installed.** A commit runs the validator over the
  tree it would create, so it takes longer. Another seat holding
  `.git/index.lock` is a commit in progress: wait for it, and never remove
  it.
- **On Monday the person says which seat holds the bench**, as card 060
  says. This card does not decide that.

## What comes back

Each seat reports to manager-microscope:

- **Microscope 2:** each plan's id; each dry run's result and stream sha256;
  the commit of the abort plan; and every place it needed code it does not
  hold, with the file and line.
- **Microscope 1:** card 063's own report.
