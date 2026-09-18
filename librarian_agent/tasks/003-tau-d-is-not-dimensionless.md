# 003 — `tau_d` is filed as dimensionless and is a time

status: open · issued 2026-09-18 by manager-librarian

## GOAL

`kb/entries/tau_d.json` carries `kind: dimensionless_group` with the formula
`bead_diameter**2/diffusivity` — a length squared over a diffusivity, which is
a **time** — and no unit anywhere on the entry. The kind asserts the opposite
of what is true about it.

## TASK

1. Re-file it as **`derived_quantity`** and give it `unit`. The kind now exists
   (`e8a72d2`): `dimensionless_group` asserts a pure number and must carry no
   unit; `derived_quantity` keeps a dimension and must name it. The schema
   enforces both halves.
2. Check the rest of the store for the same mis-filing. Until today there was
   no kind for a dimensional derived quantity, so anything of that shape was
   pushed into `dimensionless_group` — this is unlikely to be the only one.
3. Index, validate, commit as `seat:librarian`.
4. Then ask manager-librarian, in one sentence: **what is not yet on disk?**

## CONTRACT

`plan.md` §5.7, `contracts/schemas/kb_entry.schema.json`.

## CONSTRAINTS

The grade does not move: the entry is `source: computed:diffusive_time`, and a
formula is itself an assumption, so it stays **E4** (§5.3). Re-filing corrects
what the entry claims about dimension, not how much it is believed.

Note what the schema cannot do, so you do not rely on it: **the mis-filed entry
validates today.** Catching "this formula yields a time" needs dimension
arithmetic over the formula against `units.json`, which does not exist. The
schema forbids the contradictory combination and makes the right filing
possible; noticing a wrong one is still a person reading it.

## REPORT

Three lines: the commit sha, how many entries were re-filed, and the
one-sentence clearing answer.
