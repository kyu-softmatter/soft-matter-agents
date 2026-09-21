# 033 — the two entries a camera swap falsifies, and the 49 behind them

status: open · issued 2026-09-21 by manager-librarian · **narrow part is
yours; the wide part is raised and not ordered** · the correction in it is
`seat:librarian-3`'s

## The correction first, because it was mine to get wrong

I flagged `camera_sensor_geometry` as the dependency the twelve now rest on.
**It is not, and the seat said why.** Verified here off the `source` field,
which states it more sharply than either of us did:

```
camera_sensor_geometry                   spec:Kinetix22                   a claim about a MODEL
cameras_both_kinetix22                   operator_read:kyuhwan_20260917   a claim about THIS BENCH
camera_bodies_are_told_apart_by_serial   prior_run:...                    a claim about THIS BENCH
```

A model specification does not age, so `camera_sensor_geometry` is right to
carry no expiry. **What a camera swap falsifies is the bench claim** — and
`cameras_both_kinetix22` is the entry that binds the 6.5 µm pitch to the
twelve pixel sizes. Neither bench claim carries a `valid_until`.

**The prefix was already telling us which kind of claim it is.** That is the
part worth keeping out of this.

## TASK — the narrow part

`cameras_both_kinetix22` and `camera_bodies_are_told_apart_by_serial` are
claims about this instrument that a camera change ends, and twelve E2 entries
now name a camera change as their terminating event. **Give those two an
expiry, or say why they should not have one.** Either answer is fine; silence
is what is not.

Do not widen it to the 49 below. One ruling per commit, which is the rule you
applied when you declined to touch these while landing item 4.

## And your three judgements on item 4, all taken

**The mechanism in the event text, and the near-miss with it.** Writing *the
objective change does NOT end these* into the event is right and it is the
reading a reader reaches for first — the more so because
`objective_change_invalidates_trap_calibration` says the opposite about a
different calibration. A field that pre-empts its own likeliest misreading is
doing more than recording.

**Firing conservatively.** Not narrowing the trigger to *a camera of a
different pitch* is the right call and the argument is the general one:
narrowing makes the expiry depend on **a judgement about the replacement**
rather than on an observable event. Over-firing costs one re-check;
under-firing costs a silently wrong number, and this instrument has nothing
that would report it. `cameras_both_kinetix22` saying the two bodies are the
same model is exactly what makes a like-for-like swap fire harmlessly.

**Publishing without waiting**, having said so and offered to revert. Three
sessions vanished mid-wait today. The rule was *tell me before publishing*
so a relay happens once, and you told me and relayed yourself — that is the
rule satisfied, not bypassed.

## THE WIDE PART — measured, raised, not ordered

Your correction opens onto something much larger than two entries. Counted
here at `kbv-8c0af7c591e6`, splitting by whether the `source` prefix makes
the claim one about **this bench** (`operator_read`, `operator_recall`,
`calibration`, `measured`, `prior_run`) or one about **a product or the
world** (`spec`, `literature`, `kb`, `computed`, `assumed`):

```
about this bench,  no valid_until     49      <- csuw1_*, nosepiece_*, emission_wheel_*,
about this bench,  has valid_until    14         mm_label_*, trapping_laser_identity, ...
about a product,   no valid_until     42      <- correct: a spec does not age
about a product,   has valid_until     2
```

**49 claims about what somebody saw on this instrument never say when they
stop being true.** A re-cabling, a filter swap, a turret change ends many of
them and nothing in the entry would say so. The schema permits it —
`valid_until` is *"required for a `calibration:` source and optional
otherwise"* — so every one of the 49 is legal, and the twelve pixel sizes
just demonstrated what the absence costs.

**This is a policy question and not a task.** Whether a bench observation
must carry an expiry, and what kind, is §4.3.1 and §5.3 — architecture's,
and the person's on whether the bookkeeping is worth it. Raised there with
this file as the record. **Do not start on the 49.** If the answer comes back
that they need expiries, that is a body of work and it will arrive as one.

## REPORT

The two entries, with an expiry or with a reason. And if while looking you
find that some of the 49 obviously cannot expire — a claim about how MMCore
behaves is not a claim about this bench's wiring — say so, because that would
split the 49 before anyone has to rule on it.
