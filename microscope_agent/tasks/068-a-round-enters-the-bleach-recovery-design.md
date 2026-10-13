# 068 — a round enters the bleach-recovery design: its method directly, its numbers through the store

Written by `manager-microscope-20261003-1`. You read this; you do not edit it.

**Assigned to `microscope-20261007-1`**, which holds `src/` and `tests/` while
Microscope 1 is closed (card 064, added 2026-10-12, on the person's decision).
It was first written for `microscope-20261003-1`, whose session is not
running. If you are not that seat, take nothing from this card and report up.
When it lands, the same seat re-runs card 053's axes.

## The rule, settled at `8c57691` (plan.md 11-26)

Round 1 of `thr-bleach-recovery-diffusivity-001` carries two things an axis
should use. `design_bleach_recovery.py` reads only the goal and the librarian,
so neither reaches an axis today.

- **A method choice enters directly.** "Average the curves, then fit" is the
  sending side's window on the experiment. The axis takes it **cited as the
  round's, with its revision**, from the goal's `from_round`
  (`thr-bleach-recovery-diffusivity-001:r1`). It is recorded as a **design
  input with no source kind and no grade**, the way a person's tie-break is
  recorded. It constrains the design and justifies nothing inside it.
- **A number about the world enters only through the store.** The minimum
  bead count in the bleached disc is a finding of the simulation's run. It
  reaches an axis only as `kb:<entry>`, after a query, once the librarian has
  entered it from the simulation's result card. **Until then the axis
  abstains on that input and names the remedy**: the result card is not yet
  entered, and the next action is the librarian's. **Never** take the number
  from the payload, and never estimate it.

## Build

1. **The goal's field exists now: `design_inputs`** (`831ad5c`). Each item is
   `{name, statement, from_round, round_revision}`, with no value and no unit.
   `v4_goal.json` holds the choice only in prose, so write `v5_goal.json` with
   the round's choice in `design_inputs`; its `from_round` must equal the
   goal's own. Never edit `v4`.
2. **The fit method shapes the axis that fits:** the one that turns recovery
   curves into a diffusivity. That axis copies the goal's item **exactly**,
   into the axis's own `design_inputs`. Check 74 refuses an axis design input
   that is in no goal of the question, item for item. There is **no `source`
   and no `grade`**.
3. **The bead-count floor:** query the librarian for it, as for any input.
   With no entry, the axis that bounds bead number (A2) **abstains on it**.
   Its reason names the remedy: *the simulation's result card for this round,
   entered by the librarian*. Nothing substitutes a number.
4. **Card 053's other waiting items stay waiting:** the objective, the bleach
   dose and limits, the bead concentration, lot and dilution, and the
   bare-bead run's approval. Nothing here decides one of them.

## Tests, mock first, each watched failing first

- with a goal carrying the round's fit method, the fitting axis records it as
  a design input citing `from_round` and the revision, with no source or
  grade;
- with no store entry for the bead-count floor, A2 abstains, naming the
  remedy, and carries no number from the payload;
- with a TEST store entry for it in scratch, A2 cites `kb:<entry>` and
  bounds on it;
- a goal without the round leaves the axes exactly as today.

## Boundaries

`microscope_agent/src/` and `microscope_agent/tests/`, plus
`questions/mic-20260930-001/v5_goal.json` if step 1 needs it. No other
question card. The hooks are installed: commit under your seat with
`git diff HEAD -- <paths>`, then `git commit -F <file> -- <paths>`, and push.
Never force, never amend.

## What comes back

To this seat, 5 lines at most: the commit,
the tests' failing and then passing output, and which goal field the round's
design choices were read from.
