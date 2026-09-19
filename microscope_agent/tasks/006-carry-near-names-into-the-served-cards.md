# 006 — carry `near_names` into the three served cards

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

## What is about to happen

Check 49 (`33bcf34`) says `absent` may only be claimed after the name
neighbourhood was searched, and the server began emitting `near_names`
(`65d3170`). The check is a **latch**: while no gap carries the field it
reports PENDING, and **the first gap that carries it turns every bare one into
a FAIL**. Same shape as check 43 waiting on `source`.

So this is not work you can do one card at a time. One commit, or the tree
goes red for everyone.

## Scope — count it, do not read it

**This section has carried a number three times and been wrong three times.**
It said three cards and eleven gaps; a1 and a7 were re-run and it became five
and twenty-two; A4 landed and A6 grew and it became six and twenty-nine. The
number is not a fact about this task, it is a fact about the moment someone
last looked. So the card stops carrying one.

**The rule**: every `absent` gap on a card whose `degraded` does **not** name
the librarian. Check 49 skips the degraded ones — check 39's carve-out, since
a card that never reached the service wrote its gaps by hand and no
neighbourhood search can stand behind one.

**Count it at the moment you start:**

```bash
python3 contracts/validate.py 2>&1 | grep 'check 49'
```

The PENDING line states the number the check itself sees, which is the only
number that can be stale-proof — it is computed when you read it. Use that,
not a table.

**Two consequences that do not change with the count.** Every exposed card
goes in **one commit**, because check 49 is a latch and a partial migration
turns the rest red. And `a6` is `microscope-3`'s axis, so `microscope-1` runs
all of them here and the other seat stays off this card; its A6 work resumes
after.

**Do not re-run a card whose `degraded` names the librarian** to bring it into
scope. The exemption holds only while the card declares the degraded path, so
putting one through the service *adds* the obligation rather than discharging
it. `goal.json` is the remaining one and it is S3.0's anyway.

## This runs at the pin, and closes the latch only

An earlier revision of this card said the pixel size had landed, that it
closed A6's `sample_plane_pixel_size`, and that this card should therefore go
first. **The first clause is true of the store and false of this fan-out.**
Counted at the pin: `kbv-49feb73662b7` holds 25 entries and **no pixel entry
at all**. The twelve calibrated entries — six objectives by two zooms, twelve
entries and not twenty-four; that number was grade strings counted as
entries — arrived after it. Asked at the pin, `pixel_size` is still `absent`,
and that is not a wrong answer but the true one at that version.

**None of which blocks this card.** `near_names` works at the pin: asked
there, `numerical_aperture` returns `absent` with `near_names: ['na']` and
`pixel_size` returns `absent` with `near_names: []`, both stamped
`answered_from kbv-49feb73662b7`. So the whole body of this task — the
gaps, the ones that stop being gaps, a6's caller_id, one commit — runs
without the pin moving.

**Closing A6's pixel gap is a separate, deliberate re-pin and is card 008.**
Not chasing the store, which card 000 refused: a gap actually closes. But it
moves all five siblings together under check 33, and that cost belongs in its
own card rather than smuggled into this one.

## What the re-run should produce

**`near_names` is an answer, and an empty list is a different answer from a
missing key.** Carry what the service returns, both when it is populated and
when it is empty.

Two of these will stop being absences:

- `numerical_aperture` → the store calls it **`na`**, in the six `objective_*`
  entries. Your A6 was right to ask by the observable name; the answer now
  says so instead of saying nothing.
- `objective` → points at the seven objective entries.

And one stays honest: `pixel_size` returns `near_names: []` — searched, and
nothing near. That empty list is the evidence, not an omission.

If a gap that returns `near_names` turns out not to be a gap at all, **it
stops being a gap**. Do not keep `kind: absent` next to a `near_names` that
names the thing. That is the whole point of the check.

## What holds

The pin does not move: `kbv-49feb73662b7`, as everywhere in this fan-out.

`degraded` stays `[]` on all three and must stay honest — you will be making
real calls.

If check 1 refuses a gap the server produced, **report it; do not reshape the
card to fit the output.** The server's gap shape was wrong until `30bbf45`
and no card had yet copied one, so this is close to its first real exercise.

## Done when

Every exposed card carries `near_names` on every `absent` gap it holds, any gap that
turned out not to be one is no longer a gap, `python3 contracts/validate.py`
ends `0 failed` with check 49 passing rather than PENDING, and **one commit**.

Then one sentence up: how many of them survived as real absences.

## Not this task

**Re-pinning.** Card 008 does that, deliberately, for the pixel size.

**A4**, still blocked on the discrete-constraint slot. **A5**, which is
`microscope-3`'s.
