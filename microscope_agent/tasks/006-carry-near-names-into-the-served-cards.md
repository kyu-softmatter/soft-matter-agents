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

## Scope — five cards, twenty-two gaps (revised 2026-09-19)

**This section said three cards and eleven gaps and is now wrong, in the way
it warned about.** Check 49 skips a card whose `degraded` names the librarian
— check 39's carve-out, because a card that never reached the service wrote
its gaps by hand. `a1` and `a7` were carved out on that ground, and the card
said re-running them through the service would remove the exemption and
*add* the obligation. They have since been re-run. Both now read
`degraded: []`, and `a1` has grown from four absent gaps to eight.

| card | `degraded` | `absent` gaps |
|---|---|---|
| `axis_widefield_inline_a1.json` | `[]` | 8 |
| `axis_widefield_inline_a2.json` | `[]` | 4 |
| `axis_widefield_inline_a3.json` | `[]` | 4 |
| `axis_widefield_inline_a6.json` | `[]` | 3 |
| `axis_widefield_inline_a7.json` | `[]` | 3 |
| `goal.json` | `["librarian_agent"]` | 1 — carved out, and S3.0's |

**`a6` is `microscope-3`'s axis and this card touches it.** One commit is
required by the latch, so the two seats cannot each take their own cards.
`microscope-1` runs all five, including `a6`, and `microscope-3` stays off
this one — its A6 work resumes after. It also carries the last v-less
`caller_id` in the fan-out, `mic-20260918-001:widefield_inline:a6`, which
moves to `:v1:` here by re-query, not by substitution (card 005's argument).

**Twenty-two gaps, five cards, still one commit.** Count it yourself before
you start rather than trusting this table: it has been wrong once already,
and the number moves whenever a card is re-run through the service.

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
twenty-two gaps, the gaps that stop being gaps, a6's caller_id, one commit —
runs without the pin moving.

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

All five cards carry `near_names` on all twenty-two `absent` gaps, any gap that
turned out not to be one is no longer a gap, `python3 contracts/validate.py`
ends `0 failed` with check 49 passing rather than PENDING, and **one commit**.

Then one sentence up: how many of the twenty-two survived as real absences.

## Not this task

**Re-pinning.** Card 008 does that, deliberately, for the pixel size.

**A4**, still blocked on the discrete-constraint slot. **A5**, which is
`microscope-3`'s.
