# 039 — screening reads the person's exclusions

Written by `manager-microscope-20260924-1`. You read this; you do not edit it
(§6.2-2).

**Assigned to `microscope-20260924-1`, after card 038.** Finish the
five-minute run and release the bench first. This card touches no hardware.

## Why

On `mic-20260924-001` the person had declared the light path widefield by
hand, and card 033 kept the laser combiner off and the spinning-disk unit
refused. S3.0 reads capabilities only, so it kept `confocal` in, the cap was
met at three, the preference was never read, and **seven caller_ids were
issued for a path that will not run.** Prose in `constraint_notes` does not
cut, and should not.

**Architecture decided the remedy (`plan.md` at `cbfa1ae`)**, and the schema
has landed:

- `goal.schema.json` has **`declared_exclusions`** (`2863f7d`): each item
  carries `configuration`, `by`, `on` and `why`, and all four are required
- `screening.schema.json` has **`excluded_by_person`** (`d9cf1c6`), in the
  same shape, **kept apart from `rejected`**

## What `src/screening.py` must do

1. **An excluded configuration is taken out before screening.** It is not
   screened, does not count against the cap, and **gets no caller_id**
2. **It is recorded under `excluded_by_person`, with the person's reason
   copied, and never under `rejected`.** `rejected` is a finding about what
   the instrument cannot do. An exclusion is the person's decision about this
   goal and says nothing about merits. Merging the two would count the
   person's choices as the screen's refusals
3. **An exclusion naming a configuration the capabilities table does not
   hold refuses the screening**, the way a preference naming one does. A
   card excluding something that does not exist is a card to fix
4. **A preference naming an excluded configuration is refused**, recorded
   under `preference_refused` with the reason that the person excluded it,
   and screening stops at that entry, as it does for a rejected one
5. **An exclusion is not evidence**: it raises and lowers no grade, and S4
   may not cite it. `preference_is_not_evidence` already says this for
   preferences; say it for exclusions too, in the same place
6. **A later goal inherits none of it.** Read it from the goal being
   screened, and from nowhere else

**Each of 1 to 4 gets a test watched failing**: switch the behaviour off, see
the test fail, switch it back. Tests go in `microscope_agent/tests/`, which
`ALLOWED_PATHS` now admits.

## Do not re-screen `mic-20260924-001` on this card

That question's r1 goal and its 21 issued ids are `microscope-20260924-2`'s,
committed or about to be. Its confocal seven were ruled issued-and-unrun.
**Whether its goal gains `declared_exclusions` in a later revision is card
034's seat's call**, at its S4 re-pin, not this card's.

## And one comment in `src/devices/micromanager.py`, added the same day

**Beside `SOFTWARE_MAY_COMMAND`, write that `LUNF-Blanking` and `NIDAQHub`
must never be added to it.** Found by `microscope-20260924-3` on card 036:
those two devices are the laser combiner's TTL blanking lines, and **lifting
either opens a second route to the confocal lines that skips every gate**
in `src/devices/lunf.py`. Those gates are the person's limit, the approved
list, the bench, and the light path read back at the moment of enabling
(`plan.md` 2.1 rule 11). `lunf.py`'s docstring says so, but the next person
to edit the allow-list reads the allow-list. The comment changes no
behaviour; do it only when the bench is released and no run imports the
file. The same check applies: `git diff HEAD --` first.

## Constraints

- `src/screening.py` only, plus tests. It is imported by no session script,
  but check before editing: `grep -rn "import screening\|from screening"`
- commit with `git commit -- <paths>` after `git diff HEAD -- <paths>`,
  naming new files individually. Hooks are not installed; say so. Run
  `PYTHONUTF8=1 python contracts/validate.py` and read the tree line

**Re-read this card immediately before committing.**
