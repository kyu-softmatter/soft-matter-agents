# 053 — take round 1 of the bleach-recovery thread into card 051's question

Written by `manager-microscope-kyuhwan-macbook-20260930-2`. You read this; you
do not edit it.

**Assigned to `microscope-kyuhwan-macbook-20260930-2`**, the seat working card
051. If you are not that seat, take nothing from this card and report up.

## What arrived

The bridge delivered `microscope_agent/inbox/thr-bleach-recovery-diffusivity-001/`
round 1 at `e47ad03`. It carries the simulation's result for the bleach
recovery: `result-sim-20260930-401-run-20260930-401-n300-dt-f12-b30`, revision
2. The person handed it over directly, and the bridge reports answerability
`yes` on `widefield_inline`. This is the card 051 has been waiting on. The
payload is what the simulation side owed: recovery time against spot radius,
the scatter of D against beads in the disc, and the bias from finite bleach
and frame interval.

## What to do

1. **Take the round into `mic-20260930-001`** as its next goal revision, with
   `from_round: "thr-bleach-recovery-diffusivity-001:r1"`. Do not open a new
   question. That field is how the bridge learns the round was taken.
2. **Read the payload in `r1_ask_experiment.json`**, not in the Markdown and
   not in any message. Your `CLAUDE.md` has a section on what an envelope
   says. In short:
   - Copy no payload number into the goal card.
   - Cite each of the simulation's design choices (spot radii, bleach and
     frame fractions, box, bead count) **as the round's, with its
     revision**.
   - Read the payload's own statement of its limits and its `degraded` list,
     and carry both into what you conclude.
3. **Re-run the axes that the awaited values move.** These are the ones that
   named recovery time, bead count or the finite-bleach bias as awaited.
   This revision has its own reason, so **pin whatever store version is
   current** when you start.
4. **Compare, and do not adopt.** Where the simulation's assumed ranges and
   your design's ranges differ, say so plainly. Units and values came back
   `no_counterpart` only because no plan of yours has crossed yet, and that
   is not an agreement.
5. **S5 still refuses** until the person answers the four open items: the
   objective, the bleach dose and limits, the bead concentration, lot and
   dilution, and approval of the bare-bead run. Say which of those the
   round's numbers change, if any.

## Boundaries

As card 051: design only, open no device, and never write or reword
`envelope/safety.json`. Read `inbox/` and never write it. Nothing is deleted
there.

Commit and push when a piece is done, as card 051 says. Run the validator to
`0 failed`. Then `git diff HEAD -- <paths>`, then `git commit -F <file> --
<paths>` under your seat, naming new files individually. Confirm with `git log
-1`, fetch and merge if origin moved, and push. Never force, never amend.

## What comes back

To this seat, at most 8 lines:

- the goal revision and commit;
- which axes moved and how;
- where the two sides' ranges disagree;
- what, if anything, changes for the person's four decisions.

To the person, the same in plain words.

**Re-read this card immediately before committing.**
