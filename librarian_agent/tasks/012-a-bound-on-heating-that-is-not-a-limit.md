# 012 — an observed bound on sample heating, which is not a safety limit

status: open · issued 2026-09-19 by manager-librarian · **read the hazard first**

## GOAL

The person, 2026-09-19, in the manager session:

> Below roughly 20% IR laser power, I have not really noticed a temperature
> change in the sample. Above that, yes.

This speaks to the one gap that is still open on the local side of the
temperature chain: A3's `optical_heating`, `observable: sample_heating_rate`,
`absent` at `kbv-49feb73662b7`. §011 established that holding the room
isolates the local term rather than removing it. This is an observation of
that term.

## THE HAZARD — read this before filing anything

**This must not become a safety threshold, and it reads exactly like one.**
"Stay under 20%" is a sentence someone will lift out of a KB entry and treat
as a limit. It is not one:

- P0 and §2.1 rule 7: safety decisions are made by **deterministic code** from
  limits **a person wrote down**, never inferred, and never by a model.
  `envelope/safety.json` is the person's file and no seat may write it.
- §10.3 rule 4 keeps safety limits out of transfer entirely, for the same
  reason: a limit is a commitment, and an observation is not.
- **The grade forbids it by itself.** An E5 value may not parameterise an
  irreversible action without a person's individual approval (§5.3, §6.1), and
  raising laser power at a sample is irreversible for the sample.

So the entry states **what was observed**, and says in its own words that it
is not a limit and may not be used as one. If that sentence feels redundant
while writing it, that is the sentence doing its job.

## What the statement is, precisely

1. **It is a recollection, not a reading.** `operator_recall:` → **E5**. Not
   `operator_read:` — nothing was read off an instrument. This is the
   distinction §5.3 draws deliberately, and the temptation to round it up is
   the reason the distinction exists.
2. **It is a detection limit, not a zero.** "Not really noticed" means the
   effect was below what the operator could perceive **by means that are not
   recorded**. The bound is real; its resolution is unknown. An entry that
   says "no heating below 20%" states something stronger than what was said,
   and the difference is exactly the resolution nobody wrote down.
3. **"20%" is a dial setting, not a power.** Percent of an unstated maximum is
   not a measured quantity, and it does not become one by being written in
   `numbers[]`. Compare §5.3's nominal rule and 009's ruling: a nominal
   designation is a string. To become a power it needs the laser's rated
   output and the transmission of the objective in use — and the person has
   already ruled on that second one: **visible-range objective curves stop
   well short of 1064 nm, use the end of the graph, do not extrapolate.**

## A prerequisite you will hit immediately

**There is no IR laser in the store.** No entry, and `1064` appears only in
objective transmission context. So there is no `device` id to subject this to,
and the `light_engines` key of the device table does not hold rows for it.

Do not invent one to make the subject resolve — that is the inversion you
correctly refused for the objectives in 009. Either the laser gets a device
row first, by the route any device fact takes, or this entry is subjected to
what genuinely exists and says what it could not name. Report which.

## TASK

1. File the observation at E5, with the three qualifications above carried in
   the entry rather than in this file.
2. Say in the entry that it is not a limit and may not be used as one.
3. **The gap does not close.** `sample_heating_rate` still has no measured
   value; what exists now is a coarse bound on where an operator stopped
   noticing. If anything, this sharpens what to measure. Leave it open and say
   so, or the next reader sees a gap closed by an E5 recollection.

## REPORT

The entry sha, the subject you gave it, and what you could not subject it to.

Then: whether filing it changed A3's gap at all. **I expect not, and a
no-change is the result worth writing down** — an E5 bound and an absent
measurement are different things, and a gap that appears satisfied by the
first is the false-absence failure in reverse.
