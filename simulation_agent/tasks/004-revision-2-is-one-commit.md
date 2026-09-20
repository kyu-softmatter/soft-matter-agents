# 004 — revision 2, and it is one commit

Written by `manager-simulation`. You read this; you do not edit it (§6.2-2).

**Startable when `003` is done** — the issuer has to emit `:v2:` before a
revision 2 fan-out runs, or the new cards carry the wrong ids from birth.

Four separate things have collected on revision 2. They are one piece of work,
not four, because **one pin blocks all of them and one revision bump releases
all of them.** Doing them separately means the same pin argument four times and
four revisions of a question nobody has run.

| | |
|---|---|
| A | `bead_diameter` 2 → 5 µm, and everything the arithmetic drags with it |
| B | the target stated inline instead of by reference into `numbers[]` |
| C | the librarian re-run — `kb_refs`, `kb_gaps`, `degraded` empty (§9.1) |
| D | `caller_id` at `:v2:`, which falls out of `003` |

## Before you start: confirm the pin is still what it was

```bash
python3 -c "
import sys,json; sys.path.insert(0,'contracts')
from validate import card_sha
h = json.load(open('bridge/threads/thr-tracer-diffusivity-001/r1_hashes.json'))
c = json.load(open(h['source']['path']))
print('ledger rev', h['source']['revision'], '| card rev', c['revision'],
      '| hash matches', card_sha(c) == h['source']['sha256'])"
```

A delivered round pins the plan at revision 1 by hash, and §5.3.1 generalised
that on 2026-09-19: **a recorded hash pins a card and it does not matter who
recorded it** — a person signing an approval or the bridge delivering a round.
Editing in place moves `card_sha` and fails check 8 in `manager-bridge`'s tree,
where nobody can fix it. The exit is the next revision, which is this card.

## A. The diameter, and the source kind changes with it

Six cards carry `bead_diameter`: `goal.json`, the plan, `synthesis.json`, and
axes **a1, a3, a4**. Counted, not taken on trust — do the same before you edit.

**2 µm → 5 µm.** The product is identified: Abvigen `AFR-0500-COOH`, found by
the person on the vendor's page, and `manager-microscope` confirmed the same
product key in `agentic-microscope`'s `data/particles.yaml` **on disk** — a file
written at the time, so it is a second trace and not the same memory twice.

**The grade stays E5 and the source kind does not.** Two seats disagreed here
and this is the reading to follow, with the reason so you can overrule it if it
is wrong:

- **`assumed:<rationale_id>` claims nothing about this setup** — it is a
  placeholder put there to keep going. That is what 2 µm was, and `a_sample`
  says so in as many words: *"No bead lot exists to quote."*
- **`operator_recall:` is a claim about the world.** 5 µm now has a vendor
  catalogue and a contemporaneous file behind it. It is weakly supported, not
  unsupported.

Both grade E5, and §5.3 was widened on 2026-09-19 to say why that is not a
contradiction: they are E5 because the evidence is thin, not because they are
the same kind of thing. **A blank is not disagreeing.** So `operator_recall:`,
E5 unchanged, and `manager-bridge`'s advice to keep `assumed:` was written
before that distinction landed.

**Leave the lot gap open.** `spec:AFR-0500-COOH` is E3 *about that product*;
that our bottle **is** that product is still E5, because the person read a
catalogue and not a label. Reading the label lifts that layer on its own.

Two consequences to work out rather than guess: `a_sample`'s statement is
written around there being no value, and a number sourced `operator_recall:`
is not an assumption's placeholder — so that assumption probably goes and the
lot becomes a `kb_gaps` entry. And **`a_sample`'s falsifier fires on a
condition that has not happened**: it says *"a bead lot specification replaces
this with an E3 value and every interval resting on it moves."* The intervals
are moving and no lot arrived. Say what you conclude from that; it is the more
interesting half.

## B. What the diameter drags, and what it quietly does not

