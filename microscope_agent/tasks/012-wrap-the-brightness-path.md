# 012 — the control column, and three channels wrapped

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

Specified in `plan.md` §4.6.6.1 (`4de4924`), which the person settled on
2026-09-20. **Read it rather than this card where the two differ** — this one
sequences the work and names what is yours; that one is the decision.

## Why this can start before the safety envelope

`tracer_brightness` needs the instrument to move, and `src/devices/` holds
only `manual.py` and `mock.py`. All **ten** channels in the registry have
`control: null` — I checked, it is not that some are filled.

§10.2's hardware-control-path row is open and its own wording sets the order:
**wrapping a control path needs no safety limit.** So this runs **in parallel**
with the person writing `envelope/safety.json`. What waits for that file is
the moment real hardware moves, and nothing before it.

## 1. Rulings first, and the drops you already owe

**Nothing crosses from `agentic-microscope` before it is ruled** — transfer,
downgrade or drop; a transfer names its A1–A7 slot and the §10.3 rule it
passed; an item that cannot name a slot is dropped (§10.2.1).

Write them to **`microscope_agent/rulings.jsonl`**, one line per item, each
with `by`. **The file does not exist yet — you create it.** It is yours, and
it sits beside `failures.jsonl` on purpose: the same idiom for a different
thing, what was abandoned against what was ruled.

**Start by recording the three drops you already made**, before any new work:
that project's orchestrator, its per-device GUI session management, and the
seven-parallel-gate package. You said they had no place to be written; now
they do. **The store's `drop` count is 0 and that is a fact about the missing
file, not about the work** — §9.3's second criterion counts exactly this, and
a zero for want of a place cannot be told from a zero for want of drops.

## 2. The `control` column, structure only

The row points at precisely three things: **how the driver is called, the
channel, and the read-back path.** Extract those.

**No numbers cross** (§10.3). A port, an address, a wavelength, a travel range
— none of them. If a control path cannot be described without a number, the
number is a separate item and it is almost certainly a drop.

## 3. Wrap three channels, and only three

```
widefield_source_a    excitation          full · read_back
camera_red            605-band collection full · read_back
stand_ti2e            objective, filter   full · read_back
```

**This is the brightness path and nothing else.** The scope was counted rather
than chosen, and it lands on §10.2.1's *one at a time* by itself: **no
read-back-less channel is on this path at all.** Wrapping all ten would
produce control paths nothing exercises, and untested code is a class this
repository has counted more than once.

Behind the existing interface — `preflight(channel)`, `apply(params)`,
`read()`, `abort()`, the four `mock.py` and `manual.py` already implement.
**Do not add a fifth function**; a device that does not fit the four is
telling you something about the device.

## 4. Mock round-trip before anything real

All four functions through `mock.py` first, end to end. Real hardware waits on
`envelope/safety.json`, which is the person's.

## The two channels you are not wrapping, and why the note matters

`laser_combiner` and `optical_tweezers` take commands and confirm nothing. The
person chose to automate them **with the blind spot recorded**, and §4.6.6.1
draws the boundary because that choice meets §2.1 rules 2 and 8 head-on:

- **Commands go out. Nothing treats that channel's state as verified.** The
  run record carries `verification: none` for it, and **a run with that field
  empty does not stand.**
- **No safety judgement rests on those channels' state** — rule 8 exactly.
  Permission comes from `envelope/`, a person's approval, or a deterministic
  check, and from nowhere else.
- **Irreversible actions still require a confirmed limit** (check 57). Being
  able to command the trap is not being able to confirm it is off.

**The residual risk is accepted, not resolved, and it is written that way.**
`optical_tweezers` is a laser and sits on P0's first line. The condition for
reversing this is the day a read-back path exists, and on that day §4.6.6.1 is
edited before anything else.

**None of that is this card's work** — it is here so that wrapping three
channels does not read as a step toward wrapping those two.

## What holds

`rulings.jsonl` is append-only and nothing is deleted from it (§7.1 rule 9).

`git diff -- <paths>` before committing. Naming a path is not naming a change.

**`src/axis_common.py` and `questions/` are not this task.** Another seat is
working the fan-out.

## Done when

`rulings.jsonl` exists and carries every item you considered — including the
three drops — each with `by`; the `control` column is filled for the three
channels and no others; a mock round-trip exercises all four functions; and
`python3 contracts/validate.py` ends `0 failed`.

Then one sentence up: how many items were ruled, and how many of those were
drops.

## Not this task

**`laser_combiner` and `optical_tweezers`.** **Real hardware**, until
`envelope/safety.json` exists. **The remaining seven channels' `control`
column** — they come one at a time, each when a measurement needs them.
