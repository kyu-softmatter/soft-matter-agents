# 046 — the day's findings for the store: microscope-20260924-5

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-5`.** The person asked, as the day's last request, that
everything the sessions established today be saved properly to the store
before the architecture session closes. This is your part. It has one card
per microscope session.

## What I already know you established

A starting point, not the list. List everything, including what I have
missed:

- this seat has no card from me before this one, so I do not know what
  you established today. **List whatever you did establish.** If it was
  nothing, do not write an empty file (the schema needs at least one
  item): tell me so in one line instead

## What to do

**List everything you established today** in one file,
**`microscope_agent/findings/microscope-20260924-5-20260924.json`**, in the shape
`contracts/schemas/findings.schema.json` gives (`9fc1645`). One item per
fact. Each item says:

- **the fact**, in words, as it would be entered
- **how it was established**, in words
- **its kind**, which decides the source it must carry:
  - `self_report`: what a device said about itself, read back in a run.
    Give the `run_id` and the `event_index` in that run log's `events[]`
  - `document_fact`: read from a named document. Give its path
  - `person_statement`: said by the person. Give **where it is recorded**:
    a commit, a file and field, or a run log event. **A statement recorded
    nowhere is not a finding**; say so to me instead
  - `prior_project_ruling`: from `C:\agentic_microscope`, with the path and
    the ruling (transfer, downgrade or discard)
  - `observable_value`: a value of an observable in
    `contracts/observables.json`, such as a bleaching rate or a brightness.
    **List it so it is not lost, and mark it `for_store: false`.** It waits
    for the plan that cites its run (`plan.md` 11-21, `20a688b`)

**Say what is unmeasured as well as what is measured.** A value marked
unmeasured in a run log is a finding: it tells the next session not to look
for it.

**Nothing here is graded by you.** The librarian reads the file, checks each
source, and enters what passes. Check 85 now lets a store entry cite a
preparatory run for a self-report, and never for an observable's value
(`26f06df`).

## Deliver it

Commit the file, then **tell the librarian its path and commit**, and tell
me. `librarian-20260924-2` is taking the lists; `librarian-20260924-1` has
open work to commit first. **The file is the delivery. The message only
points at it.**

## Constraints

- no hardware; this card is records only
- commit with `git commit -- <paths>` after `git diff HEAD -- <paths>`,
  naming the new file. Hooks are not installed; say so. Run
  `PYTHONUTF8=1 python contracts/validate.py` and read the tree line

**Re-read this card immediately before committing.**
