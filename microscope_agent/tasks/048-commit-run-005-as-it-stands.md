# 048 — commit run -005 as it stands

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-6`.** The person asked, through
architecture, that `microscope_agent/runs/run-20260924-005/` be committed
tonight. **You are committing another seat's run, not making one.**
`microscope-20260924-2` ran it: the person's approved sine on piezo X,
through the dispatcher. It has closed for the day, and it correctly
declined a relayed pointer. **Its log already names it as the run's author.**
You are the committer and not the author, and the commit message says so.

## What makes it committable now

Its approval `appr-mic-20260924-002-r1` was corrected and committed by the
person at `e389d4d`: `approved_at` 2026-09-24T20:08:51Z, 33 s before the
run began. The validator passes with the run present.

## Do exactly this, and nothing else

1. **Verify every file against the hashes `-2` recorded**, before
   committing. They are also the out-of-tree copy at
   `D:\soft-matter-agents-frames\run-20260924-005\`:

   | file | sha256 begins |
   |---|---|
   | `deviations.json` | `a5338d955b09046e` |
   | `log.json` | `715b4f9cb175603a` |
   | `position_vs_time.svg` | `631b1ae7aff64f8b` |
   | `report.md` | `f5e832fe122b1b2e` |

   **If any differs, stop and report up. Commit nothing.**
2. **Change nothing** in the folder. No edit, no reformat, no added file
3. **Commit only those four paths**, named individually (the folder is
   untracked, so `git add` them first), after `git diff HEAD --` on them
4. **The commit message says**: the run was made by
   `microscope-20260924-2` and its log says so; this seat committed it at
   the person's request relayed through architecture, on card 048; the four
   hashes match the recorded ones; and hooks are not installed. Take your
   email from `contracts/seats.json`
5. run `python contracts/validate.py` before and after, and quote the tree
   line

**Not on this card**: the run's result card, carrying the tracking error and
the settled read-backs. That is the run's own finding, `-2`'s to write, and
a later card's. So is anything else about the run.

**Re-read this card immediately before committing.**
