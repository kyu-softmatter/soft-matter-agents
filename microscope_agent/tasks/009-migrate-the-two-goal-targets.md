# 009 — carry the target inline in both goal cards

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**After 006.** `microscope-1`'s. Two files, two single-card moves.

## Why now

§5.3.1 settled that a target is carried inline with neither source nor grade,
the way a ceiling in `envelope/safety.json` is. The person confirmed one
decade (`ad38bb0`), so **no value moves in either card**. What moves is that a
person's goal stops being filed as `assumed:a_target` at E5 — an assumption
nobody made.

**This is the cheapest moment and it will not stay cheap.** Check 12 makes a
plan's carried number cite the goal's, and check 52 compares a plan's carried
target against the goal's. So the moment either question has a plan, the goal
and the plan move in **one commit** or the tree refuses the half-move. Both of
these goals are alone today.

## Scope — two cards, verified and re-verify

| | |
|---|---|
| `questions/mic-20260918-001/goal.json` | no plan, no result, no approval names it |
| `questions/mic-20260919-001/goal.json` | same; carries `from_round: thr-tracer-diffusivity-001:r1` |

I checked both today. **Check again when you start** — the rule is *migrate if
unpinned; if an approval pins it, leave it and report*, not *migrate*.
Forward-only is what architecture settled: moving a field changes the hash and
an approval that pinned the old shape is voided. That is not discipline, it is
what a hash is.

## Follow the worked example, not this description

**`5e3ea6a`** migrated `contracts/examples/goal_compare.json`. Read that diff
and copy its shape. In outline:

- `targets[]` states the decision inline — `{metric, kind, value, unit, note}`
  — with **no `source` and no `grade`**;
- `target_decade_resolution` leaves `numbers[]`;
- the `a_target` assumption goes with it. It existed to justify an assumed
  value, and a decision needs no justification.

**Make sure `5e3ea6a` is in your tree first.** `$defs/criterion` kept `number`
in `required` until then, so a criterion pointing at a target failed check 1.
That does not bite a goal card and will the moment a plan appears under one.

## The falsifier becomes a note, and the two cards differ

Keep the falsifier's content in the target's `note`, rephrased as **the
condition under which the decision was too loose — a decision to revisit, not
a claim that was wrong.**

**Write each from its own card.** The two `a_target` statements are not the
same:

- `mic-20260918-001` — *two candidate regimes inside one decade.* Worth
  keeping; it is the sharper of the two.
- `mic-20260919-001` — *the simulated and measured values landing inside one
  decade of each other.* That one is about the bridge comparison the round
  opened, not about this instrument.

Do not write one note twice.

## What does **not** migrate

**`snr_target` stays exactly as it is** — `assumed:a_snr`, E5, with its
assumption. It is on `mic-20260918-001` and it is not in `targets[]`, and the
distinction is the whole of §5.3.1: the line runs between **the person's goal
and everything else**, not between numbers that look target-ish and numbers
that do not. The person stated one decade. Nobody has stated a signal-to-noise
ratio of five — A1 needs one and assumed it, and its falsifier is still live.

Sweeping it along because the name ends in `_target` would file an open
assumption as a settled decision, which is the error this migration exists to
undo, running backwards.

## What holds

No value changes. If a number changes, stop.

The pin does not move.

`configs.json` names `goal-mic-20260918-001-r6`. A goal revision bumps that;
carry it so the two do not disagree.

## Done when

Both goal cards carry their target inline with no source and no grade,
`target_decade_resolution` is out of `numbers[]` in both, `a_target` is gone
from both and `a_snr` is untouched, `python3 contracts/validate.py` ends
`0 failed`, and one commit as `seat:microscope-1`.

Then one sentence up: whether either card's approval state changed between my
check and yours.

## Not this task

**Card 008**, the deliberate re-pin. **A5**, `microscope-3`'s. **The frozen
example group**, which stays on the old shape until its approval does — it is
not yours and not mine.
