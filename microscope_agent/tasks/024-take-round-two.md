# 024 — take round 2, and it being one revision behind does not matter

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**REASSIGNED to `microscope-5` on 2026-09-22.** Written for
`microscope-1`, who is now three cards deep in `023` and `025` — the safety
work in `src/` — and whose own report of what remains does not list this
one. `microscope-5` asked for a card and the person had told it to.

**It does not collide.** This card lives in
`questions/mic-20260919-001/`; `microscope-1` is in
`questions/mic-20260920-001/` and `src/`. Different question, different
files, and this is S2 work rather than S5, so `plan_card.py` is not touched
either.

**`microscope-1`: do not pick this up.** If you had already started, say so
and I will move it back — a card in two hands is the failure this line
exists to prevent, and it has happened twice.

Independent of card 023 in the same way: `023` is the one with a collision
in it, this one has no P0 item.

## 0. Re-copy the envelope first

It is **one publish behind** — `kbv-e8f4a5610aa6` against the store's
`kbv-30966d978fbe` — and this question has **not fanned out yet**, so a
fresh pin costs nothing and a stale one would be carried by all seven axes
when S3 eventually runs.

**It cannot disturb `mic-20260920-001`.** That fan-out is issued and its pin
is recorded in `configs.json` and in each card; an axis takes its pin as an
argument and `pin_kb_version()` is read only when S3.0 runs fresh. I got
this wrong on 2026-09-20 and fenced two seats off the envelope for no
reason — measured since, and the fence was unfounded.

**Committed bytes only.** Name the export's commit in your message; check 26
verifies the copy against it.

## The round is here and it is intact

```
microscope_agent/inbox/thr-tracer-diffusivity-001/r2_ask_experiment.json
round 2 · supersedes 1 · turn: microscope_agent
payload  plan-sim-20260917-001-r2, revision 2
check 8  PASS -- 5 bridge rounds carry their cards unchanged
```

**The 2 s window is gone from what you hold.** What it carries now:

| | | |
|---|---|---|
| `max_lag_time` | **30 s** | `assumed:a_window` E5 |
| `bead_diameter` | **5 µm** | `kb:tracer_diameter_measured` **E2** |
| `tau_d` | **300 s** | `computed:diffusive_time` E4 |

## It is already one revision behind, and I checked whether that matters

Check 74 reports it every run: the source card is now at **revision 3**, and
this round carries revision 2. **Do not stop on that.** I diffed the
delivered payload against `v3_plan_simulation_sim-20260917-001.json`:

```
19 numbers, 16 identical. The three that moved:
   integration_timestep_point     0.03 s  ->  0.3 s
   lag_to_record_ratio            0.1     ->  0.01
   total_simulated_time_point     300 s   ->  3000 s
```

**`max_lag_time` is 30 s in both. `bead_diameter` is 5 µm at E2 in both.
`tau_d` is 300 s in both.**

All three that moved are the **simulation's own operating point** — a
timestep, a save ratio, a total run length. **None of them crosses.** They
are how that side spends its compute; ours is an acquisition.

So this refines the rule from yesterday by one step. It was *numbers the
store backs repair themselves, design parameters do not.* The missing half
is **which design parameters cross at all**: `max_lag_time` is our record
length and crosses; `integration_timestep` is theirs and never will.
**Check the ones that cross, and let the rest move.**

## What to do

**Carry `from_round: thr-tracer-diffusivity-001:r2`.** That is the whole
mechanical requirement — check 74's PENDING disappears when a card in this
tree names r2. Whether that is a revision of `mic-20260919-001`'s goal or a
new question is **yours**; the round supersedes rather than replaces, so a
revision reads more honestly to me, but you hold the question.

**Do not copy the payload's numbers into the goal.** r1's goal carried none
and that is why the stale bead diameter never reached a card of ours — P3
working rather than luck. Query for what the store backs; **cite
`max_lag_time` as the round's, with its revision**, because nothing in the
store will ever contradict it.

**The envelope carries `degraded: ["librarian_agent"]`** — it was wrapped
while the store was unreachable. Anything standing on it inherits that
until a card queries and clears it. Query before you build on it.

## Do not delete the 2 s work

`manager-bridge` raised this and it is my own rule pointed back at me.
Whatever was designed against a 2 s window, **record which revision it was
built against rather than removing it.** The arithmetic was right; the
question moved. A seat finding deleted work looks for an error that was
never there.

## One thing the round says that is worth reading

`unit_consistency: consistent`, compared against **`goal-mic-20260919-001-r1`
— our own card.** The bridge used this side's goal as the counterpart, so
that verdict is about the two sides agreeing and not about the payload alone.

`value_comparison: no_counterpart` — **there is no result on our side to
put beside theirs.** That is honest and it is what round 3 would carry. It
is also the first concrete thing the pre-measurement unblocks: a diffusivity
this side measured.

## Done when

```bash
python3 contracts/validate.py
```

`0 failed`, and **read the tree the run names with it.** Check 74's PENDING
on `mic-20260919-001/goal.json` should be gone, and its PASS count up by
one. **Read that off the run.**

If you take it as a new question, say in the commit why a revision was
wrong — I would rather be corrected than have the reasoning lost.

**Re-read this card immediately before committing.**
