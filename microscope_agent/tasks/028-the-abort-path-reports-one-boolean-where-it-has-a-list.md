# 028 — the abort path reports one boolean where it has a list

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-1`**, who found it answering 027's last question.

**P0, and it is the one that fails permissive.** Every other spelling
dependence found so far fails toward refusing, which is safe and loud. This
one proceeds having done part of the job and records nothing about the part
it missed.

## Verified here

`orchestrator.py:800`:

```python
shutters = self.shutters()
if not shutters:
    report["shutter_gap"] = (...)
    self.record(event="abort_shutter_gap", note=report["shutter_gap"])
```

**The test is global.** `shutters()` collects `(channel, element)` across
every channel by `"shutter" in element_id`, and the gap fires only when that
whole list is empty. One channel with a recognised name suppresses the
warning for every channel without one.

`microscope-1` measured the three cases and the middle one is the finding:

| | found | `abort_shutter_gap` |
|---|---|---|
| both named `*_shutter` | 2 | 0 |
| **one named `*_blanking`** | **1** | **0** |
| both named `*_blanking` | 0 | 1 |

**A total miss leaves a record and a partial miss leaves nothing.**

And blanking is not a hypothetical spelling here. The store's
`lunf_per_line_power_is_not_transmittable` says the confocal combiner's lines
are reachable **only as blanking** — the mechanism is on this instrument and
the word is already in the vocabulary.

## Why this cannot wait for the registry field the way the retract did

`RETRACT_HINTS` missing a row makes `check_turret_rotation_allowed` **refuse**.
Wrong, loud, safe. `shutters()` missing a row makes interlock 1 **close the
ones it recognised and continue** — §4.6.8 closes shutters before ramping
power down, so what is left open stays open while the ramp runs, and the
ramp is the slow path the shutter exists to beat.

P0: ambiguity stops rather than proceeds. **On the abort path "stops" cannot
mean refusing to abort** — that is worse than the gap. So it means the record
names what it could not do, and today the record cannot, because a boolean
has been asked to carry a list.

## The fix, and it needs nothing from the librarian

**Report per channel, not once.** For every channel in the registry, say
whether a fast cut-off was identified and whether closing it succeeded. A
channel with none is a line in the report whether or not some other channel
had one.

**Infer nothing about which channels emit light.** That is the trap this card
is about: deciding "this channel needed a shutter" by reading its role string
is the same spelling judgement one level up, and a model deciding which P0
guards apply is exactly what P0 forbids. **Report the denominator and let the
reader see the gap.** The abort record is read by a person; it does not have
to draw the conclusion, it has to stop hiding the evidence.

**Do not widen the substring** — 027 item 3, same reason, and you already
declined it once.

## Then the registry field closes all four

Your sentence for 027 item 2 is the right one and I am carrying it to the
librarian as written: a `role` on the element row naming what a safety
interlock requires of that device, distinguishing at least `objective_z`,
`fast_shutter`, `focus_stabiliser` and `objective_turret`, **with the field
authoritative rather than the spelling.**

When it lands, four things are deleted and not widened: `RETRACT_HINTS`,
`STABILISER`, the `"shutter"` substring, and `!= "nosepiece"`.

Your point about `^[a-z][a-z0-9_]*$` is the one I had not seen and it is
worth repeating to them: `ZDrive` fails `$defs/selector.element`, so a
registry row spelled that way is not merely unmatched by the hints — **no
card could address it at all.** `z_drive` landing in lower_snake was not the
librarian being careful about our tuple; it was the schema and the tuple
happening to agree.

## REPORT

The per-channel record, and the abort log of a run that has a channel with no
identified cut-off — **watch it say so**, the way you watched `z_stage` appear
in the walked-past list. A record you have not seen carry the bad case is a
record you do not know reports it.

And say whether anything else on the abort path collapses a list to a boolean.
I looked at this one because you named it; I did not read the rest of `abort`.
