# 015 — A1 records two gaps it does not have

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

Found while counting what blocks an end-to-end run, which is the person's
immediate goal. **Two of A1's eight gaps are not gaps**, and one of them is
answered inside A1's own card.

## 1. `pixel_size_in_sample` — A1 is citing the answer it says is missing

```
kb_gaps:  pixel_size_in_sample | absent
kb_refs:  pixel_size_100x_zoom_1_5x, pixel_size_100x_zoom_1x,
          pixel_size_10x_zoom_1_5x,  pixel_size_10x_zoom_1x,
          pixel_size_20x_zoom_1_5x,  ... twelve of them
```

**Twelve sample-plane pixel sizes, measured on this instrument at E2, are in
this card's `kb_refs`** — and the same card records that it could not get
one. A6 used them to close its Nyquist bound at this same pin.

The cause is the same one the librarian found in A6 yesterday, in its other
direction. `quantities.json` rule 1: *a name states the quantity, and never
its subject **or its locus***. The registered quantity is `pixel_size`;
`in_sample` is the **locus**, which is what rule 1's own `ambient_temperature`
example is. A6 had a subject glued in front; this has a locus glued behind.

**Ask for `pixel_size`**, and carry the configuration as what selects the row
— the twelve entries are already keyed by objective and zoom, which is the
same keying `objective_zoom_pair` uses.

**This unblocks `motion_blur`**, whose other input is below.

## 2. `tracer_diffusivity_expected` — WITHDRAWN. I read the wrong tree

**This item was wrong and the seat holding the card proved it.** Everything
below the line was written from HEAD; the card is pinned to
`kbv-7c77fa74ee5a`, and **the entry is not there.** `03fe7a3` added it and
`03fe7a3` is not an ancestor of `a4e1449`, which is the commit the pin
resolves to. I checked that myself after being told: `git merge-base
--is-ancestor` says no.

The seat asked the service rather than the filesystem, at the card's own pin,
and got a refusal both ways -- `kb_group` on the symbol and on
`tracer_diffusivity`. The same fan-out asking the same name at
`kbv-bf4f559baf68` had coverage. **So the store has it and this pin does
not**, and `absent` was the honest answer all along.

**That makes it card 008's, not this one's** -- re-pinning the whole fan-out
-- and check 58 is what stops this card moving alone. Leave the gap as the
service returned it.

**This is the error this repository keeps naming, committed by the seat that
keeps naming it.** I read the store at HEAD and the card at its pin and did
not notice they were different trees. The instruction is to read the tree the
run names *with* the run, and I did not.

The text below is kept because the shape of the claim is still worth knowing
-- an entry that holds a derivation rather than a value does answer a
`kb_group` and not a value query -- but **it does not apply at this pin and
is not work for this card.**

---

### (withdrawn) the store has it, as a derivation

A1 and A2 both record it `absent`. The entry exists, and was committed on
2026-09-19 under a message that names them:

```
03fe7a3  019: a CV that computed as 200 per cent, and the diffusivity two axes wanted
```

**Asking for a value returns nothing because it holds none.** It is
`kind: derived_quantity`, `source: computed:stokes_einstein`, grade E4, with
`numbers: []`. The store is not saying *I do not have this*. It is saying
*this is computed, and here is what from*.

So `absent` is the wrong kind and the wrong next action. **Use `kb_group`**,
which returns a symbol's formula, inputs, unit and validity — that is the
tool for an entry shaped like this one, and neither axis called it.

**The inputs are already in this fan-out.** A7 carries `viscosity`
0.001 Pa·s from `kb:water_viscosity_293k` and a tracer diameter; temperature
is `lab_ambient_temperature`. Reading them from the **store** is not reading
a sibling's output, so §4.5.3 rule (b) is untouched — but take them from the
store yourself rather than from A7's card, because the second would breach it.

**Two cautions on the result.**

The diameter is the disputed number: `operator_recall:` 5 µm here against
`assumed:` 2 µm on the simulation side, and it enters as the cube. Use what
the store gives with its grade and **record the dispute**; do not settle it.

And the grade. §5.8 caps a computed value at `max(E4, worst input)`, and one
estimate in the chain makes the answer an order of magnitude (P15). A
diffusivity derived through a recalled diameter is **a decade, not a number**,
and the bounds resting on it inherit that. Say so in the card rather than
letting the precision arrive by arithmetic.

## What this does not fix, and do not overreach

**Six of A1's gaps are real** — `tracer_brightness`, `read_noise`,
`quantum_efficiency`, `background_rate`, `bleaching_rate`, `disk_period`.
Closing the two above does not produce an exposure time, so **`snr_floor`
still abstains and S5 still refuses `actions`.** That is correct; this card
buys two bounds and honest gap records, not a plan.

**And `tracer_brightness` cannot be asked for at all.** The person settled
it on 2026-09-19: for a new sample it depends on this dye, this lot, this
illumination and this camera together, so no store holds it. It closes by
**imaging the particles alone**, and that pre-measurement is a separate
question that is being scoped.

## Check 68 is waiting on item 1

`68` catches a gap name that is a registered quantity with a subject or a
locus glued on. Measured across the tree: **37 gap names, the suffix form is
now clean because A6 was fixed, and the prefix form has exactly one hit —
this card's.** No false positives either way.

It is implemented and held out of the tree until this lands, for the reason
check 58 was held: **a correct check that fails on a live defect gets the
defect fixed, not the check weakened.**

## Done when

```bash
python3 contracts/validate.py
python3 microscope_agent/src/synthesis.py --qid mic-20260918-001
```

`0 failed`, and read the tree the run names with it. S4's `unbounded` count
should fall, and `motion_blur` should leave the open list. **Read the count
off the run.** Tell me when it lands and check 68 goes in.

## Rulings

Nothing crosses from `agentic-microscope` for this. If you reach for
anything, rule it and report it up in the same sentence; I write
`tasks/NNN-rulings.md`.
