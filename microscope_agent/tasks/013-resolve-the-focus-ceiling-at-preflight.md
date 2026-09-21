# 013 — the focus ceiling resolves, and a dispatch says who watched it

Written by `manager-microscope`. You read this; you do not edit it (§6.2-2).

**Assigned to `microscope-1`.** Added 2026-09-20 after this card was dispatched to two seats at once and they overwrote each other on one path. The seat is read off the commits, not chosen: 573d846 and 870032b. **If you are not that seat, do not take this card** -- report up instead.

Three pieces of `src/`, all in `orchestrator.py` and `operator.py`, all of
them now named by something on disk rather than by a plan for later. Nothing
here needs the prior project and nothing here moves hardware.

## What changed under you today

**`objective_clearance_min` is no longer a number.** The person rewrote it as
a `resolved_from` lookup on `working_distance`, keyed by the objective in use.
Before that it was **130 um** — which is the 100x oil working distance applied
to all six objectives, against a spread from 20 mm to 0.13 mm, a factor of
**150**. It pinned the 100x at exactly its focus and bound nothing at all for
the 4x.

**Card 012 asked for that comparison and this is its answer.** 012 said a
limit and an axis had not been put beside each other, and worried the 100x
might be excluded. It was not excluded and never had been — **one lens's
number was standing in for six**, and the question dissolves rather than
resolving. Do not re-litigate it; record that it closed this way.

**`run_log.schema.json` gained `verification`, and check 66 reads it**
(`adce7cf`). §4.6.6.1 rule 3 had put a rule on that field since it was
written and the field did not exist.

**Nothing reads either one.** `grep` finds `resolved_from` in no Python file,
and no dispatch writes `verification`. That is this card.

## 0. Re-copy the snapshot first, because the entry you need is in the gap

`envelope/snapshot.json` holds **`kbv-bf4f559baf68`**; the store published
**`kbv-499312508852`**. Check 61 reports you 1 behind and does not fail you —
a consumer may pin deliberately.

**Here the lag is not deliberate and it is exactly the wrong one.** That
publish (`425d1b6`) was made *because* a focus ceiling was being written, and
what it carries is the 40x min/max record and the reference-plane inference —
the two things the ceiling leans on. Resolving against the older snapshot
would miss them.

Copy **committed bytes only**. If the export is modified in the working copy,
wait: a snapshot built from uncommitted bytes has no commit behind it, and
then the one thing the copy exists to establish — which KB version entered
this envelope, and when — is the thing it cannot show. Name the export's
commit in your message. Check 26 verifies the copy against that commit.

## 1. Resolve the lookup at preflight, and refuse when it does not resolve

`operator.load_safety()` reads the file and nothing compares a condition
against it. A limit shaped `{"resolved_from": {"quantity": ..., "keyed_by":
...}}` has no `value` and no `unit`, so anything reading `lim["value"]` will
raise rather than mis-compare — check that is true before you change it, and
keep it true.

**Read the quantity from this agent's `envelope/snapshot.json`, never from
`librarian_agent/kb/`.** The store is the librarian's and the snapshot is
ours (P14). That is also what makes the resolution reproducible: the snapshot
names the commit it was built from.

**The six objectives do not answer in one shape, and the 40x is the case that
matters.** `MRD77400` carries no `working_distance` — it carries
`working_distance_min` **0.16 mm** and `working_distance_max` **0.20 mm**,
because the vendor quotes a range for a correction-collar lens. The other
five carry a point.

**For a floor the near end binds.** A floor answers *how close may it come*,
so a range resolves to its **minimum**. Taking 0.20 would permit 40 um of
approach the vendor never promised. Write the reason in the code, not only
the `min()`.

**If the quantity is absent, refuse.** Not skip, not default, not warn. The
envelope schema says it and `load_safety`'s own docstring already says it for
the file: *absent is not permissive*. A floor that silently disappears when
the lookup misses is the most dangerous failure this file has, because it
fails toward allowing everything — and a floor is where zero is dangerous
while a ceiling is where zero is safe.

