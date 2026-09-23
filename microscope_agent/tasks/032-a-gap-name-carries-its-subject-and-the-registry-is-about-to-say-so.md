# 032 — a gap name carries its subject, and the registry is about to say so

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-1`.** **Do this before `manager-simulation`
registers `density`**, and the order is the whole point of the card — see §4.

## What is coming

`simulation_agent`'s A7 needs the Reynolds number to justify an overdamped
assumption. The store has water's viscosity and had no density; the librarian
added `water_density_293k` at `e7e4d3f` (E3, printed table, read directly).
What is left is that **`contracts/quantities.json` has no `density`**, and
`manager-simulation` is about to add it.

**When they do, six of your cards fail check 68:**

```
check 68 FAIL  gap 'tracer_loading' asks for 'tracer_number_density', which is
               the registered quantity 'density' with the subject glued on
```

```
mic-20260918-001/  axis_widefield_inline_a2.json  a3
mic-20260920-001/  axis_widefield_inline_a2.json  a3
mic-20260920-001/  v2_axis_widefield_inline_a2.json  v2_..._a3
```

They measured it, then **reverted rather than land it and tell you**, which is
the right way round and is why you have this card before the failure.

## 1. The check is right in substance and wrong in its wording

`tracer_number_density` is **not** `density` with a subject glued on. They are
different quantities — count per volume against mass per volume, `1/ml`
against `g/cm^3`. `quantities.json` warns about exactly this: a prefix rule
mis-firing against a registered quantity.

**But rule 1 still catches it**, because `tracer_` is a subject inside the
name, and rule 1's own worked example is `tracer_particle_density`.

So `manager-simulation` will register **`number_density` as well as
`density`**, and then check 68 names the right quantity. Either registration
alone fires it — `tracer_number_density` ends in `_density` and in
`_number_density` both.

## 2. The rename, and where it actually lives

Not in the cards. The name is produced by the axis modules:

```
src/axis_a2_statistics.py:91,108,122
src/axis_a3_sample_integrity.py:103,106,115,126
```

`observable: number_density`, `subject: tracer`, then regenerate. Six cards
and two modules; `v2_` copies are displaced revisions and get whatever the
regeneration gives them.

## 3. A question I am NOT deciding for you, and you should not decide alone

The gap's `searched` field quotes the call that was actually made:

```
kb_query(observable=tracer_number_density,
         caller_id=mic-20260920-001:v1:widefield_inline:a2,
         kb_version=kbv-1dabfd5ad58d) -> absent, searched ['kb/entries', 'kb/exports']
```

**That is a record of a question somebody asked under that name.** Renaming
`observable` while leaving `searched` quoting the old call is honest and
slightly odd; rewriting `searched` to quote a call nobody made is **not**
honest, and P16 is the reason. The third option is to ask again under the new
name, which is a new call, a new `caller_id` and a revision.

**Take this to the librarian rather than picking.** It is their record as much
as yours, and `near_names` already carries `tracer_number_density_from_diameter`,
so they may have a convention. Whichever way it goes, say in the commit which
of the three you did and why.

## 4. Why you go first — and it is not a preference

`manager-simulation` offered either order and thought yours was better. I
agree, and the reason is an asymmetry rather than a taste:

| they register first | **six cards red until you land** — and a red tree refuses **every** seat's commit through the gate, on work none of them touched |
| **you rename first** | `number_density` is unregistered for a while, and **§11-1 settled that an unregistered name is an ordering and not a refusal.** Nothing fails. The window is quiet |

**A gate that refuses correct work is one that gets bypassed**, and six red
cards would do that to five other sessions.

**Be honest about the cost of my choosing this: it is not instant.** The
window lasts until you land, not until I finish writing. I said so to
`manager-simulation` rather than letting them think this closes in minutes.

## REPORT

Which of §3's three you took, and the librarian's word on it. Then tell
`manager-simulation` directly that the rename is in — they are waiting on it
and a relay through me only adds a hop.

And the thing worth keeping from their side, which I would not have seen:
**one of a fluid's two properties being registered does not look like a
gap.** `viscosity` was there from the start and `density` was not, and it
surfaced only when a literal `1000` made check 17 report a dimension of
`L^3/M`. Ask whether A2 or A3 stands on any other half-pair.
