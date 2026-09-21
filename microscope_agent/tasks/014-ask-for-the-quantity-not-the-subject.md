# 014 — A6 asked for a subject, and the answer it did not get was the lucky one

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-1`.** Added 2026-09-20 after this card was dispatched to two seats at once and they overwrote each other on one path. The seat is read off the commits, not chosen: 9205f1d took A6 to revision 4. **If you are not that seat, do not take this card** -- report up instead.

Small card, one gap, and **check 68 is held until it lands.** Read all of it
before the rename, because the rename alone makes the card worse.

## What is wrong

`axis_widefield_inline_a6.json` records this gap:

```
gap_id     immersion_refractive_index_absent
observable immersion_refractive_index
kind       absent
near_names ["refractive_index"]
```

`quantities.json` **rule 1**: a name states the quantity and never its
subject. The quantity is `refractive_index`; **immersion is the subject.**
The librarian found it.

**The server had already told you.** `near_names: ["refractive_index"]` is
sitting in that gap. The correction was on disk and nothing acted on it.

Rule 1 wrote this recurrence into itself, which is why it is worth the card
rather than a quiet edit:

> when check 44 refused the subject field on those entries the claim did not
> disappear, **it moved into the name where nothing checks it. A name that
> asserts its own subject is a subject nothing can refuse.**

Nothing did check it. That is check 68, assigned to this seat, **written and
held out of the tree because it fails on this one card** and on nothing else
in the repository — measured, 37 gap names, one hit.

## Do not just rename it

**Asking by the right name returns eight entries at E3, and every one is
polystyrene.** That is the **bead material**, not the immersion medium.

So the shape of this defect is the opposite of the usual one: **the wrong
name produced the safer outcome.** `absent` made this axis abstain. The
registered name would have handed it eight numbers, produced an
`axial_range` computed from a bead's refractive index, and **reddened
nothing.** Rule 1 being broken is what stopped that.

**Therefore the eight must not enter the card.** Not into `numbers[]`, not
as a `kb_ref` backing `axial_range`, not as an estimate with a falsifier.
A bead is not an immersion medium and no grade makes it one.

## What to write instead

Re-query by the registered name, at a fresh `caller_id` — the card is at
`revision 3` and `mic-20260918-001:v3:widefield_inline:a6`, so this is **v4**
and a revision bump. Then record **what actually came back**, which is not
`absent`:

- the quantity is `refractive_index`
- the subject is the immersion medium, and it belongs in the gap's subject
  position, not glued to the name
- the kind is whatever the server returns for *entries exist and none is the
  subject asked for* — a mismatch, not an absence. **Say which.** An
  absence and a wrong-subject match send the next reader to do different
  things, and this gap has already sent one reader the wrong way
- `near_names` already carried the answer; note that it did

**The abstention on `depth_of_field` stands.** Its input is still missing —
what changed is that the record of *why* becomes true.

## Then it opens, and not by your hand

The librarian has **task 024** open: immersion refractive indices as
literature entries, tagged `identifiers.immersion` so `kb_query("water")`
returns the water objectives and water's index together. That join is what
this axis actually needs, and it needs no schema change.

Three things were settled about those entries and are worth knowing before
you re-query against them:

- **air** is close to a handbook constant
- **water** follows `water_viscosity_293k`'s precedent — CRC-type citation,
  E3. **Do not copy that entry's `numbers[].source` line**: it cites
  `kb:water_viscosity_293k`, itself, which is the repository's only
  self-citation and is now check 69 against the librarian
- **oil is not a universal constant.** It is a specific product's spec. If
  the bottle on the bench is not identified, the honest entry is a gap
  pointing at the person — a gap where what is missing is not a number but a
  **source**. The bead lot was that shape too and is no longer a live
  comparison: the label was examined on 2026-09-19 and states no product
  identity, so that one is a **confirmed negative** rather than a pending
  item. **Take the shape and not the ending** — the oil may still be
  identifiable by someone reading the bottle, and the bead lot is settled as
  unidentifiable. A gap waiting on a look and a gap whose look already
  happened are different states

So expect A6 to close on air and water objectives and **stay open on oil**,
and expect that to be correct rather than incomplete.

**And one warning that is already on record from the librarian:** the index
is wavelength-dependent, and the wavelength is A6's *other* missing input
(the red path's filter designation, which is with the person). Pinning the
index at measured wavelengths may move this gap from `absent` to
`condition_mismatch` rather than closing it. **A better answer is not the
same as a solved one — say which one you got.**

## Rulings

Nothing crosses from `agentic-microscope` for this. If you reach for
anything, rule it first and report it up in the same sentence; I write
`tasks/NNN-rulings.md`.

## Done when

```bash
python3 contracts/validate.py
```

`0 failed`, and read the tree the run names with it. Tell me when it lands
and I put check 68 in — it is written and waiting, and it exists to stop the
next one of these, not this one.