`τ_d = d²/D` and `D = k_BT/(3πηd)`, so **τ goes as d³** — the factor of ~15.6
that §11-13 recorded as a discrepancy between two sides arrives here as
arithmetic. **Do not hand-edit any of it and do not take a number from this
card or from a peer's message.** These are `computed:` with formulas; re-run
the fan-out and let the modules derive them. Check 17 recomputes, so a
hand-edited value is caught — but being caught is not the same as being right.

**Six numbers are forced by a declared formula**, by transitive closure over
`inputs`: `diffusivity`, `tau_d`, `integration_timestep_max`,
`box_length_min_dilution`, `box_length_min_images`, and the diameter itself.

**The rest is the part worth your attention, because nothing forces it.**

`max_lag_time` is `assumed:a_window`, 2 s, **no formula and no inputs**, so the
dependency graph does not move it. Its statement is *"The fit window sits below
the diffusive time so the free regime is what is sampled."* At τ_d ≈ 20 s, 2 s
was a tenth of it. At the new τ_d it is well under one per cent. **The sentence
stays true and the choice stops making sense** — you would sample only the
shortest lags and throw the run away. A statement that goes stale while its
number sits still is not caught by anything here.

Everything under it inherits that: `save_interval_max` and
`total_simulated_time_min` both derive from `max_lag_time`.
`total_simulated_time_point` and `integration_timestep_point` are S4's chosen
operating point, picked against intervals that have now moved.
`a_cost_reference` estimates cost *"over a window of a few seconds"*, which the
window no longer is.

So A4 genuinely re-decides the window, S4 genuinely re-picks the point, and A5
re-costs it. That is a fan-out, not a patch — which is what makes this a
revision.

## C. The target, and your plan does not have one

`5e3ea6a` is the worked example; copy its shape. But **check your own tree
first, because it differs from the example and from what you may be told**:
`plan_simulation_sim-20260917-001.json` has **no `targets` key at all**.
Verified. It does not migrate a target — it **acquires** one.

- `goal.json` states the decision inline: `{metric, kind, value, unit}`,
  required exactly those four, `additionalProperties: false`. No source, no
  grade — a target is a decision, and inline is what makes a grade
  inexpressible rather than merely absent (§2.1 rule 9).
- the **plan** gains its own copy, pinned to what the goal decided rather than
  referencing it, because a `plan_approval` fixes the plan and not the goal.
  Check 52 compares the two.
- `target_decade_resolution` leaves `numbers[]` and `a_target` goes with it —
  see `002` for why that was never an assumption.
- the criterion `within_target_decade` uses `target: <metric>` in place of
  `number:`. Check 6 resolves either, since `d5af7b1`.

The person confirmed one decade (`ad38bb0`, §11-14 closed), so **the value does
not move.** What moves is that it stops being this agent's E5 assumption.

## D. Mechanics, and the corner nobody has been round

- **`v2_` prefix**, not `r2_` — rounds and revisions were one sentence until
  `a6ab72b` split them (§7.1 rule 3, P9).
- **Revision 1 stays on disk.** Revision 2 **may cite it as a record and may
  not take it as input** — feeding its numbers into a fresh calculation
  inherits the reason the re-run exists.
- `cards.refuse_overwrite` stops rather than replacing a card of another
  revision. Let it.
- **Re-pin `kb_version`** to the store as of this run. That is the whole point
  of revision 2 being the librarian run: it asks with the vocabulary that store
  actually has, and revision 1 keeps its own pin as the record of what was read
  the first time.
- **`plan_simulation_sim-20260917-001.md` must be regenerated** (P3). Check 9
  compares its numbers against the JSON and both the diameter and the target
  move under it. **`manager-bridge` never exercised this path** — their example
  plan had no markdown. If regeneration surprises you, that is the last
  unexamined corner of this migration and they asked to hear about it.

## When it lands

Tell this seat, and tell `manager-bridge` — they will re-run check 8 against
the new revision from their side. The rev-1 ledger then reads *"the source
moved on; the round is not comparable"*, which is the documented escape and is
why any of this works. **The delivered round in `microscope_agent/inbox/` then
describes a superseded plan.** That is `manager-bridge`'s to settle, they know,
and it does not gate your commit.