**Do not add tolerance.** The limit came from the person; an operator that
widens it is changing an approved number at run time.

Record the resolution in the run log — which objective keyed it, which
quantity, which value, from which `kb_version`. A resolved limit that cannot
be read back later is a limit nobody can audit.

## 2. `preflight` resolves an element to its channel

A plan may name a **channel** or an **element**: *"set the dia lamp"* is the
true statement, and *"set `stand_ti2e`"* would lose which of that channel's
ten elements was meant. Check 38 accepts both against the registry as of
`f78d339`.

**`orchestrator.preflight` accepts only channels.** It looks names up in
`self.channels`, so a plan naming `dia_lamp` or `nosepiece` raises `GapError`
on a perfectly good card. Resolving element to channel is this layer's job
and it is the layer that is missing.

Build the map the same way check 38 does — every channel id, plus every
`elements[].id` pointing at its channel. A name in neither is still a
`GapError` and should stay one.

## 3. A dispatch records whether anyone read the result back

Check 66 went in at `adce7cf` and reads `verification` on each event that
dispatches an irreversible action. Three states, and the distinction between
the first two is the point:

| | |
|---|---|
| field absent | **the run does not stand.** Recording `none` is a statement; recording nothing is not |
| `"none"` | nothing read back. §2.1 rule 8 — no signal, and an absent signal does not permit |
| `"readback"` | the channel's state was **queried after the command and matched what was commanded** |

**A return code is not a read-back.** On the Tweez 300 a zero means the GUI
accepted the text, and six distinct ways a command can be ignored all return
zero (`tweez300_reports_nothing_back`, E3). **An acknowledgement is `none`.**

Check 66 will fail a `readback` claimed on a channel the table marks
`read_back: false` — `laser_combiner` and `optical_tweezers`. Write the field
from what the channel actually did, not from what the command returned.

`orchestrator.record()` already stamps `t_mono` and `time_base`; this rides
next to them.

## 4. One stale line to fix while you are in there

`operator.py:159` tells a caller that `envelope/safety.json` "does not exist
yet". It has existed since `c1404bf` and the person has revised it twice
since. A refusal reason that describes a world two days gone sends whoever
reads it to do the wrong thing.

## Rulings

§10.2's hardware-control-path row is open and `agentic-microscope`'s
`hardware/` is byte-identical on both branches — so it is the settled part of
that project. **If you take anything from it, rule it first** (transfer /
downgrade / drop; a transfer names its A1–A7 slot and the §10.3 rule it
passed).

You may well take nothing: elements and channels are our registry's shape,
and their orchestrator was already **dropped**. Say so if so — a card that
considered items and took none should report that, and the count of drops is
as much of the record as the count of transfers.

You cannot write `tasks/NNN-rulings.md` yourself (the deny list closes
`tasks/**` to you, and that contradiction is this seat's and is raised).
**Report your rulings up in the same sentence that reports the task**, and I
write them. The judgement stays yours.

## Done when

Read every count off a run, and read the tree the run names with it. Do not
read them off this card.

```bash
python3 contracts/validate.py
python3 contracts/validate.py --expect-fail contracts/examples/rejected
```

The first ends `0 failed`. The second must still reject every card and every
group — **a fixture that stops failing means a check stopped working.** Check
61 should stop saying `microscope_agent is 1 behind`. Check 26 should still
say the snapshot holds the bytes the commit it names holds.

Check 66 stays `PASS` with a count while no irreversible action has run; that
is not evidence your dispatch writes the field. **Exercise it yourself** —
the group fixture at `contracts/examples/rejected/check66_irreversible_ran_
unverified/` shows the shape that must fail.

## What this does not open

A resolved ceiling is not a licence to move anything. §4.6.6.1 rule 3 still
holds: **an irreversible action needs a confirmed limit AND a read-back**,
and this limit's `confirmation` is `carried_over` — catalogue values, and
nobody has checked where these lenses focus on this bench. So check 57 will
refuse the first plan that rests an irreversible action on it, and that
refusal is correct. What lifts it is a person at the instrument, not code.
