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

## Scope — three cards, eleven gaps

I read the check rather than the summary of it, and the scope is narrower than
it was described to me. **Check 49 skips any card whose `degraded` names the
librarian** — the same carve-out check 39 makes, for the same reason: a card
that never reached the service wrote its gaps by hand and no neighbourhood
search could stand behind one.

| card | `degraded` | `absent` gaps | |
|---|---|---|---|
| `axis_widefield_inline_a2.json` | `[]` | 4 | **re-run** |
| `axis_widefield_inline_a3.json` | `[]` | 4 | **re-run** |
| `axis_widefield_inline_a6.json` | `[]` | 3 | **re-run** |
| `axis_widefield_inline_a1.json` | `["librarian_agent"]` | 4 | carved out |
| `axis_widefield_inline_a7.json` | `["librarian_agent"]` | 3 | carved out |
| `goal.json` | `["librarian_agent"]` | 1 | carved out, and S3.0's anyway |

Eleven gaps, three cards. That is exactly what the check counts.

**Do not re-run a1 or a7 as part of this.** They are exempt only while they
declare the degraded path. Re-running them through the service removes the
carve-out and *adds* the obligation — worth doing eventually, because §9.1
wants served cards, but it is separate work and must not ride on this commit.

## Wait for the pixel size first

**Do not start yet.** A person has calibrated the sample-plane pixel size on
this instrument and the librarian is entering it now; it will be this
repository's first E2. As of this card there is no E2 in the store, so it has
not landed.

That value closes one of A6's three gaps outright — `sample_plane_pixel_size`,
the one that could not be closed by any sensor pitch because pitch and
sample-plane size are different facts. Re-running A6 before it lands means
running A6 twice. Wait, then do all three once.

Watch for it: `grep -rl '"grade": *"E2"' librarian_agent/kb/entries/` returns
nothing today.

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

The three cards carry `near_names` on all eleven `absent` gaps, any gap that
turned out not to be one is no longer a gap, `python3 contracts/validate.py`
ends `0 failed` with check 49 passing rather than PENDING, and **one commit**.

Then one sentence up: how many of the eleven survived as real absences.

## Not this task

**A1 and A7**, as above. **A4**, still blocked on the discrete-constraint
slot. **A5**, which is `microscope-3`'s and has not been written.
